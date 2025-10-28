"""
Crypto Analytics Web Archival System

This module provides comprehensive web archival capabilities including:
- WARC-based website archiving
- Multi-engine crawler support (Browsertrix, Brozzler, Simple HTTP)
- Snapshot versioning and change detection
- CDX indexing for fast lookups
- Historical replay via pywb
- S3/Azure storage backend support
"""

# Import classes directly from submodules to avoid circular imports
from .storage import WARCStorageManager, StorageConfig
from .crawler import ArchivalCrawler, CrawlConfig, CrawlResult
from .change_detector import ChangeDetector, ChangeMetrics, format_change_report
from .indexer import CDXIndexer, CDXEntry, batch_index_warcs
from .scheduler import ArchivalScheduler, SchedulerMode, create_default_schedules
from .pipeline_integration import ArchivalPipelineIntegration, create_archival_integration

__all__ = [
    'WARCStorageManager', 'StorageConfig',
    'ArchivalCrawler', 'CrawlConfig', 'CrawlResult',
    'ChangeDetector', 'ChangeMetrics', 'format_change_report',
    'CDXIndexer', 'CDXEntry', 'batch_index_warcs',
    'ArchivalScheduler', 'SchedulerMode', 'create_default_schedules',
    'ArchivalPipelineIntegration', 'create_archival_integration',
]

__version__ = '1.0.0'
