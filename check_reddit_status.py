#!/usr/bin/env python3
"""
Check the status of Reddit analyses in the database
"""

import sqlite3

def main():
    conn = sqlite3.connect('data/crypto_analytics.db')
    cursor = conn.cursor()
    
    # Total Reddit links
    cursor.execute('SELECT COUNT(*) FROM project_links WHERE link_type = ?', ('reddit',))
    total_reddit = cursor.fetchone()[0]
    print(f'Total Reddit links: {total_reddit}')
    
    # Scrape success breakdown
    cursor.execute('SELECT scrape_success, COUNT(*) FROM project_links WHERE link_type = ? GROUP BY scrape_success', ('reddit',))
    statuses = cursor.fetchall()
    print('\nScrape success breakdown:')
    for status, count in statuses:
        if status is None:
            status_name = 'pending'
        elif status == 1 or status == True:
            status_name = 'successful'
        else:
            status_name = 'failed'
        print(f'- {status_name}: {count}')
    
    # Content analyses for Reddit
    cursor.execute('''
        SELECT COUNT(*) 
        FROM content_analyses ca
        JOIN project_links pl ON ca.project_link_id = pl.id
        WHERE pl.link_type = ?
    ''', ('reddit',))
    total_analyses = cursor.fetchone()[0]
    print(f'\nTotal Reddit content analyses: {total_analyses}')
    
    # Successful analyses
    cursor.execute('''
        SELECT COUNT(*) 
        FROM content_analyses ca
        JOIN project_links pl ON ca.project_link_id = pl.id
        WHERE pl.link_type = ? AND ca.analysis_result IS NOT NULL
    ''', ('reddit',))
    successful_analyses = cursor.fetchone()[0]
    print(f'Successful Reddit analyses: {successful_analyses}')
    
    # Sample of recent failed Reddit links
    cursor.execute('''
        SELECT p.name, pl.url, pl.scrape_success, pl.last_scraped
        FROM project_links pl
        JOIN projects p ON pl.project_id = p.id
        WHERE pl.link_type = ? AND pl.scrape_success = 0
        LIMIT 5
    ''', ('reddit',))
    failed_samples = cursor.fetchall()
    
    if failed_samples:
        print('\nSample of failed Reddit scrapes:')
        for name, url, success, last_scraped in failed_samples:
            print(f'- {name}: {url}')
            print(f'  Last scraped: {last_scraped}')
    
    conn.close()

if __name__ == "__main__":
    main()