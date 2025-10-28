# Web Archival System Implementation Plan

## Overview

This document outlines the complete plan for adding web archival and versioning capabilities to the crypto analytics platform. The system will crawl, store, archive, version, and enable replay of cryptocurrency project websites using industry-standard WARC format.

---

## 1. Architecture Overview

### 1.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                     Crypto Analytics Platform                    │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Web Archival System (New)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  Crawl         │  │   Storage      │  │  Versioning &    │  │
│  │  Scheduler     │→ │   Manager      │→ │  Change          │  │
│  │                │  │   (WARC)       │  │  Detection       │  │
│  └────────────────┘  └────────────────┘  └──────────────────┘  │
│          │                    │                    │             │
│          ▼                    ▼                    ▼             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  Brozzler/     │  │   CDX Index    │  │  Replay UI       │  │
│  │  Heritrix      │  │   Generator    │  │  (pywb)          │  │
│  │  Wrapper       │  │                │  │                  │  │
│  └────────────────┘  └────────────────┘  └──────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                           │
│  • crawl_jobs         • website_snapshots                        │
│  • warc_files         • snapshot_change_detection                │
│  • cdx_records        • crawl_schedules                          │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Crawl Scheduler** | Manages timing and prioritization of crawls | Python, APScheduler |
| **Archival Crawler** | Executes crawls with JS rendering | Brozzler (primary), Heritrix (fallback) |
| **WARC Storage Manager** | Stores and manages WARC files | Local FS / S3 + warcio |
| **CDX Indexer** | Creates fast lookup indexes | cdxj-indexer / pywb |
| **Change Detector** | Compares snapshots, detects diffs | difflib, BeautifulSoup |
| **Replay Server** | Browse historical snapshots | pywb |
| **Integration Layer** | Connects to existing pipeline | Custom Python |

---

## 2. Database Schema

### 2.1 New Tables

All tables defined in `src/models/archival_models.py`:

1. **crawl_jobs** - Crawl job configuration and execution tracking
2. **warc_files** - WARC file metadata and storage locations
3. **website_snapshots** - Snapshot metadata and versioning
4. **snapshot_change_detection** - Detected changes between versions
5. **cdx_records** - CDX index for fast WARC lookups
6. **crawl_schedules** - Recurring crawl schedules with adaptive frequency

### 2.2 Integration with Existing Schema

- Links to `project_links` table via `link_id`
- Links to `crypto_projects` table via `project_id`
- Can trigger LLM reanalysis via `requires_reanalysis` flag
- Extends existing `WebsiteStatusLog` with archival status

---

## 3. Technology Stack

### 3.1 Core Dependencies

```python
# requirements-archival.txt
brozzler>=1.5.17          # Headless browser-based crawler with JS support
pywb>=2.7.0               # Web archive replay and access
warcio>=1.7.4             # WARC reading/writing library
browsertrix-crawler>=1.0  # Alternative modern crawler (optional)

# Optional: Heritrix integration
jpype1>=1.4.1             # Java bridge for Heritrix

# Storage backends
boto3>=1.26.0             # AWS S3 support
azure-storage-blob>=12.0  # Azure Blob Storage

# Scheduling and processing
apscheduler>=3.10.0       # Advanced job scheduling
celery>=5.3.0             # Distributed task queue (optional)

# Change detection and diff
beautifulsoup4>=4.12.0    # Already installed
difflib>=3.0              # Python standard library
html5lib>=1.1             # HTML parsing
```

### 3.2 Docker Services

Update `docker-compose.yml`:

