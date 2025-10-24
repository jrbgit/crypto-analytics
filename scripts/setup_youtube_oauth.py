#!/usr/bin/env python3
"""
YouTube OAuth Setup Helper

This script helps configure YouTube OAuth 2.0 credentials for the crypto analytics platform.
Run this script to test your YouTube OAuth setup and perform the initial authorization.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from loguru import logger


def main():
    """Set up and test YouTube OAuth credentials."""

    print("🎬 YouTube OAuth 2.0 Setup Helper")
    print("=" * 50)

    # Load environment variables
    config_path = project_root / "config" / ".env"
    if not config_path.exists():
        print(
            "❌ Config file not found. Please copy config/.env.example to config/.env"
        )
        return False

    load_dotenv(config_path)

    # Check if credentials are configured
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")

    if not client_id or not client_secret or client_id == "your_youtube_client_id_here":
        print("❌ YouTube OAuth credentials not configured in config/env")
        print("\nTo configure:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth 2.0 Client ID (Desktop Application)")
        print("3. Copy Client ID and Client Secret to config/.env:")
        print(f"   YOUTUBE_CLIENT_ID=your_client_id_here")
        print(f"   YOUTUBE_CLIENT_SECRET=your_client_secret_here")
        return False

    print(f"✅ Found YouTube OAuth credentials in config")
    print(f"Client ID: {client_id[:12]}...{client_id[-12:]}")

    # Test the scraper initialization
    try:
        from src.scrapers.youtube_scraper import YouTubeScraper

        print("\n🔧 Testing YouTube scraper initialization...")
        scraper = YouTubeScraper()

        if scraper.youtube_available:
            print("✅ YouTube API connection successful!")

            # Test with a known channel
            print("\n🎯 Testing channel analysis...")
            test_url = "https://www.youtube.com/@ethereum"

            result = scraper.scrape_youtube_channel(test_url)

            if result.scrape_success:
                print(f"✅ Successfully analyzed {test_url}")
                print(f"   Videos found: {result.total_videos}")
                if result.channel_info:
                    print(f"   Channel: {result.channel_info.title}")
                    print(f"   Subscribers: {result.channel_info.subscriber_count:,}")
                print(f"   Upload frequency: {result.upload_frequency_score:.1f}/10")
                print(
                    f"   Engagement quality: {result.engagement_quality_score:.1f}/10"
                )
            else:
                print(f"❌ Channel analysis failed: {result.error_message}")
                return False

        else:
            print("❌ YouTube API not available")
            return False

    except ImportError as e:
        print(f"❌ Missing required packages: {e}")
        print("\nInstall required packages:")
        print(
            "pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2"
        )
        return False
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False

    print("\n🎉 YouTube OAuth setup complete!")
    print("Your YouTube credentials are saved and ready for use.")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
