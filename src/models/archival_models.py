"""
Database models for web archival and versioning system.

This module defines tables for:
- Crawl job scheduling and management
- WARC file storage and metadata
- Website snapshots and versioning
- Change detection between versions
- CDX index for fast lookups
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    Boolean,
    JSON,
    ForeignKey,
    BigInteger,
    Enum,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import enum

from models.database import Base


class CrawlStatus(enum.Enum):
    """Status of a crawl job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"


class CrawlFrequency(enum.Enum):
    """Frequency for scheduled crawls."""

    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"


class ChangeType(enum.Enum):
    """Type of change detected between snapshots."""

    CONTENT_ADDED = "content_added"
    CONTENT_REMOVED = "content_removed"
    CONTENT_MODIFIED = "content_modified"
    STRUCTURE_CHANGED = "structure_changed"
    RESOURCES_CHANGED = "resources_changed"
    MAJOR_REDESIGN = "major_redesign"
    NO_CHANGE = "no_change"


class CrawlJob(Base):
    """Scheduled or on-demand crawl jobs for project websites."""

    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True)
    job_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)

    # Link to project
    link_id = Column(
        Integer, ForeignKey("project_links.id"), nullable=False, index=True
    )
    project_id = Column(
        Integer, ForeignKey("crypto_projects.id"), nullable=False, index=True
    )

    # Crawl configuration
    seed_url = Column(Text, nullable=False)
    crawl_scope = Column(String(50), default="domain")  # domain, subdomain, path
    max_depth = Column(Integer, default=3)
    max_pages = Column(Integer, default=1000)
    crawl_frequency = Column(Enum(CrawlFrequency), default=CrawlFrequency.WEEKLY)

    # URL filtering
    url_patterns_include = Column(JSON)  # List of regex patterns to include
    url_patterns_exclude = Column(JSON)  # List of regex patterns to exclude
    respect_robots_txt = Column(Boolean, default=True)

    # Crawl engine selection
    crawler_engine = Column(
        String(20), default="brozzler"
    )  # brozzler, heritrix, simple
    use_javascript_rendering = Column(Boolean, default=True)

    # Scheduling
    schedule_enabled = Column(Boolean, default=True)
    next_scheduled_run = Column(DateTime)
    last_run_at = Column(DateTime)

    # Status and progress
    status = Column(Enum(CrawlStatus), default=CrawlStatus.PENDING, index=True)
    progress_percentage = Column(Float, default=0.0)
    pages_crawled = Column(Integer, default=0)
    bytes_downloaded = Column(BigInteger, default=0)

    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Resource limits
    timeout_seconds = Column(Integer, default=3600)  # 1 hour default
    rate_limit_delay = Column(Float, default=1.0)  # seconds between requests

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    warc_files = relationship(
        "WARCFile", back_populates="crawl_job", cascade="all, delete-orphan"
    )
    snapshots = relationship(
        "WebsiteSnapshot", back_populates="crawl_job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_crawl_jobs_status_scheduled", "status", "next_scheduled_run"),
        Index("idx_crawl_jobs_link_created", "link_id", "created_at"),
        {"extend_existing": True},
    )


class WARCFile(Base):
    """WARC/WACZ file storage metadata and location tracking."""

    __tablename__ = "warc_files"

    id = Column(Integer, primary_key=True)
    file_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)

    # Association with crawl job
    crawl_job_id = Column(
        Integer, ForeignKey("crawl_jobs.id"), nullable=False, index=True
    )
    snapshot_id = Column(Integer, ForeignKey("website_snapshots.id"), index=True)

    # File information
    filename = Column(String(500), nullable=False)
    file_format = Column(String(10), default="warc")  # warc, warc.gz, wacz
    file_path = Column(Text, nullable=False)  # Local path or S3 key
    storage_backend = Column(String(20), default="local")  # local, s3, azure

    # File metadata
    file_size_bytes = Column(BigInteger)
    file_hash_sha256 = Column(String(64))  # SHA256 hash for integrity
    compression = Column(String(20))  # gzip, none

    # WARC metadata
    warc_version = Column(String(10), default="1.1")
    record_count = Column(Integer)  # Number of WARC records
    pages_count = Column(Integer)  # Number of pages captured
    resources_count = Column(Integer)  # Number of resources (css, js, images)

    # CDX index
    has_cdx_index = Column(Boolean, default=False)
    cdx_file_path = Column(Text)  # Path to CDX index file

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    archived_at = Column(DateTime)  # When moved to archive storage

    # Relationships
    crawl_job = relationship("CrawlJob", back_populates="warc_files")
    snapshot = relationship("WebsiteSnapshot", back_populates="warc_files")
    cdx_records = relationship(
        "CDXRecord", back_populates="warc_file", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_warc_files_snapshot", "snapshot_id", "created_at"),
        {"extend_existing": True},
    )


