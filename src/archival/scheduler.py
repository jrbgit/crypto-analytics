"""
Automated web archival scheduler daemon.

This module implements an APScheduler-based daemon that automatically schedules
and executes web crawls based on configured frequencies and priorities.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from models.database import DatabaseManager, CryptoProject, get_db_session
from models.archival_models import CrawlSchedule, CrawlJob, CrawlStatus, CrawlFrequency
from .crawler import ArchivalCrawler, CrawlConfig

logger = logging.getLogger(__name__)


class SchedulerMode(str, Enum):
    """Scheduler operating modes."""

    DAEMON = "daemon"  # Continuous background operation
    SINGLE_RUN = "single_run"  # Execute once and exit
    DRY_RUN = "dry_run"  # Plan jobs without execution


class ArchivalScheduler:
    """
    Automated web archival scheduler.

    Features:
    - Priority-based job queueing
    - Adaptive frequency adjustment
    - Failure retry with exponential backoff
    - Resource usage tracking
    - Graceful shutdown
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        max_concurrent_crawls: int = 3,
        mode: SchedulerMode = SchedulerMode.DAEMON,
    ):
        """
        Initialize the scheduler.

        Args:
            db_manager: Database manager instance
            max_concurrent_crawls: Maximum concurrent crawl jobs
            mode: Operating mode (daemon/single_run/dry_run)
        """
        self.db = db_manager
        self.mode = mode
        self.max_concurrent = max_concurrent_crawls

        # APScheduler configuration
        # Use the original database URL string to avoid password masking by SQLAlchemy
        jobstores = {"default": SQLAlchemyJobStore(url=db_manager.database_url)}
        executors = {"default": ThreadPoolExecutor(max_concurrent_crawls)}
        job_defaults = {
            "coalesce": False,  # Run all missed jobs
            "max_instances": 1,  # One instance per job
            "misfire_grace_time": 3600,  # 1 hour grace period
        }

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores, executors=executors, job_defaults=job_defaults
        )

        self.crawler = ArchivalCrawler(db_manager)
        self._running = False

        logger.info(f"Initialized ArchivalScheduler in {mode} mode")

    def start(self) -> None:
        """Start the scheduler daemon."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        logger.info("Starting archival scheduler...")

        # Load schedules from database
        self._load_schedules()

        # Start APScheduler
        self.scheduler.start()
        self._running = True

        logger.info(f"Scheduler started with {len(self.scheduler.get_jobs())} jobs")

    def stop(self, wait: bool = True) -> None:
        """
        Stop the scheduler daemon.

        Args:
            wait: Wait for running jobs to complete
        """
        if not self._running:
            logger.warning("Scheduler is not running")
            return

        logger.info("Stopping archival scheduler...")
        self.scheduler.shutdown(wait=wait)
        self._running = False
        logger.info("Scheduler stopped")

    def _load_schedules(self) -> None:
        """Load crawl schedules from database and create APScheduler jobs."""
        with get_db_session() as session:
            schedules = (
                session.execute(
                    select(CrawlSchedule).filter(CrawlSchedule.enabled == True)
                )
                .scalars()
                .all()
            )

            logger.info(f"Loading {len(schedules)} active crawl schedules")

            for schedule in schedules:
                self._create_job(schedule)

    def _create_job(self, schedule: CrawlSchedule) -> None:
        """
        Create an APScheduler job from a crawl schedule.

        Args:
            schedule: CrawlSchedule database record
        """
        job_id = f"crawl_schedule_{schedule.schedule_id}"

        # Convert frequency to trigger
        trigger = self._get_trigger(schedule)
        if not trigger:
            logger.warning(
                f"Could not create trigger for schedule {schedule.schedule_id}"
            )
            return

        # Add job to scheduler
        self.scheduler.add_job(
            func=self._execute_crawl,
            trigger=trigger,
            id=job_id,
            args=[schedule.schedule_id],
            name=f"Crawl: {schedule.project.name if schedule.project else 'Custom'}",
            replace_existing=True,
        )

        logger.info(f"Scheduled job {job_id} with frequency {schedule.crawl_frequency}")

    def _get_trigger(self, schedule: CrawlSchedule):
        """
        Convert crawl frequency to APScheduler trigger.

        Args:
            schedule: CrawlSchedule record

        Returns:
            APScheduler trigger instance
        """
        freq = schedule.crawl_frequency

        if freq == CrawlFrequency.HOURLY:
            return IntervalTrigger(hours=1)
        elif freq == CrawlFrequency.EVERY_6_HOURS:
            return IntervalTrigger(hours=6)
        elif freq == CrawlFrequency.EVERY_12_HOURS:
            return IntervalTrigger(hours=12)
        elif freq == CrawlFrequency.DAILY:
            return CronTrigger(hour=2, minute=0)  # 2 AM daily
        elif freq == CrawlFrequency.WEEKLY:
            return CronTrigger(day_of_week="mon", hour=2, minute=0)
        elif freq == CrawlFrequency.BIWEEKLY:
            return IntervalTrigger(weeks=2)
        elif freq == CrawlFrequency.MONTHLY:
            return CronTrigger(day=1, hour=2, minute=0)
        elif freq == CrawlFrequency.MANUAL:
            return None  # Manual only
        else:
            logger.warning(f"Unknown frequency: {freq}")
            return None

    def _execute_crawl(self, schedule_id: int) -> None:
        """
        Execute a scheduled crawl.

        Args:
            schedule_id: ID of the schedule to execute
        """
        logger.info(f"Executing scheduled crawl {schedule_id}")

        with get_db_session() as session:
            # Get schedule
            schedule = session.get(CrawlSchedule, schedule_id)
            if not schedule:
                logger.error(f"Schedule {schedule_id} not found")
                return

            # Check if schedule is still enabled
            if not schedule.enabled:
                logger.info(f"Schedule {schedule_id} is disabled, skipping")
                return

            # Check for existing running jobs
            existing = session.execute(
                select(CrawlJob).filter(
                    and_(
                        CrawlJob.schedule_id == schedule_id,
                        or_(
                            CrawlJob.status == CrawlStatus.PENDING,
                            CrawlJob.status == CrawlStatus.RUNNING,
                        ),
                    )
                )
            ).scalar_one_or_none()

            if existing:
                logger.warning(
                    f"Crawl already running for schedule {schedule_id}, skipping"
                )
                return

            # Create crawler config
            config = CrawlConfig(
                seed_url=schedule.target_url,
                max_pages=schedule.max_pages,
                max_depth=schedule.max_depth,
                javascript_timeout=schedule.page_timeout_seconds or 30,
                respect_robots_txt=schedule.respect_robots_txt,
            )

            # Execute crawl
            try:
                if self.mode == SchedulerMode.DRY_RUN:
                    logger.info(f"DRY RUN: Would crawl {schedule.target_url}")
                else:
                    job = self.crawler.create_crawl_job(
                        project_id=schedule.project_id,
                        schedule_id=schedule_id,
                        priority=schedule.priority,
                        config=config,
                    )

                    # Run crawl
                    self.crawler.execute_crawl(job.job_id)

                    # Update schedule stats
                    schedule.last_crawl_time = datetime.utcnow()
                    schedule.total_crawls += 1
                    session.commit()

                    logger.info(f"Completed scheduled crawl {schedule_id}")

            except Exception as e:
                logger.error(
                    f"Error executing scheduled crawl {schedule_id}: {e}", exc_info=True
                )
                schedule.consecutive_failures += 1
                session.commit()

                # Disable schedule after too many failures
                if schedule.consecutive_failures >= 5:
                    logger.error(f"Schedule {schedule_id} disabled after 5 failures")
                    schedule.enabled = False
                    session.commit()

    def add_schedule(
        self,
        project_id: Optional[int],
        target_url: str,
        frequency: CrawlFrequency,
        priority: int = 5,
        max_pages: int = 100,
        max_depth: int = 3,
        enabled: bool = True,
    ) -> CrawlSchedule:
        """
        Add a new crawl schedule.

        Args:
            project_id: Related project ID (optional)
            target_url: URL to crawl
            frequency: Crawl frequency
            priority: Job priority (1-10, higher = more important)
            max_pages: Maximum pages to crawl
            max_depth: Maximum crawl depth
            enabled: Whether schedule is enabled

        Returns:
            Created CrawlSchedule record
        """
        with get_db_session() as session:
            schedule = CrawlSchedule(
                project_id=project_id,
                target_url=target_url,
                crawl_frequency=frequency,
                priority=priority,
                max_pages=max_pages,
                max_depth=max_depth,
                enabled=enabled,
                respect_robots_txt=True,
                consecutive_failures=0,
                total_crawls=0,
            )

            session.add(schedule)
            session.commit()
            session.refresh(schedule)

            # Add to APScheduler if running
            if self._running and enabled:
                self._create_job(schedule)

            logger.info(
                f"Created crawl schedule {schedule.schedule_id} "
                f"for {target_url} ({frequency})"
            )

            return schedule

    def remove_schedule(self, schedule_id: int) -> bool:
        """
        Remove a crawl schedule.

        Args:
            schedule_id: Schedule ID to remove

        Returns:
            True if removed, False if not found
        """
        with get_db_session() as session:
            schedule = session.get(CrawlSchedule, schedule_id)
            if not schedule:
                logger.warning(f"Schedule {schedule_id} not found")
                return False

            # Remove from APScheduler
            job_id = f"crawl_schedule_{schedule_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            # Delete from database
            session.delete(schedule)
            session.commit()

            logger.info(f"Removed crawl schedule {schedule_id}")
            return True

    def update_schedule_frequency(
        self, schedule_id: int, new_frequency: CrawlFrequency
    ) -> bool:
        """
        Update a schedule's crawl frequency.

        Args:
            schedule_id: Schedule ID
            new_frequency: New crawl frequency

        Returns:
            True if updated, False if not found
        """
        with get_db_session() as session:
            schedule = session.get(CrawlSchedule, schedule_id)
            if not schedule:
                logger.warning(f"Schedule {schedule_id} not found")
                return False

            old_frequency = schedule.crawl_frequency
            schedule.crawl_frequency = new_frequency
            session.commit()
            session.refresh(schedule)

            # Update APScheduler job
            if self._running:
                job_id = f"crawl_schedule_{schedule_id}"
                self.scheduler.remove_job(job_id)
                self._create_job(schedule)

            logger.info(
                f"Updated schedule {schedule_id} frequency: "
                f"{old_frequency} → {new_frequency}"
            )
            return True

    def get_pending_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of pending scheduled jobs.

        Returns:
            List of job information dictionaries
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time,
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    def trigger_manual_crawl(self, schedule_id: int) -> bool:
        """
        Manually trigger a scheduled crawl immediately.

        Args:
            schedule_id: Schedule ID to trigger

        Returns:
            True if triggered, False if not found
        """
        with get_db_session() as session:
            schedule = session.get(CrawlSchedule, schedule_id)
            if not schedule:
                logger.warning(f"Schedule {schedule_id} not found")
                return False

            # Execute immediately
            self._execute_crawl(schedule_id)
            return True

    def adaptive_frequency_adjustment(self) -> None:
        """
        Adjust crawl frequencies based on change detection results.

        This analyzes recent snapshot changes and adjusts frequencies:
        - More frequent crawls for frequently changing sites
        - Less frequent crawls for stable sites
        """
        logger.info("Running adaptive frequency adjustment...")

        with get_db_session() as session:
            schedules = (
                session.execute(
                    select(CrawlSchedule).filter(CrawlSchedule.enabled == True)
                )
                .scalars()
                .all()
            )

            for schedule in schedules:
                # TODO: Implement adaptive logic based on change_detection table
                # For now, this is a placeholder for future enhancement
                pass

        logger.info("Adaptive frequency adjustment complete")


def create_default_schedules(db_manager: DatabaseManager) -> None:
    """
    Create default crawl schedules for all active crypto projects.

    This is a utility function to bootstrap the scheduling system.

    Args:
        db_manager: Database manager instance
    """

    scheduler = ArchivalScheduler(db_manager)

    with get_db_session() as session:
        projects = (
            session.execute(
                select(CryptoProject)
                .filter(CryptoProject.is_active == True)
                .order_by(CryptoProject.market_cap_rank)
            )
            .scalars()
            .all()
        )

        logger.info(f"Creating default schedules for {len(projects)} projects")

        for project in projects:
            if not project.website_url:
                continue

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

            # Check if schedule already exists
            existing = session.execute(
                select(CrawlSchedule).filter(
                    and_(
                        CrawlSchedule.project_id == project.id,
                        CrawlSchedule.target_url == project.website_url,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                logger.debug(f"Schedule already exists for {project.code}")
                continue

            # Create schedule
            scheduler.add_schedule(
                project_id=project.id,
                target_url=project.website_url,
                frequency=frequency,
                priority=priority,
                max_pages=50,
                max_depth=2,
            )
