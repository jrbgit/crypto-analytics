#!/usr/bin/env python3
"""
Test script for Reddit analysis pipeline - processes a small batch of projects
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.path_utils import setup_project_paths, get_config_path

# Set up project paths
project_root = setup_project_paths()

from src.models.database import DatabaseManager
from src.pipelines.content_analysis_pipeline import ContentAnalysisPipeline
from dotenv import load_dotenv
from loguru import logger

def main():
    # Load environment variables
    load_dotenv(get_config_path() / ".env")
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize pipeline
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={'max_pages': 5, 'max_depth': 2, 'delay': 1.0, 'timeout': 30},
        analyzer_config={'provider': 'ollama', 'model': 'llama3.1:latest', 'ollama_base_url': 'http://localhost:11434'}
    )
    
    # Get only Reddit projects for testing
    projects_waiting = pipeline.discover_projects_for_analysis(link_types=['reddit'], limit=5)
    total_projects = len(projects_waiting)
    
    if total_projects == 0:
        print("No Reddit projects are waiting for content analysis.")
        return
    
    print(f"Found {total_projects} Reddit projects for testing.")
    
    # Run analysis on limited projects
    logger.info(f"Running Reddit analysis pipeline on {total_projects} projects")
    stats = pipeline.run_analysis_batch(max_projects=5, link_types=['reddit'])
    
    print(f"\n=== Reddit Analysis Test Results ===")
    print(f"Projects found: {stats['projects_found']}")
    print(f"Successful analyses: {stats['successful_analyses']}")
    print(f"Failed analyses: {stats['failed_analyses']}")
    print(f"Reddit communities analyzed: {stats['reddit_analyzed']}")
    print(f"Success rate: {stats['successful_analyses']/stats['projects_found']*100:.1f}%" if stats['projects_found'] > 0 else "N/A")

if __name__ == "__main__":
    main()