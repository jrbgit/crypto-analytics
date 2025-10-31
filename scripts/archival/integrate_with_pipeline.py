"""
Archival System Integration with Content Analysis Pipeline

This script provides utilities to integrate the archival system with the main
content analysis pipeline:
1. Crawl websites after they've been analyzed
2. Trigger reanalysis when significant website changes are detected
3. Schedule automated archival crawls for high-priority projects
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import select, and_, or_

# Load environment variables
config_dir = Path(__file__).parent.parent.parent / "config"
load_dotenv(config_dir / ".env")

from models.database import DatabaseManager, CryptoProject, ProjectLink, LinkContentAnalysis
from models.archival_models import (
    WebsiteSnapshot,
    SnapshotChangeDetection,
    CrawlJob,
    CrawlStatus,
)


def setup_logging(verbose: bool = False):
    """Configure logging."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )


def crawl_recently_analyzed_websites(
    db_manager: DatabaseManager,
    days_back: int = 7,
    limit: int = 10,
    dry_run: bool = True,
) -> List[int]:
    """
    Find recently analyzed websites and trigger archival crawls for them.

    Args:
        db_manager: Database manager instance
        days_back: How many days back to look for analyses
        limit: Maximum number of projects to crawl
        dry_run: If True, only log what would be done

    Returns:
        List of project IDs that were (or would be) crawled
    """
    logger.info(f"Looking for websites analyzed in the last {days_back} days...")

    with db_manager.get_session() as session:
        # Find recently analyzed website links
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        recent_analyses = (
            session.execute(
                select(LinkContentAnalysis, ProjectLink, CryptoProject)
                .join(ProjectLink, LinkContentAnalysis.link_id == ProjectLink.id)
                .join(CryptoProject, ProjectLink.project_id == CryptoProject.id)
                .filter(
                    and_(
                        ProjectLink.link_type == "website",
                        LinkContentAnalysis.created_at >= cutoff_date,
                    )
                )
                .order_by(LinkContentAnalysis.created_at.desc())
                .limit(limit)
            )
            .all()
        )

        logger.info(f"Found {len(recent_analyses)} recently analyzed websites")

        project_ids = []
        for analysis, link, project in recent_analyses:
            # Check if we already have a recent crawl
            existing_snapshot = (
                session.execute(
                    select(WebsiteSnapshot)
                    .filter(
                        and_(
                            WebsiteSnapshot.link_id == link.id,
                            WebsiteSnapshot.snapshot_timestamp >= cutoff_date,
                        )
                    )
                )
                .scalars()
                .first()
            )

            if existing_snapshot:
                logger.debug(
                    f"Skipping {project.name} - already crawled on {existing_snapshot.snapshot_timestamp}"
                )
                continue

            logger.info(
                f"{'[DRY RUN] Would crawl' if dry_run else 'Crawling'}: {project.name} ({project.code}) - {link.url}"
            )

            if not dry_run:
                # Import here to avoid circular dependencies
                import subprocess

                # Call trigger_crawl.py script
                try:
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(Path(__file__).parent / "trigger_crawl.py"),
                            "--project",
                            project.code,
                            "--engine",
                            "simple",
                            "--max-pages",
                            "50",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=300,  # 5 minute timeout
                    )

                    if result.returncode == 0:
                        logger.success(f"Successfully crawled {project.name}")
                    else:
                        logger.error(
                            f"Failed to crawl {project.name}: {result.stderr}"
                        )
                except Exception as e:
                    logger.error(f"Error crawling {project.name}: {e}")

            project_ids.append(project.id)

        return project_ids


