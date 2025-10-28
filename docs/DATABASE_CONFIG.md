# Database Configuration

## Overview

All archival scripts now automatically load database configuration from `config/.env`.

## Configuration File

The database connection is configured in `config/.env`:

```env
DATABASE_URL=postgresql://crypto_user:crypto_secure_password_2024@localhost:5432/crypto_analytics
```

## Docker PostgreSQL

The PostgreSQL database runs in a Docker container named `crypto_analytics_db` and is accessible on `localhost:5432`.

### Check Database Status

```powershell
# Check if container is running
docker ps --filter "name=crypto_analytics_db"

# Start the database
docker-compose up -d crypto_analytics_db

# Stop the database
docker-compose stop crypto_analytics_db
```

## Updated Scripts

All the following scripts now automatically load `DATABASE_URL` from `config/.env`:

1. **scripts/archival/monitor_archival.py** - Monitoring dashboard
2. **scripts/archival/generate_cdx_indexes.py** - CDX index generation
3. **scripts/archival/trigger_crawl.py** - Manual crawl triggering
4. **scripts/archival/run_scheduler.py** - Automated scheduler daemon

## Usage

No command-line database arguments are needed anymore. Simply run:

```bash
# Monitor archival system
python scripts/archival/monitor_archival.py --dashboard

# Generate CDX indexes
python scripts/archival/generate_cdx_indexes.py --batch --limit 100

# Trigger a crawl
python scripts/archival/trigger_crawl.py --project BTC

# Run scheduler (removed --database-url argument)
python scripts/archival/run_scheduler.py
```

## Dependencies

Make sure `python-dotenv` is installed:

```bash
pip install python-dotenv
```

## Troubleshooting

### Database Connection Refused

If you see connection errors:

1. Check if Docker container is running:
   ```powershell
   docker ps | Select-String "crypto_analytics_db"
   ```

2. Start the database:
   ```powershell
   docker-compose up -d crypto_analytics_db
   ```

3. Verify DATABASE_URL in `config/.env` matches the container port (5432)

### Environment Variable Not Found

If you see "DATABASE_URL not found in environment":

1. Verify `config/.env` exists and contains DATABASE_URL
2. Check file encoding (should be UTF-8)
3. Ensure no syntax errors in the .env file

## Changes Made

- Added `from dotenv import load_dotenv` to all archival scripts
- Scripts now load environment from `config/.env` automatically
- Removed hardcoded database URL fallbacks
- Removed `--database-url` CLI argument from run_scheduler.py
- Added validation to ensure DATABASE_URL is present before connecting
