// DOM Elements
const connectionBadge = document.getElementById('connection-badge');
const sessionBadge = document.getElementById('session-badge');
const sessionStatusText = document.getElementById('session-status-text');
const sessionDetails = document.getElementById('session-details');
const dropZone = document.getElementById('drop-zone');
const cookieFileInput = document.getElementById('cookie-file-input');
const bookInput = document.getElementById('book-input');
const downloadBtn = document.getElementById('download-btn');
const progressChecklist = document.getElementById('progress-checklist');
const progressContainer = document.getElementById('progress-container');
const progressBarFill = document.getElementById('progress-bar-fill');
const progressStatusLabel = document.getElementById('progress-status-label');
const progressPercentageText = document.getElementById('progress-percentage-text');
const logConsole = document.getElementById('log-console');
const clearLogsBtn = document.getElementById('clear-logs');
const libraryCount = document.getElementById('library-count');
const libraryGrid = document.getElementById('library-grid');

// Active event source reference
let downloadEventSource = null;

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    loadLibrary();
    setupEventListeners();
    
    // Heartbeat every 8 seconds
    setInterval(checkStatus, 8000);
});

// Set up UI Event Listeners
function setupEventListeners() {
    // Input validation: Enable download button only if there is input
    bookInput.addEventListener('input', () => {
        const hasInput = bookInput.value.trim().length > 0;
        const hasValidSession = sessionBadge.classList.contains('status-active');
        downloadBtn.disabled = !hasInput || !hasValidSession;
    });

    // Handle button download click
    downloadBtn.addEventListener('click', startDownload);

    // Speed slider listener
    const speedSlider = document.getElementById('speed-slider');
    const speedValue = document.getElementById('speed-value');
    if (speedSlider && speedValue) {
        speedSlider.addEventListener('input', () => {
            const val = speedSlider.value;
            speedValue.innerText = `${val} Worker${val !== '1' ? 's' : ''}`;
        });
    }

    // Drop zone click triggers file browser
    dropZone.addEventListener('click', () => cookieFileInput.click());

    // File input change
    cookieFileInput.addEventListener('change', handleFileSelect);

    // Drag-and-drop events
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        }, false);
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
    }, false);

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFileDrop(e);
    }, false);

    // Save Token manually button
    const saveTokenBtn = document.getElementById('save-token-btn');
    const tokenInput = document.getElementById('token-input');
    
    saveTokenBtn.addEventListener('click', async () => {
        const tokenVal = tokenInput.value.trim();
        if (!tokenVal) {
            addLog('Error: Token value cannot be empty.', 'error');
            return;
        }
        
        addLog('Saving pasted token...', 'info');
        
        const params = new URLSearchParams();
        params.append('token', tokenVal);
        
        try {
            const response = await fetch('/api/save-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: params
            });
            
            const data = await response.json();
            if (response.ok) {
                addLog('Token saved successfully.', 'success');
                tokenInput.value = '';
                await checkStatus();
            } else {
                addLog(`Save token failed: ${data.detail || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            addLog(`Save token error: ${error.message}`, 'error');
        }
    });

    // Clear logs button
    clearLogsBtn.addEventListener('click', () => {
        logConsole.innerHTML = '';
        addLog('Console cleared.', 'system');
    });
}

// Log formatting helper
function addLog(message, type = 'info') {
    const line = document.createElement('div');
    line.className = `log-line ${type}-log`;
    
    // Format timestamp
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];
    line.innerText = `[${timeStr}] ${message}`;
    
    logConsole.appendChild(line);
    
    // Auto-scroll to bottom
    logConsole.scrollTop = logConsole.scrollHeight;
}

// Check Server Status and Cookie Status
async function checkStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) throw new Error('Server returned error status');
        
        const data = await response.json();
        
        // Update connection status
        connectionBadge.className = 'badge';
        connectionBadge.querySelector('.pulse-indicator').className = 'pulse-indicator status-online';
        connectionBadge.querySelector('.badge-text').innerText = 'Web Server Active';
        
        // Update credentials badge
        if (data.has_cookies && data.cookie_info.valid) {
            sessionBadge.className = 'status-pill status-active';
            sessionStatusText.innerText = 'Session Loaded';
            
            // Show details
            sessionDetails.innerHTML = `
                <div class="detail-row">
                    <span class="detail-label">Cookie File:</span>
                    <span class="detail-val">cookies.json</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Cookie Count:</span>
                    <span class="detail-val">${data.cookie_info.count}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">JWT Token:</span>
                    <span class="detail-val" style="color: var(--accent-success);">Valid</span>
                </div>
            `;
            
            // Enable download input if book has text
            if (bookInput.value.trim().length > 0) {
                downloadBtn.disabled = false;
            }
        } else {
            sessionBadge.className = 'status-pill status-missing';
            sessionStatusText.innerText = 'No Active Session';
            
            const errMsg = data.cookie_info?.error || 'Missing cookies.json file.';
            sessionDetails.innerHTML = `
                <div class="detail-row" style="color: var(--accent-danger);">
                    <span class="detail-label">Error:</span>
                    <span>${errMsg}</span>
                </div>
            `;
            
            downloadBtn.disabled = true;
        }
        
    } catch (error) {
        // Handle server down
        connectionBadge.className = 'badge status-missing';
        connectionBadge.querySelector('.pulse-indicator').className = 'pulse-indicator status-missing';
        connectionBadge.querySelector('.badge-text').innerText = 'Server Offline';
        
        sessionBadge.className = 'status-pill status-missing';
        sessionStatusText.innerText = 'Server Unreachable';
        downloadBtn.disabled = true;
    }
}

// Handle Cookie File Upload
async function uploadCookieFile(file) {
    addLog(`Uploading credential file: ${file.name} (${file.size} bytes)...`, 'info');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/upload-cookies', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (response.ok) {
            addLog(data.message, 'success');
            await checkStatus();
        } else {
            addLog(`Upload failed: ${data.detail || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        addLog(`Upload connection error: ${error.message}`, 'error');
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        uploadCookieFile(files[0]);
    }
}

function handleFileDrop(e) {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadCookieFile(files[0]);
    }
}

// Load Downloaded Books Library
async function loadLibrary() {
    try {
        const response = await fetch('/api/downloads');
        if (!response.ok) throw new Error();
        
        const books = await response.json();
        libraryCount.innerText = `${books.length} book${books.length !== 1 ? 's' : ''}`;
        
        if (books.length === 0) {
            libraryGrid.innerHTML = `
                <div class="empty-library">
                    <i class="ph-light ph-folder-open empty-icon"></i>
                    <p>No books downloaded yet.</p>
                </div>
            `;
            return;
        }
        
        libraryGrid.innerHTML = '';
        books.forEach(book => {
            const card = document.createElement('div');
            card.className = 'book-card-wrapper';
            
            // Format size
            const sizeMB = (book.size / (1024 * 1024)).toFixed(2);
            
            // Format date
            const modDate = new Date(book.modified * 1000).toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });

            // Extract display title without extension
            const displayTitle = book.filename.replace(/\.(epub|pdf)$/i, '');
            
            card.innerHTML = `
                <div class="book-card-core">
                    <div class="book-info-block">
                        <div class="book-cover-placeholder">
                            <i class="ph-light ${book.format === 'pdf' ? 'ph-file-pdf' : 'ph-book-open'}"></i>
                        </div>
                        <div class="book-details">
                            <h3 class="book-title" title="${displayTitle}">${displayTitle}</h3>
                            <span class="book-meta-sub" title="Added on ${modDate}">Added: ${modDate}</span>
                        </div>
                    </div>
                    <div class="book-card-actions">
                        <span class="book-file-size">${sizeMB} MB</span>
                        <a href="/api/downloads/${encodeURIComponent(book.filename)}" class="btn-card-download" download>
                            <i class="ph-light ${book.format === 'pdf' ? 'ph-file-pdf' : 'ph-download'}"></i>
                            <span>Save ${book.format.toUpperCase()}</span>
                        </a>
                    </div>
                </div>
            `;
            libraryGrid.appendChild(card);
        });
        
    } catch (error) {
        libraryGrid.innerHTML = `
            <div class="empty-library" style="border-color: var(--accent-danger);">
                <i class="ph-light ph-warning empty-icon" style="color: var(--accent-danger);"></i>
                <p>Failed to load downloads library.</p>
            </div>
        `;
    }
}

