"""Command-line interface for O'Reilly book downloader."""

import re
import sys
from pathlib import Path

import click
from rich.console import Console

from .client import OreillyClient
from .cookie_auth import load_cookies
from .epub import create_epub

console = Console()


def extract_book_id(book_input: str) -> str:
    """Extract book ID from URL or direct input."""
    url_pattern = r"learning\.oreilly\.com/library/view/[^/]+/(\d+)"
    match = re.search(url_pattern, book_input)
    if match:
        return match.group(1)

    if re.match(r"^\d+$", book_input):
        return book_input

    isbn_match = re.search(r"(\d{10,13})", book_input)
    if isbn_match:
        return isbn_match.group(1)

    return book_input


def sanitize_filename(name: str) -> str:
    """Create a safe filename from book title."""
    safe = re.sub(r'[<>:"/\\|?*]', "", name)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe[:100]


@click.command()
@click.argument("book", required=False)
@click.option(
    "-c",
    "--cookies",
    type=click.Path(exists=True, path_type=Path),
    help="Path to cookies.json file",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output path (defaults to ./downloads/<title>.<format>)",
)
@click.option(
    "-f",
    "--format",
    type=click.Choice(["epub", "pdf"], case_sensitive=False),
    default="epub",
    help="Output format (epub or pdf, defaults to epub)",
)
@click.option(
    "--ui",
    is_flag=True,
    help="Start Web UI server",
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Host to bind the Web UI server to",
)
@click.option(
    "--port",
    type=int,
    default=8000,
    help="Port to run the Web UI server on",
)
def main(
    book: str | None,
    cookies: Path | None,
    output: Path | None,
    format: str,
    ui: bool,
    host: str,
    port: int,
) -> None:
    """Download O'Reilly books as EPUB.

    BOOK can be a book ID or full O'Reilly URL.

    \b
    Examples:
        oreilly-dl 9781098166298 -c cookies.json
        oreilly-dl "https://learning.oreilly.com/library/view/book/9781098166298/" -c cookies.json
        oreilly-dl --ui
    """
    if ui:
        console.print("[bold green]Starting O'Reilly EPUB Downloader Web UI...[/]")
        console.print(f"[bold]Address:[/] http://{host}:{port}")

        import threading
        import webbrowser
        import time

        def open_browser():
            time.sleep(1.0)
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=open_browser, daemon=True).start()

        import uvicorn
        # Import app directly to avoid string lookup issues
        from .server import app
        uvicorn.run(app, host=host, port=port, log_level="info")
        return

    if not book:
        console.print("[bold red]Error:[/] Missing book ID or URL. Provide BOOK or run with [bold]--ui[/] flag.")
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        sys.exit(1)

    if not cookies:
        console.print("[bold red]Error:[/] Missing option '-c' / '--cookies'. A cookie file is required for command-line download.")
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        sys.exit(1)

    book_id = extract_book_id(book)
    console.print(f"[bold]Downloading book:[/] {book_id}")

    try:
        session = load_cookies(cookies)

        with OreillyClient(session) as client:
            book_data = client.get_book(book_id)

        fmt = format.lower()
        if output:
            output_path = output if output.suffix == f".{fmt}" else output.with_suffix(f".{fmt}")
        else:
            downloads = Path("downloads")
            downloads.mkdir(exist_ok=True)
            safe_title = sanitize_filename(book_data.metadata.title)
            output_path = downloads / f"{safe_title}.{fmt}"

        if fmt == "pdf":
            from .pdf_generator import create_pdf
            create_pdf(book_data, output_path)
        else:
            create_epub(book_data, output_path)
        console.print(f"\n[bold green]Done:[/] {output_path}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
