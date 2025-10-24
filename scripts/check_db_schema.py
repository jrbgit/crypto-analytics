#!/usr/bin/env python3
"""
Check database schema and tables.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from loguru import logger

# Add the src directory to path so we can import our models
sys.path.append(str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv


def main():
    """Check database schema."""

    # Load environment variables
    config_path = Path(__file__).parent.parent / "config" / ".env"
    load_dotenv(config_path)

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return

    engine = create_engine(database_url)

    with engine.connect() as conn:
        # Check existing tables
        result = conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
            )
        )
        tables = [row[0] for row in result]

        print("Existing tables:")
        for table in tables:
            print(f"  - {table}")

        print()

        # If project_links table exists, check its columns
        if "project_links" in tables:
            print("Columns in project_links table:")
            result = conn.execute(
                text(
                    """
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'project_links' 
                ORDER BY ordinal_position;
            """
                )
            )

            for row in result:
                column_name, data_type, is_nullable, column_default = row
                print(f"  - {column_name}: {data_type} (nullable: {is_nullable})")

        else:
            print("project_links table does not exist!")

        # Check if crypto_projects table exists
        if "crypto_projects" in tables:
            print("\ncrypto_projects table exists")
        else:
            print("\ncrypto_projects table does NOT exist")


if __name__ == "__main__":
    main()
