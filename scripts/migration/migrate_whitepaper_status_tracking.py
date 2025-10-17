#!/usr/bin/env python3
"""
Database Migration: Add whitepaper status tracking

This script adds comprehensive whitepaper status tracking functionality:
1. Creates whitepaper_status_log table
2. Adds whitepaper status fields to project_links table
3. Adds missing website status fields to project_links table (if not already present)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
import psycopg2
from psycopg2 import sql

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Load environment variables
load_dotenv('.env')

def get_database_url():
    """Get database URL from environment variables."""
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'crypto_analytics')
    db_user = os.getenv('DB_USER', 'crypto_user')
    db_password = os.getenv('DB_PASSWORD', 'crypto_secure_password_2024')
    
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

def run_migration():
    """Run the whitepaper status tracking migration."""
    database_url = get_database_url()
    
    # Parse the database URL to get connection parameters
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        logger.info("Connected to database successfully")
        
        # Step 1: Create whitepaper_status_log table
        logger.info("Creating whitepaper_status_log table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whitepaper_status_log (
                id SERIAL PRIMARY KEY,
                link_id INTEGER NOT NULL REFERENCES project_links(id) ON DELETE CASCADE,
                
                -- Status information
                status_type VARCHAR(50) NOT NULL,
                status_message TEXT,
                
                -- Document details
                document_type VARCHAR(20),
                document_size_bytes INTEGER,
                pages_extracted INTEGER,
                word_count INTEGER DEFAULT 0,
                
                -- HTTP/Network details
                http_status_code INTEGER,
                response_time_ms INTEGER,
                dns_resolved BOOLEAN,
                ssl_valid BOOLEAN,
                
                -- Extraction details
                extraction_method VARCHAR(50),
                extraction_success BOOLEAN,
                content_quality_score INTEGER,
                
                -- Document analysis
                has_meaningful_content BOOLEAN,
                min_word_threshold_met BOOLEAN,
                detected_language VARCHAR(10),
                detected_format VARCHAR(50),
                
                -- Access and security
                requires_authentication BOOLEAN,
                behind_paywall BOOLEAN,
                cloudflare_protected BOOLEAN,
                javascript_required BOOLEAN,
                
                -- Error details
                error_type VARCHAR(100),
                error_details TEXT,
                
                -- Processing metadata
                file_hash VARCHAR(64),
                processed_at TIMESTAMP DEFAULT NOW(),
                
                -- Timestamps
                checked_at TIMESTAMP DEFAULT NOW()
            );
        """)
        logger.success("Created whitepaper_status_log table")
        
        # Step 2: Add website status fields to project_links (if not exist)
        logger.info("Adding website status tracking fields to project_links...")
        
        website_status_fields = [
            ("current_website_status", "VARCHAR(50) DEFAULT 'unknown'"),
            ("last_status_check", "TIMESTAMP"),
            ("consecutive_failures", "INTEGER DEFAULT 0"),
            ("first_failure_date", "TIMESTAMP"),
            ("domain_parked_detected", "BOOLEAN DEFAULT FALSE"),
            ("robots_txt_blocks_scraping", "BOOLEAN DEFAULT FALSE")
        ]
        
        for field_name, field_def in website_status_fields:
            try:
                cursor.execute(f"ALTER TABLE project_links ADD COLUMN {field_name} {field_def};")
                logger.success(f"Added website status field: {field_name}")
            except psycopg2.errors.DuplicateColumn:
                logger.debug(f"Website status field {field_name} already exists, skipping")
            except Exception as e:
                logger.warning(f"Failed to add website status field {field_name}: {e}")
        
        # Step 3: Add whitepaper status fields to project_links
        logger.info("Adding whitepaper status tracking fields to project_links...")
        
        whitepaper_status_fields = [
            ("current_whitepaper_status", "VARCHAR(50) DEFAULT 'unknown'"),
            ("last_whitepaper_check", "TIMESTAMP"),
            ("whitepaper_consecutive_failures", "INTEGER DEFAULT 0"),
            ("whitepaper_first_failure_date", "TIMESTAMP"),
            ("whitepaper_access_restricted", "BOOLEAN DEFAULT FALSE"),
            ("whitepaper_format_detected", "VARCHAR(20)"),
            ("whitepaper_last_successful_extraction", "TIMESTAMP")
        ]
        
        for field_name, field_def in whitepaper_status_fields:
            try:
                cursor.execute(f"ALTER TABLE project_links ADD COLUMN {field_name} {field_def};")
                logger.success(f"Added whitepaper status field: {field_name}")
            except psycopg2.errors.DuplicateColumn:
                logger.debug(f"Whitepaper status field {field_name} already exists, skipping")
            except Exception as e:
                logger.warning(f"Failed to add whitepaper status field {field_name}: {e}")
        
        # Step 4: Create indexes for performance
        logger.info("Creating indexes...")
        
        indexes = [
            ("idx_whitepaper_status_log_link_id", "whitepaper_status_log", "link_id"),
            ("idx_whitepaper_status_log_status_type", "whitepaper_status_log", "status_type"),
            ("idx_whitepaper_status_log_checked_at", "whitepaper_status_log", "checked_at"),
            ("idx_project_links_whitepaper_status", "project_links", "current_whitepaper_status"),
            ("idx_project_links_website_status", "project_links", "current_website_status")
        ]
        
        for index_name, table_name, column_name in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name});")
                logger.success(f"Created index: {index_name}")
            except Exception as e:
                logger.warning(f"Failed to create index {index_name}: {e}")
        
        # Step 5: Verify the migration
        logger.info("Verifying migration...")
        
        # Check whitepaper_status_log table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'whitepaper_status_log'
            );
        """)
        
        if cursor.fetchone()[0]:
            logger.success("✓ whitepaper_status_log table exists")
        else:
            logger.error("✗ whitepaper_status_log table missing")
            return False
        
        # Check project_links has new columns
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'project_links' 
            AND column_name LIKE '%whitepaper%'
            ORDER BY column_name;
        """)
        
        whitepaper_columns = [row[0] for row in cursor.fetchall()]
        expected_columns = [
            'current_whitepaper_status',
            'last_whitepaper_check', 
            'whitepaper_access_restricted',
            'whitepaper_consecutive_failures',
            'whitepaper_first_failure_date',
            'whitepaper_format_detected',
            'whitepaper_last_successful_extraction'
        ]
        
        for col in expected_columns:
            if col in whitepaper_columns:
                logger.success(f"✓ project_links.{col}")
            else:
                logger.error(f"✗ project_links.{col} missing")
                return False
        
        logger.success("Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    logger.info("Starting whitepaper status tracking migration...")
    success = run_migration()
    
    if success:
        logger.success("Migration completed successfully!")
        sys.exit(0)
    else:
        logger.error("Migration failed!")
        sys.exit(1)