```yaml
services:
  # ... existing services ...
  
  brozzler:
    image: webrecorder/browsertrix-crawler:latest
    container_name: crypto_archival_brozzler
    volumes:
      - ./data/warcs:/output
      - ./config/crawl-profiles:/profiles:ro
    environment:
      - CRAWL_HEADLESS=1
    networks:
      - crypto_analytics_network
    restart: unless-stopped
    
  pywb:
    image: webrecorder/pywb:latest
    container_name: crypto_archival_pywb
    ports:
      - "8090:8080"
    volumes:
      - ./data/warcs:/webarchive
      - ./config/pywb:/webarchive/config:ro
    environment:
      - INIT_COLLECTION=crypto_snapshots
    networks:
      - crypto_analytics_network
    restart: unless-stopped
    
  # Object storage for WARCs (optional)
  minio:
    image: minio/minio:latest
    container_name: crypto_archival_storage
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD:-minio_secure_password_2024}
    command: server /data --console-address ":9001"
    networks:
      - crypto_analytics_network
    restart: unless-stopped

volumes:
  minio_data:
    driver: local
```

---

## 4. Directory Structure

```
crypto-analytics/
├── src/
│   ├── archival/                     # NEW: Web archival system
│   │   ├── __init__.py
│   │   ├── crawler.py                # Brozzler/Heritrix wrapper
│   │   ├── scheduler.py              # Crawl scheduling logic
│   │   ├── storage.py                # WARC storage manager
│   │   ├── indexer.py                # CDX index generation
│   │   ├── versioning.py             # Snapshot versioning
│   │   ├── change_detector.py        # Diff computation
│   │   └── replay_server.py          # pywb integration
│   ├── models/
│   │   ├── archival_models.py        # NEW: Archival database models
│   │   └── database.py               # Existing models
│   └── pipelines/
│       └── archival_pipeline.py      # NEW: Full archival workflow
│
├── scripts/
│   └── archival/                     # NEW: Archival utilities
│       ├── init_archival_system.py   # Setup script
│       ├── run_scheduled_crawls.py   # Scheduler runner
│       ├── trigger_crawl.py          # Manual crawl trigger
│       ├── view_snapshot.py          # Browse snapshots
│       ├── compare_snapshots.py      # Diff viewer
│       └── monitor_storage.py        # Storage monitoring
│
├── data/
│   ├── warcs/                        # NEW: WARC file storage
│   │   ├── raw/                      # Raw WARC files
│   │   ├── compressed/               # Compressed archives
│   │   └── indexes/                  # CDX indexes
│   └── snapshots/                    # NEW: Snapshot metadata cache
│
├── config/
│   ├── archival/                     # NEW: Archival configuration
│   │   ├── crawl_profiles.yaml       # Crawl profiles per project
│   │   ├── brozzler_config.yaml      # Brozzler settings
│   │   └── storage_config.yaml       # Storage backend config
│   └── pywb/
│       └── config.yaml               # pywb replay configuration
│
├── migrations/
│   └── versions/
│       └── add_archival_tables.py    # NEW: Alembic migration
│
└── docs/
    ├── WEB_ARCHIVAL_IMPLEMENTATION_PLAN.md  # This document
    ├── ARCHIVAL_USAGE_GUIDE.md              # User guide
    └── ARCHIVAL_ARCHITECTURE.md             # Technical details
```

---

## 5. Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)

**Tasks:**
1. ✅ Create database models (`archival_models.py`)
2. Create Alembic migration for new tables
3. Set up Docker services (Brozzler, pywb, MinIO)
4. Implement WARC storage manager
5. Create basic crawler wrapper

**Deliverables:**
- Database tables created
- Docker services running
- Basic WARC writing functional

### Phase 2: Crawling Engine (Week 2-3)

**Tasks:**
1. Implement Brozzler integration
2. Add Heritrix fallback (optional)
3. Create crawl configuration system
4. Implement URL filtering and scope control
5. Add robots.txt respect and rate limiting

**Deliverables:**
- Functional web crawler
- WARC files generated
- Basic crawl metrics logged

### Phase 3: Scheduling & Automation (Week 3-4)

**Tasks:**
1. Implement crawl scheduler
2. Add priority-based job queue
3. Create adaptive scheduling logic
4. Build CLI tools for manual triggers
5. Add monitoring and alerting

**Deliverables:**
- Automated scheduled crawls
- CLI management tools
- Monitoring dashboard