def check_changes_and_reanalyze(
    db_manager: DatabaseManager,
    change_threshold: float = 0.3,
    days_back: int = 30,
    limit: int = 10,
    dry_run: bool = True,
) -> List[int]:
    """
    Find websites with significant changes and mark them for reanalysis.

    Args:
        db_manager: Database manager instance
        change_threshold: Minimum change score to trigger reanalysis
        days_back: Look for changes in the last N days
        limit: Maximum number of projects to reanalyze
        dry_run: If True, only log what would be done

    Returns:
        List of project IDs that need reanalysis
    """
    logger.info(
        f"Checking for significant website changes (threshold: {change_threshold})..."
    )

    with db_manager.get_session() as session:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        # Find significant changes that haven't triggered reanalysis yet
        significant_changes = (
            session.execute(
                select(SnapshotChangeDetection, WebsiteSnapshot, CryptoProject)
                .join(
                    WebsiteSnapshot,
                    SnapshotChangeDetection.new_snapshot_id == WebsiteSnapshot.id,
                )
                .join(CryptoProject, WebsiteSnapshot.project_id == CryptoProject.id)
                .filter(
                    and_(
                        SnapshotChangeDetection.change_score >= change_threshold,
                        SnapshotChangeDetection.requires_reanalysis == True,
                        SnapshotChangeDetection.diff_computed_at >= cutoff_date,
                    )
                )
                .order_by(SnapshotChangeDetection.change_score.desc())
                .limit(limit)
            )
            .all()
        )

        logger.info(
            f"Found {len(significant_changes)} websites with significant changes"
        )

        project_ids = []
        for change, snapshot, project in significant_changes:
            logger.info(
                f"{'[DRY RUN] Would reanalyze' if dry_run else 'Marking for reanalysis'}: "
                f"{project.name} ({project.code}) - Change: {change.change_score:.2%} ({change.change_type})"
            )

            if not dry_run:
                # Mark as requires_reanalysis = False since we're handling it
                change.requires_reanalysis = False
                session.commit()

                # You would integrate this with your pipeline's reanalysis logic
                # For now, just log it
                logger.info(f"Marked {project.name} for reanalysis in pipeline")

            project_ids.append(project.id)

        return project_ids


def create_schedules_for_top_projects(
    db_manager: DatabaseManager,
    top_n: int = 100,
    dry_run: bool = True,
) -> int:
    """
    Create archival schedules for top N projects by market cap.

    Args:
        db_manager: Database manager instance
        top_n: Number of top projects to schedule
        dry_run: If True, only log what would be done

    Returns:
        Number of schedules created
    """
    logger.info(f"Creating archival schedules for top {top_n} projects...")

    with db_manager.get_session() as session:
        # Get top projects with websites
        top_projects = (
            session.execute(
                select(CryptoProject, ProjectLink)
                .join(ProjectLink, CryptoProject.id == ProjectLink.project_id)
                .filter(
                    and_(
                        ProjectLink.link_type == "website",
                        ProjectLink.url.isnot(None),
                        CryptoProject.rank.isnot(None),
                    )
                )
                .order_by(CryptoProject.rank.asc())
                .limit(top_n)
            )
            .all()
        )

        logger.info(f"Found {len(top_projects)} top projects with websites")

        created_count = 0
        for project, link in top_projects:
            if project.rank <= 100:
                frequency = "WEEKLY"
                priority = 8
            elif project.rank <= 1000:
                frequency = "BIWEEKLY"
                priority = 5
            else:
                frequency = "MONTHLY"
                priority = 3

            logger.info(
                f"{'[DRY RUN] Would schedule' if dry_run else 'Scheduling'}: "
                f"{project.name} (rank #{project.rank}) - {frequency} at priority {priority}"
            )

            if not dry_run:
                # TODO: Call scheduler to create schedule
                # For now, just count
                created_count += 1

        return created_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Integrate archival system with content analysis pipeline"
    )
    parser.add_argument(
        "--action",
        choices=["crawl-recent", "check-changes", "create-schedules"],
        required=True,
        help="Action to perform",
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Number of days to look back"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of items to process"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="Change threshold for reanalysis (0-1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be done, don't actually do it",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    setup_logging(args.verbose)

    # Initialize database
    import os
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return 1
    
    db_manager = DatabaseManager(database_url)

    try:
        if args.action == "crawl-recent":
            project_ids = crawl_recently_analyzed_websites(
                db_manager,
                days_back=args.days,
                limit=args.limit,
                dry_run=args.dry_run,
            )
            logger.success(
                f"{'Would process' if args.dry_run else 'Processed'} {len(project_ids)} projects"
            )

        elif args.action == "check-changes":
            project_ids = check_changes_and_reanalyze(
                db_manager,
                change_threshold=args.threshold,
                days_back=args.days,
                limit=args.limit,
                dry_run=args.dry_run,
            )
            logger.success(
                f"{'Would trigger' if args.dry_run else 'Triggered'} reanalysis for {len(project_ids)} projects"
            )

        elif args.action == "create-schedules":
            count = create_schedules_for_top_projects(
                db_manager, top_n=args.limit, dry_run=args.dry_run
            )
            logger.success(
                f"{'Would create' if args.dry_run else 'Created'} {count} schedules"
            )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
