"""
Website Scraper Module for Cryptocurrency Project Analysis

This module handles:
- Fetching main pages and key subpages (About, Team, Technology)
- Spidering 2-3 levels deep within the same domain
- Content extraction and cleaning
- Respecting robots.txt and rate limiting
"""

import requests
import time
import hashlib
import urllib.robotparser
from urllib.parse import urljoin, urlparse, parse_qs
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
from loguru import logger
import re
from urllib.parse import urlparse, urljoin

# Import URL filter
from utils.url_filter import url_filter

# Import content sanitization utility
sys.path.insert(0, str(Path(__file__).parent.parent / "pipelines"))
try:
    from content_analysis_pipeline import sanitize_content_for_storage
except ImportError:
    # Fallback function if import fails
    def sanitize_content_for_storage(content: str) -> str:
        if not content:
            return ""
        return content.replace("\x00", "").strip()


@dataclass
class ScrapedPage:
    """Represents a scraped web page with metadata."""

    url: str
    title: str
    content: str
    content_hash: str
    page_type: str  # 'main', 'about', 'team', 'technology', 'other'
    links_found: List[str]
    scrape_time: datetime
    status_code: int
    word_count: int


@dataclass
class WebsiteAnalysisResult:
    """Complete website analysis result."""

    domain: str
    pages_scraped: List[ScrapedPage]
    total_pages: int
    scrape_success: bool
    error_message: Optional[str] = None
    analysis_timestamp: datetime = None

    # Enhanced status tracking
    status_type: Optional[str] = (
        None  # 'success', 'robots_blocked', 'parked_domain', 'no_content', etc.
    )
    robots_blocked: bool = False
    parked_pages_detected: int = 0
    total_content_length: int = 0
    detected_parking_service: Optional[str] = None
    error_type: Optional[str] = None  # Specific error type for better categorization


