"""
Content Analysis Pipeline

This module coordinates the complete content analysis process:
1. Discovery: Find projects that need website or whitepaper analysis
2. Scraping: Extract content from project websites and whitepapers
3. Analysis: Process content with LLM for structured insights
4. Storage: Save results to database with proper change tracking

Supports both website and whitepaper analysis.
"""

import os
import time
import hashlib
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, UTC, timedelta
from pathlib import Path
import sys
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import and_, or_, select

# Import our modules
from models.database import DatabaseManager, CryptoProject, ProjectLink, LinkContentAnalysis, APIUsage
from scrapers.website_scraper import WebsiteScraper, WebsiteAnalysisResult
from services.website_status_logger import create_status_logger
from services.whitepaper_status_logger import create_whitepaper_status_logger
from scrapers.whitepaper_scraper import WhitepaperScraper, WhitepaperContent
from scrapers.medium_scraper import MediumScraper, MediumAnalysisResult
from scrapers.reddit_scraper import RedditScraper, RedditAnalysisResult
from scrapers.youtube_scraper import YouTubeScraper, YouTubeAnalysisResult
from analyzers.website_analyzer import WebsiteContentAnalyzer, WebsiteAnalysis
from analyzers.whitepaper_analyzer import WhitepaperContentAnalyzer, WhitepaperAnalysis
from analyzers.medium_analyzer import MediumContentAnalyzer, MediumAnalysis
from analyzers.reddit_analyzer import RedditContentAnalyzer, RedditAnalysis
from analyzers.youtube_analyzer import YouTubeAnalyzer, YouTubeContentAnalysis
from services.reddit_status_logger import create_reddit_status_logger

# Load environment variables
config_path = Path(__file__).parent.parent.parent / "config" / "env"
load_dotenv(config_path)


def sanitize_content_for_storage(content: str) -> str:
    """
    Sanitize content for database storage by removing null bytes and other problematic characters.
    
    Args:
        content: Raw content string that may contain null bytes
        
    Returns:
        Sanitized content safe for PostgreSQL storage
    """
    if not content:
        return ''
    
    # Remove null bytes (0x00) which can't be stored in PostgreSQL text fields
    sanitized = content.replace('\x00', '')
    
    # Remove other control characters that might cause issues (except newlines and tabs)
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in ['\n', '\t', '\r'])
    
    return sanitized.strip()


