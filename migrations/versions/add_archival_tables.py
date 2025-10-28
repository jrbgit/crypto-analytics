"""add web archival tables

Revision ID: archival_001
Revises: 
Create Date: 2025-10-27 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'archival_001'
down_revision = None  # Update this to point to your latest migration
branch_labels = None
depends_on = None


def upgrade():
    """Add tables for web archival system."""
    
    # Create enum types
    op.execute("CREATE TYPE crawlstatus AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'cancelled', 'rate_limited')")
    op.execute("CREATE TYPE crawlfrequency AS ENUM ('daily', 'weekly', 'biweekly', 'monthly', 'on_demand')")
    op.execute("CREATE TYPE changetype AS ENUM ('content_added', 'content_removed', 'content_modified', 'structure_changed', 'resources_changed', 'major_redesign', 'no_change')")
    
    # crawl_jobs table
    op.create_table(
        'crawl_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('link_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('seed_url', sa.Text(), nullable=False),
        sa.Column('crawl_scope', sa.String(length=50), nullable=True),
        sa.Column('max_depth', sa.Integer(), nullable=True),
        sa.Column('max_pages', sa.Integer(), nullable=True),
        sa.Column('crawl_frequency', sa.Enum('daily', 'weekly', 'biweekly', 'monthly', 'on_demand', name='crawlfrequency'), nullable=True),
        sa.Column('url_patterns_include', sa.JSON(), nullable=True),
        sa.Column('url_patterns_exclude', sa.JSON(), nullable=True),
        sa.Column('respect_robots_txt', sa.Boolean(), nullable=True),
        sa.Column('crawler_engine', sa.String(length=20), nullable=True),
        sa.Column('use_javascript_rendering', sa.Boolean(), nullable=True),
        sa.Column('schedule_enabled', sa.Boolean(), nullable=True),
        sa.Column('next_scheduled_run', sa.DateTime(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'in_progress', 'completed', 'failed', 'cancelled', 'rate_limited', name='crawlstatus'), nullable=True),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('pages_crawled', sa.Integer(), nullable=True),
        sa.Column('bytes_downloaded', sa.BigInteger(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=True),
        sa.Column('rate_limit_delay', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['link_id'], ['project_links.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['crypto_projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_crawl_jobs_status_scheduled', 'crawl_jobs', ['status', 'next_scheduled_run'])
    op.create_index('idx_crawl_jobs_link_created', 'crawl_jobs', ['link_id', 'created_at'])
    op.create_index(op.f('ix_crawl_jobs_created_at'), 'crawl_jobs', ['created_at'])
    op.create_index(op.f('ix_crawl_jobs_job_uuid'), 'crawl_jobs', ['job_uuid'], unique=True)
    op.create_index(op.f('ix_crawl_jobs_link_id'), 'crawl_jobs', ['link_id'])
    op.create_index(op.f('ix_crawl_jobs_project_id'), 'crawl_jobs', ['project_id'])
    op.create_index(op.f('ix_crawl_jobs_status'), 'crawl_jobs', ['status'])
    
    # website_snapshots table
    op.create_table(
        'website_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('snapshot_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('link_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('crawl_job_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_timestamp', sa.DateTime(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(length=500), nullable=False),
        sa.Column('seed_url', sa.Text(), nullable=False),
        sa.Column('pages_captured', sa.Integer(), nullable=True),
        sa.Column('resources_captured', sa.Integer(), nullable=True),
        sa.Column('total_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('crawl_duration_seconds', sa.Float(), nullable=True),
        sa.Column('content_hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('structure_hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('resources_hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('full_site_hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('total_text_length', sa.Integer(), nullable=True),
        sa.Column('unique_pages_count', sa.Integer(), nullable=True),
        sa.Column('broken_links_count', sa.Integer(), nullable=True),
        sa.Column('technologies_detected', sa.JSON(), nullable=True),
        sa.Column('frameworks_detected', sa.JSON(), nullable=True),
        sa.Column('capture_quality_score', sa.Float(), nullable=True),
        sa.Column('javascript_errors_count', sa.Integer(), nullable=True),
        sa.Column('resource_load_failures', sa.Integer(), nullable=True),
        sa.Column('is_first_snapshot', sa.Boolean(), nullable=True),
        sa.Column('has_significant_changes', sa.Boolean(), nullable=True),
        sa.Column('change_type', sa.Enum('content_added', 'content_removed', 'content_modified', 'structure_changed', 'resources_changed', 'major_redesign', 'no_change', name='changetype'), nullable=True),
        sa.Column('change_score', sa.Float(), nullable=True),
        sa.Column('previous_snapshot_id', sa.Integer(), nullable=True),
        sa.Column('processing_complete', sa.Boolean(), nullable=True),
        sa.Column('index_generated', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['crawl_job_id'], ['crawl_jobs.id'], ),
        sa.ForeignKeyConstraint(['link_id'], ['project_links.id'], ),
        sa.ForeignKeyConstraint(['previous_snapshot_id'], ['website_snapshots.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['crypto_projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_snapshots_project_timestamp', 'website_snapshots', ['project_id', 'snapshot_timestamp'])
    op.create_index('idx_snapshots_link_version', 'website_snapshots', ['link_id', 'version_number'])
    op.create_index(op.f('ix_website_snapshots_domain'), 'website_snapshots', ['domain'])
    op.create_index(op.f('ix_website_snapshots_link_id'), 'website_snapshots', ['link_id'])
    op.create_index(op.f('ix_website_snapshots_project_id'), 'website_snapshots', ['project_id'])
    op.create_index(op.f('ix_website_snapshots_snapshot_timestamp'), 'website_snapshots', ['snapshot_timestamp'])
    op.create_index(op.f('ix_website_snapshots_snapshot_uuid'), 'website_snapshots', ['snapshot_uuid'], unique=True)
    
    # warc_files table
    op.create_table(
        'warc_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('crawl_job_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('file_format', sa.String(length=10), nullable=True),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('storage_backend', sa.String(length=20), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('file_hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('compression', sa.String(length=20), nullable=True),
        sa.Column('warc_version', sa.String(length=10), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=True),
        sa.Column('pages_count', sa.Integer(), nullable=True),
        sa.Column('resources_count', sa.Integer(), nullable=True),
        sa.Column('has_cdx_index', sa.Boolean(), nullable=True),
        sa.Column('cdx_file_path', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['crawl_job_id'], ['crawl_jobs.id'], ),
        sa.ForeignKeyConstraint(['snapshot_id'], ['website_snapshots.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_warc_files_snapshot', 'warc_files', ['snapshot_id', 'created_at'])
    op.create_index(op.f('ix_warc_files_created_at'), 'warc_files', ['created_at'])
    op.create_index(op.f('ix_warc_files_crawl_job_id'), 'warc_files', ['crawl_job_id'])
    op.create_index(op.f('ix_warc_files_file_uuid'), 'warc_files', ['file_uuid'], unique=True)
    op.create_index(op.f('ix_warc_files_snapshot_id'), 'warc_files', ['snapshot_id'])
    
    # cdx_records table
    op.create_table(
        'cdx_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('warc_file_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_id', sa.Integer(), nullable=False),
        sa.Column('url_key', sa.String(length=2000), nullable=False),
        sa.Column('timestamp', sa.String(length=14), nullable=False),
        sa.Column('original_url', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('digest', sa.String(length=64), nullable=True),
        sa.Column('redirect_url', sa.Text(), nullable=True),
        sa.Column('warc_filename', sa.String(length=500), nullable=False),
        sa.Column('warc_record_offset', sa.BigInteger(), nullable=False),
        sa.Column('warc_record_length', sa.Integer(), nullable=True),
        sa.Column('content_length', sa.Integer(), nullable=True),
        sa.Column('charset', sa.String(length=50), nullable=True),
        sa.Column('languages', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['snapshot_id'], ['website_snapshots.id'], ),
        sa.ForeignKeyConstraint(['warc_file_id'], ['warc_files.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_cdx_url_timestamp', 'cdx_records', ['url_key', 'timestamp'])
    op.create_index('idx_cdx_snapshot_url', 'cdx_records', ['snapshot_id', 'url_key'])
    op.create_index(op.f('ix_cdx_records_snapshot_id'), 'cdx_records', ['snapshot_id'])
    op.create_index(op.f('ix_cdx_records_url_key'), 'cdx_records', ['url_key'])
    op.create_index(op.f('ix_cdx_records_warc_file_id'), 'cdx_records', ['warc_file_id'])
    
    # snapshot_change_detection table
    op.create_table(
        'snapshot_change_detection',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('old_snapshot_id', sa.Integer(), nullable=False),
        sa.Column('new_snapshot_id', sa.Integer(), nullable=False),
        sa.Column('change_type', sa.Enum('content_added', 'content_removed', 'content_modified', 'structure_changed', 'resources_changed', 'major_redesign', 'no_change', name='changetype'), nullable=False),
        sa.Column('change_score', sa.Float(), nullable=True),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('text_added_bytes', sa.Integer(), nullable=True),
        sa.Column('text_removed_bytes', sa.Integer(), nullable=True),
        sa.Column('text_changed_percentage', sa.Float(), nullable=True),
        sa.Column('html_structure_diff_score', sa.Float(), nullable=True),
        sa.Column('new_sections_count', sa.Integer(), nullable=True),
        sa.Column('removed_sections_count', sa.Integer(), nullable=True),
        sa.Column('resources_added_count', sa.Integer(), nullable=True),
        sa.Column('resources_removed_count', sa.Integer(), nullable=True),
        sa.Column('resources_changed_count', sa.Integer(), nullable=True),
        sa.Column('changes_detected', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('layout_changed', sa.Boolean(), nullable=True),
        sa.Column('style_changed', sa.Boolean(), nullable=True),
        sa.Column('pages_changed', sa.JSON(), nullable=True),
        sa.Column('pages_added', sa.JSON(), nullable=True),
        sa.Column('pages_removed', sa.JSON(), nullable=True),
        sa.Column('is_significant_change', sa.Boolean(), nullable=True),
        sa.Column('requires_reanalysis', sa.Boolean(), nullable=True),
        sa.Column('diff_computed_at', sa.DateTime(), nullable=True),
        sa.Column('computation_time_seconds', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['new_snapshot_id'], ['website_snapshots.id'], ),
        sa.ForeignKeyConstraint(['old_snapshot_id'], ['website_snapshots.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_change_detection_snapshots', 'snapshot_change_detection', ['old_snapshot_id', 'new_snapshot_id'])
    op.create_index('idx_change_detection_significant', 'snapshot_change_detection', ['is_significant_change', 'change_score'])
    op.create_index(op.f('ix_snapshot_change_detection_new_snapshot_id'), 'snapshot_change_detection', ['new_snapshot_id'])
    op.create_index(op.f('ix_snapshot_change_detection_old_snapshot_id'), 'snapshot_change_detection', ['old_snapshot_id'])
    
    # crawl_schedules table
    op.create_table(
        'crawl_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('link_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('frequency', sa.Enum('daily', 'weekly', 'biweekly', 'monthly', 'on_demand', name='crawlfrequency'), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('min_market_cap', sa.Float(), nullable=True),
        sa.Column('change_frequency_observed', sa.String(length=50), nullable=True),
        sa.Column('last_significant_change', sa.DateTime(), nullable=True),
        sa.Column('average_change_score', sa.Float(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=False),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('consecutive_no_change_count', sa.Integer(), nullable=True),
        sa.Column('is_paused', sa.Boolean(), nullable=True),
        sa.Column('pause_reason', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['link_id'], ['project_links.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['crypto_projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('link_id')
    )
    op.create_index('idx_schedules_enabled_next_run', 'crawl_schedules', ['enabled', 'next_run_at'])
    op.create_index(op.f('ix_crawl_schedules_next_run_at'), 'crawl_schedules', ['next_run_at'])


def downgrade():
    """Remove web archival tables."""
    
    # Drop tables in reverse order
    op.drop_table('crawl_schedules')
    op.drop_table('snapshot_change_detection')
    op.drop_table('cdx_records')
    op.drop_table('warc_files')
    op.drop_table('website_snapshots')
    op.drop_table('crawl_jobs')
    
    # Drop enum types
    op.execute("DROP TYPE changetype")
    op.execute("DROP TYPE crawlfrequency")
    op.execute("DROP TYPE crawlstatus")
