# pywb Replay Server Setup

This directory contains the Docker configuration for the **pywb** web archive replay server, which allows browsing historical snapshots of cryptocurrency project websites.

## 📋 Overview

**pywb** (Python Web Archive Toolkit) provides:
- Web-based replay of archived websites
- Time-travel browsing (view sites as they appeared at specific dates)
- CDX API for programmatic access
- Memento protocol support
- Full-text search capabilities

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│         User Browser                │
└─────────────┬───────────────────────┘
              │ http://localhost:8080
              ▼
┌─────────────────────────────────────┐
│      pywb Replay Server             │
│   (Docker Container)                │
└─────────────┬───────────────────────┘
              │
              ├─► /warcs/raw/   (WARC files)
              └─► /warcs/cdx/   (CDX indexes)
```

## 🚀 Quick Start

### 1. Prerequisites

- Docker Desktop installed and running
- WARC files generated via `trigger_crawl.py`
- CDX indexes created via `generate_cdx_indexes.py`

### 2. Start the Replay Server

```powershell
cd D:\Analytics\crypto-analytics\docker\pywb
docker-compose up -d
```

### 3. Access the UI

Open your browser to:
- **Replay UI:** http://localhost:8080
- **Collections:** http://localhost:8080/crypto_projects/

### 4. Browse Archives

Enter a URL to view archived versions:
```
http://localhost:8080/crypto_projects/*/https://bitcoin.org
```

This will show all available snapshots of bitcoin.org.

## 📂 Directory Structure

```
docker/pywb/
├── docker-compose.yml      # Docker service configuration
├── config.yaml             # pywb server configuration
├── init_collections.sh     # Collection initialization script
├── collections/            # pywb collections (auto-created)
└── README.md              # This file
```

## ⚙️ Configuration

### Collections

The default collection is `crypto_projects`, configured in `config.yaml`:

```yaml
collections:
  crypto_projects:
    index_paths:
      - /warcs/cdx/
    archive_paths:
      - /warcs/raw/
```

### Storage Mapping

The WARC storage directory is mounted read-only:

```yaml
volumes:
  - ../../data/warcs:/warcs:ro
```

This maps:
- `data/warcs/raw/` → `/warcs/raw/` (WARC files)
- `data/warcs/cdx/` → `/warcs/cdx/` (CDX indexes)

### Ports

- `8080` - Main replay UI
- `8081` - Admin UI (optional)

## 🎯 Usage Examples

### View Latest Snapshot

```
http://localhost:8080/crypto_projects/https://bitcoin.org
```

### View Specific Date

```
http://localhost:8080/crypto_projects/20250127/https://bitcoin.org
```

### View Specific Timestamp

```
http://localhost:8080/crypto_projects/20250127143000/https://bitcoin.org
```

Format: `YYYYMMDDHHmmss`

### Calendar View

```
http://localhost:8080/crypto_projects/*/https://bitcoin.org
```

Shows a calendar with all available snapshots.

## 🔍 CDX API

The CDX API allows programmatic access to archive metadata.

### Get All Snapshots

```powershell
curl "http://localhost:8080/crypto_projects/cdx?url=bitcoin.org&output=json"
```

### Filter by Date Range

```powershell
curl "http://localhost:8080/crypto_projects/cdx?url=bitcoin.org&from=20250101&to=20250131&output=json"
```

### Response Format

```json
[
  {
    "urlkey": "org,bitcoin)/",
    "timestamp": "20250127143000",
    "original": "https://bitcoin.org/",
    "mimetype": "text/html",
    "statuscode": "200",
    "digest": "sha256:abc123...",
    "length": "45678"
  }
]
```

## 🛠️ Management Commands

### Start Server

```powershell
docker-compose up -d
```

### Stop Server

```powershell
docker-compose down
```

### View Logs

```powershell
docker-compose logs -f
```

### Restart Server

```powershell
docker-compose restart
```

### Rebuild Container

```powershell
docker-compose up -d --build
```

### Initialize Collections

```bash
docker exec -it crypto_pywb_replay bash /webarchive/init_collections.sh
```

## 🔧 Troubleshooting

### No Archives Found

**Problem:** "No Captures found" message when browsing.

**Solutions:**
1. Verify WARC files exist:
   ```powershell
   ls data/warcs/raw/
   ```

2. Check CDX indexes:
   ```powershell
   ls data/warcs/cdx/
   ```

3. Generate indexes if missing:
   ```powershell
   python scripts/archival/generate_cdx_indexes.py --batch
   ```

4. Restart pywb:
   ```powershell
   docker-compose restart
   ```

### Container Won't Start

**Problem:** Docker container fails to start.

**Solutions:**
1. Check logs:
   ```powershell
   docker-compose logs
   ```

2. Verify port availability:
   ```powershell
   netstat -an | findstr "8080"
   ```

3. Check Docker status:
   ```powershell
   docker ps -a
   ```

### Slow Replay Performance

**Problem:** Archives load slowly.

**Solutions:**
1. Ensure CDX indexes are generated (see above)
2. Use local storage instead of network mounts
3. Increase Docker memory allocation
4. Check disk I/O performance

### Path Issues (Windows)

**Problem:** Volume mounting fails on Windows.

**Solutions:**
1. Use absolute paths in `docker-compose.yml`:
   ```yaml
   volumes:
     - D:/Analytics/crypto-analytics/data/warcs:/warcs:ro
   ```

2. Enable Docker Desktop file sharing for the drive
3. Verify paths in Docker Desktop settings

## 📊 Performance Tuning

### Memory Allocation

Increase Docker memory if handling large archives:

```yaml
services:
  pywb:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