### Phase 4: Versioning & Change Detection (Week 4-5)

**Tasks:**
1. Implement snapshot versioning
2. Build change detection algorithms
3. Create diff computation engine
4. Add significance scoring
5. Integrate with LLM reanalysis triggers

**Deliverables:**
- Version tracking functional
- Change detection working
- Automatic reanalysis on major changes

### Phase 5: Replay & Search (Week 5-6)

**Tasks:**
1. Set up pywb replay server
2. Generate CDX indexes
3. Build snapshot browser UI
4. Implement full-text search
5. Add version comparison tools

**Deliverables:**
- Historical snapshot browsing
- Search across versions
- Comparison tools

### Phase 6: Integration & Testing (Week 6-7)

**Tasks:**
1. Integrate with existing pipeline
2. Add archival hooks to analysis workflow
3. Create comprehensive tests
4. Performance optimization
5. Documentation

**Deliverables:**
- Full integration complete
- Test coverage >80%
- Complete documentation

---

## 6. Crawler Selection Strategy

### 6.1 Decision Matrix

| Website Type | Recommended Crawler | Reason |
|--------------|---------------------|--------|
| **SPA / React / Vue** | Brozzler | Full JavaScript execution |
| **Static HTML** | Heritrix or simple requests | Lower resource usage |
| **Mixed content** | Brozzler | Handles all cases |
| **Very large sites** | Heritrix | Better for massive crawls |

### 6.2 Auto-Detection Logic

```python
def select_crawler(url: str, project_metadata: dict) -> str:
    """Automatically select best crawler for a website."""
    
    # Check if we've detected JS frameworks
    if project_metadata.get('uses_javascript', False):
        return 'brozzler'
    
    # For small sites, use simple crawler
    if project_metadata.get('estimated_pages', 0) < 50:
        return 'simple'
    
    # Default to Brozzler for crypto projects (often modern)
    return 'brozzler'
```

---

## 7. WARC File Organization

### 7.1 File Naming Convention

```
{project_code}_{snapshot_timestamp}_{sequence}.warc.gz

Example:
BTC_20251027_140000_001.warc.gz
ETH_20251027_141500_001.warc.gz
```

### 7.2 Directory Structure

```
data/warcs/
├── 2025/
│   ├── 10/
│   │   ├── 27/
│   │   │   ├── BTC_20251027_140000_001.warc.gz
│   │   │   ├── BTC_20251027_140000_001.cdx
│   │   │   ├── ETH_20251027_141500_001.warc.gz
│   │   │   └── ETH_20251027_141500_001.cdx
│   │   └── 28/
│   └── 11/
└── indexes/
    └── master.cdx  # Combined index for all WARCs
```

### 7.3 Storage Tiers

| Tier | Age | Storage | Compression | Access |
|------|-----|---------|-------------|--------|
| **Hot** | 0-30 days | Local SSD | GZIP | Immediate |
| **Warm** | 30-90 days | Local HDD | GZIP | < 1 min |
| **Cold** | 90+ days | S3 Glacier | WACZ | Hours |

---

## 8. Change Detection Algorithm

### 8.1 Multi-Level Comparison

```python
class ChangeDetector:
    """Detect changes between website snapshots."""
    
    def detect_changes(self, old_snapshot, new_snapshot):
        """
        Compare two snapshots at multiple levels:
        1. Content hash comparison (fast)
        2. Structure diff (medium)
        3. Visual diff (slow, optional)
        """
        
        changes = {
            'content': self._compare_content(old, new),
            'structure': self._compare_structure(old, new),
            'resources': self._compare_resources(old, new),
        }
        
        # Calculate significance score
        score = self._calculate_significance(changes)
        
        return ChangeDetectionResult(
            change_type=self._classify_change(changes),
            score=score,
            requires_reanalysis=(score > 0.3),
            details=changes
        )
```

### 8.2 Significance Thresholds

