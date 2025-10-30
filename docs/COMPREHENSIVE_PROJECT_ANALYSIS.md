# Comprehensive Project Analysis

## Directory Overview

Project: `crypto-analytics` (Windows, PowerShell environment)

## Project Status

- Git Status: Clean working tree, synced with `origin/main`
- Last Major Commit: Web archival system with crawler improvements (2025-10-27)
- Docker: Not currently running
- Data Storage: ~90 MB in `data/`


## Core Architecture

### Technology Stack

- Python 3.10+ with SQLAlchemy 2.0 and PostgreSQL
- Ollama for local LLM inference
- Docker Compose infrastructure (Postgres, Redis, pgAdmin, Adminer)
- WARC-based web archival system

### Database

- Designed for PostgreSQL (currently Docker stopped)
- ~52K crypto projects, ~179K links tracked
- Comprehensive change tracking on all data updates
- Status logging for websites, whitepapers, Reddit


## Key Components

1. Data Collection Layer (`src/collectors/`)
   - LiveCoinWatch API: Primary data source (10K requests/day limit)
   - Rate limiting with retry logic and API usage tracking
   - Collects 52K+ crypto projects with market data & social links

2. Scrapers (`src/scrapers/`)
   - Website, whitepaper (PDF), Reddit, Medium, YouTube
   - Intelligent content extraction with fallback strategies
   - Respectful crawling with rate limiting

3. LLM Analysis (`src/analyzers/`)
   - Website, whitepaper, Reddit, Twitter, Telegram, Medium, YouTube analyzers
   - Structured output for technology, tokenomics, team, risks
   - Supports Ollama (local), OpenAI, Anthropic

4. Web Archival System (`src/archival/`) — 80% Complete
   - WARC 1.1 format storage with multi-backend support (Local / S3 / Azure)
   - Three crawler engines: Browsertrix (Docker + JS), Simple HTTP, Brozzler
   - Multi-level change detection (content / structure / resources / pages)
   - CDX indexing with SURT transformation
   - CLI tools for manual operations
   - Remaining: Replay UI (`pywb`), scheduling daemon, pipeline integration

5. Pipelines (`src/pipelines/`)
   - Content analysis pipeline: discovery → scraping → LLM → storage
   - Multi-stage processing with comprehensive error handling


## Database Schema (high level)

### Main Tables

- `crypto_projects` — Core project data (price, market cap, supply)
- `project_links` — Social/official links with status tracking
- `link_content_analysis` — LLM analysis results
- `website_status_log`, `whitepaper_status_log`, `reddit_status_log`
- `api_usage` — Rate limiting tracking

### Archival Tables

- `crawl_jobs`, `website_snapshots`, `warc_files`
- `cdx_records`, `snapshot_change_detection`, `crawl_schedules`


## Documentation (in `docs/`)

Comprehensive guides available:

- `WARP.md` — Commands, architecture, development notes
- `project_spec.md` — Original vision and data source catalog
- `ARCHIVAL_FINAL_SUMMARY.md` — Web archival implementation (large document)
- `DATABASE_MIGRATION_GUIDE.md` — SQLite → PostgreSQL migration
- API integration guides (Reddit, Twitter, YouTube, Google Drive)
- Performance analysis and optimization guides


## Current Configuration

### Environment

- Config templates: `config/.env.example`
- PostgreSQL database URL configured via environment
- API keys required: LiveCoinWatch, OpenAI, Reddit, Twitter, Telegram, YouTube
- Ollama base URL: `http://localhost:11434`

### Docker Services (when running)

- `postgres:5432`, `redis:6379`
- `adminer:8080`, `pgadmin:5050`
- Automated backups configured


## Testing & Quality

- Code quality tools: `pytest`, `black`, `flake8`, `mypy`
- Test coverage exists for: DB connection, URL filtering, Reddit pipeline, YouTube implementation


## Commands (from `docs/WARP.md`)

Run in PowerShell (example):

```powershell
# Start Postgres and Redis via docker-compose
docker-compose up -d postgres redis

# Run the LiveCoinWatch collector
python src/collectors/livecoinwatch.py
```


## Next Steps / How to get running

1. Start Docker services:

```powershell
docker-compose up -d postgres redis
```

2. Configure environment: copy `config/.env.example` → `.env` and add API keys
3. Initialize/migrate the database (see `db_init/` and `migrations/`)
4. Start data collection:

```powershell
python src/collectors/livecoinwatch.py
```


## Archival System Completion Roadmap (est. 2–3 weeks)

- Phase 5: pywb replay infrastructure
- Phase 6: APScheduler automation
- Phase 7: Pipeline integration
- Phase 8: Monitoring dashboard


## Summary

A sophisticated crypto analytics platform with multi-source data collection, LLM-powered analysis, and industry-standard web archival. The database is not currently running; the web archival system is production-ready for manual operations but automation and replay integration are pending.
