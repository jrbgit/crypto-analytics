"""
Archival Crawler

Wrapper for web archival crawlers (Brozzler, Browsertrix, simple HTTP).
Generates WARC files from website crawls with JavaScript rendering support.
"""

import os
import subprocess
import json
import time
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin
import requests

from loguru import logger
from bs4 import BeautifulSoup

from .storage import WARCStorageManager, StorageConfig


@dataclass
class CrawlConfig:
    """Configuration for a crawl job."""

    seed_url: str
    max_depth: int = 3
    max_pages: int = 1000
    crawl_scope: str = "domain"  # domain, subdomain, path

    # URL filtering
    url_patterns_include: List[str] = None
    url_patterns_exclude: List[str] = None
    respect_robots_txt: bool = True

    # Crawler settings
    crawler_engine: str = "browsertrix"  # browsertrix, brozzler, simple
    use_javascript_rendering: bool = True
    javascript_timeout: int = 30

    # Rate limiting
    rate_limit_delay: float = 1.0
    timeout_seconds: int = 3600

    # User agent
    user_agent: str = (
        "Mozilla/5.0 (compatible; CryptoAnalytics/1.0; +http://cryptoanalytics.io/bot)"
    )


@dataclass
class CrawlResult:
    """Result from a crawl operation."""

    success: bool
    pages_crawled: int
    bytes_downloaded: int
    warc_file_path: Optional[Path] = None
    crawl_duration: float = 0
    error_message: Optional[str] = None
    urls_discovered: List[str] = None


