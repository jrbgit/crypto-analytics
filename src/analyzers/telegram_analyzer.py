"""
Telegram Content Analyzer for Cryptocurrency Projects

This module integrates the Telegram API client with the analysis metrics
to provide comprehensive Telegram channel analysis with database storage.
"""

import json
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import hashlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Import our components
from models.database import DatabaseManager, ProjectLink, LinkContentAnalysis
from collectors.telegram_api import TelegramAPIClient
from analyzers.telegram_analysis_metrics import TelegramAnalysisMetrics, TelegramAnalysisResult, TelegramHealthStatus

# Load environment variables
config_path = Path(__file__).parent.parent.parent / "config" / ".env"
load_dotenv(config_path)


@dataclass
class TelegramContentAnalysis:
    """Comprehensive Telegram content analysis result for database storage."""
    
    # Basic channel info
    channel_id: str
    channel_title: str
    channel_type: str
    username: Optional[str]
    description: Optional[str]
    invite_link: Optional[str]
    
    # Channel metrics
    member_count: int
    has_username: bool
    has_description: bool
    has_protected_content: bool
    has_anti_spam: bool
    
    # Analysis scores (0-10)
    authenticity_score: float
    community_score: float
    content_score: float
    activity_score: float
    security_score: float
    overall_score: float
    
    # Derived metrics
    size_category: str
    type_appropriateness: float
    
    # Health assessment
    health_status: str  # TelegramHealthStatus enum value
    confidence_score: float
    
    # Qualitative indicators
    red_flags: List[str]
    positive_indicators: List[str]
    
    # Analysis metadata
    analysis_timestamp: datetime
    api_calls_used: int
    data_quality_score: float  # How complete/reliable the data was


