#!/usr/bin/env python3

import sqlite3

conn = sqlite3.connect("data/crypto_analytics.db")
cursor = conn.cursor()

print("=== DATABASE STRUCTURE ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Available tables:", tables)
print()

# Check record counts
for table in tables[:8]:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table}: {count} records")
    except Exception as e:
        print(f"{table}: Error - {e}")

print()

# Check recent website analysis results
try:
    cursor.execute(
        """
        SELECT 
            confidence_score,
            technical_depth,
            quality_score,
            created_at
        FROM website_analyses 
        ORDER BY created_at DESC 
        LIMIT 10
    """
    )
    results = cursor.fetchall()
    if results:
        print("=== RECENT WEBSITE ANALYSES ===")
        for row in results:
            print(
                f"Confidence: {row[0]:.2f}, Tech: {row[1]}/10, Quality: {row[2]}/10, Time: {row[3]}"
            )
except Exception as e:
    print(f"Error checking website analyses: {e}")

conn.close()
