#!/usr/bin/env python3
import psycopg2

try:
    conn = psycopg2.connect(
        host='localhost',
        port='5432',
        database='crypto_analytics',
        user='crypto_user',
        password='crypto_secure_password_2024'
    )
    
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()
    print(f"✅ Success! PostgreSQL version: {version[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM crypto_projects;")
    count = cursor.fetchone()
    print(f"✅ Found {count[0]} crypto projects in database")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Connection failed: {e}")