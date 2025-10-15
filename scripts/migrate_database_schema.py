#!/usr/bin/env python3
"""
Database migration script to update schema for handling long codes and large numeric values.

This script:
1. Increases the code column size from 20 to 100 characters
2. Converts Float columns to NUMERIC(30,8) for better precision and larger value support
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
    """Run the database schema migration."""
    
    logger.info("Starting database migration...")
    
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()
        
        try:
            # 1. Increase code column size
            logger.info("Updating code column size to 100 characters...")
            conn.execute(text("ALTER TABLE crypto_projects ALTER COLUMN code TYPE VARCHAR(100)"))
            
            # 2. Convert Float columns to NUMERIC(30,8) for better precision
            numeric_columns = [
                'circulating_supply',
                'total_supply', 
                'max_supply',
                'current_price',
                'market_cap',
                'volume_24h',
                'ath_usd'
            ]
            
            for column in numeric_columns:
                logger.info(f"Converting {column} to NUMERIC(30,8)...")
                conn.execute(text(f"ALTER TABLE crypto_projects ALTER COLUMN {column} TYPE NUMERIC(30,8)"))
            
            # Commit the transaction
            trans.commit()
            logger.success("Migration completed successfully!")
            
        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"Migration failed: {e}")
            raise
            
        finally:
            conn.close()


def main():
    """Main function to run the migration."""
    
    # Load environment variables
    config_path = Path(__file__).parent.parent / "config" / "env"
    load_dotenv(config_path)
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return 1
    
    logger.info(f"Running migration on database: {database_url.split('@')[1] if '@' in database_url else 'local database'}")
    
    # Check database type
    if not database_url.startswith('postgresql'):
        logger.error("This migration script is designed for PostgreSQL databases only")
        return 1
    
    # Get user confirmation
    response = input("Are you sure you want to run this migration? It will modify the database schema. (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Migration cancelled by user")
        return 0
    
    try:
        # Run the migration
        run_migration(database_url)
        
        logger.info("\nMigration completed successfully!")
        logger.info("The following changes were made:")
        logger.info("  • code column increased from VARCHAR(20) to VARCHAR(100)")
        logger.info("  • Supply columns converted to NUMERIC(30,8) for large value support")
        logger.info("  • Price columns converted to NUMERIC(30,8) for better precision")
        logger.info("  • ath_usd column converted to NUMERIC(30,8) for very large values")
        
        return 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())