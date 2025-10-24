#!/usr/bin/env python3
"""
Limited Medium Analysis Runner

This script runs Medium analysis with very conservative rate limiting
to avoid 429 Too Many Requests errors.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths, get_config_path

# Set up project paths
project_root = setup_project_paths()

from src.models.database import DatabaseManager
from src.pipelines.content_analysis_pipeline import ContentAnalysisPipeline
from dotenv import load_dotenv

# Load environment variables
load_dotenv(get_config_path() / ".env")


def main():
    """Run conservative Medium analysis to avoid rate limits."""
    # Initialize database
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/crypto_analytics.db")
    db_manager = DatabaseManager(database_url)

    # Initialize pipeline with very conservative settings for Medium
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={
            "max_pages": 8,  # Website pages
            "max_depth": 2,  # Website depth
            "max_articles": 5,  # Very limited Medium articles
            "max_posts": 50,  # Reddit posts
            "recent_days": 90,  # Content recency
            "timeout": 60,  # Request timeout
            "delay": 8.0,  # Very conservative rate limiting
        },
        analyzer_config={
            "provider": "ollama",
            "model": "llama3.1:latest",
            "ollama_base_url": "http://localhost:11434",
        },
    )

    print("🐌 CONSERVATIVE MEDIUM ANALYSIS")
    print("Using very conservative rate limiting to avoid 429 errors")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Check how many Medium items need analysis
    projects = pipeline.discover_projects_for_analysis(link_types=["medium"])
    print(f"\nFound {len(projects)} Medium items ready for analysis")

    if len(projects) == 0:
        print("No Medium items need analysis at this time.")
        return

    # Process only 3 Medium items to be very conservative
    batch_size = min(3, len(projects))
    print(f"Processing only {batch_size} Medium items with extended delays...")

    # Run the analysis
    stats = pipeline.run_analysis_batch(link_types=["medium"], max_projects=batch_size)

    # Display results
    print(f"\n=== MEDIUM ANALYSIS RESULTS ===")
    print(f"Projects found: {stats['projects_found']}")
    print(f"Successful analyses: {stats['successful_analyses']}")
    print(f"Failed analyses: {stats['failed_analyses']}")
    print(f"Medium items analyzed: {stats.get('medium_analyzed', 0)}")

    if stats["projects_found"] > 0:
        success_rate = (stats["successful_analyses"] / stats["projects_found"]) * 100
        print(f"Success rate: {success_rate:.1f}%")

    print(f"\nCompleted at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Show next steps
    remaining = len(projects) - batch_size
    if remaining > 0:
        print(f"\n📊 NEXT STEPS:")
        print(f"• {remaining} Medium items remaining for analysis")
        print(f"• Wait at least 10 minutes before running again")
        print(f"• Run 'python run_medium_limited.py' to process next batch")
        print(f"• Monitor logs for any 429 errors")


if __name__ == "__main__":
    main()
