-- Migration 006: Add website status tracking
-- Track website health, robots.txt restrictions, parked domains, and scraping results

BEGIN;

-- Add website status tracking table
CREATE TABLE website_status_log (
    id SERIAL PRIMARY KEY,
    link_id INTEGER NOT NULL REFERENCES project_links(id),
    
    -- Status information
    status_type VARCHAR(50) NOT NULL, -- 'success', 'robots_blocked', 'parked_domain', 'dns_failure', 'server_error', 'timeout', 'content_error'
    status_message TEXT, -- Detailed message about the status
    
    -- Scraping results
    pages_attempted INTEGER DEFAULT 0,
    pages_successful INTEGER DEFAULT 0,
    pages_parked INTEGER DEFAULT 0, -- Number of parked/for-sale pages detected
    total_content_length INTEGER DEFAULT 0,
    
    -- HTTP/Network details
    http_status_code INTEGER,
    response_time_ms INTEGER,
    dns_resolved BOOLEAN,
    ssl_valid BOOLEAN,
    
    -- Content analysis
    has_robots_txt BOOLEAN,
    robots_allows_scraping BOOLEAN,
    detected_cms VARCHAR(100), -- WordPress, Squarespace, etc.
    detected_parking_service VARCHAR(100), -- GoDaddy, Sedo, etc.
    
    -- Error details
    error_type VARCHAR(100), -- 'connection_error', 'parse_error', 'content_corruption', etc.
    error_details TEXT,
    
    -- Timestamps
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes for common queries
    INDEX idx_website_status_link_id (link_id),
    INDEX idx_website_status_type (status_type),
    INDEX idx_website_status_checked_at (checked_at)
);

-- Add current website status to project_links table
ALTER TABLE project_links 
ADD COLUMN current_website_status VARCHAR(50) DEFAULT 'unknown',
ADD COLUMN last_status_check TIMESTAMP WITH TIME ZONE,
ADD COLUMN consecutive_failures INTEGER DEFAULT 0,
ADD COLUMN first_failure_date TIMESTAMP WITH TIME ZONE,
ADD COLUMN domain_parked_detected BOOLEAN DEFAULT FALSE,
ADD COLUMN robots_txt_blocks_scraping BOOLEAN DEFAULT FALSE;

-- Create index for website status queries
CREATE INDEX idx_project_links_website_status ON project_links(current_website_status);

COMMIT;