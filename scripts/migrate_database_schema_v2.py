#!/usr/bin/env python3
"""
Database migration script v2 to update numeric columns for very large cryptocurrency values.

This script updates NUMERIC(30,8) to NUMERIC(40,8) to handle extreme supply values
like 957 septillion tokens that some cryptocurrencies have.
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
    """Run the database schema migration to increase numeric precision."""
    
    logger.info("Starting database migration v2 for larger numeric values...")
    
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()
        
        try:
            # Update numeric columns from NUMERIC(30,8) to NUMERIC(40,8) for very large values
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
                logger.info(f"Converting {column} to NUMERIC(40,8) for larger value support...")
                conn.execute(text(f"ALTER TABLE crypto_projects ALTER COLUMN {column} TYPE NUMERIC(40,8)"))
            
            # Commit the transaction
            trans.commit()
            logger.success("Migration v2 completed successfully!")
            
        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"Migration v2 failed: {e}")
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
    
    logger.info(f"Running migration v2 on database: {database_url.split('@')[1] if '@' in database_url else 'local database'}")
    
    # Check database type
    if not database_url.startswith('postgresql'):
        logger.error("This migration script is designed for PostgreSQL databases only")
        return 1
    
    # Get user confirmation
    print("This migration will update numeric columns from NUMERIC(30,8) to NUMERIC(40,8)")
    print("This is needed to handle very large cryptocurrency supply values (up to 10^32)")
    print("Examples of values that will now be supported:")
    print("  • 957,673,694,542,363,517,057,792,737,280 (30 digits)")
    print("  • 420,000,000,000,000,025,165,824 (24 digits)")
    print()
    response = input("Are you sure you want to run this migration? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Migration cancelled by user")
        return 0
    
    try:
        # Run the migration
        run_migration(database_url)
        
        logger.info("\nMigration v2 completed successfully!")
        logger.info("The following changes were made:")
        logger.info("  • All numeric columns converted to NUMERIC(40,8)")
        logger.info("  • Can now handle values up to ±10^32 (40 digits total, 8 decimal places)")
        logger.info("  • Cryptocurrency supplies in the septillions are now supported")
        logger.info("  • No more 'exceeds database limits' warnings for large supplies")
        
        return 0
        
    except Exception as e:
        logger.error(f"Migration v2 failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())