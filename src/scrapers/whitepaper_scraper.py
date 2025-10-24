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
from typing import Optional, Dict, Any, List
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
    logger.debug("pdfplumber library loaded successfully")
except ImportError:
    HAS_PDFPLUMBER = False
    logger.info("pdfplumber not available - falling back to PyMuPDF for PDF extraction")
    logger.debug("To install pdfplumber: pip install pdfplumber")

try:
    import PyPDF2

    HAS_PYPDF2 = True
    logger.debug("PyPDF2 library loaded successfully")
except ImportError:
    HAS_PYPDF2 = False
    logger.info(
        "PyPDF2 not available - falling back to PyMuPDF and pdfplumber for PDF extraction"
    )
    logger.debug("To install PyPDF2: pip install PyPDF2")

from bs4 import BeautifulSoup

# Import URL filter
from utils.url_filter import url_filter


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

    def __init__(
        self,
        user_agent: str = None,
        timeout: int = 30,
        max_file_size: int = 50 * 1024 * 1024,
    ):  # 50MB limit
        """
        Initialize the whitepaper scraper.

        Args:
            user_agent: Custom user agent string
            timeout: Request timeout in seconds
            max_file_size: Maximum file size to download in bytes
        """
        self.user_agent = (
            user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.timeout = timeout
        self.max_file_size = max_file_size

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        # Log PDF extraction capabilities
        self._log_pdf_extraction_capabilities()

    def _log_pdf_extraction_capabilities(self):
        """Log available PDF extraction capabilities."""
        available_methods = []
        if HAS_PDFPLUMBER:
            available_methods.append("pdfplumber")
        if HAS_PYPDF2:
            available_methods.append("PyPDF2")
        available_methods.append("PyMuPDF")  # Always available

        logger.info(f"PDF extraction methods available: {', '.join(available_methods)}")

        if not HAS_PDFPLUMBER and not HAS_PYPDF2:
            logger.warning(
                "Only PyMuPDF available for PDF extraction - consider installing pdfplumber and PyPDF2 for better extraction reliability"
            )

    def scrape_whitepaper(self, url: str) -> WhitepaperContent:
        """
        Extract content from a whitepaper URL (PDF or webpage) with 404 fallback strategies.

        Args:
            url: URL to the whitepaper

        Returns:
            WhitepaperContent object with extracted information
        """
        logger.info(f"Starting whitepaper extraction for {url}")

        # Try the original URL first
        result = self._attempt_whitepaper_extraction(url)

        # If we got a 404, try alternative URLs
        if not result.success and "404" in result.error_message:
            alternative_urls = self._generate_alternative_urls(url)

            for alt_url in alternative_urls:
                logger.info(f"Trying alternative URL for 404 fallback: {alt_url}")
                alt_result = self._attempt_whitepaper_extraction(alt_url)

                if alt_result.success:
                    logger.success(
                        f"Successfully retrieved whitepaper from alternative URL: {alt_url}"
                    )
                    # Update the URL in the result to reflect the successful alternative
                    alt_result.url = url  # Keep original URL for tracking purposes
                    alt_result.extraction_method = (
                        f"{alt_result.extraction_method}_from_alternative_url"
                    )
                    return alt_result
                elif "404" not in alt_result.error_message:
                    # If we get a different error (not 404), it might be worth trying
                    logger.debug(
                        f"Alternative URL {alt_url} failed with non-404 error: {alt_result.error_message}"
                    )

            logger.warning(f"All alternative URLs failed for {url}")

        return result

    def _generate_alternative_urls(self, original_url: str) -> List[str]:
        """
        Generate alternative URLs to try when original returns 404.

        Args:
            original_url: The original URL that returned 404

        Returns:
            List of alternative URLs to try
        """
        alternatives = []
        parsed = urlparse(original_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.rstrip("/")

        # Strategy 1: Try common variations of the filename
        if path.endswith(".pdf"):
            # Remove .pdf and try different variations
            base_name = path[:-4]  # Remove .pdf
            alternatives.extend(
                [
                    f"{base_domain}{base_name}-whitepaper.pdf",
                    f"{base_domain}{base_name}_whitepaper.pdf",
                    f"{base_domain}/whitepaper{base_name}.pdf",
                    f"{base_domain}/docs{base_name}.pdf",
                    f"{base_domain}/assets{base_name}.pdf",
                ]
            )

            # Try in common directories
            filename = path.split("/")[-1]
            alternatives.extend(
                [
                    f"{base_domain}/whitepaper/{filename}",
                    f"{base_domain}/docs/{filename}",
                    f"{base_domain}/assets/{filename}",
                    f"{base_domain}/papers/{filename}",
                    f"{base_domain}/static/{filename}",
                    f"{base_domain}/files/{filename}",
                ]
            )

        # Strategy 2: Try common whitepaper names
        common_names = [
            "/whitepaper.pdf",
            "/whitepaper-en.pdf",
            "/whitepaper_en.pdf",
            "/white-paper.pdf",
            "/white_paper.pdf",
            "/paper.pdf",
            "/litepaper.pdf",
            "/technical-paper.pdf",
            "/technical_paper.pdf",
        ]

        for name in common_names:
            alternatives.append(f"{base_domain}{name}")
            # Also try in common directories
            alternatives.extend(
                [
                    f"{base_domain}/docs{name}",
                    f"{base_domain}/assets{name}",
                    f"{base_domain}/static{name}",
                ]
            )

        # Strategy 3: Try web.archive.org (Wayback Machine)
        # This is a last resort as it may be slow
        alternatives.append(f"https://web.archive.org/web/*/{original_url}")

        # Strategy 4: For webpage URLs, try different page variations
        if not path.endswith(".pdf"):
            alternatives.extend(
                [
                    f"{base_domain}/whitepaper",
                    f"{base_domain}/white-paper",
                    f"{base_domain}/litepaper",
                    f"{base_domain}/docs/whitepaper",
                    f"{base_domain}/documentation",
                    f"{base_domain}/paper",
                ]
            )

        # Remove duplicates while preserving order
        seen = set()
        unique_alternatives = []
        for alt in alternatives:
            if alt != original_url and alt not in seen:
                seen.add(alt)
                unique_alternatives.append(alt)

        logger.debug(
            f"Generated {len(unique_alternatives)} alternative URLs for {original_url}"
        )
        return unique_alternatives[:10]  # Limit to top 10 alternatives

    def _attempt_whitepaper_extraction(self, url: str) -> WhitepaperContent:
        """
        Attempt to extract whitepaper content from a single URL.

        Args:
            url: URL to extract from

        Returns:
            WhitepaperContent object with extracted information
        """
        try:

            # Check URL filter first
            should_skip, skip_reason = url_filter.should_skip_url(url)
            if should_skip:
                return WhitepaperContent(
                    url=url,
                    content_type="unknown",
                    title=None,
                    content="",
                    word_count=0,
                    page_count=None,
                    content_hash="",
                    extraction_method="none",
                    success=False,
                    error_message=f"URL filtered: {skip_reason}",
                )

            # Handle Google Drive URLs specially
            if self._is_google_drive_url(url):
                return self._handle_google_drive_url(url)

            # Determine content type from URL and headers
            content_type_from_url = self._guess_content_type_from_url(url)

            # Try HEAD request to get content type from headers
            content_type_from_headers = None
            try:
                response = self.session.head(
                    url, timeout=self.timeout, allow_redirects=True
                )
                content_type_from_headers = response.headers.get(
                    "content-type", ""
                ).lower()

                # Check file size
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.max_file_size:
                    return WhitepaperContent(
                        url=url,
                        content_type="unknown",
                        title=None,
                        content="",
                        word_count=0,
                        page_count=None,
                        content_hash="",
                        extraction_method="none",
                        success=False,
                        error_message=f"File too large: {content_length} bytes",
                    )
            except Exception as e:
                logger.debug(
                    f"HEAD request failed for {url}: {e}, using URL-based detection"
                )

            # Decide extraction method based on URL and headers
            if content_type_from_url == "pdf" or (
                content_type_from_headers and "pdf" in content_type_from_headers
            ):
                return self._extract_pdf_content(url)
            else:
                return self._extract_webpage_content(url)

        except requests.exceptions.HTTPError as e:
            # Handle HTTP status code errors specifically
            if e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    logger.warning(
                        f"Whitepaper not found (404) for {url} - website issue, not our code"
                    )
                    error_type = "http_404_not_found"
                elif status_code == 403:
                    logger.warning(f"Access forbidden (403) for whitepaper {url}")
                    error_type = "http_403_forbidden"
                elif status_code == 401:
                    logger.warning(
                        f"Authentication required (401) for whitepaper {url}"
                    )
                    error_type = "http_401_unauthorized"
                elif 400 <= status_code < 500:
                    logger.warning(
                        f"Client error ({status_code}) for whitepaper {url}: {e}"
                    )
                    error_type = f"http_{status_code}_client_error"
                elif 500 <= status_code < 600:
                    logger.warning(
                        f"Server error ({status_code}) for whitepaper {url}: {e}"
                    )
                    error_type = f"http_{status_code}_server_error"
                else:
                    logger.error(
                        f"HTTP error ({status_code}) for whitepaper {url}: {e}"
                    )
                    error_type = f"http_{status_code}_error"
            else:
                logger.error(f"HTTP error for whitepaper {url}: {e}")
                error_type = "http_error_no_response"

            return WhitepaperContent(
                url=url,
                content_type="unknown",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="none",
                success=False,
                error_message=f"{error_type}: {str(e)}",
            )
        except Exception as e:
            error_msg = str(e)

            # Categorize the error for better logging
            if "getaddrinfo failed" in error_msg or "Failed to resolve" in error_msg:
                logger.warning(
                    f"DNS resolution failed for whitepaper {url}: Domain not found"
                )
                error_type = "dns_resolution_error"
            elif "SSL" in error_msg.upper() or "certificate" in error_msg.lower():
                logger.warning(
                    f"SSL certificate error for whitepaper {url}: {error_msg[:100]}..."
                )
                error_type = "ssl_certificate_error"
            elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logger.warning(f"Connection timeout for whitepaper {url}")
                error_type = "connection_timeout"
            elif "Max retries exceeded" in error_msg:
                logger.warning(f"Connection failed after retries for whitepaper {url}")
                error_type = "connection_retries_exhausted"
            elif "ConnectTimeoutError" in error_msg:
                logger.warning(f"Connection timeout for whitepaper {url}")
                error_type = "connection_timeout"
            else:
                logger.error(f"Failed to scrape whitepaper {url}: {e}")
                error_type = "unknown_error"

            return WhitepaperContent(
                url=url,
                content_type="unknown",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="none",
                success=False,
                error_message=f"{error_type}: {str(e)}",
            )

    def _extract_pdf_content(self, url: str) -> WhitepaperContent:
        """Extract content from a PDF whitepaper."""
        try:
            # Download PDF to temporary file
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            # Check if we actually got a PDF or if it's HTML (404 page)
            content_type = response.headers.get("content-type", "").lower()
            if not response.content.startswith(b"%PDF") and "text/html" in content_type:
                # We got an HTML page instead of a PDF (probably a 404 page)
                logger.warning(
                    f"PDF URL {url} returned HTML content (likely 404 page), attempting webpage extraction"
                )

                # Try to extract meaningful content from the HTML
                soup = BeautifulSoup(response.content, "html.parser")
                text_content = soup.get_text(separator="\n", strip=True)

                # Check for common 404 indicators
                text_lower = text_content.lower()
                if any(
                    indicator in text_lower
                    for indicator in [
                        "page doesn't exist",
                        "page not found",
                        "404",
                        "oops",
                        "back to home",
                        "file not found",
                        "document not found",
                    ]
                ):
                    return WhitepaperContent(
                        url=url,
                        content_type="pdf",
                        title=None,
                        content="",
                        word_count=0,
                        page_count=None,
                        content_hash="",
                        extraction_method="none",
                        success=False,
                        error_message="PDF not found: URL returns 404 HTML page instead of PDF document",
                    )

                # If not a clear 404, treat as webpage content
                return WhitepaperContent(
                    url=url,
                    content_type="webpage",
                    title=(
                        soup.find("title").get_text().strip()
                        if soup.find("title")
                        else None
                    ),
                    content=self._clean_webpage_content(text_content),
                    word_count=len(text_content.split()),
                    page_count=None,
                    content_hash=hashlib.sha256(text_content.encode()).hexdigest(),
                    extraction_method="html_fallback_from_pdf_url",
                    success=True if len(text_content.split()) >= 20 else False,
                    error_message=(
                        None
                        if len(text_content.split()) >= 20
                        else "Insufficient content from HTML fallback"
                    ),
                )

            # Verify we got actual PDF content
            if not response.content.startswith(b"%PDF"):
                return WhitepaperContent(
                    url=url,
                    content_type="pdf",
                    title=None,
                    content="",
                    word_count=0,
                    page_count=None,
                    content_hash="",
                    extraction_method="none",
                    success=False,
                    error_message="Invalid PDF: Downloaded content is not a PDF file",
                )

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name

            try:
                # Try multiple extraction methods
                content, method, page_count = self._extract_with_multiple_methods(
                    tmp_path
                )

                if not content.strip():
                    return WhitepaperContent(
                        url=url,
                        content_type="pdf",
                        title=None,
                        content="",
                        word_count=0,
                        page_count=page_count,
                        content_hash="",
                        extraction_method=method,
                        success=False,
                        error_message="No text content extracted from PDF",
                    )

                # Clean and process content
                content = self._clean_pdf_content(content)
                title = self._extract_pdf_title(content)
                word_count = len(content.split())
                content_hash = hashlib.sha256(content.encode()).hexdigest()

                logger.success(
                    f"Extracted PDF content: {word_count} words, {page_count} pages"
                )

                return WhitepaperContent(
                    url=url,
                    content_type="pdf",
                    title=title,
                    content=content,
                    word_count=word_count,
                    page_count=page_count,
                    content_hash=content_hash,
                    extraction_method=method,
                    success=True,
                )

            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass

        except requests.exceptions.HTTPError as e:
            # Handle HTTP errors in PDF extraction - quiet logging for expected failures
            if e.response is not None:
                status_code = e.response.status_code
                if status_code == 403:
                    logger.debug(
                        f"Access forbidden to PDF {url} - authentication or permission issue"
                    )
                    error_msg = f"PDF access forbidden (403)"
                elif status_code == 404:
                    logger.debug(f"PDF not found (404) at {url}")
                    error_msg = f"PDF not found (404)"
                elif status_code == 429:
                    logger.debug(f"Rate limited accessing PDF {url}")
                    error_msg = f"HTTP 429 rate limit error accessing PDF"
                elif status_code == 400:
                    logger.debug(f"Bad request for PDF {url}")
                    error_msg = f"HTTP 400 bad request error accessing PDF"
                else:
                    logger.debug(f"HTTP error ({status_code}) accessing PDF {url}: {e}")
                    error_msg = f"HTTP {status_code} error accessing PDF"
            else:
                logger.debug(f"HTTP error accessing PDF {url}: {e}")
                error_msg = f"HTTP error accessing PDF: {e}"

            return WhitepaperContent(
                url=url,
                content_type="pdf",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="none",
                success=False,
                error_message=error_msg,
            )
        except Exception as e:
            logger.warning(f"Failed to extract PDF content from {url}: {e}")
            return WhitepaperContent(
                url=url,
                content_type="pdf",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="none",
                success=False,
                error_message=f"PDF extraction failed: {str(e)}",
            )

    def _extract_with_multiple_methods(self, pdf_path: str) -> tuple[str, str, int]:
        """Try multiple PDF extraction methods and return the best result with detailed error handling."""
        methods = []
        extraction_errors = []

        # Method 1: PyMuPDF (fitz) - Usually most reliable
        try:
            doc = fitz.open(pdf_path)
            if doc.is_pdf:
                text = ""
                page_count = doc.page_count

                # Check if PDF is password protected
                if doc.needs_pass:
                    doc.close()
                    extraction_errors.append(
                        ("pymupdf", "password_protected", "PDF is password protected")
                    )
                    logger.warning(
                        f"PDF is password protected, PyMuPDF cannot extract content"
                    )
                else:
                    for page_num in range(page_count):
                        try:
                            page = doc[page_num]
                            page_text = page.get_text()
                            if page_text:
                                text += page_text + "\n"
                        except Exception as page_e:
                            logger.debug(
                                f"PyMuPDF failed to extract page {page_num}: {page_e}"
                            )
                            continue

                    doc.close()

                    if text.strip():
                        methods.append(("pymupdf", text.strip(), page_count))
                        logger.debug(
                            f"PyMuPDF extracted {len(text.split())} words from {page_count} pages"
                        )
                    else:
                        extraction_errors.append(
                            (
                                "pymupdf",
                                "no_text_content",
                                "PDF contains no extractable text (possibly scanned images)",
                            )
                        )
                        logger.debug("PyMuPDF opened PDF but extracted no text content")
            else:
                doc.close()
                extraction_errors.append(
                    ("pymupdf", "invalid_pdf", "File is not a valid PDF document")
                )
                logger.debug("PyMuPDF: File is not a valid PDF")

        except Exception as e:
            error_msg = str(e)
            if "document closed" in error_msg.lower():
                extraction_errors.append(
                    (
                        "pymupdf",
                        "document_closed",
                        "PDF document was unexpectedly closed",
                    )
                )
            elif "invalid pdf" in error_msg.lower() or "not a pdf" in error_msg.lower():
                extraction_errors.append(
                    (
                        "pymupdf",
                        "corrupted_pdf",
                        "PDF file appears to be corrupted or invalid",
                    )
                )
            elif "password" in error_msg.lower():
                extraction_errors.append(
                    (
                        "pymupdf",
                        "password_protected",
                        "PDF requires password for access",
                    )
                )
            else:
                extraction_errors.append(
                    ("pymupdf", "unknown_error", f"Unexpected error: {error_msg[:100]}")
                )
            logger.debug(f"PyMuPDF failed: {error_msg}")

        # Method 2: pdfplumber (if available) - Good for structured text
        if HAS_PDFPLUMBER:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    if len(pdf.pages) == 0:
                        extraction_errors.append(
                            ("pdfplumber", "no_pages", "PDF contains no pages")
                        )
                    else:
                        text = ""
                        successful_pages = 0

                        for page_num, page in enumerate(pdf.pages):
                            try:
                                page_text = page.extract_text()
                                if page_text and page_text.strip():
                                    text += page_text + "\n"
                                    successful_pages += 1
                            except Exception as page_e:
                                logger.debug(
                                    f"pdfplumber failed to extract page {page_num}: {page_e}"
                                )
                                continue

                        if text.strip():
                            methods.append(("pdfplumber", text.strip(), len(pdf.pages)))
                            logger.debug(
                                f"pdfplumber extracted {len(text.split())} words from {successful_pages}/{len(pdf.pages)} pages"
                            )
                        else:
                            extraction_errors.append(
                                (
                                    "pdfplumber",
                                    "no_text_content",
                                    "PDF contains no extractable text",
                                )
                            )

            except Exception as e:
                error_msg = str(e)
                if "No /Root object" in error_msg:
                    extraction_errors.append(
                        (
                            "pdfplumber",
                            "corrupted_pdf",
                            "PDF structure is corrupted (no root object)",
                        )
                    )
                elif (
                    "encrypted" in error_msg.lower() or "password" in error_msg.lower()
                ):
                    extraction_errors.append(
                        (
                            "pdfplumber",
                            "encrypted_pdf",
                            "PDF is encrypted and requires password",
                        )
                    )
                else:
                    extraction_errors.append(
                        (
                            "pdfplumber",
                            "unknown_error",
                            f"Unexpected error: {error_msg[:100]}",
                        )
                    )
                logger.debug(f"pdfplumber failed: {error_msg}")

        # Method 3: PyPDF2 (if available) - Fallback option
        if HAS_PYPDF2:
            try:
                with open(pdf_path, "rb") as file:
                    reader = PyPDF2.PdfReader(file)

                    if reader.is_encrypted:
                        extraction_errors.append(
                            ("pypdf2", "encrypted_pdf", "PDF is encrypted")
                        )
                        logger.debug("PyPDF2: PDF is encrypted")
                    elif len(reader.pages) == 0:
                        extraction_errors.append(
                            ("pypdf2", "no_pages", "PDF contains no pages")
                        )
                    else:
                        text = ""
                        successful_pages = 0

                        for page_num, page in enumerate(reader.pages):
                            try:
                                page_text = page.extract_text()
                                if page_text and page_text.strip():
                                    text += page_text + "\n"
                                    successful_pages += 1
                            except Exception as page_e:
                                logger.debug(
                                    f"PyPDF2 failed to extract page {page_num}: {page_e}"
                                )
                                continue

                        if text.strip():
                            methods.append(("pypdf2", text.strip(), len(reader.pages)))
                            logger.debug(
                                f"PyPDF2 extracted {len(text.split())} words from {successful_pages}/{len(reader.pages)} pages"
                            )
                        else:
                            extraction_errors.append(
                                (
                                    "pypdf2",
                                    "no_text_content",
                                    "PDF contains no extractable text",
                                )
                            )

            except Exception as e:
                error_msg = str(e)
                if "EOF marker not found" in error_msg or "Invalid PDF" in error_msg:
                    extraction_errors.append(
                        (
                            "pypdf2",
                            "corrupted_pdf",
                            "PDF file is corrupted or incomplete",
                        )
                    )
                elif "PdfReadError" in error_msg:
                    extraction_errors.append(
                        (
                            "pypdf2",
                            "read_error",
                            "PDF cannot be read due to format issues",
                        )
                    )
                else:
                    extraction_errors.append(
                        (
                            "pypdf2",
                            "unknown_error",
                            f"Unexpected error: {error_msg[:100]}",
                        )
                    )
                logger.debug(f"PyPDF2 failed: {error_msg}")

        # Log summary of extraction attempts
        if extraction_errors:
            error_summary = "; ".join(
                [
                    f"{method}: {error_type}"
                    for method, error_type, _ in extraction_errors
                ]
            )
            logger.debug(f"PDF extraction errors: {error_summary}")

        if not methods:
            # Provide detailed error message based on the types of failures encountered
            error_types = [error_type for _, error_type, _ in extraction_errors]

            if "password_protected" in error_types or "encrypted_pdf" in error_types:
                raise Exception(
                    "PDF extraction failed: Document is password protected or encrypted"
                )
            elif "corrupted_pdf" in error_types or "invalid_pdf" in error_types:
                raise Exception(
                    "PDF extraction failed: Document is corrupted or invalid"
                )
            elif "no_text_content" in error_types:
                raise Exception(
                    "PDF extraction failed: Document contains no extractable text (possibly scanned images only)"
                )
            elif "no_pages" in error_types:
                raise Exception("PDF extraction failed: Document contains no pages")
            else:
                raise Exception("All PDF extraction methods failed")

        # Return the method with the most extracted content
        best_method = max(methods, key=lambda x: len(x[1].split()))
        logger.info(
            f"Best extraction method: {best_method[0]} with {len(best_method[1].split())} words"
        )
        return best_method[1], best_method[0], best_method[2]

    def _extract_webpage_content(self, url: str) -> WhitepaperContent:
        """Extract content from a webpage whitepaper."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Remove unwanted elements
            for element in soup(
                ["script", "style", "nav", "header", "footer", "aside", "menu"]
            ):
                element.decompose()

            # Extract title
            title = None
            title_elem = soup.find("title")
            if title_elem:
                title = title_elem.get_text().strip()

            # Try to find main content areas
            content_selectors = [
                "main",
                "article",
                ".content",
                "#content",
                ".post",
                ".whitepaper",
                ".document",
                ".paper",
                "section",
                ".main-content",
            ]

            main_content = None
            for selector in content_selectors:
                element = soup.select_one(selector)
                if element:
                    main_content = element
                    break

            # Fall back to body if no main content found
            if main_content is None:
                main_content = soup.find("body")

            if main_content is None:
                main_content = soup

            # Extract text content
            content = main_content.get_text(separator="\n", strip=True)
            content = self._clean_webpage_content(content)

            word_count = len(content.split())

            # Check if we got meaningful content
            if word_count < 20:  # Very little content extracted
                logger.debug(
                    f"Minimal content extracted from {url}: {word_count} words - likely dynamic content or access restrictions"
                )
                return WhitepaperContent(
                    url=url,
                    content_type="webpage",
                    title=title,
                    content=content,
                    word_count=word_count,
                    page_count=None,
                    content_hash="",
                    extraction_method="beautifulsoup_minimal_content",
                    success=False,
                    error_message=f"Insufficient content extracted: {word_count} words (minimum 20 required)",
                )

            content_hash = hashlib.sha256(content.encode()).hexdigest()

            logger.success(f"Extracted webpage content: {word_count} words")

            return WhitepaperContent(
                url=url,
                content_type="webpage",
                title=title,
                content=content,
                word_count=word_count,
                page_count=None,
                content_hash=content_hash,
                extraction_method="beautifulsoup",
                success=True,
            )

        except requests.exceptions.HTTPError as http_e:
            # Handle HTTP errors quietly - these are expected failures
            status_code = (
                getattr(http_e.response, "status_code", 0) if http_e.response else 0
            )
            if status_code in [400, 403, 404, 429]:
                logger.debug(f"HTTP {status_code} error for webpage {url}: {http_e}")
            else:
                logger.warning(
                    f"HTTP error extracting webpage content from {url}: {http_e}"
                )

            return WhitepaperContent(
                url=url,
                content_type="webpage",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="beautifulsoup_failed",
                success=False,
                error_message=f"Webpage extraction failed: {http_e}",
            )
        except Exception as e:
            logger.warning(f"Failed to extract webpage content from {url}: {e}")
            return WhitepaperContent(
                url=url,
                content_type="webpage",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="beautifulsoup_failed",
                success=False,
                error_message=f"Webpage extraction failed: {e}",
            )

    def _clean_pdf_content(self, content: str) -> str:
        """Clean and normalize PDF-extracted content."""
        # Split into lines and clean each line
        lines = content.split("\n")
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
        content = "\n".join(cleaned_lines)

        # Remove excessive whitespace
        import re

        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" {2,}", " ", content)

        return content.strip()

    def _clean_webpage_content(self, content: str) -> str:
        """Clean and normalize webpage-extracted content."""
        import re

        # Remove excessive whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" {2,}", " ", content)

        # Remove common webpage artifacts
        lines = content.split("\n")
        cleaned_lines = []

        skip_patterns = [
            r"cookie",
            r"privacy policy",
            r"terms of service",
            r"subscribe",
            r"newsletter",
            r"follow us",
            r"contact us",
        ]

        for line in lines:
            line = line.strip()
            if len(line) < 10:  # Skip very short lines
                continue

            # Skip lines matching common webpage artifacts
            if any(re.search(pattern, line.lower()) for pattern in skip_patterns):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    def _extract_pdf_title(self, content: str) -> Optional[str]:
        """Extract title from PDF content."""
        lines = content.split("\n")
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

    def _guess_content_type_from_url(self, url: str) -> str:
        """Guess content type from URL patterns."""
        url_lower = url.lower()

        # Check for PDF file extensions
        if (
            url_lower.endswith(".pdf")
            or "/whitepaper.pdf" in url_lower
            or "whitepaper" in url_lower
            and ".pdf" in url_lower
        ):
            return "pdf"

        # Check for known PDF hosting patterns
        if (
            ("assets." in url_lower and ".pdf" in url_lower)
            or ("github.com" in url_lower and ".pdf" in url_lower)
            or ("docs." in url_lower and "pdf" in url_lower)
        ):
            return "pdf"

        # Check for documentation/wiki sites that are typically webpages
        if any(
            pattern in url_lower
            for pattern in [
                "gitbook.",
                "docs.",
                "wiki.",
                "documentation.",
                "readme.",
                "github.io",
                "notion.",
                "confluence.",
            ]
        ):
            return "webpage"

        # Default to webpage if can't determine
        return "webpage"

    def _is_google_drive_url(self, url: str) -> bool:
        """Check if URL is a Google Drive file link."""
        return "drive.google.com" in url and "/file/d/" in url

    def _extract_google_drive_file_id(self, url: str) -> Optional[str]:
        """Extract file ID from Google Drive URL."""
        import re

        # Match pattern: /file/d/{FILE_ID}/view or /file/d/{FILE_ID}
        match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
        return match.group(1) if match else None

    def _get_google_drive_direct_url(self, file_id: str) -> str:
        """Convert Google Drive file ID to direct download URL."""
        return f"https://drive.google.com/uc?id={file_id}&export=download"

    def _handle_google_drive_url(self, url: str) -> WhitepaperContent:
        """Handle Google Drive file URLs specially."""
        try:
            logger.info(f"Processing Google Drive URL: {url}")

            # Set stricter limits for Google Drive to prevent crashes
            import signal
            import threading

            # Create a timeout for the entire operation
            timeout_occurred = threading.Event()

            def timeout_handler():
                timeout_occurred.set()
                logger.error(f"Google Drive download timed out after 60 seconds: {url}")

            # Set a 60-second timeout for the entire Google Drive operation
            timer = threading.Timer(60.0, timeout_handler)
            timer.start()

            # Extract file ID
            file_id = self._extract_google_drive_file_id(url)
            if not file_id:
                return WhitepaperContent(
                    url=url,
                    content_type="unknown",
                    title=None,
                    content="",
                    word_count=0,
                    page_count=None,
                    content_hash="",
                    extraction_method="none",
                    success=False,
                    error_message="Could not extract Google Drive file ID from URL",
                )

            # Try direct download URL first
            download_url = self._get_google_drive_direct_url(file_id)
            logger.debug(f"Attempting Google Drive direct download: {download_url}")

            try:
                # Check timeout before starting
                if timeout_occurred.is_set():
                    return self._create_timeout_error_response(url)

                # Test if it's a PDF by trying to download a small portion
                logger.debug(f"Testing Google Drive download: {download_url}")
                response = self.session.get(download_url, timeout=15, stream=True)

                # Check if we got redirected to a virus scan warning
                if "drive.google.com" in response.url and "virus" in response.url:
                    logger.info(
                        "Google Drive virus scan detected, trying alternative method"
                    )
                    # For large files, Google Drive shows a virus scan warning
                    # We can try to bypass this with a different approach
                    return self._handle_google_drive_large_file(file_id, url)

                # Check content type from response
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" not in content_type:
                    # Try to infer from content
                    chunk = next(response.iter_content(1024), b"")
                    if chunk.startswith(b"%PDF"):
                        content_type = "application/pdf"

                # Check if it's a PDF by examining the first chunk
                pdf_chunk = (
                    chunk
                    if "chunk" in locals()
                    else next(response.iter_content(1024), b"")
                )
                if "pdf" in content_type or pdf_chunk.startswith(b"%PDF"):
                    # Reset the response stream for full download
                    response.close()
                    # It's a PDF, download and process it
                    return self._extract_google_drive_pdf(download_url, url)
                else:
                    # Not a PDF, might be HTML content
                    return self._extract_google_drive_webpage(download_url, url)

            except Exception as e:
                logger.debug(f"Direct download failed: {e}, trying alternative method")
                return self._handle_google_drive_large_file(file_id, url)

        except Exception as e:
            logger.error(f"Failed to process Google Drive URL {url}: {e}")
            return WhitepaperContent(
                url=url,
                content_type="unknown",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="none",
                success=False,
                error_message=f"Google Drive processing failed: {e}",
            )
        finally:
            # Always cleanup the timer
            try:
                timer.cancel()
            except:
                pass

    def _extract_google_drive_pdf(
        self, download_url: str, original_url: str
    ) -> WhitepaperContent:
        """Extract PDF content from Google Drive direct download URL."""
        try:
            # Download PDF to temporary file with increased timeout for large files
            logger.info(f"Downloading Google Drive PDF from {download_url}")
            response = self.session.get(download_url, timeout=30, stream=True)
            response.raise_for_status()

            # Check content length
            content_length = response.headers.get("content-length")
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                logger.info(f"PDF size: {size_mb:.1f} MB")

                # Skip files that are too large (>50MB)
                if size_mb > 50:
                    logger.warning(f"PDF file too large ({size_mb:.1f} MB), skipping")
                    return WhitepaperContent(
                        url=original_url,
                        content_type="pdf",
                        title=None,
                        content="",
                        word_count=0,
                        page_count=None,
                        content_hash="",
                        extraction_method="google_drive_skipped_large",
                        success=False,
                        error_message=f"PDF file too large ({size_mb:.1f} MB)",
                    )

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                # Download in chunks to avoid memory issues
                downloaded_size = 0
                max_size = 50 * 1024 * 1024  # 50MB limit

                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        if downloaded_size > max_size:
                            logger.warning(
                                f"File too large ({downloaded_size / (1024*1024):.1f} MB), stopping download"
                            )
                            return WhitepaperContent(
                                url=original_url,
                                content_type="pdf",
                                title=None,
                                content="",
                                word_count=0,
                                page_count=None,
                                content_hash="",
                                extraction_method="google_drive_too_large",
                                success=False,
                                error_message=f"PDF file too large ({downloaded_size / (1024*1024):.1f} MB)",
                            )
                        tmp_file.write(chunk)

                tmp_path = tmp_file.name
                logger.info(
                    f"Downloaded {downloaded_size / (1024*1024):.1f} MB to {tmp_path}"
                )

            try:
                # Add safety checks for Google Drive PDFs
                import os

                file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)

                # Skip files that might cause crashes (lowered threshold for Google Drive)
                if file_size_mb > 20:
                    logger.warning(
                        f"Skipping PDF extraction for large file ({file_size_mb:.1f} MB): {original_url}"
                    )
                    return WhitepaperContent(
                        url=original_url,
                        content_type="pdf",
                        title=None,
                        content="",
                        word_count=0,
                        page_count=None,
                        content_hash="",
                        extraction_method="google_drive_skipped_large_file",
                        success=False,
                        error_message=f"PDF file too large for extraction ({file_size_mb:.1f} MB)",
                    )

                # Try extraction with error handling
                try:
                    content, method, page_count = self._extract_with_multiple_methods(
                        tmp_path
                    )
                except Exception as extraction_error:
                    logger.error(
                        f"PDF extraction failed for {original_url}: {extraction_error}"
                    )
                    return WhitepaperContent(
                        url=original_url,
                        content_type="pdf",
                        title=None,
                        content="",
                        word_count=0,
                        page_count=None,
                        content_hash="",
                        extraction_method="google_drive_extraction_failed",
                        success=False,
                        error_message=f"PDF extraction failed: {extraction_error}",
                    )

                if not content.strip():
                    return WhitepaperContent(
                        url=original_url,
                        content_type="pdf",
                        title=None,
                        content="",
                        word_count=0,
                        page_count=page_count,
                        content_hash="",
                        extraction_method=f"google_drive_{method}",
                        success=False,
                        error_message="No text content extracted from Google Drive PDF",
                    )

                # Clean and process content
                content = self._clean_pdf_content(content)
                title = self._extract_pdf_title(content)
                word_count = len(content.split())
                content_hash = hashlib.sha256(content.encode()).hexdigest()

                logger.success(
                    f"Extracted Google Drive PDF content: {word_count} words, {page_count} pages"
                )

                return WhitepaperContent(
                    url=original_url,
                    content_type="pdf",
                    title=title,
                    content=content,
                    word_count=word_count,
                    page_count=page_count,
                    content_hash=content_hash,
                    extraction_method=f"google_drive_{method}",
                    success=True,
                )

            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"Failed to extract Google Drive PDF from {download_url}: {e}")
            return WhitepaperContent(
                url=original_url,
                content_type="pdf",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="google_drive_failed",
                success=False,
                error_message=f"Google Drive PDF extraction failed: {e}",
            )

    def _extract_google_drive_webpage(
        self, download_url: str, original_url: str
    ) -> WhitepaperContent:
        """Extract webpage content from Google Drive URL."""
        try:
            response = self.session.get(download_url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Remove unwanted elements
            for element in soup(
                ["script", "style", "nav", "header", "footer", "aside", "menu"]
            ):
                element.decompose()

            # Extract title
            title = None
            title_elem = soup.find("title")
            if title_elem:
                title = title_elem.get_text().strip()

            # Extract text content
            content = soup.get_text(separator="\n", strip=True)
            content = self._clean_webpage_content(content)

            word_count = len(content.split())
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            logger.success(
                f"Extracted Google Drive webpage content: {word_count} words"
            )

            return WhitepaperContent(
                url=original_url,
                content_type="webpage",
                title=title,
                content=content,
                word_count=word_count,
                page_count=None,
                content_hash=content_hash,
                extraction_method="google_drive_webpage",
                success=True,
            )

        except Exception as e:
            logger.error(
                f"Failed to extract Google Drive webpage from {download_url}: {e}"
            )
            return WhitepaperContent(
                url=original_url,
                content_type="webpage",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="google_drive_webpage_failed",
                success=False,
                error_message=f"Google Drive webpage extraction failed: {e}",
            )

    def _create_timeout_error_response(self, url: str) -> WhitepaperContent:
        """Create error response for timeout."""
        return WhitepaperContent(
            url=url,
            content_type="unknown",
            title=None,
            content="",
            word_count=0,
            page_count=None,
            content_hash="",
            extraction_method="google_drive_timeout",
            success=False,
            error_message="Google Drive download timed out after 60 seconds",
        )

    def _handle_google_drive_large_file(
        self, file_id: str, original_url: str
    ) -> WhitepaperContent:
        """Handle large Google Drive files that show virus scan warnings."""
        try:
            # For large files, we need to confirm the download
            confirm_url = (
                f"https://drive.google.com/uc?id={file_id}&export=download&confirm=t"
            )
            logger.debug(f"Trying large file download: {confirm_url}")

            response = self.session.get(confirm_url, timeout=self.timeout)
            response.raise_for_status()

            # Check if it's a PDF
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" in content_type or response.content.startswith(b"%PDF"):
                return self._extract_google_drive_pdf(confirm_url, original_url)
            else:
                return self._extract_google_drive_webpage(confirm_url, original_url)

        except Exception as e:
            logger.error(f"Failed to handle large Google Drive file {file_id}: {e}")
            return WhitepaperContent(
                url=original_url,
                content_type="unknown",
                title=None,
                content="",
                word_count=0,
                page_count=None,
                content_hash="",
                extraction_method="google_drive_large_file_failed",
                success=False,
                error_message=f"Large Google Drive file handling failed: {e}",
            )


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
