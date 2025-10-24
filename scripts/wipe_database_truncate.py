#!/usr/bin/env python3
"""
Fast database wipe using TRUNCATE commands.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv


def wipe_database_fast():
    """Fast wipe using TRUNCATE commands."""

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
        engine = create_engine(database_url)

        with engine.connect() as conn:
            logger.info("Using TRUNCATE for fast deletion...")

            # TRUNCATE is much faster than DELETE for large tables
            # CASCADE will handle foreign key constraints automatically
            try:
                conn.execute(
                    text("TRUNCATE TABLE crypto_projects RESTART IDENTITY CASCADE")
                )
                logger.success("Successfully truncated all tables with CASCADE")

                # Verify cleanup
                tables = [
                    "crypto_projects",
                    "project_links",
                    "project_images",
                    "project_changes",
                    "api_usage",
                ]
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
                    logger.info("All sequences have been reset to 1")
                    logger.info("Ready for fresh data collection.")
                    return True
                else:
                    logger.error("Some data may not have been properly cleaned")
                    return False

            except Exception as e:
                logger.error(f"Error during TRUNCATE: {e}")
                raise

    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        return False


def main():
    """Main function."""
    logger.info("Starting fast database wipe with TRUNCATE...")
    logger.warning("This will delete ALL data from the database!")

    success = wipe_database_fast()
    if success:
        logger.success("Database is now ready for fresh data collection!")
        logger.info("You can now run: python src/collectors/livecoinwatch.py --all")
    else:
        logger.error("Database wipe failed")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
