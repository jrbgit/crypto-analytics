#!/usr/bin/env python3
"""
Wipe PostgreSQL database and reset for fresh data collection.
"""

import psycopg2
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables
config_path = Path(__file__).parent / "config" / "env"
load_dotenv(config_path, override=True)

def wipe_database():
    """Wipe all data from PostgreSQL database tables."""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url or not database_url.startswith('postgresql://'):
        print("❌ DATABASE_URL not set to PostgreSQL")
        return False
    
    try:
        # Parse connection details
        url_parts = database_url.replace('postgresql://', '').split('@')
        user_pass = url_parts[0].split(':')
        host_db = url_parts[1].split('/')
        host_port = host_db[0].split(':')
        
        conn = psycopg2.connect(
            host=host_port[0],
            port=host_port[1] if len(host_port) > 1 else '5432',
            database=host_db[1],
            user=user_pass[0],
            password=user_pass[1]
        )
        
        cursor = conn.cursor()
        
        print("🗑️  Wiping PostgreSQL database...")
        
        # Get current data counts
        tables = ['crypto_projects', 'project_links', 'project_images', 'project_changes', 'api_usage']
        
        print("\n📊 Current data counts:")
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count:,} records")
            except Exception as e:
                print(f"  {table}: Error - {e}")
        
        # Confirm before proceeding
        print("\n⚠️  WARNING: This will delete ALL data from the database!")
        print("This action cannot be undone.")
        
        confirm = input("\nType 'YES' to confirm wiping the database: ")
        if confirm != 'YES':
            print("❌ Operation cancelled")
            return False
        
        print("\n🧹 Deleting all data...")
        
        # Delete data in correct order (respecting foreign keys)
        delete_order = [
            'project_changes',
            'project_images', 
            'project_links',
            'api_usage',
            'crypto_projects'
        ]
        
        for table in delete_order:
            try:
                cursor.execute(f"DELETE FROM {table};")
                rows_deleted = cursor.rowcount
                print(f"✅ Deleted {rows_deleted:,} records from {table}")
            except Exception as e:
                print(f"❌ Error deleting from {table}: {e}")
        
        # Reset sequences to start from 1
        print("\n🔄 Resetting sequences...")
        sequences = [
            'crypto_projects_id_seq',
            'project_links_id_seq',
            'project_images_id_seq', 
            'project_changes_id_seq',
            'api_usage_id_seq'
        ]
        
        for seq in sequences:
            try:
                cursor.execute(f"SELECT setval('{seq}', 1, false);")
                print(f"✅ Reset {seq}")
            except Exception as e:
                print(f"❌ Error resetting {seq}: {e}")
        
        # Commit all changes
        conn.commit()
        
        # Verify cleanup
        print("\n🔍 Verifying cleanup...")
        all_clean = True
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                if count == 0:
                    print(f"✅ {table}: empty")
                else:
                    print(f"❌ {table}: still has {count} records")
                    all_clean = False
            except Exception as e:
                print(f"❌ Error checking {table}: {e}")
                all_clean = False
        
        cursor.close()
        conn.close()
        
        if all_clean:
            print("\n✅ Database successfully wiped and reset!")
            print("Ready for fresh data collection.")
            return True
        else:
            print("\n❌ Some data may not have been properly cleaned")
            return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = wipe_database()
    if success:
        print("\n🚀 Database is now ready for fresh data collection!")
        print("Run: ./run_livecoinwatch.ps1 -All")
    else:
        print("\n❌ Database wipe failed")