#!/usr/bin/env python3
"""
Verify that data was successfully inserted into PostgreSQL database.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths, get_config_path

# Set up project paths
project_root = setup_project_paths()

# Load environment variables
load_dotenv(get_config_path() / ".env", override=True)

def verify_postgresql_connection():
    """Verify connection to PostgreSQL and check data."""
    
    database_url = os.getenv('DATABASE_URL')
    print(f"Database URL: {database_url}")
    
    try:
        # Parse the database URL
        # Format: postgresql://username:password@host:port/database
        if not database_url.startswith('postgresql://'):
            print("ERROR: DATABASE_URL is not a PostgreSQL connection string")
            return False
            
        # Extract connection details
        url_parts = database_url.replace('postgresql://', '').split('@')
        user_pass = url_parts[0].split(':')
        host_db = url_parts[1].split('/')
        host_port = host_db[0].split(':')
        
        username = user_pass[0]
        password = user_pass[1]
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else '5432'
        database = host_db[1]
        
        print(f"Connecting to PostgreSQL:")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  Database: {database}")
        print(f"  Username: {username}")
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password
        )
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if crypto_projects table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'crypto%'
        """)
        
        tables = cursor.fetchall()
        print(f"\nFound tables: {[table['table_name'] for table in tables]}")
        
        # Check crypto_projects data
        cursor.execute("""
            SELECT code, name, rank, current_price, market_cap, last_api_fetch
            FROM crypto_projects 
            ORDER BY rank 
            LIMIT 10
        """)
        
        projects = cursor.fetchall()
        print(f"\nFound {len(projects)} crypto projects:")
        print("+" + "-"*80 + "+")
        print(f"| {'Rank':<4} | {'Code':<8} | {'Name':<20} | {'Price ($)':<12} | {'Market Cap':<15} |")
        print("+" + "-"*80 + "+")
        
        for project in projects:
            rank = project['rank'] or 'N/A'
            code = project['code'] or 'N/A'
            name = (project['name'] or 'N/A')[:20]
            price = f"${project['current_price']:,.2f}" if project['current_price'] else 'N/A'
            market_cap = f"${project['market_cap']:,.0f}" if project['market_cap'] else 'N/A'
            
            print(f"| {rank:<4} | {code:<8} | {name:<20} | {price:<12} | {market_cap:<15} |")
        
        print("+" + "-"*80 + "+")
        
        # Check API usage
        cursor.execute("""
            SELECT api_provider, COUNT(*) as call_count, 
                   MAX(request_timestamp) as last_call
            FROM api_usage 
            GROUP BY api_provider
        """)
        
        api_usage = cursor.fetchall()
        print(f"\nAPI Usage:")
        for usage in api_usage:
            print(f"  {usage['api_provider']}: {usage['call_count']} calls, last: {usage['last_call']}")
        
        # Check project changes
        cursor.execute("""
            SELECT COUNT(*) as change_count
            FROM project_changes
        """)
        
        changes = cursor.fetchone()
        print(f"\nProject changes tracked: {changes['change_count']}")
        
        cursor.close()
        conn.close()
        
        print("\n✅ PostgreSQL connection and data verification successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error connecting to PostgreSQL: {e}")
        return False

if __name__ == "__main__":
    success = verify_postgresql_connection()
    sys.exit(0 if success else 1)