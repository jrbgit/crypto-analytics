#!/usr/bin/env python3
"""
Quick migration script - focuses on migrating the most important data
and skips obvious spam/test entries.
"""

import os
import sys
import sqlite3
import psycopg2
import json
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
import hashlib

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


def connect_postgres():
    return psycopg2.connect(
        host="localhost",
        port="5432",
        database="crypto_analytics",
        user="crypto_user",
        password=os.getenv("DB_PASSWORD", "crypto_secure_password_2024"),
    )


def connect_sqlite():
    conn = sqlite3.connect("data/crypto_analytics.db")
    conn.row_factory = sqlite3.Row
    return conn


def is_valid_project(row):
    """Filter out spam/test entries"""
    code = row["code"] or ""
    name = row["name"] or ""

    # Skip obvious spam
    if "_" * 10 in code or len(code) > 50:
        return False
    if len(name) > 200:
        return False

    # Skip extreme values
    try:
        if row["market_cap"] and float(row["market_cap"]) > 1e15:
            return False
        if row["current_price"] and float(row["current_price"]) > 1e10:
            return False
    except (ValueError, TypeError):
        pass

    return True


def quick_migrate():
    """Quick migration focusing on quality data"""
    sqlite_conn = connect_sqlite()
    postgres_conn = connect_postgres()

    try:
        sqlite_cursor = sqlite_conn.cursor()
        postgres_cursor = postgres_conn.cursor()

        # Get current count in postgres
        postgres_cursor.execute("SELECT COUNT(*) FROM crypto_projects")
        current_count = postgres_cursor.fetchone()[0]
        logger.info(f"Current PostgreSQL records: {current_count}")

        # Count total valid projects in SQLite
        sqlite_cursor.execute(
            """
            SELECT COUNT(*) FROM crypto_projects 
            WHERE LENGTH(code) <= 50 
            AND (name IS NULL OR LENGTH(name) <= 200)
            AND (market_cap IS NULL OR market_cap < 1e15)
        """
        )
        total_valid = sqlite_cursor.fetchone()[0]
        logger.info(f"Total valid projects to migrate: {total_valid}")

        # Migrate projects in batches
        batch_size = 1000
        migrated = 0
        skipped = 0

        sqlite_cursor.execute(
            """
            SELECT * FROM crypto_projects 
            ORDER BY market_cap DESC NULLS LAST
        """
        )

        batch = []
        for row in sqlite_cursor:
            if is_valid_project(row):
                batch.append(dict(row))

                if len(batch) >= batch_size:
                    success = migrate_batch(postgres_cursor, batch)
                    migrated += success
                    skipped += len(batch) - success
                    postgres_conn.commit()

                    logger.info(
                        f"Migrated: {migrated}, Skipped: {skipped}, Progress: {(migrated/total_valid)*100:.1f}%"
                    )
                    batch = []

        # Handle remaining batch
        if batch:
            success = migrate_batch(postgres_cursor, batch)
            migrated += success
            skipped += len(batch) - success
            postgres_conn.commit()

        logger.success(f"Migration complete! Migrated: {migrated}, Skipped: {skipped}")

        # Quick verification
        postgres_cursor.execute("SELECT COUNT(*) FROM crypto_projects")
        final_count = postgres_cursor.fetchone()[0]
        logger.info(f"Final PostgreSQL count: {final_count}")

        # Migrate other tables quickly
        migrate_other_tables(sqlite_conn, postgres_conn)

    finally:
        sqlite_conn.close()
        postgres_conn.close()


def migrate_batch(postgres_cursor, batch):
    """Migrate a batch of projects"""
    success_count = 0

    for project in batch:
        try:
            # Clean data
            for key, value in project.items():
                if isinstance(value, str) and key in ["code", "name", "color"]:
                    if key == "color" and len(value) > 15:
                        project[key] = value[:15]
                    elif key == "code" and len(value) > 50:
                        project[key] = value[:50]
                    elif key == "name" and len(value) > 200:
                        project[key] = value[:200]

            # Convert categories to JSON if needed
            if project.get("categories") and isinstance(project["categories"], str):
                try:
                    json.loads(project["categories"])  # Validate JSON
                except json.JSONDecodeError:
                    project["categories"] = None

            columns = list(project.keys())
            placeholders = ["%s"] * len(columns)
            values = list(project.values())

            query = f"""
                INSERT INTO crypto_projects ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT (code) DO NOTHING
            """

            postgres_cursor.execute(query, values)
            success_count += 1

        except Exception as e:
            # Skip problematic records silently
            continue

    return success_count


def migrate_other_tables(sqlite_conn, postgres_conn):
    """Migrate other important tables quickly"""
    logger.info("Migrating other tables...")

    tables_to_migrate = [
        (
            "project_links",
            "SELECT * FROM project_links WHERE project_id IN (SELECT id FROM crypto_projects)",
        ),
        (
            "link_content_analysis",
            "SELECT * FROM link_content_analysis WHERE link_id IN (SELECT id FROM project_links)",
        ),
        (
            "api_usage",
            "SELECT * FROM api_usage LIMIT 10000",
        ),  # Keep recent API usage only
    ]

    postgres_cursor = postgres_conn.cursor()

    for table_name, query in tables_to_migrate:
        try:
            logger.info(f"Migrating {table_name}...")

            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute(query)

            count = 0
            batch = []
            batch_size = 500

            for row in sqlite_cursor:
                row_dict = dict(row)

                # Clean JSON fields
                json_fields = [
                    "categories",
                    "technology_stack",
                    "core_features",
                    "use_cases",
                ]
                for field in json_fields:
                    if field in row_dict and row_dict[field]:
                        if isinstance(row_dict[field], str):
                            try:
                                json.loads(row_dict[field])
                            except json.JSONDecodeError:
                                row_dict[field] = None

                batch.append(row_dict)

                if len(batch) >= batch_size:
                    count += insert_batch(postgres_cursor, table_name, batch)
                    batch = []

            if batch:
                count += insert_batch(postgres_cursor, table_name, batch)

            postgres_conn.commit()
            logger.success(f"Migrated {count} records to {table_name}")

        except Exception as e:
            logger.warning(f"Failed to migrate {table_name}: {e}")
            postgres_conn.rollback()


def insert_batch(postgres_cursor, table_name, batch):
    """Insert a batch of records"""
    success_count = 0

    for record in batch:
        try:
            columns = list(record.keys())
            placeholders = ["%s"] * len(columns)
            values = list(record.values())

            query = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT DO NOTHING
            """

            postgres_cursor.execute(query, values)
            success_count += 1

        except Exception:
            # Skip problematic records
            continue

    return success_count


if __name__ == "__main__":
    quick_migrate()
