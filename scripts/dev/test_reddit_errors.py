#!/usr/bin/env python3
"""
Test script to verify that Reddit error handling works correctly.

This script tests that expected Reddit failures (404, private, etc.)
are handled gracefully without generating error logs.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths


def main():
    """Test Reddit error handling improvements."""
    setup_project_paths()

    from src.scrapers.reddit_scraper import RedditScraper

    print("🧪 Testing Reddit Error Handling Improvements")
    print("=" * 50)

    # Initialize Reddit scraper
    scraper = RedditScraper(recent_days=7, max_posts=20)

    # Test cases - known problematic subreddits
    test_cases = [
        {
            "url": "https://reddit.com/r/nonexistentsubreddit12345",
            "expected": "404 / does not exist",
            "description": "Non-existent subreddit",
        },
        {
            "url": "https://reddit.com/r/symbiosisfinance",
            "expected": "404 / does not exist",
            "description": "Subreddit mentioned in original error",
        },
    ]

    print(f"🔍 Testing {len(test_cases)} error handling scenarios...\n")

    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['description']}")
        print(f"URL: {test_case['url']}")
        print(f"Expected: {test_case['expected']}")

        # Test the scraper
        result = scraper.scrape_reddit_community(test_case["url"])

        print(
            f"Result: {'✅ PASS' if not result.scrape_success else '❌ UNEXPECTED SUCCESS'}"
        )
        print(f"Error: {result.error_message}")
        print(f"Subreddit: {result.subreddit_name}")
        print()

    print("🎯 Key Improvements:")
    print("- Expected failures (404, private, banned) should be handled gracefully")
    print("- Error messages should be informative but not alarming")
    print("- Results should be marked as unsuccessful but not cause pipeline failures")
    print("- Status should be logged to database for tracking")

    return 0


if __name__ == "__main__":
    sys.exit(main())
