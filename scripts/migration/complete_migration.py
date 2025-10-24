#!/usr/bin/env python3
"""Complete the migration by migrating links and analysis with proper ID mapping"""

import os
import sqlite3
import psycopg2
from dotenv import load_dotenv
from loguru import logger
import json

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


def create_id_mapping():
    """Create mapping between SQLite and PostgreSQL project IDs based on unique codes"""
    sqlite_conn = connect_sqlite()
    postgres_conn = connect_postgres()

    try:
        sqlite_cursor = sqlite_conn.cursor()
        postgres_cursor = postgres_conn.cursor()

        # Get all project codes and their IDs from both databases
        sqlite_cursor.execute(
            "SELECT id, code FROM crypto_projects WHERE code IS NOT NULL"
        )
        sqlite_projects = {row["code"]: row["id"] for row in sqlite_cursor.fetchall()}

        postgres_cursor.execute(
            "SELECT id, code FROM crypto_projects WHERE code IS NOT NULL"
        )
        postgres_projects = {row[1]: row[0] for row in postgres_cursor.fetchall()}

        # Create mapping: sqlite_id -> postgres_id
        id_mapping = {}
        for code in sqlite_projects:
            if code in postgres_projects:
                sqlite_id = sqlite_projects[code]
                postgres_id = postgres_projects[code]
                id_mapping[sqlite_id] = postgres_id

        logger.info(f"Created ID mapping for {len(id_mapping)} projects")
        return id_mapping

    finally:
        sqlite_conn.close()
        postgres_conn.close()


def migrate_links_with_mapping(id_mapping):
    """Migrate project links using the ID mapping"""
    sqlite_conn = connect_sqlite()
    postgres_conn = connect_postgres()

    try:
        sqlite_cursor = sqlite_conn.cursor()
        postgres_cursor = postgres_conn.cursor()

        # Get links for mapped projects only
        mapped_sqlite_ids = list(id_mapping.keys())
        placeholders = ",".join(["?" for _ in mapped_sqlite_ids])

        query = f"SELECT * FROM project_links WHERE project_id IN ({placeholders})"
        sqlite_cursor.execute(query, mapped_sqlite_ids)

        migrated = 0
        batch = []
        batch_size = 1000

        for row in sqlite_cursor:
            row_dict = dict(row)

            # Map the project_id
            old_project_id = row_dict["project_id"]
            if old_project_id in id_mapping:
                row_dict["project_id"] = id_mapping[old_project_id]
                batch.append(row_dict)

                if len(batch) >= batch_size:
                    migrated += insert_links_batch(postgres_cursor, batch)
                    postgres_conn.commit()
                    batch = []

                    if migrated % 10000 == 0:
                        logger.info(f"Migrated {migrated} links...")

        # Handle remaining batch
        if batch:
            migrated += insert_links_batch(postgres_cursor, batch)
            postgres_conn.commit()

        logger.success(f"Migrated {migrated} project links")

    finally:
        sqlite_conn.close()
        postgres_conn.close()


def insert_links_batch(postgres_cursor, batch):
    """Insert a batch of links"""
    success_count = 0

    for link in batch:
        try:
            columns = list(link.keys())
            placeholders = ["%s"] * len(columns)
            values = list(link.values())

            query = f"""
                INSERT INTO project_links ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT DO NOTHING
            """

            postgres_cursor.execute(query, values)
            success_count += 1

        except Exception:
            continue

    return success_count


def migrate_analysis_data():
    """Migrate link content analysis data"""
    sqlite_conn = connect_sqlite()
    postgres_conn = connect_postgres()

    try:
        sqlite_cursor = sqlite_conn.cursor()
        postgres_cursor = postgres_conn.cursor()

        # Get analysis data for existing links only
        query = """
            SELECT lca.* FROM link_content_analysis lca
            INNER JOIN project_links pl ON lca.link_id = pl.id
            WHERE pl.id IN (SELECT id FROM project_links)
        """

        # First, get link ID mapping
        postgres_cursor.execute("SELECT id FROM project_links ORDER BY id")
        postgres_link_ids = set(row[0] for row in postgres_cursor.fetchall())

        sqlite_cursor.execute("SELECT * FROM link_content_analysis")

        migrated = 0
        batch = []
        batch_size = 100

        for row in sqlite_cursor:
            row_dict = dict(row)

            # Only migrate if the link_id exists in PostgreSQL
            if row_dict["link_id"] in postgres_link_ids:
                # Clean JSON fields
                json_fields = [
                    "technology_stack",
                    "core_features",
                    "use_cases",
                    "target_audience",
                    "team_members",
                    "founders",
                    "advisors",
                    "partnerships",
                    "investors",
                    "innovations",
                    "roadmap_items",
                    "red_flags",
                    "key_points",
                    "entities",
                    "categories",
                    "recent_updates",
                    "competitors_mentioned",
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
                    migrated += insert_analysis_batch(postgres_cursor, batch)
                    postgres_conn.commit()
                    batch = []

                    if migrated % 100 == 0:
                        logger.info(f"Migrated {migrated} analyses...")

        # Handle remaining batch
        if batch:
            migrated += insert_analysis_batch(postgres_cursor, batch)
            postgres_conn.commit()

        logger.success(f"Migrated {migrated} content analyses")

    finally:
        sqlite_conn.close()
        postgres_conn.close()


def insert_analysis_batch(postgres_cursor, batch):
    """Insert a batch of analyses"""
    success_count = 0

    for analysis in batch:
        try:
            columns = list(analysis.keys())
            placeholders = ["%s"] * len(columns)
            values = list(analysis.values())

            query = f"""
                INSERT INTO link_content_analysis ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT DO NOTHING
            """

            postgres_cursor.execute(query, values)
            success_count += 1

        except Exception as e:
            # Log first few errors for debugging
            if success_count < 5:
                logger.debug(f"Failed to migrate analysis: {e}")
            continue

    return success_count


def main():
    """Complete the migration"""
    logger.info(
        "Completing migration - creating ID mappings and migrating links/analysis..."
    )

    # Create ID mapping
    id_mapping = create_id_mapping()

    # Migrate links
    migrate_links_with_mapping(id_mapping)

    # Migrate analysis data
    migrate_analysis_data()

    # Final verification
    postgres_conn = connect_postgres()
    postgres_cursor = postgres_conn.cursor()

    postgres_cursor.execute("SELECT COUNT(*) FROM crypto_projects")
    projects_count = postgres_cursor.fetchone()[0]

    postgres_cursor.execute("SELECT COUNT(*) FROM project_links")
    links_count = postgres_cursor.fetchone()[0]

    postgres_cursor.execute("SELECT COUNT(*) FROM link_content_analysis")
    analysis_count = postgres_cursor.fetchone()[0]

    logger.success("🎉 Migration completed successfully!")
    logger.info(f"Final counts:")
    logger.info(f"  Projects: {projects_count:,}")
    logger.info(f"  Links: {links_count:,}")
    logger.info(f"  Analyses: {analysis_count:,}")

    postgres_conn.close()


if __name__ == "__main__":
    main()
