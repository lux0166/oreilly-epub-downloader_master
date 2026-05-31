"""PDF generation from O'Reilly book content."""

import base64
import logging
from pathlib import Path
from bs4 import BeautifulSoup
from xhtml2pdf import pisa

from .models import Book

logger = logging.getLogger("oreilly-pdf")


def create_pdf(book: Book, output_path: Path) -> Path:
    """Create a PDF file from book content.

    Args:
        book: Complete book with metadata and chapters
        output_path: Path to save the PDF file

    Returns:
        Path to the created PDF file
    """
    logger.info(f"Creating PDF: {book.metadata.title}")

    # Monkeypatch ReportLab Table._listCellGeom to prevent negative availWidth ValueError due to floating point precision errors
    try:
        from reportlab.platypus.tables import Table
        original_listCellGeom = Table._listCellGeom

        def patched_listCellGeom(self, V, w, s, *args, **kwargs):
            min_w = s.leftPadding + s.rightPadding
            if w is not None and w < min_w:
                w = min_w + 0.0001
            return original_listCellGeom(self, V, w, s, *args, **kwargs)

        Table._listCellGeom = patched_listCellGeom
        logger.info("Successfully patched ReportLab Table._listCellGeom")
    except Exception as patch_err:
        logger.warning(f"Failed to patch ReportLab: {patch_err}")

    # Build lookup map for images (filename -> Image)
    filename_to_image = {img.filename: img for img in book.images.values()}

    # CSS styles optimized for print/PDF
    style_content = """
    @page {
        size: A4;
        @frame content_frame {
            left: 2cm;
            width: 17cm;
            top: 2cm;
            height: 24.5cm;
        }
        @frame footer_frame {
            -pdf-frame-content: footer_content;
            left: 2cm;
            width: 17cm;
            bottom: 1cm;
            height: 1cm;
        }
    }
    body {
        font-family: Georgia, "Times New Roman", serif;
        font-size: 10.5pt;
        line-height: 1.6;
        color: #111111;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: Helvetica, Arial, sans-serif;
        color: #111111;
        page-break-after: avoid;
    }
    h1 {
        font-size: 24pt;
        margin-top: 0;
        margin-bottom: 20pt;
        border-bottom: 1px solid #eeeeee;
        padding-bottom: 8pt;
        text-align: center;
    }
    h2 {
        font-size: 18pt;
        margin-top: 24pt;
        margin-bottom: 12pt;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 4pt;
    }
    h3 {
        font-size: 14pt;
        margin-top: 20pt;
        margin-bottom: 10pt;
    }
    p {
        margin-top: 0;
        margin-bottom: 10pt;
        text-align: justify;
    }
    pre {
        background-color: #f5f6f8;
        border: 1px solid #e1e3e6;
        padding: 8pt;
        font-family: monospace;
        font-size: 9.5pt;
        margin-bottom: 12pt;
        white-space: pre-wrap;
    }
    code {
        background-color: #f5f6f8;
        font-family: monospace;
        font-size: 9.5pt;
        padding: 1pt 3pt;
    }
    ul, ol {
        margin-bottom: 12pt;
        padding-left: 20pt;
    }
    li {
        margin-bottom: 4pt;
    }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 15pt auto;
    }
    blockquote {
        border-left: 4px solid #dddddd;
        padding-left: 10pt;
        margin-left: 0;
        margin-right: 0;
        font-style: italic;
        color: #555555;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin-bottom: 15pt;
    }
    th, td {
        border: 1px solid #dddddd;
        padding: 6pt;
        text-align: left;
    }
    th {
        background-color: #f5f6f8;
        font-weight: bold;
    }
    .chapter-container {
        page-break-before: always;
    }
    .cover-container {
        text-align: center;
        padding-top: 5cm;
        height: 100%;
    }
    .book-title {
        font-family: Helvetica, Arial, sans-serif;
        font-size: 28pt;
        font-weight: bold;
        margin-bottom: 15pt;
        color: #111111;
    }
    .book-authors {
        font-size: 16pt;
        color: #555555;
        margin-bottom: 30pt;
    }
    .book-publisher {
        font-size: 12pt;
        color: #888888;
        margin-top: 5cm;
    }
    """

    # Build HTML document structure
    html_parts = []
    html_parts.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
    html_parts.append(f"<style>{style_content}</style>")
    html_parts.append(f"<title>{book.metadata.title}</title></head><body>")
    html_parts.append('<div id="footer_content" style="text-align: right; font-family: Helvetica, Arial, sans-serif; font-size: 9pt; color: #777777;">Page <pdf:pagenumber /></div>')

    # Add Cover Page
    if book.cover_image:
        b64_cover = base64.b64encode(book.cover_image).decode("utf-8")
        cover_mime = "image/jpeg"
        # Guess mime type if possible from magic bytes
        if book.cover_image[:8] == b"\x89PNG\r\n\x1a\n":
            cover_mime = "image/png"
        html_parts.append(
            f'<div class="cover-container" style="page-break-after: always; text-align: center;">'
            f'<h1 class="book-title">{book.metadata.title}</h1>'
            f'<div class="book-authors">By {", ".join(book.metadata.authors)}</div>'
            f'<img src="data:{cover_mime};base64,{b64_cover}" style="max-height: 14cm; max-width: 10cm; margin-bottom: 2cm;" />'
            f'<div class="book-publisher">{book.metadata.publisher}</div>'
            f'</div>'
        )
    else:
        # Text cover fallback
        html_parts.append(
            f'<div class="cover-container" style="page-break-after: always; text-align: center;">'
            f'<h1 class="book-title" style="margin-top: 10cm;">{book.metadata.title}</h1>'
            f'<div class="book-authors">By {", ".join(book.metadata.authors)}</div>'
            f'<div class="book-publisher" style="margin-top: 5cm;">{book.metadata.publisher}</div>'
            f'</div>'
        )

    # Process each chapter
    for chapter in book.chapters:
        if not chapter.html_content or not chapter.html_content.strip():
            continue
        if len(chapter.html_content.strip()) < 50:
            continue

        chapter_soup = BeautifulSoup(chapter.html_content, "lxml")

        # Clean up block elements inside tables to prevent xhtml2pdf PmlKeepInFrame crashes
        for cell in chapter_soup.find_all(["td", "th"]):
            blocks = list(cell.find_all(["p", "div", "pre", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"]))
            for block in reversed(blocks):
                try:
                    if block.name == "pre":
                        text_content = block.get_text()
                        new_content = BeautifulSoup("".join(f"{line}<br/>" for line in text_content.splitlines()), "lxml")
                        block.replace_with(new_content)
                    elif block.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                        span = chapter_soup.new_tag("span", style="font-weight: bold;")
                        span.string = block.get_text()
                        block.replace_with(span)
                    else:
                        block.unwrap()
                except Exception:
                    pass

        # Rewrite image URLs to Base64 data URIs
        for img_tag in chapter_soup.find_all("img"):
            src = img_tag.get("src", "")
            if src in filename_to_image:
                img_data = filename_to_image[src]
                if img_data.data:
                    b64_data = base64.b64encode(img_data.data).decode("utf-8")
                    img_tag["src"] = f"data:{img_data.media_type};base64,{b64_data}"

        # Extract body content
        body_tag = chapter_soup.find("body")
        if body_tag:
            body_content = "".join(str(child) for child in body_tag.children)
        else:
            body_content = str(chapter_soup)

        html_parts.append(
            f'<div class="chapter-container">'
            f'<h1>{chapter.title}</h1>'
            f'{body_content}'
            f'</div>'
        )

    html_parts.append("</body></html>")
    full_html = "".join(html_parts)

    # Ensure parent output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Compile HTML to PDF via xhtml2pdf
    with open(output_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(full_html, dest=pdf_file)

    if pisa_status.err:
        logger.error(f"Error compiling PDF: {pisa_status.err}")

    logger.info(f"PDF successfully saved to: {output_path}")
    return output_path
