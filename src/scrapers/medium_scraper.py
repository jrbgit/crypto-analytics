"""
Medium Scraper Module for Cryptocurrency Project Analysis

This module handles:
- Fetching Medium RSS feeds (https://medium.com/feed/@username or /publication)
- Extracting recent articles and their content
- Tracking publication frequency and patterns
- Analyzing content types (development updates vs marketing)
- RSS feed parsing and content extraction
"""

import requests
import time
import hashlib
import feedparser
import random
from urllib.parse import urljoin, urlparse, parse_qs
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
from loguru import logger
import re
from urllib.parse import urlparse, urljoin


@dataclass
class MediumArticle:
    """Represents a single Medium article with metadata."""

    url: str
    title: str
    content: str
    content_hash: str
    author: str
    published_date: datetime
    tags: List[str]
    claps: int  # Medium claps count (if available)
    reading_time: int  # Estimated reading time in minutes
    word_count: int
    article_type: str  # 'technical', 'announcement', 'marketing', 'update', 'other'


@dataclass
class MediumAnalysisResult:
    """Complete Medium publication analysis result."""

    publication_url: str
    feed_url: str
    publication_name: str
    articles_found: List[MediumArticle]
    total_articles: int
    scrape_success: bool
    error_message: Optional[str] = None
    analysis_timestamp: datetime = None
    # Publication metadata
    publication_frequency: float = 0.0  # Articles per week
    last_post_date: Optional[datetime] = None
    content_distribution: Dict[str, int] = None  # Count by article type
    avg_reading_time: float = 0.0