class WebsiteScraper:
    """Intelligent website scraper for cryptocurrency projects."""

    def __init__(self, max_pages: int = 10, max_depth: int = 3, delay: float = 0.2):
        """
        Initialize the website scraper.

        Args:
            max_pages: Maximum number of pages to scrape per domain
            max_depth: Maximum depth to spider (levels from main page)
            delay: Delay between requests in seconds
        """
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay
        self.session = requests.Session()

        # Set a reasonable user agent
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 CryptoAnalytics/1.0"
            }
        )

        # Keywords for identifying important pages
        self.important_keywords = {
            "about": ["about", "about-us", "company", "story", "mission"],
            "team": ["team", "people", "founders", "leadership", "staff"],
            "technology": [
                "technology",
                "tech",
                "technical",
                "architecture",
                "protocol",
                "blockchain",
            ],
            "whitepaper": [
                "whitepaper",
                "white-paper",
                "documentation",
                "docs",
                "paper",
            ],
            "roadmap": ["roadmap", "timeline", "milestones", "development"],
        }

    def can_fetch(self, url: str, max_retries: int = 2) -> Tuple[bool, Optional[str]]:
        """Check if we can fetch the URL according to robots.txt with retry logic.

        Args:
            url: URL to check
            max_retries: Maximum number of retry attempts for transient failures

        Returns:
            Tuple of (can_fetch: bool, error_info: Optional[str])
        """
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

        for attempt in range(max_retries + 1):
            try:
                rp = urllib.robotparser.RobotFileParser()
                rp.set_url(robots_url)
                rp.read()

                can_fetch_result = rp.can_fetch(self.session.headers["User-Agent"], url)
                if attempt > 0:  # Log successful retry
                    logger.debug(
                        f"Robots.txt check succeeded on attempt {attempt + 1} for {url}"
                    )

                return can_fetch_result, None

            except Exception as e:
                error_msg = str(e)

                # Categorize robots.txt fetch errors
                if (
                    "getaddrinfo failed" in error_msg
                    or "Failed to resolve" in error_msg
                ):
                    if (
                        attempt == 0
                    ):  # Only log on first attempt for DNS errors (likely permanent)
                        logger.debug(
                            f"Cannot check robots.txt for {url}: DNS resolution failed (permanent)"
                        )
                    return True, "dns_resolution_error"  # Allow if we can't resolve DNS

                elif "SSL" in error_msg.upper() or "certificate" in error_msg.lower():
                    if (
                        "CERTIFICATE_VERIFY_FAILED" in error_msg
                        or "certificate verify failed" in error_msg.lower()
                    ):
                        logger.debug(
                            f"Cannot check robots.txt for {url}: SSL certificate verification failed"
                        )
                        return True, "ssl_certificate_verification_failed"
                    elif (
                        "WRONG_VERSION_NUMBER" in error_msg
                        or "wrong version number" in error_msg.lower()
                    ):
                        logger.debug(
                            f"Cannot check robots.txt for {url}: SSL version mismatch"
                        )
                        return True, "ssl_version_mismatch"
                    else:
                        logger.debug(
                            f"Cannot check robots.txt for {url}: SSL certificate error"
                        )
                        return True, "ssl_certificate_error"

                elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    if attempt < max_retries:
                        logger.debug(
                            f"Robots.txt timeout for {url}, retrying ({attempt + 1}/{max_retries})"
                        )
                        time.sleep(1 * (attempt + 1))  # Progressive backoff
                        continue
                    else:
                        logger.debug(
                            f"Cannot check robots.txt for {url}: Connection timeout after {max_retries + 1} attempts"
                        )
                        return True, "connection_timeout_persistent"

                elif (
                    "forcibly closed" in error_msg.lower()
                    or "10054" in error_msg
                    or "ConnectionResetError" in error_msg
                ):
                    if attempt < max_retries:
                        logger.debug(
                            f"Robots.txt connection reset for {url}, retrying ({attempt + 1}/{max_retries})"
                        )
                        time.sleep(1 * (attempt + 1))  # Progressive backoff
                        continue
                    else:
                        logger.debug(
                            f"Cannot check robots.txt for {url}: Connection reset after {max_retries + 1} attempts"
                        )
                        return True, "connection_reset_persistent"

                elif "404" in error_msg or "Not Found" in error_msg:
                    logger.debug(
                        f"Robots.txt not found for {url} (404) - assuming allowed"
                    )
                    return True, "robots_txt_not_found"

                elif "403" in error_msg or "Forbidden" in error_msg:
                    logger.debug(
                        f"Robots.txt access forbidden for {url} (403) - assuming allowed"
                    )
                    return True, "robots_txt_forbidden"

                elif "Max retries exceeded" in error_msg:
                    if attempt < max_retries:
                        logger.debug(
                            f"Max retries exceeded for robots.txt {url}, retrying ({attempt + 1}/{max_retries})"
                        )
                        time.sleep(
                            2 * (attempt + 1)
                        )  # Longer backoff for connection issues
                        continue
                    else:
                        logger.debug(
                            f"Cannot check robots.txt for {url}: Max retries exceeded persistently"
                        )
                        return True, "max_retries_exceeded_persistent"

                else:
                    if attempt < max_retries:
                        logger.debug(
                            f"Unknown robots.txt error for {url}, retrying ({attempt + 1}/{max_retries}): {error_msg[:50]}..."
                        )
                        time.sleep(1 * (attempt + 1))
                        continue
                    else:
                        logger.debug(
                            f"Cannot check robots.txt for {url}: {error_msg[:100]}... (after {max_retries + 1} attempts)"
                        )
                        return True, "unknown_robots_error_persistent"

        # This should never be reached, but just in case
        return True, "robots_check_failed_unexpectedly"

    def classify_page_type(self, url: str, title: str, content: str) -> str:
        """Classify the type of page based on URL, title, and content."""
        url_lower = url.lower()
        title_lower = title.lower()
        content_lower = content.lower()[:2000]  # Check first 2000 chars

        for page_type, keywords in self.important_keywords.items():
            for keyword in keywords:
                if (
                    keyword in url_lower
                    or keyword in title_lower
                    or content_lower.count(keyword) >= 2
                ):  # Must appear at least twice in content
                    return page_type

        return "other"

    def extract_content(self, html: str, url: str) -> Tuple[str, str, List[str]]:
        """
        Extract clean content, title, and links from HTML.

        Returns:
            Tuple of (clean_content, title, internal_links)
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, nav, footer, and other non-content elements
        for element in soup(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "aside",
                "advertisement",
                ".ad",
                ".advertisement",
            ]
        ):
            element.decompose()

        # Extract title
        title_element = soup.find("title")
        title = title_element.get_text().strip() if title_element else "No Title"

        # Try to find main content area
        main_content = None
        content_selectors = [
            "main",
            '[role="main"]',
            ".main-content",
            "#main-content",
            ".content",
            "#content",
            "article",
            ".post-content",
            ".entry-content",
        ]

        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break

        # If no main content area found, use body
        if not main_content:
            main_content = soup.find("body")

        if not main_content:
            main_content = soup

        # Extract text content
        content = main_content.get_text(separator=" ", strip=True)

        # Clean up whitespace
        content = re.sub(r"\s+", " ", content).strip()

        # Extract internal links
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc

        links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            absolute_url = urljoin(url, href)
            parsed_link = urlparse(absolute_url)

            # Only keep internal links (same domain)
            if (
                parsed_link.netloc == base_domain
                and not href.startswith("#")  # Skip anchors
                and not href.startswith("mailto:")  # Skip email links
                and not href.startswith("tel:")
            ):  # Skip phone links

                # Apply URL filter to each link
                should_skip, _ = url_filter.should_skip_url(absolute_url)
                if not should_skip:
                    links.append(absolute_url)

        return content, title, list(set(links))  # Remove duplicates

    def fetch_page(
        self, url: str, max_retries: int = 2
    ) -> Tuple[Optional[ScrapedPage], Dict[str, Any]]:
        """Fetch and process a single page with retry logic for transient failures.

        Args:
            url: URL to fetch
            max_retries: Maximum number of retry attempts for transient failures

        Returns:
            Tuple of (ScrapedPage or None, status_info dict)
        """
        status_info = {
            "robots_blocked": False,
            "parked_detected": False,
            "parking_service": None,
        }

        # Check URL filter first
        should_skip, skip_reason = url_filter.should_skip_url(url)
        if should_skip:
            logger.debug(f"Skipping {url}: {skip_reason}")
            return None, status_info

        can_fetch, robots_error = self.can_fetch(url)
        if not can_fetch:
            logger.debug(f"Robots.txt check failed or disallows fetching {url}")
            status_info["robots_blocked"] = True
            if robots_error:
                status_info["robots_error_type"] = robots_error
            return None, status_info

        return self._fetch_page_with_retry(url, status_info, max_retries)

    def _fetch_page_with_retry(
        self, url: str, status_info: Dict[str, Any], max_retries: int
    ) -> Tuple[Optional[ScrapedPage], Dict[str, Any]]:
        """Internal method to handle page fetching with retry logic."""

        for attempt in range(max_retries + 1):
            try:
                return self._fetch_page_attempt(url, status_info, attempt, max_retries)
            except Exception as e:
                error_msg = str(e)

                # Check if this is a retryable error and get appropriate retry count
                is_retryable, max_retries_for_error = self._is_retryable_error(error_msg)

                # Use error-specific max retries
                effective_max_retries = min(max_retries, max_retries_for_error)

                if attempt < effective_max_retries and is_retryable:
                    # Enhanced exponential backoff: 1s, 2s, 4s, capped at 10s
                    backoff_time = min((2**attempt) * 1.0, 10.0)
                    logger.debug(
                        f"Retryable error for {url} on attempt {attempt + 1}/{effective_max_retries + 1}, retrying in {backoff_time}s: {error_msg[:50]}..."
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    # Final attempt failed or non-retryable error
                    status_info["retry_attempts"] = attempt  # Track how many retries were attempted
                    return self._handle_fetch_error(url, status_info, e, attempt + 1)

        # Should never reach here
        return None, status_info

    def _is_retryable_error(self, error_msg: str) -> Tuple[bool, int]:
        """Determine if an error is retryable and how many retries to allow.
        
        Returns:
            Tuple of (is_retryable: bool, max_retries: int)
        """
        # DNS resolution failures are typically permanent
        if "getaddrinfo failed" in error_msg or "Failed to resolve" in error_msg:
            return False, 0

        # SSL certificate errors are typically permanent
        if "SSL" in error_msg.upper() or "certificate" in error_msg.lower():
            return False, 0
        
        # 404, 410 are permanent - page doesn't exist
        if "404" in error_msg or "410" in error_msg or "Not Found" in error_msg:
            return False, 0

        # 5xx server errors are transient - allow more retries
        if any(code in error_msg for code in ["500", "502", "503", "504"]):
            return True, 3  # Server errors get 3 retries
        
        # Rate limiting should be retried with more patience
        if "429" in error_msg or "rate limit" in error_msg.lower():
            return True, 3

        # Connection issues are somewhat transient - moderate retries
        retryable_connection_patterns = [
            "timeout",
            "timed out",
            "Connection reset",
            "ConnectionResetError",
            "forcibly closed",
            "connection was aborted",
            "Connection aborted",
            "Max retries exceeded",
            "Connection broken",
        ]

        for pattern in retryable_connection_patterns:
            if pattern in error_msg:
                return True, 2  # Connection errors get 2 retries
        
        # Default: not retryable
        return False, 0

    def _fetch_page_attempt(
        self, url: str, status_info: Dict[str, Any], attempt: int, max_retries: int
    ) -> Tuple[Optional[ScrapedPage], Dict[str, Any]]:
        """Single attempt to fetch a page."""

        if attempt > 0:
            logger.debug(f"Fetching: {url} (attempt {attempt + 1}/{max_retries + 1})")
        else:
            logger.debug(f"Fetching: {url}")

        # First, make a HEAD request to check content type and size (if supported)
        try:
            head_response = self.session.head(url, timeout=15, allow_redirects=True)

            # Check content type to avoid downloading non-analyzable files
            content_type = head_response.headers.get("content-type", "").lower()
            if content_type:
                # Skip if content type indicates non-analyzable file
                non_analyzable_types = [
                    "application/octet-stream",  # Generic binary
                    "application/zip",
                    "application/x-zip",
                    "application/x-executable",
                    "application/x-msdownload",
                    "application/vnd.android.package-archive",  # APK files
                    "application/java-archive",  # JAR files
                    "application/x-deb",
                    "application/x-rpm",  # Package files
                    "application/x-apple-diskimage",  # DMG files
                    "audio/",
                    "video/",
                    "image/",  # Media files
                ]

                # Check if content type starts with any non-analyzable type
                for non_type in non_analyzable_types:
                    if content_type.startswith(non_type):
                        logger.debug(
                            f"Skipping {url}: non-analyzable content type {content_type}"
                        )
                        return None, status_info

            # Check file size to avoid very large downloads
            content_length = head_response.headers.get("content-length")
            if content_length:
                try:
                    size_mb = int(content_length) / (1024 * 1024)
                    if size_mb > 50:  # Skip files larger than 50MB
                        logger.debug(
                            f"Skipping {url}: file too large ({size_mb:.1f}MB)"
                        )
                        return None, status_info
                except ValueError:
                    pass  # Continue if size can't be parsed
        except Exception as e:
            # If HEAD request fails, continue with GET (some servers don't support HEAD)
            logger.debug(f"HEAD request failed for {url}, proceeding with GET")
            pass

        # Now make the actual GET request
        start_time = time.time()
        try:
            response = self.session.get(url, timeout=30)
            
            # Capture response metadata
            status_info["http_status_code"] = response.status_code
            status_info["response_time_ms"] = int((time.time() - start_time) * 1000)
            
            response.raise_for_status()

            # Double-check content type after GET request
            response_content_type = response.headers.get("content-type", "").lower()
            if response_content_type and not any(
                analyzable in response_content_type
                for analyzable in ["text/", "html", "xml", "json", "application/pdf"]
            ):
                logger.debug(
                    f"Skipping {url}: response content type not analyzable ({response_content_type})"
                )
                return None, status_info

            # Extract content
            content, title, links = self.extract_content(response.text, url)

            # Sanitize content for database storage
            content = sanitize_content_for_storage(content)

            # Enhanced content quality assessment
            quality_assessment = url_filter.assess_content_quality(content, title)

            # Handle different content quality issues
            if quality_assessment["content_type"] == "parked":
                logger.warning(f"Detected parked/for-sale domain: {url}")
                status_info["parked_detected"] = True
                status_info["parking_service"] = quality_assessment.get(
                    "parking_service"
                )
                return None, status_info

            elif quality_assessment["content_type"] == "dynamic":
                logger.info(
                    f"Dynamic content detected for {url} - attempting alternative extraction"
                )
                status_info["dynamic_content"] = True

                # For dynamic content, try to extract any meaningful text available
                if (
                    quality_assessment["word_count"] >= 10
                ):  # Some content is better than none
                    logger.debug(
                        f"Proceeding with limited dynamic content ({quality_assessment['word_count']} words)"
                    )
                else:
                    status_info["content_quality"] = quality_assessment
                    logger.debug(f"Insufficient dynamic content, skipping {url}")
                    return None, status_info

            elif quality_assessment["content_type"] == "restricted":
                logger.info(f"Access restricted content detected for {url}")
                status_info["access_restricted"] = True
                status_info["content_quality"] = quality_assessment
                return None, status_info

            elif quality_assessment["content_type"] == "error":
                logger.debug(f"Error page detected for {url}")
                status_info["error_page"] = True
                status_info["content_quality"] = quality_assessment
                return None, status_info

            elif (
                quality_assessment["quality_score"] < 3
                and quality_assessment["word_count"] < 30
            ):
                logger.debug(
                    f"Very low quality content for {url} (score: {quality_assessment['quality_score']}, words: {quality_assessment['word_count']})"
                )
                status_info["low_quality"] = True
                status_info["content_quality"] = quality_assessment
                return None, status_info

            # Store quality assessment for later analysis
            status_info["content_quality"] = quality_assessment

            # Skip if content is too minimal
            if len(content.strip()) < 50:
                logger.debug(f"Skipping {url}: minimal content ({len(content)} chars)")
                return None, status_info

            # Calculate content hash
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            # Classify page type
            page_type = self.classify_page_type(url, title, content)

            # Count words
            word_count = len(content.split())

            page = ScrapedPage(
                url=url,
                title=title,
                content=content,
                content_hash=content_hash,
                page_type=page_type,
                links_found=links,
                scrape_time=datetime.now(UTC),
                status_code=response.status_code,
                word_count=word_count,
            )

            logger.success(f"Scraped {url} - {page_type} page ({word_count} words)")
            return page, status_info

        except requests.exceptions.HTTPError as e:
            # Handle HTTP status code errors specifically
            if e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    logger.warning(
                        f"Page not found (404) for {url} - website issue, not our code"
                    )
                    status_info["error_type"] = "http_404_not_found"
                elif status_code == 403:
                    logger.warning(f"Access forbidden (403) for {url}")
                    status_info["error_type"] = "http_403_forbidden"
                elif status_code == 401:
                    logger.warning(f"Authentication required (401) for {url}")
                    status_info["error_type"] = "http_401_unauthorized"
                elif 400 <= status_code < 500:
                    logger.warning(f"Client error ({status_code}) for {url}: {e}")
                    status_info["error_type"] = f"http_{status_code}_client_error"
                elif 500 <= status_code < 600:
                    logger.warning(f"Server error ({status_code}) for {url}: {e}")
                    status_info["error_type"] = f"http_{status_code}_server_error"
                else:
                    logger.error(f"HTTP error ({status_code}) for {url}: {e}")
                    status_info["error_type"] = f"http_{status_code}_error"
            else:
                logger.error(f"HTTP error for {url}: {e}")
                status_info["error_type"] = "http_error_no_response"

            return None, status_info

    def _handle_fetch_error(
        self, url: str, status_info: Dict[str, Any], e: Exception, attempts_made: int
    ) -> Tuple[Optional[ScrapedPage], Dict[str, Any]]:
        """Handle fetch errors with proper categorization."""
        error_msg = str(e)

        # Handle HTTP errors specifically
        if isinstance(e, requests.exceptions.HTTPError):
            if e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    logger.warning(
                        f"Page not found (404) for {url} - website issue, not our code"
                    )
                    status_info["error_type"] = "http_404_not_found"
                elif status_code == 403:
                    logger.warning(f"Access forbidden (403) for {url}")
                    status_info["error_type"] = "http_403_forbidden"
                elif status_code == 401:
                    logger.warning(f"Authentication required (401) for {url}")
                    status_info["error_type"] = "http_401_unauthorized"
                elif 400 <= status_code < 500:
                    logger.warning(f"Client error ({status_code}) for {url}: {e}")
                    status_info["error_type"] = f"http_{status_code}_client_error"
                elif 500 <= status_code < 600:
                    logger.warning(f"Server error ({status_code}) for {url}: {e}")
                    status_info["error_type"] = f"http_{status_code}_server_error"
                else:
                    logger.error(f"HTTP error ({status_code}) for {url}: {e}")
                    status_info["error_type"] = f"http_{status_code}_error"
            else:
                logger.error(f"HTTP error for {url}: {e}")
                status_info["error_type"] = "http_error_no_response"
        else:
            # Categorize other errors with retry information
            if "getaddrinfo failed" in error_msg or "Failed to resolve" in error_msg:
                logger.warning(
                    f"DNS resolution failed for {url}: Domain not found (permanent failure)"
                )
                status_info["error_type"] = "dns_resolution_error"
                status_info["dns_resolved"] = False
            elif "SSL" in error_msg.upper() or "certificate" in error_msg.lower():
                logger.warning(f"SSL certificate error for {url}: {error_msg[:100]}...")
                status_info["error_type"] = "ssl_certificate_error"
                status_info["ssl_valid"] = False
            elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logger.warning(
                    f"Connection timeout for {url} after {attempts_made} attempts"
                )
                status_info["error_type"] = "connection_timeout_final"
            elif "Max retries exceeded" in error_msg:
                logger.warning(
                    f"Connection failed after retries for {url} (total {attempts_made} attempts)"
                )
                status_info["error_type"] = "connection_retries_exhausted_final"
            elif (
                "Connection aborted" in error_msg
                or "ConnectionResetError" in error_msg
                or "10054" in error_msg
            ):
                logger.warning(
                    f"Connection reset by remote host for {url} after {attempts_made} attempts - server/network issue"
                )
                status_info["error_type"] = "connection_reset_by_peer_final"
            elif (
                "forcibly closed" in error_msg.lower()
                or "connection was aborted" in error_msg.lower()
            ):
                logger.warning(
                    f"Connection forcibly closed for {url} after {attempts_made} attempts - server terminated connection"
                )
                status_info["error_type"] = "connection_forcibly_closed_final"
            else:
                logger.error(
                    f"Failed to fetch {url} after {attempts_made} attempts: {e}"
                )
                status_info["error_type"] = "unknown_connection_error_final"

        return None, status_info

    def prioritize_links(self, links: List[str], visited: Set[str]) -> List[str]:
        """Prioritize links based on importance keywords."""
        unvisited_links = [link for link in links if link not in visited]

        # Score links based on importance keywords
        scored_links = []
        for link in unvisited_links:
            score = 0
            link_lower = link.lower()

            # Higher scores for important page types
            if any(kw in link_lower for kw in self.important_keywords["about"]):
                score += 10
            if any(kw in link_lower for kw in self.important_keywords["team"]):
                score += 10
            if any(kw in link_lower for kw in self.important_keywords["technology"]):
                score += 10
            if any(kw in link_lower for kw in self.important_keywords["whitepaper"]):
                score += 15  # Whitepapers are especially important
            if any(kw in link_lower for kw in self.important_keywords["roadmap"]):
                score += 8

            # Penalize very long URLs or those with many parameters
            if len(link) > 100:
                score -= 2
            if "?" in link and len(parse_qs(urlparse(link).query)) > 3:
                score -= 3

            # Penalize common unimportant pages
            skip_patterns = [
                "privacy",
                "terms",
                "cookie",
                "legal",
                "support",
                "contact",
                "faq",
                "help",
                "login",
                "register",
            ]
            if any(pattern in link_lower for pattern in skip_patterns):
                score -= 5

            scored_links.append((link, score))

        # Sort by score (highest first) and return URLs
        scored_links.sort(key=lambda x: x[1], reverse=True)
        return [link for link, score in scored_links]

    def scrape_website(self, base_url: str) -> WebsiteAnalysisResult:
        """
        Scrape a website starting from the base URL.

        Args:
            base_url: The main URL to start scraping from

        Returns:
            WebsiteAnalysisResult with all scraped pages and metadata
        """
        logger.info(f"Starting website analysis for {base_url}")

        parsed_base = urlparse(base_url)
        domain = parsed_base.netloc

        # Initialize tracking
        visited = set()
        to_visit = [(base_url, 0)]  # (url, depth)
        scraped_pages = []
        robots_blocked = False
        parked_pages_detected = 0
        detected_parking_service = None
        primary_error_type = (
            None  # Track the most common or first encountered error type
        )

        while to_visit and len(scraped_pages) < self.max_pages:
            url, depth = to_visit.pop(0)

            if url in visited or depth > self.max_depth:
                continue

            visited.add(url)

            # Fetch the page
            page, status_info = self.fetch_page(url)

            # Track status information
            if status_info["robots_blocked"]:
                robots_blocked = True
            if status_info["parked_detected"]:
                parked_pages_detected += 1
                if status_info["parking_service"]:
                    detected_parking_service = status_info["parking_service"]

            # Track error types for better status reporting
            if (
                "error_type" in status_info
                and status_info["error_type"]
                and not primary_error_type
            ):
                primary_error_type = status_info["error_type"]

            if page:
                scraped_pages.append(page)

                # Add new links to visit queue if we haven't reached max depth
                if depth < self.max_depth:
                    prioritized_links = self.prioritize_links(page.links_found, visited)
                    for link in prioritized_links[:5]:  # Limit to top 5 links per page
                        to_visit.append((link, depth + 1))

            # Rate limiting
            if self.delay > 0:
                time.sleep(self.delay)

        # Calculate total content length
        total_content_length = sum(page.word_count for page in scraped_pages)

        # Determine status type
        status_type = "success"
        if robots_blocked and len(scraped_pages) == 0:
            status_type = "robots_blocked"
        elif parked_pages_detected > 0 and len(scraped_pages) == 0:
            status_type = "parked_domain"
        elif len(scraped_pages) == 0:
            status_type = "no_content"

        # Create result
        result = WebsiteAnalysisResult(
            domain=domain,
            pages_scraped=scraped_pages,
            total_pages=len(scraped_pages),
            scrape_success=len(scraped_pages) > 0,
            analysis_timestamp=datetime.now(UTC),
            status_type=status_type,
            robots_blocked=robots_blocked,
            parked_pages_detected=parked_pages_detected,
            total_content_length=total_content_length,
            detected_parking_service=detected_parking_service,
            error_type=primary_error_type,
        )

        if not result.scrape_success:
            if robots_blocked:
                result.error_message = "Robots.txt disallows scraping"
            elif parked_pages_detected > 0:
                result.error_message = "Domain appears to be parked/for-sale"
            else:
                result.error_message = "No pages could be scraped"

        logger.info(
            f"Website analysis complete for {domain}: {len(scraped_pages)} pages scraped"
        )

        return result


def main():
    """Test the website scraper."""
    scraper = WebsiteScraper(max_pages=5, max_depth=2)

    # Test with a few crypto project websites
    test_urls = ["https://ethereum.org", "https://bitcoin.org", "https://cardano.org"]

    for url in test_urls:
        try:
            result = scraper.scrape_website(url)

            print(f"\n=== Analysis Results for {result.domain} ===")
            print(f"Success: {result.scrape_success}")
            print(f"Pages scraped: {result.total_pages}")

            for page in result.pages_scraped:
                print(
                    f"  - {page.page_type.upper()}: {page.title} ({page.word_count} words)"
                )

        except Exception as e:
            logger.error(f"Failed to analyze {url}: {e}")

        time.sleep(2)  # Be respectful


if __name__ == "__main__":
    main()
