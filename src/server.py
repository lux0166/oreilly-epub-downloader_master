"""FastAPI backend server for O'Reilly EPUB Downloader Web UI."""

import asyncio
import json
import logging
import queue
import threading
from pathlib import Path
from typing import Any, Generator

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .cli import extract_book_id, sanitize_filename
from .client import OreillyClient
from .cookie_auth import load_cookies
from .epub import create_epub

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oreilly-ui")

app = FastAPI(title="O'Reilly EPUB Downloader Web UI")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = ROOT_DIR / "downloads"
COOKIES_FILE = ROOT_DIR / "cookies.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Ensure directories exist
DOWNLOADS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serve the main UI page."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse(
            "<h1>Web UI is building...</h1><p>Please refresh in a moment.</p>",
            status_code=503,
        )
    return FileResponse(index_path)


@app.get("/api/status")
def get_status():
    """Get the current configuration and cookie status."""
    has_cookies = COOKIES_FILE.exists()
    cookie_info = {}

    if has_cookies:
        try:
            # Load cookies to verify they are valid
            session = load_cookies(COOKIES_FILE)
            cookie_info = {
                "valid": True,
                "count": len(session.cookies),
                "has_jwt": "orm-jwt" in session.cookies,
            }
        except Exception as e:
            cookie_info = {
                "valid": False,
                "error": str(e),
            }
    else:
        cookie_info = {
            "valid": False,
            "error": "No cookies.json file found.",
        }

    return {
        "has_cookies": has_cookies,
        "cookie_info": cookie_info,
        "downloads_count": len(list(DOWNLOADS_DIR.glob("*.epub"))) + len(list(DOWNLOADS_DIR.glob("*.pdf"))),
    }


@app.post("/api/upload-cookies")
async def upload_cookies(file: UploadFile = File(...)):
    """Upload and validate cookies.json file."""
    try:
        content = await file.read()
        logger.info(f"Uploaded file: {file.filename}, received size: {len(content)} bytes")
        text = content.decode("utf-8", errors="ignore")
        logger.info(f"Decoded text content: {repr(text)}")
        
        cookies = {}
        
        # Clean outer quotes (common when copy-pasting console output)
        text = text.strip()
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1].strip()
        if text.startswith('"') and text.endswith('"'):
            try:
                decoded = json.loads(text)
                if isinstance(decoded, str):
                    text = decoded.strip()
            except Exception:
                text = text[1:-1].strip()

        cookies = {}
        proxy_base_url = None
        
        # Try JSON parsing first
        try:
            data = json.loads(text)
            if isinstance(data, str):
                data = json.loads(data)
                
            if isinstance(data, dict):
                cookies = data
            elif isinstance(data, list):
                for c in data:
                    domain = c.get("domain", "")
                    if "learning-oreilly-com" in domain:
                        domain = domain.lstrip('.')
                        proxy_base_url = f"https://{domain}/"
                        break
                cookies = {c["name"]: c["value"] for c in data if "name" in c}
            else:
                raise ValueError("Invalid cookie format. Must be JSON object or list.")
        except json.JSONDecodeError:
            # Fallback: Parse Netscape cookie format (tab-separated)
            parsed = {}
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain = parts[0].lstrip('.')
                    if "learning-oreilly-com" in domain:
                        proxy_base_url = f"https://{domain}/"
                    # Netscape format: domain, flag, path, secure, expiration, name, value
                    name = parts[5]
                    value = parts[6]
                    parsed[name] = value
                elif len(parts) >= 2:
                    # Simple tab-delimited name-value format
                    parsed[parts[0]] = parts[1]
            cookies = parsed
            
            if not cookies:
                raise ValueError("Could not parse file. Please upload a valid JSON or Netscape cookie file.")

        if "orm-jwt" not in cookies and "ezproxy" not in cookies and "ezproxyn" not in cookies:
            raise ValueError("Missing O'Reilly credentials. Make sure you are logged into O'Reilly (missing 'orm-jwt' or library 'ezproxy' cookies).")

        if proxy_base_url:
            cookies["__proxy_base_url__"] = proxy_base_url
            logger.info(f"Detected proxy base URL: {proxy_base_url}")

        # Save cookies.json
        COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
        return {"status": "success", "message": "Cookies uploaded and saved successfully."}

    except json.JSONDecodeError as e:
        logger.exception("JSON decode error during cookie upload")
        raise HTTPException(status_code=400, detail="Invalid JSON file format.")
    except Exception as e:
        logger.exception("Unexpected error during cookie upload")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/save-token")