class MediumScraper:
    """Intelligent Medium scraper for cryptocurrency projects."""

    def __init__(
        self, max_articles: int = 20, recent_days: int = 90, delay: float = 1.0
    ):
        """
        Initialize the Medium scraper.

        Args:
            max_articles: Maximum number of recent articles to analyze
            recent_days: Only analyze articles from the last N days
            delay: Delay between requests in seconds
        """
        self.max_articles = max_articles
        self.recent_days = recent_days
        self.delay = delay
        self.session = requests.Session()
        self.request_count = 0
        self.last_request_time = 0

        # Set a reasonable user agent
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 CryptoAnalytics/1.0"
            }
        )

        # Keywords for classifying article types
        self.technical_keywords = [
            "technical",
            "development",
            "code",
            "blockchain",
            "protocol",
            "smart contract",
            "architecture",
            "implementation",
            "upgrade",
            "fork",
            "consensus",
            "node",
            "testnet",
            "mainnet",
            "sdk",
            "api",
            "integration",
            "security",
            "audit",
        ]

        self.announcement_keywords = [
            "announcement",
            "launched",
            "release",
            "introducing",
            "partnership",
            "collaboration",
            "funding",
            "investment",
            "listing",
            "exchange",
        ]

        self.marketing_keywords = [
            "community",
            "event",
            "meetup",
            "conference",
            "ama",
            "giveaway",
            "competition",
            "reward",
            "airdrop",
            "token",
            "brand",
        ]

        self.update_keywords = [
            "update",
            "progress",
            "milestone",
            "roadmap",
            "quarterly",
            "monthly",
            "weekly",
            "report",
            "summary",
            "recap",
        ]

    def _wait_with_backoff(self, attempt: int = 0):
        """
        Implement exponential backoff with jitter for rate limiting.
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        # Base delay with exponential backoff for retries
        base_delay = self.delay + (2**attempt)

        # Add random jitter (±20%)
        jitter = random.uniform(0.8, 1.2)
        total_delay = base_delay * jitter

        # Ensure minimum time between requests
        if time_since_last < total_delay:
            sleep_time = total_delay - time_since_last
            logger.debug(
                f"Rate limiting: waiting {sleep_time:.2f}s (attempt {attempt})"
            )
            time.sleep(sleep_time)

        self.last_request_time = time.time()
        self.request_count += 1

        # Add extra delay every 10 requests to avoid overwhelming server
        if self.request_count % 10 == 0:
            extra_delay = random.uniform(1, 2)
            logger.info(
                f"Extended rate limit break: {extra_delay:.2f}s after {self.request_count} requests"
            )
            time.sleep(extra_delay)

    def _make_request_with_retry(
        self, url: str, max_retries: int = 3
    ) -> requests.Response:
        """
        Make HTTP request with retry logic for 429 errors.
        """
        for attempt in range(max_retries + 1):
            try:
                self._wait_with_backoff(attempt)

                response = self.session.get(url, timeout=30)

                if response.status_code == 429:
                    if attempt < max_retries:
                        retry_delay = min(60 * (2**attempt), 300)  # Cap at 5 minutes
                        logger.warning(
                            f"Rate limited (429). Retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries + 1})"
                        )
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for {url}")
                        response.raise_for_status()

                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                    time.sleep(random.uniform(1, 3))  # Random delay before retry
                else:
                    logger.error(f"All retry attempts failed for {url}: {e}")
                    raise

        return response

    def construct_feed_url(self, medium_url: str) -> str:
        """
        Convert a Medium profile/publication URL to its RSS feed URL.

        Args:
            medium_url: Medium profile or publication URL

        Returns:
            RSS feed URL
        """
        try:
            parsed = urlparse(medium_url)

            # Handle different Medium URL patterns:
            # https://medium.com/@username -> https://medium.com/feed/@username
            # https://medium.com/publication -> https://medium.com/feed/publication
            # https://username.medium.com -> https://medium.com/feed/@username

            if parsed.netloc.endswith(".medium.com") and parsed.netloc != "medium.com":
                # Handle custom domain like username.medium.com
                username = parsed.netloc.split(".")[0]
                return f"https://medium.com/feed/@{username}"
            elif parsed.netloc == "medium.com":
                # Handle medium.com URLs
                if parsed.path.startswith("/@"):
                    # Profile URL: https://medium.com/@username
                    return f"https://medium.com/feed{parsed.path}"
                elif parsed.path.startswith("/") and len(parsed.path.split("/")) >= 2:
                    # Publication URL: https://medium.com/publication
                    publication = parsed.path.split("/")[1]
                    return f"https://medium.com/feed/{publication}"

            # Fallback: try to append /feed to the path
            return f"https://medium.com/feed{parsed.path}"

        except Exception as e:
            logger.warning(f"Could not construct feed URL from {medium_url}: {e}")
            return medium_url  # Return original if parsing fails

    def classify_article_type(self, title: str, content: str, tags: List[str]) -> str:
        """
        Classify the article type based on title, content, and tags.

        Returns:
            Article type: 'technical', 'announcement', 'marketing', 'update', 'other'
        """
        text_to_analyze = (
            f"{title} {content[:1000]}".lower()
        )  # First 1000 chars of content
        tag_text = " ".join(tags).lower()
        combined_text = f"{text_to_analyze} {tag_text}"

        # Count keyword matches for each category
        technical_count = sum(
            1 for keyword in self.technical_keywords if keyword in combined_text
        )
        announcement_count = sum(
            1 for keyword in self.announcement_keywords if keyword in combined_text
        )
        marketing_count = sum(
            1 for keyword in self.marketing_keywords if keyword in combined_text
        )
        update_count = sum(
            1 for keyword in self.update_keywords if keyword in combined_text
        )

        # Determine the category with the highest count
        category_scores = {
            "technical": technical_count,
            "announcement": announcement_count,
            "marketing": marketing_count,
            "update": update_count,
        }

        max_score = max(category_scores.values())
        if max_score == 0:
            return "other"

        # Return the category with the highest score
        for category, score in category_scores.items():
            if score == max_score:
                return category

        return "other"

    def extract_article_content(self, article_url: str) -> Tuple[str, int, int]:
        """
        Extract content from a single Medium article.

        Returns:
            Tuple of (content, reading_time_minutes, claps)
        """
        try:
            response = self._make_request_with_retry(article_url)

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script, style, and other non-content elements
            for element in soup(
                ["script", "style", "nav", "footer", "header", "aside"]
            ):
                element.decompose()

            # Try to find article content with various selectors
            content_selectors = [
                "article",
                ".postArticle-content",
                ".section-content",
                ".markup",
                '[data-testid="storyContent"]',
                "main",
            ]

            content_element = None
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    break

            if not content_element:
                content_element = soup.find("body")

            # Extract text content
            content = (
                content_element.get_text(separator=" ", strip=True)
                if content_element
                else ""
            )
            content = re.sub(r"\s+", " ", content).strip()

            # Try to extract reading time (Medium usually displays this)
            reading_time = 0
            reading_time_element = soup.find(string=re.compile(r"\d+\s*min\s*read"))
            if reading_time_element:
                match = re.search(r"(\d+)\s*min", reading_time_element)
                if match:
                    reading_time = int(match.group(1))

            # Try to extract claps count (if available)
            claps = 0
            claps_element = soup.find(attrs={"aria-label": re.compile(r"\d+\s*claps")})
            if claps_element:
                match = re.search(r"(\d+)", claps_element.get("aria-label", ""))
                if match:
                    claps = int(match.group(1))

            return content, reading_time, claps

        except Exception as e:
            logger.warning(f"Could not extract content from {article_url}: {e}")
            return "", 0, 0

    def parse_feed(self, feed_url: str) -> List[MediumArticle]:
        """
        Parse Medium RSS feed using AllOrigins proxy to bypass Cloudflare.

        Returns:
            List of MediumArticle objects
        """
        try:
            logger.info(f"Fetching RSS feed via AllOrigins: {feed_url}")

            # Use AllOrigins to bypass Cloudflare protection
            proxy_url = f"https://api.allorigins.win/raw?url={feed_url}"
            response = self._make_request_with_retry(proxy_url)

            # Parse RSS with feedparser
            feed = feedparser.parse(response.content)

            if not feed.entries:
                logger.warning(f"No entries found in RSS feed: {feed_url}")
                return []

            articles = []
            cutoff_date = datetime.now(UTC) - timedelta(days=self.recent_days)

            for entry in feed.entries[: self.max_articles]:
                try:
                    # Parse published date
                    published_date = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published_date = datetime(
                            *entry.published_parsed[:6], tzinfo=UTC
                        )
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        published_date = datetime(*entry.updated_parsed[:6], tzinfo=UTC)

                    # Skip articles older than cutoff
                    if published_date and published_date < cutoff_date:
                        continue

                    # Extract basic article info
                    title = entry.title if hasattr(entry, "title") else "No Title"
                    article_url = entry.link if hasattr(entry, "link") else ""
                    author = entry.author if hasattr(entry, "author") else "Unknown"

                    # Extract tags
                    tags = []
                    if hasattr(entry, "tags"):
                        tags = [tag.term for tag in entry.tags if hasattr(tag, "term")]

                    # Get content from RSS (summary) or fetch full content
                    rss_content = ""
                    if hasattr(entry, "summary"):
                        soup = BeautifulSoup(entry.summary, "html.parser")
                        rss_content = soup.get_text(strip=True)

                    # For full content, fetch the article page (optional, can be resource intensive)
                    full_content = rss_content  # Start with RSS content
                    reading_time = 0
                    claps = 0

                    # Skip individual article fetching to avoid Cloudflare blocking
                    # Use RSS content only for now
                    # if len(articles) < 5:  # Limit full content extraction
                    #     extracted_content, extracted_reading_time, extracted_claps = self.extract_article_content(article_url)
                    #     if extracted_content:
                    #         full_content = extracted_content
                    #         reading_time = extracted_reading_time
                    #         claps = extracted_claps

                    # Create content hash
                    content_hash = hashlib.sha256(full_content.encode()).hexdigest()

                    # Count words
                    word_count = len(full_content.split())

                    # Classify article type
                    article_type = self.classify_article_type(title, full_content, tags)

                    article = MediumArticle(
                        url=article_url,
                        title=title,
                        content=full_content,
                        content_hash=content_hash,
                        author=author,
                        published_date=published_date or datetime.now(UTC),
                        tags=tags,
                        claps=claps,
                        reading_time=reading_time,
                        word_count=word_count,
                        article_type=article_type,
                    )

                    articles.append(article)
                    logger.debug(f"Extracted article: {title} ({article_type})")

                except Exception as e:
                    logger.warning(f"Error processing RSS entry: {e}")
                    continue

            logger.info(f"Successfully parsed {len(articles)} articles from RSS feed")
            return articles

        except Exception as e:
            logger.error(f"Error parsing RSS feed {feed_url}: {e}")
            return []

    def calculate_publication_metrics(self, articles: List[MediumArticle]) -> Dict:
        """Calculate publication frequency and content distribution metrics."""
        if not articles:
            return {
                "publication_frequency": 0.0,
                "last_post_date": None,
                "content_distribution": {},
                "avg_reading_time": 0.0,
            }

        # Sort articles by date
        sorted_articles = sorted(articles, key=lambda x: x.published_date, reverse=True)

        # Calculate publication frequency (articles per week)
        if len(sorted_articles) > 1:
            date_range = (
                sorted_articles[0].published_date - sorted_articles[-1].published_date
            ).days
            if date_range > 0:
                publication_frequency = len(sorted_articles) / (date_range / 7.0)
            else:
                publication_frequency = len(sorted_articles)  # All published same day
        else:
            publication_frequency = 0.0

        # Content type distribution
        content_distribution = {}
        for article in articles:
            content_distribution[article.article_type] = (
                content_distribution.get(article.article_type, 0) + 1
            )

        # Average reading time
        reading_times = [a.reading_time for a in articles if a.reading_time > 0]
        avg_reading_time = (
            sum(reading_times) / len(reading_times) if reading_times else 0.0
        )

        return {
            "publication_frequency": publication_frequency,
            "last_post_date": sorted_articles[0].published_date,
            "content_distribution": content_distribution,
            "avg_reading_time": avg_reading_time,
        }

    def scrape_medium_publication(self, medium_url: str) -> MediumAnalysisResult:
        """
        Scrape and analyze a Medium publication or profile.

        Args:
            medium_url: Medium publication or profile URL

        Returns:
            MediumAnalysisResult with scraped content and analysis
        """
        logger.info(f"Starting Medium scraping for: {medium_url}")

        try:
            # Construct RSS feed URL
            feed_url = self.construct_feed_url(medium_url)

            # Parse RSS feed and extract articles
            articles = self.parse_feed(feed_url)

            if not articles:
                return MediumAnalysisResult(
                    publication_url=medium_url,
                    feed_url=feed_url,
                    publication_name="Unknown",
                    articles_found=[],
                    total_articles=0,
                    scrape_success=False,
                    error_message="No articles found or feed parsing failed",
                    analysis_timestamp=datetime.now(UTC),
                )

            # Calculate metrics
            metrics = self.calculate_publication_metrics(articles)

            # Extract publication name from feed or URL
            publication_name = "Unknown"
            try:
                # Try to extract from URL path
                parsed = urlparse(medium_url)
                if parsed.path.startswith("/@"):
                    publication_name = parsed.path[2:]  # Remove /@
                elif parsed.path.startswith("/"):
                    publication_name = parsed.path.split("/")[1]
            except:
                pass

            result = MediumAnalysisResult(
                publication_url=medium_url,
                feed_url=feed_url,
                publication_name=publication_name,
                articles_found=articles,
                total_articles=len(articles),
                scrape_success=True,
                analysis_timestamp=datetime.now(UTC),
                publication_frequency=metrics["publication_frequency"],
                last_post_date=metrics["last_post_date"],
                content_distribution=metrics["content_distribution"],
                avg_reading_time=metrics["avg_reading_time"],
            )

            logger.success(
                f"Medium scraping complete: {len(articles)} articles analyzed"
            )
            return result

        except Exception as e:
            logger.error(f"Medium scraping failed for {medium_url}: {e}")
            return MediumAnalysisResult(
                publication_url=medium_url,
                feed_url="",
                publication_name="Unknown",
                articles_found=[],
                total_articles=0,
                scrape_success=False,
                error_message=str(e),
                analysis_timestamp=datetime.now(UTC),
            )


# Test functionality
if __name__ == "__main__":
    scraper = MediumScraper(max_articles=10, recent_days=30)

    # Test with a few known Medium publications
    test_urls = [
        "https://medium.com/@binance",
        "https://medium.com/chainlink",
        "https://medium.com/solana-labs",
    ]

    for url in test_urls:
        print(f"\n=== Testing {url} ===")
        result = scraper.scrape_medium_publication(url)
        print(f"Success: {result.scrape_success}")
        if result.scrape_success:
            print(f"Articles found: {result.total_articles}")
            print(
                f"Publication frequency: {result.publication_frequency:.2f} posts/week"
            )
            print(f"Content distribution: {result.content_distribution}")
            print(f"Last post: {result.last_post_date}")
        else:
            print(f"Error: {result.error_message}")