class WebsiteSnapshot(Base):
    """Website snapshot metadata and versioning information."""

    __tablename__ = "website_snapshots"

    id = Column(Integer, primary_key=True)
    snapshot_uuid = Column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True
    )

    # Association
    link_id = Column(
        Integer, ForeignKey("project_links.id"), nullable=False, index=True
    )
    project_id = Column(
        Integer, ForeignKey("crypto_projects.id"), nullable=False, index=True
    )
    crawl_job_id = Column(Integer, ForeignKey("crawl_jobs.id"), nullable=False)

    # Snapshot metadata
    snapshot_timestamp = Column(DateTime, nullable=False, index=True)
    version_number = Column(
        Integer, nullable=False
    )  # Sequential version for this project

    # Domain and URL info
    domain = Column(String(500), nullable=False, index=True)
    seed_url = Column(Text, nullable=False)

    # Crawl statistics
    pages_captured = Column(Integer, default=0)
    resources_captured = Column(Integer, default=0)
    total_size_bytes = Column(BigInteger, default=0)
    crawl_duration_seconds = Column(Float)

    # Content hashes for change detection
    content_hash_sha256 = Column(String(64))  # Hash of main page content
    structure_hash_sha256 = Column(String(64))  # Hash of page structure (DOM tree)
    resources_hash_sha256 = Column(String(64))  # Hash of all resource URLs
    full_site_hash_sha256 = Column(String(64))  # Hash of entire snapshot

    # Content statistics
    total_text_length = Column(Integer)
    unique_pages_count = Column(Integer)
    broken_links_count = Column(Integer)

    # Technical metadata
    technologies_detected = Column(JSON)  # List of detected technologies
    frameworks_detected = Column(JSON)  # Web frameworks identified

    # Quality indicators
    capture_quality_score = Column(Float)  # 0-1 score of capture completeness
    javascript_errors_count = Column(Integer, default=0)
    resource_load_failures = Column(Integer, default=0)

    # Change detection flags
    is_first_snapshot = Column(Boolean, default=False)
    has_significant_changes = Column(Boolean, default=False)
    change_type = Column(Enum(ChangeType))
    change_score = Column(Float)  # 0-1 score of how much changed

    # Previous version reference
    previous_snapshot_id = Column(Integer, ForeignKey("website_snapshots.id"))

    # Status
    processing_complete = Column(Boolean, default=False)
    index_generated = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    link = relationship("ProjectLink", foreign_keys=[link_id])
    crawl_job = relationship("CrawlJob", back_populates="snapshots")
    warc_files = relationship("WARCFile", back_populates="snapshot")
    changes_as_old = relationship(
        "SnapshotChangeDetection",
        foreign_keys="SnapshotChangeDetection.old_snapshot_id",
        back_populates="old_snapshot",
    )
    changes_as_new = relationship(
        "SnapshotChangeDetection",
        foreign_keys="SnapshotChangeDetection.new_snapshot_id",
        back_populates="new_snapshot",
    )
    previous_snapshot = relationship("WebsiteSnapshot", remote_side=[id], uselist=False)

    __table_args__ = (
        Index("idx_snapshots_project_timestamp", "project_id", "snapshot_timestamp"),
        Index("idx_snapshots_link_version", "link_id", "version_number"),
        {"extend_existing": True},
    )


