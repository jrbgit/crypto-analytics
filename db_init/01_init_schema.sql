-- PostgreSQL initialization script for crypto analytics
-- This script creates the optimized schema and indexes

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create optimized tables with partitioning support

-- Projects table (same structure, better indexes)
CREATE TABLE IF NOT EXISTS crypto_projects (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    
    -- Basic project info
    rank INTEGER,
    age INTEGER,
    color VARCHAR(10),
    
    -- Supply information
    circulating_supply NUMERIC(30,8),
    total_supply NUMERIC(30,8),
    max_supply NUMERIC(30,8),
    
    -- Market data
    current_price NUMERIC(20,8),
    market_cap NUMERIC(30,2),
    volume_24h NUMERIC(30,2),
    
    -- Price deltas
    price_change_1h NUMERIC(10,4),
    price_change_24h NUMERIC(10,4),
    price_change_7d NUMERIC(10,4),
    price_change_30d NUMERIC(10,4),
    price_change_90d NUMERIC(10,4),
    price_change_1y NUMERIC(10,4),
    
    -- Exchange data
    exchanges_count INTEGER,
    markets_count INTEGER,
    pairs_count INTEGER,
    
    -- All time high
    ath_usd NUMERIC(20,8),
    
    -- Categories (JSONB for better performance)
    categories JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_api_fetch TIMESTAMP WITH TIME ZONE
);

