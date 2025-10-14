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
from typing import Dict, List, Optional, Set, Tuple
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
    
    def can_fetch(self, url: str) -> bool:
        """Check if we can fetch the URL according to robots.txt."""
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            return rp.can_fetch(self.session.headers['User-Agent'], url)
        except Exception as e:
            logger.warning(f"Could not check robots.txt for {url}: {e}")
            return True  # Default to allowing if we can't check
    
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
    
    def fetch_page(self, url: str) -> Optional[ScrapedPage]:
        """Fetch and process a single page."""
        # Check URL filter first
        should_skip, skip_reason = url_filter.should_skip_url(url)
        if should_skip:
            logger.debug(f"Skipping {url}: {skip_reason}")
            return None
        
        if not self.can_fetch(url):
            logger.warning(f"Robots.txt disallows fetching {url}")
            return None
        
        try:
            logger.debug(f"Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Extract content
            content, title, links = self.extract_content(response.text, url)
            
            # Check if content indicates a parked domain
            if url_filter.is_likely_parked_domain(content):
                logger.warning(f"Detected parked/for-sale domain: {url}")
                return None
            
            # Skip if content is too minimal
            if len(content.strip()) < 50:
                logger.debug(f"Skipping {url}: minimal content ({len(content)} chars)")
                return None
            
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
            return page
            
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
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
        
        while to_visit and len(scraped_pages) < self.max_pages:
            url, depth = to_visit.pop(0)
            
            if url in visited or depth > self.max_depth:
                continue
            
            visited.add(url)
            
            # Fetch the page
            page = self.fetch_page(url)
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
        
        # Create result
        result = WebsiteAnalysisResult(
            domain=domain,
            pages_scraped=scraped_pages,
            total_pages=len(scraped_pages),
            scrape_success=len(scraped_pages) > 0,
            analysis_timestamp=datetime.now(UTC)
        )
        
        if not result.scrape_success:
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