class ArchivalCrawler:
    """Manages archival crawling with multiple engine support."""

    def __init__(self, storage_manager: WARCStorageManager = None):
        """
        Initialize the archival crawler.

        Args:
            storage_manager: WARC storage manager instance
        """
        self.storage_manager = storage_manager or WARCStorageManager()

    def crawl(
        self, config: CrawlConfig, output_path: Optional[Path] = None
    ) -> CrawlResult:
        """
        Execute a crawl with the configured engine.

        Args:
            config: Crawl configuration
            output_path: Optional output path for WARC file

        Returns:
            CrawlResult with crawl statistics
        """
        logger.info(
            f"Starting crawl of {config.seed_url} with engine: {config.crawler_engine}"
        )
        start_time = time.time()

        try:
            if config.crawler_engine == "browsertrix":
                result = self._crawl_with_browsertrix(config, output_path)
            elif config.crawler_engine == "brozzler":
                result = self._crawl_with_brozzler(config, output_path)
            elif config.crawler_engine == "simple":
                result = self._crawl_simple(config, output_path)
            else:
                raise ValueError(f"Unknown crawler engine: {config.crawler_engine}")

            result.crawl_duration = time.time() - start_time
            logger.success(
                f"Crawl completed: {result.pages_crawled} pages in {result.crawl_duration:.1f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            return CrawlResult(
                success=False,
                pages_crawled=0,
                bytes_downloaded=0,
                crawl_duration=time.time() - start_time,
                error_message=str(e),
            )

    def _crawl_with_browsertrix(
        self, config: CrawlConfig, output_path: Optional[Path] = None
    ) -> CrawlResult:
        """
        Crawl using Browsertrix Crawler (modern, Docker-based).

        Args:
            config: Crawl configuration
            output_path: Output path for WARC

        Returns:
            CrawlResult
        """
        # Create temporary directory for crawl
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create crawl configuration file
            crawl_config = {
                "seeds": [{"url": config.seed_url, "scopeType": config.crawl_scope}],
                "combineWARC": True,
                "generateWACZ": False,
                "collection": "crypto_archive",
                "saveState": "never",
                "behaviors": (
                    "autoscroll,autoplay,autofetch,siteSpecific"
                    if config.use_javascript_rendering
                    else ""
                ),
                "behaviorTimeout": config.javascript_timeout
                * 1000,  # Convert to milliseconds
                "pageLoadTimeout": config.javascript_timeout * 1000,
                "delay": int(config.rate_limit_delay * 1000),
                "limit": config.max_pages,
                "maxPageLimit": config.max_pages,
                "depth": config.max_depth,
                "userAgent": config.user_agent,
                "exclude": config.url_patterns_exclude or [],
            }

            config_file = temp_path / "crawl-config.json"
            with open(config_file, "w") as f:
                json.dump(crawl_config, f, indent=2)

            logger.info(f"Browsertrix config: {crawl_config}")

            # Run Docker container
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{temp_path}:/output",
                "-v",
                f"{config_file}:/app/crawl-config.json:ro",
                "webrecorder/browsertrix-crawler",
                "crawl",
                "--config",
                "/app/crawl-config.json",
            ]

            process = None
            try:
                logger.info(f"Running: {' '.join(docker_cmd)}")
                process = subprocess.Popen(
                    docker_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                try:
                    stdout, stderr = process.communicate(timeout=config.timeout_seconds)
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    # Kill the Docker container on timeout
                    logger.warning(
                        f"Crawl timeout after {config.timeout_seconds}s, killing container..."
                    )
                    process.kill()
                    try:
                        # Also try to find and stop the container
                        subprocess.run(
                            [
                                "docker",
                                "ps",
                                "-q",
                                "--filter",
                                "ancestor=webrecorder/browsertrix-crawler",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                    except:
                        pass  # Best effort

                    stdout, stderr = process.communicate()
                    logger.error(f"Crawl timeout after {config.timeout_seconds}s")
                    return CrawlResult(
                        success=False,
                        pages_crawled=0,
                        bytes_downloaded=0,
                        error_message="Crawl timeout",
                    )

                if returncode != 0:
                    logger.error(f"Browsertrix failed: {stderr}")
                    return CrawlResult(
                        success=False,
                        pages_crawled=0,
                        bytes_downloaded=0,
                        error_message=stderr,
                    )

                # Find generated WARC file
                warc_files = list(temp_path.glob("collections/**/*.warc.gz"))
                if not warc_files:
                    return CrawlResult(
                        success=False,
                        pages_crawled=0,
                        bytes_downloaded=0,
                        error_message="No WARC file generated",
                    )

                warc_file = warc_files[0]

                # Move WARC to output location
                if output_path:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    warc_file.rename(output_path)
                    final_path = output_path
                else:
                    final_path = warc_file

                # Parse statistics from output
                pages_crawled = stdout.count("Fetched:")  # Rough estimate

                return CrawlResult(
                    success=True,
                    pages_crawled=pages_crawled,
                    bytes_downloaded=(
                        final_path.stat().st_size if final_path.exists() else 0
                    ),
                    warc_file_path=final_path,
                )
            except Exception as e:
                logger.error(f"Browsertrix error: {e}")
                if process and process.poll() is None:
                    process.kill()
                return CrawlResult(
                    success=False,
                    pages_crawled=0,
                    bytes_downloaded=0,
                    error_message=str(e),
                )

    def _crawl_with_brozzler(
        self, config: CrawlConfig, output_path: Optional[Path] = None
    ) -> CrawlResult:
        """
        Crawl using Brozzler (legacy, requires more setup).

        Note: This is a placeholder. Full Brozzler integration requires
        RethinkDB and more complex setup.

        Args:
            config: Crawl configuration
            output_path: Output path for WARC

        Returns:
            CrawlResult
        """
        logger.warning(
            "Brozzler integration not fully implemented. Falling back to simple crawler."
        )
        return self._crawl_simple(config, output_path)

    def _crawl_simple(
        self, config: CrawlConfig, output_path: Optional[Path] = None
    ) -> CrawlResult:
        """
        Simple HTTP-based crawler without JavaScript rendering.
        Useful for static websites.

        Args:
            config: Crawl configuration
            output_path: Output path for WARC

        Returns:
            CrawlResult
        """
        logger.info(f"Starting simple crawl (no JS rendering)")

        # Generate output path if not provided
        if output_path is None:
            timestamp = datetime.now(timezone.utc)
            domain = urlparse(config.seed_url).netloc.replace(".", "_")
            filename = self.storage_manager.generate_warc_filename(domain, timestamp)
            output_path = self.storage_manager.get_storage_path(filename, timestamp)

        # Create WARC writer
        writer = self.storage_manager.create_warc_writer(output_path)

        # Crawl state
        visited_urls: Set[str] = set()
        to_visit: List[tuple] = [(config.seed_url, 0)]  # (url, depth)
        pages_crawled = 0
        bytes_downloaded = 0
        base_domain = urlparse(config.seed_url).netloc

        session = requests.Session()
        session.headers.update({"User-Agent": config.user_agent})

        while to_visit and pages_crawled < config.max_pages:
            url, depth = to_visit.pop(0)

            if url in visited_urls or depth > config.max_depth:
                continue

            # Apply scope rules
            url_domain = urlparse(url).netloc
            if config.crawl_scope == "domain" and not url_domain.endswith(base_domain):
                continue

            try:
                logger.debug(f"Fetching: {url} (depth {depth})")

                # Fetch URL
                response = session.get(url, timeout=30, allow_redirects=True)
                visited_urls.add(url)
                pages_crawled += 1
                bytes_downloaded += len(response.content)

                # Write to WARC
                self.storage_manager.write_response_record(
                    writer,
                    url,
                    {
                        "status_code": response.status_code,
                        "headers": list(response.headers.items()),
                    },
                    response.content,
                    datetime.now(timezone.utc),
                )

                # Extract links if HTML
                if "text/html" in response.headers.get("Content-Type", ""):
                    soup = BeautifulSoup(response.content, "html.parser")

                    for link in soup.find_all("a", href=True):
                        next_url = urljoin(url, link["href"])

                        # Basic filtering
                        if next_url.startswith("http") and next_url not in visited_urls:
                            to_visit.append((next_url, depth + 1))

                # Rate limiting
                time.sleep(config.rate_limit_delay)

            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")
                continue

        # Close WARC writer
        if hasattr(writer, "out"):
            writer.out.close()

        logger.info(
            f"Simple crawl complete: {pages_crawled} pages, {bytes_downloaded} bytes"
        )

        return CrawlResult(
            success=True,
            pages_crawled=pages_crawled,
            bytes_downloaded=bytes_downloaded,
            warc_file_path=output_path,
            urls_discovered=list(visited_urls),
        )

    def validate_warc(self, warc_path: Path) -> bool:
        """
        Validate a WARC file.

        Args:
            warc_path: Path to WARC file

        Returns:
            True if valid
        """
        try:
            from warcio.archiveiterator import ArchiveIterator

            with open(warc_path, "rb") as f:
                record_count = 0
                for record in ArchiveIterator(f):
                    record_count += 1

                logger.info(f"WARC validation: {record_count} records found")
                return record_count > 0

        except Exception as e:
            logger.error(f"WARC validation failed: {e}")
            return False

    def extract_warc_metadata(self, warc_path: Path) -> Dict:
        """
        Extract metadata from a WARC file.

        Args:
            warc_path: Path to WARC file

        Returns:
            Metadata dictionary
        """
        from warcio.archiveiterator import ArchiveIterator

        metadata = {
            "record_count": 0,
            "pages_count": 0,
            "resources_count": 0,
            "total_size": warc_path.stat().st_size if warc_path.exists() else 0,
            "urls": [],
        }

        try:
            with open(warc_path, "rb") as f:
                for record in ArchiveIterator(f):
                    metadata["record_count"] += 1

                    if record.rec_type == "response":
                        url = record.rec_headers.get_header("WARC-Target-URI")
                        if url:
                            metadata["urls"].append(url)

                            # Classify as page or resource
                            content_type = (
                                record.http_headers.get_header("Content-Type")
                                if record.http_headers
                                else ""
                            )
                            if "text/html" in content_type:
                                metadata["pages_count"] += 1
                            else:
                                metadata["resources_count"] += 1

            logger.info(
                f"Extracted metadata from WARC: {metadata['record_count']} records"
            )

        except Exception as e:
            logger.error(f"Failed to extract WARC metadata: {e}")

        return metadata
