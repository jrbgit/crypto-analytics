#!/usr/bin/env python3
"""
Analyze the potential impact of URL filtering on our current database.
Shows how many URLs would be filtered and categorizes the reasons.
"""

import sys
from pathlib import Path
import sqlite3
from collections import Counter, defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths, get_data_path

# Set up project paths
project_root = setup_project_paths()

from src.utils.url_filter import url_filter

def analyze_database_urls():
    """Analyze URLs in the database to see filtering impact."""
    
    print("🔍 Analyzing Database URLs for Filtering Impact")
    print("=" * 60)
    
    # Connect to database
    db_path = get_data_path() / 'crypto_analytics.db'
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get all project links
    query = """
    SELECT 
        pl.id,
        pl.url,
        pl.link_type,
        pl.scrape_success,
        pl.last_scraped
    FROM project_links pl
    WHERE pl.url IS NOT NULL AND pl.url != ''
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    print(f"📊 Found {len(rows)} URLs in database")
    print()
    
    # Analyze each URL
    results = {
        'total': len(rows),
        'filtered': [],
        'allowed': [],
        'by_type': defaultdict(lambda: {'total': 0, 'filtered': 0}),
        'filter_reasons': Counter(),
        'by_status': defaultdict(lambda: {'total': 0, 'filtered': 0})
    }
    
    for row in rows:
        url_id, url, link_type, scrape_success, last_scraped = row
        
        # Count by type
        results['by_type'][link_type]['total'] += 1
        
        # Count by current status
        status = 'completed' if scrape_success else 'pending' if not last_scraped else 'failed'
        results['by_status'][status]['total'] += 1
        
        # Test filtering
        should_skip, skip_reason = url_filter.should_skip_url(url)
        
        if should_skip:
            results['filtered'].append((url, skip_reason, link_type))
            results['by_type'][link_type]['filtered'] += 1
            results['by_status'][status]['filtered'] += 1
            results['filter_reasons'][skip_reason] += 1
        else:
            results['allowed'].append((url, link_type))
    
    # Report results
    print(f"📈 FILTERING IMPACT SUMMARY")
    print(f"   Total URLs: {results['total']:,}")
    print(f"   Would be filtered: {len(results['filtered']):,} ({len(results['filtered'])/results['total']*100:.1f}%)")
    print(f"   Would be processed: {len(results['allowed']):,} ({len(results['allowed'])/results['total']*100:.1f}%)")
    print()
    
    print("📋 BY CONTENT TYPE:")
    for content_type, stats in sorted(results['by_type'].items()):
        if stats['total'] > 0:
            pct = stats['filtered'] / stats['total'] * 100
            print(f"   {content_type}: {stats['filtered']:,}/{stats['total']:,} filtered ({pct:.1f}%)")
    print()
    
    print("📊 BY CURRENT STATUS:")
    for status, stats in sorted(results['by_status'].items()):
        if stats['total'] > 0:
            pct = stats['filtered'] / stats['total'] * 100
            print(f"   {status}: {stats['filtered']:,}/{stats['total']:,} would be filtered ({pct:.1f}%)")
    print()
    
    print("🚫 TOP FILTERING REASONS:")
    for reason, count in results['filter_reasons'].most_common(10):
        pct = count / len(results['filtered']) * 100
        print(f"   {reason}: {count:,} URLs ({pct:.1f}%)")
    print()
    
    # Show some examples of filtered URLs
    print("🔍 EXAMPLE FILTERED URLs:")
    for i, (url, reason, content_type) in enumerate(results['filtered'][:10]):
        print(f"   {i+1}. [{content_type}] {url[:60]}...")
        print(f"      Reason: {reason}")
    
    if len(results['filtered']) > 10:
        print(f"   ... and {len(results['filtered']) - 10:,} more")
    
    print()
    
    # Calculate savings
    print("💰 ESTIMATED SAVINGS:")
    filtered_count = len(results['filtered'])
    
    # Rough estimates based on observed processing times
    time_per_url = {
        'website': 45,  # seconds per website
        'whitepaper': 30,  # seconds per whitepaper  
        'reddit': 20,    # seconds per reddit
        'medium': 25     # seconds per medium
    }
    
    total_time_saved = 0
    for url, reason, content_type in results['filtered']:
        total_time_saved += time_per_url.get(content_type, 30)
    
    hours_saved = total_time_saved / 3600
    days_saved = hours_saved / 24
    
    print(f"   Processing time saved: {hours_saved:.1f} hours ({days_saved:.1f} days)")
    print(f"   Network requests avoided: {filtered_count:,}")
    print(f"   Storage space saved: ~{filtered_count * 2:.0f} MB (estimated)")
    
    conn.close()
    
    return results

def show_problematic_patterns():
    """Show patterns of problematic URLs we're now filtering."""
    
    print("\n🎯 COMMON PROBLEMATIC PATTERNS NOW FILTERED:")
    print("=" * 60)
    
    patterns = [
        ("CDN/Protection URLs", "cdn-cgi/l/email-protection", "Cloudflare email protection links"),
        ("Binary Downloads", "*.exe, *.dmg, *.zip", "Executable files and archives"),
        ("Domain Parking", "domains.atom.com", "Domain-for-sale redirect services"),
        ("Admin/API URLs", "/wp-admin/, /api/", "Backend and administration URLs"),
        ("Asset URLs", "/assets/, /css/, /js/", "Static resource files"),
        ("Development URLs", "/test/, /debug/", "Development and testing endpoints"),
        ("Social Media", "facebook.com, twitter.com", "Social media profile links"),
        ("Tracking URLs", "utm_*, fbclid", "URLs with tracking parameters"),
    ]
    
    for category, example, description in patterns:
        print(f"✅ {category}")
        print(f"   Example: {example}")
        print(f"   Impact: {description}")
        print()

if __name__ == "__main__":
    results = analyze_database_urls()
    show_problematic_patterns()
    
    print("🎉 URL Filtering Analysis Complete!")
    print()
    print("💡 Next Steps:")
    print("   1. Deploy the URL filtering updates")
    print("   2. Monitor filtering effectiveness in production")
    print("   3. Adjust filters based on any false positives")
    print("   4. Track performance improvements")