def save_token(token: str = Form(...)):
    """Save raw orm-jwt token directly."""
    try:
        token = token.strip()
        # Clean outer quotes if pasted with them
        if token.startswith("'") and token.endswith("'"):
            token = token[1:-1].strip()
        if token.startswith('"') and token.endswith('"'):
            token = token[1:-1].strip()

        if not token:
            raise ValueError("Token cannot be empty.")

        cookies = {"orm-jwt": token}
        COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
        return {"status": "success", "message": "Token saved successfully."}
    except Exception as e:
        logger.exception("Unexpected error during token save")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/downloads")
def list_downloads():
    """List all downloaded EPUB and PDF files."""
    downloads = []
    for filepath in list(DOWNLOADS_DIR.glob("*.epub")) + list(DOWNLOADS_DIR.glob("*.pdf")):
        stat = filepath.stat()
        downloads.append({
            "filename": filepath.name,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "format": filepath.suffix[1:], # "epub" or "pdf"
        })
    # Sort by modified time (newest first)
    downloads.sort(key=lambda x: x["modified"], reverse=True)
    return downloads


@app.get("/api/downloads/{filename}")
def get_download(filename: str):
    """Download a specific EPUB or PDF file."""
    filepath = DOWNLOADS_DIR / filename
    if not filepath.exists() or not filepath.is_relative_to(DOWNLOADS_DIR):
        raise HTTPException(status_code=404, detail="File not found")
    
    media_type = "application/epub+zip"
    if filepath.suffix == ".pdf":
        media_type = "application/pdf"
        
    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename,
    )


@app.get("/api/download/stream")
def download_stream(book: str, format: str = "epub", workers: int = 5):
    """Start downloader and stream progress via Server-Sent Events."""
    if not book:
        raise HTTPException(status_code=400, detail="Book ID or URL is required")

    q = queue.Queue()

    def run_download_thread():
        try:
            if not COOKIES_FILE.exists():
                q.put({"event": "error", "message": "cookies.json not found. Please upload your O'Reilly cookies first."})
                return

            session = load_cookies(COOKIES_FILE)
            book_id = extract_book_id(book)
            
            q.put({"event": "status", "message": f"Resolved book ID: {book_id}"})
            q.put({"event": "status", "message": "Connecting to O'Reilly API..."})

            def progress_callback(event_type: str, data: Any):
                q.put({"event": event_type, "data": data})

            # Pass workers dynamically to OreillyClient
            with OreillyClient(session, progress_callback=progress_callback, max_workers=workers) as client:
                book_data = client.get_book(book_id)

            q.put({"event": "status", "message": f"Chapters and images downloaded. Building {format.upper()}..."})
            q.put({"event": "building_epub" if format == "epub" else "building_pdf", "message": f"Generating {format.upper()}..."})
            
            safe_title = sanitize_filename(book_data.metadata.title)
            
            if format == "pdf":
                from .pdf_generator import create_pdf
                output_path = DOWNLOADS_DIR / f"{safe_title}.pdf"
                create_pdf(book_data, output_path)
            else:
                output_path = DOWNLOADS_DIR / f"{safe_title}.epub"
                create_epub(book_data, output_path)

            q.put({
                "event": "done",
                "message": f"Successfully downloaded: {book_data.metadata.title}",
                "filename": f"{safe_title}.{format}"
            })

        except Exception as e:
            logger.exception("Error in downloader thread")
            q.put({"event": "error", "message": str(e)})
        finally:
            q.put(None)

    # Start thread
    thread = threading.Thread(target=run_download_thread, daemon=True)
    thread.start()

    async def event_generator() -> Generator[str, None, None]:
        while True:
            # Retrieve progress events from the Queue in a non-blocking way
            item = await asyncio.to_thread(q.get)
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Mount static files directory if we want direct links to CSS/JS
# Note: we mount it last so that index route '/' doesn't get overridden by it.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
