"""
Reddit Scraper Module for Cryptocurrency Project Analysis

This module handles:
- Fetching subreddit information and recent posts using PRAW
- Analyzing community activity and engagement metrics
- Tracking mention frequency across crypto subreddits
- Analyzing post types (technical vs hype content)
- Assessing moderator activity and community management
- Sentiment analysis of Reddit discussions
"""

import praw
import time
import hashlib
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
from pathlib import Path
import sys
import re

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
import os
from dotenv import load_dotenv

# Load environment variables
config_path = Path(__file__).parent.parent.parent / "config" / "env"
load_dotenv(config_path)


@dataclass
class RedditPost:
    """Represents a single Reddit post with metadata."""
    id: str
    title: str
    content: str
    author: str
    score: int  # Upvotes - downvotes
    upvote_ratio: float  # Ratio of upvotes
    num_comments: int
    created_utc: datetime
    subreddit: str
    url: str
    post_type: str  # 'technical', 'news', 'discussion', 'hype', 'question', 'other'
    is_stickied: bool
    is_moderator_post: bool
    flair: Optional[str]


@dataclass
class SubredditInfo:
    """Information about a subreddit."""
    name: str
    display_name: str
    description: str
    subscribers: int
    active_users: int  # Currently online
    created_utc: datetime
    is_over18: bool
    public_description: str
    moderator_count: int
    rules_count: int


@dataclass
class RedditAnalysisResult:
    """Complete Reddit community analysis result."""
    subreddit_name: str
    subreddit_url: str
    subreddit_info: Optional[SubredditInfo]
    posts_analyzed: List[RedditPost]
    total_posts: int
    scrape_success: bool
    error_message: Optional[str] = None
    analysis_timestamp: datetime = None
    
    # Community metrics
    community_activity_score: float = 0.0  # Posts per day over analysis period
    engagement_quality_score: float = 0.0  # Average score per post
    discussion_depth_score: float = 0.0  # Average comments per post
    moderator_activity_score: float = 0.0  # % of posts with mod interaction
    
    # Content analysis
    content_type_distribution: Dict[str, int] = None  # Count by post type
    avg_upvote_ratio: float = 0.0
    sentiment_indicators: Dict[str, int] = None  # Positive/negative/neutral counts
    
    # Cross-subreddit mentions (for broader crypto projects)
    mention_frequency: int = 0
    mention_subreddits: List[str] = None


