"""
Twitter Content Analyzer for Cryptocurrency Projects

This module integrates the Twitter API client with the analysis metrics
to provide comprehensive Twitter account analysis with database storage.
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
from collectors.twitter_api import TwitterAPIClient
from analyzers.twitter_analysis_metrics import TwitterAnalysisMetrics, TwitterAnalysisResult, TwitterHealthStatus

# Load environment variables
config_path = Path(__file__).parent.parent.parent / "config" / ".env"
load_dotenv(config_path)


@dataclass
class TwitterContentAnalysis:
    """Comprehensive Twitter content analysis result for database storage."""
    
    # Basic account info
    username: str
    user_id: str
    account_name: str
    account_description: Optional[str]
    account_location: Optional[str]
    account_url: Optional[str]
    profile_image_url: Optional[str]
    
    # Account metrics
    followers_count: int
    following_count: int
    tweet_count: int
    listed_count: int
    account_age_days: int
    verified: bool
    verified_type: Optional[str]
    protected: bool
    
    # Analysis scores (0-10)
    authenticity_score: float
    professional_score: float
    community_score: float
    activity_score: float
    engagement_quality_score: float
    overall_score: float
    
    # Derived metrics
    follower_following_ratio: float
    tweets_per_day: float
    profile_completeness_score: int
    
    # Health assessment
    health_status: str  # TwitterHealthStatus enum value
    confidence_score: float
    
    # Qualitative indicators
    red_flags: List[str]
    positive_indicators: List[str]
    
    # Analysis metadata
    analysis_timestamp: datetime
    api_calls_used: int
    data_quality_score: float  # How complete/reliable the data was


class TwitterContentAnalyzer:
    """Main analyzer that combines API client and metrics analysis."""
    
    def __init__(self, database_manager: DatabaseManager, api_client: TwitterAPIClient = None):
        """
        Initialize the Twitter content analyzer.
        
        Args:
            database_manager: Database manager for storing results
            api_client: Optional pre-initialized API client
        """
        self.db_manager = database_manager
        
        # Initialize API client if not provided
        if api_client is None:
            bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
            if not bearer_token:
                raise ValueError("TWITTER_BEARER_TOKEN environment variable not set")
            self.api_client = TwitterAPIClient(bearer_token, database_manager)
        else:
            self.api_client = api_client
        
        # Initialize metrics analyzer
        self.metrics_analyzer = TwitterAnalysisMetrics()
        
        logger.info("Twitter content analyzer initialized")
    
    def analyze_twitter_link(self, link_id: int, twitter_url: str, 
                           project_name: str = None) -> Optional[TwitterContentAnalysis]:
        """
        Analyze a Twitter account and return comprehensive results.
        
        Args:
            link_id: Database ID of the project link
            twitter_url: Twitter URL to analyze
            project_name: Optional project name for context
            
        Returns:
            TwitterContentAnalysis or None if analysis failed
        """
        
        logger.info(f"Starting Twitter analysis for link ID {link_id}: {twitter_url}")
        
        # Check if we can make API requests
        can_proceed, message = self.api_client.can_make_request()
        if not can_proceed:
            logger.error(f"Cannot proceed with Twitter analysis: {message}")
            return None
        
        # Extract username from URL
        username = self.api_client.extract_username_from_url(twitter_url)
        if not username:
            logger.error(f"Could not extract username from Twitter URL: {twitter_url}")
            return None
        
        # Track API usage before making call
        initial_usage = self.api_client.get_usage_stats()
        
        try:
            # Get profile analysis from API
            profile_analysis = self.api_client.analyze_user_profile(twitter_url)
            if not profile_analysis:
                logger.error(f"Failed to get profile analysis for @{username}")
                return None
            
            # Calculate API calls used
            final_usage = self.api_client.get_usage_stats()
            api_calls_used = final_usage['monthly_usage'] - initial_usage['monthly_usage']
            
            # Run metrics analysis
            metrics_result = self.metrics_analyzer.analyze_account(profile_analysis)
            
            # Calculate data quality score
            data_quality_score = self._calculate_data_quality_score(profile_analysis)
            
            # Combine results into analysis object
            analysis = TwitterContentAnalysis(
                username=username,
                user_id=profile_analysis.get('user_id', ''),
                account_name=profile_analysis.get('name', ''),
                account_description=profile_analysis.get('description'),
                account_location=profile_analysis.get('location'),
                account_url=profile_analysis.get('url'),
                profile_image_url=profile_analysis.get('profile_image_url'),
                
                followers_count=profile_analysis.get('followers_count', 0),
                following_count=profile_analysis.get('following_count', 0),
                tweet_count=profile_analysis.get('tweet_count', 0),
                listed_count=profile_analysis.get('listed_count', 0),
                account_age_days=profile_analysis.get('account_age_days', 0),
                verified=profile_analysis.get('verified', False),
                verified_type=profile_analysis.get('verified_type'),
                protected=profile_analysis.get('protected', False),
                
                authenticity_score=metrics_result.authenticity_score,
                professional_score=metrics_result.professional_score,
                community_score=metrics_result.community_score,
                activity_score=metrics_result.activity_score,
                engagement_quality_score=metrics_result.engagement_quality_score,
                overall_score=metrics_result.overall_score,
                
                follower_following_ratio=profile_analysis.get('follower_following_ratio', 0),
                tweets_per_day=profile_analysis.get('tweets_per_day', 0),
                profile_completeness_score=profile_analysis.get('profile_completeness_score', 0),
                
                health_status=metrics_result.health_status.value,
                confidence_score=metrics_result.confidence_score,
                
                red_flags=metrics_result.red_flags,
                positive_indicators=metrics_result.positive_indicators,
                
                analysis_timestamp=datetime.now(timezone.utc),
                api_calls_used=api_calls_used,
                data_quality_score=data_quality_score
            )
            
            logger.success(f"Twitter analysis complete for @{username} (Score: {analysis.overall_score:.2f})")
            return analysis
            
        except Exception as e:
            logger.error(f"Error during Twitter analysis for @{username}: {e}")
            return None
    
    def _calculate_data_quality_score(self, profile_data: Dict) -> float:
        """Calculate how complete and reliable the profile data is (0-1)."""
        
        score = 0.0
        max_score = 0.0
        
        # Core fields that should be present
        core_fields = [
            ('user_id', 0.2),
            ('username', 0.15),
            ('name', 0.1),
            ('followers_count', 0.15),
            ('following_count', 0.1),
            ('tweet_count', 0.1),
            ('account_age_days', 0.2)
        ]
        
        for field, weight in core_fields:
            max_score += weight
            if profile_data.get(field) is not None:
                if field in ['followers_count', 'following_count', 'tweet_count']:
                    # Numeric fields should be >= 0
                    if profile_data[field] >= 0:
                        score += weight
                elif field == 'account_age_days':
                    # Account age should be > 0
                    if profile_data[field] > 0:
                        score += weight
                else:
                    # String fields should not be empty
                    if str(profile_data[field]).strip():
                        score += weight
        
        return min(1.0, score / max_score if max_score > 0 else 0)
    
    def store_analysis_result(self, link_id: int, analysis: TwitterContentAnalysis) -> bool:
        """
        Store Twitter analysis results in the database.
        
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
                    logger.info(f"Updating existing Twitter analysis for link ID {link_id}")
                    # Update existing record
                    content_analysis = existing_analysis
                else:
                    logger.info(f"Creating new Twitter analysis for link ID {link_id}")
                    # Create new record
                    content_analysis = LinkContentAnalysis(link_id=link_id)
                    session.add(content_analysis)
                
                # Store core data
                content_analysis.raw_content = json.dumps(asdict(analysis), default=str, indent=2)
                content_analysis.content_hash = hashlib.sha256(
                    analysis.username.encode() + str(analysis.analysis_timestamp).encode()
                ).hexdigest()
                content_analysis.pages_analyzed = 1
                content_analysis.total_word_count = len(analysis.account_description or '')
                
                # Store Twitter-specific data in JSON fields
                twitter_data = {
                    'username': analysis.username,
                    'user_id': analysis.user_id,
                    'account_name': analysis.account_name,
                    'followers_count': analysis.followers_count,
                    'following_count': analysis.following_count,
                    'tweet_count': analysis.tweet_count,
                    'listed_count': analysis.listed_count,
                    'account_age_days': analysis.account_age_days,
                    'verified': analysis.verified,
                    'verified_type': analysis.verified_type,
                    'protected': analysis.protected,
                    'follower_following_ratio': analysis.follower_following_ratio,
                    'tweets_per_day': analysis.tweets_per_day,
                    'profile_completeness_score': analysis.profile_completeness_score
                }
                
                content_analysis.technology_stack = [f"twitter_metrics_{k}" for k in twitter_data.keys()]
                content_analysis.core_features = analysis.positive_indicators
                content_analysis.red_flags = analysis.red_flags
                
                # Map Twitter scores to existing fields creatively
                content_analysis.technical_depth_score = analysis.authenticity_score
                content_analysis.content_quality_score = analysis.professional_score
                content_analysis.confidence_score = analysis.confidence_score
                
                # Store additional metrics in business information fields
                content_analysis.partnerships = [f"Community Score: {analysis.community_score:.1f}"]
                content_analysis.funding_raised = f"Activity Score: {analysis.activity_score:.1f}, Engagement: {analysis.engagement_quality_score:.1f}"
                content_analysis.development_stage = analysis.health_status
                
                # Store comprehensive data in roadmap_items
                content_analysis.roadmap_items = [
                    f"Overall Score: {analysis.overall_score:.2f}/10",
                    f"Health Status: {analysis.health_status}",
                    f"API Calls Used: {analysis.api_calls_used}",
                    f"Data Quality: {analysis.data_quality_score:.2f}",
                    f"Analysis Date: {analysis.analysis_timestamp.isoformat()}"
                ]
                
                # Update metadata
                content_analysis.created_at = analysis.analysis_timestamp
                content_analysis.updated_at = analysis.analysis_timestamp
                
                session.commit()
                
                logger.success(f"Twitter analysis stored successfully for link ID {link_id}")
                return True
                
        except IntegrityError as e:
            logger.error(f"Database integrity error storing Twitter analysis: {e}")
            return False
        except Exception as e:
            logger.error(f"Error storing Twitter analysis: {e}")
            return False
    
    def analyze_and_store(self, link_id: int, twitter_url: str, 
                         project_name: str = None) -> bool:
        """
        Complete workflow: analyze Twitter account and store results.
        
        Args:
            link_id: Database ID of the project link
            twitter_url: Twitter URL to analyze
            project_name: Optional project name for context
            
        Returns:
            True if analysis and storage successful, False otherwise
        """
        
        logger.info(f"Starting complete Twitter analysis workflow for link ID {link_id}")
        
        # Perform analysis
        analysis = self.analyze_twitter_link(link_id, twitter_url, project_name)
        if not analysis:
            logger.error(f"Twitter analysis failed for link ID {link_id}")
            return False
        
        # Store results
        if not self.store_analysis_result(link_id, analysis):
            logger.error(f"Failed to store Twitter analysis results for link ID {link_id}")
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
        
        logger.success(f"Complete Twitter analysis workflow finished for link ID {link_id}")
        return True
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics."""
        return self.api_client.get_usage_stats()
    
    def can_analyze_more(self) -> tuple[bool, str]:
        """Check if we can perform more analyses."""
        return self.api_client.can_make_request()


def analyze_twitter_link_batch(database_url: str, limit: int = 10) -> Dict[str, Any]:
    """
    Batch analyze Twitter links that need analysis.
    
    Args:
        database_url: Database connection URL
        limit: Maximum number of links to analyze
        
    Returns:
        Dictionary with analysis results and statistics
    """
    
    logger.info(f"Starting Twitter batch analysis (limit: {limit})")
    
    # Initialize components
    db_manager = DatabaseManager(database_url)
    analyzer = TwitterContentAnalyzer(db_manager)
    
    # Check initial usage
    initial_stats = analyzer.get_usage_stats()
    logger.info(f"Initial API usage: Monthly {initial_stats['monthly_usage']}/{initial_stats['monthly_limit']}, Daily {initial_stats['daily_usage']}/{initial_stats['daily_allocation']}")

    # Determine effective limit considering daily and monthly remaining calls
    effective_limit = limit
    if initial_stats['monthly_remaining'] <= 0:
        logger.error("No API calls remaining this month")
        return {
            'success': False,
            'error': 'No API calls remaining this month',
            'stats': initial_stats
        }
    if initial_stats['daily_remaining'] <= 0:
        logger.error("No API calls remaining today")
        return {
            'success': False,
            'error': 'No API calls remaining today',
            'stats': initial_stats
        }

    effective_limit = min(limit, initial_stats['daily_remaining'], initial_stats['monthly_remaining'])
    if effective_limit <= 0:
        logger.warning("Effective limit for analysis is 0, skipping batch.")
        return {
            'success': True,
            'analyzed': 0,
            'message': 'No API calls available for analysis within current limits'
        }

    # Find Twitter links that need analysis
    with db_manager.get_session() as session:
        twitter_links = session.execute(text("""
            SELECT 
                pl.id,
                pl.url,
                cp.name as project_name,
                cp.code as project_code
            FROM project_links pl
            JOIN crypto_projects cp ON pl.project_id = cp.id
            WHERE pl.link_type = 'twitter'
                AND pl.needs_analysis = TRUE
                AND pl.url IS NOT NULL
                AND pl.url != ''
                AND NOT EXISTS (
                    SELECT 1 FROM link_content_analysis lca 
                    WHERE lca.link_id = pl.id
                )
            ORDER BY cp.market_cap DESC NULLS LAST, cp.rank ASC NULLS LAST
            LIMIT :limit
        """), {'limit': effective_limit}).fetchall()
    
    if not twitter_links:
        logger.info("No Twitter links found that need analysis")
        return {
            'success': True,
            'analyzed': 0,
            'message': 'No links need analysis'
        }
    
    logger.info(f"Found {len(twitter_links)} Twitter links to analyze")
    
    # Process each link
    results = {
        'success': True,
        'analyzed': 0,
        'failed': 0,
        'skipped': 0,
        'api_calls_used': 0,
        'analyses': []
    }
    
    for link in twitter_links:
        link_id, twitter_url, project_name, project_code = link
        
        # Check if we can still make API calls
        can_proceed, reason = analyzer.can_analyze_more()
        if not can_proceed:
            logger.warning(f"Stopping batch analysis: {reason}")
            results['skipped'] = len(twitter_links) - results['analyzed'] - results['failed']
            break
        
        logger.info(f"Analyzing Twitter for {project_name} ({project_code}): {twitter_url}")
        
        try:
            success = analyzer.analyze_and_store(link_id, twitter_url, project_name)
            
            if success:
                results['analyzed'] += 1
                results['analyses'].append({
                    'link_id': link_id,
                    'project_name': project_name,
                    'twitter_url': twitter_url,
                    'status': 'success'
                })
                logger.success(f"✅ Analysis complete for {project_name}")
            else:
                results['failed'] += 1
                results['analyses'].append({
                    'link_id': link_id,
                    'project_name': project_name,
                    'twitter_url': twitter_url,
                    'status': 'failed'
                })
                logger.error(f"❌ Analysis failed for {project_name}")
                
        except Exception as e:
            results['failed'] += 1
            logger.error(f"❌ Exception analyzing {project_name}: {e}")
            results['analyses'].append({
                'link_id': link_id,
                'project_name': project_name,
                'twitter_url': twitter_url,
                'status': 'error',
                'error': str(e)
            })
        
        # Brief pause between analyses
        time.sleep(2)
    
    # Final usage stats
    final_stats = analyzer.get_usage_stats()
    results['api_calls_used'] = final_stats['monthly_usage'] - initial_stats['monthly_usage']
    results['final_usage'] = final_stats
    
    logger.info(f"Twitter batch analysis complete:")
    logger.info(f"  ✅ Analyzed: {results['analyzed']}")
    logger.info(f"  ❌ Failed: {results['failed']}")
    logger.info(f"  ⏭️  Skipped: {results['skipped']}")
    logger.info(f"  🔧 API calls used: {results['api_calls_used']}")
    logger.info(f"  📊 Remaining calls: {final_stats['monthly_remaining']}")
    
    return results


def main():
    """Test the Twitter analyzer."""
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    
    if len(sys.argv) > 1 and sys.argv[1] == 'batch':
        # Run batch analysis
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        results = analyze_twitter_link_batch(database_url, limit)
        
        print("\n=== Batch Analysis Results ===")
        print(f"Analyzed: {results['analyzed']}")
        print(f"Failed: {results['failed']}")
        print(f"API calls used: {results['api_calls_used']}")
        
    else:
        # Test single analysis
        db_manager = DatabaseManager(database_url)
        analyzer = TwitterContentAnalyzer(db_manager)
        
        # Test with Bitcoin's Twitter
        test_url = "https://twitter.com/bitcoin"
        analysis = analyzer.analyze_twitter_link(1, test_url, "Bitcoin")
        
        if analysis:
            print(f"\n=== Analysis Results for @{analysis.username} ===")
            print(f"Overall Score: {analysis.overall_score:.2f}/10")
            print(f"Health Status: {analysis.health_status.title()}")
            print(f"Followers: {analysis.followers_count:,}")
            print(f"Account Age: {analysis.account_age_days} days")
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
        print(f"\nAPI Usage: {stats['monthly_usage']}/{stats['monthly_limit']} ({stats['usage_percentage']:.1f}%)")


if __name__ == "__main__":
    main()