class TelegramContentAnalyzer:
    """Main analyzer that combines API client and metrics analysis."""
    
    def __init__(self, database_manager: DatabaseManager, api_client: TelegramAPIClient = None):
        """
        Initialize the Telegram content analyzer.
        
        Args:
            database_manager: Database manager for storing results
            api_client: Optional pre-initialized API client
        """
        self.db_manager = database_manager
        
        # Initialize API client if not provided
        if api_client is None:
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
            self.api_client = TelegramAPIClient(bot_token, database_manager)
        else:
            self.api_client = api_client
        
        # Initialize metrics analyzer
        self.metrics_analyzer = TelegramAnalysisMetrics()
        
        logger.info("Telegram content analyzer initialized")
    
    def analyze_telegram_link(self, link_id: int, telegram_url: str, 
                           project_name: str = None) -> Optional[TelegramContentAnalysis]:
        """
        Analyze a Telegram channel and return comprehensive results.
        
        Args:
            link_id: Database ID of the project link
            telegram_url: Telegram URL to analyze
            project_name: Optional project name for context
            
        Returns:
            TelegramContentAnalysis or None if analysis failed
        """
        
        logger.info(f"Starting Telegram analysis for link ID {link_id}: {telegram_url}")
        
        # Check if we can make API requests
        can_proceed, message = self.api_client.can_make_request()
        if not can_proceed:
            logger.error(f"Cannot proceed with Telegram analysis: {message}")
            return None
        
        # Extract channel ID from URL
        channel_id = self.api_client.extract_channel_id_from_url(telegram_url)
        if not channel_id:
            logger.error(f"Could not extract channel ID from Telegram URL: {telegram_url}")
            return None
        
        # Track API usage before making call
        initial_usage = self.api_client.get_usage_stats()
        
        try:
            # Get channel analysis from API
            channel_analysis = self.api_client.analyze_channel_profile(telegram_url)
            if not channel_analysis:
                logger.error(f"Failed to get channel analysis for @{channel_id}")
                return None
            
            # Calculate API calls used
            final_usage = self.api_client.get_usage_stats()
            api_calls_used = final_usage['minute_usage'] - initial_usage['minute_usage']
            
            # Run metrics analysis
            metrics_result = self.metrics_analyzer.analyze_channel(channel_analysis)
            
            # Calculate data quality score
            data_quality_score = self._calculate_data_quality_score(channel_analysis)
            
            # Combine results into analysis object
            analysis = TelegramContentAnalysis(
                channel_id=channel_id,
                channel_title=channel_analysis.get('title', ''),
                channel_type=channel_analysis.get('type', ''),
                username=channel_analysis.get('username'),
                description=channel_analysis.get('description'),
                invite_link=channel_analysis.get('invite_link'),
                
                member_count=channel_analysis.get('member_count', 0),
                has_username=bool(channel_analysis.get('username')),
                has_description=bool(channel_analysis.get('description')),
                has_protected_content=channel_analysis.get('has_protected_content', False),
                has_anti_spam=channel_analysis.get('has_aggressive_anti_spam_enabled', False),
                
                authenticity_score=metrics_result.authenticity_score,
                community_score=metrics_result.community_score,
                content_score=metrics_result.content_score,
                activity_score=metrics_result.activity_score,
                security_score=metrics_result.security_score,
                overall_score=metrics_result.overall_score,
                
                size_category=channel_analysis.get('size_category', 'unknown'),
                type_appropriateness=metrics_result.type_appropriateness,
                
                health_status=metrics_result.health_status.value,
                confidence_score=metrics_result.confidence_score,
                
                red_flags=metrics_result.red_flags,
                positive_indicators=metrics_result.positive_indicators,
                
                analysis_timestamp=datetime.now(timezone.utc),
                api_calls_used=api_calls_used,
                data_quality_score=data_quality_score
            )
            
            logger.success(f"Telegram analysis complete for @{channel_id} (Score: {analysis.overall_score:.2f})")
            return analysis
            
        except Exception as e:
            logger.error(f"Error during Telegram analysis for @{channel_id}: {e}")
            return None
    
    def _calculate_data_quality_score(self, channel_data: Dict) -> float:
        """Calculate how complete and reliable the channel data is (0-1)."""
        
        score = 0.0
        max_score = 0.0
        
        # Core fields that should be present
        core_fields = [
            ('channel_id', 0.2),
            ('title', 0.15),
            ('type', 0.1),
            ('member_count', 0.2),
            ('description', 0.15),
            ('username', 0.1),
            ('chat_id', 0.1)
        ]
        
        for field, weight in core_fields:
            max_score += weight
            if channel_data.get(field) is not None:
                if field == 'member_count':
                    # Member count should be >= 0
                    if channel_data[field] >= 0:
                        score += weight
                else:
                    # String fields should not be empty
                    if str(channel_data[field]).strip():
                        score += weight
        
        return min(1.0, score / max_score if max_score > 0 else 0)
    
    def store_analysis_result(self, link_id: int, analysis: TelegramContentAnalysis) -> bool:
        """
        Store Telegram analysis results in the database.
        
        Args:
            link_id: Database ID of the project link
            analysis: Analysis results to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        
        try:
            with self.db_manager.get_session() as session:
                # Check if analysis already exists
                existing_analysis = session.query(LinkContentAnalysis).filter_by(link_id=link_id).first()
                
                if existing_analysis:
                    logger.info(f"Updating existing Telegram analysis for link ID {link_id}")
                    # Update existing record
                    content_analysis = existing_analysis
                else:
                    logger.info(f"Creating new Telegram analysis for link ID {link_id}")
                    # Create new record
                    content_analysis = LinkContentAnalysis(link_id=link_id)
                    session.add(content_analysis)
                
                # Store core data
                content_analysis.raw_content = json.dumps(asdict(analysis), default=str, indent=2)
                content_analysis.content_hash = hashlib.sha256(
                    analysis.channel_id.encode() + str(analysis.analysis_timestamp).encode()
                ).hexdigest()
                content_analysis.pages_analyzed = 1
                content_analysis.total_word_count = len(analysis.description or '')
                
                # Store Telegram-specific data in JSON fields
                telegram_data = {
                    'channel_id': analysis.channel_id,
                    'channel_title': analysis.channel_title,
                    'channel_type': analysis.channel_type,
                    'username': analysis.username,
                    'member_count': analysis.member_count,
                    'has_username': analysis.has_username,
                    'has_description': analysis.has_description,
                    'has_protected_content': analysis.has_protected_content,
                    'has_anti_spam': analysis.has_anti_spam,
                    'size_category': analysis.size_category,
                    'type_appropriateness': analysis.type_appropriateness
                }
                
                content_analysis.technology_stack = [f"telegram_metrics_{k}" for k in telegram_data.keys()]
                content_analysis.core_features = analysis.positive_indicators
                content_analysis.red_flags = analysis.red_flags
                
                # Map Telegram scores to existing fields creatively
                content_analysis.technical_depth_score = analysis.authenticity_score
                content_analysis.content_quality_score = analysis.content_score
                content_analysis.confidence_score = analysis.confidence_score
                
                # Store additional metrics in business information fields
                content_analysis.partnerships = [f"Community Score: {analysis.community_score:.1f}"]
                content_analysis.funding_raised = f"Activity Score: {analysis.activity_score:.1f}, Security: {analysis.security_score:.1f}"
                content_analysis.development_stage = analysis.health_status
                
                # Store comprehensive data in roadmap_items
                content_analysis.roadmap_items = [
                    f"Overall Score: {analysis.overall_score:.2f}/10",
                    f"Health Status: {analysis.health_status}",
                    f"API Calls Used: {analysis.api_calls_used}",
                    f"Data Quality: {analysis.data_quality_score:.2f}",
                    f"Analysis Date: {analysis.analysis_timestamp.isoformat()}",
                    f"Member Count: {analysis.member_count:,}",
                    f"Size Category: {analysis.size_category}"
                ]
                
                # Update metadata
                content_analysis.created_at = analysis.analysis_timestamp
                content_analysis.updated_at = analysis.analysis_timestamp
                
                session.commit()
                
                logger.success(f"Telegram analysis stored successfully for link ID {link_id}")
                return True
                
        except IntegrityError as e:
            logger.error(f"Database integrity error storing Telegram analysis: {e}")
            return False
        except Exception as e:
            logger.error(f"Error storing Telegram analysis: {e}")
            return False
    
    def analyze_and_store(self, link_id: int, telegram_url: str, 
                         project_name: str = None) -> bool:
        """
        Complete workflow: analyze Telegram channel and store results.
        
        Args:
            link_id: Database ID of the project link
            telegram_url: Telegram URL to analyze
            project_name: Optional project name for context
            
        Returns:
            True if analysis and storage successful, False otherwise
        """
        
        logger.info(f"Starting complete Telegram analysis workflow for link ID {link_id}")
        
        # Perform analysis
        analysis = self.analyze_telegram_link(link_id, telegram_url, project_name)
        if not analysis:
            logger.error(f"Telegram analysis failed for link ID {link_id}")
            return False
        
        # Store results
        if not self.store_analysis_result(link_id, analysis):
            logger.error(f"Failed to store Telegram analysis results for link ID {link_id}")
            return False
        
        # Update the project link to mark it as analyzed
        try:
            with self.db_manager.get_session() as session:
                link = session.query(ProjectLink).filter_by(id=link_id).first()
                if link:
                    link.needs_analysis = False
                    link.last_scraped = datetime.now(timezone.utc)
                    link.scrape_success = True
                    session.commit()
                    logger.info(f"Updated project link {link_id} status")
        except Exception as e:
            logger.warning(f"Could not update project link status: {e}")
        
        logger.success(f"Complete Telegram analysis workflow finished for link ID {link_id}")
        return True
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics."""
        return self.api_client.get_usage_stats()
    
    def can_analyze_more(self) -> tuple[bool, str]:
        """Check if we can perform more analyses."""
        return self.api_client.can_make_request()


