#!/usr/bin/env python3
"""
Apply database migrations from SQL migration files.

This script reads SQL migration files and applies them to the database
to ensure the schema is up-to-date.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from loguru import logger

# Add the src directory to path so we can import our models
sys.path.append(str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv


def get_database_connection():
    """Get database connection using environment variables."""

    # Load environment variables
    config_path = Path(__file__).parent.parent / "config" / ".env"
    load_dotenv(config_path)

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return None

    return create_engine(database_url)


def check_migration_applied(conn, migration_name):
    """Check if a migration has already been applied."""
    try:
        # Try to create the migration tracking table if it doesn't exist
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS applied_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """
            )
        )

        # Check if this migration has been applied
        result = conn.execute(
            text(
                """
            SELECT COUNT(*) FROM applied_migrations WHERE migration_name = :migration_name
        """
            ),
            {"migration_name": migration_name},
        )

        return result.fetchone()[0] > 0

    except Exception as e:
        logger.warning(f"Could not check migration status: {e}")
        return False


def mark_migration_applied(conn, migration_name):
    """Mark a migration as applied."""
    try:
        conn.execute(
            text(
                """
            INSERT INTO applied_migrations (migration_name) VALUES (:migration_name)
            ON CONFLICT (migration_name) DO NOTHING
        """
            ),
            {"migration_name": migration_name},
        )

    except Exception as e:
        logger.warning(f"Could not mark migration as applied: {e}")


def apply_migration_file(conn, migration_file):
    """Apply a single migration file."""

    migration_name = migration_file.name
    logger.info(f"Checking migration: {migration_name}")

    # Check if migration was already applied
    if check_migration_applied(conn, migration_name):
        logger.info(f"Migration {migration_name} already applied, skipping")
        return True

    logger.info(f"Applying migration: {migration_name}")

    try:
        # Read the migration file
        with open(migration_file, "r", encoding="utf-8") as f:
            migration_sql = f.read()

        # Execute the migration SQL
        conn.execute(text(migration_sql))

        # Mark as applied
        mark_migration_applied(conn, migration_name)

        logger.success(f"Successfully applied migration: {migration_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to apply migration {migration_name}: {e}")
        return False


def apply_all_migrations():
    """Apply all pending migrations."""

    # Get database engine
    engine = get_database_connection()
    if not engine:
        return False

    # Find migration files
    migrations_dir = Path(__file__).parent.parent / "migrations"
    if not migrations_dir.exists():
        logger.error(f"Migrations directory not found: {migrations_dir}")
        return False

    # Get all SQL migration files
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        logger.warning("No migration files found")
        return True

    logger.info(f"Found {len(migration_files)} migration files")

    success = True

    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()

        try:
            for migration_file in migration_files:
                if not apply_migration_file(conn, migration_file):
                    success = False
                    break

            if success:
                # Commit all migrations
                trans.commit()
                logger.success("All migrations applied successfully!")
            else:
                # Rollback on any failure
                trans.rollback()
                logger.error("Migration failed, rolling back changes")

        except Exception as e:
            trans.rollback()
            logger.error(f"Migration process failed: {e}")
            success = False

    return success


def main():
    """Main function."""

    logger.info("Starting database migration process...")

    if apply_all_migrations():
        logger.success("Database migration completed successfully!")
        return 0
    else:
        logger.error("Database migration failed!")
        return 1


if __name__ == "__main__":
    exit(main())
