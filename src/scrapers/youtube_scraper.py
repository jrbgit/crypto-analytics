"""
YouTube Scraper Module for Cryptocurrency Project Analysis

This module handles:
- Fetching YouTube channel information and recent videos using YouTube Data API v3
- Analyzing video metadata, descriptions, and engagement metrics
- Tracking content types (educational, promotional, technical updates)
- Monitoring upload frequency and community engagement
- Extracting project-related content from video descriptions
"""

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
config_path = Path(__file__).parent.parent.parent / "config" / ".env"
load_dotenv(config_path)

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from google.auth.transport.requests import Request
    import pickle
    import os
    # Allow insecure transport for localhost OAuth
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    logger.warning("Google API Client not installed. Run: pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2")
    YOUTUBE_API_AVAILABLE = False


@dataclass
class YouTubeVideo:
    """Represents a single YouTube video with metadata."""
    video_id: str
    title: str
    description: str
    published_at: datetime
    duration: str  # ISO 8601 duration (e.g., "PT4M13S")
    view_count: int
    like_count: int
    comment_count: int
    video_url: str
    thumbnail_url: str
    tags: List[str]
    category_id: str
    video_type: str  # 'educational', 'announcement', 'ama', 'technical', 'marketing', 'other'
    content_hash: str


@dataclass
class YouTubeChannelInfo:
    """Information about a YouTube channel."""
    channel_id: str
    title: str
    description: str
    subscriber_count: int
    video_count: int
    view_count: int
    created_at: datetime
    country: Optional[str]
    custom_url: Optional[str]
    profile_image_url: str
    banner_image_url: Optional[str]


@dataclass
class YouTubeAnalysisResult:
    """Complete YouTube channel analysis result."""
    channel_url: str
    channel_id: str
    channel_info: Optional[YouTubeChannelInfo]
    videos_analyzed: List[YouTubeVideo]
    total_videos: int
    scrape_success: bool
    error_message: Optional[str] = None
    analysis_timestamp: datetime = None
    
    # Channel metrics
    upload_frequency_score: float = 0.0  # Videos per week over analysis period
    engagement_quality_score: float = 0.0  # Average engagement rate
    content_consistency_score: float = 0.0  # Consistency of uploads
    subscriber_growth_indicator: str = "unknown"  # Estimated growth pattern
    
    # Content analysis
    content_type_distribution: Dict[str, int] = None  # Count by video type
    avg_view_count: float = 0.0
    avg_engagement_rate: float = 0.0  # (likes + comments) / views
    last_upload_date: Optional[datetime] = None
    
    # Quality indicators
    educational_content_ratio: float = 0.0  # Educational vs promotional content
    technical_depth_score: float = 0.0  # Based on content analysis


