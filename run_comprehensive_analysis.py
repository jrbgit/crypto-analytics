#!/usr/bin/env python3
"""
Comprehensive Analysis Runner

This script runs analysis across all content types (websites, Medium, whitepapers, Reddit)
using llama3.1:latest for the highest quality analysis.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.database import DatabaseManager
from src.pipelines.content_analysis_pipeline import ContentAnalysisPipeline
from dotenv import load_dotenv

# Load environment variables
config_path = Path(__file__).parent / "config" / "env"
load_dotenv(config_path)

def run_analysis_batch(content_type, pipeline, batch_size):
    """Run analysis for a specific content type."""
    print(f"\n{'='*20} {content_type.upper()} ANALYSIS {'='*20}")
    
    # Check how many items need analysis
    projects = pipeline.discover_projects_for_analysis(link_types=[content_type])
    print(f"Found {len(projects)} {content_type} items ready for analysis")
    
    if len(projects) == 0:
        print(f"No {content_type} items need analysis at this time.")
        return None
    
    print(f"Processing first {batch_size} {content_type} items...")
    
    # Run the analysis
    stats = pipeline.run_analysis_batch(link_types=[content_type], max_projects=batch_size)
    
    # Display results
    print(f"\n=== {content_type.upper()} ANALYSIS RESULTS ===")
    print(f"Projects found: {stats['projects_found']}")
    print(f"Successful analyses: {stats['successful_analyses']}")
    print(f"Failed analyses: {stats['failed_analyses']}")
    
    content_key = f"{content_type}s_analyzed" if content_type == 'website' else f"{content_type}_analyzed"
    analyzed_count = stats.get(content_key, 0)
    print(f"{content_type.title()} items analyzed: {analyzed_count}")
    
    if stats['projects_found'] > 0:
        success_rate = (stats['successful_analyses'] / stats['projects_found']) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    return stats

def main():
    """Run comprehensive analysis across all content types."""
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize pipeline with llama3.1:latest for all analysis
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={
            'max_pages': 8,         # Website pages
            'max_depth': 2,         # Website depth
            'max_articles': 15,     # Medium articles
            'max_posts': 50,        # Reddit posts
            'recent_days': 90,      # Content recency
            'timeout': 60,          # Request timeout
            'delay': 1.0            # Rate limiting
        },
        analyzer_config={
            'provider': 'ollama', 
            'model': 'llama3.1:latest',    # High-quality model for comprehensive analysis
            'ollama_base_url': 'http://localhost:11434'
        }
    )
    
    print("🚀 COMPREHENSIVE CRYPTO ANALYTICS PROCESSING")
    print("Using llama3.1:latest for high-quality analysis")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Define batch sizes for each content type (optimized for quality vs speed)
    batch_configs = [
        ('website', 30),      # Websites - good balance of speed and coverage
        ('whitepaper', 15),   # Whitepapers - slower due to PDF processing
        ('medium', 20),       # Medium - medium complexity
        ('reddit', 25),       # Reddit - community analysis
    ]
    
    total_stats = {
        'successful_analyses': 0,
        'failed_analyses': 0,
        'projects_found': 0
    }
    
    # Process each content type
    for content_type, batch_size in batch_configs:
        stats = run_analysis_batch(content_type, pipeline, batch_size)
        
        if stats:
            total_stats['successful_analyses'] += stats['successful_analyses']
            total_stats['failed_analyses'] += stats['failed_analyses']
            total_stats['projects_found'] += stats['projects_found']
        
        # Brief pause between content types
        if stats and stats['projects_found'] > 0:
            print(f"\nWaiting 30 seconds before processing next content type...")
            time.sleep(30)
    
    # Final summary
    print(f"\n{'='*60}")
    print("🎉 COMPREHENSIVE ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"Total projects processed: {total_stats['projects_found']}")
    print(f"Total successful analyses: {total_stats['successful_analyses']}")
    print(f"Total failed analyses: {total_stats['failed_analyses']}")
    
    if total_stats['projects_found'] > 0:
        overall_success_rate = (total_stats['successful_analyses'] / total_stats['projects_found']) * 100
        print(f"Overall success rate: {overall_success_rate:.1f}%")
    
    print(f"Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Show next steps
    print(f"\n📊 NEXT STEPS:")
    print(f"• Run 'python monitor_progress.py' to see updated statistics")
    print(f"• Run this script again to process more batches")
    print(f"• Check 'ANALYSIS_REPORT.md' for detailed findings")

if __name__ == "__main__":
    main()