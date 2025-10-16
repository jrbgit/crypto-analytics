#!/usr/bin/env python3
"""
Test script to verify that non-analyzable file types are properly filtered
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.url_filter import url_filter

def test_url_filtering():
    """Test URL filtering for various file types"""
    
    test_cases = [
        # Should be SKIPPED (non-analyzable)
        ("https://example.com/app.apk", True, "APK file"),
        ("https://example.com/file.zip", True, "ZIP archive"),
        ("https://example.com/installer.exe", True, "Executable"),
        ("https://example.com/photo.jpg", True, "Image file"),
        ("https://example.com/video.mp4", True, "Video file"),
        ("https://example.com/music.mp3", True, "Audio file"),
        ("https://example.com/data.db", True, "Database file"),
        ("https://example.com/lib.dll", True, "Library file"),
        ("https://example.com/program.jar", True, "JAR file"),
        ("https://example.com/package.deb", True, "Package file"),
        ("https://example.com/temp.log", True, "Log file"),
        ("https://example.com/backup.bak", True, "Backup file"),
        
        # Should be ALLOWED (analyzable)
        ("https://example.com/whitepaper.pdf", False, "PDF document"),
        ("https://example.com/index.html", False, "HTML page"),
        ("https://example.com/about.htm", False, "HTM page"),
        ("https://example.com/data.json", False, "JSON data"),
        ("https://example.com/data.xml", False, "XML data"),
        ("https://example.com/readme.txt", False, "Text file"),
        ("https://example.com/", False, "Root page"),
        ("https://example.com/team", False, "Regular page"),
        ("https://drive.google.com/file/d/abc123/view", False, "Google Drive link"),
    ]
    
    print("🧪 Testing URL Filtering for Non-Analyzable Files")
    print("=" * 60)
    
    all_passed = True
    
    for url, should_skip, description in test_cases:
        is_skipped, reason = url_filter.should_skip_url(url)
        
        if is_skipped == should_skip:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_passed = False
        
        action = "SKIP" if is_skipped else "ALLOW"
        expected = "SKIP" if should_skip else "ALLOW"
        
        print(f"{status} {description}")
        print(f"    URL: {url}")
        print(f"    Expected: {expected}, Got: {action}")
        if reason:
            print(f"    Reason: {reason}")
        print()
    
    print("=" * 60)
    if all_passed:
        print("🎉 All tests PASSED! File filtering is working correctly.")
    else:
        print("⚠️  Some tests FAILED. File filtering needs adjustment.")
    
    return all_passed

if __name__ == "__main__":
    test_url_filtering()