### CDX Caching

pywb caches CDX data in memory. For large collections:

```yaml
environment:
  - PYWB_CDX_CACHE_SIZE=1000000
```

## 🔐 Security Considerations

### Read-Only Mounts

WARCs are mounted read-only to prevent accidental modification:

```yaml
volumes:
  - ../../data/warcs:/warcs:ro
```

### Network Isolation

For production, restrict access:

```yaml
ports:
  - "127.0.0.1:8080:8080"  # Localhost only
```

### CORS Configuration

Adjust CORS settings in `config.yaml`:

```yaml
cors:
  enabled: true
  origins: ['http://localhost:3000']  # Restrict origins
```

## 🌐 Integration

### Python Client

```python path=null start=null
import requests

# Get available snapshots
response = requests.get(
    "http://localhost:8080/crypto_projects/cdx",
    params={
        "url": "bitcoin.org",
        "output": "json"
    }
)
snapshots = response.json()

# Replay specific snapshot
timestamp = snapshots[0]["timestamp"]
replay_url = f"http://localhost:8080/crypto_projects/{timestamp}/https://bitcoin.org"
```

### Database Integration

Link pywb snapshots with database records:

```python path=null start=null
from src.database.manager import DatabaseManager
from src.models.archival_models import WebsiteSnapshot

db = DatabaseManager()
with db.session() as session:
    snapshot = session.query(WebsiteSnapshot).filter_by(
        snapshot_id=123
    ).first()
    
    # Generate replay URL
    timestamp = snapshot.snapshot_timestamp.strftime("%Y%m%d%H%M%S")
    replay_url = f"http://localhost:8080/crypto_projects/{timestamp}/{snapshot.base_url}"
    
    print(f"View archive: {replay_url}")
```

## 📚 Advanced Features

### Custom UI Branding

Edit `config.yaml`:

```yaml
ui:
  banner_html: "<h2>My Custom Archive</h2>"
  logo: "/static/logo.png"
```

### Proxy Mode

Browse the live web through pywb (records as you browse):

```
http://localhost:8080/crypto_projects/record/https://bitcoin.org
```

**Note:** Recording is disabled by default in our read-only configuration.

### Full-Text Search

If enabled, search across archive content:

```
http://localhost:8080/crypto_projects/search?q=blockchain
```

### Memento Protocol

Access archives via Memento TimeGate:

```
curl -H "Accept-Datetime: Mon, 27 Jan 2025 14:30:00 GMT" \
  http://localhost:8080/crypto_projects/timegate/https://bitcoin.org
```

## 🔗 Resources

- **pywb Documentation:** https://pywb.readthedocs.io/
- **Memento Protocol:** http://timetravel.mementoweb.org/
- **WARC Format:** https://iipc.github.io/warc-specifications/
- **CDX Format:** https://archive.org/web/researcher/cdx_file_format.php

## 📈 Monitoring

### Health Check

```powershell
curl http://localhost:8080/crypto_projects/
```

### Storage Usage

```powershell
# Check WARC storage
Get-ChildItem -Path data\warcs\raw -Recurse | 
  Measure-Object -Property Length -Sum | 
  Select-Object @{Name="TotalGB";Expression={$_.Sum / 1GB}}
```

### Collection Stats

```powershell
# Count total snapshots
(Get-ChildItem -Path data\warcs\raw -Filter "*.warc.gz").Count
```

## 🎓 Best Practices

1. **Always generate CDX indexes** before starting pywb for fast lookups
2. **Use read-only mounts** for production to prevent data corruption
3. **Monitor disk space** - WARC files accumulate quickly
4. **Regular backups** of both WARCs and CDX files
5. **Version control** your `config.yaml` changes

---

**Status:** Production Ready  
**Last Updated:** 2025-10-27  
**Version:** 1.0.0
