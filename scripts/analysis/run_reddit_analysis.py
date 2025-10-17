#!/usr/bin/env python3
"""
Reddit Analysis Batch Runner

This script processes Reddit community links in manageable batches,
analyzing community health, sentiment, and development discussions.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.database import DatabaseManager
from src.pipelines.content_analysis_pipeline import ContentAnalysisPipeline
from dotenv import load_dotenv

# Load environment variables
config_path = Path(__file__).parent / "config" / "env"
load_dotenv(config_path)

def main():
    """Run Reddit community analysis in batches."""
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize pipeline with optimized settings for Reddit
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={
            'max_posts': 50,        # Limit posts per subreddit for efficiency
            'recent_days': 30,      # Focus on recent discussions
            'delay': 1.0            # Rate limiting between requests
        },
        analyzer_config={
            'provider': 'ollama', 
            'model': 'llama3.1:latest',    # High-quality model for comprehensive analysis
            'ollama_base_url': 'http://localhost:11434'
        }
    )
    
    print("=== Reddit Community Analysis ===")
    print("Starting Reddit community analysis batch...")
    
    # Check how many Reddit communities need analysis
    reddit_projects = pipeline.discover_projects_for_analysis(link_types=['reddit'])
    print(f"Found {len(reddit_projects)} Reddit communities ready for analysis")
    
    if len(reddit_projects) == 0:
        print("No Reddit communities need analysis at this time.")
        return
    
    # Run analysis on first 50 communities to start
    batch_size = 50
    print(f"Processing first {batch_size} Reddit communities...")
    print(f"Estimated time: {batch_size * 2} minutes")
    print()
    
    stats = pipeline.run_analysis_batch(link_types=['reddit'], max_projects=batch_size)
    
    print("\n=== Reddit Analysis Results ===")
    print(f"Projects found: {stats['projects_found']}")
    print(f"Successful analyses: {stats['successful_analyses']}")
    print(f"Failed analyses: {stats['failed_analyses']}")
    print(f"Reddit communities analyzed: {stats['reddit_analyzed']}")
    
    if stats['projects_found'] > 0:
        success_rate = (stats['successful_analyses'] / stats['projects_found']) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    # Calculate remaining work
    remaining = len(reddit_projects) - stats['projects_found']
    print(f"Remaining Reddit communities to analyze: {remaining}")
    
    if remaining > 0:
        print(f"\nTo continue processing, run this script again.")
        print(f"Estimated total time for all Reddit communities: {remaining * 2 // 60} hours")

if __name__ == "__main__":
    main()