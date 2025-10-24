#!/usr/bin/env python3
"""
Analysis Progress Monitor

This script checks the current status of content analysis across all types
and provides a summary of completed vs remaining work.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths, get_config_path

# Set up project paths
project_root = setup_project_paths()

from src.models.database import DatabaseManager
from dotenv import load_dotenv
from sqlalchemy import text

# Load environment variables
load_dotenv(get_config_path() / ".env")


def main():
    """Monitor analysis progress across all content types."""
    # Initialize database
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/crypto_analytics.db")
    db_manager = DatabaseManager(database_url)

    print("=== Crypto Analytics Progress Monitor ===")
    print(f"Report generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    with db_manager.get_session() as session:
        # Get overall project count
        total_projects = session.execute(
            text("SELECT COUNT(*) FROM crypto_projects")
        ).scalar()
        print(f"📊 Total Projects in Database: {total_projects:,}")
        print()

        # Check link analysis status
        print("🔗 Content Links Status:")

        # Website links
        website_total = session.execute(
            text("SELECT COUNT(*) FROM project_links WHERE link_type = 'website'")
        ).scalar()

        website_analyzed = session.execute(
            text(
                """
            SELECT COUNT(DISTINCT pl.id) 
            FROM project_links pl 
            JOIN link_content_analysis lca ON pl.id = lca.link_id 
            WHERE pl.link_type = 'website'
        """
            )
        ).scalar()

        website_remaining = website_total - website_analyzed
        website_pct = (
            (website_analyzed / website_total * 100) if website_total > 0 else 0
        )

        print(
            f"  🌐 Websites: {website_analyzed:,}/{website_total:,} ({website_pct:.1f}%) - {website_remaining:,} remaining"
        )

        # Reddit links
        reddit_total = session.execute(
            text("SELECT COUNT(*) FROM project_links WHERE link_type = 'reddit'")
        ).scalar()

        reddit_analyzed = session.execute(
            text(
                """
            SELECT COUNT(DISTINCT pl.id) 
            FROM project_links pl 
            JOIN link_content_analysis lca ON pl.id = lca.link_id 
            WHERE pl.link_type = 'reddit'
        """
            )
        ).scalar()

        reddit_remaining = reddit_total - reddit_analyzed
        reddit_pct = (reddit_analyzed / reddit_total * 100) if reddit_total > 0 else 0

        print(
            f"  📱 Reddit: {reddit_analyzed:,}/{reddit_total:,} ({reddit_pct:.1f}%) - {reddit_remaining:,} remaining"
        )

        # Medium links
        medium_total = session.execute(
            text("SELECT COUNT(*) FROM project_links WHERE link_type = 'medium'")
        ).scalar()

        medium_analyzed = session.execute(
            text(
                """
            SELECT COUNT(DISTINCT pl.id) 
            FROM project_links pl 
            JOIN link_content_analysis lca ON pl.id = lca.link_id 
            WHERE pl.link_type = 'medium'
        """
            )
        ).scalar()

        medium_remaining = medium_total - medium_analyzed
        medium_pct = (medium_analyzed / medium_total * 100) if medium_total > 0 else 0

        print(
            f"  📝 Medium: {medium_analyzed:,}/{medium_total:,} ({medium_pct:.1f}%) - {medium_remaining:,} remaining"
        )

        # Whitepaper links
        whitepaper_total = session.execute(
            text("SELECT COUNT(*) FROM project_links WHERE link_type = 'whitepaper'")
        ).scalar()

        whitepaper_analyzed = session.execute(
            text(
                """
            SELECT COUNT(DISTINCT pl.id) 
            FROM project_links pl 
            JOIN link_content_analysis lca ON pl.id = lca.link_id 
            WHERE pl.link_type = 'whitepaper'
        """
            )
        ).scalar()

        whitepaper_remaining = whitepaper_total - whitepaper_analyzed
        whitepaper_pct = (
            (whitepaper_analyzed / whitepaper_total * 100)
            if whitepaper_total > 0
            else 0
        )

        print(
            f"  📄 Whitepapers: {whitepaper_analyzed:,}/{whitepaper_total:,} ({whitepaper_pct:.1f}%) - {whitepaper_remaining:,} remaining"
        )

        # YouTube links
        youtube_total = session.execute(
            text("SELECT COUNT(*) FROM project_links WHERE link_type = 'youtube'")
        ).scalar()

        youtube_analyzed = session.execute(
            text(
                """
            SELECT COUNT(DISTINCT pl.id) 
            FROM project_links pl 
            JOIN link_content_analysis lca ON pl.id = lca.link_id 
            WHERE pl.link_type = 'youtube'
        """
            )
        ).scalar()

        youtube_remaining = youtube_total - youtube_analyzed
        youtube_pct = (
            (youtube_analyzed / youtube_total * 100) if youtube_total > 0 else 0
        )

        print(
            f"  📺 YouTube: {youtube_analyzed:,}/{youtube_total:,} ({youtube_pct:.1f}%) - {youtube_remaining:,} remaining"
        )

        # Twitter links
        twitter_total = session.execute(
            text("SELECT COUNT(*) FROM project_links WHERE link_type = 'twitter'")
        ).scalar()

        twitter_analyzed = session.execute(
            text(
                """
            SELECT COUNT(DISTINCT pl.id) 
            FROM project_links pl 
            JOIN link_content_analysis lca ON pl.id = lca.link_id 
            WHERE pl.link_type = 'twitter'
        """
            )
        ).scalar()

        twitter_remaining = twitter_total - twitter_analyzed
        twitter_pct = (
            (twitter_analyzed / twitter_total * 100) if twitter_total > 0 else 0
        )

        print(
            f"  🐦 Twitter: {twitter_analyzed:,}/{twitter_total:,} ({twitter_pct:.1f}%) - {twitter_remaining:,} remaining"
        )

        # Telegram links
        telegram_total = session.execute(
            text("SELECT COUNT(*) FROM project_links WHERE link_type = 'telegram'")
        ).scalar()

        telegram_analyzed = session.execute(
            text(
                """
            SELECT COUNT(DISTINCT pl.id) 
            FROM project_links pl 
            JOIN link_content_analysis lca ON pl.id = lca.link_id 
            WHERE pl.link_type = 'telegram'
        """
            )
        ).scalar()

        telegram_remaining = telegram_total - telegram_analyzed
        telegram_pct = (
            (telegram_analyzed / telegram_total * 100) if telegram_total > 0 else 0
        )

        print(
            f"  📱 Telegram: {telegram_analyzed:,}/{telegram_total:,} ({telegram_pct:.1f}%) - {telegram_remaining:,} remaining"
        )

        # Overall totals
        total_links = (
            website_total
            + reddit_total
            + medium_total
            + whitepaper_total
            + youtube_total
            + twitter_total
            + telegram_total
        )
        total_analyzed = (
            website_analyzed
            + reddit_analyzed
            + medium_analyzed
            + whitepaper_analyzed
            + youtube_analyzed
            + twitter_analyzed
            + telegram_analyzed
        )
        total_remaining = total_links - total_analyzed
        overall_pct = (total_analyzed / total_links * 100) if total_links > 0 else 0

        print()
        print(
            f"📈 Overall Progress: {total_analyzed:,}/{total_links:,} ({overall_pct:.1f}%)"
        )
        print(f"⏳ Remaining Work: {total_remaining:,} links to analyze")

        # Recent analysis activity
        print()
        print("⚡ Recent Analysis Activity (Last 24 hours):")

        recent_analyses = session.execute(
            text(
                """
            SELECT 
                pl.link_type,
                COUNT(*) as count,
                AVG(CAST(lca.confidence_score AS REAL)) as avg_confidence
            FROM link_content_analysis lca
            JOIN project_links pl ON lca.link_id = pl.id
            WHERE lca.created_at > NOW() - INTERVAL '1 day'
            GROUP BY pl.link_type
            ORDER BY count DESC
        """
            )
        ).fetchall()

        if recent_analyses:
            for analysis in recent_analyses:
                link_type, count, avg_confidence = analysis
                print(
                    f"  {link_type.title()}: {count} analyses (avg confidence: {avg_confidence:.2f})"
                )
        else:
            print("  No analyses completed in the last 24 hours")

        # Analysis quality metrics
        print()
        print("📊 Analysis Quality Metrics:")

        quality_stats = session.execute(
            text(
                """
            SELECT 
                pl.link_type,
                COUNT(*) as total,
                AVG(CAST(lca.confidence_score AS REAL)) as avg_confidence,
                AVG(CAST(lca.technical_depth_score AS REAL)) as avg_technical_depth,
                AVG(CAST(lca.content_quality_score AS REAL)) as avg_content_quality
            FROM link_content_analysis lca
            JOIN project_links pl ON lca.link_id = pl.id
            WHERE lca.confidence_score IS NOT NULL
            GROUP BY pl.link_type
            ORDER BY total DESC
        """
            )
        ).fetchall()

        if quality_stats:
            for stat in quality_stats:
                link_type, total, avg_conf, avg_tech, avg_qual = stat
                if avg_tech and avg_qual:  # Website data
                    print(
                        f"  {link_type.title()}: {total} analyses | Confidence: {avg_conf:.2f} | Tech Depth: {avg_tech:.1f}/10 | Quality: {avg_qual:.1f}/10"
                    )
                else:  # Other content types
                    print(
                        f"  {link_type.title()}: {total} analyses | Confidence: {avg_conf:.2f}"
                    )

        # Time estimates
        print()
        print("⏰ Estimated Completion Times (at current rate):")

        # Calculate processing rate based on recent activity
        analyses_last_hour = session.execute(
            text(
                """
            SELECT COUNT(*) FROM link_content_analysis 
            WHERE created_at > NOW() - INTERVAL '1 hour'
        """
            )
        ).scalar()

        if analyses_last_hour > 0:
            rate_per_hour = analyses_last_hour
            hours_remaining = (
                total_remaining / rate_per_hour if rate_per_hour > 0 else float("inf")
            )

            if hours_remaining < 24:
                print(f"  At current rate: {hours_remaining:.1f} hours")
            else:
                print(f"  At current rate: {hours_remaining/24:.1f} days")
        else:
            print("  Cannot estimate - no recent activity detected")

        # Twitter API Usage Monitoring (if Twitter analysis available)
        print()
        print("🐦 Twitter API Usage & Analysis Insights:")

        # Check for Twitter API usage in the last 30 days
        twitter_api_usage = session.execute(
            text(
                """
            SELECT COUNT(*) as api_calls_used
            FROM api_usage 
            WHERE api_provider = 'twitter' 
                AND request_timestamp > NOW() - INTERVAL '30 days'
                AND response_status = 200
        """
            )
        ).scalar()

        if twitter_api_usage:
            print(
                f"  🔍 API Calls Used (Last 30 days): {twitter_api_usage}/100 ({twitter_api_usage:.0f}%)"
            )
            print(f"  📊 Remaining Monthly Quota: {100 - twitter_api_usage} calls")

            # Twitter analysis quality insights
            twitter_quality = session.execute(
                text(
                    """
                SELECT 
                    AVG(CAST(lca.technical_depth_score AS REAL)) as avg_authenticity,
                    AVG(CAST(lca.content_quality_score AS REAL)) as avg_professional,
                    COUNT(*) as total_analyzed
                FROM link_content_analysis lca
                JOIN project_links pl ON lca.link_id = pl.id
                WHERE pl.link_type = 'twitter'
                    AND lca.confidence_score IS NOT NULL
            """
                )
            ).fetchone()

            if twitter_quality and twitter_quality[2] > 0:
                avg_auth, avg_prof, total = twitter_quality
                print(f"  🎆 Analysis Quality: {total} accounts analyzed")
                print(f"      • Avg Authenticity Score: {avg_auth:.1f}/10")
                print(f"      • Avg Professional Score: {avg_prof:.1f}/10")

            # High priority Twitter accounts analyzed
            high_priority_twitter = session.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM link_content_analysis lca
                JOIN project_links pl ON lca.link_id = pl.id
                JOIN crypto_projects cp ON pl.project_id = cp.id
                WHERE pl.link_type = 'twitter'
                    AND (cp.rank <= 100 OR cp.market_cap > 1000000000)
            """
                )
            ).scalar()

            if high_priority_twitter:
                print(
                    f"  🏆 High Priority Accounts Analyzed: {high_priority_twitter} (Top 100 or $1B+ market cap)"
                )
        else:
            print(
                f"  🚨 No Twitter API usage detected - Twitter analysis may not be active"
            )
            print(f"  📝 Tip: Run Twitter batch analysis to start analyzing accounts")

        # Telegram API Usage Monitoring (if Telegram analysis available)
        print()
        print("📱 Telegram Bot API Usage & Analysis Insights:")

        # Check for Telegram API usage in the last 30 days
        telegram_api_usage = session.execute(
            text(
                """
            SELECT COUNT(*) as api_calls_used
            FROM api_usage 
            WHERE api_provider = 'telegram' 
                AND request_timestamp > NOW() - INTERVAL '30 days'
                AND response_status = 200
        """
            )
        ).scalar()

        if telegram_api_usage:
            print(f"  🔍 API Calls Used (Last 30 days): {telegram_api_usage} calls")
            print(f"  📊 Rate Limit: Conservative 20 calls/minute for channel analysis")

            # Telegram analysis quality insights
            telegram_quality = session.execute(
                text(
                    """
                SELECT 
                    AVG(CAST(lca.technical_depth_score AS REAL)) as avg_authenticity,
                    AVG(CAST(lca.content_quality_score AS REAL)) as avg_content,
                    COUNT(*) as total_analyzed
                FROM link_content_analysis lca
                JOIN project_links pl ON lca.link_id = pl.id
                WHERE pl.link_type = 'telegram'
                    AND lca.confidence_score IS NOT NULL
            """
                )
            ).fetchone()

            if telegram_quality and telegram_quality[2] > 0:
                avg_auth, avg_content, total = telegram_quality
                print(f"  🎆 Analysis Quality: {total} channels analyzed")
                print(f"      • Avg Authenticity Score: {avg_auth:.1f}/10")
                print(f"      • Avg Content Score: {avg_content:.1f}/10")

            # High priority Telegram channels analyzed
            high_priority_telegram = session.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM link_content_analysis lca
                JOIN project_links pl ON lca.link_id = pl.id
                JOIN crypto_projects cp ON pl.project_id = cp.id
                WHERE pl.link_type = 'telegram'
                    AND (cp.rank <= 100 OR cp.market_cap > 1000000000)
            """
                )
            ).scalar()

            if high_priority_telegram:
                print(
                    f"  🏆 High Priority Channels Analyzed: {high_priority_telegram} (Top 100 or $1B+ market cap)"
                )

            # Channel health insights
            telegram_health_stats = session.execute(
                text(
                    """
                SELECT 
                    COUNT(CASE WHEN lca.development_stage = 'excellent' THEN 1 END) as excellent,
                    COUNT(CASE WHEN lca.development_stage = 'good' THEN 1 END) as good,
                    COUNT(CASE WHEN lca.development_stage = 'suspicious' THEN 1 END) as suspicious
                FROM link_content_analysis lca
                JOIN project_links pl ON lca.link_id = pl.id
                WHERE pl.link_type = 'telegram'
                    AND lca.development_stage IS NOT NULL
            """
                )
            ).fetchone()

            if telegram_health_stats:
                excellent, good, suspicious = telegram_health_stats
                if excellent or good or suspicious:
                    print(
                        f"  🏥 Channel Health: {excellent} excellent, {good} good, {suspicious} suspicious"
                    )
        else:
            print(
                f"  🚨 No Telegram API usage detected - Telegram analysis may not be active"
            )
            print(
                f"  📝 Tip: Set up TELEGRAM_BOT_TOKEN and run Telegram batch analysis"
            )


if __name__ == "__main__":
    main()
