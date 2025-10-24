#!/usr/bin/env python3
"""
Database migration script to add reddit_status_log table.

This script creates the reddit_status_log table for detailed Reddit status tracking.
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
    """Run the database schema migration to add reddit_status_log table."""

    logger.info("Starting database migration for reddit_status_log table...")

    engine = create_engine(database_url)

    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()

        try:
            # Check if table already exists
            result = conn.execute(
                text(
                    """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'reddit_status_log'
                )
            """
                )
            )
            table_exists = result.scalar()

            if table_exists:
                logger.info("Table reddit_status_log already exists, skipping creation")
            else:
                logger.info("Creating reddit_status_log table...")

                # Create the table
                conn.execute(
                    text(
                        """
                    CREATE TABLE reddit_status_log (
                        id SERIAL PRIMARY KEY,
                        link_id INTEGER NOT NULL REFERENCES project_links(id),
                        
                        -- Status information
                        status_type VARCHAR(50) NOT NULL,
                        status_message TEXT,
                        
                        -- Community details
                        posts_found INTEGER DEFAULT 0,
                        subscriber_count INTEGER,
                        last_post_date TIMESTAMP WITH TIME ZONE,
                        
                        -- Error details
                        error_type VARCHAR(100),
                        error_details TEXT,
                        
                        -- Timestamps
                        checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """
                    )
                )

                # Create indexes
                logger.info("Creating indexes for reddit_status_log...")
                conn.execute(
                    text(
                        "CREATE INDEX idx_reddit_status_log_link_id ON reddit_status_log(link_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX idx_reddit_status_log_type ON reddit_status_log(status_type)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX idx_reddit_status_log_checked_at ON reddit_status_log(checked_at)"
                    )
                )

                logger.success("reddit_status_log table created successfully!")

            # Commit the transaction
            trans.commit()
            logger.success("Reddit status log table migration completed successfully!")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"Reddit status log table migration failed: {e}")
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
        f"Running Reddit status log table migration on database: {database_url.split('@')[1] if '@' in database_url else 'local database'}"
    )

    # Check database type
    if not database_url.startswith("postgresql"):
        logger.error("This migration script is designed for PostgreSQL databases only")
        return 1

    # Show what will be changed
    print("This migration will create the reddit_status_log table with columns:")
    print("  • id (SERIAL PRIMARY KEY)")
    print("  • link_id (INTEGER, FK to project_links.id)")
    print("  • status_type (VARCHAR(50), NOT NULL)")
    print("  • status_message (TEXT)")
    print("  • posts_found (INTEGER, DEFAULT 0)")
    print("  • subscriber_count (INTEGER)")
    print("  • last_post_date (TIMESTAMP WITH TIME ZONE)")
    print("  • error_type (VARCHAR(100))")
    print("  • error_details (TEXT)")
    print("  • checked_at (TIMESTAMP WITH TIME ZONE, DEFAULT NOW())")
    print("\nIndexes:")
    print("  • idx_reddit_status_log_link_id")
    print("  • idx_reddit_status_log_type")
    print("  • idx_reddit_status_log_checked_at")
    print()

    try:
        # Run the migration
        run_migration(database_url)

        logger.info("\nReddit status log table migration completed successfully!")
        logger.info(
            "The reddit_status_log table is now available for detailed Reddit community status tracking"
        )

        return 0

    except Exception as e:
        logger.error(f"Reddit status log table migration failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
