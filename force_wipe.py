import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "src"))
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from models.database import DatabaseManager

load_dotenv("config/env")
database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)

print("🗑️ Force wiping database by dropping and recreating tables...")

with engine.connect() as conn:
    print("Dropping all tables in dependency order...")
    
    # Drop in reverse dependency order
    tables_to_drop = [
        'link_content_analysis',
        'project_analysis', 
        'project_changes',
        'project_images',
        'project_links',
        'api_usage',
        'crypto_projects'
    ]
    
    for table in tables_to_drop:
        try:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            print(f"✅ Dropped {table}")
        except Exception as e:
            print(f"⚠️ Could not drop {table}: {e}")
    
    conn.commit()

print("🔨 Recreating tables with new schema...")
db_manager = DatabaseManager(database_url)
db_manager.create_tables()

print("✅ Verifying clean database...")
with engine.connect() as conn:
    tables = ['crypto_projects', 'project_links', 'project_images', 'project_changes', 'api_usage']
    all_empty = True
    for table in tables:
        try:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table}: {count:,} records")
            if count > 0:
                all_empty = False
        except Exception as e:
            print(f"  {table}: Error - {e}")
            all_empty = False

if all_empty:
    print("\n🎉 Database successfully wiped and recreated!")
    print("Ready for fresh data collection with:")
    print("  python src/collectors/livecoinwatch.py --all")
else:
    print("\n❌ Some tables still have data")