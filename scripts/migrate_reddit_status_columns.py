#!/usr/bin/env python3
"""
Database migration script to add Reddit status tracking columns.

This script adds Reddit-related status columns to the project_links table
to support Reddit community health monitoring.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from loguru import logger

# Add the src directory to path so we can import our models
sys.path.append(str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv


def run_migration(database_url: str):
    """Run the database schema migration to add Reddit status tracking columns."""

    logger.info("Starting database migration for Reddit status tracking columns...")

    engine = create_engine(database_url)

    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()

        try:
            # Check if columns already exist
            result = conn.execute(
                text(
                    """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'project_links' 
                AND column_name IN ('current_reddit_status', 'last_reddit_check', 'reddit_consecutive_failures', 
                                   'reddit_inactive_90_days', 'reddit_subscriber_count', 'reddit_last_post_date')
            """
                )
            )
            existing_columns = [row[0] for row in result]

            if existing_columns:
                logger.info(f"Some Reddit columns already exist: {existing_columns}")
                logger.info("Checking which columns need to be added...")

            # Define all Reddit columns that need to exist
            reddit_columns = [
                ("current_reddit_status", "VARCHAR(50) DEFAULT 'unknown'"),
                ("last_reddit_check", "TIMESTAMP WITH TIME ZONE"),
                ("reddit_consecutive_failures", "INTEGER DEFAULT 0"),
                ("reddit_inactive_90_days", "BOOLEAN DEFAULT FALSE"),
                ("reddit_subscriber_count", "INTEGER"),
                ("reddit_last_post_date", "TIMESTAMP WITH TIME ZONE"),
            ]

            # Add columns that don't exist
            for column_name, column_def in reddit_columns:
                if column_name not in existing_columns:
                    logger.info(f"Adding column: {column_name}")
                    conn.execute(
                        text(
                            f"ALTER TABLE project_links ADD COLUMN {column_name} {column_def}"
                        )
                    )
                else:
                    logger.info(f"Column {column_name} already exists, skipping")

            # Create indexes (these will be skipped if they already exist)
            try:
                logger.info("Creating index: idx_project_links_reddit_status")
                conn.execute(
                    text(
                        "CREATE INDEX idx_project_links_reddit_status ON project_links(current_reddit_status)"
                    )
                )
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Index idx_project_links_reddit_status already exists")
                else:
                    raise

            try:
                logger.info("Creating index: idx_project_links_reddit_check")
                conn.execute(
                    text(
                        "CREATE INDEX idx_project_links_reddit_check ON project_links(last_reddit_check)"
                    )
                )
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Index idx_project_links_reddit_check already exists")
                else:
                    raise

            # Commit the transaction
            trans.commit()
            logger.success("Reddit status tracking migration completed successfully!")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"Reddit status tracking migration failed: {e}")
            raise

        finally:
            conn.close()


def main():
    """Main function to run the migration."""

    # Load environment variables
    config_path = Path(__file__).parent.parent / "config" / "env"
    load_dotenv(config_path)

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return 1

    logger.info(
        f"Running Reddit status migration on database: {database_url.split('@')[1] if '@' in database_url else 'local database'}"
    )

    # Check database type
    if not database_url.startswith("postgresql"):
        logger.error("This migration script is designed for PostgreSQL databases only")
        return 1

    # Show what will be changed
    print(
        "This migration will add Reddit status tracking columns to project_links table:"
    )
    print("  • current_reddit_status (VARCHAR(50) DEFAULT 'unknown')")
    print("  • last_reddit_check (TIMESTAMP WITH TIME ZONE)")
    print("  • reddit_consecutive_failures (INTEGER DEFAULT 0)")
    print("  • reddit_inactive_90_days (BOOLEAN DEFAULT FALSE)")
    print("  • reddit_subscriber_count (INTEGER)")
    print("  • reddit_last_post_date (TIMESTAMP WITH TIME ZONE)")
    print("\nIndexes:")
    print("  • idx_project_links_reddit_status")
    print("  • idx_project_links_reddit_check")
    print()

    try:
        # Run the migration
        run_migration(database_url)

        logger.info("\nReddit status tracking migration completed successfully!")
        logger.info("The following columns have been added to project_links:")
        logger.info("  • current_reddit_status - Current status of Reddit community")
        logger.info("  • last_reddit_check - Last time Reddit was checked")
        logger.info(
            "  • reddit_consecutive_failures - Number of consecutive check failures"
        )
        logger.info("  • reddit_inactive_90_days - Whether community has been inactive")
        logger.info("  • reddit_subscriber_count - Number of subscribers")
        logger.info("  • reddit_last_post_date - Date of last post in the community")

        return 0

    except Exception as e:
        logger.error(f"Reddit status tracking migration failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
