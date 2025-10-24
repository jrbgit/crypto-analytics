#!/usr/bin/env python3
"""
Database migration script v3 to increase decimal precision for cryptocurrency price fields.

This script updates price-related columns from NUMERIC(40,8) to NUMERIC(40,20) to handle
very small cryptocurrency prices (down to 1e-20) without precision loss.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from loguru import logger

# Add the src directory to path so we can import our models
sys.path.append(str(Path(__file__).parent.parent / "src"))

from models.database import DatabaseManager
from dotenv import load_dotenv


def run_migration(database_url: str):
    """Run the database schema migration to increase decimal precision for price fields."""

    logger.info("Starting database migration v3 for higher price precision...")

    engine = create_engine(database_url)

    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()

        try:
            # Update price-related columns to NUMERIC(40,20) for very small value precision
            price_columns = [
                "current_price",  # Can be extremely small (1e-16 or smaller)
                "ath_usd",  # All-time high can also be very small for some tokens
            ]

            for column in price_columns:
                logger.info(
                    f"Converting {column} to NUMERIC(50,20) for higher precision..."
                )
                conn.execute(
                    text(
                        f"ALTER TABLE crypto_projects ALTER COLUMN {column} TYPE NUMERIC(50,20)"
                    )
                )

            # Commit the transaction
            trans.commit()
            logger.success("Migration v3 completed successfully!")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"Migration v3 failed: {e}")
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
        f"Running migration v3 on database: {database_url.split('@')[1] if '@' in database_url else 'local database'}"
    )

    # Check database type
    if not database_url.startswith("postgresql"):
        logger.error("This migration script is designed for PostgreSQL databases only")
        return 1

    # Show what will be changed
    print("This migration will increase decimal precision for price fields:")
    print("  • current_price: NUMERIC(40,8) → NUMERIC(50,20)")
    print("  • ath_usd: NUMERIC(40,8) → NUMERIC(50,20)")
    print()
    print("Benefits:")
    print("  • Handles cryptocurrency prices down to 1e-20 (vs 1e-8 previously)")
    print("  • Supports large ATH values up to 1e+30 (vs 1e+20 with NUMERIC(40,20))")
    print("  • No more precision loss for micro-cap tokens")
    print("  • Values like 4.30383e-14 will be stored accurately")
    print("  • Large values like 1.857e+22 (current max ATH) will fit comfortably")
    print("  • All existing data will be preserved")
    print()

    response = input("Are you sure you want to run this migration? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Migration cancelled by user")
        return 0

    try:
        # Run the migration
        run_migration(database_url)

        logger.info("\nMigration v3 completed successfully!")
        logger.info("The following changes were made:")
        logger.info(
            "  • current_price column now supports 20 decimal places (NUMERIC(50,20))"
        )
        logger.info(
            "  • ath_usd column now supports 20 decimal places (NUMERIC(50,20))"
        )
        logger.info(
            "  • Can accurately store prices down to 0.00000000000000000001 (1e-20)"
        )
        logger.info("  • Can handle large values up to 1e+30")
        logger.info("  • No more precision loss for very small cryptocurrency prices")

        return 0

    except Exception as e:
        logger.error(f"Migration v3 failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
