import sqlite3

conn = sqlite3.connect('data/crypto_analytics.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
tables = cursor.fetchall()

print('Database tables:')
for table in tables:
    print(f'  {table[0]}')

cursor.execute('SELECT COUNT(*) FROM project_links WHERE link_type = "reddit"')
reddit_total = cursor.fetchone()[0]

cursor.execute('SELECT scrape_success, COUNT(*) FROM project_links WHERE link_type = "reddit" GROUP BY scrape_success')
statuses = cursor.fetchall()

print(f'\nReddit links: {reddit_total} total')
print('Status breakdown:')
for status, count in statuses:
    if status is None:
        print(f'  pending: {count}')
    elif status:
        print(f'  successful: {count}')
    else:
        print(f'  failed: {count}')

conn.close()