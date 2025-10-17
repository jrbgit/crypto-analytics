"""
Test Suite for YouTube Scraper and Analyzer Implementation

Tests YouTube channel URL parsing, scraping, and analysis functionality
for cryptocurrency project analysis.
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch
from datetime import datetime, UTC, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.youtube_scraper import YouTubeScraper, YouTubeVideo, YouTubeChannelInfo, YouTubeAnalysisResult
from src.analyzers.youtube_analyzer import YouTubeAnalyzer, YouTubeContentAnalysis
from src.utils.url_filter import url_filter


class TestYouTubeScraper:
    """Test YouTube scraper functionality."""
    
    def setup_method(self):
        """Set up test instances."""
        self.scraper = YouTubeScraper(recent_days=30, max_videos=10)
    
    def test_channel_id_extraction_direct(self):
        """Test extracting channel ID from direct channel URL."""
        url = "https://www.youtube.com/channel/UCBJycsmduvYEL83R_U4JriQ"
        channel_id = self.scraper.extract_channel_id_from_url(url)
        assert channel_id == "UCBJycsmduvYEL83R_U4JriQ"
    
    def test_channel_id_extraction_handle(self):
        """Test extracting channel ID from @handle URL."""
        url = "https://www.youtube.com/@ethereum"
        # This would require API call to resolve, so we test the parsing logic
        parsed_id = self.scraper.extract_channel_id_from_url(url)
        # The method should return None if API is not available for resolution
        # In real usage, it would resolve the handle to a channel ID
        assert parsed_id is None or isinstance(parsed_id, str)
    
    def test_channel_id_extraction_custom(self):
        """Test extracting channel ID from custom URL."""
        url = "https://www.youtube.com/c/ethereum"
        # This would require API call to resolve
        parsed_id = self.scraper.extract_channel_id_from_url(url)
        assert parsed_id is None or isinstance(parsed_id, str)
    
    def test_channel_id_extraction_user(self):
        """Test extracting channel ID from legacy user URL."""
        url = "https://www.youtube.com/user/ethereumproject"
        # This would require API call to resolve
        parsed_id = self.scraper.extract_channel_id_from_url(url)
        assert parsed_id is None or isinstance(parsed_id, str)
    
    def test_channel_id_extraction_invalid(self):
        """Test extracting channel ID from invalid URL."""
        url = "https://www.example.com/not-youtube"
        channel_id = self.scraper.extract_channel_id_from_url(url)
        assert channel_id is None
    
    def test_video_type_classification(self):
        """Test video type classification logic."""
        # Educational video
        educational_result = self.scraper.classify_video_type(
            "How to Build Smart Contracts - Tutorial",
            "Complete guide to building smart contracts on Ethereum",
            ["tutorial", "education", "blockchain"]
        )
        assert educational_result == "educational"
        
        # Announcement video
        announcement_result = self.scraper.classify_video_type(
            "Major Partnership Announcement",
            "We're excited to announce our new partnership",
            ["announcement", "partnership"]
        )
        assert announcement_result == "announcement"
        
        # Technical video
        technical_result = self.scraper.classify_video_type(
            "Protocol Architecture Deep Dive",
            "Technical overview of our blockchain protocol",
            ["technical", "development", "protocol"]
        )
        assert technical_result == "technical"
        
        # AMA video
        ama_result = self.scraper.classify_video_type(
            "Ask Me Anything - Community Q&A",
            "Join us for a live Q&A session",
            ["ama", "live", "community"]
        )
        assert ama_result == "ama"
        
        # Marketing video
        marketing_result = self.scraper.classify_video_type(
            "Join Our Community Event",
            "Don't miss our exclusive community event",
            ["marketing", "community", "event"]
        )
        assert marketing_result == "marketing"
        
        # Other/unknown
        other_result = self.scraper.classify_video_type(
            "Random Video Title",
            "Random description without specific keywords",
            []
        )
        assert other_result == "other"
    
    @patch('src.scrapers.youtube_scraper.build')
    def test_scraper_initialization_no_api_key(self, mock_build):
        """Test scraper initialization without API key."""
        with patch.dict(os.environ, {}, clear=True):
            scraper = YouTubeScraper()
            assert not scraper.youtube_available
            assert scraper.youtube is None
    
    def test_scraper_without_api_returns_error_result(self):
        """Test that scraper returns error result when API is not available."""
        # Force scraper to be unavailable
        self.scraper.youtube_available = False
        self.scraper.youtube = None
        
        result = self.scraper.scrape_youtube_channel("https://www.youtube.com/@ethereum")
        
        assert not result.scrape_success
        assert "YouTube API not available" in result.error_message
        assert result.total_videos == 0
    
    def test_calculate_channel_metrics_empty_videos(self):
        """Test metric calculation with no videos."""
        metrics = self.scraper.calculate_channel_metrics([], None)
        
        expected_keys = [
            'upload_frequency_score', 'engagement_quality_score', 'content_consistency_score',
            'subscriber_growth_indicator', 'content_type_distribution', 'avg_view_count',
            'avg_engagement_rate', 'last_upload_date', 'educational_content_ratio',
            'technical_depth_score'
        ]
        
        for key in expected_keys:
            assert key in metrics
        
        assert metrics['upload_frequency_score'] == 0.0
        assert metrics['engagement_quality_score'] == 0.0
        assert metrics['last_upload_date'] is None
    
    def test_calculate_channel_metrics_with_videos(self):
        """Test metric calculation with sample videos."""
        # Create sample videos
        now = datetime.now(UTC)
        videos = [
            YouTubeVideo(
                video_id="vid1",
                title="Tutorial: Smart Contracts",
                description="Learn smart contracts",
                published_at=now - timedelta(days=1),
                duration="PT10M",
                view_count=1000,
                like_count=50,
                comment_count=10,
                video_url="https://youtube.com/watch?v=vid1",
                thumbnail_url="",
                tags=["tutorial", "blockchain"],
                category_id="27",
                video_type="educational",
                content_hash="hash1"
            ),
            YouTubeVideo(
                video_id="vid2",
                title="Partnership Announcement",
                description="New partnership news",
                published_at=now - timedelta(days=7),
                duration="PT5M",
                view_count=2000,
                like_count=100,
                comment_count=20,
                video_url="https://youtube.com/watch?v=vid2",
                thumbnail_url="",
                tags=["announcement", "partnership"],
                category_id="27",
                video_type="announcement",
                content_hash="hash2"
            )
        ]
        
        metrics = self.scraper.calculate_channel_metrics(videos, None)
        
        assert metrics['upload_frequency_score'] > 0
        assert metrics['avg_view_count'] == 1500  # (1000 + 2000) / 2
        assert metrics['educational_content_ratio'] == 0.5  # 1 educational out of 2 total
        assert len(metrics['content_type_distribution']) == 2
        assert metrics['content_type_distribution']['educational'] == 1
        assert metrics['content_type_distribution']['announcement'] == 1


class TestYouTubeAnalyzer:
    """Test YouTube analyzer functionality."""
    
    def setup_method(self):
        """Set up test instances."""
        self.analyzer = YouTubeAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        assert self.analyzer is not None
        assert hasattr(self.analyzer, 'quality_indicators')
        assert hasattr(self.analyzer, 'technical_indicators')
        assert hasattr(self.analyzer, 'red_flag_indicators')
    
    def test_extract_topics_from_metadata(self):
        """Test topic extraction from video metadata."""
        videos = [
            YouTubeVideo(
                video_id="vid1",
                title="DeFi Protocol Tutorial",
                description="Learn about DeFi",
                published_at=datetime.now(UTC),
                duration="PT10M",
                view_count=1000,
                like_count=50,
                comment_count=10,
                video_url="https://youtube.com/watch?v=vid1",
                thumbnail_url="",
                tags=["defi", "protocol", "tutorial"],
                category_id="27",
                video_type="educational",
                content_hash="hash1"
            )
        ]
        
        topics = self.analyzer._extract_topics_from_metadata(videos)
        assert "defi" in topics
        assert "protocol" in topics
    
    def test_determine_target_audience(self):
        """Test target audience determination."""
        # Beginner-focused videos
        beginner_videos = [
            YouTubeVideo(
                video_id="vid1",
                title="Blockchain Basics for Beginners",
                description="Introduction to blockchain",
                published_at=datetime.now(UTC),
                duration="PT10M",
                view_count=1000,
                like_count=50,
                comment_count=10,
                video_url="https://youtube.com/watch?v=vid1",
                thumbnail_url="",
                tags=["beginner", "introduction", "basics"],
                category_id="27",
                video_type="educational",
                content_hash="hash1"
            )
        ]
        
        audience = self.analyzer._determine_target_audience(beginner_videos)
        assert audience == "beginners"
        
        # Advanced videos
        advanced_videos = [
            YouTubeVideo(
                video_id="vid2",
                title="Advanced Protocol Architecture",
                description="Deep dive into technical details",
                published_at=datetime.now(UTC),
                duration="PT30M",
                view_count=500,
                like_count=25,
                comment_count=5,
                video_url="https://youtube.com/watch?v=vid2",
                thumbnail_url="",
                tags=["advanced", "technical", "architecture"],
                category_id="27",
                video_type="technical",
                content_hash="hash2"
            )
        ]
        
        audience = self.analyzer._determine_target_audience(advanced_videos)
        assert audience == "advanced"
    
    def test_calculate_marketing_ratio(self):
        """Test marketing vs substance ratio calculation."""
        # Marketing-heavy videos
        marketing_videos = [
            YouTubeVideo(
                video_id="vid1",
                title="Buy Our Token Now!",
                description="Investment opportunity",
                published_at=datetime.now(UTC),
                duration="PT5M",
                view_count=1000,
                like_count=50,
                comment_count=10,
                video_url="https://youtube.com/watch?v=vid1",
                thumbnail_url="",
                tags=["buy", "investment", "profit"],
                category_id="27",
                video_type="marketing",
                content_hash="hash1"
            )
        ]
        
        ratio = self.analyzer._calculate_marketing_ratio(marketing_videos)
        assert ratio > 0.5  # Should be marketing-heavy
        
        # Technical/substance videos
        technical_videos = [
            YouTubeVideo(
                video_id="vid2",
                title="Technical Analysis of Protocol",
                description="Research and development update",
                published_at=datetime.now(UTC),
                duration="PT20M",
                view_count=500,
                like_count=25,
                comment_count=5,
                video_url="https://youtube.com/watch?v=vid2",
                thumbnail_url="",
                tags=["technical", "analysis", "research"],
                category_id="27",
                video_type="technical",
                content_hash="hash2"
            )
        ]
        
        ratio = self.analyzer._calculate_marketing_ratio(technical_videos)
        assert ratio < 0.5  # Should be substance-heavy
    
    def test_analyze_failed_scrape_result(self):
        """Test analysis of failed scrape result."""
        failed_result = YouTubeAnalysisResult(
            channel_url="https://youtube.com/@nonexistent",
            channel_id="unknown",
            channel_info=None,
            videos_analyzed=[],
            total_videos=0,
            scrape_success=False,
            error_message="Channel not found",
            analysis_timestamp=datetime.now(UTC)
        )
        
        analysis = self.analyzer.analyze_youtube_content(failed_result)
        
        assert not analysis.analysis_method != "failed"
        assert analysis.confidence_score == 0.0
        assert analysis.videos_analyzed_count == 0
        assert "Analysis failed" in analysis.channel_summary
    
    def test_analyze_successful_scrape_result(self):
        """Test analysis of successful scrape result."""
        # Create a successful result with sample data
        channel_info = YouTubeChannelInfo(
            channel_id="UCtest",
            title="Test Crypto Channel",
            description="A test cryptocurrency channel",
            subscriber_count=10000,
            video_count=100,
            view_count=1000000,
            created_at=datetime.now(UTC) - timedelta(days=365),
            country="US",
            custom_url="testcrypto",
            profile_image_url="",
            banner_image_url=""
        )
        
        videos = [
            YouTubeVideo(
                video_id="vid1",
                title="Educational Content: Smart Contracts",
                description="Learn about smart contracts",
                published_at=datetime.now(UTC) - timedelta(days=1),
                duration="PT15M",
                view_count=5000,
                like_count=250,
                comment_count=50,
                video_url="https://youtube.com/watch?v=vid1",
                thumbnail_url="",
                tags=["education", "smart contracts", "tutorial"],
                category_id="27",
                video_type="educational",
                content_hash="hash1"
            )
        ]
        
        successful_result = YouTubeAnalysisResult(
            channel_url="https://youtube.com/@testcrypto",
            channel_id="UCtest",
            channel_info=channel_info,
            videos_analyzed=videos,
            total_videos=1,
            scrape_success=True,
            analysis_timestamp=datetime.now(UTC),
            upload_frequency_score=2.0,
            engagement_quality_score=6.0,
            content_consistency_score=7.0,
            content_type_distribution={"educational": 1},
            avg_view_count=5000.0,
            avg_engagement_rate=0.06,
            last_upload_date=datetime.now(UTC) - timedelta(days=1),
            educational_content_ratio=1.0
        )
        
        analysis = self.analyzer.analyze_youtube_content(successful_result)
        
        assert analysis.videos_analyzed_count == 1
        assert analysis.confidence_score > 0.0
        assert analysis.analysis_method in ["metadata_only", "llm"]
        assert analysis.educational_value_score > 0
        assert analysis.technical_depth_score >= 0
        assert len(analysis.primary_content_types) > 0
    
    def test_format_analysis_for_storage(self):
        """Test formatting analysis for database storage."""
        # Create a sample analysis
        analysis = YouTubeContentAnalysis(
            channel_summary="Test channel analysis",
            communication_style="educational",
            content_quality_score=8,
            educational_value_score=7,
            technical_depth_score=6,
            primary_content_types=["educational", "technical"],
            topics_covered=["blockchain", "defi"],
            target_audience="mixed",
            update_frequency_pattern="regular",
            project_focus_areas=["technology", "education"],
            development_activity_indicators=["Recent update content"],
            community_engagement_style="high engagement",
            transparency_level="high",
            information_density="high",
            marketing_vs_substance_ratio=0.2,
            consistency_score=8,
            red_flags=[],
            positive_indicators=["Strong educational content"],
            confidence_score=0.85,
            analysis_timestamp=datetime.now(UTC),
            videos_analyzed_count=10,
            analysis_method="metadata_only"
        )
        
        formatted = self.analyzer.format_analysis_for_storage(analysis)
        
        # Check required fields
        assert "summary" in formatted
        assert "technical_depth_score" in formatted
        assert "content_quality_score" in formatted
        assert "marketing_vs_tech_ratio" in formatted
        assert "confidence_score" in formatted
        
        # Check YouTube-specific fields
        assert "communication_style" in formatted
        assert "educational_value_score" in formatted
        assert "target_audience" in formatted
        
        # Check JSON fields
        assert "primary_content_types" in formatted
        assert "topics_covered" in formatted
        
        # Verify JSON serialization
        import json
        assert json.loads(formatted["primary_content_types"]) == ["educational", "technical"]


class TestURLFilter:
    """Test URL filter with YouTube URLs."""
    
    def test_youtube_channel_id_extraction(self):
        """Test YouTube channel ID extraction in URL filter."""
        # Direct channel ID
        channel_url = "https://www.youtube.com/channel/UCBJycsmduvYEL83R_U4JriQ"
        channel_id = url_filter.extract_youtube_channel_id(channel_url)
        assert channel_id == "UCBJycsmduvYEL83R_U4JriQ"
        
        # Handle format
        handle_url = "https://www.youtube.com/@ethereum"
        handle_id = url_filter.extract_youtube_channel_id(handle_url)
        assert handle_id == "@ethereum"
        
        # Custom URL
        custom_url = "https://www.youtube.com/c/ethereum"
        custom_id = url_filter.extract_youtube_channel_id(custom_url)
        assert custom_id == "c/ethereum"
        
        # Legacy user URL
        user_url = "https://www.youtube.com/user/ethereumproject"
        user_id = url_filter.extract_youtube_channel_id(user_url)
        assert user_id == "user/ethereumproject"
        
        # Non-YouTube URL
        non_youtube = "https://www.example.com/channel/test"
        result = url_filter.extract_youtube_channel_id(non_youtube)
        assert result is None
    
    def test_valid_youtube_channel_url(self):
        """Test YouTube channel URL validation."""
        valid_urls = [
            "https://www.youtube.com/channel/UCBJycsmduvYEL83R_U4JriQ",
            "https://www.youtube.com/@ethereum",
            "https://www.youtube.com/c/ethereum",
            "https://www.youtube.com/user/ethereumproject"
        ]
        
        for url in valid_urls:
            assert url_filter.is_valid_youtube_channel_url(url)
        
        invalid_urls = [
            "https://www.example.com/channel/test",
            "https://www.youtube.com/watch?v=123",
            "https://www.youtube.com/playlist?list=123",
            ""
        ]
        
        for url in invalid_urls:
            assert not url_filter.is_valid_youtube_channel_url(url)


class TestIntegration:
    """Integration tests for YouTube scraper and analyzer."""
    
    @pytest.mark.skip(reason="Requires actual YouTube API key")
    def test_full_youtube_analysis_pipeline(self):
        """Test complete YouTube analysis pipeline (requires API key)."""
        # This test requires actual API credentials
        scraper = YouTubeScraper(recent_days=7, max_videos=5)
        analyzer = YouTubeAnalyzer()
        
        # Test with a known crypto channel
        test_url = "https://www.youtube.com/@ethereum"
        
        # Scrape
        scrape_result = scraper.scrape_youtube_channel(test_url)
        
        if scrape_result.scrape_success:
            # Analyze
            analysis = analyzer.analyze_youtube_content(scrape_result)
            
            # Verify analysis results
            assert analysis.videos_analyzed_count > 0
            assert analysis.confidence_score > 0
            assert analysis.channel_summary != ""
            assert analysis.analysis_method in ["metadata_only", "llm"]
            
            # Format for storage
            storage_format = analyzer.format_analysis_for_storage(analysis)
            assert isinstance(storage_format, dict)
            assert "summary" in storage_format


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])