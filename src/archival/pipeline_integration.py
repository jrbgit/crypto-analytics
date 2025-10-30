"""
Pipeline Integration for Web Archival System

This module provides hooks to integrate the web archival system with
the existing content_analysis_pipeline, enabling:
- Auto-crawl on project discovery
- Trigger LLM reanalysis on significant website changes
- Update pipeline status logging with archival information
"""

import logging
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select
from models.database import DatabaseManager, CryptoProject
from models.archival_models import (
    WebsiteSnapshot,
    SnapshotChangeDetection,
    CrawlJob,
    CrawlSchedule,
    CrawlFrequency,
    ChangeType,
)
from .crawler import ArchivalCrawler, CrawlConfig
from .change_detector import ChangeDetector
from .scheduler import ArchivalScheduler

logger = logging.getLogger(__name__)


class ArchivalPipelineIntegration:
    """
    Integration layer between archival system and content analysis pipeline.

    This class provides methods that can be called from the pipeline at various
    stages to trigger archival operations and handle change detection.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        archival_crawler: Optional[ArchivalCrawler] = None,
        scheduler: Optional[ArchivalScheduler] = None,
    ):
        """
        Initialize the integration layer.

        Args:
            db_manager: Database manager instance
            archival_crawler: Archival crawler instance (created if None)
            scheduler: Scheduler instance (created if None)
        """
        self.db = db_manager
        self.crawler = archival_crawler or ArchivalCrawler(db_manager)
        self.scheduler = scheduler or ArchivalScheduler(db_manager)
        self.change_detector = ChangeDetector(db_manager)

    def on_project_discovered(
        self, project_id: int, website_url: str, create_schedule: bool = True
    ) -> Optional[int]:
        """
        Hook called when a new project is discovered or added.

        This initiates an immediate crawl and optionally creates a schedule
        for future automated crawls.

        Args:
            project_id: ID of the discovered project
            website_url: Website URL to archive
            create_schedule: Whether to create automated schedule

        Returns:
            Job ID of the initiated crawl, or None if failed
        """
        logger.info(f"New project discovered: {project_id} - {website_url}")

        try:
            # Create immediate crawl job
            config = CrawlerConfig(
                url=website_url, max_pages=50, max_depth=2, respect_robots_txt=True
            )

            job = self.crawler.create_crawl_job(
                project_id=project_id,
                priority=8,  # High priority for new discoveries
                config=config,
            )

            logger.info(
                f"Created initial crawl job {job.job_id} for project {project_id}"
            )

            # Execute crawl asynchronously (or queue for worker)
            # For now, run synchronously
            self.crawler.execute_crawl(job.job_id)

            # Optionally create automated schedule
            if create_schedule:
                self._create_default_schedule(project_id, website_url)

            return job.job_id

        except Exception as e:
            logger.error(
                f"Error initiating crawl for new project {project_id}: {e}",
                exc_info=True,
            )
            return None

    def on_analysis_completed(
        self, project_id: int, analysis_content_hash: str
    ) -> None:
        """
        Hook called after content analysis is completed.

        This can be used to compare with the archived version's content hash
        to detect if the live site has changed since archival.

        Args:
            project_id: Project ID
            analysis_content_hash: Hash of the analyzed content
        """
        logger.debug(f"Analysis completed for project {project_id}")

        with self.db.session() as session:
            # Get latest snapshot
            latest_snapshot = (
                session.execute(
                    select(WebsiteSnapshot)
                    .filter(WebsiteSnapshot.project_id == project_id)
                    .order_by(WebsiteSnapshot.snapshot_timestamp.desc())
                )
                .scalars()
                .first()
            )

            if not latest_snapshot:
                logger.info(f"No archived snapshot found for project {project_id}")
                return

            # Compare content hashes
            if latest_snapshot.content_hash != analysis_content_hash:
                logger.info(
                    f"Content mismatch detected for project {project_id}: "
                    f"archive={latest_snapshot.content_hash[:8]} vs live={analysis_content_hash[:8]}"
                )
                # Could trigger a new crawl here if desired

    def check_for_changes_and_reanalyze(
        self, reanalysis_threshold: float = 0.3
    ) -> List[int]:
        """
        Check all recent change detections and trigger reanalysis if needed.

        This should be called periodically (e.g., daily) to process any
        significant website changes that were detected during automated crawls.

        Args:
            reanalysis_threshold: Minimum change score to trigger reanalysis

        Returns:
            List of project IDs that need reanalysis
        """
        logger.info("Checking for significant changes requiring reanalysis...")

        projects_to_reanalyze = []

        with self.db.session() as session:
            # Find recent significant changes that require reanalysis
            significant_changes = (
                session.execute(
                    select(SnapshotChangeDetection)
                    .filter(
                        SnapshotChangeDetection.requires_llm_reanalysis == True,
                        SnapshotChangeDetection.overall_change_score
                        >= reanalysis_threshold,
                    )
                    .order_by(SnapshotChangeDetection.comparison_timestamp.desc())
                )
                .scalars()
                .all()
            )

            logger.info(
                f"Found {len(significant_changes)} changes requiring reanalysis"
            )

            for change in significant_changes:
                # Get the new snapshot
                new_snapshot = session.get(WebsiteSnapshot, change.new_snapshot_id)
                if not new_snapshot or not new_snapshot.project_id:
                    continue

                project_id = new_snapshot.project_id

                # Check if we already triggered reanalysis for this
                if change.llm_reanalysis_triggered_at:
                    logger.debug(
                        f"Reanalysis already triggered for project {project_id}"
                    )
                    continue

                logger.info(
                    f"Project {project_id} needs reanalysis - "
                    f"Change type: {change.change_type}, Score: {change.overall_change_score:.3f}"
                )

                projects_to_reanalyze.append(project_id)

                # Mark as triggered
                change.llm_reanalysis_triggered_at = datetime.utcnow()
                session.commit()

        return projects_to_reanalyze

    def trigger_reanalysis_for_project(
        self, project_id: int, reason: str = "Significant website change detected"
    ) -> bool:
        """
        Trigger reanalysis for a specific project.

        This method should be called from the pipeline to initiate a new
        content analysis cycle for a project whose website has changed.

        Args:
            project_id: Project to reanalyze
            reason: Reason for reanalysis

        Returns:
            True if reanalysis was initiated successfully
        """
        logger.info(f"Triggering reanalysis for project {project_id}: {reason}")

        try:
            with self.db.session() as session:
                project = session.get(CryptoProject, project_id)
                if not project:
                    logger.error(f"Project {project_id} not found")
                    return False

                # This would integrate with the pipeline's analysis logic
                # For now, just log the intent
                logger.info(
                    f"Would trigger reanalysis for {project.name} ({project.code})"
                )

                # In a full integration, you would call:
                # pipeline.analyze_project(project_id, force=True, reason=reason)

                return True

        except Exception as e:
            logger.error(f"Error triggering reanalysis: {e}", exc_info=True)
            return False

    def _create_default_schedule(
        self, project_id: int, website_url: str
    ) -> Optional[CrawlSchedule]:
        """
        Create a default crawl schedule for a project.

        Args:
            project_id: Project ID
            website_url: Website URL

        Returns:
            Created CrawlSchedule or None
        """
        try:
            with self.db.session() as session:
                project = session.get(CryptoProject, project_id)
                if not project:
                    return None

                # Determine frequency based on market cap rank
                if project.market_cap_rank and project.market_cap_rank <= 100:
                    frequency = CrawlFrequency.WEEKLY
                    priority = 8  # High priority
                elif project.market_cap_rank and project.market_cap_rank <= 1000:
                    frequency = CrawlFrequency.BIWEEKLY
                    priority = 5  # Normal priority
                else:
                    frequency = CrawlFrequency.MONTHLY
                    priority = 3  # Low priority

                schedule = self.scheduler.add_schedule(
                    project_id=project_id,
                    target_url=website_url,
                    frequency=frequency,
                    priority=priority,
                    max_pages=50,
                    max_depth=2,
                )

                logger.info(
                    f"Created {frequency} schedule for {project.name} "
                    f"(rank: {project.market_cap_rank})"
                )

                return schedule

        except Exception as e:
            logger.error(f"Error creating schedule: {e}", exc_info=True)
            return None

    def get_archival_status_for_project(self, project_id: int) -> dict:
        """
        Get archival status summary for a project.

        Useful for status logging and displaying in the pipeline.

        Args:
            project_id: Project ID

        Returns:
            Dictionary with archival status information
        """
        with self.db.session() as session:
            # Get snapshot count
            snapshot_count = (
                session.execute(
                    select(WebsiteSnapshot).filter(
                        WebsiteSnapshot.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )

            # Get latest snapshot
            latest_snapshot = (
                session.execute(
                    select(WebsiteSnapshot)
                    .filter(WebsiteSnapshot.project_id == project_id)
                    .order_by(WebsiteSnapshot.snapshot_timestamp.desc())
                )
                .scalars()
                .first()
            )

            # Get latest crawl job
            latest_job = (
                session.execute(
                    select(CrawlJob)
                    .filter(CrawlJob.project_id == project_id)
                    .order_by(CrawlJob.created_at.desc())
                )
                .scalars()
                .first()
            )

            # Get schedule
            schedule = (
                session.execute(
                    select(CrawlSchedule).filter(
                        CrawlSchedule.project_id == project_id,
                        CrawlSchedule.enabled == True,
                    )
                )
                .scalars()
                .first()
            )

            return {
                "has_archive": bool(latest_snapshot),
                "snapshot_count": len(snapshot_count),
                "latest_snapshot": (
                    {
                        "timestamp": (
                            latest_snapshot.snapshot_timestamp.isoformat()
                            if latest_snapshot
                            else None
                        ),
                        "version": (
                            latest_snapshot.version_number if latest_snapshot else None
                        ),
                        "pages": (
                            latest_snapshot.total_pages_archived
                            if latest_snapshot
                            else None
                        ),
                    }
                    if latest_snapshot
                    else None
                ),
                "latest_crawl": (
                    {
                        "status": str(latest_job.status) if latest_job else None,
                        "timestamp": (
                            latest_job.created_at.isoformat() if latest_job else None
                        ),
                    }
                    if latest_job
                    else None
                ),
                "has_schedule": bool(schedule),
                "schedule_frequency": (
                    str(schedule.crawl_frequency) if schedule else None
                ),
            }

    def update_pipeline_status_with_archival(
        self, project_id: int, status_logger
    ) -> None:
        """
        Update pipeline status logger with archival information.

        Args:
            project_id: Project ID
            status_logger: Status logger instance from pipeline
        """
        status = self.get_archival_status_for_project(project_id)

        if status["has_archive"]:
            status_logger.log_info(
                f"Web archive: {status['snapshot_count']} versions, "
                f"latest from {status['latest_snapshot']['timestamp']}"
            )
        else:
            status_logger.log_warning("No web archive found")

        if status["has_schedule"]:
            status_logger.log_info(f"Automated crawls: {status['schedule_frequency']}")


def create_archival_integration(
    db_manager: DatabaseManager, enable_scheduler: bool = False
) -> ArchivalPipelineIntegration:
    """
    Factory function to create archival integration instance.

    Args:
        db_manager: Database manager
        enable_scheduler: Whether to start the scheduler

    Returns:
        Configured ArchivalPipelineIntegration instance
    """
    crawler = ArchivalCrawler(db_manager)

    scheduler = None
    if enable_scheduler:
        scheduler = ArchivalScheduler(db_manager)
        scheduler.start()
        logger.info("Archival scheduler started")

    integration = ArchivalPipelineIntegration(
        db_manager=db_manager, archival_crawler=crawler, scheduler=scheduler
    )

    logger.info("Archival pipeline integration initialized")
    return integration
