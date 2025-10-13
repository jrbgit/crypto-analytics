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
                 rate_limit_delay: float = 1.0):
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
        # Using read-only mode with minimal configuration
        try:
            self.reddit = praw.Reddit(
                client_id=os.getenv('REDDIT_CLIENT_ID', 'crypto-analytics'),
                client_secret=os.getenv('REDDIT_CLIENT_SECRET', 'not-needed-for-read-only'),
                user_agent='crypto-analytics-scraper/1.0 by u/crypto-analyst',
                check_for_async=False,
                # These settings help with read-only access
                username=None,
                password=None
            )
            # Test connection
            self.reddit.read_only = True
            logger.info("Reddit API connection initialized in read-only mode")
        except Exception as e:
            logger.warning(f"Reddit API initialization issue: {e}")
            logger.info("Will attempt to continue with basic functionality")
        
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
        """Get information about a subreddit."""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Get moderator count
            moderator_count = len(list(subreddit.moderator()))
            
            # Get rules count
            rules_count = len(list(subreddit.rules))
            
            info = SubredditInfo(
                name=subreddit.display_name,
                display_name=subreddit.display_name_prefixed,
                description=subreddit.description[:500] if subreddit.description else "",
                subscribers=subreddit.subscribers,
                active_users=subreddit.accounts_active if hasattr(subreddit, 'accounts_active') else 0,
                created_utc=datetime.fromtimestamp(subreddit.created_utc, tz=UTC),
                is_over18=subreddit.over18,
                public_description=subreddit.public_description[:200] if subreddit.public_description else "",
                moderator_count=moderator_count,
                rules_count=rules_count
            )
            
            return info
            
        except Exception as e:
            logger.warning(f"Could not get subreddit info for {subreddit_name}: {e}")
            return None
    
    def scrape_subreddit_posts(self, subreddit_name: str) -> List[RedditPost]:
        """
        Scrape recent posts from a subreddit.
        
        Args:
            subreddit_name: Name of the subreddit to scrape
            
        Returns:
            List of RedditPost objects
        """
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
            
            logger.info(f"Successfully scraped {len(posts)} posts from r/{subreddit_name}")
            return posts
            
        except Exception as e:
            logger.error(f"Error scraping r/{subreddit_name}: {e}")
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
            
            if not posts:
                return RedditAnalysisResult(
                    subreddit_name=subreddit_name,
                    subreddit_url=reddit_url,
                    subreddit_info=subreddit_info,
                    posts_analyzed=[],
                    total_posts=0,
                    scrape_success=False,
                    error_message="No posts found or subreddit access failed",
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
            
            logger.success(f"Reddit analysis complete for r/{subreddit_name}: {len(posts)} posts analyzed")
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