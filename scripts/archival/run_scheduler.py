#!/usr/bin/env python3
"""
Web Archival Scheduler Daemon

This script runs the automated web archival scheduler that executes crawls
based on configured schedules in the database.

Usage:
    # Run in daemon mode (continuous)
    python run_scheduler.py

    # Dry run (show what would be scheduled)
    python run_scheduler.py --dry-run

    # Create default schedules for all projects
    python run_scheduler.py --init-schedules
    
    # List pending jobs
    python run_scheduler.py --list-jobs
"""

import argparse
import logging
import signal
import sys
import time
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables from config/.env
config_dir = Path(__file__).parent.parent.parent / "config"
load_dotenv(config_dir / ".env")

from src.database.manager import DatabaseManager
from src.archival.scheduler import (
    ArchivalScheduler,
    SchedulerMode,
    create_default_schedules
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/archival_scheduler.log')
    ]
)
logger = logging.getLogger(__name__)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Web Archival Scheduler Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run daemon
  python run_scheduler.py
  
  # Initialize default schedules
  python run_scheduler.py --init-schedules
  
  # Dry run
  python run_scheduler.py --dry-run
  
  # List pending jobs
  python run_scheduler.py --list-jobs
  
  # Custom concurrency
  python run_scheduler.py --max-concurrent 5
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be scheduled without executing'
    )
    
    parser.add_argument(
        '--init-schedules',
        action='store_true',
        help='Create default schedules for all projects and exit'
    )
    
    parser.add_argument(
        '--list-jobs',
        action='store_true',
        help='List all pending jobs and exit'
    )
    
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=3,
        help='Maximum concurrent crawl jobs (default: 3)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize database from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not found in environment. Please check config/.env file.")
        sys.exit(1)
    
    db = DatabaseManager(database_url=database_url)
    logger.info("Database connection established")
    
    # Handle initialization mode
    if args.init_schedules:
        logger.info("Initializing default crawl schedules...")
        create_default_schedules(db)
        logger.info("✓ Default schedules created")
        return
    
    # Determine mode
    if args.dry_run:
        mode = SchedulerMode.DRY_RUN
        logger.info("Running in DRY RUN mode")
    else:
        mode = SchedulerMode.DAEMON
        logger.info("Running in DAEMON mode")
    
    # Create scheduler
    scheduler = ArchivalScheduler(
        db_manager=db,
        max_concurrent_crawls=args.max_concurrent,
        mode=mode
    )
    
    # Handle list jobs mode
    if args.list_jobs:
        scheduler.start()
        jobs = scheduler.get_pending_jobs()
        
        print("\n" + "="*80)
        print(f"PENDING SCHEDULED JOBS ({len(jobs)})")
        print("="*80)
        
        if not jobs:
            print("No jobs scheduled")
        else:
            for job in jobs:
                print(f"\n{job['name']}")
                print(f"  ID: {job['id']}")
                print(f"  Next Run: {job['next_run_time']}")
                print(f"  Trigger: {job['trigger']}")
        
        print("\n" + "="*80 + "\n")
        scheduler.stop(wait=False)
        return
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start scheduler
    try:
        scheduler.start()
        
        print("\n" + "="*80)
        print("WEB ARCHIVAL SCHEDULER DAEMON")
        print("="*80)
        print(f"Started: {datetime.now()}")
        print(f"Mode: {mode.value}")
        print(f"Max Concurrent: {args.max_concurrent}")
        print(f"Active Jobs: {len(scheduler.get_pending_jobs())}")
        print("="*80)
        print("\nPress Ctrl+C to stop\n")
        
        # Keep running
        while True:
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Shutting down scheduler...")
        scheduler.stop(wait=True)
        logger.info("Scheduler stopped cleanly")


if __name__ == '__main__':
    main()