// Start SSE Download Stream
function startDownload() {
    const bookVal = bookInput.value.trim();
    if (!bookVal) return;
    
    // Prevent starting another download
    downloadBtn.disabled = true;
    bookInput.disabled = true;
    
    const formatSelect = document.getElementById('format-select');
    const speedSlider = document.getElementById('speed-slider');
    
    const format = formatSelect ? formatSelect.value : 'epub';
    const workers = speedSlider ? speedSlider.value : '5';
    
    if (formatSelect) formatSelect.disabled = true;
    if (speedSlider) speedSlider.disabled = true;
    
    // Reset and show progress containers
    progressChecklist.style.display = 'flex';
    progressContainer.style.display = 'flex';
    progressBarFill.style.width = '0%';
    progressPercentageText.innerText = '0%';
    progressStatusLabel.innerText = 'Initializing...';
    
    // Clear checklist item classes
    document.querySelectorAll('.checklist-item').forEach(item => {
        item.className = 'checklist-item';
    });
    
    // Update checklist text for the assembly phase
    const chkEpubText = document.querySelector('#chk-epub .chk-text');
    if (chkEpubText) {
        chkEpubText.innerText = format === 'pdf' ? 'Assembling PDF' : 'Assembling EPUB';
    }
    
    addLog(`Initiating ${format.toUpperCase()} download for: "${bookVal}" with ${workers} workers`, 'info');
    
    // Initialize EventSource
    const streamUrl = `/api/download/stream?book=${encodeURIComponent(bookVal)}&format=${format}&workers=${workers}`;
    downloadEventSource = new EventSource(streamUrl);
    
    // Set active first checklist item
    document.getElementById('chk-metadata').classList.add('active');
    
    downloadEventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleProgressEvent(data);
        } catch (err) {
            addLog(`Error parsing stream event: ${err.message}`, 'error');
        }
    };
    
    downloadEventSource.onerror = (err) => {
        addLog('Download stream disconnected.', 'error');
        terminateStream();
    };
}

