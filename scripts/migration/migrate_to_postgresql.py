#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to PostgreSQL
with integrity checks and progress reporting.
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
from dataclasses import dataclass

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


@dataclass
class MigrationStats:
    """Track migration statistics"""
    table_name: str
    total_records: int
    migrated_records: int = 0
    failed_records: int = 0
    start_time: datetime = None
    end_time: datetime = None
    
    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_records == 0:
            return 100.0
        return (self.migrated_records / self.total_records) * 100


class DataMigrator:
    """Handles SQLite to PostgreSQL data migration with integrity checks"""
    
    def __init__(self, 
                 sqlite_path: str = "data/crypto_analytics.db",
                 postgres_config: Dict[str, str] = None):
        self.sqlite_path = sqlite_path
        self.postgres_config = postgres_config or {
            'host': 'localhost',
            'port': '5432',
            'database': 'crypto_analytics',
            'user': 'crypto_user',
            'password': os.getenv('DB_PASSWORD', 'crypto_secure_password_2024')
        }
        
        self.migration_stats: Dict[str, MigrationStats] = {}
        self.batch_size = 1000
        
        # Table migration order (respects foreign key constraints)
        self.migration_order = [
            'crypto_projects',
            'project_images', 
            'project_links',
            'link_raw_content',  # New table for raw content
            'link_content_analysis',
            'project_changes',
            'project_analysis',
            'api_usage',
            'social_sentiment_history',  # New table
            'project_competitors'  # New table
        ]
        
        # Field mappings for data transformation
        self.field_mappings = {
            'link_content_analysis': {
                'raw_content': 'link_raw_content_table',  # Move to separate table
                'categories': 'categories::jsonb',  # Ensure proper JSONB casting
                'technology_stack': 'technology_stack::jsonb',
                'core_features': 'core_features::jsonb',
                'use_cases': 'use_cases::jsonb',
                'target_audience': 'target_audience::jsonb'
            }
        }

    def connect_sqlite(self) -> sqlite3.Connection:
        """Connect to SQLite database"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            logger.info(f"Connected to SQLite: {self.sqlite_path}")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            raise

    def connect_postgres(self) -> psycopg2.extensions.connection:
        """Connect to PostgreSQL database"""
        try:
            conn = psycopg2.connect(
                host=self.postgres_config['host'],
                port=self.postgres_config['port'],
                database=self.postgres_config['database'],
                user=self.postgres_config['user'],
                password=self.postgres_config['password']
            )
            conn.autocommit = False
            logger.info(f"Connected to PostgreSQL: {self.postgres_config['database']}")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def get_table_info(self, sqlite_conn: sqlite3.Connection) -> Dict[str, Dict]:
        """Get table structure information from SQLite"""
        cursor = sqlite_conn.cursor()
        table_info = {}
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            # Get column info
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1]: row[2] for row in cursor.fetchall()}  # name: type
            
            # Get record count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            
            table_info[table] = {
                'columns': columns,
                'record_count': count
            }
            
        return table_info

    def prepare_migration_stats(self, table_info: Dict[str, Dict]):
        """Initialize migration statistics"""
        for table_name in self.migration_order:
            if table_name in table_info:
                self.migration_stats[table_name] = MigrationStats(
                    table_name=table_name,
                    total_records=table_info[table_name]['record_count']
                )
            else:
                logger.warning(f"Table {table_name} not found in SQLite database")

    def transform_row_data(self, table_name: str, row_data: Dict) -> Tuple[Dict, Optional[Dict]]:
        """Transform SQLite row data for PostgreSQL compatibility"""
        main_data = dict(row_data)
        separate_data = None
        
        # Handle special transformations
        if table_name == 'link_content_analysis':
            # Move raw content to separate table
            if 'raw_content' in main_data and main_data['raw_content']:
                content_hash = hashlib.sha256(
                    main_data['raw_content'].encode()
                ).hexdigest()
                
                separate_data = {
                    'link_id': main_data['link_id'],
                    'content_hash': content_hash,
                    'raw_content': main_data['raw_content'],
                    'content_type': main_data.get('document_type', 'unknown'),
                    'content_size': len(main_data['raw_content'])
                }
                
                # Update main record to reference content hash
                main_data['content_hash'] = content_hash
                del main_data['raw_content']  # Remove from main table
        
        # Convert JSON fields to proper format
        json_fields = [
            'categories', 'technology_stack', 'core_features', 'use_cases',
            'target_audience', 'team_members', 'founders', 'advisors',
            'partnerships', 'investors', 'innovations', 'roadmap_items',
            'red_flags', 'key_points', 'entities', 'recent_updates',
            'competitors_mentioned', 'competitive_advantages_claimed',
            'plagiarism_indicators', 'vague_claims', 'unrealistic_promises',
            'partnerships_mentioned', 'data_sources_used', 'engagement_metrics'
        ]
        
        for field in json_fields:
            if field in main_data and main_data[field]:
                try:
                    # If it's already a string that looks like JSON, parse and re-serialize
                    if isinstance(main_data[field], str):
                        parsed = json.loads(main_data[field])
                        main_data[field] = json.dumps(parsed)
                    elif isinstance(main_data[field], (list, dict)):
                        main_data[field] = json.dumps(main_data[field])
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Invalid JSON in {table_name}.{field}: {main_data[field]}")
                    main_data[field] = None
        
        # Handle datetime fields
        datetime_fields = [
            'created_at', 'updated_at', 'last_api_fetch', 'last_scraped',
            'request_timestamp', 'measured_at'
        ]
        
        for field in datetime_fields:
            if field in main_data and main_data[field]:
                if isinstance(main_data[field], str):
                    try:
                        # Try to parse various datetime formats
                        dt = datetime.fromisoformat(main_data[field].replace('Z', '+00:00'))
                        main_data[field] = dt
                    except ValueError:
                        logger.warning(f"Invalid datetime format: {main_data[field]}")
                        main_data[field] = None
        
        return main_data, separate_data

    def should_skip_record(self, table_name: str, data: Dict) -> bool:
        """Determine if a record should be skipped (spam/test entries)"""
        if table_name == 'crypto_projects':
            code = data.get('code', '')
            name = data.get('name', '')
            
            # Skip obvious spam/test entries
            if code and ('_' * 10 in code or len(code) > 50):
                return True
                
            if name and len(name) > 200:
                return True
                
            # Skip entries with extreme numeric values that cause overflow
            numeric_fields = ['circulating_supply', 'total_supply', 'max_supply', 
                            'current_price', 'market_cap', 'volume_24h']
            
            for field in numeric_fields:
                if field in data and data[field] is not None:
                    try:
                        value = float(data[field])
                        if value > 1e20:  # Extremely large number
                            return True
                    except (ValueError, TypeError):
                        pass
        
        return False
    
    def clean_data_for_postgres(self, table_name: str, data: Dict) -> Dict:
        """Clean and validate data for PostgreSQL constraints"""
        cleaned_data = data.copy()
        
        # Handle crypto_projects specific constraints
        if table_name == 'crypto_projects':
            # Clean color field
            if 'color' in cleaned_data and cleaned_data['color']:
                if len(cleaned_data['color']) > 15:
                    cleaned_data['color'] = cleaned_data['color'][:15]
        
        return cleaned_data
    
    def create_insert_query(self, table_name: str, data: Dict) -> Tuple[str, List]:
        """Create INSERT query with proper parameter placeholders"""
        # Clean the data first
        cleaned_data = self.clean_data_for_postgres(table_name, data)
        
        columns = list(cleaned_data.keys())
        placeholders = ['%s'] * len(columns)
        values = [cleaned_data[col] for col in columns]
        
        query = f"""
        INSERT INTO {table_name} ({', '.join(columns)})
        VALUES ({', '.join(placeholders)})
        ON CONFLICT DO NOTHING
        """
        
        return query, values

    def migrate_table(self, table_name: str, 
                     sqlite_conn: sqlite3.Connection,
                     postgres_conn: psycopg2.extensions.connection) -> bool:
        """Migrate a single table with batch processing and error handling"""
        
        if table_name not in self.migration_stats:
            logger.warning(f"No migration stats for table {table_name}")
            return False
            
        stats = self.migration_stats[table_name]
        stats.start_time = datetime.now()
        
        try:
            sqlite_cursor = sqlite_conn.cursor()
            postgres_cursor = postgres_conn.cursor()
            
            logger.info(f"Starting migration of {table_name} ({stats.total_records} records)")
            
            # Fetch data in batches
            offset = 0
            while offset < stats.total_records:
                # Fetch batch from SQLite
                query = f"SELECT * FROM {table_name} LIMIT {self.batch_size} OFFSET {offset}"
                sqlite_cursor.execute(query)
                rows = sqlite_cursor.fetchall()
                
                if not rows:
                    break
                
                batch_success = 0
                batch_failed = 0
                
                skipped_count = 0
                for row in rows:
                    try:
                        row_dict = dict(row)
                        
                        # Skip spam/test entries
                        if self.should_skip_record(table_name, row_dict):
                            skipped_count += 1
                            continue
                        
                        # Transform data
                        main_data, separate_data = self.transform_row_data(table_name, row_dict)
                        
                        # Insert separate data first (if any)
                        if separate_data:
                            separate_query, separate_values = self.create_insert_query(
                                'link_raw_content', separate_data
                            )
                            postgres_cursor.execute(separate_query, separate_values)
                        
                        # Insert main data
                        main_query, main_values = self.create_insert_query(table_name, main_data)
                        postgres_cursor.execute(main_query, main_values)
                        
                        batch_success += 1
                        
                    except Exception as e:
                        batch_failed += 1
                        
                        # For crypto_projects table, show more specific error info
                        if table_name == 'crypto_projects' and batch_failed <= 5:
                            code = dict(row).get('code', 'UNKNOWN')
                            name = dict(row).get('name', 'UNKNOWN')
                            logger.debug(f"Skipped project {code[:20]}...: {str(e)[:50]}...")
                        elif batch_failed <= 5:
                            logger.debug(f"Failed to migrate record from {table_name}: {e}")
                        
                        # Continue with next record
                        postgres_conn.rollback()  # Rollback failed transaction
                        continue
                
                if skipped_count > 0:
                    logger.info(f"Skipped {skipped_count} spam/test entries in batch")
                
                # Commit batch
                postgres_conn.commit()
                
                stats.migrated_records += batch_success
                stats.failed_records += batch_failed
                offset += self.batch_size
                
                # Progress reporting
                progress = (offset / stats.total_records) * 100
                logger.info(f"{table_name}: {progress:.1f}% complete "
                          f"({stats.migrated_records} migrated, {stats.failed_records} failed)")
            
            stats.end_time = datetime.now()
            
            logger.success(f"Migration of {table_name} completed: "
                         f"{stats.migrated_records}/{stats.total_records} records "
                         f"({stats.success_rate:.1f}%) in {stats.duration:.1f}s")
            
            return stats.success_rate > 90  # Consider successful if > 90% migrated
            
        except Exception as e:
            stats.end_time = datetime.now()
            logger.error(f"Migration of {table_name} failed: {e}")
            postgres_conn.rollback()
            return False

    def verify_migration(self, postgres_conn: psycopg2.extensions.connection) -> Dict[str, int]:
        """Verify migration by counting records in PostgreSQL"""
        cursor = postgres_conn.cursor()
        verification_results = {}
        
        for table_name in self.migration_stats.keys():
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                verification_results[table_name] = count
                
                expected = self.migration_stats[table_name].migrated_records
                if count == expected:
                    logger.success(f"✓ {table_name}: {count} records (verified)")
                else:
                    logger.warning(f"⚠ {table_name}: {count} records (expected {expected})")
                    
            except Exception as e:
                logger.error(f"Verification failed for {table_name}: {e}")
                verification_results[table_name] = -1
        
        return verification_results

    def create_materialized_views(self, postgres_conn: psycopg2.extensions.connection):
        """Create materialized views for improved query performance"""
        cursor = postgres_conn.cursor()
        
        views = [
            # Project summary view
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS project_summary AS
            SELECT 
                p.id,
                p.code,
                p.name,
                p.rank,
                p.current_price,
                p.market_cap,
                p.volume_24h,
                p.price_change_24h,
                COUNT(pl.id) as total_links,
                COUNT(lca.id) as analyzed_links,
                AVG(lca.technical_depth_score) as avg_tech_score,
                AVG(lca.content_quality_score) as avg_quality_score,
                MAX(lca.updated_at) as last_analysis
            FROM crypto_projects p
            LEFT JOIN project_links pl ON p.id = pl.project_id
            LEFT JOIN link_content_analysis lca ON pl.id = lca.link_id
            WHERE pl.is_active = true
            GROUP BY p.id, p.code, p.name, p.rank, p.current_price, p.market_cap, p.volume_24h, p.price_change_24h;
            """,
            
            # Analysis summary by link type
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS analysis_by_link_type AS
            SELECT 
                pl.link_type,
                COUNT(*) as total_analyses,
                AVG(lca.technical_depth_score) as avg_tech_score,
                AVG(lca.content_quality_score) as avg_quality_score,
                AVG(lca.confidence_score) as avg_confidence,
                COUNT(*) FILTER (WHERE lca.has_tokenomics = true) as with_tokenomics,
                COUNT(*) FILTER (WHERE lca.team_described = true) as with_team_info
            FROM project_links pl
            JOIN link_content_analysis lca ON pl.id = lca.link_id
            GROUP BY pl.link_type;
            """
        ]
        
        for view_sql in views:
            try:
                cursor.execute(view_sql)
                postgres_conn.commit()
                logger.info("Created materialized view")
            except Exception as e:
                logger.warning(f"Failed to create materialized view: {e}")
                postgres_conn.rollback()

    def run_migration(self) -> bool:
        """Execute the complete migration process"""
        logger.info("Starting SQLite to PostgreSQL migration")
        
        # Connect to databases
        sqlite_conn = self.connect_sqlite()
        postgres_conn = self.connect_postgres()
        
        try:
            # Get table information
            logger.info("Analyzing SQLite database structure...")
            table_info = self.get_table_info(sqlite_conn)
            self.prepare_migration_stats(table_info)
            
            # Display migration plan
            logger.info("Migration Plan:")
            total_records = sum(stats.total_records for stats in self.migration_stats.values())
            logger.info(f"Total records to migrate: {total_records:,}")
            
            for table_name in self.migration_order:
                if table_name in self.migration_stats:
                    stats = self.migration_stats[table_name]
                    logger.info(f"  {table_name}: {stats.total_records:,} records")
            
            # Confirm migration
            response = input("\nProceed with migration? (y/N): ").strip().lower()
            if response != 'y':
                logger.info("Migration cancelled")
                return False
            
            # Execute migration
            migration_start = datetime.now()
            successful_tables = 0
            
            for table_name in self.migration_order:
                if table_name in self.migration_stats:
                    success = self.migrate_table(table_name, sqlite_conn, postgres_conn)
                    if success:
                        successful_tables += 1
                    else:
                        logger.error(f"Migration failed for {table_name}")
            
            migration_end = datetime.now()
            total_duration = (migration_end - migration_start).total_seconds()
            
            # Verify migration
            logger.info("Verifying migration results...")
            verification_results = self.verify_migration(postgres_conn)
            
            # Create performance views
            logger.info("Creating materialized views...")
            self.create_materialized_views(postgres_conn)
            
            # Final summary
            logger.info("=" * 60)
            logger.info("MIGRATION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total migration time: {total_duration:.1f} seconds")
            logger.info(f"Successful tables: {successful_tables}/{len(self.migration_stats)}")
            
            total_migrated = sum(stats.migrated_records for stats in self.migration_stats.values())
            total_failed = sum(stats.failed_records for stats in self.migration_stats.values())
            overall_success_rate = (total_migrated / (total_migrated + total_failed)) * 100 if (total_migrated + total_failed) > 0 else 0
            
            logger.info(f"Total records migrated: {total_migrated:,}")
            logger.info(f"Total records failed: {total_failed:,}")
            logger.info(f"Overall success rate: {overall_success_rate:.1f}%")
            
            if overall_success_rate > 95:
                logger.success("🎉 Migration completed successfully!")
                logger.info("\nNext steps:")
                logger.info("1. Update your application configuration to use PostgreSQL")
                logger.info("2. Update DATABASE_URL in your environment")
                logger.info("3. Test your application with the new database")
                logger.info("4. Consider running ANALYZE on tables for optimal performance")
                return True
            else:
                logger.warning("⚠️ Migration completed with some issues")
                logger.info("Review the logs above for details on failed records")
                return False
        
        finally:
            sqlite_conn.close()
            postgres_conn.close()


def main():
    """Main migration execution"""
    
    # Check if PostgreSQL is running
    try:
        import psycopg2
        test_conn = psycopg2.connect(
            host='localhost',
            port='5432',
            database='postgres',
            user='crypto_user',
            password=os.getenv('DB_PASSWORD', 'crypto_secure_password_2024')
        )
        test_conn.close()
        logger.success("PostgreSQL connection test passed")
    except Exception as e:
        logger.error(f"Cannot connect to PostgreSQL: {e}")
        logger.info("Please ensure PostgreSQL is running (docker-compose up postgres)")
        return False
    
    # Run migration
    migrator = DataMigrator()
    success = migrator.run_migration()
    
    if success:
        logger.info("\n🚀 Ready to update your application!")
        logger.info("Set DATABASE_URL='postgresql://crypto_user:${DB_PASSWORD}@localhost:5432/crypto_analytics'")
    
    return success


if __name__ == "__main__":
    main()