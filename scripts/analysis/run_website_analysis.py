#!/usr/bin/env python3
"""
Website Analysis Batch Runner

This script processes cryptocurrency project websites in manageable batches,
analyzing technical depth, team information, value propositions, and project details.
"""

import os
import sys
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
    """Run website analysis in batches."""
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize pipeline with optimized settings for websites
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={
            'max_pages': 8,         # Limit pages per website for efficiency
            'max_depth': 2,         # Limit depth to avoid getting lost in sites
            'delay': 1.0            # Rate limiting between requests
        },
        analyzer_config={
            'provider': 'ollama', 
            'model': 'llama3.1:latest',    # High-quality model for comprehensive analysis
            'ollama_base_url': 'http://localhost:11434'
        }
    )
    
    print("=== Website Analysis ===")
    print("Starting website analysis batch...")
    
    # Check how many websites need analysis
    website_projects = pipeline.discover_projects_for_analysis(link_types=['website'])
    print(f"Found {len(website_projects)} websites ready for analysis")
    
    if len(website_projects) == 0:
        print("No websites need analysis at this time.")
        return
    
    # Run analysis on first 25 websites to start
    batch_size = 25
    print(f"Processing first {batch_size} websites...")
    print(f"Estimated time: {batch_size * 4} minutes")
    print()
    
    stats = pipeline.run_analysis_batch(link_types=['website'], max_projects=batch_size)
    
    print("\n=== Website Analysis Results ===")
    print(f"Projects found: {stats['projects_found']}")
    print(f"Successful analyses: {stats['successful_analyses']}")
    print(f"Failed analyses: {stats['failed_analyses']}")
    print(f"Websites analyzed: {stats['websites_analyzed']}")
    
    if stats['projects_found'] > 0:
        success_rate = (stats['successful_analyses'] / stats['projects_found']) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    # Calculate remaining work
    remaining = len(website_projects) - stats['projects_found']
    print(f"Remaining websites to analyze: {remaining}")
    
    if remaining > 0:
        print(f"\nTo continue processing, run this script again.")
        print(f"Estimated total time for all websites: {remaining * 4 // 60} hours")

if __name__ == "__main__":
    main()