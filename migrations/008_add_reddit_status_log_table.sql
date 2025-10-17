-- Migration 008: Add Reddit status log table
-- Creates table for detailed logging of Reddit community status checks

BEGIN;

-- Create Reddit status log table for detailed tracking
CREATE TABLE reddit_status_log (
    id SERIAL PRIMARY KEY,
    link_id INTEGER NOT NULL REFERENCES project_links(id),
    
    -- Status information
    status_type VARCHAR(50) NOT NULL, -- 'success', 'inactive_90d', 'access_denied', 'not_found', 'private', 'rate_limited', 'error'
    status_message TEXT,
    
    -- Community details
    posts_found INTEGER DEFAULT 0,
    subscriber_count INTEGER,
    last_post_date TIMESTAMP WITH TIME ZONE,
    
    -- Error details
    error_type VARCHAR(100),
    error_details TEXT,
    
    -- Timestamps
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX idx_reddit_status_log_link_id ON reddit_status_log(link_id);
CREATE INDEX idx_reddit_status_log_type ON reddit_status_log(status_type);
CREATE INDEX idx_reddit_status_log_checked_at ON reddit_status_log(checked_at);

COMMIT;