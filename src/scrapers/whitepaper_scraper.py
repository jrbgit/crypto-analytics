"""
Whitepaper Scraper

This module handles:
- PDF whitepaper extraction using multiple libraries
- Webpage whitepaper content extraction
- Content cleaning and preprocessing
- Hash generation for change detection
"""

import os
import requests
import hashlib
import tempfile
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import sys
from urllib.parse import urljoin, urlparse
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
import fitz  # PyMuPDF
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    logger.warning("pdfplumber not available, using PyMuPDF only")

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    logger.warning("PyPDF2 not available, using PyMuPDF only")

from bs4 import BeautifulSoup


@dataclass
class WhitepaperContent:
    """Container for extracted whitepaper content."""
    url: str
    content_type: str  # 'pdf' or 'webpage'
    title: Optional[str]
    content: str
    word_count: int
    page_count: Optional[int]  # For PDFs
    content_hash: str
    extraction_method: str  # Which library/method was used
    success: bool
    error_message: Optional[str] = None


class WhitepaperScraper:
    """Scraper for extracting content from cryptocurrency whitepapers."""
    
    def __init__(self, 
                 user_agent: str = None,
                 timeout: int = 30,
                 max_file_size: int = 50 * 1024 * 1024):  # 50MB limit
        """
        Initialize the whitepaper scraper.
        
        Args:
            user_agent: Custom user agent string
            timeout: Request timeout in seconds
            max_file_size: Maximum file size to download in bytes
        """
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.timeout = timeout
        self.max_file_size = max_file_size
        
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
        
    def scrape_whitepaper(self, url: str) -> WhitepaperContent:
        """
        Extract content from a whitepaper URL (PDF or webpage).
        
        Args:
            url: URL to the whitepaper
            
        Returns:
            WhitepaperContent object with extracted information
        """
        try:
            logger.info(f"Starting whitepaper extraction for {url}")
            
            # First, check what type of content we're dealing with
            response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
            content_type = response.headers.get('content-type', '').lower()
            
            # Check file size
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_file_size:
                return WhitepaperContent(
                    url=url,
                    content_type='unknown',
                    title=None,
                    content='',
                    word_count=0,
                    page_count=None,
                    content_hash='',
                    extraction_method='none',
                    success=False,
                    error_message=f"File too large: {content_length} bytes"
                )
            
            if 'pdf' in content_type:
                return self._extract_pdf_content(url)
            else:
                return self._extract_webpage_content(url)
                
        except Exception as e:
            logger.error(f"Failed to scrape whitepaper {url}: {e}")
            return WhitepaperContent(
                url=url,
                content_type='unknown',
                title=None,
                content='',
                word_count=0,
                page_count=None,
                content_hash='',
                extraction_method='none',
                success=False,
                error_message=str(e)
            )
    
    def _extract_pdf_content(self, url: str) -> WhitepaperContent:
        """Extract content from a PDF whitepaper."""
        try:
            # Download PDF to temporary file
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name
            
            try:
                # Try multiple extraction methods
                content, method, page_count = self._extract_with_multiple_methods(tmp_path)
                
                if not content.strip():
                    return WhitepaperContent(
                        url=url,
                        content_type='pdf',
                        title=None,
                        content='',
                        word_count=0,
                        page_count=page_count,
                        content_hash='',
                        extraction_method=method,
                        success=False,
                        error_message="No text content extracted from PDF"
                    )
                
                # Clean and process content
                content = self._clean_pdf_content(content)
                title = self._extract_pdf_title(content)
                word_count = len(content.split())
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                
                logger.success(f"Extracted PDF content: {word_count} words, {page_count} pages")
                
                return WhitepaperContent(
                    url=url,
                    content_type='pdf',
                    title=title,
                    content=content,
                    word_count=word_count,
                    page_count=page_count,
                    content_hash=content_hash,
                    extraction_method=method,
                    success=True
                )
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Failed to extract PDF content from {url}: {e}")
            return WhitepaperContent(
                url=url,
                content_type='pdf',
                title=None,
                content='',
                word_count=0,
                page_count=None,
                content_hash='',
                extraction_method='none',
                success=False,
                error_message=str(e)
            )
    
    def _extract_with_multiple_methods(self, pdf_path: str) -> tuple[str, str, int]:
        """Try multiple PDF extraction methods and return the best result."""
        methods = []
        
        # Method 1: PyMuPDF (fitz)
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            methods.append(('pymupdf', text.strip(), doc.page_count))
            logger.debug(f"PyMuPDF extracted {len(text.split())} words")
        except Exception as e:
            logger.debug(f"PyMuPDF failed: {e}")
        
        # Method 2: pdfplumber (if available)
        if HAS_PDFPLUMBER:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    methods.append(('pdfplumber', text.strip(), len(pdf.pages)))
                    logger.debug(f"pdfplumber extracted {len(text.split())} words")
            except Exception as e:
                logger.debug(f"pdfplumber failed: {e}")
        
        # Method 3: PyPDF2 (if available)
        if HAS_PYPDF2:
            try:
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    methods.append(('pypdf2', text.strip(), len(reader.pages)))
                    logger.debug(f"PyPDF2 extracted {len(text.split())} words")
            except Exception as e:
                logger.debug(f"PyPDF2 failed: {e}")
        
        if not methods:
            raise Exception("All PDF extraction methods failed")
        
        # Return the method with the most extracted content
        best_method = max(methods, key=lambda x: len(x[1].split()))
        return best_method[1], best_method[0], best_method[2]
    
    def _extract_webpage_content(self, url: str) -> WhitepaperContent:
        """Extract content from a webpage whitepaper."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'menu']):
                element.decompose()
            
            # Extract title
            title = None
            title_elem = soup.find('title')
            if title_elem:
                title = title_elem.get_text().strip()
            
            # Try to find main content areas
            content_selectors = [
                'main', 'article', '.content', '#content', '.post', '.whitepaper',
                '.document', '.paper', 'section', '.main-content'
            ]
            
            main_content = None
            for selector in content_selectors:
                element = soup.select_one(selector)
                if element:
                    main_content = element
                    break
            
            # Fall back to body if no main content found
            if main_content is None:
                main_content = soup.find('body')
            
            if main_content is None:
                main_content = soup
            
            # Extract text content
            content = main_content.get_text(separator='\n', strip=True)
            content = self._clean_webpage_content(content)
            
            word_count = len(content.split())
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            logger.success(f"Extracted webpage content: {word_count} words")
            
            return WhitepaperContent(
                url=url,
                content_type='webpage',
                title=title,
                content=content,
                word_count=word_count,
                page_count=None,
                content_hash=content_hash,
                extraction_method='beautifulsoup',
                success=True
            )
            
        except Exception as e:
            logger.error(f"Failed to extract webpage content from {url}: {e}")
            return WhitepaperContent(
                url=url,
                content_type='webpage',
                title=None,
                content='',
                word_count=0,
                page_count=None,
                content_hash='',
                extraction_method='none',
                success=False,
                error_message=str(e)
            )
    
    def _clean_pdf_content(self, content: str) -> str:
        """Clean and normalize PDF-extracted content."""
        # Split into lines and clean each line
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines and lines that are too short to be meaningful
            if len(line) < 3:
                continue
            # Skip lines that are mostly numbers/symbols (page numbers, etc.)
            if len([c for c in line if c.isalpha()]) < len(line) * 0.5:
                continue
            cleaned_lines.append(line)
        
        # Join lines back together
        content = '\n'.join(cleaned_lines)
        
        # Remove excessive whitespace
        import re
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r' {2,}', ' ', content)
        
        return content.strip()
    
    def _clean_webpage_content(self, content: str) -> str:
        """Clean and normalize webpage-extracted content."""
        import re
        
        # Remove excessive whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r' {2,}', ' ', content)
        
        # Remove common webpage artifacts
        lines = content.split('\n')
        cleaned_lines = []
        
        skip_patterns = [
            r'cookie', r'privacy policy', r'terms of service',
            r'subscribe', r'newsletter', r'follow us', r'contact us'
        ]
        
        for line in lines:
            line = line.strip()
            if len(line) < 10:  # Skip very short lines
                continue
            
            # Skip lines matching common webpage artifacts
            if any(re.search(pattern, line.lower()) for pattern in skip_patterns):
                continue
                
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    def _extract_pdf_title(self, content: str) -> Optional[str]:
        """Extract title from PDF content."""
        lines = content.split('\n')
        # Look for title in first few lines
        for line in lines[:10]:
            line = line.strip()
            # Skip very short lines
            if len(line) < 10:
                continue
            # Skip lines that are mostly numbers/symbols
            if len([c for c in line if c.isalpha()]) < len(line) * 0.7:
                continue
            # This is likely the title
            return line
        return None


def main():
    """Test the whitepaper scraper."""
    scraper = WhitepaperScraper()
    
    # Test URLs (you can modify these for testing)
    test_urls = [
        "https://bitcoin.org/bitcoin.pdf",  # PDF whitepaper
        "https://ethereum.org/whitepaper/",  # Webpage whitepaper
    ]
    
    for url in test_urls:
        print(f"\n=== Testing {url} ===")
        result = scraper.scrape_whitepaper(url)
        print(f"Success: {result.success}")
        print(f"Content Type: {result.content_type}")
        print(f"Title: {result.title}")
        print(f"Word Count: {result.word_count}")
        print(f"Page Count: {result.page_count}")
        print(f"Method: {result.extraction_method}")
        if result.error_message:
            print(f"Error: {result.error_message}")
        if result.content:
            print(f"Content Preview: {result.content[:200]}...")


if __name__ == "__main__":
    main()