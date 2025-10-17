"""
Twitter API v2 client with comprehensive rate limiting and data collection.

This client is designed for the free tier (100 API calls/month) and includes:
- Strict rate limiting and usage tracking
- Comprehensive error handling and retries
- User profile and metrics extraction
- Database integration for usage logging
"""

import os
import time
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger
from dotenv import load_dotenv

# Import our database models
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.database import DatabaseManager, APIUsage


@dataclass
class TwitterRateLimit:
    """Twitter API rate limiting configuration."""
    monthly_limit: int = 100      # Free tier limit
    requests_per_day: int = 4     # Conservative daily allocation (100/30 days)
    current_monthly_usage: int = 0
    current_daily_usage: int = 0
    last_reset_date: datetime = None
    last_reset_month: int = None


class TwitterAPIClient:
    """Client for Twitter API v2 with strict rate limiting for free tier."""
    
    BASE_URL = "https://api.twitter.com/2"
    
    def __init__(self, bearer_token: str, database_manager: DatabaseManager):
        self.bearer_token = bearer_token
        self.db_manager = database_manager
        self.rate_limit = TwitterRateLimit()
        
        # Setup HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]  # Only retry GET requests
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Default headers
        self.session.headers.update({
            'Authorization': f'Bearer {self.bearer_token}',
            'User-Agent': 'CryptoAnalytics-TwitterBot/1.0'
        })
        
        # Initialize usage tracking
        self._update_usage_counters()
        
        logger.info("Twitter API client initialized")
        logger.info(f"Monthly usage: {self.rate_limit.current_monthly_usage}/{self.rate_limit.monthly_limit}")
        logger.info(f"Daily usage: {self.rate_limit.current_daily_usage}/{self.rate_limit.requests_per_day}")
    
    def _update_usage_counters(self):
        """Update usage counters from database."""
        now = datetime.now(timezone.utc)
        
        with self.db_manager.get_session() as session:
            # Monthly usage count
            month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            monthly_usage = session.query(APIUsage).filter(
                APIUsage.api_provider == 'twitter',
                APIUsage.request_timestamp >= month_start,
                APIUsage.status_code == 200  # Only count successful requests
            ).count()
            
            # Daily usage count
            day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            daily_usage = session.query(APIUsage).filter(
                APIUsage.api_provider == 'twitter',
                APIUsage.request_timestamp >= day_start,
                APIUsage.status_code == 200  # Only count successful requests
            ).count()
            
            self.rate_limit.current_monthly_usage = monthly_usage
            self.rate_limit.current_daily_usage = daily_usage
            self.rate_limit.last_reset_date = now.date()
            self.rate_limit.last_reset_month = now.month
    
    def _check_rate_limits(self) -> tuple[bool, str]:
        """Check if we can make a request within rate limits."""
        now = datetime.now(timezone.utc)
        
        # Reset daily counter if it's a new day
        if self.rate_limit.last_reset_date != now.date():
            self._update_usage_counters()
        
        # Reset monthly counter if it's a new month
        if self.rate_limit.last_reset_month != now.month:
            self._update_usage_counters()
        
        # Check monthly limit (hard limit)
        if self.rate_limit.current_monthly_usage >= self.rate_limit.monthly_limit:
            return False, f"Monthly limit exceeded ({self.rate_limit.current_monthly_usage}/{self.rate_limit.monthly_limit})"
        
        # Check daily allocation (soft limit to spread usage)
        if self.rate_limit.current_daily_usage >= self.rate_limit.requests_per_day:
            return False, f"Daily allocation exceeded ({self.rate_limit.current_daily_usage}/{self.rate_limit.requests_per_day})"
        
        return True, "Rate limits OK"
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make a request to the Twitter API with comprehensive error handling."""
        
        # Check rate limits before making request
        can_proceed, limit_message = self._check_rate_limits()
        if not can_proceed:
            logger.error(f"Rate limit check failed: {limit_message}")
            return None
        
        url = f"{self.BASE_URL}{endpoint}"
        start_time = time.time()
        
        try:
            logger.debug(f"Making Twitter API request to {endpoint}")
            logger.debug(f"Remaining monthly calls: {self.rate_limit.monthly_limit - self.rate_limit.current_monthly_usage}")
            
            response = self.session.get(url, params=params, timeout=30)
            response_time = time.time() - start_time
            
            # Log API usage to database
            with self.db_manager.get_session() as session:
                self.db_manager.log_api_usage(
                    session=session,
                    provider='twitter',
                    endpoint=endpoint,
                    status=response.status_code,
                    response_size=len(response.content) if response.content else 0,
                    response_time=response_time
                )
                session.commit()
            
            # Update usage counters
            if response.status_code == 200:
                self.rate_limit.current_monthly_usage += 1
                self.rate_limit.current_daily_usage += 1
                logger.success(f"Twitter API request successful: {endpoint}")
                logger.info(f"Monthly usage now: {self.rate_limit.current_monthly_usage}/{self.rate_limit.monthly_limit}")
                
                return response.json()
            
            elif response.status_code == 429:
                # Rate limit exceeded - log and wait
                logger.warning("Twitter API rate limit exceeded, backing off")
                rate_limit_reset = response.headers.get('x-rate-limit-reset')
                if rate_limit_reset:
                    reset_time = datetime.fromtimestamp(int(rate_limit_reset), tz=timezone.utc)
                    wait_time = (reset_time - datetime.now(timezone.utc)).total_seconds()
                    logger.info(f"Rate limit resets at {reset_time}, waiting {wait_time:.0f} seconds")
                    time.sleep(min(wait_time + 10, 900))  # Wait max 15 minutes
                return None
            
            elif response.status_code == 401:
                logger.error("Twitter API authentication failed - check bearer token")
                return None
            
            elif response.status_code == 403:
                logger.error("Twitter API access forbidden - check app permissions")
                return None
            
            elif response.status_code == 404:
                logger.warning(f"Twitter API resource not found: {endpoint}")
                return None
            
            else:
                logger.error(f"Twitter API request failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Twitter API request timeout: {endpoint}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Twitter API connection error: {endpoint}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Twitter API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Twitter API request: {e}")
            return None
    
    def extract_username_from_url(self, twitter_url: str) -> Optional[str]:
        """Extract Twitter username from URL."""
        if not twitter_url:
            return None
        
        try:
            # Handle various Twitter URL formats
            if 'twitter.com/' in twitter_url or 'x.com/' in twitter_url:
                # Parse URL and extract username
                parsed = urlparse(twitter_url)
                path = parsed.path.strip('/')
                
                # Handle formats like:
                # - https://twitter.com/username
                # - https://x.com/username
                # - https://twitter.com/username/status/123
                parts = path.split('/')
                if parts and parts[0] and not parts[0].startswith('@'):
                    username = parts[0]
                    # Clean up username (remove @ if present)
                    username = username.lstrip('@')
                    return username if username else None
            
            # Handle @username format
            elif twitter_url.startswith('@'):
                return twitter_url[1:]
            
            # Handle plain username
            elif twitter_url and not '/' in twitter_url and not '.' in twitter_url:
                return twitter_url.lstrip('@')
                
        except Exception as e:
            logger.warning(f"Error extracting username from Twitter URL '{twitter_url}': {e}")
        
        return None
    
    def get_user_by_username(self, username: str, include_metrics: bool = True) -> Optional[Dict]:
        """Get Twitter user data by username."""
        
        if not username:
            return None
        
        # Clean username
        username = username.lstrip('@').strip()
        
        # Build query parameters
        params = {
            'user.fields': 'created_at,description,location,pinned_tweet_id,profile_image_url,protected,public_metrics,url,verified,verified_type'
        }
        
        endpoint = f"/users/by/username/{username}"
        
        response = self._make_request(endpoint, params)
        
        if response and 'data' in response:
            user_data = response['data']
            
            # Add extracted username for consistency
            user_data['extracted_username'] = username
            
            return user_data
        
        return None
    
    def get_user_tweets(self, user_id: str, max_results: int = 10) -> Optional[List[Dict]]:
        """Get recent tweets for a user (limited usage due to API constraints)."""
        
        params = {
            'max_results': min(max_results, 10),  # Limit to preserve API calls
            'tweet.fields': 'created_at,public_metrics,context_annotations,lang'
        }
        
        endpoint = f"/users/{user_id}/tweets"
        
        response = self._make_request(endpoint, params)
        
        if response and 'data' in response:
            return response['data']
        
        return []
    
    def analyze_user_profile(self, twitter_url: str) -> Optional[Dict]:
        """Comprehensive analysis of a Twitter user profile."""
        
        username = self.extract_username_from_url(twitter_url)
        if not username:
            logger.error(f"Could not extract username from Twitter URL: {twitter_url}")
            return None
        
        logger.info(f"Analyzing Twitter profile: @{username}")
        
        # Get user profile data
        user_data = self.get_user_by_username(username)
        if not user_data:
            logger.error(f"Could not fetch user data for @{username}")
            return None
        
        # Extract key metrics
        analysis = {
            'username': username,
            'user_id': user_data.get('id'),
            'name': user_data.get('name'),
            'description': user_data.get('description'),
            'location': user_data.get('location'),
            'url': user_data.get('url'),
            'profile_image_url': user_data.get('profile_image_url'),
            'created_at': user_data.get('created_at'),
            'verified': user_data.get('verified', False),
            'verified_type': user_data.get('verified_type'),
            'protected': user_data.get('protected', False),
            
            # Public metrics
            'followers_count': 0,
            'following_count': 0,
            'tweet_count': 0,
            'listed_count': 0
        }
        
        # Extract public metrics if available
        if 'public_metrics' in user_data:
            metrics = user_data['public_metrics']
            analysis.update({
                'followers_count': metrics.get('followers_count', 0),
                'following_count': metrics.get('following_count', 0),
                'tweet_count': metrics.get('tweet_count', 0),
                'listed_count': metrics.get('listed_count', 0)
            })
        
        # Calculate derived metrics
        analysis.update(self._calculate_derived_metrics(analysis))
        
        logger.success(f"Twitter analysis complete for @{username}")
        return analysis
    
    def _calculate_derived_metrics(self, profile_data: Dict) -> Dict:
        """Calculate derived metrics for Twitter profile analysis."""
        
        derived = {}
        
        # Account age in days
        if profile_data.get('created_at'):
            try:
                created_date = datetime.fromisoformat(profile_data['created_at'].replace('Z', '+00:00'))
                account_age_days = (datetime.now(timezone.utc) - created_date).days
                derived['account_age_days'] = account_age_days
            except Exception as e:
                logger.warning(f"Error calculating account age: {e}")
                derived['account_age_days'] = None
        
        # Follower/following ratio
        followers = profile_data.get('followers_count', 0)
        following = profile_data.get('following_count', 0)
        
        if following > 0:
            derived['follower_following_ratio'] = followers / following
        else:
            derived['follower_following_ratio'] = followers if followers > 0 else 0
        
        # Tweets per day (average)
        tweet_count = profile_data.get('tweet_count', 0)
        account_age = derived.get('account_age_days', 0)
        
        if account_age > 0:
            derived['tweets_per_day'] = tweet_count / account_age
        else:
            derived['tweets_per_day'] = 0
        
        # Profile completeness score (0-10)
        completeness_score = 0
        if profile_data.get('name'): completeness_score += 1
        if profile_data.get('description'): completeness_score += 2
        if profile_data.get('location'): completeness_score += 1
        if profile_data.get('url'): completeness_score += 2
        if profile_data.get('profile_image_url'): completeness_score += 1
        if profile_data.get('verified'): completeness_score += 2
        if followers > 100: completeness_score += 1  # Has meaningful follower base
        
        derived['profile_completeness_score'] = completeness_score
        
        return derived
    
    def get_usage_stats(self) -> Dict:
        """Get current API usage statistics."""
        
        # Update counters first
        self._update_usage_counters()
        
        return {
            'monthly_limit': self.rate_limit.monthly_limit,
            'monthly_usage': self.rate_limit.current_monthly_usage,
            'monthly_remaining': self.rate_limit.monthly_limit - self.rate_limit.current_monthly_usage,
            'daily_allocation': self.rate_limit.requests_per_day,
            'daily_usage': self.rate_limit.current_daily_usage,
            'daily_remaining': self.rate_limit.requests_per_day - self.rate_limit.current_daily_usage,
            'usage_percentage': (self.rate_limit.current_monthly_usage / self.rate_limit.monthly_limit) * 100,
            'estimated_days_remaining': None
        }
    
    def can_make_request(self) -> tuple[bool, str]:
        """Check if we can make another API request."""
        return self._check_rate_limits()


def main():
    """Test the Twitter API client."""
    
    # Load environment variables
    config_path = Path(__file__).parent.parent.parent / "config" / ".env"
    load_dotenv(config_path)
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize Twitter client
    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
    if not bearer_token:
        logger.error("TWITTER_BEARER_TOKEN environment variable not set")
        return
    
    client = TwitterAPIClient(bearer_token, db_manager)
    
    # Show current usage
    stats = client.get_usage_stats()
    logger.info(f"Usage stats: {stats}")
    
    # Test with a sample crypto project (Bitcoin)
    test_url = "https://twitter.com/bitcoin"
    
    can_proceed, message = client.can_make_request()
    if not can_proceed:
        logger.error(f"Cannot make request: {message}")
        return
    
    # Analyze profile
    analysis = client.analyze_user_profile(test_url)
    if analysis:
        logger.success("Profile analysis successful!")
        logger.info(f"Username: @{analysis['username']}")
        logger.info(f"Name: {analysis['name']}")
        logger.info(f"Followers: {analysis['followers_count']:,}")
        logger.info(f"Account age: {analysis.get('account_age_days', 'Unknown')} days")
        logger.info(f"Profile completeness: {analysis.get('profile_completeness_score', 0)}/10")
    else:
        logger.error("Profile analysis failed")
    
    # Show final usage
    final_stats = client.get_usage_stats()
    logger.info(f"Final usage stats: {final_stats}")


if __name__ == "__main__":
    main()