-- Project links table
CREATE TABLE IF NOT EXISTS project_links (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES crypto_projects(id) ON DELETE CASCADE,
    
    link_type VARCHAR(50) NOT NULL,
    url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    
    -- LLM analysis flags
    needs_analysis BOOLEAN DEFAULT true,
    last_scraped TIMESTAMP WITH TIME ZONE,
    scrape_success BOOLEAN,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Project images table
CREATE TABLE IF NOT EXISTS project_images (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES crypto_projects(id) ON DELETE CASCADE,
    
    image_type VARCHAR(20) NOT NULL,
    url TEXT NOT NULL,
    local_path VARCHAR(500),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Separate table for raw content (better memory management)
CREATE TABLE IF NOT EXISTS link_raw_content (
    id SERIAL PRIMARY KEY,
    link_id INTEGER NOT NULL REFERENCES project_links(id) ON DELETE CASCADE,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    raw_content TEXT,
    content_type VARCHAR(50),
    content_size INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Partitioned analysis table by date
CREATE TABLE IF NOT EXISTS link_content_analysis (
    id SERIAL PRIMARY KEY,
    link_id INTEGER NOT NULL REFERENCES project_links(id) ON DELETE CASCADE,
    
    -- Content metadata
    content_hash VARCHAR(64),
    page_title VARCHAR(500),
    meta_description TEXT,
    pages_analyzed INTEGER DEFAULT 1,
    total_word_count INTEGER,
    
    -- Core technology information
    technology_stack JSONB,
    blockchain_platform VARCHAR(100),
    consensus_mechanism VARCHAR(100),
    
    -- Key value propositions
    core_features JSONB,
    use_cases JSONB,
    unique_value_proposition TEXT,
    target_audience JSONB,
    
    -- Team and organization
    team_members JSONB,
    founders JSONB,
    team_size_estimate INTEGER,
    advisors JSONB,
    
    -- Business information
    partnerships JSONB,
    investors JSONB,
    funding_raised VARCHAR(200),
    
    -- Development and innovation
    innovations JSONB,
    development_stage VARCHAR(50),
    roadmap_items JSONB,
    
    -- Analysis scores and metadata
    technical_depth_score INTEGER CHECK (technical_depth_score >= 1 AND technical_depth_score <= 10),
    marketing_vs_tech_ratio NUMERIC(3,2) CHECK (marketing_vs_tech_ratio >= 0 AND marketing_vs_tech_ratio <= 1),
    content_quality_score INTEGER CHECK (content_quality_score >= 1 AND content_quality_score <= 10),
    red_flags JSONB,
    confidence_score NUMERIC(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    
    -- Document-specific fields
    document_structure_score INTEGER CHECK (document_structure_score >= 1 AND document_structure_score <= 10),
    document_type VARCHAR(20),
    page_count INTEGER,
    extraction_method VARCHAR(50),
    
    -- Tokenomics and economics
    has_tokenomics BOOLEAN DEFAULT false,
    tokenomics_summary TEXT,
    token_distribution_described BOOLEAN DEFAULT false,
    economic_model_clarity INTEGER CHECK (economic_model_clarity >= 1 AND economic_model_clarity <= 10),
    
    -- Enhanced analysis fields
    use_case_viability_score INTEGER CHECK (use_case_viability_score >= 1 AND use_case_viability_score <= 10),
    target_market_defined BOOLEAN DEFAULT false,
    technical_innovations_score INTEGER CHECK (technical_innovations_score >= 1 AND technical_innovations_score <= 10),
    implementation_details_score INTEGER CHECK (implementation_details_score >= 1 AND implementation_details_score <= 10),
    
    -- Competitive analysis
    has_competitive_analysis BOOLEAN DEFAULT false,
    competitors_mentioned JSONB,
    competitive_advantages_claimed JSONB,
    
    -- Team and development
    team_described BOOLEAN DEFAULT false,
    team_expertise_apparent BOOLEAN DEFAULT false,
    development_roadmap_present BOOLEAN DEFAULT false,
    roadmap_specificity INTEGER CHECK (roadmap_specificity >= 1 AND roadmap_specificity <= 10),
    
    -- Risk and validation
    plagiarism_indicators JSONB,
    vague_claims JSONB,
    unrealistic_promises JSONB,
    
    -- Market and adoption
    market_size_analysis BOOLEAN DEFAULT false,
    adoption_strategy_described BOOLEAN DEFAULT false,
    partnerships_mentioned JSONB,
    
    -- Legacy fields for backward compatibility
    summary TEXT,
    key_points JSONB,
    sentiment_score NUMERIC(3,2) CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    categories JSONB,
    entities JSONB,
    recent_updates JSONB,
    technical_summary TEXT,
    
    -- Analysis metadata
    model_used VARCHAR(50),
    tokens_consumed INTEGER,
    analysis_version VARCHAR(20) DEFAULT '2.0',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Project changes table for audit trail
CREATE TABLE IF NOT EXISTS project_changes (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES crypto_projects(id) ON DELETE CASCADE,
    
    field_name VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    change_type VARCHAR(20) NOT NULL DEFAULT 'UPDATE',
    
    -- Metadata
    data_source VARCHAR(50) DEFAULT 'livecoinwatch',
    api_endpoint VARCHAR(200),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Project analysis summary table
CREATE TABLE IF NOT EXISTS project_analysis (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES crypto_projects(id) ON DELETE CASCADE,
    
    -- Overall analysis
    overall_summary TEXT,
    risk_assessment TEXT,
    opportunity_assessment TEXT,
    
    -- Scores (0-100)
    technology_score NUMERIC(5,2) CHECK (technology_score >= 0 AND technology_score <= 100),
    community_score NUMERIC(5,2) CHECK (community_score >= 0 AND community_score <= 100),
    market_performance_score NUMERIC(5,2) CHECK (market_performance_score >= 0 AND market_performance_score <= 100),
    development_activity_score NUMERIC(5,2) CHECK (development_activity_score >= 0 AND development_activity_score <= 100),
    overall_score NUMERIC(5,2) CHECK (overall_score >= 0 AND overall_score <= 100),
    
    -- Market analysis
    price_trend_analysis TEXT,
    volume_analysis TEXT,
    market_cap_analysis TEXT,
    
    -- Social sentiment
    social_sentiment_score NUMERIC(3,2) CHECK (social_sentiment_score >= -1 AND social_sentiment_score <= 1),
    social_engagement_score NUMERIC(5,2) CHECK (social_engagement_score >= 0 AND social_engagement_score <= 100),
    community_growth_trend VARCHAR(20) CHECK (community_growth_trend IN ('growing', 'stable', 'declining')),
    
    -- Recommendations
    investment_recommendation VARCHAR(20) CHECK (investment_recommendation IN ('buy', 'hold', 'sell', 'avoid')),
    time_horizon VARCHAR(20) CHECK (time_horizon IN ('short', 'medium', 'long')),
    risk_level VARCHAR(20) CHECK (risk_level IN ('low', 'medium', 'high')),
    
    -- Analysis metadata
    data_sources_used JSONB,
    analysis_confidence NUMERIC(3,2) CHECK (analysis_confidence >= 0 AND analysis_confidence <= 1),
    model_version VARCHAR(20),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- API usage tracking
CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    
    api_provider VARCHAR(50) NOT NULL,
    endpoint VARCHAR(200) NOT NULL,
    
    -- Request details
    request_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    response_status INTEGER,
    credits_used INTEGER DEFAULT 1,
    
    -- Response metadata
    response_size INTEGER,
    response_time NUMERIC(8,3),
    rate_limit_remaining INTEGER,
    
    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- New tables for enhanced analytics

-- Social sentiment tracking over time
CREATE TABLE IF NOT EXISTS social_sentiment_history (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES crypto_projects(id) ON DELETE CASCADE,
    link_type VARCHAR(50) NOT NULL,
    sentiment_score NUMERIC(3,2) CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    engagement_metrics JSONB,
    measured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Competitor analysis relationships
CREATE TABLE IF NOT EXISTS project_competitors (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES crypto_projects(id) ON DELETE CASCADE,
    competitor_id INTEGER NOT NULL REFERENCES crypto_projects(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) CHECK (relationship_type IN ('direct', 'indirect', 'ecosystem')),
    strength NUMERIC(3,2) CHECK (strength >= 0 AND strength <= 1),
    identified_by VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT no_self_competition CHECK (project_id != competitor_id),
    CONSTRAINT unique_competition UNIQUE (project_id, competitor_id)
);

COMMENT ON TABLE crypto_projects IS 'Main cryptocurrency projects with market data';
COMMENT ON TABLE project_links IS 'All social media and official links for projects';
COMMENT ON TABLE link_content_analysis IS 'LLM analysis results for scraped content';
COMMENT ON TABLE link_raw_content IS 'Raw scraped content separated for better memory management';
COMMENT ON TABLE social_sentiment_history IS 'Time-series sentiment data for trend analysis';
COMMENT ON TABLE project_competitors IS 'Competitive relationships between projects';