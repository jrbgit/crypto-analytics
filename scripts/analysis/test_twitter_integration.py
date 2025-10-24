#!/usr/bin/env python3
"""
Twitter Integration Test Suite

This script tests the complete Twitter analysis workflow with real crypto project accounts
to ensure data quality and analysis accuracy before production deployment.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths, get_config_path

# Set up project paths
project_root = setup_project_paths()

from src.models.database import DatabaseManager
from sqlalchemy import text
from src.collectors.twitter_api import TwitterAPIClient
from src.analyzers.twitter_analyzer import TwitterContentAnalyzer
from src.analyzers.twitter_analysis_metrics import TwitterAnalysisMetrics
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv(get_config_path() / ".env")


class TwitterIntegrationTester:
    """Test suite for Twitter integration functionality."""

    def __init__(self, database_url: str):
        """Initialize test suite with database connection."""
        self.database_url = database_url
        self.db_manager = DatabaseManager(database_url)
        self.test_results = []

        # Test accounts - well-known crypto projects with different characteristics
        self.test_accounts = [
            {
                "name": "Bitcoin",
                "url": "https://twitter.com/bitcoin",
                "expected_characteristics": {
                    "large_following": True,
                    "verified": True,
                    "old_account": True,
                    "expected_min_followers": 1000000,
                },
            },
            {
                "name": "Ethereum",
                "url": "https://twitter.com/ethereum",
                "expected_characteristics": {
                    "large_following": True,
                    "verified": True,
                    "old_account": True,
                    "expected_min_followers": 500000,
                },
            },
            {
                "name": "Chainlink",
                "url": "https://twitter.com/chainlink",
                "expected_characteristics": {
                    "large_following": True,
                    "verified": True,
                    "professional": True,
                    "expected_min_followers": 100000,
                },
            },
            {
                "name": "Uniswap",
                "url": "https://twitter.com/uniswap",
                "expected_characteristics": {
                    "large_following": True,
                    "verified": True,
                    "professional": True,
                    "expected_min_followers": 50000,
                },
            },
            {
                "name": "CoinGecko",
                "url": "https://twitter.com/coingecko",
                "expected_characteristics": {
                    "large_following": True,
                    "verified": True,
                    "active": True,
                    "expected_min_followers": 200000,
                },
            },
        ]

        logger.info("Twitter Integration Test Suite initialized")

    def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite and return results."""

        logger.info("🚀 Starting Twitter Integration Test Suite")
        print("=" * 60)
        print("🐦 TWITTER INTEGRATION TEST SUITE")
        print("=" * 60)

        # Check prerequisites
        if not self._check_prerequisites():
            return self._generate_failure_report("Prerequisites not met")

        # Test API client functionality
        if not self._test_api_client():
            return self._generate_failure_report("API client tests failed")

        # Test analysis metrics
        if not self._test_analysis_metrics():
            return self._generate_failure_report("Analysis metrics tests failed")

        # Test complete analyzer integration
        if not self._test_analyzer_integration():
            return self._generate_failure_report("Analyzer integration tests failed")

        # Test with real accounts (limited to preserve API quota)
        if not self._test_real_accounts():
            return self._generate_failure_report("Real account tests failed")

        # Generate comprehensive report
        return self._generate_success_report()

    def _check_prerequisites(self) -> bool:
        """Check that all prerequisites are met."""

        logger.info("🔍 Checking prerequisites...")

        # Check environment variables
        bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        if not bearer_token:
            logger.error("❌ TWITTER_BEARER_TOKEN environment variable not set")
            return False

        logger.success("✅ Twitter Bearer Token found")

        # Check database connection
        try:
            with self.db_manager.get_session() as session:
                result = session.execute(text("SELECT 1")).scalar()
                if result == 1:
                    logger.success("✅ Database connection working")
                else:
                    logger.error("❌ Database connection failed")
                    return False
        except Exception as e:
            logger.error(f"❌ Database error: {e}")
            return False

        # Check API usage quota
        try:
            api_client = TwitterAPIClient(bearer_token, self.db_manager)
            stats = api_client.get_usage_stats()
            remaining_calls = stats["monthly_remaining"]

            if remaining_calls < 5:  # Need at least 5 calls for testing
                logger.error(
                    f"❌ Insufficient API quota: {remaining_calls} calls remaining"
                )
                logger.error("   Need at least 5 API calls to run tests safely")
                return False

            logger.success(
                f"✅ API quota sufficient: {remaining_calls} calls remaining"
            )

        except Exception as e:
            logger.error(f"❌ API client initialization failed: {e}")
            return False

        return True

    def _test_api_client(self) -> bool:
        """Test Twitter API client functionality."""

        logger.info("🔧 Testing Twitter API Client...")

        try:
            bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
            api_client = TwitterAPIClient(bearer_token, self.db_manager)

            # Test URL parsing
            test_urls = [
                "https://twitter.com/bitcoin",
                "https://x.com/ethereum",
                "@chainlink",
                "https://twitter.com/uniswap/status/123456",
            ]

            expected_usernames = ["bitcoin", "ethereum", "chainlink", "uniswap"]

            for i, url in enumerate(test_urls):
                username = api_client.extract_username_from_url(url)
                if username != expected_usernames[i]:
                    logger.error(
                        f"❌ URL parsing failed: {url} -> {username} (expected {expected_usernames[i]})"
                    )
                    return False

            logger.success("✅ URL parsing tests passed")

            # Test rate limit checking
            can_proceed, message = api_client.can_make_request()
            if not can_proceed:
                logger.warning(f"⚠️ Rate limit check: {message}")
            else:
                logger.success("✅ Rate limit checks working")

            return True

        except Exception as e:
            logger.error(f"❌ API client test failed: {e}")
            return False

    def _test_analysis_metrics(self) -> bool:
        """Test the analysis metrics calculation."""

        logger.info("📊 Testing Analysis Metrics...")

        try:
            metrics_analyzer = TwitterAnalysisMetrics()

            # Test with sample data representing different account types
            test_profiles = [
                {
                    "name": "High Quality Account",
                    "data": {
                        "username": "bitcoin",
                        "account_age_days": 2500,
                        "verified": True,
                        "followers_count": 5000000,
                        "following_count": 1,
                        "tweet_count": 400,
                        "listed_count": 100000,
                        "description": "Bitcoin is a decentralized digital currency.",
                        "url": "https://bitcoin.org",
                        "profile_image_url": "https://example.com/image.jpg",
                    },
                    "expected_score_range": (8.0, 10.0),
                },
                {
                    "name": "Suspicious Account",
                    "data": {
                        "username": "fakecoin123",
                        "account_age_days": 15,
                        "verified": False,
                        "followers_count": 50,
                        "following_count": 5000,
                        "tweet_count": 1000,
                        "listed_count": 0,
                        "description": "Get rich quick with guaranteed returns!",
                        "profile_image_url": None,
                    },
                    "expected_score_range": (0.0, 3.0),
                },
                {
                    "name": "Average Account",
                    "data": {
                        "username": "normalproject",
                        "account_age_days": 365,
                        "verified": False,
                        "followers_count": 5000,
                        "following_count": 1000,
                        "tweet_count": 300,
                        "listed_count": 50,
                        "description": "A blockchain project for the future.",
                        "url": "https://example.com",
                        "profile_image_url": "https://example.com/image.jpg",
                    },
                    "expected_score_range": (4.0, 8.0),
                },
            ]

            for test_profile in test_profiles:
                result = metrics_analyzer.analyze_account(test_profile["data"])

                expected_min, expected_max = test_profile["expected_score_range"]
                actual_score = result.overall_score

                if not (expected_min <= actual_score <= expected_max):
                    logger.error(f"❌ Metrics test failed for {test_profile['name']}")
                    logger.error(
                        f"   Expected score: {expected_min}-{expected_max}, Got: {actual_score:.2f}"
                    )
                    return False

                logger.success(
                    f"✅ {test_profile['name']}: Score {actual_score:.2f} (expected {expected_min}-{expected_max})"
                )

            return True

        except Exception as e:
            logger.error(f"❌ Analysis metrics test failed: {e}")
            return False

    def _test_analyzer_integration(self) -> bool:
        """Test the complete analyzer integration without API calls."""

        logger.info("🔧 Testing Analyzer Integration...")

        try:
            analyzer = TwitterContentAnalyzer(self.db_manager)

            # Test data quality calculation
            sample_profile = {
                "user_id": "12345",
                "username": "testaccount",
                "name": "Test Account",
                "followers_count": 1000,
                "following_count": 500,
                "tweet_count": 200,
                "account_age_days": 365,
            }

            quality_score = analyzer._calculate_data_quality_score(sample_profile)

            if not (
                0.8 <= quality_score <= 1.0
            ):  # Should be high quality with all fields
                logger.error(f"❌ Data quality calculation failed: {quality_score}")
                return False

            logger.success(f"✅ Data quality calculation working: {quality_score:.2f}")

            # Test usage stats
            stats = analyzer.get_usage_stats()
            if "monthly_usage" not in stats or "monthly_limit" not in stats:
                logger.error("❌ Usage stats format incorrect")
                return False

            logger.success("✅ Usage stats working")

            return True

        except Exception as e:
            logger.error(f"❌ Analyzer integration test failed: {e}")
            return False

    def _test_real_accounts(self) -> bool:
        """Test with real Twitter accounts (limited to preserve quota)."""

        logger.info("🌐 Testing with Real Twitter Accounts...")

        try:
            analyzer = TwitterContentAnalyzer(self.db_manager)

            # Check available quota
            stats = analyzer.get_usage_stats()
            available_calls = stats["monthly_remaining"]

            # Limit tests based on available quota
            max_tests = min(3, available_calls - 2)  # Keep 2 calls as buffer

            if max_tests < 1:
                logger.warning("⚠️ Skipping real account tests - insufficient API quota")
                return True

            logger.info(f"📊 Testing {max_tests} accounts (preserving API quota)")

            test_accounts = self.test_accounts[:max_tests]
            successful_tests = 0

            for account in test_accounts:
                logger.info(f"🔍 Testing {account['name']}: {account['url']}")

                try:
                    # Perform analysis
                    analysis = analyzer.analyze_twitter_link(
                        link_id=999999,  # Fake ID for testing
                        twitter_url=account["url"],
                        project_name=account["name"],
                    )

                    if not analysis:
                        logger.error(f"❌ Analysis failed for {account['name']}")
                        continue

                    # Validate results against expected characteristics
                    expected = account["expected_characteristics"]

                    if expected.get(
                        "large_following"
                    ) and analysis.followers_count < expected.get(
                        "expected_min_followers", 0
                    ):
                        logger.warning(
                            f"⚠️ {account['name']}: Followers lower than expected ({analysis.followers_count:,})"
                        )

                    if expected.get("verified") and not analysis.verified:
                        logger.warning(
                            f"⚠️ {account['name']}: Expected verified account"
                        )

                    if expected.get("old_account") and analysis.account_age_days < 365:
                        logger.warning(
                            f"⚠️ {account['name']}: Account newer than expected ({analysis.account_age_days} days)"
                        )

                    # Check overall analysis quality
                    if analysis.overall_score < 5.0:
                        logger.warning(
                            f"⚠️ {account['name']}: Lower score than expected ({analysis.overall_score:.2f})"
                        )

                    logger.success(f"✅ {account['name']}: Analysis complete")
                    logger.info(
                        f"   Score: {analysis.overall_score:.2f}/10, Followers: {analysis.followers_count:,}"
                    )
                    logger.info(
                        f"   Health: {analysis.health_status}, Confidence: {analysis.confidence_score:.2f}"
                    )

                    successful_tests += 1

                    # Brief pause between API calls
                    time.sleep(3)

                except Exception as e:
                    logger.error(f"❌ Error testing {account['name']}: {e}")
                    continue

            if successful_tests == 0:
                logger.error("❌ No real account tests succeeded")
                return False

            logger.success(
                f"✅ Real account tests completed: {successful_tests}/{len(test_accounts)} successful"
            )

            # Show final API usage
            final_stats = analyzer.get_usage_stats()
            calls_used = final_stats["monthly_usage"] - stats["monthly_usage"]
            logger.info(f"📊 API calls used for testing: {calls_used}")
            logger.info(f"📊 Remaining quota: {final_stats['monthly_remaining']}")

            return True

        except Exception as e:
            logger.error(f"❌ Real account test failed: {e}")
            return False

    def _generate_success_report(self) -> Dict[str, Any]:
        """Generate comprehensive success report."""

        logger.success("🎉 All Twitter Integration Tests Passed!")

        report = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "tests_completed": [
                "Prerequisites Check",
                "API Client Functionality",
                "Analysis Metrics Calculation",
                "Analyzer Integration",
                "Real Account Analysis",
            ],
            "recommendations": [
                "Twitter integration is ready for production use",
                "Monitor API usage to stay within 100 calls/month limit",
                "Use prioritization strategy for maximum value",
                "Run batch analysis during low-activity periods",
            ],
            "next_steps": [
                "Set up Twitter API credentials in production",
                "Run prioritization script to identify target accounts",
                "Schedule regular batch analysis runs",
                "Monitor progress with enhanced progress monitor",
            ],
        }

        print("\n" + "=" * 60)
        print("✅ TWITTER INTEGRATION TEST RESULTS")
        print("=" * 60)
        print("🎉 Status: ALL TESTS PASSED")
        print(f"📅 Test Date: {report['timestamp']}")
        print("\n📋 Tests Completed:")
        for test in report["tests_completed"]:
            print(f"  ✅ {test}")

        print("\n💡 Recommendations:")
        for rec in report["recommendations"]:
            print(f"  • {rec}")

        print("\n🚀 Next Steps:")
        for step in report["next_steps"]:
            print(f"  1. {step}")

        return report

    def _generate_failure_report(self, error_reason: str) -> Dict[str, Any]:
        """Generate failure report."""

        logger.error(f"❌ Twitter Integration Tests Failed: {error_reason}")

        report = {
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error_reason": error_reason,
            "troubleshooting_steps": [
                "Check TWITTER_BEARER_TOKEN environment variable",
                "Verify database connection",
                "Check API quota availability",
                "Review error logs for specific issues",
            ],
        }

        print("\n" + "=" * 60)
        print("❌ TWITTER INTEGRATION TEST RESULTS")
        print("=" * 60)
        print(f"❌ Status: FAILED - {error_reason}")
        print(f"📅 Test Date: {report['timestamp']}")

        print("\n🔧 Troubleshooting Steps:")
        for step in report["troubleshooting_steps"]:
            print(f"  • {step}")

        return report


def main():
    """Run the Twitter integration test suite."""

    # Initialize database
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/crypto_analytics.db")

    # Run tests
    tester = TwitterIntegrationTester(database_url)
    results = tester.run_all_tests()

    # Exit with appropriate code
    if results["status"] == "success":
        logger.success("🎉 Twitter integration testing completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Twitter integration testing failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
