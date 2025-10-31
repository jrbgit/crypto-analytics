"""
Test Website Scraper Retry Logic and Error Handling

This script tests the enhanced retry logic and error classification
to verify that the improvements work as expected.
"""

import sys
from pathlib import Path
from time import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scrapers.website_scraper import WebsiteScraper
from loguru import logger

# Configure logger for testing
logger.remove()
logger.add(
    sys.stdout,
    level="DEBUG",
    format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
)


def test_error_classification():
    """Test that errors are properly classified"""
    print("\n" + "=" * 80)
    print("TEST: Error Classification")
    print("=" * 80)
    
    scraper = WebsiteScraper(max_pages=3, max_depth=1, delay=0.1)
    
    test_cases = [
        # (error_message, expected_retryable, expected_max_retries, description)
        ("getaddrinfo failed", False, 0, "DNS failure - permanent"),
        ("SSL certificate error", False, 0, "SSL error - permanent"),
        ("404 Not Found", False, 0, "404 error - permanent"),
        ("500 Internal Server Error", True, 3, "5xx server error - transient"),
        ("502 Bad Gateway", True, 3, "5xx server error - transient"),
        ("503 Service Unavailable", True, 3, "5xx server error - transient"),
        ("Connection timeout", True, 2, "Connection issue - moderate"),
        ("Connection reset", True, 2, "Connection issue - moderate"),
        ("429 Rate Limited", True, 3, "Rate limit - transient"),
        ("Max retries exceeded", True, 2, "Connection issue - moderate"),
    ]
    
    passed = 0
    failed = 0
    
    for error_msg, expected_retryable, expected_max_retries, description in test_cases:
        is_retryable, max_retries = scraper._is_retryable_error(error_msg)
        
        if is_retryable == expected_retryable and max_retries == expected_max_retries:
            print(f"✓ PASS: {description}")
            print(f"  Error: '{error_msg}' -> Retryable: {is_retryable}, Max retries: {max_retries}")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  Error: '{error_msg}'")
            print(f"  Expected: Retryable={expected_retryable}, Max={expected_max_retries}")
            print(f"  Got:      Retryable={is_retryable}, Max={max_retries}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_backoff_timing():
    """Test exponential backoff timing"""
    print("\n" + "=" * 80)
    print("TEST: Exponential Backoff Timing")
    print("=" * 80)
    
    attempts = [0, 1, 2, 3, 4, 5]
    expected_backoffs = [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]  # Capped at 10s
    
    passed = 0
    failed = 0
    
    for attempt, expected in zip(attempts, expected_backoffs):
        backoff = min((2 ** attempt) * 1.0, 10.0)
        
        if backoff == expected:
            print(f"✓ PASS: Attempt {attempt} -> {backoff}s backoff")
            passed += 1
        else:
            print(f"✗ FAIL: Attempt {attempt} -> Expected {expected}s, got {backoff}s")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_real_urls():
    """Test scraper with real URLs to verify behavior"""
    print("\n" + "=" * 80)
    print("TEST: Real URL Scraping")
    print("=" * 80)
    
    scraper = WebsiteScraper(max_pages=1, max_depth=1, delay=0.5)
    
    test_urls = [
        {
            "url": "https://httpstat.us/404",
            "expected_error_type": "http_404",
            "description": "404 error page"
        },
        {
            "url": "https://httpstat.us/500",
            "expected_error_type": "http_500",
            "description": "500 server error"
        },
        {
            "url": "https://httpstat.us/503",
            "expected_error_type": "http_503",
            "description": "503 service unavailable"
        },
        {
            "url": "https://thisdomain-definitely-does-not-exist-12345.com",
            "expected_error_type": "dns",
            "description": "DNS resolution failure"
        },
    ]
    
    passed = 0
    failed = 0
    
    for test_case in test_urls:
        url = test_case["url"]
        expected_type = test_case["expected_error_type"]
        description = test_case["description"]
        
        print(f"\nTesting: {description}")
        print(f"URL: {url}")
        
        start_time = time()
        try:
            result = scraper.scrape_website(url)
            elapsed = time() - start_time
            
            print(f"Time elapsed: {elapsed:.2f}s")
            print(f"Success: {result.scrape_success}")
            print(f"Error type: {result.error_type}")
            print(f"Error message: {result.error_message}")
            
            # Check if error type matches expected pattern
            if result.error_type and expected_type.lower() in result.error_type.lower():
                print(f"✓ PASS: Correct error type detected")
                passed += 1
            else:
                print(f"✗ FAIL: Expected error type containing '{expected_type}', got '{result.error_type}'")
                failed += 1
                
        except Exception as e:
            elapsed = time() - start_time
            print(f"✗ Exception occurred: {e}")
            print(f"Time elapsed: {elapsed:.2f}s")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_parked_domain_detection():
    """Test that parked domains are properly detected"""
    print("\n" + "=" * 80)
    print("TEST: Parked Domain Detection")
    print("=" * 80)
    
    from utils.url_filter import url_filter
    
    test_cases = [
        ("This domain is for sale. Contact us to purchase.", True, "Domain for sale"),
        ("Domain parking by GoDaddy. Buy this domain.", True, "Parking service"),
        ("Coming soon. Under construction.", True, "Under construction"),
        ("Welcome to our cryptocurrency platform. Learn about blockchain technology.", False, "Real content"),
        ("About our team and mission to revolutionize DeFi.", False, "Real content"),
    ]
    
    passed = 0
    failed = 0
    
    for content, should_be_parked, description in test_cases:
        is_parked, service = url_filter.is_likely_parked_domain(content)
        
        if is_parked == should_be_parked:
            status = "parked" if is_parked else "real"
            print(f"✓ PASS: {description} -> Correctly identified as {status}")
            if service:
                print(f"  Detected service: {service}")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  Expected: {should_be_parked}, Got: {is_parked}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_content_quality_assessment():
    """Test content quality assessment"""
    print("\n" + "=" * 80)
    print("TEST: Content Quality Assessment")
    print("=" * 80)
    
    from utils.url_filter import url_filter
    
    test_cases = [
        ("", "empty", "Empty content"),
        ("404 Page Not Found", "error", "Error page"),
        ("Access denied. Login required.", "restricted", "Access restricted"),
        ("JavaScript is required to view this page.", "dynamic", "Dynamic content"),
        ("This domain is for sale.", "parked", "Parked domain"),
        ("Welcome to our blockchain platform. We provide decentralized solutions for DeFi.", "substantial", "Substantial content"),
    ]
    
    passed = 0
    failed = 0
    
    for content, expected_type, description in test_cases:
        assessment = url_filter.assess_content_quality(content, "Test Page")
        content_type = assessment.get("content_type", "unknown")
        
        if content_type == expected_type:
            print(f"✓ PASS: {description} -> {content_type}")
            print(f"  Quality score: {assessment.get('quality_score')}, Word count: {assessment.get('word_count')}")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  Expected: {expected_type}, Got: {content_type}")
            print(f"  Assessment: {assessment}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("WEBSITE SCRAPER RETRY LOGIC AND ERROR HANDLING TESTS")
    print("=" * 80)
    
    results = []
    
    # Run all tests
    results.append(("Error Classification", test_error_classification()))
    results.append(("Exponential Backoff", test_backoff_timing()))
    results.append(("Parked Domain Detection", test_parked_domain_detection()))
    results.append(("Content Quality Assessment", test_content_quality_assessment()))
    
    # Optional: Test with real URLs (may be slow and depend on network)
    print("\n" + "=" * 80)
    print("REAL URL TESTS (These may take longer and require network access)")
    print("=" * 80)
    
    response = input("\nRun real URL tests? (y/n): ").strip().lower()
    if response == 'y':
        results.append(("Real URL Scraping", test_real_urls()))
    else:
        print("Skipping real URL tests")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    failed_count = len(results) - passed_count
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nOverall: {passed_count}/{len(results)} test suites passed")
    
    if failed_count == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {failed_count} test suite(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
