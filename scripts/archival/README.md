# Web Archival Scripts

Command-line tools for managing the web archival system.

## Available Scripts

### `trigger_crawl.py` - Manual Crawl Trigger

Manually trigger web archival crawls for crypto projects or arbitrary URLs.

**Features:**
- Crawl by project code
- Crawl arbitrary URLs
- Batch processing
- Multiple crawler engines
- Full database integration

**Usage:**

```powershell
# Basic crawl
python trigger_crawl.py --project BTC

# With options
python trigger_crawl.py --project ETH --engine browsertrix --max-pages 100 --max-depth 3

# Multiple projects
python trigger_crawl.py -p BTC -p ETH -p BNB

# Arbitrary URL
python trigger_crawl.py --url https://uniswap.org --max-pages 50

# Verbose output
python trigger_crawl.py --project BTC --verbose
```

**Arguments:**
- `--project, -p` : Project code (can be used multiple times)
- `--url, -u` : Arbitrary URL to crawl
- `--engine, -e` : Crawler engine (simple|browsertrix|brozzler)
- `--max-depth, -d` : Maximum crawl depth (default: 2)
- `--max-pages, -m` : Maximum pages (default: 50)
- `--storage` : Storage backend (local|s3|azure)
- `--verbose, -v` : Verbose output

**Examples:**

```powershell
# Development testing (small, fast)
python trigger_crawl.py --url https://bitcoin.org --max-pages 5

# Production crawl (comprehensive)
python trigger_crawl.py --project BTC --engine browsertrix --max-pages 500 --max-depth 4

# Batch crawl top projects
python trigger_crawl.py -p BTC -p ETH -p BNB -p ADA -p SOL

# S3 storage
python trigger_crawl.py --project ETH --storage s3
```

---

## Coming Soon

### `run_scheduled_crawls.py` - Scheduler Daemon
Run continuous crawl scheduling in daemon mode.

### `monitor_storage.py` - Storage Monitor
Monitor WARC storage usage and health.

### `compare_snapshots.py` - Snapshot Comparison
Compare two snapshots and generate diff reports.

### `view_snapshot.py` - Snapshot Viewer
Browse and inspect website snapshots.

### `manage_schedules.py` - Schedule Manager
Create and manage crawl schedules.

---

## Directory Structure

```
scripts/archival/
├── README.md                    # This file
├── trigger_crawl.py            # ✅ Manual crawl trigger
├── run_scheduled_crawls.py     # 🔄 Coming soon
├── monitor_storage.py          # 🔄 Coming soon
├── compare_snapshots.py        # 🔄 Coming soon
├── view_snapshot.py            # 🔄 Coming soon
└── manage_schedules.py         # 🔄 Coming soon
```

---

## Requirements

**Dependencies:**
```powershell
pip install -r requirements-archival.txt
```

**Database:**
```powershell
# Run migration first
alembic upgrade head
```

**Docker (for Browsertrix):**
```powershell
docker pull webrecorder/browsertrix-crawler:latest
```

---

## Environment Variables

Set these in your `.env` file or environment:

```env
DATABASE_URL=postgresql://crypto_user:password@localhost:5432/crypto_analytics

# Optional: S3 configuration
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=us-east-1
```

---

## Exit Codes

- `0` - Success
- `1` - Error (check logs)

---

## Logging

Logs are output to stderr with color coding:
- **GREEN** - Timestamp
- **INFO** - General information
- **SUCCESS** - Successful operations
- **WARNING** - Warnings
- **ERROR** - Errors

Use `--verbose` for debug-level logging.

---

## Database Integration

All crawls create records in:
- `crawl_jobs` - Job tracking
- `website_snapshots` - Version history
- `warc_files` - WARC metadata

Query examples in `docs/ARCHIVAL_STATUS.md`.

---

## Troubleshooting

### Project not found
```
ERROR | Project not found: XYZ
```
**Solution:** Check project code exists in database with correct spelling.

### No website URL
```
ERROR | No website URL found for Project Name
```
**Solution:** Project has no website link in `project_links` table.

### Docker error (Browsertrix)
```
ERROR | Browsertrix failed: docker: command not found
```
**Solution:** Use `--engine simple` or install Docker.

### Permission denied
```
ERROR | Permission denied: data/warcs/...
```
**Solution:** Ensure `data/warcs` directory exists and is writable.

---

## Best Practices

### For Testing
- Use `--max-pages 5 --max-depth 1`
- Use `--engine simple` (no Docker needed)
- Test with `--url` before projects

### For Production
- Use `--engine browsertrix` for JavaScript sites
- Set reasonable limits (max-pages 500)
- Use S3 storage for large-scale
- Monitor disk space regularly

### For Batch Processing
- Process in batches of 10-20
- Add delays between batches
- Monitor for failures
- Retry failed crawls

---

## Performance Tips

### Simple Crawler
- **Speed:** ~10 pages/minute
- **Use for:** Static HTML sites
- **CPU:** Low
- **Memory:** < 100 MB

### Browsertrix Crawler
- **Speed:** ~5 pages/minute (with JS rendering)
- **Use for:** SPAs, React, Vue sites
- **CPU:** High (browser rendering)
- **Memory:** 2-4 GB per instance

### Storage
- **Local:** Fast writes, limited capacity
- **S3:** Slower writes, unlimited capacity
- **Tip:** Start local, migrate to S3 when > 500 GB

---

## Integration Examples

### With Content Pipeline

```python
from scripts.archival.trigger_crawl import crawl_project
from models.database import DatabaseManager

db_manager = DatabaseManager(DATABASE_URL)

# Crawl project
success = crawl_project(
    db_manager,
    crawler,
    storage_manager,
    "BTC",
    engine="simple",
    max_depth=2,
    max_pages=50
)

if success:
    print("Crawl complete - ready for LLM analysis")
```

### Scheduled Crawls

```python
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

@scheduler.scheduled_job('cron', day_of_week='mon', hour=0)
def weekly_crawls():
    projects = ["BTC", "ETH", "BNB", "ADA", "SOL"]
    for project_code in projects:
        crawl_project(db_manager, crawler, storage_manager, project_code)

scheduler.start()
```

---

## Contributing

When adding new scripts:

1. Follow existing patterns
2. Add argparse CLI
3. Include `--verbose` flag
4. Log to stderr
5. Return meaningful exit codes
6. Update this README

---

**For More Information:**
- Full documentation: `docs/WEB_ARCHIVAL_IMPLEMENTATION_PLAN.md`
- Quick start guide: `docs/ARCHIVAL_QUICKSTART.md`
- Status and capabilities: `docs/ARCHIVAL_STATUS.md`