| Change Score | Classification | Action |
|--------------|----------------|--------|
| 0.0 - 0.1 | Trivial | Log only |
| 0.1 - 0.3 | Minor | Update metadata |
| 0.3 - 0.7 | Significant | Trigger LLM reanalysis |
| 0.7 - 1.0 | Major | Priority reanalysis + alert |

---

## 9. Integration with Existing Pipeline

### 9.1 Hook Points

**In `content_analysis_pipeline.py`:**

```python
def analyze_content(self, project, link):
    """Enhanced with archival integration."""
    
    # 1. Trigger archival crawl (if enabled)
    if self.archival_enabled:
        snapshot = self.archival_manager.create_snapshot(link)
    
    # 2. Existing scraping logic
    scraped_data = self.website_scraper.scrape(link.url)
    
    # 3. Check for significant changes
    if snapshot and snapshot.has_significant_changes:
        # Force reanalysis even if recently analyzed
        force_reanalysis = True
    
    # 4. LLM analysis
    analysis = self.analyze_with_llm(scraped_data)
    
    # 5. Link snapshot to analysis
    if snapshot:
        analysis.snapshot_id = snapshot.id
```

### 9.2 New Analysis Runners

```bash
# Run archival crawls only (no LLM analysis)
python scripts/archival/run_scheduled_crawls.py

# Trigger crawl + analysis for specific project
python scripts/archival/trigger_crawl.py --project BTC --analyze

# Compare two snapshots
python scripts/archival/compare_snapshots.py --project BTC --from 2025-10-01 --to 2025-10-27
```

---

## 10. Configuration Examples

### 10.1 Crawl Profile (YAML)

```yaml
# config/archival/crawl_profiles.yaml

default:
  max_depth: 3
  max_pages: 1000
  respect_robots_txt: true
  crawl_frequency: weekly
  rate_limit_delay: 1.0
  url_patterns_exclude:
    - ".*\\.pdf$"
    - ".*login.*"
    - ".*admin.*"

high_priority:
  # For top 100 projects
  max_depth: 5
  max_pages: 5000
  crawl_frequency: daily
  
static_sites:
  # For simple static websites
  crawler_engine: simple
  use_javascript_rendering: false
  max_depth: 2
  
spa_projects:
  # For React/Vue/Angular sites
  crawler_engine: brozzler
  use_javascript_rendering: true
  javascript_timeout: 30
  wait_for_selector: ".app-loaded"
```

### 10.2 Storage Configuration

```yaml
# config/archival/storage_config.yaml

storage:
  backend: local  # local, s3, azure
  base_path: ./data/warcs
  
  compression:
    enabled: true
    format: gzip
    level: 6
  
  retention:
    hot_tier_days: 30
    warm_tier_days: 90
    archive_tier_days: 365
  
  s3:  # Optional S3 configuration
    bucket: crypto-archival-warcs
    region: us-east-1
    storage_class: STANDARD_IA
```

---

## 11. CLI Tools

### 11.1 Management Commands

```bash
# Initialize archival system
python scripts/archival/init_archival_system.py

# Create schedules for all projects
python scripts/archival/init_archival_system.py --create-schedules

# Start the scheduler daemon
python scripts/archival/run_scheduled_crawls.py --daemon

# Trigger manual crawl
python scripts/archival/trigger_crawl.py --project BTC --priority high

# View snapshot
python scripts/archival/view_snapshot.py --project BTC --version 5

# Compare versions
python scripts/archival/compare_snapshots.py --project BTC --v1 5 --v2 6

# Storage monitoring
python scripts/archival/monitor_storage.py --report
```

### 11.2 Monitoring Queries

