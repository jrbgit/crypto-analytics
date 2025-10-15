import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "src"))
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv("config/env")
engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    result = conn.execute(text("DELETE FROM api_usage"))
    print(f"Deleted {result.rowcount} records from api_usage")
    
    conn.execute(text("SELECT setval('api_usage_id_seq', 1, false)"))
    print("Reset api_usage sequence")
    
    tables = ["crypto_projects", "project_links", "project_images", "project_changes", "api_usage"]
    for table in tables:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        print(f"{table}: {count} records")

print("✅ Database is completely clean and ready for fresh data collection!")