class YouTubeScraper:
    """YouTube scraper for cryptocurrency project channel analysis."""
    
    def __init__(self, 
                 recent_days: int = 90,
                 max_videos: int = 50,
                 rate_limit_delay: float = 0.1):
        """
        Initialize the YouTube scraper.
        
        Args:
            recent_days: Analyze videos from the last N days
            max_videos: Maximum number of videos to analyze per channel
            rate_limit_delay: Delay between API calls in seconds
        """
        self.recent_days = recent_days
        self.max_videos = max_videos
        self.rate_limit_delay = rate_limit_delay
        
        # Initialize YouTube API client
        self.youtube_available = False
        self.youtube = None
        
        if not YOUTUBE_API_AVAILABLE:
            logger.warning("YouTube API client not available - install google-api-python-client")
            return
            
        try:
            # OAuth 2.0 setup
            client_id = os.getenv('YOUTUBE_CLIENT_ID')
            client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
            
            if not client_id or not client_secret or client_id == 'your_youtube_client_id_here':
                logger.warning("YouTube OAuth credentials not properly configured - YouTube scraping disabled")
                logger.info("💡 To enable YouTube analysis, set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in config/env")
                logger.info("   Get OAuth credentials at: https://console.cloud.google.com/apis/credentials")
                return
            
            # Set up OAuth 2.0 credentials
            credentials = self._get_oauth_credentials(client_id, client_secret)
            if not credentials:
                logger.warning("Failed to obtain YouTube OAuth credentials")
                return
            
            self.youtube = build('youtube', 'v3', credentials=credentials)
            
            # Test API connection with a simple request (try to get any public channel)
            test_request = self.youtube.channels().list(
                part='snippet',
                id='UC_7PdcU2KlXMMkKABh5QyE',  # YouTube's own channel ID for testing
                maxResults=1
            )
            test_response = test_request.execute()
            
            self.youtube_available = True
            logger.info("🔗 YouTube API connection initialized successfully with OAuth 2.0")
            
        except HttpError as e:
            if e.resp.status == 403:
                logger.error("❌ YouTube API quota exceeded or API key invalid")
                logger.info("   Check your API quota at: https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas")
            elif e.resp.status == 400:
                logger.error("❌ YouTube API request invalid - check API key configuration")
            else:
                logger.error(f"❌ YouTube API error: {e}")
                
        except Exception as e:
            logger.error(f"❌ YouTube API initialization failed: {e}")
            
        if not self.youtube_available:
            logger.info("📴 YouTube analysis disabled until API key is configured properly")
        
        # Keywords for classifying video types
        self.educational_keywords = [
            'tutorial', 'how to', 'guide', 'learn', 'education', 'explained', 'basics',
            'introduction', 'beginner', 'course', 'lesson', 'workshop', 'training',
            'deep dive', 'analysis', 'review', 'comparison', 'technical analysis'
        ]
        
        self.announcement_keywords = [
            'announcement', 'news', 'update', 'release', 'launched', 'introducing',
            'new feature', 'partnership', 'collaboration', 'milestone', 'achievement',
            'upcoming', 'roadmap', 'development update', 'progress'
        ]
        
        self.ama_keywords = [
            'ama', 'ask me anything', 'q&a', 'questions', 'live', 'interview',
            'discussion', 'community', 'chat', 'talk', 'conversation', 'panel'
        ]
        
        self.technical_keywords = [
            'technical', 'development', 'coding', 'programming', 'blockchain',
            'smart contract', 'consensus', 'protocol', 'architecture', 'security',
            'audit', 'testnet', 'mainnet', 'node', 'validator', 'staking'
        ]
        
        self.marketing_keywords = [
            'marketing', 'promotion', 'brand', 'community', 'social', 'campaign',
            'contest', 'giveaway', 'competition', 'event', 'meetup', 'conference'
        ]
    
    def _get_oauth_credentials(self, client_id: str, client_secret: str) -> Optional[Credentials]:
        """Get OAuth 2.0 credentials for YouTube API access."""
        scopes = ['https://www.googleapis.com/auth/youtube.readonly']
        
        # Path to store credentials
        credentials_file = Path(__file__).parent.parent.parent / "config" / "youtube_credentials.pickle"
        
        credentials = None
        
        # Load existing credentials if available
        if credentials_file.exists():
            try:
                with open(credentials_file, 'rb') as token:
                    credentials = pickle.load(token)
                logger.debug("Loaded existing YouTube OAuth credentials")
            except Exception as e:
                logger.warning(f"Could not load existing credentials: {e}")
        
        # If there are no valid credentials available, request authorization
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    logger.info("Refreshed YouTube OAuth credentials")
                except Exception as e:
                    logger.warning(f"Could not refresh credentials: {e}")
                    credentials = None
            
            if not credentials:
                # Create OAuth flow configuration using web client
                client_config = {
                    "web": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost:8080"]
                    }
                }
                
                try:
                    # Use web flow for manual code exchange
                    flow = Flow.from_client_config(
                        client_config, scopes)
                    
                    # Set redirect URI on the flow
                    redirect_uri = 'http://localhost:8080'
                    flow.redirect_uri = redirect_uri
                    auth_url, _ = flow.authorization_url(
                        prompt='consent',
                        access_type='offline'
                    )
                    
                    print(f"\n🔗 Please visit this URL to authorize the application:")
                    print(f"{auth_url}\n")
                    print("After authorizing, you'll be redirected to a page that shows 'Bad Gateway'.")
                    print("Copy the full URL from your browser address bar and paste it here.")
                    print("The URL should look like: http://localhost:8080/?state=...&code=...")
                    
                    # Get full redirect URL from user
                    redirect_url = input("\n🔗 Paste the full redirect URL here: ").strip()
                    
                    if not redirect_url or 'code=' not in redirect_url:
                        raise ValueError("Invalid redirect URL provided")
                    
                    # Exchange authorization response for credentials
                    flow.fetch_token(authorization_response=redirect_url)
                    credentials = flow.credentials
                    
                    logger.info("Successfully obtained YouTube OAuth credentials")
                except Exception as e:
                    logger.error(f"OAuth flow failed: {e}")
                    logger.info("💡 Make sure you copy the authorization code correctly")
                    return None
        
        # Save credentials for future use
        if credentials:
            try:
                # Ensure config directory exists
                credentials_file.parent.mkdir(parents=True, exist_ok=True)
                with open(credentials_file, 'wb') as token:
                    pickle.dump(credentials, token)
                logger.debug("Saved YouTube OAuth credentials")
            except Exception as e:
                logger.warning(f"Could not save credentials: {e}")
        
        return credentials
    
    def extract_channel_id_from_url(self, youtube_url: str) -> Optional[str]:
        """
        Extract channel ID from various YouTube URL formats.
        
        Args:
            youtube_url: YouTube channel URL
            
        Returns:
            Channel ID or None if extraction fails
        """
        try:
            parsed = urlparse(youtube_url)
            
            # Handle different YouTube URL formats:
            # https://youtube.com/channel/UCxxxxx
            # https://youtube.com/@username
            # https://youtube.com/c/channelname
            # https://youtube.com/user/username
            
            if '/channel/' in parsed.path:
                # Direct channel ID URL
                channel_id = parsed.path.split('/channel/')[1].split('/')[0]
                return channel_id
            elif parsed.path.startswith('/@'):
                # Handle @username format
                username = parsed.path[2:].split('/')[0]  # Remove @ and get username
                return self._resolve_username_to_channel_id(username)
            elif '/c/' in parsed.path:
                # Custom channel URL
                channel_name = parsed.path.split('/c/')[1].split('/')[0]
                return self._resolve_custom_url_to_channel_id(channel_name)
            elif '/user/' in parsed.path:
                # Legacy user URL
                username = parsed.path.split('/user/')[1].split('/')[0]
                return self._resolve_username_to_channel_id(username)
            
            logger.warning(f"Could not extract channel ID from {youtube_url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting channel ID from {youtube_url}: {e}")
            return None
    
    def _resolve_username_to_channel_id(self, username: str) -> Optional[str]:
        """Resolve YouTube username/handle to channel ID using API."""
        if not self.youtube_available:
            return None
            
        try:
            # Try to search for the channel by username
            request = self.youtube.search().list(
                part='snippet',
                q=username,
                type='channel',
                maxResults=1
            )
            response = request.execute()
            
            if response['items']:
                return response['items'][0]['snippet']['channelId']
            
            return None
            
        except Exception as e:
            logger.warning(f"Could not resolve username {username} to channel ID: {e}")
            return None
    
    def _resolve_custom_url_to_channel_id(self, custom_url: str) -> Optional[str]:
        """Resolve custom YouTube URL to channel ID."""
        # For custom URLs, we need to use the search API as there's no direct resolution
        return self._resolve_username_to_channel_id(custom_url)
    
    def classify_video_type(self, title: str, description: str, tags: List[str]) -> str:
        """
        Classify the video type based on title, description, and tags.
        
        Returns:
            Video type: 'educational', 'announcement', 'ama', 'technical', 'marketing', 'other'
        """
        combined_text = f"{title} {description} {' '.join(tags)}".lower()
        
        # Count keyword matches for each category
        educational_count = sum(1 for keyword in self.educational_keywords if keyword in combined_text)
        announcement_count = sum(1 for keyword in self.announcement_keywords if keyword in combined_text)
        ama_count = sum(1 for keyword in self.ama_keywords if keyword in combined_text)
        technical_count = sum(1 for keyword in self.technical_keywords if keyword in combined_text)
        marketing_count = sum(1 for keyword in self.marketing_keywords if keyword in combined_text)
        
        # Return the category with the highest count
        category_scores = {
            'educational': educational_count,
            'announcement': announcement_count,
            'ama': ama_count,
            'technical': technical_count,
            'marketing': marketing_count
        }
        
        max_score = max(category_scores.values())
        if max_score == 0:
            return 'other'
        
        for category, score in category_scores.items():
            if score == max_score:
                return category
        
        return 'other'
    
    def get_channel_info(self, channel_id: str) -> Optional[YouTubeChannelInfo]:
        """Get information about a YouTube channel."""
        if not self.youtube_available:
            logger.debug(f"YouTube API not available for channel info: {channel_id}")
            return None
            
        try:
            request = self.youtube.channels().list(
                part='snippet,statistics,brandingSettings',
                id=channel_id
            )
            response = request.execute()
            
            if not response['items']:
                logger.warning(f"YouTube channel not found: {channel_id}")
                return None
            
            channel_data = response['items'][0]
            snippet = channel_data['snippet']
            statistics = channel_data.get('statistics', {})
            branding = channel_data.get('brandingSettings', {})
            
            # Parse creation date
            created_at = datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00'))
            
            # Get profile and banner images
            thumbnails = snippet.get('thumbnails', {})
            profile_image_url = thumbnails.get('high', {}).get('url', '') or thumbnails.get('default', {}).get('url', '')
            
            banner_image_url = None
            if 'image' in branding and 'bannerExternalUrl' in branding['image']:
                banner_image_url = branding['image']['bannerExternalUrl']
            
            info = YouTubeChannelInfo(
                channel_id=channel_id,
                title=snippet['title'],
                description=snippet.get('description', ''),
                subscriber_count=int(statistics.get('subscriberCount', 0)),
                video_count=int(statistics.get('videoCount', 0)),
                view_count=int(statistics.get('viewCount', 0)),
                created_at=created_at,
                country=snippet.get('country'),
                custom_url=snippet.get('customUrl'),
                profile_image_url=profile_image_url,
                banner_image_url=banner_image_url
            )
            
            logger.debug(f"Retrieved channel info for {snippet['title']}")
            return info
            
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"YouTube channel not found: {channel_id}")
            elif e.resp.status == 403:
                logger.error(f"Access denied to YouTube channel {channel_id} - API quota or permissions issue")
            else:
                logger.error(f"YouTube API error getting channel info for {channel_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting channel info for {channel_id}: {e}")
            return None
    
    def get_channel_videos(self, channel_id: str) -> List[YouTubeVideo]:
        """
        Get recent videos from a YouTube channel.
        
        Args:
            channel_id: YouTube channel ID
            
        Returns:
            List of YouTubeVideo objects
        """
        if not self.youtube_available:
            logger.error(f"YouTube API not available for scraping channel: {channel_id}")
            return []
            
        try:
            logger.info(f"Fetching videos from YouTube channel: {channel_id}")
            
            cutoff_date = datetime.now(UTC) - timedelta(days=self.recent_days)
            videos = []
            
            # Get channel uploads playlist
            channel_request = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
            )
            channel_response = channel_request.execute()
            
            if not channel_response['items']:
                logger.warning(f"Channel not found: {channel_id}")
                return []
            
            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get videos from uploads playlist
            next_page_token = None
            videos_fetched = 0
            
            while videos_fetched < self.max_videos:
                playlist_request = self.youtube.playlistItems().list(
                    part='snippet',
                    playlistId=uploads_playlist_id,
                    maxResults=min(50, self.max_videos - videos_fetched),
                    pageToken=next_page_token
                )
                playlist_response = playlist_request.execute()
                
                if not playlist_response['items']:
                    break
                
                # Get video IDs for detailed info
                video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_response['items']]
                
                # Get detailed video information
                video_request = self.youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(video_ids)
                )
                video_response = video_request.execute()
                
                for video_data in video_response['items']:
                    try:
                        snippet = video_data['snippet']
                        statistics = video_data.get('statistics', {})
                        content_details = video_data.get('contentDetails', {})
                        
                        # Parse published date
                        published_at = datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00'))
                        
                        # Skip videos older than cutoff
                        if published_at < cutoff_date:
                            continue
                        
                        # Extract tags
                        tags = snippet.get('tags', [])
                        
                        # Get thumbnail URL
                        thumbnails = snippet.get('thumbnails', {})
                        thumbnail_url = thumbnails.get('high', {}).get('url', '') or thumbnails.get('default', {}).get('url', '')
                        
                        # Classify video type
                        video_type = self.classify_video_type(
                            snippet['title'],
                            snippet.get('description', ''),
                            tags
                        )
                        
                        # Create content hash
                        content = f"{snippet['title']} {snippet.get('description', '')}"
                        content_hash = hashlib.sha256(content.encode()).hexdigest()
                        
                        video = YouTubeVideo(
                            video_id=video_data['id'],
                            title=snippet['title'],
                            description=snippet.get('description', ''),
                            published_at=published_at,
                            duration=content_details.get('duration', ''),
                            view_count=int(statistics.get('viewCount', 0)),
                            like_count=int(statistics.get('likeCount', 0)),
                            comment_count=int(statistics.get('commentCount', 0)),
                            video_url=f"https://www.youtube.com/watch?v={video_data['id']}",
                            thumbnail_url=thumbnail_url,
                            tags=tags,
                            category_id=snippet.get('categoryId', ''),
                            video_type=video_type,
                            content_hash=content_hash
                        )
                        
                        videos.append(video)
                        videos_fetched += 1
                        
                        # Rate limiting
                        time.sleep(self.rate_limit_delay)
                        
                    except Exception as e:
                        logger.warning(f"Error processing video {video_data.get('id', 'unknown')}: {e}")
                        continue
                
                # Check for next page
                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token or videos_fetched >= self.max_videos:
                    break
                
                # Rate limiting between pages
                time.sleep(self.rate_limit_delay * 2)
            
            if videos:
                logger.success(f"Successfully fetched {len(videos)} videos from channel {channel_id}")
            else:
                logger.info(f"No recent videos found in channel {channel_id} (within last {self.recent_days} days)")
            
            return videos
            
        except HttpError as e:
            error_msg = str(e).lower()
            
            if e.resp.status == 403:
                if 'quota' in error_msg:
                    logger.error(f"YouTube API quota exceeded for channel {channel_id}")
                else:
                    logger.error(f"Access denied to YouTube channel {channel_id}")
            elif e.resp.status == 404:
                logger.warning(f"YouTube channel {channel_id} not found")
            else:
                logger.error(f"YouTube API error for channel {channel_id}: {e}")
                
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching videos from channel {channel_id}: {e}")
            return []
    
    def calculate_channel_metrics(self, videos: List[YouTubeVideo], channel_info: Optional[YouTubeChannelInfo]) -> Dict:
        """Calculate channel engagement and activity metrics."""
        if not videos:
            return {
                'upload_frequency_score': 0.0,
                'engagement_quality_score': 0.0,
                'content_consistency_score': 0.0,
                'subscriber_growth_indicator': 'unknown',
                'content_type_distribution': {},
                'avg_view_count': 0.0,
                'avg_engagement_rate': 0.0,
                'last_upload_date': None,
                'educational_content_ratio': 0.0,
                'technical_depth_score': 0.0
            }
        
        # Sort videos by date
        sorted_videos = sorted(videos, key=lambda x: x.published_at, reverse=True)
        
        # Upload frequency (videos per week)
        if len(sorted_videos) > 1:
            date_range = (sorted_videos[0].published_at - sorted_videos[-1].published_at).days
            upload_frequency_score = len(sorted_videos) / max(date_range / 7.0, 1) if date_range > 0 else len(sorted_videos)
        else:
            upload_frequency_score = 0.1
        
        # Engagement metrics
        total_views = sum(v.view_count for v in videos)
        avg_view_count = total_views / len(videos)
        
        engagement_rates = []
        for video in videos:
            if video.view_count > 0:
                engagement_rate = (video.like_count + video.comment_count) / video.view_count
                engagement_rates.append(engagement_rate)
        
        avg_engagement_rate = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0
        engagement_quality_score = min(avg_engagement_rate * 1000, 10)  # Normalize to 0-10
        
        # Content consistency (regularity of uploads)
        if len(sorted_videos) > 2:
            upload_intervals = []
            for i in range(len(sorted_videos) - 1):
                interval = (sorted_videos[i].published_at - sorted_videos[i + 1].published_at).days
                upload_intervals.append(interval)
            
            # Lower variance = more consistent
            avg_interval = sum(upload_intervals) / len(upload_intervals)
            variance = sum((x - avg_interval) ** 2 for x in upload_intervals) / len(upload_intervals)
            consistency_score = max(0, 10 - (variance / avg_interval if avg_interval > 0 else 10))
        else:
            consistency_score = 5.0
        
        # Content type distribution
        content_type_distribution = {}
        for video in videos:
            content_type_distribution[video.video_type] = content_type_distribution.get(video.video_type, 0) + 1
        
        # Educational content ratio
        educational_count = content_type_distribution.get('educational', 0) + content_type_distribution.get('technical', 0)
        educational_content_ratio = educational_count / len(videos)
        
        # Technical depth score (based on technical and educational content)
        technical_depth_score = min(educational_content_ratio * 10, 10)
        
        # Subscriber growth indicator (basic estimation)
        subscriber_growth_indicator = "unknown"
        if channel_info and channel_info.subscriber_count > 0:
            # Simple heuristic based on subscriber-to-video ratio and engagement
            sub_to_video_ratio = channel_info.subscriber_count / max(channel_info.video_count, 1)
            if avg_engagement_rate > 0.01 and sub_to_video_ratio > 100:
                subscriber_growth_indicator = "growing"
            elif avg_engagement_rate > 0.005:
                subscriber_growth_indicator = "stable"
            else:
                subscriber_growth_indicator = "declining"
        
        return {
            'upload_frequency_score': min(upload_frequency_score, 10),
            'engagement_quality_score': engagement_quality_score,
            'content_consistency_score': consistency_score,
            'subscriber_growth_indicator': subscriber_growth_indicator,
            'content_type_distribution': content_type_distribution,
            'avg_view_count': avg_view_count,
            'avg_engagement_rate': avg_engagement_rate,
            'last_upload_date': sorted_videos[0].published_at,
            'educational_content_ratio': educational_content_ratio,
            'technical_depth_score': technical_depth_score
        }
    
    def scrape_youtube_channel(self, youtube_url: str) -> YouTubeAnalysisResult:
        """
        Scrape and analyze a YouTube channel.
        
        Args:
            youtube_url: YouTube channel URL
            
        Returns:
            YouTubeAnalysisResult with scraped content and analysis
        """
        logger.info(f"Starting YouTube analysis for: {youtube_url}")
        
        # Check if YouTube API is available
        if not self.youtube_available:
            logger.warning(f"🚫 Cannot analyze YouTube channel - API not configured")
            return YouTubeAnalysisResult(
                channel_url=youtube_url,
                channel_id="unknown",
                channel_info=None,
                videos_analyzed=[],
                total_videos=0,
                scrape_success=False,
                error_message="YouTube API not available - configure YOUTUBE_API_KEY in config/env",
                analysis_timestamp=datetime.now(UTC)
            )
        
        try:
            # Extract channel ID
            channel_id = self.extract_channel_id_from_url(youtube_url)
            if not channel_id:
                return YouTubeAnalysisResult(
                    channel_url=youtube_url,
                    channel_id="unknown",
                    channel_info=None,
                    videos_analyzed=[],
                    total_videos=0,
                    scrape_success=False,
                    error_message="Could not extract channel ID from URL",
                    analysis_timestamp=datetime.now(UTC)
                )
            
            # Get channel information
            channel_info = self.get_channel_info(channel_id)
            
            # Get recent videos
            videos = self.get_channel_videos(channel_id)
            
            if not videos:
                error_message = f"No recent videos found in channel within the last {self.recent_days} days"
                if not channel_info:
                    error_message = "Channel appears to be inaccessible or has no content"
                
                return YouTubeAnalysisResult(
                    channel_url=youtube_url,
                    channel_id=channel_id,
                    channel_info=channel_info,
                    videos_analyzed=[],
                    total_videos=0,
                    scrape_success=False,
                    error_message=error_message,
                    analysis_timestamp=datetime.now(UTC)
                )
            
            # Calculate metrics
            metrics = self.calculate_channel_metrics(videos, channel_info)
            
            result = YouTubeAnalysisResult(
                channel_url=youtube_url,
                channel_id=channel_id,
                channel_info=channel_info,
                videos_analyzed=videos,
                total_videos=len(videos),
                scrape_success=True,
                analysis_timestamp=datetime.now(UTC),
                upload_frequency_score=metrics['upload_frequency_score'],
                engagement_quality_score=metrics['engagement_quality_score'],
                content_consistency_score=metrics['content_consistency_score'],
                subscriber_growth_indicator=metrics['subscriber_growth_indicator'],
                content_type_distribution=metrics['content_type_distribution'],
                avg_view_count=metrics['avg_view_count'],
                avg_engagement_rate=metrics['avg_engagement_rate'],
                last_upload_date=metrics['last_upload_date'],
                educational_content_ratio=metrics['educational_content_ratio'],
                technical_depth_score=metrics['technical_depth_score']
            )
            
            # Enhanced success logging
            success_msg = f"✅ YouTube analysis complete for channel {channel_id}: {len(videos)} videos analyzed"
            if channel_info and channel_info.subscriber_count > 0:
                success_msg += f" ({channel_info.subscriber_count:,} subscribers)"
            
            # Add content type summary
            if metrics['content_type_distribution']:
                top_types = sorted(metrics['content_type_distribution'].items(), key=lambda x: x[1], reverse=True)[:2]
                type_summary = ", ".join([f"{count} {type_}" for type_, count in top_types])
                success_msg += f" - Content: {type_summary}"
            
            logger.success(success_msg)
            return result
            
        except Exception as e:
            logger.error(f"YouTube analysis failed for {youtube_url}: {e}")
            return YouTubeAnalysisResult(
                channel_url=youtube_url,
                channel_id=channel_id if 'channel_id' in locals() else "unknown",
                channel_info=None,
                videos_analyzed=[],
                total_videos=0,
                scrape_success=False,
                error_message=str(e),
                analysis_timestamp=datetime.now(UTC)
            )


# Test functionality
if __name__ == "__main__":
    scraper = YouTubeScraper(recent_days=30, max_videos=20)
    
    # Test with some known crypto project YouTube channels
    test_urls = [
        "https://www.youtube.com/@ethereum",
        "https://www.youtube.com/@Cardano",
        "https://www.youtube.com/@avalancheavax"
    ]
    
    for url in test_urls:
        print(f"\n=== Testing {url} ===")
        result = scraper.scrape_youtube_channel(url)
        print(f"Success: {result.scrape_success}")
        if result.scrape_success:
            print(f"Videos analyzed: {result.total_videos}")
            print(f"Upload frequency: {result.upload_frequency_score:.2f}/10")
            print(f"Engagement quality: {result.engagement_quality_score:.2f}/10")
            print(f"Content consistency: {result.content_consistency_score:.2f}/10")
            print(f"Content types: {result.content_type_distribution}")
            print(f"Educational ratio: {result.educational_content_ratio:.2%}")
            if result.channel_info:
                print(f"Subscribers: {result.channel_info.subscriber_count:,}")
        else:
            print(f"Error: {result.error_message}")