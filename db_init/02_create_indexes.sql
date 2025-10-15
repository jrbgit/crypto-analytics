-- Performance optimization indexes for crypto analytics database

-- ===============================================
-- PRIMARY PERFORMANCE INDEXES
-- ===============================================

-- Crypto projects indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_code ON crypto_projects (code);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_rank ON crypto_projects (rank) WHERE rank IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_market_cap ON crypto_projects (market_cap DESC) WHERE market_cap IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_volume ON crypto_projects (volume_24h DESC) WHERE volume_24h IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_price_change ON crypto_projects (price_change_24h DESC) WHERE price_change_24h IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_updated_at ON crypto_projects (updated_at DESC);

-- Categories JSON index for fast filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_categories_gin ON crypto_projects USING GIN (categories);

-- Project links indexes - CRITICAL for scraper performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_links_project_id ON project_links (project_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_links_type_active ON project_links (link_type, is_active) WHERE is_active = true;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_links_needs_analysis ON project_links (needs_analysis, link_type, last_scraped) WHERE needs_analysis = true;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_links_scraped_success ON project_links (last_scraped DESC, scrape_success) WHERE scrape_success = true;

-- Composite index for scraper queue management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_links_scraper_queue ON project_links (link_type, needs_analysis, is_active, last_scraped) 
WHERE is_active = true;

-- URL hash for duplicate detection
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_links_url_hash ON project_links USING hash (url);

-- ===============================================
-- CONTENT ANALYSIS INDEXES
-- ===============================================

-- Link content analysis indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_link_id ON link_content_analysis (link_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_created_at ON link_content_analysis (created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_content_hash ON link_content_analysis (content_hash) WHERE content_hash IS NOT NULL;

-- Score-based indexes for ranking queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_tech_score ON link_content_analysis (technical_depth_score DESC) 
WHERE technical_depth_score IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_quality_score ON link_content_analysis (content_quality_score DESC) 
WHERE content_quality_score IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_confidence ON link_content_analysis (confidence_score DESC) 
WHERE confidence_score IS NOT NULL;

-- Composite index for analysis filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_scores_composite ON link_content_analysis 
(technical_depth_score DESC, content_quality_score DESC, confidence_score DESC) 
WHERE technical_depth_score IS NOT NULL AND content_quality_score IS NOT NULL;

-- JSON indexes for technology and features analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_tech_stack_gin ON link_content_analysis USING GIN (technology_stack);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_core_features_gin ON link_content_analysis USING GIN (core_features);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_use_cases_gin ON link_content_analysis USING GIN (use_cases);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_partnerships_gin ON link_content_analysis USING GIN (partnerships);

-- Full-text search indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_summary_fts ON link_content_analysis 
USING GIN (to_tsvector('english', COALESCE(summary, '') || ' ' || COALESCE(page_title, '')));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_technical_summary_fts ON link_content_analysis 
USING GIN (to_tsvector('english', COALESCE(technical_summary, '')));

-- Document type specific indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_document_type ON link_content_analysis (document_type, page_count) 
WHERE document_type IS NOT NULL;

-- Boolean field indexes for fast filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_has_tokenomics ON link_content_analysis (has_tokenomics) 
WHERE has_tokenomics = true;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_has_competitive ON link_content_analysis (has_competitive_analysis) 
WHERE has_competitive_analysis = true;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_team_described ON link_content_analysis (team_described) 
WHERE team_described = true;

-- ===============================================
-- RAW CONTENT INDEXES
-- ===============================================

-- Raw content indexes
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_raw_content_hash ON link_raw_content (content_hash);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_raw_content_link_id ON link_raw_content (link_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_raw_content_type ON link_raw_content (content_type);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_raw_content_size ON link_raw_content (content_size DESC) WHERE content_size IS NOT NULL;

-- ===============================================
-- CHANGE TRACKING INDEXES
-- ===============================================

-- Project changes indexes for audit queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_changes_project_id ON project_changes (project_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_changes_created_at ON project_changes (created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_changes_field_name ON project_changes (field_name, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_changes_type_source ON project_changes (change_type, data_source, created_at DESC);

-- Composite index for change analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_changes_composite ON project_changes 
(project_id, field_name, created_at DESC);

-- ===============================================
-- ANALYTICS AND REPORTING INDEXES
-- ===============================================

-- Project analysis indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_analysis_project_id ON project_analysis (project_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_analysis_overall_score ON project_analysis (overall_score DESC) 
WHERE overall_score IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_analysis_tech_score ON project_analysis (technology_score DESC) 
WHERE technology_score IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_analysis_updated_at ON project_analysis (updated_at DESC);

-- Investment recommendation index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_analysis_recommendation ON project_analysis 
(investment_recommendation, overall_score DESC) WHERE investment_recommendation IS NOT NULL;

-- Social sentiment history indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sentiment_project_id ON social_sentiment_history (project_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sentiment_measured_at ON social_sentiment_history (measured_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sentiment_link_type ON social_sentiment_history (link_type, measured_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sentiment_score ON social_sentiment_history (sentiment_score DESC) 
WHERE sentiment_score IS NOT NULL;

-- Time-series composite index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sentiment_timeseries ON social_sentiment_history 
(project_id, link_type, measured_at DESC);

-- Competitor analysis indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_competitors_project_id ON project_competitors (project_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_competitors_competitor_id ON project_competitors (competitor_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_competitors_strength ON project_competitors (strength DESC) 
WHERE strength IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_competitors_type ON project_competitors (relationship_type, strength DESC);

-- ===============================================
-- API USAGE TRACKING INDEXES
-- ===============================================

-- API usage indexes for monitoring
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_usage_timestamp ON api_usage (request_timestamp DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_usage_provider ON api_usage (api_provider, request_timestamp DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_usage_endpoint ON api_usage (endpoint, request_timestamp DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_usage_status ON api_usage (response_status, request_timestamp DESC);

-- Credits and rate limiting
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_usage_credits ON api_usage (credits_used, request_timestamp DESC) 
WHERE credits_used > 1;

-- ===============================================
-- PARTIAL INDEXES FOR SPECIFIC QUERIES
-- ===============================================

-- High-value projects (market cap > 1B)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_high_value ON crypto_projects (market_cap DESC, rank) 
WHERE market_cap > 1000000000;

-- Recent analyses (last 30 days)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_recent ON link_content_analysis 
(created_at DESC, technical_depth_score DESC) 
WHERE created_at > (NOW() - INTERVAL '30 days');

-- Failed scrapes for retry analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_links_failed_scrapes ON project_links (last_scraped, link_type) 
WHERE scrape_success = false AND is_active = true;

-- High-confidence analyses
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_high_confidence ON link_content_analysis 
(confidence_score DESC, technical_depth_score DESC) 
WHERE confidence_score > 0.8;

-- ===============================================
-- EXPRESSION INDEXES FOR COMPLEX QUERIES
-- ===============================================

-- Price change magnitude (absolute value)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_price_change_abs ON crypto_projects 
(ABS(price_change_24h) DESC) WHERE price_change_24h IS NOT NULL;

-- Combined score calculation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_combined_score ON link_content_analysis 
((COALESCE(technical_depth_score, 0) + COALESCE(content_quality_score, 0)) / 2.0 DESC) 
WHERE technical_depth_score IS NOT NULL OR content_quality_score IS NOT NULL;

-- Content richness indicator
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_content_richness ON link_content_analysis 
(total_word_count DESC, pages_analyzed DESC) 
WHERE total_word_count IS NOT NULL AND total_word_count > 1000;

-- ===============================================
-- STATISTICS UPDATES
-- ===============================================

-- Update table statistics for query planner
-- This should be run after initial data load
-- ANALYZE crypto_projects;
-- ANALYZE project_links;
-- ANALYZE link_content_analysis;
-- ANALYZE link_raw_content;
-- ANALYZE project_changes;

COMMENT ON INDEX idx_links_scraper_queue IS 'Optimizes scraper queue queries for pending analysis';
COMMENT ON INDEX idx_analysis_scores_composite IS 'Enables fast filtering by multiple quality scores';
COMMENT ON INDEX idx_analysis_summary_fts IS 'Full-text search across summaries and titles';
COMMENT ON INDEX idx_sentiment_timeseries IS 'Time-series sentiment analysis queries';
COMMENT ON INDEX idx_projects_high_value IS 'Partial index for high market cap projects';