"""
Database models for crypto analytics with change tracking.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, JSON, ForeignKey, NUMERIC
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import json

Base = declarative_base()


class CryptoProject(Base):
    """Main table for cryptocurrency projects."""
    
    __tablename__ = 'crypto_projects'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(100), unique=True, index=True)  # e.g., 'BTC', 'AVAX' - increased to handle long codes
    name = Column(String(200), nullable=False)
    
    # Basic project info
    rank = Column(Integer)
    age = Column(Integer)  # Days since launch
    color = Column(String(10))  # Hex color code
    
    # Supply information (using NUMERIC(40,8) for very large cryptocurrency supplies)
    circulating_supply = Column(NUMERIC(40, 8))
    total_supply = Column(NUMERIC(40, 8))
    max_supply = Column(NUMERIC(40, 8))
    
    # Market data (using NUMERIC(40,8) for precision and very large values)
    current_price = Column(NUMERIC(40, 8))
    market_cap = Column(NUMERIC(40, 8))
    volume_24h = Column(NUMERIC(40, 8))
    
    # Price deltas
    price_change_1h = Column(Float)
    price_change_24h = Column(Float)
    price_change_7d = Column(Float)
    price_change_30d = Column(Float)
    price_change_90d = Column(Float)
    price_change_1y = Column(Float)
    
    # Exchange data
    exchanges_count = Column(Integer)
    markets_count = Column(Integer)
    pairs_count = Column(Integer)
    
    # All time high (using NUMERIC(40,8) to handle very large values)
    ath_usd = Column(NUMERIC(40, 8))
    
    # Categories (stored as JSON array)
    categories = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_api_fetch = Column(DateTime)
    
    # Relationships
    links = relationship("ProjectLink", back_populates="project", cascade="all, delete-orphan")
    images = relationship("ProjectImage", back_populates="project", cascade="all, delete-orphan")
    changes = relationship("ProjectChange", back_populates="project", cascade="all, delete-orphan")
    analysis = relationship("ProjectAnalysis", back_populates="project", cascade="all, delete-orphan")


class ProjectLink(Base):
    """Social media and official links for crypto projects."""
    
    __tablename__ = 'project_links'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('crypto_projects.id'), nullable=False)
    
    link_type = Column(String(50), nullable=False)  # website, twitter, reddit, etc.
    url = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # LLM analysis flags
    needs_analysis = Column(Boolean, default=True)
    last_scraped = Column(DateTime)
    scrape_success = Column(Boolean)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("CryptoProject", back_populates="links")
    content_analysis = relationship("LinkContentAnalysis", back_populates="link", cascade="all, delete-orphan")


class ProjectImage(Base):
    """Images and icons for crypto projects."""
    
    __tablename__ = 'project_images'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('crypto_projects.id'), nullable=False)
    
    image_type = Column(String(20), nullable=False)  # png32, png64, webp32, webp64
    url = Column(Text, nullable=False)
    local_path = Column(String(500))  # If downloaded locally
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship("CryptoProject", back_populates="images")


class ProjectChange(Base):
    """Track all changes to project data for historical analysis."""
    
    __tablename__ = 'project_changes'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('crypto_projects.id'), nullable=False)
    
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text)  # JSON serialized for complex types
    new_value = Column(Text)  # JSON serialized for complex types
    change_type = Column(String(20), nullable=False)  # INSERT, UPDATE, DELETE
    
    # Metadata
    data_source = Column(String(50), default='livecoinwatch')
    api_endpoint = Column(String(200))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship("CryptoProject", back_populates="changes")
    
    def serialize_value(self, value: Any) -> str:
        """Serialize complex values to JSON string."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return json.dumps(value, default=str)