class ContentAnalysisPipeline:
    """Complete pipeline for cryptocurrency content analysis (websites and whitepapers)."""
    
    def __init__(self, 
                 db_manager: DatabaseManager,
                 scraper_config: Dict = None,
                 analyzer_config: Dict = None):
        """
        Initialize the content analysis pipeline.
        
        Args:
            db_manager: Database manager instance
            scraper_config: Configuration for scrapers
            analyzer_config: Configuration for LLM analyzers
        """
        self.db_manager = db_manager
        
        # Initialize status loggers
        self.status_logger = create_status_logger(db_manager)
        self.whitepaper_status_logger = create_whitepaper_status_logger(db_manager)
        self.reddit_status_logger = create_reddit_status_logger(db_manager)
        
        # Initialize scrapers
        scraper_config = scraper_config or {}
        self.website_scraper = WebsiteScraper(
            max_pages=scraper_config.get('max_pages', 10),
            max_depth=scraper_config.get('max_depth', 3),
            delay=scraper_config.get('delay', 1.0)
        )
        self.whitepaper_scraper = WhitepaperScraper(
            timeout=scraper_config.get('timeout', 30),
            max_file_size=scraper_config.get('max_file_size', 50 * 1024 * 1024)
        )
        self.medium_scraper = MediumScraper(
            max_articles=scraper_config.get('max_articles', 20),
            recent_days=scraper_config.get('recent_days', 90),
            delay=scraper_config.get('delay', 1.0)
        )
        self.reddit_scraper = RedditScraper(
            recent_days=scraper_config.get('recent_days', 30),
            max_posts=scraper_config.get('max_posts', 100),
            rate_limit_delay=scraper_config.get('delay', 0.2)
        )
        self.youtube_scraper = YouTubeScraper(
            recent_days=scraper_config.get('recent_days', 90),
            max_videos=scraper_config.get('max_videos', 50),
            rate_limit_delay=scraper_config.get('delay', 0.1)
        )
        
        # Initialize analyzers
        analyzer_config = analyzer_config or {}
        self.website_analyzer = WebsiteContentAnalyzer(
            provider=analyzer_config.get('provider', 'ollama'),
            model=analyzer_config.get('model', 'llama3.1:latest'),
            ollama_base_url=analyzer_config.get('ollama_base_url', 'http://localhost:11434'),
            db_manager=db_manager
        )
        self.whitepaper_analyzer = WhitepaperContentAnalyzer(
            provider=analyzer_config.get('provider', 'ollama'),
            model=analyzer_config.get('model', 'llama3.1:latest'),
            ollama_base_url=analyzer_config.get('ollama_base_url', 'http://localhost:11434'),
            db_manager=db_manager
        )
        self.medium_analyzer = MediumContentAnalyzer(
            provider=analyzer_config.get('provider', 'ollama'),
            model=analyzer_config.get('model', 'llama3.1:latest'),
            ollama_base_url=analyzer_config.get('ollama_base_url', 'http://localhost:11434'),
            db_manager=db_manager
        )
        self.reddit_analyzer = RedditContentAnalyzer(
            provider=analyzer_config.get('provider', 'ollama'),
            model=analyzer_config.get('model', 'llama3.1:latest'),
            ollama_base_url=analyzer_config.get('ollama_base_url', 'http://localhost:11434'),
            db_manager=db_manager
        )
        self.youtube_analyzer = YouTubeAnalyzer()
        
        # Analysis settings
        self.max_projects_per_run = 10  # Limit for cost control
        self.min_analysis_interval = timedelta(days=7)  # Minimum time between re-analysis
        
    def discover_projects_for_analysis(self, link_types: List[str] = None, limit: int = None) -> List[Tuple[CryptoProject, ProjectLink]]:
        """
        Find cryptocurrency projects that need content analysis.
        
        Args:
            link_types: Types of links to analyze ['website', 'whitepaper'] or None for both
            limit: Maximum number of projects to return
            
        Returns:
            List of (project, link) tuples ready for analysis
        """
        if link_types is None:
            link_types = ['website', 'whitepaper', 'medium', 'reddit', 'youtube']
            
        with self.db_manager.get_session() as session:
            # Query for projects with links that need analysis
            query = session.query(CryptoProject, ProjectLink).join(
                ProjectLink, CryptoProject.id == ProjectLink.project_id
            ).filter(
                and_(
                    ProjectLink.link_type.in_(link_types),
                    ProjectLink.is_active == True,
                    or_(
                        ProjectLink.needs_analysis == True,
                        ProjectLink.last_scraped.is_(None)
                    )
                )
            )
            
            # Prioritize by market cap (larger projects first) and exclude recently analyzed
            cutoff_time = datetime.now(UTC) - self.min_analysis_interval
            
            # Check for existing analysis
            analyzed_link_ids = select(LinkContentAnalysis.link_id).filter(
                LinkContentAnalysis.created_at > cutoff_time
            )
            
            query = query.filter(
                ProjectLink.id.notin_(analyzed_link_ids)
            ).order_by(
                CryptoProject.market_cap.desc().nullslast(),
                CryptoProject.rank.asc().nullslast()
            )
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
            
            logger.info(f"Found {len(results)} projects ready for content analysis")
            return results
    
    def analyze_content(self, project: CryptoProject, link: ProjectLink) -> Optional[LinkContentAnalysis]:
        """
        Complete scraping and analysis workflow for a single content link.
        
        Args:
            project: CryptoProject instance
            link: ProjectLink for the content
            
        Returns:
            LinkContentAnalysis instance if successful, None otherwise
        """
        logger.info(f"Starting {link.link_type} analysis for {project.name} ({project.code}) - {link.url}")
        
        try:
            if link.link_type == 'website':
                return self._analyze_website(project, link)
            elif link.link_type == 'whitepaper':
                return self._analyze_whitepaper(project, link)
            elif link.link_type == 'medium':
                return self._analyze_medium(project, link)
            elif link.link_type == 'reddit':
                return self._analyze_reddit(project, link)
            elif link.link_type == 'youtube':
                return self._analyze_youtube(project, link)
            else:
                logger.warning(f"Unsupported link type: {link.link_type}")
                return None
                
        except Exception as e:
            logger.error(f"Analysis failed for {project.name}: {e}")
            self._update_scrape_status(link, success=False, error=str(e))
            return None
    
    def _analyze_website(self, project: CryptoProject, website_link: ProjectLink) -> Optional[LinkContentAnalysis]:
        """Analyze a website link."""
        # Step 1: Scrape the website
        scrape_result = self.website_scraper.scrape_website(website_link.url)
        
        if not scrape_result.scrape_success:
            # Log detailed status instead of generic error
            if scrape_result.status_type == 'robots_blocked':
                self.status_logger.log_robots_blocked(
                    link_id=website_link.id,
                    url=website_link.url,
                    robots_message=scrape_result.error_message
                )
            elif scrape_result.status_type == 'parked_domain':
                self.status_logger.log_parked_domain(
                    link_id=website_link.id,
                    url=website_link.url,
                    parking_service=scrape_result.detected_parking_service
                )
            elif scrape_result.status_type == 'no_content':
                self.status_logger.log_no_pages_scraped(
                    link_id=website_link.id,
                    url=website_link.url,
                    reason=scrape_result.error_message
                )
            else:
                # Handle specific error types for better status tracking
                # Check if scraper provided error type information
                error_type = getattr(scrape_result, 'error_type', None)
                
                if error_type == 'dns_resolution_error':
                    self.status_logger.log_dns_error(
                        link_id=website_link.id,
                        url=website_link.url,
                        error_message=scrape_result.error_message
                    )
                elif error_type == 'ssl_certificate_error':
                    self.status_logger.log_ssl_error(
                        link_id=website_link.id,
                        url=website_link.url,
                        error_message=scrape_result.error_message
                    )
                else:
                    # Connection or other technical errors
                    self.status_logger.log_connection_error(
                        link_id=website_link.id,
                        url=website_link.url,
                        error_message=scrape_result.error_message or "Unknown scraping error"
                    )
            
            # Update scrape status without logging as error
            self._update_scrape_status(website_link, success=False, error=scrape_result.error_message)
            return None
        
        # Log successful scraping
        self.status_logger.log_scraping_success(
            link_id=website_link.id,
            url=website_link.url,
            pages_scraped=len(scrape_result.pages_scraped),
            total_content_length=scrape_result.total_content_length
        )
        
        # Step 2: Analyze with LLM
        try:
            website_analysis = self.website_analyzer.analyze_website(
                scrape_result.pages_scraped, 
                scrape_result.domain
            )
            
            if not website_analysis:
                logger.error(f"Website LLM analysis failed for {website_link.url}")
                self._update_scrape_status(website_link, success=False, error="LLM analysis failed")
                return None
        except Exception as analysis_error:
            # Handle content processing errors (like NUL characters)
            error_message = str(analysis_error)
            if "NUL" in error_message or "0x00" in error_message:
                self.status_logger.log_content_error(
                    link_id=website_link.id,
                    url=website_link.url,
                    error_message=error_message
                )
                logger.warning(f"Content processing error for {website_link.url}: NUL characters detected")
            else:
                self.status_logger.log_content_error(
                    link_id=website_link.id,
                    url=website_link.url,
                    error_message=error_message
                )
                logger.error(f"Analysis failed for {project.name}: {error_message}")
            
            self._update_scrape_status(website_link, success=False, error=error_message)
            return None
        
        # Step 3: Store results in database
        analysis_record = self._store_website_analysis_results(
            website_link, 
            scrape_result, 
            website_analysis
        )
        
        # Step 4: Update scrape status
        self._update_scrape_status(website_link, success=True)
        
        # Step 5: Log API usage
        self._log_website_analysis_usage(website_analysis)
        
        logger.success(f"Website analysis complete for {project.name}: Technical depth {website_analysis.technical_depth_score}/10")
        
        return analysis_record
    
    def _analyze_whitepaper(self, project: CryptoProject, whitepaper_link: ProjectLink) -> Optional[LinkContentAnalysis]:
        """Analyze a whitepaper link."""
        # Step 1: Scrape the whitepaper
        scrape_result = self.whitepaper_scraper.scrape_whitepaper(whitepaper_link.url)
        
        if not scrape_result.success:
            error_msg = scrape_result.error_message or "Unknown scraping error"
            
            # Log detailed error status to database with quiet console logging
            self._log_whitepaper_error(whitepaper_link, error_msg, scrape_result)
                
            self._update_scrape_status(whitepaper_link, success=False, error=error_msg)
            return None
        
        # Step 2: Analyze with LLM
        whitepaper_analysis = self.whitepaper_analyzer.analyze_whitepaper(
            scrape_result.content,
            scrape_result.content_type,
            scrape_result.word_count,
            scrape_result.page_count
        )
        
        if not whitepaper_analysis:
            logger.warning(f"Whitepaper LLM analysis failed for {whitepaper_link.url} - likely empty content or extraction issues")
            self._update_scrape_status(whitepaper_link, success=False, error="LLM analysis failed")
            return None
        
        # Step 3: Store results in database
        analysis_record = self._store_whitepaper_analysis_results(
            whitepaper_link,
            scrape_result,
            whitepaper_analysis
        )
        
        # Step 4: Update scrape status
        self._update_scrape_status(whitepaper_link, success=True)
        
        # Step 5: Log API usage
        self._log_whitepaper_analysis_usage(whitepaper_analysis)
        
        logger.success(f"Whitepaper analysis complete for {project.name}: Technical depth {whitepaper_analysis.technical_depth_score}/10")
        
        return analysis_record
    
    def _analyze_medium(self, project: CryptoProject, medium_link: ProjectLink) -> Optional[LinkContentAnalysis]:
        """Analyze a Medium publication link."""
        # Step 1: Scrape the Medium publication
        scrape_result = self.medium_scraper.scrape_medium_publication(medium_link.url)
        
        if not scrape_result.scrape_success:
            # Check if this is an inactive publication (no articles found)
            if ("No articles found" in scrape_result.error_message or 
                "feed parsing failed" in scrape_result.error_message or
                scrape_result.total_articles == 0):
                
                # Store basic publication information even if no articles
                analysis_record = self._store_inactive_medium_publication(
                    medium_link,
                    scrape_result
                )
                
                # Update status as processed (not failed) since we handled it gracefully
                self._update_scrape_status(medium_link, success=True)
                recent_days = self.medium_scraper.recent_days
                logger.info(f"Medium publication inactive for {recent_days} days: {project.name} - stored publication info")
                return analysis_record
            else:
                # Actual error (network issues, etc.)
                logger.error(f"Medium scraping failed for {medium_link.url}: {scrape_result.error_message}")
                self._update_scrape_status(medium_link, success=False, error=scrape_result.error_message)
                return None
        
        # Step 2: Analyze with LLM
        medium_analysis = self.medium_analyzer.analyze_medium_publication(scrape_result)
        
        if not medium_analysis:
            logger.error(f"Medium LLM analysis failed for {medium_link.url}")
            self._update_scrape_status(medium_link, success=False, error="LLM analysis failed")
            return None
        
        # Step 3: Store results in database
        analysis_record = self._store_medium_analysis_results(
            medium_link,
            scrape_result,
            medium_analysis
        )
        
        # Step 4: Update scrape status
        self._update_scrape_status(medium_link, success=True)
        
        # Step 5: Log API usage
        self._log_medium_analysis_usage(medium_analysis)
        
        logger.success(f"Medium analysis complete for {project.name}: Engagement score {medium_analysis.community_engagement_score}/10")
        
        return analysis_record
    
    def _analyze_reddit(self, project: CryptoProject, reddit_link: ProjectLink) -> Optional[LinkContentAnalysis]:
        """Analyze a Reddit community link."""
        # Step 1: Scrape the Reddit community
        scrape_result = self.reddit_scraper.scrape_reddit_community(reddit_link.url)
        
        if not scrape_result.scrape_success:
            # Check if this is an inactive community (not an error)
            if "No recent posts found" in scrape_result.error_message and "within the last" in scrape_result.error_message:
                # Extract days from error message or use default
                recent_days = self.reddit_scraper.recent_days
                
                # Log as inactive community, not failure
                self.reddit_status_logger.log_inactive(
                    link_id=reddit_link.id,
                    url=reddit_link.url,
                    recent_days=recent_days,
                    subscriber_count=scrape_result.subreddit_info.subscribers if scrape_result.subreddit_info else None
                )
                
                # Store basic community information even if inactive
                analysis_record = self._store_inactive_reddit_community(
                    reddit_link,
                    scrape_result
                )
                
                # Update status as processed (not failed)
                self._update_scrape_status(reddit_link, success=True)
                logger.info(f"Reddit community inactive for {recent_days} days: {project.name} - stored community info")
                return analysis_record
            else:
                # Check if this is an expected failure that should be handled gracefully
                error_msg = scrape_result.error_message
                error_lower = error_msg.lower()
                
                # Expected failures that should be logged to database, not as errors
                expected_failures = [
                    'does not exist', '404', 'not found', 'private', 'restricted', 
                    'banned', 'quarantined', 'forbidden', '403'
                ]
                
                if any(condition in error_lower for condition in expected_failures):
                    # This is an expected failure - log to status logger and store in database
                    self._log_reddit_expected_failure(reddit_link, scrape_result)
                    
                    # Update status as processed (not failed) since we handled it gracefully
                    self._update_scrape_status(reddit_link, success=True, error=None)
                    logger.info(f"Reddit community unavailable: {project.name} - {error_msg} (stored in database)")
                    return self._create_reddit_unavailable_record(reddit_link, scrape_result)
                else:
                    # Unexpected error (API issues, network problems, etc.)
                    logger.error(f"Reddit scraping failed for {reddit_link.url}: {error_msg}")
                    self._update_scrape_status(reddit_link, success=False, error=error_msg)
                    return None
        
        # Step 2: Analyze with LLM
        reddit_analysis = self.reddit_analyzer.analyze_reddit_community(scrape_result)
        
        if not reddit_analysis:
            logger.error(f"Reddit LLM analysis failed for {reddit_link.url}")
            self._update_scrape_status(reddit_link, success=False, error="LLM analysis failed")
            return None
        
        # Step 3: Store results in database
        analysis_record = self._store_reddit_analysis_results(
            reddit_link,
            scrape_result,
            reddit_analysis
        )
        
        # Step 4: Update scrape status
        self._update_scrape_status(reddit_link, success=True)
        
        # Step 5: Log successful Reddit analysis
        self.reddit_status_logger.log_success(
            link_id=reddit_link.id,
            url=reddit_link.url,
            posts_found=len(scrape_result.posts_analyzed),
            subscriber_count=scrape_result.subreddit_info.subscribers if scrape_result.subreddit_info else None
        )
        
        # Step 6: Log API usage
        self._log_reddit_analysis_usage(reddit_analysis)
        
        logger.success(f"Reddit analysis complete for {project.name}: Community health {reddit_analysis.community_health_score}/10")
        
        return analysis_record
    
    def _analyze_youtube(self, project: CryptoProject, youtube_link: ProjectLink) -> Optional[LinkContentAnalysis]:
        """Analyze a YouTube channel link."""
        # Step 1: Scrape the YouTube channel
        scrape_result = self.youtube_scraper.scrape_youtube_channel(youtube_link.url)
        
        if not scrape_result.scrape_success:
            error_msg = scrape_result.error_message or "Unknown error"
            error_lower = error_msg.lower()
            
            # Check if this is an expected failure that should be handled gracefully
            expected_failures = [
                'could not extract channel id', 'channel not found', 
                'no recent videos', 'channel id from url', 'invalid url',
                'channel does not exist', '404'
            ]
            
            if any(condition in error_lower for condition in expected_failures):
                # This is an expected failure - log as warning and update status as processed
                logger.warning(f"YouTube channel unavailable: {project.name} - {error_msg} (expected failure)")
                self._update_scrape_status(youtube_link, success=True, error=None)  # Mark as processed, not failed
                
                # Create a minimal analysis record to show why it failed
                return self._create_youtube_unavailable_record(youtube_link, scrape_result)
            else:
                # Unexpected error (API issues, network problems, etc.)
                logger.error(f"YouTube scraping failed for {youtube_link.url}: {error_msg}")
                self._update_scrape_status(youtube_link, success=False, error=error_msg)
                return None
        
        # Step 2: Analyze with YouTube analyzer
        youtube_analysis = self.youtube_analyzer.analyze_youtube_content(scrape_result)
        
        if not youtube_analysis:
            logger.error(f"YouTube analysis failed for {youtube_link.url}")
            self._update_scrape_status(youtube_link, success=False, error="YouTube analysis failed")
            return None
        
        # Step 3: Store results in database
        analysis_record = self._store_youtube_analysis_results(
            youtube_link,
            scrape_result,
            youtube_analysis
        )
        
        # Step 4: Update scrape status
        self._update_scrape_status(youtube_link, success=True)
        
        # Step 5: Log API usage
        self._log_youtube_analysis_usage(youtube_analysis)
        
        logger.success(f"YouTube analysis complete for {project.name}: Educational content {youtube_analysis.educational_value_score}/10")
        
        return analysis_record
    
    
    def _store_website_analysis_results(self,
                                      website_link: ProjectLink, 
                                      scrape_result: WebsiteAnalysisResult, 
                                      website_analysis: WebsiteAnalysis) -> LinkContentAnalysis:
        """Store website analysis results in the database."""
        
        with self.db_manager.get_session() as session:
            # Combine all page content for storage
            combined_content = "\n\n".join([
                f"=== {page.page_type.upper()}: {page.title} ===\n{page.content}"
                for page in scrape_result.pages_scraped
            ])
            
            # Sanitize combined content for database storage
            combined_content = sanitize_content_for_storage(combined_content)
            
            # Calculate content hash
            content_hash = hashlib.sha256(combined_content.encode()).hexdigest()
            
            # Check if we already have analysis for this content
            existing = session.query(LinkContentAnalysis).filter(
                and_(
                    LinkContentAnalysis.link_id == website_link.id,
                    LinkContentAnalysis.content_hash == content_hash
                )
            ).first()
            
            if existing:
                logger.info(f"Content unchanged for {website_link.url}, skipping analysis storage")
                return existing
            
            # Create new analysis record
            analysis_record = LinkContentAnalysis(
                link_id=website_link.id,
                
                # Content metadata
                raw_content=combined_content[:50000],  # Limit size for database
                content_hash=content_hash,
                page_title=scrape_result.pages_scraped[0].title if scrape_result.pages_scraped else None,
                pages_analyzed=len(scrape_result.pages_scraped),
                total_word_count=website_analysis.total_word_count,
                
                # Document info
                document_type='website',
                extraction_method='website_scraper',
                
                # Core technology information
                technology_stack=website_analysis.technology_stack,
                blockchain_platform=website_analysis.blockchain_platform,
                consensus_mechanism=website_analysis.consensus_mechanism,
                
                # Key value propositions
                core_features=website_analysis.core_features,
                use_cases=website_analysis.use_cases,
                unique_value_proposition=website_analysis.unique_value_proposition,
                target_audience=website_analysis.target_audience,
                
                # Team and organization
                team_members=website_analysis.team_members,
                founders=website_analysis.founders,
                team_size_estimate=website_analysis.team_size_estimate,
                advisors=website_analysis.advisors,
                
                # Business information
                partnerships=website_analysis.partnerships,
                investors=website_analysis.investors,
                funding_raised=website_analysis.funding_raised,
                
                # Development and innovation
                innovations=website_analysis.innovations,
                development_stage=website_analysis.development_stage,
                roadmap_items=website_analysis.roadmap_items,
                
                # Analysis scores
                technical_depth_score=website_analysis.technical_depth_score,
                marketing_vs_tech_ratio=website_analysis.marketing_vs_tech_ratio,
                content_quality_score=website_analysis.content_quality_score,
                red_flags=website_analysis.red_flags,
                confidence_score=website_analysis.confidence_score,
                
                # Legacy fields for summary
                summary=website_analysis.unique_value_proposition,
                key_points=(website_analysis.core_features or []) + (website_analysis.innovations or []),
                entities=(website_analysis.founders or []) + [tm.get('name', '') for tm in (website_analysis.team_members or [])],
                technical_summary=f"Tech stack: {', '.join(website_analysis.technology_stack or [])}. Platform: {website_analysis.blockchain_platform or 'Unknown'}. Stage: {website_analysis.development_stage}",
                
                # Analysis metadata
                model_used=website_analysis.model_used,
                analysis_version='2.0'
            )
            
            session.add(analysis_record)
            session.commit()
            
            logger.success(f"Stored website analysis results for {website_link.url}")
            return analysis_record
    
    def _store_whitepaper_analysis_results(self,
                                         whitepaper_link: ProjectLink,
                                         scrape_result: WhitepaperContent,
                                         whitepaper_analysis: WhitepaperAnalysis) -> LinkContentAnalysis:
        """Store whitepaper analysis results in the database."""
        
        with self.db_manager.get_session() as session:
            # Check if we already have analysis for this content
            existing = session.query(LinkContentAnalysis).filter(
                and_(
                    LinkContentAnalysis.link_id == whitepaper_link.id,
                    LinkContentAnalysis.content_hash == scrape_result.content_hash
                )
            ).first()
            
            if existing:
                logger.info(f"Content unchanged for {whitepaper_link.url}, skipping analysis storage")
                return existing
            
            # Sanitize whitepaper content for database storage
            sanitized_content = sanitize_content_for_storage(scrape_result.content)
            
            # Create new analysis record
            analysis_record = LinkContentAnalysis(
                link_id=whitepaper_link.id,
                
                # Content metadata
                raw_content=sanitized_content[:50000],  # Limit size for database
                content_hash=scrape_result.content_hash,
                page_title=scrape_result.title,
                pages_analyzed=1,
                total_word_count=scrape_result.word_count,
                page_count=scrape_result.page_count,
                
                # Document info
                document_type=scrape_result.content_type,
                extraction_method=scrape_result.extraction_method,
                
                # Whitepaper-specific scores
                document_structure_score=whitepaper_analysis.document_structure_score,
                technical_depth_score=whitepaper_analysis.technical_depth_score,
                content_quality_score=whitepaper_analysis.content_quality_score,
                
                # Tokenomics
                has_tokenomics=whitepaper_analysis.has_tokenomics,
                tokenomics_summary=whitepaper_analysis.tokenomics_summary,
                token_distribution_described=whitepaper_analysis.token_distribution_described,
                economic_model_clarity=whitepaper_analysis.economic_model_clarity,
                
                # Use case and value proposition
                use_cases=whitepaper_analysis.use_cases_described,
                use_case_viability_score=whitepaper_analysis.use_case_viability_score,
                target_market_defined=whitepaper_analysis.target_market_defined,
                unique_value_proposition=whitepaper_analysis.unique_value_proposition,
                
                # Technical innovation
                innovations=whitepaper_analysis.innovations_claimed,
                technical_innovations_score=whitepaper_analysis.technical_innovations_score,
                implementation_details_score=whitepaper_analysis.implementation_details,
                
                # Competitive analysis
                has_competitive_analysis=whitepaper_analysis.has_competitive_analysis,
                competitors_mentioned=whitepaper_analysis.competitors_mentioned,
                competitive_advantages_claimed=whitepaper_analysis.competitive_advantages_claimed,
                
                # Team and development
                team_described=whitepaper_analysis.team_described,
                team_expertise_apparent=whitepaper_analysis.team_expertise_apparent,
                development_roadmap_present=whitepaper_analysis.development_roadmap_present,
                roadmap_specificity=whitepaper_analysis.roadmap_specificity,
                
                # Risk and validation
                red_flags=whitepaper_analysis.red_flags,
                plagiarism_indicators=whitepaper_analysis.plagiarism_indicators,
                vague_claims=whitepaper_analysis.vague_claims,
                unrealistic_promises=whitepaper_analysis.unrealistic_promises,
                
                # Market and adoption
                market_size_analysis=whitepaper_analysis.market_size_analysis,
                adoption_strategy_described=whitepaper_analysis.adoption_strategy_described,
                partnerships_mentioned=whitepaper_analysis.partnerships_mentioned,
                
                # Analysis metadata
                confidence_score=whitepaper_analysis.confidence_score,
                model_used=whitepaper_analysis.model_used,
                analysis_version='2.1'
            )
            
            session.add(analysis_record)
            session.commit()
            
            logger.success(f"Stored whitepaper analysis results for {whitepaper_link.url}")
            return analysis_record
    
    def _log_website_analysis_usage(self, website_analysis: WebsiteAnalysis):
        """Website LLM API usage is now tracked automatically in the analyzer.
        
        This method is kept for backward compatibility but no longer creates 
        duplicate usage records since the analyzers now track usage directly.
        """
        # Usage is now tracked automatically in WebsiteContentAnalyzer._call_ollama()
        # when db_manager is available, including actual response times and token counts
        logger.debug(f"Website analysis usage tracked automatically for {website_analysis.model_used}")
    
    def _log_whitepaper_analysis_usage(self, whitepaper_analysis: WhitepaperAnalysis):
        """Whitepaper LLM API usage is now tracked automatically in the analyzer.
        
        This method is kept for backward compatibility but no longer creates 
        duplicate usage records since the analyzers now track usage directly.
        """
        # Usage is now tracked automatically in WhitepaperContentAnalyzer._call_ollama()
        # when db_manager is available, including actual response times and token counts
        logger.debug(f"Whitepaper analysis usage tracked automatically for {whitepaper_analysis.model_used}")
    
    def _store_medium_analysis_results(self,
                                     medium_link: ProjectLink,
                                     scrape_result: MediumAnalysisResult,
                                     medium_analysis: MediumAnalysis) -> LinkContentAnalysis:
        """Store Medium analysis results in the database."""
        
        with self.db_manager.get_session() as session:
            # Combine article content for storage
            combined_content = "\n\n".join([
                f"=== {article.title} ({article.published_date.strftime('%Y-%m-%d')}) ===\n{article.content[:1000]}..."
                for article in scrape_result.articles_found
            ])
            
            # Sanitize combined content for database storage
            combined_content = sanitize_content_for_storage(combined_content)
            
            # Calculate content hash based on publication and recent content
            content_hash = hashlib.sha256(f"{scrape_result.publication_url}_{scrape_result.last_post_date}".encode()).hexdigest()
            
            # Check if we already have analysis for this content
            existing = session.query(LinkContentAnalysis).filter(
                and_(
                    LinkContentAnalysis.link_id == medium_link.id,
                    LinkContentAnalysis.content_hash == content_hash
                )
            ).first()
            
            if existing:
                logger.info(f"Content unchanged for {medium_link.url}, skipping analysis storage")
                return existing
            
            # Create new analysis record with Medium-specific data
            analysis_record = LinkContentAnalysis(
                link_id=medium_link.id,
                
                # Content metadata
                raw_content=combined_content[:50000],  # Limit size for database
                content_hash=content_hash,
                page_title=f"{medium_analysis.publication_name} - Medium Publication",
                pages_analyzed=medium_analysis.total_articles_analyzed,
                total_word_count=sum(article.word_count for article in scrape_result.articles_found),
                
                # Document info
                document_type='medium_publication',
                extraction_method='medium_scraper',
                
                # Analysis scores adapted for Medium
                technical_depth_score=medium_analysis.development_activity_score,  # Map development activity to technical depth
                content_quality_score=medium_analysis.content_quality_score,
                confidence_score=medium_analysis.confidence_score,
                
                # Medium-specific insights mapped to existing fields
                use_cases=medium_analysis.educational_content,  # Educational content as use cases
                partnerships=medium_analysis.partnership_announcements,
                roadmap_items=medium_analysis.roadmap_mentions,
                recent_updates=medium_analysis.recent_development_mentions,
                red_flags=medium_analysis.red_flags + medium_analysis.spam_indicators + medium_analysis.misleading_claims,
                
                # Sentiment and engagement (map to existing fields)
                sentiment_score=medium_analysis.overall_sentiment_score,
                categories=list(medium_analysis.content_breakdown.keys()),
                entities=medium_analysis.competitive_mentions,
                
                # Store Medium-specific data in JSON fields
                summary=f"Medium publication analysis: {medium_analysis.total_articles_analyzed} articles analyzed over {medium_analysis.analysis_period_days} days. Publication frequency: {medium_analysis.publication_frequency:.1f}/week. Technical content: {medium_analysis.technical_content_percentage:.1f}%",
                technical_summary=f"Development activity score: {medium_analysis.development_activity_score}/10. Recent mentions: {len(medium_analysis.recent_development_mentions)} topics. Community engagement: {medium_analysis.community_engagement_score}/10",
                key_points=(
                    [f"Engagement: {medium_analysis.community_engagement_score}/10"] +
                    [f"Development activity: {medium_analysis.development_activity_score}/10"] +
                    [f"Publication freq: {medium_analysis.publication_frequency:.1f}/week"] +
                    [f"Technical content: {medium_analysis.technical_content_percentage:.1f}%"] +
                    medium_analysis.team_activity_indicators[:3]  # Top 3 activity indicators
                ),
                
                # Analysis metadata
                model_used=medium_analysis.model_used,
                analysis_version='2.2'
            )
            
            session.add(analysis_record)
            session.commit()
            
        logger.success(f"Stored Medium analysis results for {medium_link.url}")
        return analysis_record
    
    def _store_inactive_medium_publication(self,
                                         medium_link: ProjectLink,
                                         scrape_result) -> LinkContentAnalysis:
        """Store basic information for inactive Medium publications."""
        
        with self.db_manager.get_session() as session:
            # Create a basic analysis record for inactive publication
            content_hash = hashlib.sha256(f"{scrape_result.publication_name}_inactive_{datetime.now(UTC)}".encode()).hexdigest()
            
            # Check if we already have an inactive record for this publication
            existing = session.query(LinkContentAnalysis).filter(
                and_(
                    LinkContentAnalysis.link_id == medium_link.id,
                    LinkContentAnalysis.summary.like('%inactive%')
                )
            ).first()
            
            if existing:
                logger.info(f"Inactive publication record already exists for {medium_link.url}")
                return existing
            
            # Create basic inactive publication record
            analysis_record = LinkContentAnalysis(
                link_id=medium_link.id,
                
                # Content metadata
                raw_content=f"No recent articles within analysis period: {scrape_result.error_message or 'Empty feed'}",
                content_hash=content_hash,
                page_title=f"{scrape_result.publication_name} - Inactive Medium Publication",
                pages_analyzed=0,
                total_word_count=0,
                
                # Document info
                document_type='medium_publication',
                extraction_method='medium_scraper',
                
                # Basic scores for inactive publication
                technical_depth_score=0,
                content_quality_score=0,
                confidence_score=0.9,  # High confidence that it's inactive
                
                # Store inactive status info
                summary=f"Inactive Medium publication: {scrape_result.publication_name} - No articles within analysis period ({self.medium_scraper.recent_days} days). Feed URL: {scrape_result.feed_url}",
                technical_summary="Publication appears inactive - no recent articles to analyze",
                key_points=[
                    "Publication status: Inactive (no recent articles)",
                    f"Feed URL: {scrape_result.feed_url}",
                    f"Analysis period: {self.medium_scraper.recent_days} days",
                    "Recommendation: Monitor for future activity"
                ],
                
                # Analysis metadata
                model_used='n/a',
                analysis_version='2.4'
            )
            
            session.add(analysis_record)
            session.commit()
            
            logger.info(f"Stored inactive Medium publication record for {medium_link.url}")
            return analysis_record
    
    def _log_medium_analysis_usage(self, medium_analysis: MediumAnalysis):
        """Medium LLM API usage is now tracked automatically in the analyzer.
        
        This method is kept for backward compatibility but no longer creates 
        duplicate usage records since the analyzers now track usage directly.
        """
        # Usage is now tracked automatically in MediumContentAnalyzer._call_ollama()
        # when db_manager is available, including actual response times and token counts
        logger.debug(f"Medium analysis usage tracked automatically for {medium_analysis.model_used}")
    
    def _store_reddit_analysis_results(self,
                                     reddit_link: ProjectLink,
                                     scrape_result: RedditAnalysisResult,
                                     reddit_analysis: RedditAnalysis) -> LinkContentAnalysis:
        """Store Reddit analysis results in the database."""
        
        with self.db_manager.get_session() as session:
            # Combine post data for storage
            combined_content = "\n\n".join([
                f"=== {post.title} (Score: {post.score}, Comments: {post.num_comments}) ===\n{post.content[:500]}..."
                for post in scrape_result.posts_analyzed[:10]  # Top 10 posts
            ])
            
            # Sanitize combined content for database storage
            combined_content = sanitize_content_for_storage(combined_content)
            
            # Calculate content hash based on subreddit and analysis time
            content_hash = hashlib.sha256(f"{scrape_result.subreddit_name}_{scrape_result.analysis_timestamp}".encode()).hexdigest()
            
            # Check if we already have analysis for this content
            existing = session.query(LinkContentAnalysis).filter(
                and_(
                    LinkContentAnalysis.link_id == reddit_link.id,
                    LinkContentAnalysis.content_hash == content_hash
                )
            ).first()
            
            if existing:
                logger.info(f"Content unchanged for {reddit_link.url}, skipping analysis storage")
                return existing
            
            # Create new analysis record with Reddit-specific data
            analysis_record = LinkContentAnalysis(
                link_id=reddit_link.id,
                
                # Content metadata
                raw_content=combined_content[:50000],  # Limit size for database
                content_hash=content_hash,
                page_title=f"r/{reddit_analysis.subreddit_name} - Reddit Community",
                pages_analyzed=reddit_analysis.total_posts_analyzed,
                total_word_count=sum(len(post.title + post.content) for post in scrape_result.posts_analyzed),
                
                # Document info
                document_type='reddit_community',
                extraction_method='reddit_scraper',
                
                # Analysis scores adapted for Reddit
                technical_depth_score=reddit_analysis.development_awareness_score,  # Map development awareness to technical depth
                content_quality_score=reddit_analysis.discussion_quality_score,
                confidence_score=reddit_analysis.confidence_score,
                
                # Reddit-specific insights mapped to existing fields
                use_cases=reddit_analysis.project_milestone_discussions,  # Milestone discussions as use cases
                partnerships=reddit_analysis.partnership_discussions,
                roadmap_items=reddit_analysis.roadmap_awareness_indicators,
                recent_updates=reddit_analysis.competitive_discussions,
                red_flags=reddit_analysis.red_flags + reddit_analysis.manipulation_indicators + reddit_analysis.misinformation_presence,
                
                # Sentiment and engagement (map to existing fields)
                sentiment_score=reddit_analysis.overall_sentiment_score,
                categories=list(reddit_analysis.content_type_breakdown.keys()),
                entities=reddit_analysis.fud_indicators + reddit_analysis.fomo_indicators,
                
                # Store Reddit-specific data in JSON fields
                summary=f"Reddit community analysis: {reddit_analysis.total_posts_analyzed} posts analyzed from r/{reddit_analysis.subreddit_name} ({reddit_analysis.subscriber_count:,} subscribers). Community health: {reddit_analysis.community_health_score}/10. Technical discussion: {reddit_analysis.technical_discussion_percentage:.1f}%",
                technical_summary=f"Community health: {reddit_analysis.community_health_score}/10. Discussion quality: {reddit_analysis.discussion_quality_score}/10. Technical literacy: {reddit_analysis.technical_literacy_level}. Confidence level: {reddit_analysis.community_confidence_level}",
                key_points=(
                    [f"Community health: {reddit_analysis.community_health_score}/10"] +
                    [f"Discussion quality: {reddit_analysis.discussion_quality_score}/10"] +
                    [f"Engagement authenticity: {reddit_analysis.engagement_authenticity_score}/10"] +
                    [f"Technical discussion: {reddit_analysis.technical_discussion_percentage:.1f}%"] +
                    [f"Hype content: {reddit_analysis.hype_content_percentage:.1f}%"] +
                    [f"Echo chamber risk: {reddit_analysis.echo_chamber_risk}"] +
                    reddit_analysis.user_retention_indicators[:3]  # Top 3 retention indicators
                ),
                
                # Analysis metadata
                model_used=reddit_analysis.model_used,
                analysis_version='2.3'
            )
            
            session.add(analysis_record)
            session.commit()
            
            logger.success(f"Stored Reddit analysis results for {reddit_link.url}")
            return analysis_record
    
    def _store_inactive_reddit_community(self,
                                        reddit_link: ProjectLink,
                                        scrape_result: RedditAnalysisResult) -> LinkContentAnalysis:
        """Store basic information for inactive Reddit communities."""
        
        with self.db_manager.get_session() as session:
            # Create a basic analysis record for inactive community
            content_hash = hashlib.sha256(f"{scrape_result.subreddit_name}_inactive_{datetime.now(UTC)}".encode()).hexdigest()
            
            # Check if we already have an inactive record for this community
            existing = session.query(LinkContentAnalysis).filter(
                and_(
                    LinkContentAnalysis.link_id == reddit_link.id,
                    LinkContentAnalysis.summary.like('%inactive%')
                )
            ).first()
            
            if existing:
                logger.info(f"Inactive community record already exists for {reddit_link.url}")
                return existing
            
            # Create basic inactive community record
            analysis_record = LinkContentAnalysis(
                link_id=reddit_link.id,
                
                # Content metadata
                raw_content="No recent activity within analysis period",
                content_hash=content_hash,
                page_title=f"r/{scrape_result.subreddit_name} - Inactive Reddit Community",
                pages_analyzed=0,
                total_word_count=0,
                
                # Document info
                document_type='reddit_community',
                extraction_method='reddit_scraper',
                
                # Basic scores for inactive community
                technical_depth_score=0,
                content_quality_score=0,
                confidence_score=0.9,  # High confidence that it's inactive
                
                # Store inactive status info
                summary=f"Inactive Reddit community: r/{scrape_result.subreddit_name} - No posts within analysis period. {scrape_result.subreddit_info.subscribers:,} subscribers." if scrape_result.subreddit_info else f"Inactive Reddit community: r/{scrape_result.subreddit_name} - No recent activity.",
                technical_summary="Community appears inactive - no recent posts to analyze",
                key_points=[
                    "Community status: Inactive (no recent posts)",
                    f"Subscriber count: {scrape_result.subreddit_info.subscribers:,}" if scrape_result.subreddit_info else "Subscriber count: Unknown",
                    "Analysis period: No qualifying content found",
                    "Recommendation: Monitor for future activity"
                ],
                
                # Analysis metadata
                model_used='n/a',
                analysis_version='2.3'
            )
            
            session.add(analysis_record)
            session.commit()
            
            logger.info(f"Stored inactive Reddit community record for {reddit_link.url}")
            return analysis_record
    
    def _log_reddit_analysis_usage(self, reddit_analysis: RedditAnalysis):
        """Log Reddit LLM API usage for cost tracking."""
        with self.db_manager.get_session() as session:
            # Estimate token usage based on posts analyzed
            estimated_tokens = reddit_analysis.posts_with_detailed_analysis * 2000  # Rough estimate per detailed post
            
            usage = APIUsage(
                api_provider=self.reddit_analyzer.provider,
                endpoint='reddit_analysis',
                response_status=200,
                credits_used=1,
                response_size=estimated_tokens,
                response_time=0.0  # We don't track this currently
            )
            
            session.add(usage)
            session.commit()
    
    def _store_youtube_analysis_results(self,
                                      youtube_link: ProjectLink,
                                      scrape_result: YouTubeAnalysisResult,
                                      youtube_analysis: YouTubeContentAnalysis) -> LinkContentAnalysis:
        """Store YouTube analysis results in the database."""
        
        with self.db_manager.get_session() as session:
            # Combine video content for storage
            combined_content = "\n\n".join([
                f"=== {video.title} ({video.published_at.strftime('%Y-%m-%d')}) ===\nViews: {video.view_count:,} | Likes: {video.like_count:,} | Comments: {video.comment_count:,}\nType: {video.video_type}\nDescription: {video.description[:300]}..."
                for video in scrape_result.videos_analyzed[:10]  # Top 10 videos
            ])
            
            # Sanitize combined content for database storage
            combined_content = sanitize_content_for_storage(combined_content)
            
            # Calculate content hash based on channel and analysis time
            content_hash = hashlib.sha256(f"{scrape_result.channel_id}_{scrape_result.analysis_timestamp}".encode()).hexdigest()
            
            # Check if we already have analysis for this content
            existing = session.query(LinkContentAnalysis).filter(
                and_(
                    LinkContentAnalysis.link_id == youtube_link.id,
                    LinkContentAnalysis.content_hash == content_hash
                )
            ).first()
            
            if existing:
                logger.info(f"Content unchanged for {youtube_link.url}, skipping analysis storage")
                return existing
            
            # Create new analysis record with YouTube-specific data
            analysis_record = LinkContentAnalysis(
                link_id=youtube_link.id,
                
                # Content metadata
                raw_content=combined_content[:50000],  # Limit size for database
                content_hash=content_hash,
                page_title=f"{scrape_result.channel_info.title if scrape_result.channel_info else 'Unknown'} - YouTube Channel",
                pages_analyzed=youtube_analysis.videos_analyzed_count,
                total_word_count=sum(len(video.title + video.description) for video in scrape_result.videos_analyzed),
                
                # Document info
                document_type='youtube_channel',
                extraction_method='youtube_scraper',
                
                # Analysis scores adapted for YouTube
                technical_depth_score=youtube_analysis.technical_depth_score,
                content_quality_score=youtube_analysis.content_quality_score,
                confidence_score=youtube_analysis.confidence_score,
                marketing_vs_tech_ratio=youtube_analysis.marketing_vs_substance_ratio,
                
                # YouTube-specific insights mapped to existing fields
                use_cases=youtube_analysis.project_focus_areas,  # Focus areas as use cases
                core_features=youtube_analysis.primary_content_types,  # Content types as features
                target_audience=[youtube_analysis.target_audience],  # Target audience
                roadmap_items=youtube_analysis.development_activity_indicators,
                red_flags=youtube_analysis.red_flags,
                
                # Store YouTube-specific data in JSON fields
                summary=youtube_analysis.channel_summary,
                technical_summary=f"Communication style: {youtube_analysis.communication_style}. Educational value: {youtube_analysis.educational_value_score}/10. Upload consistency: {youtube_analysis.consistency_score}/10. Transparency: {youtube_analysis.transparency_level}",
                key_points=(
                    [f"Educational value: {youtube_analysis.educational_value_score}/10"] +
                    [f"Content quality: {youtube_analysis.content_quality_score}/10"] +
                    [f"Technical depth: {youtube_analysis.technical_depth_score}/10"] +
                    [f"Communication style: {youtube_analysis.communication_style}"] +
                    [f"Target audience: {youtube_analysis.target_audience}"] +
                    [f"Transparency level: {youtube_analysis.transparency_level}"] +
                    youtube_analysis.positive_indicators[:3]  # Top 3 positive indicators
                ),
                
                # Additional fields using JSONB
                entities=youtube_analysis.topics_covered,
                categories=youtube_analysis.primary_content_types,
                recent_updates=youtube_analysis.development_activity_indicators,
                
                # Analysis metadata
                model_used=youtube_analysis.analysis_method,
                analysis_version='2.4'
            )
            
            session.add(analysis_record)
            session.commit()
            
            logger.success(f"Stored YouTube analysis results for {youtube_link.url}")
            return analysis_record
    
    def _log_youtube_analysis_usage(self, youtube_analysis: YouTubeContentAnalysis):
        """Log YouTube analysis usage for cost tracking."""
        with self.db_manager.get_session() as session:
            # Estimate token usage based on videos analyzed
            estimated_tokens = youtube_analysis.videos_analyzed_count * 500  # Rough estimate per video analyzed
            
            usage = APIUsage(
                api_provider='youtube_api',
                endpoint='youtube_analysis',
                response_status=200,
                credits_used=1,
                response_size=estimated_tokens,
                response_time=0.0  # We don't track this currently
            )
            
            session.add(usage)
            session.commit()
    
    def _log_whitepaper_error(self, whitepaper_link: ProjectLink, error_msg: str, scrape_result: WhitepaperContent):
        """Log whitepaper errors to database with appropriate categorization."""
        error_lower = error_msg.lower()
        
        if "404" in error_msg or "not found" in error_lower:
            self.whitepaper_status_logger.log_not_found(
                link_id=whitepaper_link.id,
                url=whitepaper_link.url,
                error_details=error_msg
            )
        elif "403" in error_msg or "access forbidden" in error_lower:
            self.whitepaper_status_logger.log_access_denied(
                link_id=whitepaper_link.id,
                url=whitepaper_link.url,
                http_status_code=403,
                error_details=error_msg
            )
        elif "429" in error_msg or "rate limit" in error_lower:
            self.whitepaper_status_logger.log_access_denied(
                link_id=whitepaper_link.id,
                url=whitepaper_link.url,
                http_status_code=429,
                error_details=error_msg
            )
        elif "400" in error_msg or "bad request" in error_lower:
            self.whitepaper_status_logger.log_access_denied(
                link_id=whitepaper_link.id,
                url=whitepaper_link.url,
                http_status_code=400,
                error_details=error_msg
            )
        elif "insufficient content" in error_lower and hasattr(scrape_result, 'word_count'):
            self.whitepaper_status_logger.log_insufficient_content(
                link_id=whitepaper_link.id,
                url=whitepaper_link.url,
                word_count=scrape_result.word_count,
                document_type=getattr(scrape_result, 'content_type', 'unknown'),
                extraction_method=getattr(scrape_result, 'extraction_method', None)
            )
        elif "timeout" in error_lower or "connection" in error_lower or "dns" in error_lower or "ssl" in error_lower:
            self.whitepaper_status_logger.log_connection_error(
                link_id=whitepaper_link.id,
                url=whitepaper_link.url,
                error_message=error_msg
            )
        elif "pdf" in error_lower and ("extraction" in error_lower or "password" in error_lower or "corrupted" in error_lower):
            self.whitepaper_status_logger.log_pdf_extraction_failed(
                link_id=whitepaper_link.id,
                url=whitepaper_link.url,
                error_message=error_msg
            )
        elif "google drive" in error_lower or "drive.google.com" in whitepaper_link.url:
            # Google Drive specific failures - treat as connection errors
            if "too large" in error_lower:
                self.whitepaper_status_logger.log_pdf_extraction_failed(
                    link_id=whitepaper_link.id,
                    url=whitepaper_link.url,
                    error_message=f"Google Drive file too large: {error_msg}"
                )
            else:
                self.whitepaper_status_logger.log_connection_error(
                    link_id=whitepaper_link.id,
                    url=whitepaper_link.url,
                    error_message=f"Google Drive access failed: {error_msg}"
                )
        else:
            # General connection error for unclassified errors
            self.whitepaper_status_logger.log_connection_error(
                link_id=whitepaper_link.id,
                url=whitepaper_link.url,
                error_message=error_msg
            )
    
    def _log_reddit_expected_failure(self, reddit_link: ProjectLink, scrape_result):
        """Log expected Reddit failures to the status logger."""
        error_msg = scrape_result.error_message
        error_lower = error_msg.lower()
        
        if 'does not exist' in error_lower or '404' in error_lower or 'not found' in error_lower:
            self.reddit_status_logger.log_not_found(
                link_id=reddit_link.id,
                url=reddit_link.url,
                subreddit_name=getattr(scrape_result, 'subreddit_name', 'unknown'),
                error_details=error_msg
            )
        elif 'private' in error_lower or 'restricted' in error_lower or '403' in error_lower:
            self.reddit_status_logger.log_access_denied(
                link_id=reddit_link.id,
                url=reddit_link.url,
                subreddit_name=getattr(scrape_result, 'subreddit_name', 'unknown'),
                http_status_code=403,
                error_details=error_msg
            )
        elif 'banned' in error_lower or 'quarantined' in error_lower:
            self.reddit_status_logger.log_community_unavailable(
                link_id=reddit_link.id,
                url=reddit_link.url,
                subreddit_name=getattr(scrape_result, 'subreddit_name', 'unknown'),
                reason=error_msg
            )
        else:
            # Default to access denied for other expected failures
            self.reddit_status_logger.log_access_denied(
                link_id=reddit_link.id,
                url=reddit_link.url,
                subreddit_name=getattr(scrape_result, 'subreddit_name', 'unknown'),
                http_status_code=0,
                error_details=error_msg
            )
    
    def _create_youtube_unavailable_record(self, youtube_link: ProjectLink, scrape_result) -> LinkContentAnalysis:
        """Create a basic record for unavailable YouTube channels."""
        with self.db_manager.get_session() as session:
            # Create a minimal analysis record to mark this as processed
            analysis_record = LinkContentAnalysis(
                link_id=youtube_link.id,
                
                # Minimal content info
                raw_content=f"YouTube channel unavailable: {scrape_result.error_message}",
                content_hash=hashlib.sha256(scrape_result.error_message.encode()).hexdigest()[:64],
                page_title=f"YouTube Channel - Unavailable",
                pages_analyzed=0,
                total_word_count=0,
                
                # Document info
                document_type='youtube_channel',
                extraction_method='youtube_scraper',
                
                # Use existing fields to indicate unavailability
                summary=f"YouTube channel unavailable: {scrape_result.error_message}",
                confidence_score=0.0,  # Zero confidence indicates unavailable
                technical_depth_score=0,
                content_quality_score=0,
                marketing_vs_tech_ratio=0.5,  # Neutral
                
                # Store error details
                red_flags=[f"Channel unavailable: {scrape_result.error_message}"],
                key_points=["Status: Unavailable", f"Reason: {scrape_result.error_message}"],
                
                # Analysis metadata
                model_used='n/a',
                analysis_version='2.4'
            )
            
            session.add(analysis_record)
            session.commit()
            session.refresh(analysis_record)
            
            return analysis_record
    
    def _create_reddit_unavailable_record(self, reddit_link: ProjectLink, scrape_result) -> LinkContentAnalysis:
        """Create a basic record for unavailable Reddit communities."""
        with self.db_manager.get_session() as session:
            # Create a minimal analysis record to mark this as processed
            analysis_record = LinkContentAnalysis(
                link_id=reddit_link.id,
                
                # Minimal content info
                raw_content=f"Reddit community unavailable: {scrape_result.error_message}",
                content_hash=hashlib.sha256(scrape_result.error_message.encode()).hexdigest()[:64],
                page_title=f"r/{getattr(scrape_result, 'subreddit_name', 'unknown')}",
                pages_analyzed=0,
                total_word_count=0,
                
                # Document info
                document_type='reddit',
                extraction_method='reddit_scraper',
                
                # Use existing fields to indicate unavailability
                summary=f"Community unavailable: {scrape_result.error_message}",
                confidence_score=0.0,  # Zero confidence indicates unavailable
                technical_depth_score=0,
                content_quality_score=0,
                
                # Timestamps
                created_at=datetime.now(UTC)
            )
            
            session.add(analysis_record)
            session.commit()
            session.refresh(analysis_record)
            
            return analysis_record
    
    def _update_scrape_status(self, link: ProjectLink, success: bool, error: str = None):
        """Update the scrape status for a project link with reduced log noise."""
        with self.db_manager.get_session() as session:
            link_obj = session.merge(link)
            link_obj.last_scraped = datetime.now(UTC)
            link_obj.scrape_success = success
            link_obj.needs_analysis = False  # Mark as processed
            
            # Reduced logging - status is now logged by specialized status loggers
            if success:
                logger.debug(f"Successfully processed {link_obj.url}")
            else:
                # Only log actual errors, not expected conditions like 404, 403, robots.txt, etc.
                error_lower = (error or '').lower()
                expected_failures = [
                    '404', '403', '429', '400', 'not found', 'access forbidden', 
                    'robots.txt', 'parked', 'for-sale', 'no pages could be scraped',
                    'insufficient content', 'rate limit', 'minimal content',
                    'does not exist', 'private', 'restricted', 'banned', 'quarantined',
                    'no articles found', 'feed parsing failed', 'empty feed'
                ]
                if any(condition in error_lower for condition in expected_failures):
                    logger.debug(f"Expected failure for {link_obj.url}: {error}")
                else:
                    logger.warning(f"Processing failed for {link_obj.url}: {error}")
            
            session.commit()
    
    def run_analysis_batch(self, link_types: List[str] = None, max_projects: int = None) -> Dict[str, int]:
        """
        Run a batch of content analyses.
        
        Args:
            link_types: Types of links to analyze ['website', 'whitepaper', 'medium', 'reddit'] or None for all
            max_projects: Maximum number of projects to analyze (None for unlimited)
            
        Returns:
            Dictionary with analysis statistics
        """
        if max_projects is None:
            logger.info("Starting content analysis batch (processing ALL projects)")
        else:
            max_projects = max_projects or self.max_projects_per_run
            logger.info(f"Starting content analysis batch (max {max_projects} projects)")
        
        # Discover projects for analysis
        projects_to_analyze = self.discover_projects_for_analysis(link_types=link_types, limit=max_projects)
        
        if not projects_to_analyze:
            logger.info("No projects need content analysis at this time")
            return {
                'projects_found': 0,
                'successful_analyses': 0,
                'failed_analyses': 0,
                'websites_analyzed': 0,
                'whitepapers_analyzed': 0,
                'medium_analyzed': 0,
                'reddit_analyzed': 0,
                'youtube_analyzed': 0
            }
        
        # Process each project
        successful_analyses = 0
        failed_analyses = 0
        websites_analyzed = 0
        whitepapers_analyzed = 0
        medium_analyzed = 0
        reddit_analyzed = 0
        youtube_analyzed = 0
        
        for i, (project, link) in enumerate(projects_to_analyze):
            logger.info(f"Processing {i+1}/{len(projects_to_analyze)}: {project.name} ({link.link_type})")
            
            analysis_result = self.analyze_content(project, link)
            
            if analysis_result:
                successful_analyses += 1
                if link.link_type == 'website':
                    websites_analyzed += 1
                elif link.link_type == 'whitepaper':
                    whitepapers_analyzed += 1
                elif link.link_type == 'medium':
                    medium_analyzed += 1
                elif link.link_type == 'reddit':
                    reddit_analyzed += 1
                elif link.link_type == 'youtube':
                    youtube_analyzed += 1
            else:
                failed_analyses += 1
            
            # Rate limiting between projects
            if i < len(projects_to_analyze) - 1:
                time.sleep(0.5)  # 0.5 seconds between projects
        
        # Summary
        stats = {
            'projects_found': len(projects_to_analyze),
            'successful_analyses': successful_analyses,
            'failed_analyses': failed_analyses,
            'websites_analyzed': websites_analyzed,
            'whitepapers_analyzed': whitepapers_analyzed,
            'medium_analyzed': medium_analyzed,
            'reddit_analyzed': reddit_analyzed,
            'youtube_analyzed': youtube_analyzed
        }
        
        logger.info(f"Batch complete: {successful_analyses} successful, {failed_analyses} failed")
        logger.info(f"Breakdown: {websites_analyzed} websites, {whitepapers_analyzed} whitepapers, {medium_analyzed} medium publications, {reddit_analyzed} reddit communities, {youtube_analyzed} youtube channels")
        return stats


