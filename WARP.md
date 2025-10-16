# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Commands

### Environment Setup
```powershell
# Install Python dependencies
pip install -r requirements.txt

# Set up environment variables
# Copy config/env to .env and configure API keys and database credentials
```

### Database Operations
```powershell
# Start database services
docker-compose up postgres redis

# Initialize database schema
python src/models/init_db.py

# Database administration (optional)
docker-compose --profile admin up pgadmin  # Access at http://localhost:5050
docker-compose --profile admin up adminer  # Access at http://localhost:8080

# Database migrations
python migrate_to_postgresql.py
python complete_migration.py
```

### Data Collection
```powershell
# Collect cryptocurrency data from LiveCoinWatch
python src/collectors/livecoinwatch.py

# Run comprehensive analysis pipeline
python run_comprehensive_analysis.py

# Specific content analysis tasks
python run_website_analysis.py      # Analyze project websites
python run_whitepaper_analysis.py   # Analyze whitepapers
python run_medium_analysis.py       # Analyze Medium articles
python run_reddit_analysis.py       # Analyze Reddit discussions
```

### Testing and Quality
```powershell
# Run tests
pytest tests/                    # Run all tests
pytest test_pg_connection.py    # Test database connection
pytest test_url_filtering.py    # Test URL filtering logic
pytest test_reddit_pipeline.py  # Test Reddit analysis pipeline

# Code quality
black src/                       # Format code
flake8 src/                     # Lint code
mypy src/                       # Type checking
```

## Architecture

### Core Components

**Data Collection Layer**
- `src/collectors/`: API clients for external data sources (LiveCoinWatch primary)
- Rate limiting, error handling, and API usage tracking
- Change detection and historical data preservation

**Storage Layer** 
- `src/models/database.py`: SQLAlchemy models with comprehensive change tracking
- PostgreSQL with Redis caching for performance
- Handles cryptocurrency market data, project metadata, and analysis results

**Content Analysis Pipeline**
- `src/pipelines/content_analysis_pipeline.py`: Orchestrates complete analysis workflow
- Multi-stage processing: discovery → scraping → LLM analysis → storage
- Supports websites, whitepapers, Medium articles, and Reddit discussions

**Scraping Infrastructure**
- `src/scrapers/`: Specialized scrapers for different content types
- Intelligent content extraction with fallback strategies
- Rate limiting and respectful crawling practices

**LLM Analysis Engine**
- `src/analyzers/`: Content analysis using local Ollama or cloud LLMs
- Structured output with comprehensive project assessment
- Support for multiple model providers (OpenAI, Anthropic, Ollama)

**Utilities and Services**
- `src/services/`: Background services and logging
- `src/utils/`: URL filtering, content processing utilities

### Database Schema

Key tables for development:
- `crypto_projects`: Main project data with market information
- `project_links`: URLs for websites, whitepapers, social media
- `link_content_analysis`: LLM analysis results with structured insights
- `project_changes`: Complete change history for all data updates

### Analysis Pipeline Flow

1. **Discovery**: Identify projects needing analysis based on market cap, recency
2. **Content Scraping**: Extract text from websites/documents with error handling
3. **LLM Processing**: Analyze content for technology, team, tokenomics, risks
4. **Storage**: Save structured results with change tracking
5. **Monitoring**: Track API usage, success rates, and analysis quality

## Development Notes

### Environment Configuration
- Main config in `config/env` (copy to `.env`)
- Database credentials, API keys (LiveCoinWatch, OpenAI, etc.)
- LLM provider settings (Ollama recommended for local development)

### Database Management
- Uses PostgreSQL for production with comprehensive indexing
- Change tracking on all major data updates
- Migration scripts in root directory for schema updates
- Backup strategies configured in docker-compose

### Content Analysis Strategy
- Prioritizes high market cap projects for analysis
- Implements respectful rate limiting for all external services  
- Comprehensive error handling and retry logic
- Structured LLM prompts for consistent analysis quality

### Performance Considerations
- Redis caching for frequently accessed data
- Batch processing for large-scale analysis
- Configurable concurrency limits
- Database query optimization for large datasets

### Testing Strategy
- Individual component tests for scrapers and analyzers
- Database connection and migration testing
- URL filtering validation
- Pipeline integration testing