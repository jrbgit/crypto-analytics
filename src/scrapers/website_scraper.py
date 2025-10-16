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
    status_type: Optional[str] = None  # 'success', 'robots_blocked', 'parked_domain', 'no_content', etc.
    robots_blocked: bool = False
    parked_pages_detected: int = 0
    total_content_length: int = 0
    detected_parking_service: Optional[str] = None
    error_type: Optional[str] = None  # Specific error type for better categorization


class WebsiteScraper:
    """Intelligent website scraper for cryptocurrency projects."""
    
    def __init__(self, max_pages: int = 10, max_depth: int = 3, delay: float = 1.0):
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
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 CryptoAnalytics/1.0'
        })
        
        # Keywords for identifying important pages
        self.important_keywords = {
            'about': ['about', 'about-us', 'company', 'story', 'mission'],
            'team': ['team', 'people', 'founders', 'leadership', 'staff'],
            'technology': ['technology', 'tech', 'technical', 'architecture', 'protocol', 'blockchain'],
            'whitepaper': ['whitepaper', 'white-paper', 'documentation', 'docs', 'paper'],
            'roadmap': ['roadmap', 'timeline', 'milestones', 'development']
        }
    
    def can_fetch(self, url: str) -> Tuple[bool, Optional[str]]:
        """Check if we can fetch the URL according to robots.txt.
        
        Returns:
            Tuple of (can_fetch: bool, error_info: Optional[str])
        """
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            return rp.can_fetch(self.session.headers['User-Agent'], url), None
        except Exception as e:
            error_msg = str(e)
            
            # Categorize robots.txt fetch errors for quieter logging
            if "getaddrinfo failed" in error_msg or "Failed to resolve" in error_msg:
                logger.debug(f"Cannot check robots.txt for {url}: DNS resolution failed")
                return True, 'dns_resolution_error'  # Allow if we can't resolve DNS
            elif "SSL" in error_msg.upper() or "certificate" in error_msg.lower():
                logger.debug(f"Cannot check robots.txt for {url}: SSL certificate error")
                return True, 'ssl_certificate_error'  # Allow if SSL issues
            elif "timeout" in error_msg.lower():
                logger.debug(f"Cannot check robots.txt for {url}: Connection timeout")
                return True, 'connection_timeout'  # Allow if timeout
            else:
                logger.debug(f"Cannot check robots.txt for {url}: {error_msg[:100]}...")
                return True, 'unknown_robots_error'  # Default to allowing if we can't check
    
    def classify_page_type(self, url: str, title: str, content: str) -> str:
        """Classify the type of page based on URL, title, and content."""
        url_lower = url.lower()
        title_lower = title.lower()
        content_lower = content.lower()[:2000]  # Check first 2000 chars
        
        for page_type, keywords in self.important_keywords.items():
            for keyword in keywords:
                if (keyword in url_lower or 
                    keyword in title_lower or 
                    content_lower.count(keyword) >= 2):  # Must appear at least twice in content
                    return page_type
        
        return 'other'
    
    def extract_content(self, html: str, url: str) -> Tuple[str, str, List[str]]:
        """
        Extract clean content, title, and links from HTML.
        
        Returns:
            Tuple of (clean_content, title, internal_links)
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script, style, nav, footer, and other non-content elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 
                           'aside', 'advertisement', '.ad', '.advertisement']):
            element.decompose()
        
        # Extract title
        title_element = soup.find('title')
        title = title_element.get_text().strip() if title_element else 'No Title'
        
        # Try to find main content area
        main_content = None
        content_selectors = [
            'main', '[role="main"]', '.main-content', '#main-content',
            '.content', '#content', 'article', '.post-content', '.entry-content'
        ]
        
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # If no main content area found, use body
        if not main_content:
            main_content = soup.find('body')
        
        if not main_content:
            main_content = soup
        
        # Extract text content
        content = main_content.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Extract internal links
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc
        
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(url, href)
            parsed_link = urlparse(absolute_url)
            
            # Only keep internal links (same domain)
            if (parsed_link.netloc == base_domain and 
                not href.startswith('#') and  # Skip anchors
                not href.startswith('mailto:') and  # Skip email links
                not href.startswith('tel:')):  # Skip phone links
                
                # Apply URL filter to each link
                should_skip, _ = url_filter.should_skip_url(absolute_url)
                if not should_skip:
                    links.append(absolute_url)
        
        return content, title, list(set(links))  # Remove duplicates
    
    def fetch_page(self, url: str) -> Tuple[Optional[ScrapedPage], Dict[str, Any]]:
        """Fetch and process a single page.
        
        Returns:
            Tuple of (ScrapedPage or None, status_info dict)
        """
        status_info = {'robots_blocked': False, 'parked_detected': False, 'parking_service': None}
        
        # Check URL filter first
        should_skip, skip_reason = url_filter.should_skip_url(url)
        if should_skip:
            logger.debug(f"Skipping {url}: {skip_reason}")
            return None, status_info
        
        can_fetch, robots_error = self.can_fetch(url)
        if not can_fetch:
            logger.debug(f"Robots.txt check failed or disallows fetching {url}")
            status_info['robots_blocked'] = True
            if robots_error:
                status_info['robots_error_type'] = robots_error
            return None, status_info
        
        try:
            logger.debug(f"Fetching: {url}")
            
            # First, make a HEAD request to check content type and size (if supported)
            try:
                head_response = self.session.head(url, timeout=15, allow_redirects=True)
                
                # Check content type to avoid downloading non-analyzable files
                content_type = head_response.headers.get('content-type', '').lower()
                if content_type:
                    # Skip if content type indicates non-analyzable file
                    non_analyzable_types = [
                        'application/octet-stream',  # Generic binary
                        'application/zip', 'application/x-zip',
                        'application/x-executable', 'application/x-msdownload',
                        'application/vnd.android.package-archive',  # APK files
                        'application/java-archive',  # JAR files
                        'application/x-deb', 'application/x-rpm',  # Package files
                        'application/x-apple-diskimage',  # DMG files
                        'audio/', 'video/', 'image/'  # Media files
                    ]
                    
                    # Check if content type starts with any non-analyzable type
                    for non_type in non_analyzable_types:
                        if content_type.startswith(non_type):
                            logger.debug(f"Skipping {url}: non-analyzable content type {content_type}")
                            return None, status_info
                
                # Check file size to avoid very large downloads
                content_length = head_response.headers.get('content-length')
                if content_length:
                    try:
                        size_mb = int(content_length) / (1024 * 1024)
                        if size_mb > 50:  # Skip files larger than 50MB
                            logger.debug(f"Skipping {url}: file too large ({size_mb:.1f}MB)")
                            return None, status_info
                    except ValueError:
                        pass  # Continue if size can't be parsed
                        
            except Exception:
                # If HEAD request fails, continue with GET (some servers don't support HEAD)
                logger.debug(f"HEAD request failed for {url}, proceeding with GET")
                pass
            
            # Now make the actual GET request
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Double-check content type after GET request
            response_content_type = response.headers.get('content-type', '').lower()
            if response_content_type and not any(analyzable in response_content_type for analyzable in ['text/', 'html', 'xml', 'json', 'application/pdf']):
                logger.debug(f"Skipping {url}: response content type not analyzable ({response_content_type})")
                return None, status_info
            
            # Extract content
            content, title, links = self.extract_content(response.text, url)
            
            # Check if content indicates a parked domain
            if url_filter.is_likely_parked_domain(content):
                logger.warning(f"Detected parked/for-sale domain: {url}")
                status_info['parked_detected'] = True
                # Try to detect parking service from content
                content_lower = content.lower()
                if 'godaddy' in content_lower:
                    status_info['parking_service'] = 'GoDaddy'
                elif 'sedo' in content_lower:
                    status_info['parking_service'] = 'Sedo'
                elif 'namecheap' in content_lower:
                    status_info['parking_service'] = 'Namecheap'
                return None, status_info
            
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
                word_count=word_count
            )
            
            logger.success(f"Scraped {url} - {page_type} page ({word_count} words)")
            return page, status_info
            
        except requests.exceptions.HTTPError as e:
            # Handle HTTP status code errors specifically
            if e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    logger.warning(f"Page not found (404) for {url} - website issue, not our code")
                    status_info['error_type'] = 'http_404_not_found'
                elif status_code == 403:
                    logger.warning(f"Access forbidden (403) for {url}")
                    status_info['error_type'] = 'http_403_forbidden'
                elif status_code == 401:
                    logger.warning(f"Authentication required (401) for {url}")
                    status_info['error_type'] = 'http_401_unauthorized'
                elif 400 <= status_code < 500:
                    logger.warning(f"Client error ({status_code}) for {url}: {e}")
                    status_info['error_type'] = f'http_{status_code}_client_error'
                elif 500 <= status_code < 600:
                    logger.warning(f"Server error ({status_code}) for {url}: {e}")
                    status_info['error_type'] = f'http_{status_code}_server_error'
                else:
                    logger.error(f"HTTP error ({status_code}) for {url}: {e}")
                    status_info['error_type'] = f'http_{status_code}_error'
            else:
                logger.error(f"HTTP error for {url}: {e}")
                status_info['error_type'] = 'http_error_no_response'
            
            return None, status_info
        except Exception as e:
            error_msg = str(e)
            
            # Categorize the error for better status logging
            if "getaddrinfo failed" in error_msg or "Failed to resolve" in error_msg:
                logger.warning(f"DNS resolution failed for {url}: Domain not found")
                status_info['error_type'] = 'dns_resolution_error'
                status_info['dns_resolved'] = False
            elif "SSL" in error_msg.upper() or "certificate" in error_msg.lower():
                logger.warning(f"SSL certificate error for {url}: {error_msg[:100]}...")
                status_info['error_type'] = 'ssl_certificate_error'
                status_info['ssl_valid'] = False
            elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logger.warning(f"Connection timeout for {url}")
                status_info['error_type'] = 'connection_timeout'
            elif "Max retries exceeded" in error_msg:
                logger.warning(f"Connection failed after retries for {url}")
                status_info['error_type'] = 'connection_retries_exhausted'
            else:
                logger.error(f"Failed to fetch {url}: {e}")
                status_info['error_type'] = 'unknown_connection_error'
            
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
            if any(kw in link_lower for kw in self.important_keywords['about']):
                score += 10
            if any(kw in link_lower for kw in self.important_keywords['team']):
                score += 10
            if any(kw in link_lower for kw in self.important_keywords['technology']):
                score += 10
            if any(kw in link_lower for kw in self.important_keywords['whitepaper']):
                score += 15  # Whitepapers are especially important
            if any(kw in link_lower for kw in self.important_keywords['roadmap']):
                score += 8
            
            # Penalize very long URLs or those with many parameters
            if len(link) > 100:
                score -= 2
            if '?' in link and len(parse_qs(urlparse(link).query)) > 3:
                score -= 3
            
            # Penalize common unimportant pages
            skip_patterns = ['privacy', 'terms', 'cookie', 'legal', 'support', 
                           'contact', 'faq', 'help', 'login', 'register']
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
        primary_error_type = None  # Track the most common or first encountered error type
        
        while to_visit and len(scraped_pages) < self.max_pages:
            url, depth = to_visit.pop(0)
            
            if url in visited or depth > self.max_depth:
                continue
            
            visited.add(url)
            
            # Fetch the page
            page, status_info = self.fetch_page(url)
            
            # Track status information
            if status_info['robots_blocked']:
                robots_blocked = True
            if status_info['parked_detected']:
                parked_pages_detected += 1
                if status_info['parking_service']:
                    detected_parking_service = status_info['parking_service']
            
            # Track error types for better status reporting
            if 'error_type' in status_info and status_info['error_type'] and not primary_error_type:
                primary_error_type = status_info['error_type']
            
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
        status_type = 'success'
        if robots_blocked and len(scraped_pages) == 0:
            status_type = 'robots_blocked'
        elif parked_pages_detected > 0 and len(scraped_pages) == 0:
            status_type = 'parked_domain'
        elif len(scraped_pages) == 0:
            status_type = 'no_content'
        
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
            error_type=primary_error_type
        )
        
        if not result.scrape_success:
            if robots_blocked:
                result.error_message = "Robots.txt disallows scraping"
            elif parked_pages_detected > 0:
                result.error_message = "Domain appears to be parked/for-sale"
            else:
                result.error_message = "No pages could be scraped"
        
        logger.info(f"Website analysis complete for {domain}: {len(scraped_pages)} pages scraped")
        
        return result


def main():
    """Test the website scraper."""
    scraper = WebsiteScraper(max_pages=5, max_depth=2)
    
    # Test with a few crypto project websites
    test_urls = [
        "https://ethereum.org",
        "https://bitcoin.org",
        "https://cardano.org"
    ]
    
    for url in test_urls:
        try:
            result = scraper.scrape_website(url)
            
            print(f"\n=== Analysis Results for {result.domain} ===")
            print(f"Success: {result.scrape_success}")
            print(f"Pages scraped: {result.total_pages}")
            
            for page in result.pages_scraped:
                print(f"  - {page.page_type.upper()}: {page.title} ({page.word_count} words)")
                
        except Exception as e:
            logger.error(f"Failed to analyze {url}: {e}")
        
        time.sleep(2)  # Be respectful


if __name__ == "__main__":
    main()