class LinkContentAnalysis(Base):
    """Comprehensive LLM analysis results for scraped website content."""
    
    __tablename__ = 'link_content_analysis'
    
    id = Column(Integer, primary_key=True)
    link_id = Column(Integer, ForeignKey('project_links.id'), nullable=False)
    
    # Scraped content metadata
    raw_content = Column(Text)
    content_hash = Column(String(64))  # SHA256 hash to detect changes
    page_title = Column(String(500))
    meta_description = Column(Text)
    pages_analyzed = Column(Integer, default=1)
    total_word_count = Column(Integer)
    
    # Core technology information
    technology_stack = Column(JSON)  # List of technologies
    blockchain_platform = Column(String(100))
    consensus_mechanism = Column(String(100))
    
    # Key value propositions
    core_features = Column(JSON)  # Main features/capabilities
    use_cases = Column(JSON)  # Primary use cases
    unique_value_proposition = Column(Text)
    target_audience = Column(JSON)  # Target market segments
    
    # Team and organization
    team_members = Column(JSON)  # [{"name": "...", "role": "...", "background": "..."}]
    founders = Column(JSON)  # Founder names
    team_size_estimate = Column(Integer)
    advisors = Column(JSON)  # Advisor names
    
    # Business information
    partnerships = Column(JSON)  # Strategic partnerships
    investors = Column(JSON)  # Investment firms/angels
    funding_raised = Column(String(200))  # Funding information
    
    # Development and innovation
    innovations = Column(JSON)  # Novel approaches or features
    development_stage = Column(String(50))  # concept, development, testnet, mainnet, mature
    roadmap_items = Column(JSON)  # Key roadmap milestones
    
    # Analysis scores and metadata
    technical_depth_score = Column(Integer)  # 1-10
    marketing_vs_tech_ratio = Column(Float)  # 0-1
    content_quality_score = Column(Integer)  # 1-10
    red_flags = Column(JSON)  # Potential concerns or warning signs
    confidence_score = Column(Float)  # 0-1
    
    # Whitepaper-specific fields
    document_structure_score = Column(Integer)  # 1-10, organization and clarity
    document_type = Column(String(20))  # 'pdf', 'webpage', etc.
    page_count = Column(Integer)  # For PDFs
    extraction_method = Column(String(50))  # Which method was used to extract content
    
    # Tokenomics and economics
    has_tokenomics = Column(Boolean, default=False)
    tokenomics_summary = Column(Text)
    token_distribution_described = Column(Boolean, default=False)
    economic_model_clarity = Column(Integer)  # 1-10
    
    # Use case and value proposition (enhanced)
    use_case_viability_score = Column(Integer)  # 1-10
    target_market_defined = Column(Boolean, default=False)
    
    # Technical innovation (enhanced)
    technical_innovations_score = Column(Integer)  # 1-10
    implementation_details_score = Column(Integer)  # 1-10
    
    # Competitive analysis
    has_competitive_analysis = Column(Boolean, default=False)
    competitors_mentioned = Column(JSON)  # List of competitors
    competitive_advantages_claimed = Column(JSON)  # List of claimed advantages
    
    # Team and development (enhanced)
    team_described = Column(Boolean, default=False)
    team_expertise_apparent = Column(Boolean, default=False)
    development_roadmap_present = Column(Boolean, default=False)
    roadmap_specificity = Column(Integer)  # 1-10
    
    # Risk and validation
    plagiarism_indicators = Column(JSON)  # Signs of copied content
    vague_claims = Column(JSON)  # Vague or unsubstantiated claims
    unrealistic_promises = Column(JSON)  # Promises that seem unrealistic
    
    # Market and adoption
    market_size_analysis = Column(Boolean, default=False)
    adoption_strategy_described = Column(Boolean, default=False)
    partnerships_mentioned = Column(JSON)  # Partnerships mentioned in document
    
    # Legacy fields for backward compatibility
    summary = Column(Text)  # Overall summary
    key_points = Column(JSON)  # Key insights
    sentiment_score = Column(Float)  # -1 to 1
    categories = Column(JSON)  # Detected categories
    entities = Column(JSON)  # Named entities
    recent_updates = Column(JSON)  # Recent developments
    technical_summary = Column(Text)  # Technical summary
    
    # Analysis metadata
    model_used = Column(String(50))
    tokens_consumed = Column(Integer)
    analysis_version = Column(String(20), default='2.0')
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    link = relationship("ProjectLink", back_populates="content_analysis")


class ProjectAnalysis(Base):
    """Comprehensive project analysis combining all data sources."""
    
    __tablename__ = 'project_analysis'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('crypto_projects.id'), nullable=False)
    
    # Overall analysis
    overall_summary = Column(Text)
    risk_assessment = Column(Text)
    opportunity_assessment = Column(Text)
    
    # Scores (0-100)
    technology_score = Column(Float)
    community_score = Column(Float)
    market_performance_score = Column(Float)
    development_activity_score = Column(Float)
    overall_score = Column(Float)
    
    # Market analysis
    price_trend_analysis = Column(Text)
    volume_analysis = Column(Text)
    market_cap_analysis = Column(Text)
    
    # Social sentiment
    social_sentiment_score = Column(Float)  # -1 to 1
    social_engagement_score = Column(Float)  # 0-100
    community_growth_trend = Column(String(20))  # growing, stable, declining
    
    # Recommendations
    investment_recommendation = Column(String(20))  # buy, hold, sell, avoid
    time_horizon = Column(String(20))  # short, medium, long
    risk_level = Column(String(20))  # low, medium, high
    
    # Analysis metadata
    data_sources_used = Column(JSON)  # List of data sources
    analysis_confidence = Column(Float)  # 0-1
    model_version = Column(String(20))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("CryptoProject", back_populates="analysis")


class APIUsage(Base):
    """Track API usage for rate limiting and credit management."""
    
    __tablename__ = 'api_usage'
    
    id = Column(Integer, primary_key=True)
    
    api_provider = Column(String(50), nullable=False)  # livecoinwatch, openai, etc.
    endpoint = Column(String(200), nullable=False)
    
    # Request details
    request_timestamp = Column(DateTime, default=datetime.utcnow)
    response_status = Column(Integer)
    credits_used = Column(Integer, default=1)
    
    # Response metadata
    response_size = Column(Integer)  # bytes
    response_time = Column(Float)  # seconds
    rate_limit_remaining = Column(Integer)
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# Database utility functions
class DatabaseManager:
    """Manage database connections and operations."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
        
    def get_session(self):
        """Get database session."""
        return self.SessionLocal()
        
    def track_change(self, session, project: CryptoProject, field_name: str, 
                    old_value: Any, new_value: Any, data_source: str = 'livecoinwatch',
                    change_type: str = 'UPDATE'):
        """Track changes to project data."""
        # For INSERT operations, always track regardless of old_value
        # For UPDATE operations, only track when values are different
        if change_type == 'INSERT' or old_value != new_value:
            # Serialize values before creating the ProjectChange object
            serialized_old = str(old_value) if old_value is not None else None
            serialized_new = str(new_value) if new_value is not None else None
            
            change = ProjectChange(
                project_id=project.id,
                field_name=field_name,
                old_value=serialized_old,
                new_value=serialized_new,
                change_type=change_type,
                data_source=data_source
            )
            session.add(change)
            
    def log_api_usage(self, session, provider: str, endpoint: str, 
                     status: int, credits: int = 1, **kwargs):
        """Log API usage for tracking."""
        usage = APIUsage(
            api_provider=provider,
            endpoint=endpoint,
            response_status=status,
            credits_used=credits,
            **kwargs
        )
        session.add(usage)