def analyze_telegram_link_batch(database_url: str, limit: int = 10) -> Dict[str, Any]:
    """
    Batch analyze Telegram links that need analysis.
    
    Args:
        database_url: Database connection URL
        limit: Maximum number of links to analyze
        
    Returns:
        Dictionary with analysis results and statistics
    """
    
    logger.info(f"Starting Telegram batch analysis (limit: {limit})")
    
    # Initialize components
    db_manager = DatabaseManager(database_url)
    analyzer = TelegramContentAnalyzer(db_manager)
    
    # Check initial usage
    initial_stats = analyzer.get_usage_stats()
    logger.info(f"Initial API usage: {initial_stats['minute_usage']}/{initial_stats['minute_limit']} per minute")
    
    if initial_stats['minute_remaining'] <= 0:
        logger.error("No API calls remaining this minute")
        return {
            'success': False,
            'error': 'No API calls remaining',
            'stats': initial_stats
        }
    
    # Find Telegram links that need analysis
    with db_manager.get_session() as session:
        telegram_links = session.execute(text("""
            SELECT 
                pl.id,
                pl.url,
                cp.name as project_name,
                cp.code as project_code
            FROM project_links pl
            JOIN crypto_projects cp ON pl.project_id = cp.id
            WHERE pl.link_type = 'telegram'
                AND pl.needs_analysis = TRUE
                AND pl.url IS NOT NULL
                AND pl.url != ''
                AND NOT EXISTS (
                    SELECT 1 FROM link_content_analysis lca 
                    WHERE lca.link_id = pl.id
                )
            ORDER BY cp.market_cap DESC NULLS LAST, cp.rank ASC NULLS LAST
            LIMIT :limit
        """), {'limit': limit}).fetchall()
    
    if not telegram_links:
        logger.info("No Telegram links found that need analysis")
        return {
            'success': True,
            'analyzed': 0,
            'message': 'No links need analysis'
        }
    
    logger.info(f"Found {len(telegram_links)} Telegram links to analyze")
    
    # Process each link
    results = {
        'success': True,
        'analyzed': 0,
        'failed': 0,
        'skipped': 0,
        'api_calls_used': 0,
        'analyses': []
    }
    
    for link in telegram_links:
        link_id, telegram_url, project_name, project_code = link
        
        # Check if we can still make API calls
        can_proceed, reason = analyzer.can_analyze_more()
        if not can_proceed:
            logger.warning(f"Stopping batch analysis: {reason}")
            results['skipped'] = len(telegram_links) - results['analyzed'] - results['failed']
            break
        
        logger.info(f"Analyzing Telegram for {project_name} ({project_code}): {telegram_url}")
        
        try:
            success = analyzer.analyze_and_store(link_id, telegram_url, project_name)
            
            if success:
                results['analyzed'] += 1
                results['analyses'].append({
                    'link_id': link_id,
                    'project_name': project_name,
                    'telegram_url': telegram_url,
                    'status': 'success'
                })
                logger.success(f"✅ Analysis complete for {project_name}")
            else:
                results['failed'] += 1
                results['analyses'].append({
                    'link_id': link_id,
                    'project_name': project_name,
                    'telegram_url': telegram_url,
                    'status': 'failed'
                })
                logger.error(f"❌ Analysis failed for {project_name}")
                
        except Exception as e:
            results['failed'] += 1
            logger.error(f"❌ Exception analyzing {project_name}: {e}")
            results['analyses'].append({
                'link_id': link_id,
                'project_name': project_name,
                'telegram_url': telegram_url,
                'status': 'error',
                'error': str(e)
            })
        
        # Brief pause between analyses
        time.sleep(1)
    
    # Final usage stats
    final_stats = analyzer.get_usage_stats()
    results['api_calls_used'] = final_stats['minute_usage'] - initial_stats['minute_usage']
    results['final_usage'] = final_stats
    
    logger.info(f"Telegram batch analysis complete:")
    logger.info(f"  ✅ Analyzed: {results['analyzed']}")
    logger.info(f"  ❌ Failed: {results['failed']}")
    logger.info(f"  ⏭️  Skipped: {results['skipped']}")
    logger.info(f"  🔧 API calls used: {results['api_calls_used']}")
    logger.info(f"  📊 Remaining calls: {final_stats['minute_remaining']}")
    
    return results


