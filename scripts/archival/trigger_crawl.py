"""
Manual Crawl Trigger

CLI tool for manually triggering web archival crawls of cryptocurrency projects.
Supports crawling by project code, URL, or batch processing.
"""

import sys
import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Load environment variables from config/.env
config_dir = Path(__file__).parent.parent.parent / "config"
load_dotenv(config_dir / ".env")

from loguru import logger
from sqlalchemy import select

from models.database import DatabaseManager, CryptoProject, ProjectLink
from models.archival_models import CrawlJob, WebsiteSnapshot, WARCFile, CrawlStatus, CrawlFrequency
from archival import ArchivalCrawler, CrawlConfig, WARCStorageManager, StorageConfig


def setup_logging(verbose: bool = False):
    """Configure logging."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def create_crawl_job(
    session,
    project: CryptoProject,
    link: ProjectLink,
    config: CrawlConfig
) -> CrawlJob:
    """
    Create a crawl job record in the database.
    
    Args:
        session: Database session
        project: Crypto project
        link: Project link to crawl
        config: Crawl configuration
    
    Returns:
        Created CrawlJob
    """
    job = CrawlJob(
        link_id=link.id,
        project_id=project.id,
        seed_url=config.seed_url,
        crawl_scope=config.crawl_scope,
        max_depth=config.max_depth,
        max_pages=config.max_pages,
        crawler_engine=config.crawler_engine,
        use_javascript_rendering=config.use_javascript_rendering,
        respect_robots_txt=config.respect_robots_txt,
        rate_limit_delay=config.rate_limit_delay,
        timeout_seconds=config.timeout_seconds,
        status=CrawlStatus.PENDING,
        created_at=datetime.now(timezone.utc)
    )
    
    session.add(job)
    session.commit()
    session.refresh(job)
    
    return job


def update_crawl_job_status(
    session,
    job: CrawlJob,
    status: CrawlStatus,
    **kwargs
):
    """Update crawl job status and metrics."""
    job.status = status
    
    for key, value in kwargs.items():
        if hasattr(job, key):
            setattr(job, key, value)
    
    session.commit()


def create_snapshot(
    session,
    job: CrawlJob,
    crawl_result,
    warc_metadata: dict
) -> WebsiteSnapshot:
    """
    Create a snapshot record from crawl results.
    
    Args:
        session: Database session
        job: Crawl job
        crawl_result: Result from crawler
        warc_metadata: WARC file metadata
    
    Returns:
        Created WebsiteSnapshot
    """
    # Get previous snapshot count for versioning
    prev_count = session.query(WebsiteSnapshot)\
        .filter_by(link_id=job.link_id)\
        .count()
    
    snapshot = WebsiteSnapshot(
        link_id=job.link_id,
        project_id=job.project_id,
        crawl_job_id=job.id,
        snapshot_timestamp=datetime.now(timezone.utc),
        version_number=prev_count + 1,
        domain=job.seed_url.split('//')[-1].split('/')[0],
        seed_url=job.seed_url,
        pages_captured=warc_metadata.get('pages_count', 0),
        resources_captured=warc_metadata.get('resources_count', 0),
        total_size_bytes=crawl_result.bytes_downloaded,
        crawl_duration_seconds=crawl_result.crawl_duration,
        is_first_snapshot=(prev_count == 0),
        processing_complete=True,
        created_at=datetime.now(timezone.utc)
    )
    
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    
    return snapshot


def create_warc_record(
    session,
    job: CrawlJob,
    snapshot: WebsiteSnapshot,
    warc_path: Path,
    storage_metadata: dict
) -> WARCFile:
    """
    Create a WARC file record.
    
    Args:
        session: Database session
        job: Crawl job
        snapshot: Website snapshot
        warc_path: Path to WARC file
        storage_metadata: Storage metadata
    
    Returns:
        Created WARCFile
    """
    from archival.crawler import ArchivalCrawler
    
    # Extract metadata from WARC
    crawler = ArchivalCrawler()
    warc_metadata = crawler.extract_warc_metadata(warc_path)
    
    warc_file = WARCFile(
        crawl_job_id=job.id,
        snapshot_id=snapshot.id,
        filename=storage_metadata['filename'],
        file_format='warc.gz',
        file_path=storage_metadata['local_path'],
        storage_backend=storage_metadata['storage_backend'],
        file_size_bytes=storage_metadata['file_size'],
        file_hash_sha256=storage_metadata['file_hash'],
        compression='gzip',
        record_count=warc_metadata['record_count'],
        pages_count=warc_metadata['pages_count'],
        resources_count=warc_metadata['resources_count'],
        created_at=datetime.now(timezone.utc)
    )
    
    session.add(warc_file)
    session.commit()
    session.refresh(warc_file)
    
    return warc_file


def crawl_project(
    db_manager: DatabaseManager,
    crawler: ArchivalCrawler,
    storage_manager: WARCStorageManager,
    project_code: str,
    engine: str = "simple",
    max_depth: int = 2,
    max_pages: int = 50
) -> bool:
    """
    Crawl a project by its code.
    
    Args:
        db_manager: Database manager
        crawler: Archival crawler
        storage_manager: WARC storage manager
        project_code: Project code (e.g., 'BTC')
        engine: Crawler engine to use
        max_depth: Maximum crawl depth
        max_pages: Maximum pages to crawl
    
    Returns:
        True if successful
    """
    with db_manager.get_session() as session:
        # Find project
        project = session.query(CryptoProject)\
            .filter_by(code=project_code.upper())\
            .first()
        
        if not project:
            logger.error(f"Project not found: {project_code}")
            return False
        
        # Find website link
        link = session.query(ProjectLink)\
            .filter_by(project_id=project.id, link_type='website')\
            .first()
        
        if not link or not link.url:
            logger.error(f"No website URL found for {project.name}")
            return False
        
        logger.info(f"Crawling {project.name} ({project_code}): {link.url}")
        
        # Create crawl configuration
        config = CrawlConfig(
            seed_url=link.url,
            max_depth=max_depth,
            max_pages=max_pages,
            crawler_engine=engine,
            use_javascript_rendering=(engine != "simple"),
            rate_limit_delay=1.0
        )
        
        # Create crawl job record
        job = create_crawl_job(session, project, link, config)
        logger.info(f"Created crawl job: {job.id}")
        
        # Update job status to in_progress
        update_crawl_job_status(
            session, job,
            CrawlStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            # Execute crawl
            result = crawler.crawl(config)
            
            if not result.success:
                update_crawl_job_status(
                    session, job,
                    CrawlStatus.FAILED,
                    error_message=result.error_message,
                    completed_at=datetime.now(timezone.utc)
                )
                logger.error(f"Crawl failed: {result.error_message}")
                return False
            
            # Store WARC file
            storage_metadata = storage_manager.store_warc_file(result.warc_file_path)
            
            # Extract WARC metadata
            warc_metadata = crawler.extract_warc_metadata(result.warc_file_path)
            
            # Create snapshot
            snapshot = create_snapshot(session, job, result, warc_metadata)
            logger.success(f"Created snapshot v{snapshot.version_number}")
            
            # Create WARC record
            warc_record = create_warc_record(
                session, job, snapshot,
                result.warc_file_path,
                storage_metadata
            )
            logger.success(f"Stored WARC file: {warc_record.filename}")
            
            # Update job status to completed
            update_crawl_job_status(
                session, job,
                CrawlStatus.COMPLETED,
                pages_crawled=result.pages_crawled,
                bytes_downloaded=result.bytes_downloaded,
                completed_at=datetime.now(timezone.utc)
            )
            
            logger.success(
                f"✓ Crawl complete: {result.pages_crawled} pages, "
                f"{result.bytes_downloaded / 1024:.1f} KB"
            )
            
            return True
            
        except Exception as e:
            update_crawl_job_status(
                session, job,
                CrawlStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.now(timezone.utc)
            )
            logger.error(f"Crawl error: {e}")
            return False


def crawl_url(
    crawler: ArchivalCrawler,
    storage_manager: WARCStorageManager,
    url: str,
    engine: str = "simple",
    max_depth: int = 2,
    max_pages: int = 50
) -> bool:
    """
    Crawl an arbitrary URL (not in database).
    
    Args:
        crawler: Archival crawler
        storage_manager: WARC storage manager
        url: URL to crawl
        engine: Crawler engine to use
        max_depth: Maximum crawl depth
        max_pages: Maximum pages to crawl
    
    Returns:
        True if successful
    """
    logger.info(f"Crawling URL: {url}")
    
    config = CrawlConfig(
        seed_url=url,
        max_depth=max_depth,
        max_pages=max_pages,
        crawler_engine=engine,
        use_javascript_rendering=(engine != "simple"),
        rate_limit_delay=1.0
    )
    
    result = crawler.crawl(config)
    
    if not result.success:
        logger.error(f"Crawl failed: {result.error_message}")
        return False
    
    # Store WARC
    storage_metadata = storage_manager.store_warc_file(result.warc_file_path)
    
    logger.success(
        f"✓ Crawl complete: {result.pages_crawled} pages, "
        f"{result.bytes_downloaded / 1024:.1f} KB"
    )
    logger.info(f"WARC stored: {storage_metadata['local_path']}")
    
    return True


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Trigger manual web archival crawls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Crawl Bitcoin project
  python trigger_crawl.py --project BTC

  # Crawl with Browsertrix (requires Docker)
  python trigger_crawl.py --project ETH --engine browsertrix --max-pages 100

  # Crawl arbitrary URL
  python trigger_crawl.py --url https://uniswap.org --engine simple

  # Crawl multiple projects
  python trigger_crawl.py --project BTC --project ETH --project BNB
        """
    )
    
    parser.add_argument(
        '--project', '-p',
        action='append',
        help='Project code to crawl (can be used multiple times)'
    )
    
    parser.add_argument(
        '--url', '-u',
        help='URL to crawl (not in database)'
    )
    
    parser.add_argument(
        '--engine', '-e',
        choices=['simple', 'browsertrix', 'brozzler'],
        default='simple',
        help='Crawler engine (default: simple)'
    )
    
    parser.add_argument(
        '--max-depth', '-d',
        type=int,
        default=2,
        help='Maximum crawl depth (default: 2)'
    )
    
    parser.add_argument(
        '--max-pages', '-m',
        type=int,
        default=50,
        help='Maximum pages to crawl (default: 50)'
    )
    
    parser.add_argument(
        '--storage',
        choices=['local', 's3', 'azure'],
        default='local',
        help='Storage backend (default: local)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Initialize components
    storage_config = StorageConfig(
        backend=args.storage,
        base_path="./data/warcs"
    )
    storage_manager = WARCStorageManager(storage_config)
    crawler = ArchivalCrawler(storage_manager)
    
    # Process requests
    if args.url:
        # Crawl URL
        success = crawl_url(
            crawler,
            storage_manager,
            args.url,
            args.engine,
            args.max_depth,
            args.max_pages
        )
        sys.exit(0 if success else 1)
    
    elif args.project:
        # Crawl projects
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL not found in environment. Please check config/.env file.")
            sys.exit(1)
        
        db_manager = DatabaseManager(database_url)
        
        success_count = 0
        for project_code in args.project:
            if crawl_project(
                db_manager,
                crawler,
                storage_manager,
                project_code,
                args.engine,
                args.max_depth,
                args.max_pages
            ):
                success_count += 1
        
        logger.info(f"Completed: {success_count}/{len(args.project)} projects crawled successfully")
        sys.exit(0 if success_count == len(args.project) else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