```sql
-- View crawl job status
SELECT 
    p.name,
    cj.status,
    cj.pages_crawled,
    cj.progress_percentage,
    cj.started_at
FROM crawl_jobs cj
JOIN crypto_projects p ON cj.project_id = p.id
WHERE cj.status = 'in_progress'
ORDER BY cj.started_at DESC;

-- Snapshots with significant changes
SELECT 
    p.name,
    ws.version_number,
    ws.snapshot_timestamp,
    ws.change_type,
    ws.change_score
FROM website_snapshots ws
JOIN crypto_projects p ON ws.project_id = p.id
WHERE ws.has_significant_changes = true
ORDER BY ws.change_score DESC
LIMIT 20;

-- Storage usage by project
SELECT 
    p.name,
    COUNT(wf.id) as warc_count,
    SUM(wf.file_size_bytes) / 1024 / 1024 / 1024 as total_gb
FROM warc_files wf
JOIN crawl_jobs cj ON wf.crawl_job_id = cj.id
JOIN crypto_projects p ON cj.project_id = p.id
GROUP BY p.name
ORDER BY total_gb DESC
LIMIT 20;
```

---

## 12. Performance Considerations

### 12.1 Resource Estimates

| Component | CPU | Memory | Disk I/O | Network |
|-----------|-----|--------|----------|---------|
| Brozzler | High | 2-4GB per instance | Medium | High |
| WARC Writing | Low | 512MB | High | Low |
| CDX Indexing | Medium | 1GB | High | Low |
| Change Detection | Medium | 1-2GB | Medium | Low |
| pywb Replay | Low | 512MB | Medium | Medium |

### 12.2 Scaling Strategy

**Horizontal Scaling:**
- Run multiple Brozzler instances for parallel crawls
- Use Celery for distributed task processing
- Separate read/write database instances

**Vertical Scaling:**
- Increase storage IOPS for WARC writes
- More RAM for in-memory CDX indexes
- Faster CPUs for change detection

### 12.3 Storage Projections

**Assumptions:**
- 51,000 projects in database
- Average WARC size: 50MB (compressed)
- Weekly crawl frequency

**Storage Requirements:**

| Timeframe | Active Projects | Total Storage |
|-----------|----------------|---------------|
| 1 month | 5,000 | ~1 TB |
| 3 months | 10,000 | ~6 TB |
| 1 year | 20,000 | ~50 TB |

---

## 13. Security & Privacy

### 13.1 Considerations

- **Respect robots.txt** - Always honor exclusions
- **Rate limiting** - Don't overwhelm target servers
- **User-Agent** - Identify as archival crawler
- **Privacy** - Don't archive user data or login areas
- **Compliance** - GDPR, CCPA considerations

### 13.2 URL Exclusion Patterns

```python
DEFAULT_EXCLUSIONS = [
    r'.*login.*',
    r'.*admin.*',
    r'.*dashboard.*',
    r'.*account.*',
    r'.*user.*',
    r'.*profile.*',
    r'.*settings.*',
    r'.*\.pdf$',
    r'.*\.zip$',
    r'.*\.exe$',
]
```

---

## 14. Testing Strategy

### 14.1 Unit Tests

- WARC file writing and reading
- CDX index generation
- Change detection algorithms
- Snapshot versioning logic

### 14.2 Integration Tests

- Full crawl → WARC → index workflow
- Database operations
- Storage backend operations
- pywb replay functionality

### 14.3 End-to-End Tests

```python
def test_full_archival_workflow():
    """Test complete archival process."""
    
    # 1. Create crawl job
    job = create_crawl_job(project_id=1, url="https://example.com")
    
    # 2. Execute crawl
    result = execute_crawl(job)
    assert result.pages_crawled > 0
    
    # 3. Verify WARC created
    warc_file = get_warc_file(job.id)
    assert warc_file.file_size_bytes > 0
    
    # 4. Generate CDX index
    cdx_records = generate_cdx_index(warc_file)
    assert len(cdx_records) > 0
    
    # 5. Create snapshot
    snapshot = create_snapshot(job)
    assert snapshot.version_number == 1
    
    # 6. Verify replay
    response = replay_url(snapshot, "https://example.com")
    assert response.status_code == 200
```

---

## 15. Migration Plan

### 15.1 Database Migration

