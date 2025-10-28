#!/usr/bin/env python3
"""
Web Archival System Monitoring Tool

This script provides monitoring and analytics for the web archival system including:
- Storage usage statistics
- Crawl success rates
- Change detection frequency
- WARC file inventory
- Snapshot history

Usage:
    # Show storage summary
    python monitor_archival.py --storage
    
    # Show crawl statistics
    python monitor_archival.py --crawl-stats
    
    # Show recent changes
    python monitor_archival.py --changes
    
    # Full dashboard
    python monitor_archival.py --dashboard
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import json
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables from config/.env
config_dir = Path(__file__).parent.parent.parent / "config"
load_dotenv(config_dir / ".env")

from sqlalchemy import select, func, and_, desc
from src.database.manager import DatabaseManager
from sqlalchemy.orm import sessionmaker
from src.models.archival_models import (
    CrawlJob,
    WebsiteSnapshot,
    WARCFile,
    CDXRecord,
    Column, Boolean, Integer,
    SnapshotChangeDetection,
    CrawlSchedule,
    CrawlStatus,
    ChangeType,
    Base
)


class ArchivalMonitor:
    """Monitor and analyze web archival system metrics."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage usage statistics."""
        with self.db.session() as session:
            # Total WARCs
            total_warcs = session.execute(
                select(func.count(WARCFile.id))
            ).scalar_one()
            
            # Total storage size
            total_bytes = session.execute(
                select(func.sum(WARCFile.file_size_bytes))
            ).scalar_one() or 0
            
            # By storage backend
            backend_stats = session.execute(
                select(
                    WARCFile.storage_backend,
                    func.count(WARCFile.id),
                    func.sum(WARCFile.file_size_bytes)
                ).group_by(WARCFile.storage_backend)
            ).all()
            
            # WARC compression stats
            compressed_warcs = session.execute(
                select(func.count(WARCFile.id))
.where(WARCFile.compression.isnot(None))
            ).scalar_one()
            
            return {
                'total_warcs': total_warcs,
                'total_bytes': total_bytes,
                'total_gb': round(total_bytes / (1024**3), 2),
                'compressed_warcs': compressed_warcs,
                'compression_ratio': round(compressed_warcs / total_warcs * 100, 1) if total_warcs > 0 else 0,
                'backend_distribution': [
                    {
                        'backend': backend,
                        'count': count,
                        'bytes': size,
                        'gb': round(size / (1024**3), 2)
                    }
                    for backend, count, size in backend_stats
                ]
            }
    
    def get_crawl_stats(self, days: int = 30) -> Dict[str, Any]:

        """Get crawl job statistics."""
        with self.db.session() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Total crawls
            total_crawls = session.execute(
                select(func.count(CrawlJob.job_uuid))
                .where(CrawlJob.created_at >= cutoff)
            ).scalar_one()
            
            # By status
            status_counts = session.execute(
                select(
                    CrawlJob.status,
                    func.count(CrawlJob.job_uuid)
                )
                .where(CrawlJob.created_at >= cutoff)
                .group_by(CrawlJob.status)
            ).all()
            
            # Success rate
            completed = session.execute(
                select(func.count(CrawlJob.job_uuid))
                .where(
                    and_(
                        CrawlJob.created_at >= cutoff,
                        CrawlJob.status == CrawlStatus.COMPLETED
                    )
                )
            ).scalar_one()
            
            success_rate = round(completed / total_crawls * 100, 1) if total_crawls > 0 else 0
            
            # Average pages crawled
            avg_pages = session.execute(
                select(func.avg(CrawlJob.pages_crawled))
                .where(
                    and_(
                        CrawlJob.created_at >= cutoff,
                        CrawlJob.status == CrawlStatus.COMPLETED
                    )
                )
            ).scalar_one() or 0
            
            # Average duration (calculate from started_at and completed_at)
            completed_jobs = session.execute(
                select(CrawlJob.started_at, CrawlJob.completed_at)
                .where(
                    and_(
                        CrawlJob.created_at >= cutoff,
                        CrawlJob.status == CrawlStatus.COMPLETED,
                        CrawlJob.started_at.isnot(None),
                        CrawlJob.completed_at.isnot(None)
                    )
                )
            ).all()
            
            if completed_jobs:
                durations = [(completed - started).total_seconds() for started, completed in completed_jobs]
                avg_duration = sum(durations) / len(durations)
            else:
                avg_duration = 0
            
            return {
                'period_days': days,
                'total_crawls': total_crawls,
                'status_distribution': {
                    str(status): count
                    for status, count in status_counts
                },
                'success_rate': success_rate,
                'avg_pages_per_crawl': round(avg_pages, 1),
                'avg_duration_minutes': round(avg_duration / 60, 1)
            }
    
    def get_change_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get change detection statistics."""
        with self.db.session() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Total comparisons
            total_comparisons = session.execute(
                select(func.count(SnapshotChangeDetection.id))
                .where(SnapshotChangeDetection.diff_computed_at >= cutoff)
            ).scalar_one()
            
            # By change type
            change_types = session.execute(
                select(
                    SnapshotChangeDetection.change_type,
                    func.count(SnapshotChangeDetection.id)
                )
                .where(SnapshotChangeDetection.diff_computed_at >= cutoff)
                .group_by(SnapshotChangeDetection.change_type)
            ).all()
            
            # Significant changes
            significant_changes = session.execute(
                select(func.count(SnapshotChangeDetection.id))
                .where(
                    and_(
                        SnapshotChangeDetection.diff_computed_at >= cutoff,
                        SnapshotChangeDetection.is_significant_change == True
                    )
                )
            ).scalar_one()
            
            # Average change score
            avg_score = session.execute(
                select(func.avg(SnapshotChangeDetection.change_score))
                .where(SnapshotChangeDetection.diff_computed_at >= cutoff)
            ).scalar_one() or 0
            
            # LLM reanalysis triggered
            reanalysis_count = session.execute(
                select(func.count(SnapshotChangeDetection.id))
                .where(
                    and_(
                        SnapshotChangeDetection.diff_computed_at >= cutoff,
                        SnapshotChangeDetection.requires_reanalysis == True
                    )
                )
            ).scalar_one()
            
            return {
                'period_days': days,
                'total_comparisons': total_comparisons,
                'change_type_distribution': {
                    str(change_type): count
                    for change_type, count in change_types
                },
                'significant_changes': significant_changes,
                'significance_rate': round(significant_changes / total_comparisons * 100, 1) if total_comparisons > 0 else 0,
                'avg_change_score': round(avg_score, 3),
                'llm_reanalysis_triggered': reanalysis_count
            }
    
    def get_snapshot_stats(self) -> Dict[str, Any]:
        """Get snapshot statistics."""
        with self.db.session() as session:
            # Total snapshots
            total_snapshots = session.execute(
                select(func.count(WebsiteSnapshot.id))
            ).scalar_one()
            
            # Distinct projects with snapshots
            distinct_projects = session.execute(
                select(func.count(func.distinct(WebsiteSnapshot.project_id)))
            ).scalar_one()
            
            # Total versions
            total_versions = session.execute(
                select(func.sum(WebsiteSnapshot.version_number))
            ).scalar_one() or 0
            
            # Average versions per project
            avg_versions = total_versions / distinct_projects if distinct_projects > 0 else 0
            
            return {
                'total_snapshots': total_snapshots,
                'distinct_projects': distinct_projects,
                'avg_versions_per_project': round(avg_versions, 1)
            }
    
    def get_schedule_stats(self) -> Dict[str, Any]:
        """Get crawl schedule statistics."""
        with self.db.session() as session:
            # Total schedules
            total_schedules = session.execute(
                select(func.count(CrawlSchedule.id))
            ).scalar_one()
            
            # Enabled schedules
            enabled_schedules = session.execute(
                select(func.count(CrawlSchedule.id))
                .where(CrawlSchedule.enabled == True)
            ).scalar_one()
            
            # By frequency
            frequency_dist = session.execute(
                select(
                    CrawlSchedule.frequency,
                    func.count(CrawlSchedule.id)
                )
                .where(CrawlSchedule.enabled == True)
                .group_by(CrawlSchedule.frequency)
            ).all()
            
            return {
                'total_schedules': total_schedules,
                'enabled_schedules': enabled_schedules,
                'frequency_distribution': {
                    str(freq): count
                    for freq, count in frequency_dist
                }
            }
    
    def get_recent_changes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent significant changes."""
        with self.db.session() as session:
            changes = session.execute(
                select(SnapshotChangeDetection)
                .where(SnapshotChangeDetection.is_significant_change == True)
                .order_by(desc(SnapshotChangeDetection.diff_computed_at))
                .limit(limit)
            ).scalars().all()
            
            return [
                {
                    'id': change.id,
                    'timestamp': change.diff_computed_at.isoformat(),
                    'change_type': str(change.change_type),
                    'change_score': round(change.change_score, 3),
                    'similarity_score': round(change.similarity_score, 3) if change.similarity_score else None,
                    'requires_reanalysis': change.requires_reanalysis
                }
                for change in changes
            ]
    
    def get_recent_crawls(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent crawl jobs."""
        with self.db.session() as session:
            jobs = session.execute(
                select(CrawlJob)
                .order_by(desc(CrawlJob.created_at))
                .limit(limit)
            ).scalars().all()
            
            return [
                {
                    'job_uuid': str(job.job_uuid),
                    'created_at': job.created_at.isoformat(),
                    'status': str(job.status),
                    'pages_crawled': job.pages_crawled,
                    'duration_seconds': ((job.completed_at - job.started_at).total_seconds() if job.started_at and job.completed_at else None),
                    'has_warc_files': len(job.warc_files) > 0
                }
                for job in jobs
            ]
    
    def print_dashboard(self):
        """Print full monitoring dashboard."""
        print("\n" + "="*80)
        print("WEB ARCHIVAL SYSTEM MONITORING DASHBOARD")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")
        
        # Storage Stats
        print("📦 STORAGE STATISTICS")
        print("-" * 80)
        storage = self.get_storage_stats()
        print(f"Total WARC Files: {storage['total_warcs']:,}")
        print(f"Total Storage: {storage['total_gb']} GB ({storage['total_bytes']:,} bytes)")
        print(f"Compressed: {storage['compressed_warcs']:,} ({storage['compression_ratio']}%)")
        print("\nBy Storage Backend:")
        for backend in storage['backend_distribution']:
            print(f"  {backend['backend']}: {backend['count']:,} files, {backend['gb']} GB")
        print()
        
        # Crawl Stats
        print("🕷️  CRAWL STATISTICS (Last 30 Days)")
        print("-" * 80)
        crawls = self.get_crawl_stats(30)
        print(f"Total Crawls: {crawls['total_crawls']:,}")
        print(f"Success Rate: {crawls['success_rate']}%")
        print(f"Avg Pages/Crawl: {crawls['avg_pages_per_crawl']}")
        print(f"Avg Duration: {crawls['avg_duration_minutes']} minutes")
        print("\nBy Status:")
        for status, count in crawls['status_distribution'].items():
            print(f"  {status}: {count:,}")
        print()
        
        # Change Detection Stats
        print("🔍 CHANGE DETECTION (Last 30 Days)")
        print("-" * 80)
        changes = self.get_change_stats(30)
        print(f"Total Comparisons: {changes['total_comparisons']:,}")
        print(f"Significant Changes: {changes['significant_changes']:,} ({changes['significance_rate']}%)")
        print(f"Avg Change Score: {changes['avg_change_score']}")
        print(f"LLM Reanalysis Triggered: {changes['llm_reanalysis_triggered']:,}")
        print("\nBy Change Type:")
        for change_type, count in changes['change_type_distribution'].items():
            print(f"  {change_type}: {count:,}")
        print()
        
        # Snapshot Stats
        print("📸 SNAPSHOT STATISTICS")
        print("-" * 80)
        snapshots = self.get_snapshot_stats()
        print(f"Total Snapshots: {snapshots['total_snapshots']:,}")
        print(f"Distinct Projects: {snapshots['distinct_projects']:,}")
        print(f"Avg Versions/Project: {snapshots['avg_versions_per_project']}")
        print()
        
        # Schedule Stats
        print("⏰ SCHEDULE STATISTICS")
        print("-" * 80)
        schedules = self.get_schedule_stats()
        print(f"Total Schedules: {schedules['total_schedules']:,}")
        print(f"Enabled: {schedules['enabled_schedules']:,}")
        print("\nBy Frequency:")
        for freq, count in schedules['frequency_distribution'].items():
            print(f"  {freq}: {count:,}")
        print()
        
        # Recent Activity
        print("🕐 RECENT ACTIVITY")
        print("-" * 80)
        print("\nRecent Significant Changes:")
        recent_changes = self.get_recent_changes(5)
        for change in recent_changes:
            print(f"  [{change['timestamp']}] {change['change_type']} - Score: {change['change_score']}")
        
        print("\nRecent Crawls:")
        recent_crawls = self.get_recent_crawls(5)
        for crawl in recent_crawls:
            print(f"  [{crawl['created_at']}] {crawl['status']} - {crawl['pages_crawled']} pages")
        
        print("\n" + "="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Web Archival System Monitoring Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--dashboard',
        action='store_true',
        help='Show full monitoring dashboard'
    )
    
    parser.add_argument(
        '--storage',
        action='store_true',
        help='Show storage statistics'
    )
    
    parser.add_argument(
        '--crawl-stats',
        action='store_true',
        help='Show crawl statistics'
    )
    
    parser.add_argument(
        '--changes',
        action='store_true',
        help='Show change detection statistics'
    )
    
    parser.add_argument(
        '--schedules',
        action='store_true',
        help='Show schedule statistics'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days for time-based statistics (default: 30)'
    )
    
    args = parser.parse_args()
    
    # Initialize database
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not found in environment. Please check config/.env file.")
        sys.exit(1)
    
    db_manager = DatabaseManager(database_url=database_url)
    
    # Add a session method to DatabaseManager for compatibility with ArchivalMonitor
    Session = sessionmaker(bind=db_manager.engine)
    db_manager.session = lambda: Session()

    # Create all tables if they do not exist
    Base.metadata.create_all(db_manager.engine)
    
    monitor = ArchivalMonitor(db_manager)
    
    # Show full dashboard if no specific option
    if args.dashboard or not any([args.storage, args.crawl_stats, args.changes, args.schedules]):
        monitor.print_dashboard()
        return
    
    # Collect requested data
    data = {}
    
    if args.storage:
        data['storage'] = monitor.get_storage_stats()
    
    if args.crawl_stats:
        data['crawl_stats'] = monitor.get_crawl_stats(args.days)
    
    if args.changes:
        data['change_stats'] = monitor.get_change_stats(args.days)
    
    if args.schedules:
        data['schedule_stats'] = monitor.get_schedule_stats()
    
    # Output
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        for key, value in data.items():
            print(f"\n{key.upper()}:")
            print(json.dumps(value, indent=2))


if __name__ == '__main__':
    main()
