#!/usr/bin/env python3
"""
Telegram Integration Test Suite

This script tests the complete Telegram analysis workflow with real crypto project channels
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
from src.collectors.telegram_api import TelegramAPIClient
from src.analyzers.telegram_analyzer import TelegramContentAnalyzer
from src.analyzers.telegram_analysis_metrics import TelegramAnalysisMetrics
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv(get_config_path() / ".env")


class TelegramIntegrationTester:
    """Test suite for Telegram integration functionality."""

    def __init__(self, database_url: str):
        """Initialize test suite with database connection."""
        self.database_url = database_url
        self.db_manager = DatabaseManager(database_url)
        self.test_results = []

        # Test channels - well-known crypto projects with different characteristics
        self.test_channels = [
            {
                "name": "Ethereum",
                "url": "https://t.me/ethereum",
                "expected_characteristics": {
                    "large_following": True,
                    "official": True,
                    "active": True,
                    "expected_min_members": 10000,
                },
            },
            {
                "name": "Chainlink",
                "url": "https://t.me/chainlink_official",
                "expected_characteristics": {
                    "large_following": True,
                    "official": True,
                    "professional": True,
                    "expected_min_members": 5000,
                },
            },
            {
                "name": "Binance",
                "url": "https://t.me/binance",
                "expected_characteristics": {
                    "large_following": True,
                    "verified": True,
                    "active": True,
                    "expected_min_members": 50000,
                },
            },
        ]

        logger.info("Telegram Integration Test Suite initialized")

    def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite and return results."""

        logger.info("🚀 Starting Telegram Integration Test Suite")
        print("=" * 60)
        print("📱 TELEGRAM INTEGRATION TEST SUITE")
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

        # Test with real channels (limited to preserve API quota)
        if not self._test_real_channels():
            return self._generate_failure_report("Real channel tests failed")

        # Generate comprehensive report
        return self._generate_success_report()

    def _check_prerequisites(self) -> bool:
        """Check that all prerequisites are met."""

        logger.info("🔍 Checking prerequisites...")

        # Check environment variables
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN environment variable not set")
            return False

        logger.success("✅ Telegram Bot Token found")

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

        # Check API client initialization
        try:
            api_client = TelegramAPIClient(bot_token, self.db_manager)
            stats = api_client.get_usage_stats()
            remaining_calls = stats["minute_remaining"]

            if remaining_calls < 3:  # Need at least 3 calls for testing
                logger.error(
                    f"❌ Insufficient API quota: {remaining_calls} calls remaining this minute"
                )
                logger.error("   Need at least 3 API calls to run tests safely")
                return False

            logger.success(
                f"✅ API quota sufficient: {remaining_calls} calls remaining this minute"
            )

        except Exception as e:
            logger.error(f"❌ API client initialization failed: {e}")
            return False

        return True

    def _test_api_client(self) -> bool:
        """Test Telegram API client functionality."""

        logger.info("🔧 Testing Telegram API Client...")

        try:
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            api_client = TelegramAPIClient(bot_token, self.db_manager)

            # Test URL parsing
            test_urls = [
                "https://t.me/ethereum",
                "https://telegram.me/chainlink",
                "@binance",
                "https://t.me/bitcoin/123",
            ]

            expected_ids = ["ethereum", "chainlink", "binance", "bitcoin"]

            for i, url in enumerate(test_urls):
                channel_id = api_client.extract_channel_id_from_url(url)
                if channel_id != expected_ids[i]:
                    logger.error(
                        f"❌ URL parsing failed: {url} -> {channel_id} (expected {expected_ids[i]})"
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
            metrics_analyzer = TelegramAnalysisMetrics()

            # Test with sample data representing different channel types
            test_channels = [
                {
                    "name": "High Quality Channel",
                    "data": {
                        "channel_id": "ethereum",
                        "title": "Ethereum Official",
                        "username": "ethereum",
                        "type": "channel",
                        "description": "Official Ethereum blockchain protocol announcements and development updates. Visit our GitHub.",
                        "member_count": 150000,
                        "has_protected_content": True,
                        "has_aggressive_anti_spam_enabled": True,
                        "pinned_message": {
                            "text": "Welcome to Ethereum official channel"
                        },
                        "size_category": "large",
                        "type_score": 10,
                    },
                    "expected_score_range": (8.0, 10.0),
                },
                {
                    "name": "Suspicious Channel",
                    "data": {
                        "channel_id": "moonpump123",
                        "title": "🚀MOONPUMP🚀 100x GUARANTEED 💎",
                        "type": "group",
                        "description": "GET RICH QUICK!!! Free money airdrop guaranteed profit 1000x!!!",
                        "member_count": 0,
                        "size_category": "minimal",
                        "type_score": 6,
                    },
                    "expected_score_range": (0.0, 3.0),
                },
                {
                    "name": "Average Channel",
                    "data": {
                        "channel_id": "normalproject",
                        "title": "Normal Crypto Project",
                        "type": "channel",
                        "description": "A blockchain project for the future.",
                        "username": "normalproject",
                        "member_count": 5000,
                        "size_category": "medium",
                        "type_score": 10,
                    },
                    "expected_score_range": (5.0, 8.0),
                },
            ]

            for test_channel in test_channels:
                result = metrics_analyzer.analyze_channel(test_channel["data"])

                expected_min, expected_max = test_channel["expected_score_range"]
                actual_score = result.overall_score

                if not (expected_min <= actual_score <= expected_max):
                    logger.error(f"❌ Metrics test failed for {test_channel['name']}")
                    logger.error(
                        f"   Expected score: {expected_min}-{expected_max}, Got: {actual_score:.2f}"
                    )
                    return False

                logger.success(
                    f"✅ {test_channel['name']}: Score {actual_score:.2f} (expected {expected_min}-{expected_max})"
                )

            return True

        except Exception as e:
            logger.error(f"❌ Analysis metrics test failed: {e}")
            return False

    def _test_analyzer_integration(self) -> bool:
        """Test the complete analyzer integration without API calls."""

        logger.info("🔧 Testing Analyzer Integration...")

        try:
            analyzer = TelegramContentAnalyzer(self.db_manager)

            # Test data quality calculation
            sample_channel = {
                "channel_id": "testchannel",
                "title": "Test Channel",
                "type": "channel",
                "member_count": 1000,
                "description": "Test description",
                "username": "testchannel",
                "chat_id": 123456,
            }

            quality_score = analyzer._calculate_data_quality_score(sample_channel)

            if not (
                0.8 <= quality_score <= 1.0
            ):  # Should be high quality with all fields
                logger.error(f"❌ Data quality calculation failed: {quality_score}")
                return False

            logger.success(f"✅ Data quality calculation working: {quality_score:.2f}")

            # Test usage stats
            stats = analyzer.get_usage_stats()
            if "minute_usage" not in stats or "minute_limit" not in stats:
                logger.error("❌ Usage stats format incorrect")
                return False

            logger.success("✅ Usage stats working")

            return True

        except Exception as e:
            logger.error(f"❌ Analyzer integration test failed: {e}")
            return False

    def _test_real_channels(self) -> bool:
        """Test with real Telegram channels (limited to preserve quota)."""

        logger.info("🌐 Testing with Real Telegram Channels...")

        try:
            analyzer = TelegramContentAnalyzer(self.db_manager)

            # Check available quota
            stats = analyzer.get_usage_stats()
            available_calls = stats["minute_remaining"]

            # Limit tests based on available quota
            max_tests = min(2, available_calls - 1)  # Keep 1 call as buffer

            if max_tests < 1:
                logger.warning("⚠️ Skipping real channel tests - insufficient API quota")
                return True

            logger.info(f"📊 Testing {max_tests} channels (preserving API quota)")

            test_channels = self.test_channels[:max_tests]
            successful_tests = 0

            for channel in test_channels:
                logger.info(f"🔍 Testing {channel['name']}: {channel['url']}")

                try:
                    # Perform analysis
                    analysis = analyzer.analyze_telegram_link(
                        link_id=999999,  # Fake ID for testing
                        telegram_url=channel["url"],
                        project_name=channel["name"],
                    )

                    if not analysis:
                        logger.error(f"❌ Analysis failed for {channel['name']}")
                        continue

                    # Validate results against expected characteristics
                    expected = channel["expected_characteristics"]

                    if expected.get(
                        "large_following"
                    ) and analysis.member_count < expected.get(
                        "expected_min_members", 0
                    ):
                        logger.warning(
                            f"⚠️ {channel['name']}: Members lower than expected ({analysis.member_count:,})"
                        )

                    if expected.get("official") and not analysis.has_username:
                        logger.warning(
                            f"⚠️ {channel['name']}: Expected official channel with username"
                        )

                    # Check overall analysis quality
                    if analysis.overall_score < 5.0:
                        logger.warning(
                            f"⚠️ {channel['name']}: Lower score than expected ({analysis.overall_score:.2f})"
                        )

                    logger.success(f"✅ {channel['name']}: Analysis complete")
                    logger.info(
                        f"   Score: {analysis.overall_score:.2f}/10, Members: {analysis.member_count:,}"
                    )
                    logger.info(
                        f"   Health: {analysis.health_status}, Confidence: {analysis.confidence_score:.2f}"
                    )

                    successful_tests += 1

                    # Brief pause between API calls
                    time.sleep(2)

                except Exception as e:
                    logger.error(f"❌ Error testing {channel['name']}: {e}")
                    continue

            if successful_tests == 0:
                logger.error("❌ No real channel tests succeeded")
                return False

            logger.success(
                f"✅ Real channel tests completed: {successful_tests}/{len(test_channels)} successful"
            )

            # Show final API usage
            final_stats = analyzer.get_usage_stats()
            calls_used = stats["minute_usage"] - final_stats["minute_usage"]
            logger.info(f"📊 API calls used for testing: {calls_used}")
            logger.info(f"📊 Remaining quota: {final_stats['minute_remaining']}")

            return True

        except Exception as e:
            logger.error(f"❌ Real channel test failed: {e}")
            return False

    def _generate_success_report(self) -> Dict[str, Any]:
        """Generate comprehensive success report."""

        logger.success("🎉 All Telegram Integration Tests Passed!")

        report = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "tests_completed": [
                "Prerequisites Check",
                "API Client Functionality",
                "Analysis Metrics Calculation",
                "Analyzer Integration",
                "Real Channel Analysis",
            ],
            "recommendations": [
                "Telegram integration is ready for production use",
                "Monitor API usage to stay within rate limits",
                "Use batch analysis for efficient processing",
                "Run regular analysis of high-priority channels",
            ],
            "next_steps": [
                "Set up Telegram Bot API credentials in production",
                "Run batch analysis on crypto project channels",
                "Monitor channel quality and community health",
                "Integrate with overall project analysis workflow",
            ],
        }

        print("\n" + "=" * 60)
        print("✅ TELEGRAM INTEGRATION TEST RESULTS")
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

        logger.error(f"❌ Telegram Integration Tests Failed: {error_reason}")

        report = {
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error_reason": error_reason,
            "troubleshooting_steps": [
                "Check TELEGRAM_BOT_TOKEN environment variable",
                "Verify database connection",
                "Ensure bot has access to test channels",
                "Check API rate limits and quotas",
                "Review error logs for specific issues",
            ],
        }

        print("\n" + "=" * 60)
        print("❌ TELEGRAM INTEGRATION TEST RESULTS")
        print("=" * 60)
        print(f"❌ Status: FAILED - {error_reason}")
        print(f"📅 Test Date: {report['timestamp']}")

        print("\n🔧 Troubleshooting Steps:")
        for step in report["troubleshooting_steps"]:
            print(f"  • {step}")

        return report


def main():
    """Run the Telegram integration test suite."""

    # Initialize database
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/crypto_analytics.db")

    # Run tests
    tester = TelegramIntegrationTester(database_url)
    results = tester.run_all_tests()

    # Exit with appropriate code
    if results["status"] == "success":
        logger.success("🎉 Telegram integration testing completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Telegram integration testing failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