```bash
# Create migration
alembic revision -m "add_archival_tables"

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

### 15.2 Backfilling Existing Projects

```python
# scripts/archival/backfill_schedules.py

def backfill_crawl_schedules():
    """Create schedules for existing high-priority projects."""
    
    # Get top projects by market cap
    top_projects = session.query(CryptoProject)\
        .filter(CryptoProject.market_cap > 100_000_000)\
        .order_by(CryptoProject.market_cap.desc())\
        .limit(1000)\
        .all()
    
    for project in top_projects:
        website_link = get_website_link(project)
        if website_link:
            create_crawl_schedule(
                link_id=website_link.id,
                frequency=CrawlFrequency.WEEKLY,
                priority=calculate_priority(project)
            )
```

---

## 16. Monitoring & Alerting

### 16.1 Key Metrics

- Crawl success rate
- Average crawl duration
- WARC file sizes
- Storage usage trends
- Change detection rate
- Significant change alerts

### 16.2 Alerting Rules

```yaml
alerts:
  - name: crawl_failure_rate_high
    condition: failure_rate > 0.2
    action: email_admin
    
  - name: storage_capacity_low
    condition: disk_usage > 0.85
    action: email_admin + pause_new_crawls
    
  - name: significant_change_detected
    condition: change_score > 0.7
    action: trigger_priority_reanalysis
```

---

## 17. Future Enhancements

### Phase 2 Improvements (Post-MVP)

1. **Visual Regression Testing**
   - Screenshot comparison
   - Visual diff highlighting
   
2. **Machine Learning Integration**
   - Predict site update frequency
   - Anomaly detection in changes
   - Auto-categorize change types

3. **Advanced Replay Features**
   - Side-by-side version comparison
   - Timeline scrubber UI
   - Annotation system

4. **API Endpoints**
   - REST API for external access
   - Webhook notifications
   - Real-time crawl status

5. **Content Extraction Pipeline**
   - Structured data extraction from snapshots
   - Entity recognition across versions
   - Temporal knowledge graph

---

## 18. Summary & Next Steps

### Implementation Summary

This plan provides a complete, production-ready web archival system that:

✅ Uses industry-standard WARC format  
✅ Supports JavaScript-heavy websites via Brozzler  
✅ Provides comprehensive versioning and change detection  
✅ Enables historical browsing via pywb  
✅ Integrates seamlessly with existing pipeline  
✅ Scales from hundreds to tens of thousands of projects  

### Immediate Next Steps

1. **Week 1**: Create database migration, set up Docker services
2. **Week 2**: Implement core crawler wrapper and WARC storage
3. **Week 3**: Build scheduling system and CLI tools
4. **Week 4**: Add change detection and versioning
5. **Week 5**: Set up replay server and search
6. **Week 6**: Integration testing and documentation
7. **Week 7**: Production deployment and monitoring

### Success Criteria

- [ ] 1,000+ projects crawled and archived
- [ ] WARC files successfully stored and indexed
- [ ] Historical snapshots browsable via pywb
- [ ] Change detection identifying significant updates
- [ ] <5% crawl failure rate
- [ ] Integration with LLM analysis pipeline complete

---

## Appendix A: Brozzler vs Heritrix Comparison

| Feature | Brozzler | Heritrix |
|---------|----------|----------|
| JavaScript | ✅ Full support | ❌ Limited |
| Resource Usage | High | Medium |
| Setup Complexity | Low | High |
| Scalability | Good | Excellent |
| WARC Output | ✅ Native | ✅ Native |
| Configuration | Simple YAML | Complex XML |
| **Recommendation** | Primary choice | Fallback/static sites |

## Appendix B: Useful Resources

- [WARC Specification](https://iipc.github.io/warc-specifications/)
- [pywb Documentation](https://pywb.readthedocs.io/)
- [Brozzler GitHub](https://github.com/internetarchive/brozzler)
- [CDX Format](https://pywb.readthedocs.io/en/latest/manual/indexing.html)
