#!/usr/bin/env python3
"""
Test Medium analysis pipeline setup
"""

import sys
import os
from pathlib import Path

# Add project root to path  
sys.path.insert(0, str(Path.cwd() / 'src'))

from models.database import DatabaseManager
from pipelines.content_analysis_pipeline import ContentAnalysisPipeline
from dotenv import load_dotenv

def main():
    # Load environment variables
    config_path = Path.cwd() / 'config' / 'env'
    load_dotenv(config_path)

    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)

    # Initialize pipeline with Medium-focused configuration
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={'max_articles': 15, 'recent_days': 60, 'delay': 2.0},
        analyzer_config={'provider': 'ollama', 'model': 'llama3.1:latest', 'ollama_base_url': 'http://localhost:11434'}
    )

    # Check how many Medium projects need analysis
    projects_waiting = pipeline.discover_projects_for_analysis(link_types=['medium'])
    total_medium = len(projects_waiting)

    print(f'Found {total_medium} Medium projects waiting for analysis.')

    if total_medium > 0:
        print(f'This will take approximately {total_medium * 2 // 60} minutes to complete.')
        print()
        print('First 10 examples:')
        for i, (project, link) in enumerate(projects_waiting[:10]):
            print(f'{i+1}. {project.name} ({project.code}): {link.url}')
    else:
        print('No Medium projects need analysis at this time.')

if __name__ == "__main__":
    main()