def main():
    """Run the content analysis pipeline on all projects waiting for analysis."""
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize pipeline
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={'max_pages': 5, 'max_depth': 2, 'delay': 0.2, 'timeout': 30},
        analyzer_config={'provider': 'ollama', 'model': 'llama3.1:latest', 'ollama_base_url': 'http://localhost:11434'}
    )
    
    # First, check how many projects are waiting for analysis
    projects_waiting = pipeline.discover_projects_for_analysis()
    total_projects = len(projects_waiting)
    
    if total_projects == 0:
        print("No projects are waiting for content analysis.")
        return
    
    print(f"Found {total_projects} projects waiting for content analysis.")
    print(f"This will take approximately {total_projects * 15 // 60} minutes to complete.")
    
    # Run analysis on all projects (remove the limit)
    logger.info(f"Running content analysis pipeline on all {total_projects} projects")
    stats = pipeline.run_analysis_batch(max_projects=None)  # No limit - process all
    
    print(f"\n=== Final Analysis Results ===")
    print(f"Projects found: {stats['projects_found']}")
    print(f"Successful analyses: {stats['successful_analyses']}")
    print(f"Failed analyses: {stats['failed_analyses']}")
    print(f"Websites analyzed: {stats['websites_analyzed']}")
    print(f"Whitepapers analyzed: {stats['whitepapers_analyzed']}")
    print(f"Medium publications analyzed: {stats['medium_analyzed']}")
    print(f"Reddit communities analyzed: {stats['reddit_analyzed']}")
    print(f"YouTube channels analyzed: {stats['youtube_analyzed']}")
    print(f"Success rate: {stats['successful_analyses']/stats['projects_found']*100:.1f}%" if stats['projects_found'] > 0 else "N/A")


if __name__ == "__main__":
    main()