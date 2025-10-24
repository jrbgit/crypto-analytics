#!/usr/bin/env python3
"""
Wipe PostgreSQL database and reset for fresh data collection.
Non-interactive version that wipes immediately.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from models.database import DatabaseManager


def wipe_database_direct():
    """Wipe all data from PostgreSQL database tables (non-interactive)."""

    # Load environment variables
    config_path = Path(__file__).parent.parent / "config" / "env"
    load_dotenv(config_path)

    database_url = os.getenv("DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        logger.error("DATABASE_URL not set to PostgreSQL")
        return False

    logger.info(
        f"Connecting to database: {database_url.split('@')[1] if '@' in database_url else 'local database'}"
    )

    try:
        # Use autocommit for simpler transaction handling
        engine = create_engine(database_url).execution_options(autocommit=True)

        with engine.connect() as conn:
            # Get current data counts
            tables = [
                "crypto_projects",
                "project_links",
                "project_images",
                "project_changes",
                "api_usage",
                "link_content_analysis",
                "project_analysis",
            ]

            logger.info("Current data counts:")
            total_records = 0
            for table in tables:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    logger.info(f"  {table}: {count:,} records")
                    total_records += count
                except Exception as e:
                    logger.warning(f"  {table}: Error - {e}")

            logger.info(f"Total records to delete: {total_records:,}")
            logger.info("Deleting all data...")

            # Delete data in correct order (respecting foreign keys)
            delete_order = [
                "link_content_analysis",
                "project_analysis",
                "project_changes",
                "project_images",
                "project_links",
                "api_usage",
                "crypto_projects",
            ]

            total_deleted = 0
            for table in delete_order:
                try:
                    result = conn.execute(text(f"DELETE FROM {table}"))
                    rows_deleted = result.rowcount
                    logger.success(f"Deleted {rows_deleted:,} records from {table}")
                    total_deleted += rows_deleted
                except Exception as e:
                    logger.error(f"Error deleting from {table}: {e}")
                    raise

            logger.info(f"Total records deleted: {total_deleted:,}")

            # Reset sequences to start from 1
            logger.info("Resetting sequences...")
            sequences = [
                "crypto_projects_id_seq",
                "project_links_id_seq",
                "project_images_id_seq",
                "project_changes_id_seq",
                "api_usage_id_seq",
                "link_content_analysis_id_seq",
                "project_analysis_id_seq",
            ]

            for seq in sequences:
                try:
                    conn.execute(text(f"SELECT setval('{seq}', 1, false)"))
                    logger.success(f"Reset {seq}")
                except Exception as e:
                    logger.warning(f"Could not reset {seq}: {e}")

            # Verify cleanup
            logger.info("Verifying cleanup...")
            all_clean = True
            for table in tables:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    if count == 0:
                        logger.success(f"{table}: empty")
                    else:
                        logger.error(f"{table}: still has {count} records")
                        all_clean = False
                except Exception as e:
                    logger.error(f"Error checking {table}: {e}")
                    all_clean = False

            if all_clean:
                logger.success("Database successfully wiped and reset!")
                logger.info("Ready for fresh data collection.")
                return True
            else:
                logger.error("Some data may not have been properly cleaned")
                return False

    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        return False


def main():
    """Main function."""
    logger.info("Starting database wipe operation...")
    logger.warning("This will delete ALL data from the database!")

    success = wipe_database_direct()
    if success:
        logger.success("Database is now ready for fresh data collection!")
        logger.info("You can now run: python src/collectors/livecoinwatch.py --all")
    else:
        logger.error("Database wipe failed")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
