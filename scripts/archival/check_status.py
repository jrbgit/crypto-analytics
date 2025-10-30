#!/usr/bin/env python3
"""Check the status of the archival system."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import get_config_path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(get_config_path() / ".env")

import os
from sqlalchemy import create_engine, text

def main():
    database_url = os.getenv("DATABASE_URL")
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        print("=" * 80)
        print("ARCHIVAL SYSTEM STATUS")
        print("=" * 80)
        
        # Check crawl jobs
        print("\n=== Crawl Jobs ===")
        result = conn.execute(text("""
            SELECT status, COUNT(*) as count 
            FROM crawl_jobs 
            GROUP BY status
        """))
        job_counts = result.fetchall()
        total_jobs = sum(row[1] for row in job_counts)
        print(f"Total jobs: {total_jobs}")
        for status, count in job_counts:
            print(f"  {status}: {count}")
        
        # Show recent jobs
        print("\nRecent jobs:")
        result = conn.execute(text("""
            SELECT id, project_id, seed_url, status, created_at, started_at, completed_at 
            FROM crawl_jobs 
            ORDER BY created_at DESC 
            LIMIT 5
        """))
        recent_jobs = result.fetchall()
        for job in recent_jobs:
            url_preview = job[2][:60] + "..." if len(job[2]) > 60 else job[2]
            print(f"  Job {job[0]}: {job[3]} - {url_preview}")
            if job[6]:  # completed_at
                duration = (job[6] - job[5]).total_seconds() if job[5] else None
                print(f"    Duration: {duration:.1f}s" if duration else "    Duration: unknown")
        
        # Check website snapshots
        print("\n=== Website Snapshots ===")
        result = conn.execute(text("SELECT COUNT(*) FROM website_snapshots"))
        snapshot_count = result.fetchone()[0]
        print(f"Total snapshots: {snapshot_count}")
        
        if snapshot_count > 0:
            result = conn.execute(text("""
                SELECT project_id, seed_url, snapshot_timestamp, version_number 
                FROM website_snapshots 
                ORDER BY snapshot_timestamp DESC 
                LIMIT 5
            """))
            snapshots = result.fetchall()
            print("Recent snapshots:")
            for snap in snapshots:
                url_preview = snap[1][:60] + "..." if len(snap[1]) > 60 else snap[1]
                print(f"  Project {snap[0]}: {url_preview} (v{snap[3]})")
        
        # Check WARC files
        print("\n=== WARC Files ===")
        result = conn.execute(text("SELECT COUNT(*) FROM warc_files"))
        warc_count = result.fetchone()[0]
        print(f"Total WARC files: {warc_count}")
        
        if warc_count > 0:
            result = conn.execute(text("""
                SELECT file_path, file_size_bytes, record_count, created_at 
                FROM warc_files 
                ORDER BY created_at DESC 
                LIMIT 5
            """))
            warcs = result.fetchall()
            print("Recent WARC files:")
            for warc in warcs:
                size_mb = warc[1] / (1024 * 1024) if warc[1] else 0
                print(f"  {Path(warc[0]).name}: {size_mb:.2f} MB, {warc[2]} records")
        
        # Check crawl schedules
        print("\n=== Crawl Schedules ===")
        result = conn.execute(text("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN enabled THEN 1 ELSE 0 END) as enabled
            FROM crawl_schedules
        """))
        sched_stats = result.fetchone()
        print(f"Total schedules: {sched_stats[0]}")
        print(f"Enabled schedules: {sched_stats[1]}")
        
        if sched_stats[0] > 0:
            result = conn.execute(text("""
                SELECT cs.id, cs.project_id, cp.name, cs.frequency, cs.enabled
                FROM crawl_schedules cs
                LEFT JOIN crypto_projects cp ON cs.project_id = cp.id
                ORDER BY cs.id
                LIMIT 10
            """))
            schedules = result.fetchall()
            print("\nSchedules:")
            for sched in schedules:
                status = "OK" if sched[4] else "X"
                project_name = sched[2] or f"Project {sched[1]}"
                print(f"  {status} Schedule {sched[0]}: {project_name} - {sched[3]}")
        
        # Check for stuck jobs
        print("\n=== Potential Issues ===")
        result = conn.execute(text("""
            SELECT id, project_id, seed_url, started_at
            FROM crawl_jobs
            WHERE status = 'IN_PROGRESS'
            AND started_at < NOW() - INTERVAL '1 hour'
        """))
        stuck_jobs = result.fetchall()
        if stuck_jobs:
            print(f"⚠️  {len(stuck_jobs)} stuck job(s) (IN_PROGRESS > 1 hour):")
            for job in stuck_jobs:
                url_preview = job[2][:60] + "..." if len(job[2]) > 60 else job[2]
                print(f"  Job {job[0]}: {url_preview}")
        else:
            print("✓ No stuck jobs detected")
        
        # Check WARC/snapshot mismatch
        if warc_count > 0 and snapshot_count == 0:
            print("⚠️  WARC files exist but no snapshots recorded")
        elif warc_count > snapshot_count:
            print(f"⚠️  More WARC files ({warc_count}) than snapshots ({snapshot_count})")
        else:
            print("✓ WARC/snapshot counts look reasonable")
        
        print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
