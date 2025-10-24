#!/usr/bin/env python3
"""
Test script to verify enhanced Ollama API usage tracking.

This script tests the new usage tracking functionality by:
1. Making a test analysis call through the enhanced analyzer
2. Verifying that usage data is properly recorded in the api_usage table
3. Checking that response times and token estimates are captured
"""

import os
import sys
from pathlib import Path
from datetime import datetime, UTC

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from loguru import logger
from src.models.database import DatabaseManager
from src.analyzers.website_analyzer import WebsiteContentAnalyzer

# Load environment variables
config_path = Path(__file__).parent / "config" / "env"
load_dotenv(config_path)


def test_ollama_usage_tracking():
    """Test the enhanced Ollama usage tracking."""

    # Initialize database manager
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://crypto_user:crypto_secure_password_2024@localhost:5432/crypto_analytics",
    )
    db_manager = DatabaseManager(database_url)

    logger.info("Testing enhanced Ollama usage tracking...")

    try:
        # Initialize analyzer with database manager
        analyzer = WebsiteContentAnalyzer(
            provider="ollama",
            model="llama3.1:latest",
            ollama_base_url="http://localhost:11434",
            db_manager=db_manager,
        )

        # Test content
        test_content = """
        CryptoTest is a revolutionary blockchain platform that aims to solve scalability issues.
        Our team consists of experienced developers from major tech companies.
        The project uses Proof of Stake consensus mechanism and is built on Ethereum.
        We plan to launch our mainnet in Q2 2024.
        """

        logger.info("Making test API call to Ollama...")
        start_time = datetime.now(UTC)

        # This should automatically track usage in the database
        result = analyzer.analyze_website(
            test_content, "test", len(test_content.split())
        )

        end_time = datetime.now(UTC)

        if result:
            logger.success("✅ Ollama API call successful")
            logger.info(
                f"Analysis completed: Technical depth: {result.technical_depth_score}/10"
            )
        else:
            logger.error("❌ Ollama API call failed")
            return False

        # Check if usage was recorded in database
        with db_manager.get_session() as session:
            from sqlalchemy import desc
            from src.models.database import APIUsage

            # Look for recent usage records
            recent_usage = (
                session.query(APIUsage)
                .filter(
                    APIUsage.api_provider == "ollama", APIUsage.created_at >= start_time
                )
                .order_by(desc(APIUsage.created_at))
                .first()
            )

            if recent_usage:
                logger.success("✅ Usage tracking verification passed!")
                logger.info(f"Provider: {recent_usage.api_provider}")
                logger.info(f"Endpoint: {recent_usage.endpoint}")
                logger.info(f"Status: {recent_usage.response_status}")
                logger.info(f"Response time: {recent_usage.response_time:.3f}s")
                logger.info(f"Estimated tokens: {recent_usage.response_size}")
                logger.info(f"Credits used: {recent_usage.credits_used}")

                if recent_usage.error_message:
                    logger.warning(f"Error message: {recent_usage.error_message}")

                return True
            else:
                logger.error("❌ No usage record found in database")
                return False

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False


def show_recent_usage_stats():
    """Show recent usage statistics from the database."""

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://crypto_user:crypto_secure_password_2024@localhost:5432/crypto_analytics",
    )
    db_manager = DatabaseManager(database_url)

    with db_manager.get_session() as session:
        from sqlalchemy import desc, func
        from src.models.database import APIUsage

        logger.info("\n📊 Recent API Usage Statistics (last 24 hours):")

        # Get stats by provider
        stats = (
            session.query(
                APIUsage.api_provider,
                func.count(APIUsage.id).label("total_calls"),
                func.avg(APIUsage.response_time).label("avg_response_time"),
                func.sum(APIUsage.response_size).label("total_tokens"),
                func.sum(APIUsage.credits_used).label("total_credits"),
            )
            .filter(
                APIUsage.created_at
                >= datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            )
            .group_by(APIUsage.api_provider)
            .all()
        )

        for stat in stats:
            logger.info(f"\n{stat.api_provider.upper()}:")
            logger.info(f"  📞 Total calls: {stat.total_calls}")
            logger.info(
                f"  ⏱️ Avg response time: {stat.avg_response_time:.3f}s"
                if stat.avg_response_time
                else "  ⏱️ Avg response time: N/A"
            )
            logger.info(
                f"  🎯 Total tokens: {stat.total_tokens:,}"
                if stat.total_tokens
                else "  🎯 Total tokens: N/A"
            )
            logger.info(
                f"  💰 Total credits: {stat.total_credits}"
                if stat.total_credits
                else "  💰 Total credits: N/A"
            )

        # Show recent failed calls
        failed_calls = (
            session.query(APIUsage)
            .filter(
                APIUsage.response_status.notin_([200]),
                APIUsage.created_at
                >= datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0),
            )
            .count()
        )

        if failed_calls > 0:
            logger.warning(f"\n⚠️ Failed calls today: {failed_calls}")


if __name__ == "__main__":
    logger.info("🚀 Starting Ollama usage tracking test")

    # Show current stats
    show_recent_usage_stats()

    # Run the test
    success = test_ollama_usage_tracking()

    if success:
        logger.success(
            "\n🎉 All tests passed! Ollama usage tracking is working correctly."
        )
    else:
        logger.error(
            "\n❌ Tests failed. Check Ollama server and database configuration."
        )
        sys.exit(1)

    # Show updated stats
    logger.info("\n" + "=" * 60)
    show_recent_usage_stats()