def main():
    """Test the Telegram analyzer."""
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    
    if len(sys.argv) > 1 and sys.argv[1] == 'batch':
        # Run batch analysis
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        results = analyze_telegram_link_batch(database_url, limit)
        
        print("\n=== Batch Analysis Results ===")
        print(f"Analyzed: {results['analyzed']}")
        print(f"Failed: {results['failed']}")
        print(f"API calls used: {results['api_calls_used']}")
        
    else:
        # Test single analysis
        db_manager = DatabaseManager(database_url)
        analyzer = TelegramContentAnalyzer(db_manager)
        
        # Test with a known crypto project Telegram
        test_url = "https://t.me/ethereum"
        analysis = analyzer.analyze_telegram_link(1, test_url, "Ethereum")
        
        if analysis:
            print(f"\n=== Analysis Results for @{analysis.channel_id} ===")
            print(f"Channel: {analysis.channel_title}")
            print(f"Type: {analysis.channel_type}")
            print(f"Members: {analysis.member_count:,}")
            print(f"Overall Score: {analysis.overall_score:.2f}/10")
            print(f"Health Status: {analysis.health_status.title()}")
            print(f"Confidence: {analysis.confidence_score:.2f}")
            
            if analysis.positive_indicators:
                print(f"\nPositive Indicators:")
                for indicator in analysis.positive_indicators[:5]:
                    print(f"  ✅ {indicator}")
            
            if analysis.red_flags:
                print(f"\nRed Flags:")
                for flag in analysis.red_flags[:5]:
                    print(f"  🚩 {flag}")
        
        stats = analyzer.get_usage_stats()
        print(f"\nAPI Usage: {stats['minute_usage']}/{stats['minute_limit']} per minute ({stats['usage_percentage']:.1f}%)")


if __name__ == "__main__":
    main()