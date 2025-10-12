#!/usr/bin/env python3
"""
Initialize the database for crypto analytics.
"""

import os
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from database import DatabaseManager
from loguru import logger
from sqlalchemy import text

def main():
    """Initialize the database with all tables."""
    
    # Load environment variables
    load_dotenv()
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    
    # Ensure data directory exists for SQLite
    if database_url.startswith('sqlite'):
        data_dir = Path('./data')
        data_dir.mkdir(exist_ok=True)
        logger.info(f"Created data directory: {data_dir}")
    
    # Initialize database manager
    logger.info(f"Connecting to database: {database_url}")
    db_manager = DatabaseManager(database_url)
    
    # Create all tables
    try:
        logger.info("Creating database tables...")
        db_manager.create_tables()
        logger.success("Database tables created successfully!")
        
        # Test connection
        with db_manager.get_session() as session:
            logger.info("Testing database connection...")
            # Try a simple query
            session.execute(text("SELECT 1")).fetchone()
            logger.success("Database connection test passed!")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)
    
    logger.info("Database initialization completed successfully!")

if __name__ == "__main__":
    main()