// Terminate Stream & Reset Controls
function terminateStream() {
    if (downloadEventSource) {
        downloadEventSource.close();
        downloadEventSource = null;
    }
    
    // Enable inputs
    bookInput.disabled = false;
    const formatSelect = document.getElementById('format-select');
    const speedSlider = document.getElementById('speed-slider');
    if (formatSelect) formatSelect.disabled = false;
    if (speedSlider) speedSlider.disabled = false;
    
    // Check status will decide if downloadBtn is disabled or not
    checkStatus();
}

// Process Download Stream Events
function handleProgressEvent(event) {
    const type = event.event;
    const payload = event.data;
    
    switch (type) {
        case 'status':
            addLog(event.message || payload, 'info');
            break;
            
        case 'metadata':
            addLog(`Metadata loaded: "${payload.title}" by ${payload.authors.join(', ')}`, 'success');
            
            // Update checklist
            const chkMeta = document.getElementById('chk-metadata');
            chkMeta.className = 'checklist-item completed';
            
            const chkChapters = document.getElementById('chk-chapters');
            chkChapters.className = 'checklist-item active';
            chkChapters.querySelector('.chk-text').innerText = 'Downloading chapters (0/?)';
            
            progressStatusLabel.innerText = 'Fetching book information...';
            progressBarFill.style.width = '10%';
            progressPercentageText.innerText = '10%';
            break;
            
        case 'chapters_count':
            addLog(`Total chapters to download: ${payload}`, 'info');
            document.getElementById('chk-chapters').querySelector('.chk-text').innerText = `Downloading chapters (0/${payload})`;
            break;
            
        case 'chapter_download':
            // Update checklist label
            const chkChap = document.getElementById('chk-chapters');
            chkChap.querySelector('.chk-text').innerText = `Downloading chapters (${payload.index}/${payload.total})`;
            
            // Console log on key intervals or start
            if (payload.index === 1 || payload.index % 5 === 0 || payload.index === payload.total) {
                addLog(`Downloaded chapter ${payload.index}/${payload.total}: ${payload.title}`, 'info');
            }
            
            // Percentage maps 10% -> 70% during chapter fetching
            const chapProgress = 10 + Math.floor((payload.index / payload.total) * 60);
            progressBarFill.style.width = `${chapProgress}%`;
            progressPercentageText.innerText = `${chapProgress}%`;
            progressStatusLabel.innerText = `Downloading: ${payload.title}`;
            
            if (payload.index === payload.total) {
                chkChap.className = 'checklist-item completed';
                document.getElementById('chk-images').className = 'checklist-item active';
                document.getElementById('chk-images').querySelector('.chk-text').innerText = 'Downloading images (0/?)';
            }
            break;
            
        case 'images_start':
            addLog(`Extracted ${payload} images to download.`, 'info');
            document.getElementById('chk-images').querySelector('.chk-text').innerText = `Downloading images (0/${payload})`;
            if (payload === 0) {
                // If no images, complete instantly
                document.getElementById('chk-images').className = 'checklist-item completed';
                document.getElementById('chk-cover').className = 'checklist-item active';
            }
            break;
            
        case 'image_download':
            const chkImg = document.getElementById('chk-images');
            chkImg.querySelector('.chk-text').innerText = `Downloading images (${payload.index}/${payload.total})`;
            
            // Map 70% -> 90% during image download
            const imgProgress = 70 + Math.floor((payload.index / payload.total) * 20);
            progressBarFill.style.width = `${imgProgress}%`;
            progressPercentageText.innerText = `${imgProgress}%`;
            progressStatusLabel.innerText = `Fetching image ${payload.index} of ${payload.total}`;
            
            if (payload.index === payload.total) {
                chkImg.className = 'checklist-item completed';
                document.getElementById('chk-cover').className = 'checklist-item active';
            }
            break;
            
        case 'cover_start':
            progressStatusLabel.innerText = 'Fetching cover art...';
            break;
            
        case 'cover_done':
            addLog('Cover art retrieved successfully.', 'success');
            document.getElementById('chk-cover').className = 'checklist-item completed';
            document.getElementById('chk-epub').className = 'checklist-item active';
            progressBarFill.style.width = '92%';
            progressPercentageText.innerText = '92%';
            break;
            
        case 'building_epub':
            progressStatusLabel.innerText = 'Assembling EPUB package structure...';
            progressBarFill.style.width = '95%';
            progressPercentageText.innerText = '95%';
            break;
            
        case 'building_pdf':
            progressStatusLabel.innerText = 'Compiling PDF document structure...';
            progressBarFill.style.width = '95%';
            progressPercentageText.innerText = '95%';
            break;
            
        case 'done':
            addLog(event.message, 'success');
            
            // Set all checklist items as completed
            document.querySelectorAll('.checklist-item').forEach(item => {
                item.className = 'checklist-item completed';
            });
            
            progressBarFill.style.width = '100%';
            progressPercentageText.innerText = '100%';
            progressStatusLabel.innerText = 'Completed!';
            
            // Clear input box
            bookInput.value = '';
            
            // Reload Library list to show the new book
            loadLibrary();
            
            terminateStream();
            break;
            
        case 'error':
            addLog(`Error: ${event.message || payload}`, 'error');
            progressStatusLabel.innerText = 'Download failed.';
            
            // Highlight active checklist item as error
            const activeItem = document.querySelector('.checklist-item.active');
            if (activeItem) {
                activeItem.style.color = 'var(--accent-danger)';
            }
            
            terminateStream();
            break;
            
        default:
            console.log('Unhandled event:', type, payload);
    }
}