class RedditScraper:
    """Reddit scraper for cryptocurrency project community analysis."""
    
    def __init__(self, 
                 recent_days: int = 30,
                 max_posts: int = 100,
                 rate_limit_delay: float = 0.5):
        """
        Initialize the Reddit scraper.
        
        Args:
            recent_days: Analyze posts from the last N days
            max_posts: Maximum number of posts to analyze per subreddit
            rate_limit_delay: Delay between API calls in seconds
        """
        self.recent_days = recent_days
        self.max_posts = max_posts
        self.rate_limit_delay = rate_limit_delay
        
        # Initialize Reddit API client
        # Using read-only mode with proper credentials
        self.reddit_available = False
        try:
            client_id = os.getenv('REDDIT_CLIENT_ID')
            client_secret = os.getenv('REDDIT_CLIENT_SECRET')
            user_agent = os.getenv('REDDIT_USER_AGENT', 'crypto-analytics-scraper/1.0')
            
            if not client_id or not client_secret or client_id == 'your_reddit_client_id_here':
                logger.warning("Reddit API credentials not properly configured - Reddit scraping disabled")
                logger.info("💡 To enable Reddit analysis, set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in config/env")
                logger.info("   Get credentials at: https://www.reddit.com/prefs/apps")
                self.reddit = None
                return
            
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                check_for_async=False,
                # Read-only mode settings
                username=None,
                password=None
            )
            
            # Test connection by accessing a public subreddit
            test_sub = self.reddit.subreddit('test')
            _ = test_sub.display_name  # This will fail if credentials are invalid
            
            self.reddit.read_only = True
            self.reddit_available = True
            logger.info("🔗 Reddit API connection initialized successfully in read-only mode")
            
        except Exception as e:
            error_msg = str(e).lower()
            if "401" in error_msg or "unauthorized" in error_msg:
                logger.error(f"❌ Reddit API authentication failed - check your client_id and client_secret")
                logger.info("   Verify credentials at: https://www.reddit.com/prefs/apps")
            elif "403" in error_msg:
                logger.error(f"❌ Reddit API access forbidden - check app permissions")
            else:
                logger.error(f"❌ Reddit API initialization failed: {e}")
            
            logger.info("📴 Reddit analysis disabled until API credentials are configured properly")
            self.reddit = None
            self.reddit_available = False
        
        # Keywords for classifying post types
        self.technical_keywords = [
            'technical', 'code', 'development', 'github', 'update', 'release',
            'protocol', 'blockchain', 'consensus', 'node', 'wallet', 'integration',
            'api', 'documentation', 'tutorial', 'guide', 'analysis', 'research'
        ]
        
        self.news_keywords = [
            'news', 'announcement', 'partnership', 'collaboration', 'launch',
            'release', 'update', 'breaking', 'official', 'confirmed'
        ]
        
        self.hype_keywords = [
            'moon', 'pump', 'bullish', 'bearish', 'hodl', 'diamond hands',
            'to the moon', 'rocket', 'lambo', 'wen', 'predictions', 'price target'
        ]
        
        self.discussion_keywords = [
            'discussion', 'thoughts', 'opinion', 'what do you think', 'community',
            'future', 'potential', 'pros and cons', 'comparison', 'vs'
        ]
        
        # Crypto subreddits for cross-mention analysis
        self.crypto_subreddits = [
            'cryptocurrency', 'cryptomarkets', 'altcoin', 'defi', 'bitcoin',
            'ethereum', 'cryptomoonshots', 'satoshistreetbets'
        ]
    
    def extract_subreddit_from_url(self, reddit_url: str) -> str:
        """
        Extract subreddit name from Reddit URL.
        
        Args:
            reddit_url: Reddit URL (e.g., https://reddit.com/r/bitcoin)
            
        Returns:
            Subreddit name (e.g., 'bitcoin')
        """
        try:
            # Handle different Reddit URL formats
            if '/r/' in reddit_url:
                # Extract subreddit name from URL like https://reddit.com/r/bitcoin
                parts = reddit_url.split('/r/')
                if len(parts) > 1:
                    subreddit_name = parts[1].split('/')[0]
                    return subreddit_name.lower()
            elif 'reddit.com/' in reddit_url:
                # Handle other Reddit URL formats
                parsed = urlparse(reddit_url)
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 2 and path_parts[0] == 'r':
                    return path_parts[1].lower()
            
            # If we can't extract from URL, try to guess from the URL itself
            logger.warning(f"Could not extract subreddit name from {reddit_url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting subreddit from {reddit_url}: {e}")
            return None
    
    def classify_post_type(self, title: str, content: str, flair: Optional[str] = None) -> str:
        """
        Classify the post type based on title, content, and flair.
        
        Returns:
            Post type: 'technical', 'news', 'discussion', 'hype', 'question', 'other'
        """
        combined_text = f"{title} {content} {flair or ''}".lower()
        
        # Count keyword matches for each category
        technical_count = sum(1 for keyword in self.technical_keywords if keyword in combined_text)
        news_count = sum(1 for keyword in self.news_keywords if keyword in combined_text)
        hype_count = sum(1 for keyword in self.hype_keywords if keyword in combined_text)
        discussion_count = sum(1 for keyword in self.discussion_keywords if keyword in combined_text)
        
        # Check for question indicators
        if '?' in title or combined_text.startswith(('how', 'what', 'why', 'when', 'where', 'eli5')):
            return 'question'
        
        # Return the category with the highest count
        category_scores = {
            'technical': technical_count,
            'news': news_count,
            'hype': hype_count,
            'discussion': discussion_count
        }
        
        max_score = max(category_scores.values())
        if max_score == 0:
            return 'other'
        
        for category, score in category_scores.items():
            if score == max_score:
                return category
        
        return 'other'
    
    def analyze_sentiment_indicators(self, posts: List[RedditPost]) -> Dict[str, int]:
        """Analyze sentiment indicators from posts."""
        sentiment_indicators = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        positive_words = ['good', 'great', 'awesome', 'bullish', 'up', 'rise', 'gain', 'profit', 'success']
        negative_words = ['bad', 'terrible', 'bearish', 'down', 'fall', 'loss', 'fail', 'crash', 'dump']
        
        for post in posts:
            text = f"{post.title} {post.content}".lower()
            positive_count = sum(1 for word in positive_words if word in text)
            negative_count = sum(1 for word in negative_words if word in text)
            
            if positive_count > negative_count:
                sentiment_indicators['positive'] += 1
            elif negative_count > positive_count:
                sentiment_indicators['negative'] += 1
            else:
                sentiment_indicators['neutral'] += 1
        
        return sentiment_indicators
    
    def get_subreddit_info(self, subreddit_name: str) -> Optional[SubredditInfo]:
        """Get information about a subreddit with graceful error handling."""
        if not self.reddit_available or not self.reddit:
            logger.debug(f"Reddit API not available for subreddit info: {subreddit_name}")
            return None
            
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Try to get basic info first (most likely to succeed)
            basic_info = {
                'name': subreddit.display_name,
                'display_name': subreddit.display_name_prefixed,
                'subscribers': getattr(subreddit, 'subscribers', 0),
                'is_over18': getattr(subreddit, 'over18', False),
                'created_utc': datetime.fromtimestamp(getattr(subreddit, 'created_utc', 0), tz=UTC) if getattr(subreddit, 'created_utc', 0) else datetime.now(UTC)
            }
            
            # Try to get additional info (may fail with 403)
            additional_info = {}
            
            # Safely get description
            try:
                additional_info['description'] = (subreddit.description or "")[:500]
            except:
                additional_info['description'] = ""
            
            # Safely get public description
            try:
                additional_info['public_description'] = (subreddit.public_description or "")[:200]
            except:
                additional_info['public_description'] = ""
            
            # Safely get active users
            try:
                additional_info['active_users'] = getattr(subreddit, 'accounts_active', 0)
            except:
                additional_info['active_users'] = 0
            
            # Safely get moderator count (often restricted)
            try:
                additional_info['moderator_count'] = len(list(subreddit.moderator()))
            except:
                additional_info['moderator_count'] = 0
            
            # Safely get rules count (often restricted)
            try:
                additional_info['rules_count'] = len(list(subreddit.rules))
            except:
                additional_info['rules_count'] = 0
            
            info = SubredditInfo(
                name=basic_info['name'],
                display_name=basic_info['display_name'],
                description=additional_info['description'],
                subscribers=basic_info['subscribers'],
                active_users=additional_info['active_users'],
                created_utc=basic_info['created_utc'],
                is_over18=basic_info['is_over18'],
                public_description=additional_info['public_description'],
                moderator_count=additional_info['moderator_count'],
                rules_count=additional_info['rules_count']
            )
            
            logger.debug(f"Retrieved subreddit info for r/{subreddit_name}")
            return info
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Handle different error types with appropriate logging levels
            if "403" in error_msg or "forbidden" in error_msg:
                # 403 is expected for restricted subreddits - log as debug only
                logger.debug(f"Subreddit info restricted for r/{subreddit_name} (403 Forbidden) - will attempt to scrape posts directly")
            elif "404" in error_msg or "not found" in error_msg:
                # 404 means subreddit doesn't exist - this is a real issue
                logger.warning(f"Subreddit r/{subreddit_name} does not exist (404 Not Found)")
            elif "401" in error_msg or "unauthorized" in error_msg:
                # 401 means authentication problem - this needs attention
                logger.error(f"Authentication failed for subreddit info r/{subreddit_name} - check Reddit API credentials")
            elif "private" in error_msg:
                # Private subreddit
                logger.debug(f"Subreddit r/{subreddit_name} is private - will attempt to scrape posts if possible")
            else:
                # Other errors
                logger.debug(f"Could not retrieve subreddit info for r/{subreddit_name}: {e}")
                
            return None
    
    def scrape_subreddit_posts(self, subreddit_name: str) -> List[RedditPost]:
        """
        Scrape recent posts from a subreddit.
        
        Args:
            subreddit_name: Name of the subreddit to scrape
            
        Returns:
            List of RedditPost objects
        """
        if not self.reddit_available or not self.reddit:
            logger.error(f"Reddit API not available for scraping r/{subreddit_name}")
            return []
            
        try:
            logger.info(f"Scraping posts from r/{subreddit_name}")
            
            subreddit = self.reddit.subreddit(subreddit_name)
            cutoff_date = datetime.now(UTC) - timedelta(days=self.recent_days)
            
            posts = []
            
            # Get recent posts (hot, new, top from week)
            post_sources = [
                ('hot', subreddit.hot(limit=self.max_posts // 3)),
                ('new', subreddit.new(limit=self.max_posts // 3)),
                ('top_week', subreddit.top(time_filter='week', limit=self.max_posts // 3))
            ]
            
            processed_ids = set()  # Avoid duplicates
            
            for source_name, posts_iterator in post_sources:
                for submission in posts_iterator:
                    try:
                        # Skip if already processed or too old
                        post_date = datetime.fromtimestamp(submission.created_utc, tz=UTC)
                        if submission.id in processed_ids or post_date < cutoff_date:
                            continue
                        
                        # Skip removed/deleted posts
                        if submission.selftext == '[removed]' or submission.selftext == '[deleted]':
                            continue
                        
                        processed_ids.add(submission.id)
                        
                        # Check if author is moderator
                        is_moderator_post = False
                        try:
                            if submission.author and submission.distinguished == 'moderator':
                                is_moderator_post = True
                        except:
                            pass
                        
                        # Get post content
                        content = submission.selftext if submission.selftext else ""
                        
                        # Classify post type
                        post_type = self.classify_post_type(
                            submission.title,
                            content,
                            submission.link_flair_text
                        )
                        
                        post = RedditPost(
                            id=submission.id,
                            title=submission.title,
                            content=content,
                            author=str(submission.author) if submission.author else "[deleted]",
                            score=submission.score,
                            upvote_ratio=submission.upvote_ratio,
                            num_comments=submission.num_comments,
                            created_utc=post_date,
                            subreddit=subreddit_name,
                            url=f"https://reddit.com{submission.permalink}",
                            post_type=post_type,
                            is_stickied=submission.stickied,
                            is_moderator_post=is_moderator_post,
                            flair=submission.link_flair_text
                        )
                        
                        posts.append(post)
                        
                        # Rate limiting
                        time.sleep(self.rate_limit_delay)
                        
                        if len(posts) >= self.max_posts:
                            break
                            
                    except Exception as e:
                        logger.warning(f"Error processing post {submission.id}: {e}")
                        continue
                
                if len(posts) >= self.max_posts:
                    break
            
            if len(posts) > 0:
                logger.success(f"Successfully scraped {len(posts)} posts from r/{subreddit_name}")
            else:
                logger.info(f"No recent posts found in r/{subreddit_name} (within last {self.recent_days} days)")
            return posts
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Handle different error types with appropriate logging levels and retry logic
            if "403" in error_msg or "forbidden" in error_msg:
                # 403 for posts means subreddit is truly restricted (private/banned)
                logger.warning(f"Access denied to r/{subreddit_name} posts (403 Forbidden) - subreddit is private, restricted, or banned")
            elif "404" in error_msg or "not found" in error_msg:
                # 404 means subreddit doesn't exist
                logger.warning(f"Subreddit r/{subreddit_name} does not exist (404 Not Found)")
            elif "401" in error_msg or "unauthorized" in error_msg:
                # 401 means authentication problem - this needs immediate attention
                logger.error(f"Authentication failed for r/{subreddit_name} - check Reddit API credentials (client_id/client_secret)")
            elif "429" in error_msg or "rate limit" in error_msg:
                # Rate limiting - suggest increasing delays
                logger.warning(f"Rate limit exceeded for r/{subreddit_name} - consider increasing rate_limit_delay")
            elif "private" in error_msg:
                # Private subreddit
                logger.warning(f"Subreddit r/{subreddit_name} is private and cannot be accessed")
            elif "quarantined" in error_msg:
                # Quarantined subreddit
                logger.warning(f"Subreddit r/{subreddit_name} is quarantined and cannot be accessed with current credentials")
            elif "banned" in error_msg:
                # Banned subreddit
                logger.warning(f"Subreddit r/{subreddit_name} is banned")
            else:
                # Other unexpected errors
                logger.error(f"Unexpected error scraping r/{subreddit_name}: {e}")
                
            return []
    
    def calculate_community_metrics(self, posts: List[RedditPost], subreddit_info: Optional[SubredditInfo]) -> Dict:
        """Calculate community engagement and activity metrics."""
        if not posts:
            return {
                'community_activity_score': 0.0,
                'engagement_quality_score': 0.0,
                'discussion_depth_score': 0.0,
                'moderator_activity_score': 0.0,
                'content_type_distribution': {},
                'avg_upvote_ratio': 0.0,
                'sentiment_indicators': {'positive': 0, 'negative': 0, 'neutral': 0}
            }
        
        # Community activity (posts per day)
        if len(posts) > 1:
            date_range = (max(p.created_utc for p in posts) - min(p.created_utc for p in posts)).days
            community_activity_score = len(posts) / max(date_range, 1) if date_range > 0 else len(posts)
        else:
            community_activity_score = 1.0
        
        # Engagement quality (average score)
        avg_score = sum(p.score for p in posts) / len(posts)
        engagement_quality_score = min(max(avg_score / 10, 0), 10)  # Normalize to 0-10
        
        # Discussion depth (average comments per post)
        avg_comments = sum(p.num_comments for p in posts) / len(posts)
        discussion_depth_score = min(avg_comments / 5, 10)  # Normalize to 0-10
        
        # Moderator activity (percentage of posts with mod interaction)
        mod_posts = sum(1 for p in posts if p.is_moderator_post)
        moderator_activity_score = (mod_posts / len(posts)) * 10
        
        # Content type distribution
        content_type_distribution = {}
        for post in posts:
            content_type_distribution[post.post_type] = content_type_distribution.get(post.post_type, 0) + 1
        
        # Average upvote ratio
        avg_upvote_ratio = sum(p.upvote_ratio for p in posts) / len(posts)
        
        # Sentiment indicators
        sentiment_indicators = self.analyze_sentiment_indicators(posts)
        
        return {
            'community_activity_score': min(community_activity_score, 10),
            'engagement_quality_score': engagement_quality_score,
            'discussion_depth_score': discussion_depth_score,
            'moderator_activity_score': moderator_activity_score,
            'content_type_distribution': content_type_distribution,
            'avg_upvote_ratio': avg_upvote_ratio,
            'sentiment_indicators': sentiment_indicators
        }
    
    def scrape_reddit_community(self, reddit_url: str) -> RedditAnalysisResult:
        """
        Scrape and analyze a Reddit community.
        
        Args:
            reddit_url: Reddit community URL
            
        Returns:
            RedditAnalysisResult with scraped content and analysis
        """
        logger.info(f"Starting Reddit analysis for: {reddit_url}")
        
        # Check if Reddit API is available
        if not self.reddit_available or not self.reddit:
            subreddit_name = self.extract_subreddit_from_url(reddit_url) or "unknown"
            logger.warning(f"🚫 Cannot analyze r/{subreddit_name} - Reddit API not configured")
            return RedditAnalysisResult(
                subreddit_name=subreddit_name,
                subreddit_url=reddit_url,
                subreddit_info=None,
                posts_analyzed=[],
                total_posts=0,
                scrape_success=False,
                error_message="Reddit API not available - configure REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in config/env",
                analysis_timestamp=datetime.now(UTC)
            )
        
        try:
            # Extract subreddit name
            subreddit_name = self.extract_subreddit_from_url(reddit_url)
            if not subreddit_name:
                return RedditAnalysisResult(
                    subreddit_name="unknown",
                    subreddit_url=reddit_url,
                    subreddit_info=None,
                    posts_analyzed=[],
                    total_posts=0,
                    scrape_success=False,
                    error_message="Could not extract subreddit name from URL",
                    analysis_timestamp=datetime.now(UTC)
                )
            
            # Get subreddit information
            subreddit_info = self.get_subreddit_info(subreddit_name)
            
            # Scrape posts
            posts = self.scrape_subreddit_posts(subreddit_name)
            
            # Log success context if subreddit info was restricted but posts worked
            if not subreddit_info and posts:
                logger.info(f"📊 Successfully analyzed r/{subreddit_name}: {len(posts)} posts scraped despite restricted subreddit info access")
            elif subreddit_info and posts:
                logger.debug(f"Complete analysis successful for r/{subreddit_name}: both subreddit info and posts retrieved")
            
            if not posts:
                # Determine more specific error message based on what we learned
                if subreddit_info is None:
                    error_message = "Subreddit appears to be private, restricted, banned, or does not exist - no content accessible"
                else:
                    error_message = f"No recent posts found in r/{subreddit_name} within the last {self.recent_days} days"
                
                return RedditAnalysisResult(
                    subreddit_name=subreddit_name,
                    subreddit_url=reddit_url,
                    subreddit_info=subreddit_info,
                    posts_analyzed=[],
                    total_posts=0,
                    scrape_success=False,
                    error_message=error_message,
                    analysis_timestamp=datetime.now(UTC)
                )
            
            # Calculate metrics
            metrics = self.calculate_community_metrics(posts, subreddit_info)
            
            result = RedditAnalysisResult(
                subreddit_name=subreddit_name,
                subreddit_url=reddit_url,
                subreddit_info=subreddit_info,
                posts_analyzed=posts,
                total_posts=len(posts),
                scrape_success=True,
                analysis_timestamp=datetime.now(UTC),
                community_activity_score=metrics['community_activity_score'],
                engagement_quality_score=metrics['engagement_quality_score'],
                discussion_depth_score=metrics['discussion_depth_score'],
                moderator_activity_score=metrics['moderator_activity_score'],
                content_type_distribution=metrics['content_type_distribution'],
                avg_upvote_ratio=metrics['avg_upvote_ratio'],
                sentiment_indicators=metrics['sentiment_indicators']
            )
            
            # Enhanced success logging with key metrics
            success_msg = f"✅ Reddit analysis complete for r/{subreddit_name}: {len(posts)} posts analyzed"
            if subreddit_info and subreddit_info.subscribers > 0:
                success_msg += f" ({subreddit_info.subscribers:,} subscribers)"
            
            # Add content type summary
            if metrics['content_type_distribution']:
                top_types = sorted(metrics['content_type_distribution'].items(), key=lambda x: x[1], reverse=True)[:2]
                type_summary = ", ".join([f"{count} {type_}" for type_, count in top_types])
                success_msg += f" - Content: {type_summary}"
            
            logger.success(success_msg)
            return result
            
        except Exception as e:
            logger.error(f"Reddit analysis failed for {reddit_url}: {e}")
            return RedditAnalysisResult(
                subreddit_name=subreddit_name if 'subreddit_name' in locals() else "unknown",
                subreddit_url=reddit_url,
                subreddit_info=None,
                posts_analyzed=[],
                total_posts=0,
                scrape_success=False,
                error_message=str(e),
                analysis_timestamp=datetime.now(UTC)
            )


# Test functionality
if __name__ == "__main__":
    scraper = RedditScraper(recent_days=7, max_posts=50)
    
    # Test with a few known crypto subreddits
    test_urls = [
        "https://reddit.com/r/bitcoin",
        "https://reddit.com/r/ethereum",
        "https://reddit.com/r/cardano"
    ]
    
    for url in test_urls:
        print(f"\n=== Testing {url} ===")
        result = scraper.scrape_reddit_community(url)
        print(f"Success: {result.scrape_success}")
        if result.scrape_success:
            print(f"Posts analyzed: {result.total_posts}")
            print(f"Community activity: {result.community_activity_score:.2f}/10")
            print(f"Engagement quality: {result.engagement_quality_score:.2f}/10")
            print(f"Discussion depth: {result.discussion_depth_score:.2f}/10")
            print(f"Content types: {result.content_type_distribution}")
            print(f"Sentiment: {result.sentiment_indicators}")
            if result.subreddit_info:
                print(f"Subscribers: {result.subreddit_info.subscribers}")
        else:
            print(f"Error: {result.error_message}")