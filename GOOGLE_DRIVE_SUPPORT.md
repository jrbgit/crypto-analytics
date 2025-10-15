# Google Drive Whitepaper Support

## Overview
The whitepaper scraper now supports extracting content from Google Drive files, which is common for cryptocurrency whitepapers hosted on Google Drive.

## Supported URL Formats

The scraper recognizes and processes these Google Drive URL patterns:
```
https://drive.google.com/file/d/{FILE_ID}/view
https://drive.google.com/file/d/{FILE_ID}/edit
https://drive.google.com/file/d/{FILE_ID}
```

**Example:**
```
https://drive.google.com/file/d/1I-NmSnQ6E7wY1nyouuf-GuDdJWNCnJWl/view
```

## How It Works

### 1. URL Detection & Processing
- **URL Filter Updated**: Google Drive file URLs are no longer blocked
- **File ID Extraction**: Extracts the unique file ID from the URL
- **Direct Download**: Converts to direct download URL format

### 2. Download Methods

**Method 1: Direct Download**
```python
https://drive.google.com/uc?id={FILE_ID}&export=download
```

**Method 2: Large File Handling** (when virus scan appears)
```python
https://drive.google.com/uc?id={FILE_ID}&export=download&confirm=t
```

### 3. Content Type Detection
- Automatically detects PDF vs HTML content
- Uses content headers and file signatures (`%PDF` for PDFs)
- Routes to appropriate extraction method

### 4. Extraction Methods

**For PDF Files:**
- Downloads to temporary file
- Uses existing multi-method PDF extraction (PyMuPDF, pdfplumber)
- Cleans and processes content same as regular PDFs

**For HTML/Web Content:**
- Extracts text using BeautifulSoup
- Removes unwanted elements (scripts, styles, etc.)
- Applies webpage content cleaning

## Features

### ✅ **What Works**
- **PDF Whitepapers**: Full text extraction with word/page counts
- **HTML Documents**: Webpage content extraction and cleaning  
- **Large Files**: Handles Google Drive virus scan warnings
- **Error Handling**: Graceful fallbacks and detailed error messages
- **Metadata**: Extracts titles, calculates content hashes
- **Multiple Methods**: Same robust PDF extraction as regular files

### ⚠️ **Limitations**
- **Private Files**: Cannot access files without public sharing
- **Permission Required**: Files must be set to "Anyone with link can view"
- **File Size**: Subject to Google Drive download limits
- **Rate Limiting**: Google Drive may throttle requests

## Error Handling

### Common Scenarios Handled

**File ID Extraction Failure:**
```
Error: "Could not extract Google Drive file ID from URL"
```

**Access Denied:**
```
Error: "HTTP 403 - File may be private or sharing is restricted"
```

**Virus Scan Warning:**
```
Info: "Google Drive virus scan detected, trying alternative method"
```

**Large File Processing:**
```
Info: "Trying large file download with confirmation"
```

## Usage in Analytics Pipeline

### Before (Blocked)
```bash
ERROR | Whitepaper scraping failed: URL filtered: Problematic domain pattern: drive.google.com
```

### After (Working)
```bash
INFO  | Processing Google Drive URL: https://drive.google.com/file/d/...
DEBUG | Attempting Google Drive direct download: https://drive.google.com/uc?id=...
SUCCESS | Extracted Google Drive PDF content: 2847 words, 12 pages
```

## Configuration

### No Additional Setup Required
- Uses existing WhitepaperScraper configuration
- Same timeout and file size limits apply
- Uses existing PDF extraction libraries

### Recommended Settings
```python
scraper = WhitepaperScraper(
    timeout=30,              # Allow extra time for Google Drive
    max_file_size=50*1024*1024  # 50MB limit still applies
)
```

## Testing

### Test Google Drive URL Processing
```python
from scrapers.whitepaper_scraper import WhitepaperScraper

scraper = WhitepaperScraper()
url = "https://drive.google.com/file/d/YOUR_FILE_ID/view"

# Test URL detection
print("Is Google Drive:", scraper._is_google_drive_url(url))
print("File ID:", scraper._extract_google_drive_file_id(url))

# Test full extraction
result = scraper.scrape_whitepaper(url)
print("Success:", result.success)
print("Word Count:", result.word_count)
```

### URL Filter Testing
```python
from utils.url_filter import url_filter

url = "https://drive.google.com/file/d/YOUR_FILE_ID/view"
should_skip, reason = url_filter.should_skip_url(url)
print("Should skip:", should_skip)  # Should be False
```

## Implementation Details

### File ID Extraction
Uses regex pattern to extract file ID:
```python
r'/file/d/([a-zA-Z0-9_-]+)'
```

### Direct Download URL Generation
Converts sharing URL to download URL:
```python
f"https://drive.google.com/uc?id={file_id}&export=download"
```

### Virus Scan Handling
For large files that trigger virus scan warnings:
```python
f"https://drive.google.com/uc?id={file_id}&export=download&confirm=t"
```

## Benefits

1. **Expanded Coverage**: Can now process whitepapers hosted on Google Drive
2. **Robust Extraction**: Same multi-method PDF processing as regular files
3. **Graceful Handling**: Proper error messages and fallback methods
4. **No Breaking Changes**: Existing functionality unchanged
5. **Common Use Case**: Many crypto projects host whitepapers on Google Drive

## Common Issues & Solutions

### Issue: "File not found" or 403 errors
**Solution**: Ensure the Google Drive file is shared publicly:
1. Open the file in Google Drive
2. Click "Share" 
3. Set to "Anyone with the link can view"
4. Use the sharing URL in your analytics

### Issue: Large file virus scan warning
**Solution**: Automatic handling implemented - scraper will try alternative download method

### Issue: Empty content extracted
**Check**: 
- File is actually a PDF or HTML document
- File contains text content (not just images)
- File permissions allow access

This implementation makes the whitepaper scraper much more versatile for handling cryptocurrency whitepapers commonly shared via Google Drive.