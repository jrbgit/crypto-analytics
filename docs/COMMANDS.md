# Crypto Analytics Commands Reference

Complete reference for all commands available in the crypto-analytics project.

---

## Table of Contents

1. [Quick Start Commands](#quick-start-commands)
2. [Data Collection](#data-collection)
3. [Content Analysis](#content-analysis)
4. [Progress Monitoring](#progress-monitoring)
5. [Batch Processing Commands](#batch-processing-commands)
6. [Database Management](#database-management)
7. [Archival System](#archival-system)
8. [Development & Testing](#development--testing)
9. [Utilities](#utilities)

---

## Quick Start Commands

### View Current Progress
```powershell
python scripts/analysis/monitor_progress.py
```
Monitor the current state of all analysis types with statistics and completion percentages.

### Comprehensive Analysis (All Content Types)
```powershell
python scripts/analysis/run_comprehensive_analysis.py
```
Runs analysis across all content types (websites, Medium, whitepapers, Reddit, YouTube).

---

## Data Collection

### LiveCoinWatch Data Collection

**Command:**
```powershell
python src/collectors/livecoinwatch.py [OPTIONS]
```

**Description:**
Collects cryptocurrency project data from LiveCoinWatch API including:
- Market data (price, market cap, volume)
- Project metadata (name, code, rank)
- Social media links
- Project images

**Options:**
- `--all` - Collect all available cryptocurrencies instead of just top coins
- `--limit <number>` - Maximum number of coins to collect (default: 100)
- `--max-coins <number>` - Maximum coins when using `--all` flag
- `--offset <number>` - Starting offset for collection, useful for resuming (default: 0)

**Default Batch Sizes:**
- Batch size: 100 coins per API request (LiveCoinWatch API limit)
- Default collection: Top 100 coins by market cap
- Rate limit buffer: Stops when 10 or fewer API calls remain

**Examples:**
```powershell
# Collect top 100 cryptocurrencies (default)
python src/collectors/livecoinwatch.py

# Collect top 500 cryptocurrencies
python src/collectors/livecoinwatch.py --limit 500

# Collect all available cryptocurrencies
python src/collectors/livecoinwatch.py --all

# Collect up to 1000 coins from all available
python src/collectors/livecoinwatch.py --all --max-coins 1000

# Resume collection from offset 2000
python src/collectors/livecoinwatch.py --all --offset 2000

# Collect top 200, starting from offset 100
python src/collectors/livecoinwatch.py --limit 200 --offset 100
```

**Features:**
- Rate limiting (10,000 requests/day)
- Automatic retry logic
- Change tracking for all data fields
- Progress updates every 10 batches
- Graceful handling of rate limit exhaustion
- Supports 52,000+ crypto projects
- Database sanitization for large numeric values
- Duplicate detection and update handling

**Output Includes:**
- Total projects collected
- API calls used in session
- API calls remaining for the day
- Sample of collected projects

**Note:** Requires `LIVECOINWATCH_API_KEY` in `config/.env`

---

## Content Analysis

### Comprehensive Analysis Pipeline

**Command:**
```powershell
python scripts/analysis/run_comprehensive_analysis.py [OPTIONS]
```

**Options:**
- `--disable <types>` - Comma-separated list of analysis types to disable
  - Types: `website`, `whitepaper`, `medium`, `reddit`, `youtube`
- `--enable <types>` - Comma-separated list of analysis types to enable (mutually exclusive with --disable)
- `--batch-size <type>=<number>` - Set custom batch sizes (e.g., `website=50,reddit=30`)
- `--list-types` - List available analysis types and exit

**Default Batch Sizes:**
- Websites: 30
- Whitepapers: 15
- Medium: 8
- Reddit: 25
- YouTube: 20

**Examples:**
```powershell
# Run all analysis types
python scripts/analysis/run_comprehensive_analysis.py

# Skip reddit and website analysis
python scripts/analysis/run_comprehensive_analysis.py --disable reddit,website

# Only run whitepaper and medium analysis
python scripts/analysis/run_comprehensive_analysis.py --enable whitepaper,medium

# Skip medium, use 50 websites per batch
python scripts/analysis/run_comprehensive_analysis.py --disable medium --batch-size website=50
```

**Features:**
- Graceful interrupt handling (Ctrl+C)
- Progress saving and resume capability
- Automatic rate limiting
- Error reporting

---

### Website Analysis

**Command:**
```powershell
python scripts/analysis/run_website_analysis.py
```

**Description:**
Analyzes cryptocurrency project websites for:
- Technology stack
- Core features
- Value proposition
- Team information
- Technical depth
- Content quality

**Default Configuration:**
- Batch size: 25 websites
- Max pages per site: 8
- Max depth: 2
- Model: llama3.1:latest

---

### Whitepaper Analysis

**Command:**
```powershell
python scripts/analysis/run_whitepaper_analysis.py
```

**Description:**
Analyzes project whitepapers (PDF and web formats) for:
- Technical specifications
- Tokenomics
- Use cases
- Innovation level
- Roadmap items

**Features:**
- PDF parsing
- Web-based whitepaper support
- Google Drive integration

---

### Medium Content Analysis

**Commands:**
```powershell
# Standard batch
python scripts/analysis/run_medium_analysis.py

# Limited batch (smaller)
python scripts/analysis/run_medium_limited.py
```

**Description:**
Analyzes Medium blog posts and articles for:
- Content themes
- Project updates
- Community engagement
- Writing quality

**Rate Limiting:**
- Reduced batch sizes to avoid 429 errors
- 5-minute delay between batches
- Conservative request timing

---

### Reddit Analysis

**Command:**
```powershell
python scripts/analysis/run_reddit_analysis.py
```

**Description:**
Analyzes Reddit communities for:
- Sentiment analysis
- Community activity
- Discussion topics
- Engagement metrics

**Features:**
- Post scraping (up to 50 posts)
- Content recency filtering (90 days)
- Error tracking

**Note:** Requires Reddit API credentials in `config/.env`

---

### Twitter Analysis

**Command:**
```powershell
python src/analyzers/twitter_analyzer.py batch <limit>
```

**Arguments:**
- `<limit>` - Number of Twitter accounts to analyze

**Description:**
Analyzes Twitter accounts for:
- Authenticity score
- Professional score
- Community engagement
- Activity metrics
- Account health status

**Metrics:**
- Follower/following ratio
- Tweets per day
- Verification status
- Profile completeness

**API Usage:**
- 100 calls per month (Twitter API Free Tier)
- Prioritizes high-value projects (Top 100 or $1B+ market cap)

**Examples:**
```powershell
# Analyze 1 Twitter account
python src/analyzers/twitter_analyzer.py batch 1

# Analyze 5 Twitter accounts
python src/analyzers/twitter_analyzer.py batch 5
```

**Note:** Requires `TWITTER_BEARER_TOKEN` in `config/.env`

---

### Telegram Analysis

**Command:**
```powershell
python src/analyzers/telegram_analyzer.py batch <limit>
```

**Arguments:**
- `<limit>` - Number of Telegram channels to analyze

**Description:**
Analyzes Telegram channels for:
- Authenticity score
- Community size and engagement
- Content quality
- Activity level
- Security features
- Channel health status

**Metrics:**
- Member count
- Channel type (channel, group, supergroup)
- Username presence
- Protected content settings
- Anti-spam features

**Rate Limiting:**
- Conservative 20 calls/minute
- Automatic rate limit handling
- Error tracking for private/deleted channels

**Examples:**
```powershell
# Analyze 3 Telegram channels
python src/analyzers/telegram_analyzer.py batch 3

# Analyze 10 Telegram channels
python src/analyzers/telegram_analyzer.py batch 10
```

**Note:** Requires `TELEGRAM_BOT_TOKEN` in `config/.env`

---

### YouTube Analysis

**Command:**
```powershell
python scripts/analysis/test_youtube_integration.py
```

**Description:**
Analyzes YouTube channels for:
- Channel metrics
- Video content
- Subscriber count
- Upload frequency
- Engagement statistics

**Note:** Requires YouTube API credentials and OAuth setup

---

## Progress Monitoring

### Monitor Analysis Progress

**Command:**
```powershell
python scripts/analysis/monitor_progress.py
```

**Output Includes:**
- Total projects in database
- Content links status (by type)
- Completion percentages
- Remaining work
- Recent analysis activity (last 24 hours)
- Analysis quality metrics
- Estimated completion times
- Twitter API usage statistics
- Telegram API usage statistics
- High-priority project analysis status

**Content Types Tracked:**
- Websites
- Reddit
- Medium
- Whitepapers
- YouTube
- Twitter
- Telegram

---

### Analyze Filtering Impact

**Command:**
```powershell
python scripts/analysis/analyze_filtering_impact.py
```

**Description:**
Analyzes the impact of URL filtering on content analysis results.

---

## Batch Processing Commands

These PowerShell loop commands are designed for continuous processing of specific content types.

### YouTube Continuous Processing
```powershell
while ($true) {
    Start-Sleep 100
    python scripts/analysis/run_comprehensive_analysis.py --disable medium,reddit,website,whitepaper
    Start-Sleep 6600
}
```
Processes YouTube content with delays to respect rate limits.

---

### Reddit Continuous Processing
```powershell
while ($true) {
    python scripts/analysis/run_comprehensive_analysis.py --disable medium,website,whitepaper,youtube
    Start-Sleep 600
}
```
Processes Reddit content every 10 minutes.

---

### Telegram Continuous Processing
```powershell
while ($true) {
    python src/analyzers/telegram_analyzer.py batch 3
    Start-Sleep 3600
}
```
Processes 3 Telegram channels per hour.

---

### Medium Continuous Processing
```powershell
while ($true) {
    Start-Sleep 14400
    python scripts/analysis/run_comprehensive_analysis.py --disable reddit,website,whitepaper,youtube
}
```
Processes Medium content with 4-hour initial delay to avoid rate limits.

---

### Website Continuous Processing
```powershell
while ($true) {
    python scripts/analysis/run_comprehensive_analysis.py --disable medium,reddit,whitepaper,youtube
    Start-Sleep 10
}
```
Processes websites with minimal delay between batches.

---

### Whitepaper Continuous Processing
```powershell
while ($true) {
    python scripts/analysis/run_comprehensive_analysis.py --disable medium,reddit,website,youtube
    Start-Sleep 5
}
```
Processes whitepapers with short delay between batches.

---

### Twitter Continuous Processing
```powershell
while ($true) {
    python src/analyzers/twitter_analyzer.py batch 1
    Start-Sleep 900
}
```
Processes 1 Twitter account every 15 minutes (conservative rate limiting).

---

## Database Management

### Initialize Database

**Command:**
```powershell
python src/models/init_db.py
```

**Description:**
Creates all database tables with proper schema. Run this on first setup or after major schema changes.

**Tables Created:**
- `crypto_projects` - Core project data
- `project_links` - Social media and official links
- `project_images` - Project logos/icons
- `project_changes` - Historical change tracking
- `link_content_analysis` - LLM analysis results
- `website_status_log` - Website scraping status
- `whitepaper_status_log` - Whitepaper analysis status
- `reddit_status_log` - Reddit scraping status
- `api_usage` - API usage tracking

---

### Database Migrations

**Apply Migrations:**
```powershell
alembic upgrade head
```

**Create New Migration:**
```powershell
alembic revision --autogenerate -m "Description of changes"
```

**Rollback Migration:**
```powershell
alembic downgrade -1
```

**View Migration History:**
```powershell
alembic history
```

---

### Database Schema Management

**Check Schema:**
```powershell
python scripts/check_db_schema.py
```

**Migrate Schema (Various versions):**
```powershell
python scripts/migrate_database_schema.py
python scripts/migrate_database_schema_v2.py
python scripts/migrate_database_schema_v3.py
```

**Specific Migrations:**
```powershell
python scripts/migrate_reddit_status_columns.py
python scripts/migrate_reddit_status_log_table.py
```

---

### Database Maintenance

**Wipe Database (Direct):**
```powershell
python scripts/wipe_database_direct.py
```
⚠️ **WARNING:** Deletes all data from database.

**Wipe Database (Truncate):**
```powershell
python scripts/wipe_database_truncate.py
```
⚠️ **WARNING:** Truncates all tables.

---

### Database Verification

**Check Database:**
```powershell
python scripts/utils/check_db.py
```

**Check Tables:**
```powershell
python scripts/utils/check_tables.py
```

**Verify PostgreSQL:**
```powershell
python scripts/utils/verify_postgresql.py
```

**Check Reddit Status:**
```powershell
python scripts/utils/check_reddit_status.py
```

---

### Reset Failed Projects

**Command:**
```powershell
python scripts/utils/reset_failed_projects.py [OPTIONS]
```

**Options:**
- `--link-type <type>` - Specific link type to reset (e.g., website, reddit)
- `--dry-run` - Show what would be reset without making changes
- `--all` - Reset all failed projects
- `--days <number>` - Only reset projects that failed more than N days ago

**Examples:**
```powershell
# Reset failed website analyses (dry run)
python scripts/utils/reset_failed_projects.py --link-type website --dry-run

# Reset all failed analyses older than 7 days
python scripts/utils/reset_failed_projects.py --all --days 7
```

---

## Archival System

The archival system captures and stores historical snapshots of cryptocurrency project websites.

### Trigger Crawl

**Command:**
```powershell
python scripts/archival/trigger_crawl.py [OPTIONS]
```

**Options:**
- `--project <code>` - Project code to crawl
- `--engine <type>` - Crawl engine: `simple` or `playwright` (default: simple)
- `--max-pages <number>` - Maximum pages to crawl (default: 50)
- `--max-depth <number>` - Maximum crawl depth (default: 3)
- `--timeout <seconds>` - Request timeout (default: 30)

**Examples:**
```powershell
# Crawl Bitcoin project website
python scripts/archival/trigger_crawl.py --project BTC --engine simple --max-pages 50

# Deep crawl with Playwright
python scripts/archival/trigger_crawl.py --project ETH --engine playwright --max-depth 4
```

---

### Integration with Analysis Pipeline

**Command:**
```powershell
python scripts/archival/integrate_with_pipeline.py [OPTIONS]
```

**Actions:**
- `crawl-recent` - Crawl recently analyzed websites
- `check-changes` - Check for website changes and trigger reanalysis
- `create-schedules` - Create automated crawl schedules

**Options:**
- `--action <action>` - Action to perform
- `--days <number>` - Number of days to look back (default: 30)
- `--limit <number>` - Maximum number of projects to process (default: 10)
- `--threshold <float>` - Change detection threshold (0.0-1.0, default: 0.3)
- `--dry-run` - Simulate without making actual changes

**Examples:**
```powershell
# Crawl websites analyzed in last 30 days (dry run)
python scripts/archival/integrate_with_pipeline.py --action crawl-recent --days 30 --limit 10 --dry-run

# Check for significant changes
python scripts/archival/integrate_with_pipeline.py --action check-changes --threshold 0.3 --days 30 --limit 10 --dry-run

# Create crawl schedules for top 100 projects
python scripts/archival/integrate_with_pipeline.py --action create-schedules --limit 100 --dry-run
```

---

### Monitor Archival System

**Command:**
```powershell
python scripts/archival/monitor_archival.py [OPTIONS]
```

**Options:**
- `--days <number>` - Number of days of history to show (default: 30)
- `--show-errors` - Show detailed error information
- `--show-jobs` - Show crawl job details
- `--show-changes` - Show detected website changes
- `--project <code>` - Filter by specific project code

**Examples:**
```powershell
# View archival status for last 30 days
python scripts/archival/monitor_archival.py

# Show errors and job details
python scripts/archival/monitor_archival.py --show-errors --show-jobs

# Monitor specific project
python scripts/archival/monitor_archival.py --project BTC --show-changes
```

---

### Check Archival Status

**Command:**
```powershell
python scripts/archival/check_status.py
```

**Description:**
Quick overview of archival system status including snapshot counts and recent activity.

---

### Generate CDX Indexes

**Command:**
```powershell
python scripts/archival/generate_cdx_indexes.py [OPTIONS]
```

**Options:**
- `--project <code>` - Generate index for specific project
- `--all` - Generate indexes for all projects
- `--rebuild` - Rebuild existing indexes
- `--output-dir <path>` - Output directory for CDX files

**Description:**
Generates CDX (Capture Index) files for archived web content, useful for Wayback Machine-style browsing.

---

### Run Archival Scheduler

**Command:**
```powershell
python scripts/archival/run_scheduler.py [OPTIONS]
```

**Options:**
- `--interval <minutes>` - Check interval in minutes (default: 60)
- `--daemon` - Run as background daemon
- `--max-concurrent <number>` - Maximum concurrent crawls (default: 3)

**Description:**
Runs automated scheduler for periodic website crawling based on configured schedules.

---

## Development & Testing

### Linting

**Run All Linters:**
```powershell
python scripts/dev/lint.py
```

**Individual Linters:**
```powershell
# Flake8
flake8 src/

# Black (format check)
black --check src/

# Black (auto-format)
black src/
```

---

### Type Checking

**Check Types:**
```powershell
python scripts/dev/check_types.py
```

**Or directly:**
```powershell
mypy src/
```

**Fix Type Errors:**
```powershell
python scripts/dev/fix_type_errors.py
```

---

### Testing

**Run All Tests:**
```powershell
pytest tests/
```

**Run with Coverage:**
```powershell
pytest --cov=src tests/
```

**Test Specific Module:**
```powershell
pytest tests/test_specific_module.py
```

---

### Integration Testing

**Test Twitter Integration:**
```powershell
python scripts/analysis/test_twitter_integration.py
```

**Test Telegram Integration:**
```powershell
python scripts/analysis/test_telegram_integration.py
```

**Test Reddit Errors:**
```powershell
python scripts/dev/test_reddit_errors.py
```

---

### Development Setup

**Initial Setup:**
```powershell
python scripts/dev/setup.py
```

**Description:**
Sets up development environment including dependencies and pre-commit hooks.

---

## Utilities

### YouTube OAuth Setup

**Command:**
```powershell
python scripts/setup_youtube_oauth.py
```

**Description:**
Interactive setup for YouTube API OAuth authentication.

---

### Twitter Prioritization Strategy

**Command:**
```powershell
python scripts/analysis/twitter_prioritization_strategy.py
```

**Description:**
Analyzes and displays the strategy for prioritizing Twitter account analysis based on project importance.

---

### Migration Utilities

**Complete Migration:**
```powershell
python scripts/migration/complete_migration.py
```

**Fix Sequences:**
```powershell
python scripts/migration/fix_sequences.py
```

**Migrate Field Lengths:**
```powershell
python scripts/migration/migrate_field_lengths.py
```

**Migrate to PostgreSQL:**
```powershell
python scripts/migration/migrate_to_postgresql.py
```

**Migrate Whitepaper Status Tracking:**
```powershell
python scripts/migration/migrate_whitepaper_status_tracking.py
```

**Quick Migrate:**
```powershell
python scripts/migration/quick_migrate.py
```

---

## Docker Services

### Start Database
```powershell
docker-compose up -d postgres
```

### Start All Services (with Admin Tools)
```powershell
docker-compose --profile admin up -d
```

### Stop Services
```powershell
docker-compose down
```

### View Logs
```powershell
docker-compose logs -f postgres
```

### Services Included:
- **postgres** (port 5432) - Main PostgreSQL database
- **redis** (port 6379) - Caching layer
- **adminer** (port 8080) - Database admin UI
- **pgadmin** (port 5050) - PostgreSQL admin
- **postgres_backup** - Automated daily backups

---

## Environment Variables

Key environment variables needed in `config/.env`:

```env
# Database
DATABASE_URL=postgresql://crypto_user:password@localhost:5432/crypto_analytics

# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:latest

# API Keys
LIVECOINWATCH_API_KEY=your_api_key_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret
YOUTUBE_API_KEY=your_youtube_key
```

---

## Command Categories Summary

| Category | Primary Commands |
|----------|------------------|
| **Data Collection** | `livecoinwatch.py` |
| **Analysis** | `run_comprehensive_analysis.py`, `run_website_analysis.py`, `twitter_analyzer.py`, `telegram_analyzer.py` |
| **Monitoring** | `monitor_progress.py`, `monitor_archival.py` |
| **Database** | `init_db.py`, `alembic`, migration scripts |
| **Archival** | `trigger_crawl.py`, `integrate_with_pipeline.py` |
| **Development** | `lint.py`, `check_types.py`, `pytest` |

---

## Additional Resources

- **README.md** - Project overview and quick start
- **docs/DATABASE_MIGRATION_GUIDE.md** - Database schema details
- **docs/ANALYSIS_REPORT.md** - Analysis findings
- **docs/PERFORMANCE_ANALYSIS.md** - Performance optimization
- **docs/livecoinwatch_api.md** - LiveCoinWatch API documentation
- **docs/REDDIT_API_NOTES.md** - Reddit integration guide
- **docs/twitter_integration_guide.md** - Twitter API setup
- **docs/YOUTUBE_API_SETUP.md** - YouTube OAuth configuration

---

*Last Updated: 2025-10-31*
