"""
Telegram Bot API client for cryptocurrency project analysis.

This client is designed to analyze public Telegram channels/groups for crypto projects:
- Channel member count and growth tracking
- Message activity and engagement analysis
- Channel verification and legitimacy checks
- Community health metrics
"""

import os
import time
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from urllib.parse import urlparse

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
class TelegramRateLimit:
    """Telegram Bot API rate limiting configuration."""
    requests_per_second: int = 30  # Telegram allows 30 req/sec
    requests_per_minute: int = 20  # Conservative limit for channel info
    current_minute_usage: int = 0
    last_reset_minute: int = None
    

class TelegramAPIClient:
    """Client for Telegram Bot API with focus on channel analysis."""
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self, bot_token: str, database_manager: DatabaseManager):
        self.bot_token = bot_token
        self.db_manager = database_manager
        self.rate_limit = TelegramRateLimit()
        
        # Setup HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Default headers
        self.session.headers.update({
            'User-Agent': 'CryptoAnalytics-TelegramBot/1.0'
        })
        
        # Initialize usage tracking
        self._update_usage_counters()
        
        logger.info("Telegram API client initialized")
        logger.info(f"Rate limit: {self.rate_limit.requests_per_minute} req/min")
    
    def _update_usage_counters(self):
        """Update usage counters from database."""
        now = datetime.now(timezone.utc)
        
        with self.db_manager.get_session() as session:
            # Current minute usage
            minute_start = datetime(now.year, now.month, now.day, now.hour, now.minute, tzinfo=timezone.utc)
            minute_usage = session.query(APIUsage).filter(
                APIUsage.api_provider == 'telegram',
                APIUsage.request_timestamp >= minute_start,
                APIUsage.response_status == 200  # Only count successful requests
            ).count()
            
            self.rate_limit.current_minute_usage = minute_usage
            self.rate_limit.last_reset_minute = now.minute
    
    def _check_rate_limits(self) -> tuple[bool, str]:
        """Check if we can make a request within rate limits."""
        now = datetime.now(timezone.utc)
        
        # Reset minute counter if it's a new minute
        if self.rate_limit.last_reset_minute != now.minute:
            self._update_usage_counters()
        
        # Check minute limit
        if self.rate_limit.current_minute_usage >= self.rate_limit.requests_per_minute:
            return False, f"Minute limit exceeded ({self.rate_limit.current_minute_usage}/{self.rate_limit.requests_per_minute})"
        
        return True, "Rate limits OK"
    
    def _make_request(self, method: str, params: Dict = None) -> Optional[Dict]:
        """Make a request to the Telegram Bot API."""
        
        # Check rate limits before making request
        can_proceed, limit_message = self._check_rate_limits()
        if not can_proceed:
            logger.warning(f"Rate limit check failed: {limit_message}")
            return None
        
        url = f"{self.BASE_URL}{self.bot_token}/{method}"
        start_time = time.time()
        
        try:
            logger.debug(f"Making Telegram API request to {method}")
            
            response = self.session.get(url, params=params, timeout=30)
            response_time = time.time() - start_time
            
            # Log API usage to database
            with self.db_manager.get_session() as session:
                self.db_manager.log_api_usage(
                    session=session,
                    provider='telegram',
                    endpoint=method,
                    status=response.status_code,
                    response_size=len(response.content) if response.content else 0,
                    response_time=response_time
                )
                session.commit()
            
            # Update usage counters
            if response.status_code == 200:
                self.rate_limit.current_minute_usage += 1
                logger.debug(f"Telegram API request successful: {method}")
                
                result = response.json()
                
                # Check if the response indicates success
                if result.get('ok'):
                    return result.get('result')
                else:
                    error_code = result.get('error_code')
                    description = result.get('description', 'Unknown error')
                    logger.error(f"Telegram API error {error_code}: {description}")
                    return None
            
            elif response.status_code == 429:
                # Rate limit exceeded
                logger.warning("Telegram API rate limit exceeded")
                retry_after = response.headers.get('retry-after', '60')
                logger.info(f"Retry after {retry_after} seconds")
                time.sleep(min(int(retry_after), 300))  # Wait max 5 minutes
                return None
            
            elif response.status_code == 401:
                logger.error("Telegram API authentication failed - check bot token")
                return None
            
            elif response.status_code == 403:
                logger.warning("Telegram API access forbidden - bot may be blocked or channel is private")
                return None
            
            elif response.status_code == 404:
                logger.warning(f"Telegram API resource not found: {method}")
                return None
            
            else:
                logger.error(f"Telegram API request failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Telegram API request timeout: {method}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Telegram API connection error: {method}")
            return None
        except KeyboardInterrupt:
            logger.warning(f"KeyboardInterrupt received during API request: {method}")
            raise  # Re-raise to allow graceful shutdown
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Telegram API request: {e}")
            return None
    
    def extract_channel_id_from_url(self, telegram_url: str) -> Optional[str]:
        """Extract Telegram channel/group identifier from URL."""
        if not telegram_url:
            return None
        
        try:
            # Handle various Telegram URL formats
            patterns = [
                r't\.me/(.+)',           # https://t.me/channelname
                r'telegram\.me/(.+)',    # https://telegram.me/channelname
                r'telegram\.org/(.+)',  # https://telegram.org/channelname (rare)
            ]
            
            for pattern in patterns:
                match = re.search(pattern, telegram_url.lower())
                if match:
                    channel_id = match.group(1)
                    
                    # Remove any additional path components
                    channel_id = channel_id.split('/')[0]
                    channel_id = channel_id.split('?')[0]  # Remove query params
                    
                    # Clean up the channel ID
                    channel_id = channel_id.strip()
                    
                    # Skip common non-channel paths
                    skip_paths = ['joinchat', 'addstickers', 's', 'share', 'login', 'proxy']
                    if channel_id.lower() in skip_paths:
                        return None
                    
                    return channel_id if channel_id else None
            
            # Handle @username format
            if telegram_url.startswith('@'):
                return telegram_url[1:]
            
            # Handle plain username
            if telegram_url and not '/' in telegram_url and not '.' in telegram_url:
                return telegram_url.lstrip('@')
                
        except Exception as e:
            logger.warning(f"Error extracting channel ID from Telegram URL '{telegram_url}': {e}")
        
        return None
    
    def get_chat_info(self, chat_id: str) -> Optional[Dict]:
        """Get information about a chat/channel."""
        
        if not chat_id:
            return None
        
        # Clean chat_id - prepend @ if it doesn't start with one and isn't numeric
        if not chat_id.startswith('@') and not chat_id.lstrip('-').isdigit():
            chat_id = f"@{chat_id}"
        
        params = {'chat_id': chat_id}
        
        result = self._make_request('getChat', params)
        
        if result:
            logger.success(f"Retrieved chat info for {chat_id}")
            return result
        
        return None
    
    def get_chat_member_count(self, chat_id: str) -> Optional[int]:
        """Get the member count for a chat/channel."""
        
        if not chat_id:
            return None
        
        # Clean chat_id
        if not chat_id.startswith('@') and not chat_id.lstrip('-').isdigit():
            chat_id = f"@{chat_id}"
        
        params = {'chat_id': chat_id}
        
        result = self._make_request('getChatMemberCount', params)
        
        if result is not None:
            logger.success(f"Retrieved member count for {chat_id}: {result}")
            return int(result)
        
        return None
    
    def analyze_channel_profile(self, telegram_url: str) -> Optional[Dict]:
        """Comprehensive analysis of a Telegram channel/group."""
        
        channel_id = self.extract_channel_id_from_url(telegram_url)
        if not channel_id:
            logger.error(f"Could not extract channel ID from Telegram URL: {telegram_url}")
            return None
        
        logger.info(f"Analyzing Telegram channel: @{channel_id}")
        
        # Get basic chat information
        chat_info = self.get_chat_info(channel_id)
        if not chat_info:
            logger.error(f"Could not fetch chat info for @{channel_id}")
            return None
        
        # Get member count
        member_count = self.get_chat_member_count(channel_id)
        
        # Extract key metrics
        analysis = {
            'channel_id': channel_id,
            'chat_id': chat_info.get('id'),
            'title': chat_info.get('title'),
            'username': chat_info.get('username'),
            'type': chat_info.get('type'),  # 'channel', 'group', 'supergroup'
            'description': chat_info.get('description'),
            'invite_link': chat_info.get('invite_link'),
            'member_count': member_count or 0,
            
            # Channel settings
            'has_protected_content': chat_info.get('has_protected_content', False),
            'has_visible_history': chat_info.get('has_visible_history', True),
            'has_aggressive_anti_spam_enabled': chat_info.get('has_aggressive_anti_spam_enabled', False),
            
            # Additional info if available
            'pinned_message': chat_info.get('pinned_message'),
            'permissions': chat_info.get('permissions'),
            'slow_mode_delay': chat_info.get('slow_mode_delay'),
        }
        
        # Calculate derived metrics
        analysis.update(self._calculate_derived_metrics(analysis))
        
        logger.success(f"Telegram analysis complete for @{channel_id}")
        return analysis
    
    def _calculate_derived_metrics(self, channel_data: Dict) -> Dict:
        """Calculate derived metrics for Telegram channel analysis."""
        
        derived = {}
        
        # Channel type scoring
        channel_type = channel_data.get('type', '').lower()
        if channel_type == 'channel':
            derived['type_score'] = 10  # Broadcast channels are ideal for crypto projects
        elif channel_type == 'supergroup':
            derived['type_score'] = 8   # Large groups are good for community
        elif channel_type == 'group':
            derived['type_score'] = 6   # Regular groups are okay
        else:
            derived['type_score'] = 3   # Unknown or private
        
        # Member count analysis
        member_count = channel_data.get('member_count', 0)
        if member_count >= 100000:
            derived['size_category'] = 'large'
            derived['size_score'] = 10
        elif member_count >= 10000:
            derived['size_category'] = 'medium'
            derived['size_score'] = 8
        elif member_count >= 1000:
            derived['size_category'] = 'small'
            derived['size_score'] = 6
        elif member_count >= 100:
            derived['size_category'] = 'tiny'
            derived['size_score'] = 4
        else:
            derived['size_category'] = 'minimal'
            derived['size_score'] = 2
        
        # Content quality indicators
        quality_score = 5  # Base score
        
        if channel_data.get('description'):
            description = channel_data['description'].lower()
            # Look for official indicators
            if any(word in description for word in ['official', 'team', 'announcements']):
                quality_score += 2
            # Look for professional language
            if any(word in description for word in ['project', 'blockchain', 'development']):
                quality_score += 1
            # Deduct for spam indicators
            if any(word in description for word in ['pump', 'moon', 'guaranteed']):
                quality_score -= 2
        
        # Username indicates official status
        if channel_data.get('username'):
            quality_score += 1
        
        # Protected content suggests legitimate project
        if channel_data.get('has_protected_content'):
            quality_score += 1
        
        derived['quality_score'] = max(0, min(10, quality_score))
        
        return derived
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics."""
        
        # Update counters first
        self._update_usage_counters()
        
        return {
            'minute_limit': self.rate_limit.requests_per_minute,
            'minute_usage': self.rate_limit.current_minute_usage,
            'minute_remaining': self.rate_limit.requests_per_minute - self.rate_limit.current_minute_usage,
            'requests_per_second': self.rate_limit.requests_per_second,
            'usage_percentage': (self.rate_limit.current_minute_usage / self.rate_limit.requests_per_minute) * 100
        }
    
    def can_make_request(self) -> tuple[bool, str]:
        """Check if we can make another API request."""
        return self._check_rate_limits()


def main():
    """Test the Telegram API client."""
    
    # Load environment variables
    config_path = Path(__file__).parent.parent.parent / "config" / ".env"
    load_dotenv(config_path)
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize Telegram client
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        return
    
    client = TelegramAPIClient(bot_token, db_manager)
    
    # Show current usage
    stats = client.get_usage_stats()
    logger.info(f"Usage stats: {stats}")
    
    # Test with sample crypto project Telegram channels
    test_channels = [
        "https://t.me/ethereum",
        "https://t.me/bitcoin", 
        "@binance",
        "chainlink"
    ]
    
    for test_url in test_channels:
        can_proceed, message = client.can_make_request()
        if not can_proceed:
            logger.error(f"Cannot make request: {message}")
            break
        
        logger.info(f"\nTesting: {test_url}")
        
        # Analyze channel
        analysis = client.analyze_channel_profile(test_url)
        if analysis:
            logger.success("Channel analysis successful!")
            logger.info(f"Channel: {analysis['title']}")
            logger.info(f"Type: {analysis['type']}")
            logger.info(f"Members: {analysis['member_count']:,}")
            logger.info(f"Size Score: {analysis.get('size_score', 0)}/10")
            logger.info(f"Quality Score: {analysis.get('quality_score', 0)}/10")
        else:
            logger.error(f"Channel analysis failed for {test_url}")
        
        # Brief pause between requests
        time.sleep(2)
    
    # Show final usage
    final_stats = client.get_usage_stats()
    logger.info(f"Final usage stats: {final_stats}")


if __name__ == "__main__":
    main()