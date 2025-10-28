# Web Archival System - Integration Guide

**Complete! Ready for Production Use**

This guide shows how to integrate the web archival system with your existing crypto analytics pipeline.

---

## 📋 Table of Contents

1. [Quick Integration](#quick-integration)
2. [Pipeline Hooks](#pipeline-hooks)
3. [Automated Workflows](#automated-workflows)
4. [Usage Examples](#usage-examples)
5. [Configuration](#configuration)
6. [Best Practices](#best-practices)

---

## 🚀 Quick Integration

### Step 1: Import Integration Layer

```python path=null start=null
from src.archival import create_archival_integration
from src.database.manager import DatabaseManager

# Initialize
db = DatabaseManager()
archival = create_archival_integration(
    db_manager=db,
    enable_scheduler=True  # Start automated crawls
)
```

### Step 2: Add to Your Pipeline

```python path=null start=null
from src.pipelines.content_analysis_pipeline import ContentAnalysisPipeline

class EnhancedPipeline(ContentAnalysisPipeline):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add archival integration
        self.archival = create_archival_integration(
            db_manager=self.db_manager,
            enable_scheduler=False  # Manage scheduler separately
        )
```

---

## 🔗 Pipeline Hooks

The integration provides several hooks you can use at different pipeline stages:

### 1. On Project Discovery

When you discover a new project with a website:

```python path=null start=null
def discover_project(self, project_id: int, website_url: str):
    # Your existing discovery logic
    project = self.add_project_to_database(project_id, website_url)
    
    # Archive the website immediately
    job_id = self.archival.on_project_discovered(
        project_id=project_id,
        website_url=website_url,
        create_schedule=True  # Auto-schedule future crawls
    )
    
    self.logger.info(f"Initiated archival job {job_id}")
```

### 2. After Content Analysis

After analyzing website content:

```python path=null start=null
def analyze_project_website(self, project_id: int):
    # Your existing analysis logic
    analysis = self.website_analyzer.analyze(project_id)
    content_hash = self.calculate_hash(analysis.content)
    
    # Check against archived version
    self.archival.on_analysis_completed(
        project_id=project_id,
        analysis_content_hash=content_hash
    )
    
    return analysis
```

### 3. Periodic Change Detection

Run daily to check for significant changes:

```python path=null start=null
def check_website_changes(self):
    """Daily job to process detected changes."""
    
    # Get projects with significant changes
    projects_to_reanalyze = self.archival.check_for_changes_and_reanalyze(
        reanalysis_threshold=0.3  # 30% change
    )
    
    # Trigger reanalysis for each
    for project_id in projects_to_reanalyze:
        self.analyze_project_website(project_id)
```

### 4. Status Logging

Add archival status to your logs:

```python path=null start=null
def log_project_status(self, project_id: int):
    # Your existing status logging
    status_logger = self.create_status_logger(project_id)
    
    # Add archival information
    self.archival.update_pipeline_status_with_archival(
        project_id=project_id,
        status_logger=status_logger
    )
```

---

## 🤖 Automated Workflows

### Workflow 1: New Project Onboarding

```python path=null start=null
def onboard_new_project(self, project_data: dict):
    """Complete onboarding workflow with archival."""
    
    # 1. Create project record
    project = self.create_project(project_data)
    
    # 2. Archive website immediately
    job_id = self.archival.on_project_discovered(
        project_id=project.id,
        website_url=project.website_url,
        create_schedule=True
    )
    
    # 3. Wait for archival to complete
    self.wait_for_crawl(job_id, timeout=300)
    
    # 4. Analyze archived content
    analysis = self.analyze_project_website(project.id)
    
    # 5. Store results
    self.store_analysis(project.id, analysis)
    
    return project
```

### Workflow 2: Daily Change Detection

```python path=null start=null
def daily_change_detection_job(self):
    """
    Daily job to detect and process website changes.
    
    This should be run as a cron job or scheduled task.
    """
    
    # 1. Check for significant changes
    projects = self.archival.check_for_changes_and_reanalyze(
        reanalysis_threshold=0.3
    )
    
    if not projects:
        self.logger.info("No significant changes detected")
        return
    
    self.logger.info(f"Processing {len(projects)} changed websites")
    
    # 2. Reanalyze each project
    for project_id in projects:
        try:
            # Get change details
            status = self.archival.get_archival_status_for_project(project_id)
            
            # Trigger reanalysis
            self.archival.trigger_reanalysis_for_project(
                project_id=project_id,
                reason="Website change detected"
            )
            
            # Your pipeline logic to actually perform reanalysis
            self.analyze_project_website(project_id)
            
        except Exception as e:
            self.logger.error(f"Error processing project {project_id}: {e}")
```

### Workflow 3: Bulk Historical Analysis

```python path=null start=null
def analyze_historical_snapshots(self, project_id: int):
    """Analyze all historical snapshots of a project."""
    
    from src.models.archival_models import WebsiteSnapshot
    from sqlalchemy import select
    
    with self.db_manager.session() as session:
        snapshots = session.execute(
            select(WebsiteSnapshot)
            .filter(WebsiteSnapshot.project_id == project_id)
            .order_by(WebsiteSnapshot.snapshot_timestamp)
        ).scalars().all()
        
        analyses = []
        for snapshot in snapshots:
            # Extract content from archived WARC
            content = self.extract_warc_content(snapshot.warc_file_id)
            
            # Analyze
            analysis = self.website_analyzer.analyze_content(content)
            analyses.append({
                'version': snapshot.version_number,
                'timestamp': snapshot.snapshot_timestamp,
                'analysis': analysis
            })
        
        return analyses
```

---

## 📝 Usage Examples

### Example 1: Basic Integration

```python path=null start=null
# main.py
from src.database.manager import DatabaseManager
from src.archival import create_archival_integration
from src.pipelines.content_analysis_pipeline import ContentAnalysisPipeline

def main():
    # Initialize
    db = DatabaseManager()
    
    # Create pipeline with archival
    pipeline = ContentAnalysisPipeline(
        db_manager=db,
        scraper_config={'max_pages': 50},
        analyzer_config={'provider': 'ollama'}
    )
    
    # Add archival integration
    archival = create_archival_integration(db, enable_scheduler=False)
    
    # Process new projects
    for project in pipeline.get_unprocessed_projects():
        # Archive
        job_id = archival.on_project_discovered(
            project_id=project.id,
            website_url=project.website_url
        )
        
        # Analyze
        pipeline.analyze_project(project.id)

if __name__ == '__main__':
    main()
```

### Example 2: Scheduled Integration

```python path=null start=null
# scheduler.py
import schedule
import time
from src.database.manager import DatabaseManager
from src.archival import create_archival_integration

def check_changes():
    """Check for website changes daily."""
    db = DatabaseManager()
    archival = create_archival_integration(db)
    
    projects = archival.check_for_changes_and_reanalyze(
        reanalysis_threshold=0.3
    )
    
    print(f"Found {len(projects)} projects with significant changes")
    
    # Trigger reanalysis via your pipeline
    for project_id in projects:
        # Your reanalysis logic here
        pass

# Schedule daily at 3 AM
schedule.every().day.at("03:00").do(check_changes)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Example 3: API Integration

```python path=null start=null
# api.py
from fastapi import FastAPI, BackgroundTasks
from src.archival import create_archival_integration

app = FastAPI()
archival = create_archival_integration(db, enable_scheduler=False)

@app.post("/projects/{project_id}/archive")
async def archive_project(
    project_id: int,
    background_tasks: BackgroundTasks
):
    """Trigger archival for a project."""
    
    # Get project
    project = db.get_project(project_id)
    
    # Start archival in background
    background_tasks.add_task(
        archival.on_project_discovered,
        project_id=project_id,
        website_url=project.website_url
    )
    
    return {"status": "archival_initiated", "project_id": project_id}

@app.get("/projects/{project_id}/archival-status")
async def get_archival_status(project_id: int):
    """Get archival status for a project."""
    
    status = archival.get_archival_status_for_project(project_id)
    return status
```

---

## ⚙️ Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Archival settings
ARCHIVAL_ENABLED=true
ARCHIVAL_SCHEDULER_ENABLED=true
ARCHIVAL_MAX_CONCURRENT_CRAWLS=3
ARCHIVAL_CHANGE_THRESHOLD=0.3
ARCHIVAL_REANALYSIS_ENABLED=true

# Storage backend
ARCHIVAL_STORAGE_BACKEND=local
ARCHIVAL_STORAGE_PATH=data/warcs

# Optional: S3 storage
ARCHIVAL_S3_BUCKET=my-archival-bucket
ARCHIVAL_S3_REGION=us-east-1
```

### Pipeline Configuration

```python path=null start=null
# config/archival_config.py

ARCHIVAL_CONFIG = {
    # Crawler settings
    'crawler': {
        'max_pages': 50,
        'max_depth': 2,
        'page_timeout': 30,
        'respect_robots_txt': True
    },
    
    # Schedule settings
    'scheduler': {
        'max_concurrent': 3,
        'default_frequency': 'weekly',
        'high_priority_frequency': 'daily'
    },
    
    # Change detection settings
    'change_detection': {
        'threshold': 0.3,
        'auto_reanalyze': True,
        'weights': {
            'content': 0.4,
            'structure': 0.3,
            'resources': 0.2,
            'pages': 0.1
        }
    },
    
    # Storage settings
    'storage': {
        'backend': 'local',
        'base_path': 'data/warcs',
        'compression': True,
        'retention_days': 365
    }
}
```

---

## 💡 Best Practices

### 1. Archival Strategy

**Do:**
- Archive immediately on project discovery
- Create schedules based on project importance
- Run change detection daily
- Use thresholds to avoid false positives

**Don't:**
- Archive every project at the same frequency
- Reanalyze for minor changes (<20% change score)
- Archive sites that block crawlers
- Store duplicate snapshots

### 2. Resource Management

```python path=null start=null
# Limit concurrent operations
archival = create_archival_integration(
    db,
    enable_scheduler=True
)

# Set max concurrent crawls
scheduler = archival.scheduler
scheduler.max_concurrent = 3  # Adjust based on resources
```

### 3. Error Handling

```python path=null start=null
def safe_archive(project_id: int, website_url: str):
    """Archive with proper error handling."""
    try:
        job_id = archival.on_project_discovered(
            project_id=project_id,
            website_url=website_url,
            create_schedule=True
        )
        
        if not job_id:
            logger.error(f"Failed to create crawl job for {project_id}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Archival error for {project_id}: {e}", exc_info=True)
        return False
```

### 4. Monitoring

```python path=null start=null
def monitor_archival_health():
    """Monitor archival system health."""
    from scripts.archival.monitor_archival import ArchivalMonitor
    
    monitor = ArchivalMonitor(db)
    
    # Check storage
    storage = monitor.get_storage_stats()
    if storage['total_gb'] > 1000:  # 1TB limit
        alert("Storage limit approaching")
    
    # Check crawl success rate
    crawls = monitor.get_crawl_stats(7)  # Last 7 days
    if crawls['success_rate'] < 80:
        alert("Low crawl success rate")
    
    # Check for failed schedules
    schedules = monitor.get_schedule_stats()
    # Add your monitoring logic
```

### 5. Performance Optimization

```python path=null start=null
# Use batch operations
def batch_archive_projects(project_ids: List[int]):
    """Archive multiple projects efficiently."""
    
    for project_id in project_ids:
        # Queue for background processing
        archival.on_project_discovered(
            project_id=project_id,
            website_url=get_website_url(project_id),
            create_schedule=True
        )
        
        # Don't wait for completion
        # Let scheduler handle execution
```

---

## 🔄 Migration Path

### Phase 1: Add Archival (No Changes)

```python path=null start=null
# Just add archival alongside existing pipeline
archival = create_archival_integration(db, enable_scheduler=False)

# Continue using your existing pipeline
# Archival runs independently
```

### Phase 2: Integrate Hooks

```python path=null start=null
# Add hooks to existing pipeline methods
class MyPipeline(ContentAnalysisPipeline):
    def analyze_project(self, project_id):
        # Existing code
        result = super().analyze_project(project_id)
        
        # Add archival hook
        self.archival.on_analysis_completed(
            project_id=project_id,
            analysis_content_hash=result.content_hash
        )
        
        return result
```

### Phase 3: Enable Automation

```python path=null start=null
# Enable scheduler and change detection
archival = create_archival_integration(db, enable_scheduler=True)

# Add daily change detection job
# Use your existing job scheduler (cron/celery/etc)
```

---

## 📊 Monitoring & Alerts

### Dashboard Integration

```python path=null start=null
def get_dashboard_stats():
    """Get stats for dashboard display."""
    from scripts.archival.monitor_archival import ArchivalMonitor
    
    monitor = ArchivalMonitor(db)
    
    return {
        'storage': monitor.get_storage_stats(),
        'crawls': monitor.get_crawl_stats(30),
        'changes': monitor.get_change_stats(30),
        'schedules': monitor.get_schedule_stats()
    }
```

### Health Check Endpoint

```python path=null start=null
@app.get("/health/archival")
async def archival_health_check():
    """Health check for archival system."""
    
    monitor = ArchivalMonitor(db)
    storage = monitor.get_storage_stats()
    crawls = monitor.get_crawl_stats(1)  # Last 24h
    
    health = {
        'status': 'healthy',
        'storage_gb': storage['total_gb'],
        'crawls_today': crawls['total_crawls'],
        'success_rate': crawls['success_rate']
    }
    
    # Check thresholds
    if storage['total_gb'] > 1000:
        health['status'] = 'warning'
    if crawls['success_rate'] < 70:
        health['status'] = 'degraded'
    
    return health
```

---

## 🎯 Summary

### What You Get

✅ **Automatic website archiving** on project discovery  
✅ **Version tracking** with complete history  
✅ **Change detection** with configurable thresholds  
✅ **Automated reanalysis** when websites change significantly  
✅ **Scheduled crawls** based on project importance  
✅ **Status logging** integration  
✅ **Historical replay** via pywb

### Next Steps

1. **Add integration to your pipeline** - Use hooks shown above
2. **Configure schedules** - Run `run_scheduler.py --init-schedules`
3. **Start scheduler daemon** - Run `run_scheduler.py`
4. **Monitor system** - Use `monitor_archival.py --dashboard`
5. **View archives** - Access pywb at http://localhost:8080

---

**Questions?** Check the main documentation:
- `docs/ARCHIVAL_QUICKSTART.md` - Quick start guide
- `docs/ARCHIVAL_STATUS.md` - Current status and capabilities
- `docs/ARCHIVAL_FINAL_SUMMARY.md` - Complete system overview

**Ready to integrate!** 🚀
