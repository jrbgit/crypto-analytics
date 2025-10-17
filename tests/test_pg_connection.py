#!/usr/bin/env python3
"""
Simple PostgreSQL connection test.
"""

import psycopg2

# Test different password combinations
passwords = ['admin', 'password', 'postgres', '123456']
username = 'postgres'
host = 'localhost'
port = '5432'
database = 'crypto_analytics'

for password in passwords:
    try:
        print(f"Trying password: {password}")
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Success! PostgreSQL version: {version[0]}")
        
        cursor.close()
        conn.close()
        
        print(f"✅ Correct password is: {password}")
        break
        
    except Exception as e:
        print(f"❌ Failed with password '{password}': {e}")
        continue
else:
    print("❌ None of the tested passwords worked")