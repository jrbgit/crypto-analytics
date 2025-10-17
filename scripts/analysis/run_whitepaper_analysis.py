#!/usr/bin/env python3
"""
Whitepaper Analysis Batch Runner

This script processes whitepaper links in manageable batches,
analyzing technical depth, tokenomics, and project fundamentals.
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
    """Run whitepaper analysis in batches."""
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize pipeline with optimized settings for whitepapers
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={
            'timeout': 60,          # Longer timeout for PDF downloads
            'max_file_size': 50 * 1024 * 1024,  # 50MB max file size
        },
        analyzer_config={
            'provider': 'ollama', 
            'model': 'llama3.1:latest',    # High-quality model for comprehensive analysis
            'ollama_base_url': 'http://localhost:11434'
        }
    )
    
    print("=== Whitepaper Analysis ===")
    print("Starting whitepaper analysis batch...")
    
    # Check how many whitepapers need analysis
    whitepaper_projects = pipeline.discover_projects_for_analysis(link_types=['whitepaper'])
    print(f"Found {len(whitepaper_projects)} whitepapers ready for analysis")
    
    if len(whitepaper_projects) == 0:
        print("No whitepapers need analysis at this time.")
        return
    
    # Run analysis on first 20 whitepapers to start
    batch_size = 20
    print(f"Processing first {batch_size} whitepapers...")
    print(f"Estimated time: {batch_size * 5} minutes")
    print()
    
    stats = pipeline.run_analysis_batch(link_types=['whitepaper'], max_projects=batch_size)
    
    print("\n=== Whitepaper Analysis Results ===")
    print(f"Projects found: {stats['projects_found']}")
    print(f"Successful analyses: {stats['successful_analyses']}")
    print(f"Failed analyses: {stats['failed_analyses']}")
    print(f"Whitepapers analyzed: {stats['whitepapers_analyzed']}")
    
    if stats['projects_found'] > 0:
        success_rate = (stats['successful_analyses'] / stats['projects_found']) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    # Calculate remaining work
    remaining = len(whitepaper_projects) - stats['projects_found']
    print(f"Remaining whitepapers to analyze: {remaining}")
    
    if remaining > 0:
        print(f"\nTo continue processing, run this script again.")
        print(f"Estimated total time for all whitepapers: {remaining * 5 // 60} hours")

if __name__ == "__main__":
    main()