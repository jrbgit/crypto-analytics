#!/usr/bin/env python3
"""
Medium Analysis Batch Runner

This script processes Medium publication links in manageable batches,
analyzing development activity, announcements, and content quality.
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
    """Run Medium publication analysis in batches."""
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize pipeline with optimized settings for Medium
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={
            'max_articles': 15,     # Limit articles per publication for efficiency
            'recent_days': 90,      # Focus on recent content
            'delay': 1.5            # Rate limiting between requests
        },
        analyzer_config={
            'provider': 'ollama', 
            'model': 'llama3.1:latest',    # High-quality model for comprehensive analysis
            'ollama_base_url': 'http://localhost:11434'
        }
    )
    
    print("=== Medium Publication Analysis ===")
    print("Starting Medium publication analysis batch...")
    
    # Check how many Medium publications need analysis
    medium_projects = pipeline.discover_projects_for_analysis(link_types=['medium'])
    print(f"Found {len(medium_projects)} Medium publications ready for analysis")
    
    if len(medium_projects) == 0:
        print("No Medium publications need analysis at this time.")
        return
    
    # Run analysis on first 30 publications to start
    batch_size = 30
    print(f"Processing first {batch_size} Medium publications...")
    print(f"Estimated time: {batch_size * 3} minutes")
    print()
    
    stats = pipeline.run_analysis_batch(link_types=['medium'], max_projects=batch_size)
    
    print("\n=== Medium Analysis Results ===")
    print(f"Projects found: {stats['projects_found']}")
    print(f"Successful analyses: {stats['successful_analyses']}")
    print(f"Failed analyses: {stats['failed_analyses']}")
    print(f"Medium publications analyzed: {stats['medium_analyzed']}")
    
    if stats['projects_found'] > 0:
        success_rate = (stats['successful_analyses'] / stats['projects_found']) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    # Calculate remaining work
    remaining = len(medium_projects) - stats['projects_found']
    print(f"Remaining Medium publications to analyze: {remaining}")
    
    if remaining > 0:
        print(f"\nTo continue processing, run this script again.")
        print(f"Estimated total time for all Medium publications: {remaining * 3 // 60} hours")

if __name__ == "__main__":
    main()