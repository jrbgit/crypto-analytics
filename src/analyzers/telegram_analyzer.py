"""
Telegram Content Analyzer for Cryptocurrency Projects

This module integrates the Telegram API client with the analysis metrics
to provide comprehensive Telegram channel analysis with database storage.
"""

import json
import os
import signal
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import hashlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Import our components
from models.database import DatabaseManager, ProjectLink, LinkContentAnalysis
from collectors.telegram_api import TelegramAPIClient
from analyzers.telegram_analysis_metrics import (
    TelegramAnalysisMetrics,
    TelegramAnalysisResult,
    TelegramHealthStatus,
)

# Load environment variables
config_path = Path(__file__).parent.parent.parent / "config" / ".env"
load_dotenv(config_path)


class TelegramAnalyzerError(Exception):
    """Custom exception for Telegram analyzer errors, including API issues."""

    def __init__(self, error_code: int, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(f"Telegram Analyzer Error {error_code}: {error_message}")


@dataclass
class TelegramContentAnalysis:
    """Comprehensive Telegram content analysis result for database storage."""

    # Basic channel info
    channel_id: str
    channel_title: str
    channel_type: str
    username: Optional[str]
    description: Optional[str]
    invite_link: Optional[str]

    # Channel metrics
    member_count: int
    has_username: bool
    has_description: bool
    has_protected_content: bool
    has_anti_spam: bool

    # Analysis scores (0-10)
    authenticity_score: float
    community_score: float
    content_score: float
    activity_score: float
    security_score: float
    overall_score: float

    # Derived metrics
    size_category: str
    type_appropriateness: float

    # Health assessment
    health_status: str  # TelegramHealthStatus enum value
    confidence_score: float

    # Qualitative indicators
    red_flags: List[str]
    positive_indicators: List[str]

    # Analysis metadata
    analysis_timestamp: datetime
    api_calls_used: int
    data_quality_score: float  # How complete/reliable the data was


class TelegramContentAnalyzer:
    """Main analyzer that combines API client and metrics analysis."""

    def __init__(
        self, database_manager: DatabaseManager, api_client: TelegramAPIClient = None
    ):
        """
        Initialize the Telegram content analyzer.

        Args:
            database_manager: Database manager for storing results
            api_client: Optional pre-initialized API client
        """
        self.db_manager = database_manager

        # Initialize API client if not provided
        if api_client is None:
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            if not bot_token:
                raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
            self.api_client = TelegramAPIClient(bot_token, database_manager)
        else:
            self.api_client = api_client

        # Initialize metrics analyzer
        self.metrics_analyzer = TelegramAnalysisMetrics()

        logger.info("Telegram content analyzer initialized")

    def analyze_telegram_link(
        self, link_id: int, telegram_url: str, project_name: str = None
    ) -> Optional[TelegramContentAnalysis]:
        """
        Analyze a Telegram channel and return comprehensive results.

        Args:
            link_id: Database ID of the project link
            telegram_url: Telegram URL to analyze
            project_name: Optional project name for context

        Returns:
            TelegramContentAnalysis or None if analysis failed
        """

        logger.info(f"Starting Telegram analysis for link ID {link_id}: {telegram_url}")

        # Check if we can make API requests
        can_proceed, message = self.api_client.can_make_request()
        if not can_proceed:
            logger.error(f"Cannot proceed with Telegram analysis: {message}")
            return None

        # Extract channel ID from URL
        channel_id = self.api_client.extract_channel_id_from_url(telegram_url)
        if not channel_id:
            logger.error(
                f"Could not extract channel ID from Telegram URL: {telegram_url}"
            )
            return None

        # Track API usage before making call
        initial_usage = self.api_client.get_usage_stats()

        try:
            # Get channel analysis from API
            channel_analysis = self.api_client.analyze_channel_profile(telegram_url)
            if not channel_analysis:
                # If analyze_channel_profile returns None, it implies a specific API error already handled (like 400 chat not found)
                # We assume 400 for 'chat not found' given typical Telegram API responses.
                raise TelegramAnalyzerError(
                    400,
                    "Chat not found - channel may be private, deleted, or username incorrect",
                )

            # Calculate API calls used
            final_usage = self.api_client.get_usage_stats()
            api_calls_used = final_usage["minute_usage"] - initial_usage["minute_usage"]

            # Run metrics analysis
            metrics_result = self.metrics_analyzer.analyze_channel(channel_analysis)

            # Calculate data quality score
            data_quality_score = self._calculate_data_quality_score(channel_analysis)

            # Combine results into analysis object
            analysis = TelegramContentAnalysis(
                channel_id=channel_id,
                channel_title=channel_analysis.get("title", ""),
                channel_type=channel_analysis.get("type", ""),
                username=channel_analysis.get("username"),
                description=channel_analysis.get("description"),
                invite_link=channel_analysis.get("invite_link"),
                member_count=channel_analysis.get("member_count", 0),
                has_username=bool(channel_analysis.get("username")),
                has_description=bool(channel_analysis.get("description")),
                has_protected_content=channel_analysis.get(
                    "has_protected_content", False
                ),
                has_anti_spam=channel_analysis.get(
                    "has_aggressive_anti_spam_enabled", False
                ),
                authenticity_score=metrics_result.authenticity_score,
                community_score=metrics_result.community_score,
                content_score=metrics_result.content_score,
                activity_score=metrics_result.activity_score,
                security_score=metrics_result.security_score,
                overall_score=metrics_result.overall_score,
                size_category=channel_analysis.get("size_category", "unknown"),
                type_appropriateness=metrics_result.type_appropriateness,
                health_status=metrics_result.health_status.value,
                confidence_score=metrics_result.confidence_score,
                red_flags=metrics_result.red_flags,
                positive_indicators=metrics_result.positive_indicators,
                analysis_timestamp=datetime.now(timezone.utc),
                api_calls_used=api_calls_used,
                data_quality_score=data_quality_score,
            )

            logger.success(
                f"Telegram analysis complete for @{channel_id} (Score: {analysis.overall_score:.2f})"
            )
            return analysis

        except Exception as e:
            logger.error(
                f"Unexpected error during Telegram analysis for @{channel_id}: {e}"
            )
            # Wrap any other exceptions in TelegramAnalyzerError for consistent handling
            raise TelegramAnalyzerError(500, f"Unexpected analysis error: {e}") from e

    def _calculate_data_quality_score(self, channel_data: Dict) -> float:
        """Calculate how complete and reliable the channel data is (0-1)."""

        score = 0.0
        max_score = 0.0

        # Core fields that should be present
        core_fields = [
            ("channel_id", 0.2),
            ("title", 0.15),
            ("type", 0.1),
            ("member_count", 0.2),
            ("description", 0.15),
            ("username", 0.1),
            ("chat_id", 0.1),
        ]

        for field, weight in core_fields:
            max_score += weight
            if channel_data.get(field) is not None:
                if field == "member_count":
                    # Member count should be >= 0
                    if channel_data[field] >= 0:
                        score += weight
                else:
                    # String fields should not be empty
                    if str(channel_data[field]).strip():
                        score += weight

        return min(1.0, score / max_score if max_score > 0 else 0)

    def store_analysis_result(
        self, link_id: int, analysis: TelegramContentAnalysis
    ) -> bool:
        """
        Store Telegram analysis results in the database.

        Args:
            link_id: Database ID of the project link
            analysis: Analysis results to store

        Returns:
            True if stored successfully, False otherwise
        """

        try:
            with self.db_manager.get_session() as session:
                # Check if analysis already exists
                existing_analysis = (
                    session.query(LinkContentAnalysis)
                    .filter_by(link_id=link_id)
                    .first()
                )

                if existing_analysis:
                    logger.info(
                        f"Updating existing Telegram analysis for link ID {link_id}"
                    )
                    # Update existing record
                    content_analysis = existing_analysis
                else:
                    logger.info(f"Creating new Telegram analysis for link ID {link_id}")
                    # Create new record
                    content_analysis = LinkContentAnalysis(link_id=link_id)
                    session.add(content_analysis)

                # Store core data
                content_analysis.raw_content = json.dumps(
                    asdict(analysis), default=str, indent=2
                )
                content_analysis.content_hash = hashlib.sha256(
                    analysis.channel_id.encode()
                    + str(analysis.analysis_timestamp).encode()
                ).hexdigest()
                content_analysis.pages_analyzed = 1
                content_analysis.total_word_count = len(analysis.description or "")

                # Store Telegram-specific data in JSON fields
                telegram_data = {
                    "channel_id": analysis.channel_id,
                    "channel_title": analysis.channel_title,
                    "channel_type": analysis.channel_type,
                    "username": analysis.username,
                    "member_count": analysis.member_count,
                    "has_username": analysis.has_username,
                    "has_description": analysis.has_description,
                    "has_protected_content": analysis.has_protected_content,
                    "has_anti_spam": analysis.has_anti_spam,
                    "size_category": analysis.size_category,
                    "type_appropriateness": analysis.type_appropriateness,
                }

                content_analysis.technology_stack = [
                    f"telegram_metrics_{k}" for k in telegram_data.keys()
                ]
                content_analysis.core_features = analysis.positive_indicators
                content_analysis.red_flags = analysis.red_flags

                # Map Telegram scores to existing fields creatively
                content_analysis.technical_depth_score = analysis.authenticity_score
                content_analysis.content_quality_score = analysis.content_score
                content_analysis.confidence_score = analysis.confidence_score

                # Store additional metrics in business information fields
                content_analysis.partnerships = [
                    f"Community Score: {analysis.community_score:.1f}"
                ]
                content_analysis.funding_raised = f"Activity Score: {analysis.activity_score:.1f}, Security: {analysis.security_score:.1f}"
                content_analysis.development_stage = analysis.health_status

                # Store comprehensive data in roadmap_items
                content_analysis.roadmap_items = [
                    f"Overall Score: {analysis.overall_score:.2f}/10",
                    f"Health Status: {analysis.health_status}",
                    f"API Calls Used: {analysis.api_calls_used}",
                    f"Data Quality: {analysis.data_quality_score:.2f}",
                    f"Analysis Date: {analysis.analysis_timestamp.isoformat()}",
                    f"Member Count: {analysis.member_count:,}",
                    f"Size Category: {analysis.size_category}",
                ]

                # Update metadata
                content_analysis.created_at = analysis.analysis_timestamp
                content_analysis.updated_at = analysis.analysis_timestamp

                session.commit()

                logger.success(
                    f"Telegram analysis stored successfully for link ID {link_id}"
                )
                return True

        except IntegrityError as e:
            logger.error(f"Database integrity error storing Telegram analysis: {e}")
            return False
        except Exception as e:
            logger.error(f"Error storing Telegram analysis: {e}")
            return False

    def store_error_result(
        self, link_id: int, telegram_url: str, error_code: int, error_message: str
    ) -> bool:
        """
        Store error information when Telegram analysis fails due to API errors.

        Args:
            link_id: Database ID of the project link
            telegram_url: Telegram URL that failed
            error_code: HTTP error code from Telegram API
            error_message: Error message from Telegram API

        Returns:
            True if stored successfully, False otherwise
        """

        try:
            with self.db_manager.get_session() as session:
                # Check if analysis already exists
                existing_analysis = (
                    session.query(LinkContentAnalysis)
                    .filter_by(link_id=link_id)
                    .first()
                )

                if existing_analysis:
                    logger.info(
                        f"Updating existing Telegram error record for link ID {link_id}"
                    )
                    content_analysis = existing_analysis
                else:
                    logger.info(
                        f"Creating new Telegram error record for link ID {link_id}"
                    )
                    content_analysis = LinkContentAnalysis(link_id=link_id)
                    session.add(content_analysis)

                # Store error information
                error_data = {
                    "error": True,
                    "error_code": error_code,
                    "error_message": error_message,
                    "telegram_url": telegram_url,
                    "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                }

                content_analysis.raw_content = json.dumps(error_data, indent=2)
                content_analysis.content_hash = hashlib.sha256(
                    f"error_{error_code}_{telegram_url}_{int(time.time())}".encode()
                ).hexdigest()
                content_analysis.pages_analyzed = 0
                content_analysis.total_word_count = 0

                # Mark as error in various fields
                content_analysis.red_flags = [
                    f"Telegram API Error {error_code}: {error_message}"
                ]
                content_analysis.development_stage = f"API_ERROR_{error_code}"
                content_analysis.technical_depth_score = 0.0
                content_analysis.content_quality_score = 0.0
                content_analysis.confidence_score = 0.0

                # Store error details in roadmap_items
                content_analysis.roadmap_items = [
                    f"Error Code: {error_code}",
                    f"Error Message: {error_message}",
                    f"Failed URL: {telegram_url}",
                    f"Analysis Date: {datetime.now(timezone.utc).isoformat()}",
                    "Status: Analysis Failed - Channel Not Found or Inaccessible",
                ]

                content_analysis.created_at = datetime.now(timezone.utc)
                content_analysis.updated_at = datetime.now(timezone.utc)

                session.commit()

                logger.info(
                    f"Telegram error record stored successfully for link ID {link_id}"
                )
                return True

        except Exception as e:
            logger.error(f"Error storing Telegram error record: {e}")
            return False

    def analyze_and_store(
        self, link_id: int, telegram_url: str, project_name: str = None
    ) -> bool:
        """
        Complete workflow: analyze Telegram channel and store results.

        Args:
            link_id: Database ID of the project link
            telegram_url: Telegram URL to analyze
            project_name: Optional project name for context

        Returns:
            True if analysis and storage successful, False otherwise
        """

        logger.info(
            f"Starting complete Telegram analysis workflow for link ID {link_id}"
        )

        # Check if we can make API requests
        can_proceed, message = self.api_client.can_make_request()
        if not can_proceed:
            logger.error(f"Cannot proceed with Telegram analysis: {message}")
            # Store rate limit error
            self.store_error_result(
                link_id, telegram_url, 429, f"Rate limit exceeded: {message}"
            )
            self._update_link_status(link_id, False, "Rate limit exceeded")
            return True  # Return True to continue batch processing

        # Extract channel ID from URL for error tracking
        channel_id = self.api_client.extract_channel_id_from_url(telegram_url)
        if not channel_id:
            logger.error(
                f"Could not extract channel ID from Telegram URL: {telegram_url}"
            )
            self.store_error_result(
                link_id, telegram_url, 400, "Invalid Telegram URL format"
            )
            self._update_link_status(link_id, False, "Invalid URL format")
            return True  # Return True to continue batch processing

        # Perform analysis
        try:
            analysis = self.analyze_telegram_link(link_id, telegram_url, project_name)

            # Store results
            if not self.store_analysis_result(link_id, analysis):
                logger.error(
                    f"Failed to store Telegram analysis results for link ID {link_id}"
                )
                return False

            # Update the project link to mark it as analyzed successfully
            self._update_link_status(link_id, True, "Analysis completed successfully")
            return True

        except TelegramAnalyzerError as tae:
            logger.info(
                f"Channel @{channel_id} analysis failed with API error {tae.error_code}: {tae.error_message}"
            )
            self.store_error_result(
                link_id, telegram_url, tae.error_code, tae.error_message
            )
            self._update_link_status(link_id, False, tae.error_message)
            return True  # Return True to continue batch processing for other links
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during analysis for @{channel_id}: {e}"
            )
            self.store_error_result(
                link_id, telegram_url, 500, f"Unexpected error: {e}"
            )
            self._update_link_status(link_id, False, "Unexpected error during analysis")
            return True  # Return True to continue batch processing for other links

    def _update_link_status(
        self, link_id: int, success: bool, status_message: str = None
    ):
        """
        Update the project link status after analysis.

        Args:
            link_id: Database ID of the project link
            success: Whether the analysis was successful
            status_message: Optional status message
        """
        try:
            with self.db_manager.get_session() as session:
                link = session.query(ProjectLink).filter_by(id=link_id).first()
                if link:
                    link.needs_analysis = False
                    link.last_scraped = datetime.now(timezone.utc)
                    link.scrape_success = success
                    if status_message:
                        # Store status in a field if available, or just log it
                        pass
                    session.commit()
                    logger.info(
                        f"Updated project link {link_id} status: {'success' if success else 'failed'}"
                    )
        except Exception as e:
            logger.warning(f"Could not update project link status: {e}")

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics."""
        return self.api_client.get_usage_stats()

    def can_analyze_more(self) -> tuple[bool, str]:
        """Check if we can perform more analyses."""
        return self.api_client.can_make_request()


# Global flag for graceful shutdown
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    logger.warning(f"Received signal {signum}, requesting graceful shutdown...")
    _shutdown_requested = True


def analyze_telegram_link_batch(database_url: str, limit: int = 10) -> Dict[str, Any]:
    """
    Batch analyze Telegram links that need analysis.

    Args:
        database_url: Database connection URL
        limit: Maximum number of links to analyze

    Returns:
        Dictionary with analysis results and statistics
    """
    global _shutdown_requested
    _shutdown_requested = False

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):  # Windows doesn't have SIGTERM
        signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Starting Telegram batch analysis (limit: {limit})")

    # Initialize components
    db_manager = DatabaseManager(database_url)
    analyzer = TelegramContentAnalyzer(db_manager)

    # Check initial usage
    initial_stats = analyzer.get_usage_stats()
    logger.info(
        f"Initial API usage: {initial_stats['minute_usage']}/{initial_stats['minute_limit']} per minute"
    )

    if initial_stats["minute_remaining"] <= 0:
        logger.error("No API calls remaining this minute")
        return {
            "success": False,
            "error": "No API calls remaining",
            "stats": initial_stats,
        }

    # Find Telegram links that need analysis (excluding those already processed or errored)
    with db_manager.get_session() as session:
        telegram_links = session.execute(
            text(
                """
            SELECT 
                pl.id,
                pl.url,
                cp.name as project_name,
                cp.code as project_code
            FROM project_links pl
            JOIN crypto_projects cp ON pl.project_id = cp.id
            WHERE pl.link_type = 'telegram'
                AND pl.needs_analysis = TRUE
                AND pl.url IS NOT NULL
                AND pl.url != ''
                AND NOT EXISTS (
                    SELECT 1 FROM link_content_analysis lca 
                    WHERE lca.link_id = pl.id
                )
            ORDER BY cp.market_cap DESC NULLS LAST, cp.rank ASC NULLS LAST
            LIMIT :limit
        """
            ),
            {"limit": limit},
        ).fetchall()

    if not telegram_links:
        logger.info("No Telegram links found that need analysis")
        return {"success": True, "analyzed": 0, "message": "No links need analysis"}

    logger.info(f"Found {len(telegram_links)} Telegram links to analyze")

    # Process each link
    results = {
        "success": True,
        "analyzed": 0,
        "failed": 0,
        "skipped": 0,
        "api_calls_used": 0,
        "analyses": [],
    }

    for link in telegram_links:
        # Check for shutdown signal
        if _shutdown_requested:
            logger.warning("Shutdown requested, stopping batch analysis gracefully")
            results["skipped"] = (
                len(telegram_links) - results["analyzed"] - results["failed"]
            )
            results["shutdown_requested"] = True
            break

        link_id, telegram_url, project_name, project_code = link

        # Check if we can still make API calls
        can_proceed, reason = analyzer.can_analyze_more()
        if not can_proceed:
            logger.warning(f"Stopping batch analysis: {reason}")
            results["skipped"] = (
                len(telegram_links) - results["analyzed"] - results["failed"]
            )
            break

        logger.info(
            f"Analyzing Telegram for {project_name} ({project_code}): {telegram_url}"
        )

        try:
            success = analyzer.analyze_and_store(link_id, telegram_url, project_name)

            if success:
                results["analyzed"] += 1
                results["analyses"].append(
                    {
                        "link_id": link_id,
                        "project_name": project_name,
                        "telegram_url": telegram_url,
                        "status": "success",
                    }
                )
                logger.success(f"✅ Analysis complete for {project_name}")
            else:
                results["failed"] += 1
                results["analyses"].append(
                    {
                        "link_id": link_id,
                        "project_name": project_name,
                        "telegram_url": telegram_url,
                        "status": "failed",
                    }
                )
                logger.error(f"❌ Analysis failed for {project_name}")

        except KeyboardInterrupt:
            logger.warning(
                "KeyboardInterrupt received during analysis; stopping gracefully after current item"
            )
            results["skipped"] = (
                len(telegram_links) - results["analyzed"] - results["failed"]
            )
            results["shutdown_requested"] = True
            break
        except Exception as e:
            results["failed"] += 1
            logger.error(f"❌ Exception analyzing {project_name}: {e}")
            results["analyses"].append(
                {
                    "link_id": link_id,
                    "project_name": project_name,
                    "telegram_url": telegram_url,
                    "status": "error",
                    "error": str(e),
                }
            )

        # Brief pause between analyses
        time.sleep(1)

    # Final usage stats
    final_stats = analyzer.get_usage_stats()
    results["api_calls_used"] = (
        final_stats["minute_usage"] - initial_stats["minute_usage"]
    )
    results["final_usage"] = final_stats

    logger.info(f"Telegram batch analysis complete:")
    logger.info(f"  ✅ Analyzed: {results['analyzed']}")
    logger.info(f"  ❌ Failed: {results['failed']}")
    logger.info(f"  ⏭️  Skipped: {results['skipped']}")
    logger.info(f"  🔧 API calls used: {results['api_calls_used']}")
    logger.info(f"  📊 Remaining calls: {final_stats['minute_remaining']}")

    return results


def main():
    """Test the Telegram analyzer."""

    try:
        # Initialize database
        database_url = os.getenv("DATABASE_URL", "sqlite:///./data/crypto_analytics.db")

        if len(sys.argv) > 1 and sys.argv[1] == "batch":
            # Run batch analysis
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            results = analyze_telegram_link_batch(database_url, limit)

            print("\n=== Batch Analysis Results ===")
            print(f"Analyzed: {results['analyzed']}")
            print(f"Failed: {results['failed']}")
            print(f"API calls used: {results['api_calls_used']}")
            if results.get("shutdown_requested"):
                print("Analysis stopped due to user interruption")

        else:
            # Test single analysis
            db_manager = DatabaseManager(database_url)
            analyzer = TelegramContentAnalyzer(db_manager)

            # Test with a known crypto project Telegram
            test_url = "https://t.me/ethereum"
            analysis = analyzer.analyze_telegram_link(1, test_url, "Ethereum")

            if analysis:
                print(f"\n=== Analysis Results for @{analysis.channel_id} ===")
                print(f"Channel: {analysis.channel_title}")
                print(f"Type: {analysis.channel_type}")
                print(f"Members: {analysis.member_count:,}")
                print(f"Overall Score: {analysis.overall_score:.2f}/10")
                print(f"Health Status: {analysis.health_status.title()}")
                print(f"Confidence: {analysis.confidence_score:.2f}")

                if analysis.positive_indicators:
                    print(f"\nPositive Indicators:")
                    for indicator in analysis.positive_indicators[:5]:
                        print(f"  ✅ {indicator}")

                if analysis.red_flags:
                    print(f"\nRed Flags:")
                    for flag in analysis.red_flags[:5]:
                        print(f"  🚩 {flag}")

            stats = analyzer.get_usage_stats()
            print(
                f"\nAPI Usage: {stats['minute_usage']}/{stats['minute_limit']} per minute ({stats['usage_percentage']:.1f}%)"
            )

    except KeyboardInterrupt:
        logger.warning("Program interrupted by user")
        print("\nProgram interrupted by user. Exiting gracefully...")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
