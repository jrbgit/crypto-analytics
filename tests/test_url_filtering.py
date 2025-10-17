#!/usr/bin/env python3
"""
Test script for URL filtering functionality.
Tests various problematic URL patterns that should be filtered out.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from utils.url_filter import url_filter

def test_url_filtering():
    """Test URL filtering with various problematic URLs."""
    
    print("🧪 Testing URL Filter")
    print("=" * 50)
    
    # Test cases from actual log examples
    test_urls = [
        # CDN-CGI and email protection URLs (should be filtered)
        "https://bitcore.cc/cdn-cgi/l/email-protection#563f38303916343f2235392433783535",
        "https://example.com/cdn-cgi/scripts/something.js",
        "https://cloudflare.com/something",
        
        # Binary files (should be filtered)
        "https://bitcoin.org/bitcoin-core-0.21.0-win64-setup.exe",
        "https://example.com/wallet.dmg",
        "https://project.io/whitepaper.tar.gz",
        "https://crypto.com/app.zip",
        
        # Domain parking/for sale (should be filtered) 
        "https://domains.atom.com/lpd/name/unit.xyz",
        "https://sedo.com/search/details/?domain=crypto.com",
        
        # Development/admin URLs (should be filtered)
        "https://example.com/wp-admin/admin.php",
        "https://project.io/api/v1/tokens",
        "https://crypto.com/test/debug",
        "https://blockchain.io/assets/style.css",
        
        # PDF files in normally filtered directories (should NOT be filtered - PDFs are valuable!)
        "https://www.coreum.com/assets/coreum_technical_paper.pdf",
        "https://project.io/wp-content/uploads/whitepaper.pdf",
        "https://crypto.com/static/documents/paper.pdf",
        
        # Valid URLs (should NOT be filtered)
        "https://ethereum.org",
        "https://bitcoin.org/en/",
        "https://docs.ethereum.org/whitepaper",
        "https://uniswap.org/about",
        "https://compound.finance/docs",
        "https://example.com/whitepaper.pdf",  # PDFs should always be allowed
        
        # Problematic URLs from logs (should be filtered)
        "https://www.kuma-inu.com/",  # This might be valid, but let's see
        "https://unit.xyz/",  # This redirects to domain registrar
        "https://docs.keep.network/development/README.html",  # 404 but valid structure
        "https://pirate.black/files/whitepaper/The_Pirate_Code_V1.0.pdf",  # 404 but valid structure
        "https://binaryx.pro/#/whitepaper",  # Cloudflare blocked
        
        # Edge cases
        "",  # Empty URL
        "not-a-url",  # Invalid format
        "https://",  # Incomplete URL
    ]
    
    results = {"filtered": [], "allowed": []}
    
    for url in test_urls:
        should_skip, reason = url_filter.should_skip_url(url)
        
        status = "🚫 FILTERED" if should_skip else "✅ ALLOWED"
        reason_text = f" - {reason}" if reason else ""
        
        print(f"{status}: {url}{reason_text}")
        
        if should_skip:
            results["filtered"].append((url, reason))
        else:
            results["allowed"].append(url)
    
    print("\n" + "=" * 50)
    print(f"📊 Results: {len(results['filtered'])} filtered, {len(results['allowed'])} allowed")
    
    return results

def test_content_filtering():
    """Test content-based filtering for parked domains."""
    
    print("\n🔍 Testing Content Filtering")
    print("=" * 50)
    
    test_content = [
        # Parked domain content (should be detected)
        ("This domain is for sale. Contact us to buy this premium domain.", True),
        ("Domain parking by GoDaddy. This domain is for sale.", True),
        ("Coming soon! This site is under construction.", True),
        ("Buy this domain - Premium domain for sale", True),
        ("Expired domain - contact registrar", True),
        
        # Valid content (should NOT be detected as parked)
        ("Welcome to our cryptocurrency project. We are building the future of finance with blockchain technology.", False),
        ("About us: Founded in 2020, we are developing decentralized finance solutions.", False),
        ("", False),  # Empty content
        ("Short content", False),  # Short but not parked
        
        # Edge cases
        ("domain", False),  # Just the word domain (too short to trigger)
        ("This domain provides cryptocurrency news and analysis for the blockchain community.", False),  # Contains "domain" but legitimate
    ]
    
    for content, expected_parked in test_content:
        is_parked = url_filter.is_likely_parked_domain(content)
        status = "🏠 PARKED" if is_parked else "✅ VALID"
        expected_status = "🏠 PARKED" if expected_parked else "✅ VALID"
        
        result = "✓" if is_parked == expected_parked else "✗ MISMATCH"
        
        print(f"{result} {status} (expected {expected_status}): {content[:60]}...")
    
    print("=" * 50)

def test_url_cleaning():
    """Test URL cleaning functionality."""
    
    print("\n🧹 Testing URL Cleaning")
    print("=" * 50)
    
    test_urls = [
        "https://ethereum.org/en/whitepaper/#introduction",
        "https://compound.finance/docs?utm_source=google&utm_medium=cpc",
        "https://uniswap.org/?fbclid=abc123&ref=twitter",
        "https://bitcoin.org/en/",
    ]
    
    for url in test_urls:
        clean_url = url_filter.get_clean_url(url)
        print(f"Original: {url}")
        print(f"Cleaned:  {clean_url}")
        print()

if __name__ == "__main__":
    test_url_filtering()
    test_content_filtering() 
    test_url_cleaning()
    
    print("\n🎯 URL filtering tests completed!")
    print("Check the results above to verify filtering is working correctly.")