class SnapshotChangeDetection(Base):
    """Detected changes between two consecutive website snapshots."""

    __tablename__ = "snapshot_change_detection"

    id = Column(Integer, primary_key=True)

    # Snapshot references
    old_snapshot_id = Column(
        Integer, ForeignKey("website_snapshots.id"), nullable=False, index=True
    )
    new_snapshot_id = Column(
        Integer, ForeignKey("website_snapshots.id"), nullable=False, index=True
    )

    # Overall change metrics
    change_type = Column(Enum(ChangeType), nullable=False)
    change_score = Column(Float)  # 0-1, how significant the change is
    similarity_score = Column(Float)  # 0-1, how similar the snapshots are

    # Content changes
    text_added_bytes = Column(Integer, default=0)
    text_removed_bytes = Column(Integer, default=0)
    text_changed_percentage = Column(Float)

    # Structure changes
    html_structure_diff_score = Column(Float)
    new_sections_count = Column(Integer, default=0)
    removed_sections_count = Column(Integer, default=0)

    # Resource changes
    resources_added_count = Column(Integer, default=0)
    resources_removed_count = Column(Integer, default=0)
    resources_changed_count = Column(Integer, default=0)

    # Detected changes (detailed)
    changes_detected = Column(JSONB)  # Detailed list of changes
    # Structure: {
    #   "content": [{"type": "added", "location": "section#about", "length": 1234}],
    #   "structure": [{"type": "removed", "element": "div.old-feature"}],
    #   "resources": [{"type": "changed", "url": "app.js", "old_hash": "...", "new_hash": "..."}]
    # }

    # Visual changes
    layout_changed = Column(Boolean, default=False)
    style_changed = Column(Boolean, default=False)

    # Specific page changes
    pages_changed = Column(JSON)  # List of URLs with changes
    pages_added = Column(JSON)
    pages_removed = Column(JSON)

    # Analysis
    is_significant_change = Column(Boolean, default=False)
    requires_reanalysis = Column(
        Boolean, default=False
    )  # Should trigger LLM reanalysis

    # Metadata
    diff_computed_at = Column(DateTime, default=datetime.utcnow)
    computation_time_seconds = Column(Float)

    # Relationships
    old_snapshot = relationship(
        "WebsiteSnapshot",
        foreign_keys=[old_snapshot_id],
        back_populates="changes_as_old",
    )
    new_snapshot = relationship(
        "WebsiteSnapshot",
        foreign_keys=[new_snapshot_id],
        back_populates="changes_as_new",
    )

    __table_args__ = (
        Index("idx_change_detection_snapshots", "old_snapshot_id", "new_snapshot_id"),
        Index(
            "idx_change_detection_significant", "is_significant_change", "change_score"
        ),
        {"extend_existing": True},
    )


class CDXRecord(Base):
    """CDX index records for fast WARC lookups (URL → WARC location)."""

    __tablename__ = "cdx_records"

    id = Column(Integer, primary_key=True)

    # Association
    warc_file_id = Column(
        Integer, ForeignKey("warc_files.id"), nullable=False, index=True
    )
    snapshot_id = Column(
        Integer, ForeignKey("website_snapshots.id"), nullable=False, index=True
    )

    # CDX fields (standard format)
    url_key = Column(String(2000), nullable=False, index=True)  # SURT format URL
    timestamp = Column(String(14), nullable=False)  # YYYYMMDDhhmmss format
    original_url = Column(Text, nullable=False)
    mime_type = Column(String(100))
    status_code = Column(Integer)
    digest = Column(String(64))  # Content hash (SHA1 or SHA256)
    redirect_url = Column(Text)

    # WARC location
    warc_filename = Column(String(500), nullable=False)
    warc_record_offset = Column(BigInteger, nullable=False)
    warc_record_length = Column(Integer)

    # Additional metadata
    content_length = Column(Integer)
    charset = Column(String(50))
    languages = Column(JSON)  # Detected languages

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    warc_file = relationship("WARCFile", back_populates="cdx_records")

    __table_args__ = (
        Index("idx_cdx_url_timestamp", "url_key", "timestamp"),
        Index("idx_cdx_snapshot_url", "snapshot_id", "url_key"),
        {"extend_existing": True},
    )


class CrawlSchedule(Base):
    """Recurring crawl schedules for projects."""

    __tablename__ = "crawl_schedules"

    id = Column(Integer, primary_key=True)

    # Association
    link_id = Column(
        Integer, ForeignKey("project_links.id"), nullable=False, unique=True
    )
    project_id = Column(Integer, ForeignKey("crypto_projects.id"), nullable=False)

    # Schedule configuration
    enabled = Column(Boolean, default=True)
    frequency = Column(Enum(CrawlFrequency), default=CrawlFrequency.WEEKLY)

    # Priority and conditions
    priority = Column(Integer, default=5)  # 1-10, higher = more important
    min_market_cap = Column(Float)  # Only crawl if market cap above threshold

    # Adaptive scheduling
    change_frequency_observed = Column(String(50))  # How often site changes
    last_significant_change = Column(DateTime)
    average_change_score = Column(Float)

    # Next run calculation
    next_run_at = Column(DateTime, nullable=False, index=True)
    last_run_at = Column(DateTime)
    consecutive_no_change_count = Column(Integer, default=0)

    # Status
    is_paused = Column(Boolean, default=False)
    pause_reason = Column(String(200))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_schedules_enabled_next_run", "enabled", "next_run_at"),
        {"extend_existing": True},
    )
