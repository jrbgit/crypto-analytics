#!/usr/bin/env python3
"""
Fix PostgreSQL sequence issues after migration.
The migration copied data but didn't properly reset the auto-increment sequences.
"""

import psycopg2
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables
config_path = Path(__file__).parent / "config" / "env"
load_dotenv(config_path, override=True)

def fix_sequences():
    """Reset all PostgreSQL sequences to their correct values."""
    
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
        
        # Get all tables with serial/auto-increment columns
        tables_with_sequences = [
            ('crypto_projects', 'id'),
            ('project_links', 'id'), 
            ('project_images', 'id'),
            ('project_changes', 'id'),
            ('api_usage', 'id')
        ]
        
        print("🔧 Fixing PostgreSQL sequences...")
        
        for table_name, id_column in tables_with_sequences:
            try:
                # Check if table exists and has data
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                
                if count > 0:
                    # Get the maximum ID value
                    cursor.execute(f"SELECT MAX({id_column}) FROM {table_name};")
                    max_id = cursor.fetchone()[0]
                    
                    if max_id is not None:
                        # Set the sequence to the next value after max_id
                        sequence_name = f"{table_name}_{id_column}_seq"
                        cursor.execute(f"SELECT setval('{sequence_name}', {max_id + 1});")
                        
                        print(f"✅ Fixed {table_name}: max_id={max_id}, sequence set to {max_id + 1}")
                    else:
                        print(f"⚠️  {table_name}: no data found")
                else:
                    print(f"⚠️  {table_name}: empty table")
                    
            except Exception as e:
                print(f"❌ Error fixing {table_name}: {e}")
                continue
        
        # Commit all changes
        conn.commit()
        
        # Verify the fixes
        print("\n🔍 Verifying sequence fixes...")
        for table_name, id_column in tables_with_sequences:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                
                if count > 0:
                    cursor.execute(f"SELECT MAX({id_column}) FROM {table_name};")
                    max_id = cursor.fetchone()[0]
                    
                    sequence_name = f"{table_name}_{id_column}_seq"
                    cursor.execute(f"SELECT last_value FROM {sequence_name};")
                    seq_value = cursor.fetchone()[0]
                    
                    if seq_value > max_id:
                        print(f"✅ {table_name}: max_id={max_id}, sequence={seq_value} ✓")
                    else:
                        print(f"❌ {table_name}: max_id={max_id}, sequence={seq_value} ✗")
                        
            except Exception as e:
                print(f"❌ Error verifying {table_name}: {e}")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Sequence fix complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    fix_sequences()