-- Migration 007: Add Reddit status tracking columns
-- Adds columns for tracking Reddit community health and status

BEGIN;

-- Add Reddit status tracking columns to project_links table
ALTER TABLE project_links 
ADD COLUMN current_reddit_status VARCHAR(50) DEFAULT 'unknown',
ADD COLUMN last_reddit_check TIMESTAMP WITH TIME ZONE,
ADD COLUMN reddit_consecutive_failures INTEGER DEFAULT 0,
ADD COLUMN reddit_inactive_90_days BOOLEAN DEFAULT FALSE,
ADD COLUMN reddit_subscriber_count INTEGER,
ADD COLUMN reddit_last_post_date TIMESTAMP WITH TIME ZONE;

-- Create index for reddit status queries
CREATE INDEX idx_project_links_reddit_status ON project_links(current_reddit_status);
CREATE INDEX idx_project_links_reddit_check ON project_links(last_reddit_check);

COMMIT;