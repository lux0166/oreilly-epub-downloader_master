# O'Reilly EPUB & PDF Downloader

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

A premium utility and Web UI to download O'Reilly books as EPUB or PDF for offline reading. Features include:
- **Web UI & CLI**: Run in your terminal or start the dashboard server.
- **Multi-threaded Downloading**: Configurable worker pools for rapid chapter and image downloads.
- **EPUB & PDF Formats**: Compile books into standard EPUB packages or print-styled PDF files.
- **EZProxy / Institutional Library Gateway**: Automatically detects and routes API calls through your institutional library proxy domain using session cookies.
- **Reliable PDF Engine**: Includes BeautifulSoup table-cell sanitization and a ReportLab layout monkeypatch to prevent negative width rendering crashes on dense columns.

---

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/lux0166/oreilly-epub-downloader.git
   cd oreilly-epub-downloader
   ```

2. Install the package in editable mode:
   ```bash
   pip install -e .
   ```

---

## Web UI Dashboard

Start the local web dashboard:
```bash
# Starts on default port 8000
oreilly-dl --ui

# Starts on custom port 8050
oreilly-dl --ui --port 8050
```
This automatically opens your browser at `http://127.0.0.1:8000`. Inside the dashboard you can:
- Drag and drop `cookies.json` or paste your raw `orm-jwt` token directly.
- Input book IDs or URLs.
- Choose between **EPUB** and **PDF** formats.
- Slide the **Speed slider** to adjust download concurrency (1 to 10 workers).
- View real-time download checklist progress and log consoles.
- Access the Downloaded Books Library card deck to directly download or preview your files.

---

## Command Line Usage

### 1. Export cookies from O'Reilly

#### Method A: Cookie-Editor Extension (Easiest)
1. Install the **Cookie-Editor** browser extension ([Chrome Web Store](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhceonfjogjjoaoakdhinep) / [Firefox Add-ons](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/)).
2. Log into your account (standard `learning.oreilly.com` or via your institutional/library proxy portal).
3. Click the extension icon, click **Export**, and select **JSON** to copy the cookies to your clipboard.
4. Save the clipboard contents to a file named `cookies.json` in this project directory.

#### Method B: Browser Console
1. Log into your account (standard `learning.oreilly.com` or via your institutional/library proxy login).
2. Open Developer Tools (F12 / `Cmd+Option+I`).
3. In the **Console** tab, run:
   ```javascript
   JSON.stringify(Object.fromEntries(document.cookie.split('; ').map(c => c.split('='))))
   ```
4. Copy the JSON output string and save it to a file named `cookies.json`.

### 2. Download books

```bash
# Download as EPUB (Default)
oreilly-dl 9781098166298 -c cookies.json

# Download as PDF
oreilly-dl 9781098166298 -c cookies.json --format pdf

# By URL
oreilly-dl "https://learning.oreilly.com/library/view/ai-engineering/9781098166298/" -c cookies.json --format pdf

# Custom output path
oreilly-dl 9781098166298 -c cookies.json --format pdf -o "custom_folder/AI_Engineering.pdf"
```

Books are saved to the `./downloads/` folder by default.

---

## Finding Book IDs

The book ID is the number sequence in the book page URL:
- URL: `https://learning.oreilly.com/library/view/ai-engineering/9781098166298/`
- Book ID: `9781098166298`

---

## Requirements

- Python 3.11+
- Active O'Reilly subscription (personal or institutional library card)
