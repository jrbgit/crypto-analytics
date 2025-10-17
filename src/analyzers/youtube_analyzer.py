"""
YouTube Analyzer Module for Cryptocurrency Project Analysis

This module handles:
- Processing scraped YouTube channel data and video content
- LLM analysis of video descriptions and titles for project insights
- Evaluating content quality, technical depth, and communication patterns
- Assessing community engagement and educational value
- Generating structured analysis results for storage and reporting
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
import re

# Import scraped data types
from scrapers.youtube_scraper import YouTubeVideo, YouTubeChannelInfo, YouTubeAnalysisResult

# Import LLM utilities
try:
    from pipelines.llm_analysis_pipeline import LLMAnalysisPipeline, AnalysisConfig
    LLM_AVAILABLE = True
except ImportError:
    logger.warning("LLM analysis pipeline not available - YouTube analysis will be limited to metadata only")
    LLM_AVAILABLE = False


@dataclass
class YouTubeContentAnalysis:
    """Analysis results for YouTube channel content."""
    
    # Channel overview
    channel_summary: str
    communication_style: str  # 'educational', 'promotional', 'mixed', 'technical'
    content_quality_score: int  # 1-10
    educational_value_score: int  # 1-10
    technical_depth_score: int  # 1-10
    
    # Content patterns
    primary_content_types: List[str]
    topics_covered: List[str]
    target_audience: str  # 'beginners', 'advanced', 'mixed', 'developers'
    update_frequency_pattern: str  # 'regular', 'sporadic', 'burst', 'inactive'
    
    # Project insights
    project_focus_areas: List[str]
    development_activity_indicators: List[str]
    community_engagement_style: str
    transparency_level: str  # 'high', 'medium', 'low'
    
    # Content quality analysis
    information_density: str  # 'high', 'medium', 'low'
    marketing_vs_substance_ratio: float  # 0.0 = all substance, 1.0 = all marketing
    consistency_score: int  # 1-10 for content consistency
    
    # Red flags and positive indicators
    red_flags: List[str]
    positive_indicators: List[str]
    
    # Confidence and metadata
    confidence_score: float  # 0.0-1.0
    analysis_timestamp: datetime
    videos_analyzed_count: int
    analysis_method: str  # 'llm', 'metadata_only', 'hybrid'


class YouTubeAnalyzer:
    """Analyzes scraped YouTube content for cryptocurrency projects."""
    
    def __init__(self):
        """Initialize the YouTube analyzer."""
        self.llm_available = LLM_AVAILABLE
        
        if self.llm_available:
            try:
                # Initialize LLM pipeline for content analysis
                self.llm_pipeline = LLMAnalysisPipeline()
                logger.info("🤖 LLM pipeline initialized for YouTube content analysis")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM pipeline: {e}")
                self.llm_available = False
        
        # Content quality indicators
        self.quality_indicators = {
            'high_quality': [
                'technical explanation', 'detailed analysis', 'educational content',
                'step by step', 'in-depth', 'comprehensive', 'tutorial',
                'technical documentation', 'code walkthrough', 'architecture'
            ],
            'medium_quality': [
                'overview', 'introduction', 'summary', 'update', 'news',
                'announcement', 'discussion', 'interview', 'ama'
            ],
            'low_quality': [
                'hype', 'moon', 'pump', 'quick profit', 'get rich', 'guaranteed',
                'clickbait', 'shocking', 'you won\'t believe', 'must watch'
            ]
        }
        
        # Technical depth indicators
        self.technical_indicators = [
            'blockchain', 'consensus', 'protocol', 'smart contract', 'dapp',
            'defi', 'cryptography', 'hash', 'merkle', 'validator', 'node',
            'api', 'sdk', 'whitepaper', 'tokenomics', 'governance', 'dao',
            'staking', 'yield', 'liquidity', 'oracle', 'bridge', 'layer 2'
        ]
        
        # Red flag indicators
        self.red_flag_indicators = [
            'guaranteed returns', 'risk-free', 'easy money', 'get rich quick',
            'limited time', 'exclusive offer', 'secret strategy', 'insider info',
            'pump and dump', 'shill', 'not financial advice but', 'to the moon'
        ]
    
    def _extract_video_content_summary(self, videos: List[YouTubeVideo]) -> str:
        """Extract a summary of video content for LLM analysis."""
        if not videos:
            return ""
        
        # Sort by recent and most viewed
        sorted_videos = sorted(videos, key=lambda v: (v.published_at, v.view_count), reverse=True)
        
        content_parts = []
        for i, video in enumerate(sorted_videos[:10]):  # Analyze top 10 videos
            # Create a content summary for each video
            video_summary = f"Video {i+1}:\n"
            video_summary += f"Title: {video.title}\n"
            video_summary += f"Views: {video.view_count:,}, Likes: {video.like_count:,}, Comments: {video.comment_count:,}\n"
            video_summary += f"Type: {video.video_type}\n"
            video_summary += f"Published: {video.published_at.strftime('%Y-%m-%d')}\n"
            
            if video.description:
                # Truncate description to first 300 characters for analysis
                desc = video.description[:300].replace('\n', ' ')
                video_summary += f"Description: {desc}...\n"
            
            if video.tags:
                video_summary += f"Tags: {', '.join(video.tags[:10])}\n"  # First 10 tags
            
            content_parts.append(video_summary)
        
        return "\n---\n".join(content_parts)
    
    def _analyze_metadata_patterns(self, result: YouTubeAnalysisResult) -> Dict[str, Any]:
        """Analyze patterns from metadata without LLM."""
        if not result.videos_analyzed:
            return self._get_empty_metadata_analysis()
        
        videos = result.videos_analyzed
        channel_info = result.channel_info
        
        # Analyze content types
        content_type_counts = result.content_type_distribution or {}
        primary_types = sorted(content_type_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        primary_content_types = [t[0] for t in primary_types]
        
        # Analyze upload patterns
        if len(videos) > 1:
            sorted_videos = sorted(videos, key=lambda v: v.published_at, reverse=True)
            recent_uploads = len([v for v in sorted_videos[:5]])  # Recent 5 videos
            if recent_uploads >= 4:
                update_pattern = "regular"
            elif recent_uploads >= 2:
                update_pattern = "moderate"
            else:
                update_pattern = "sporadic"
        else:
            update_pattern = "insufficient_data"
        
        # Analyze engagement patterns
        avg_engagement = result.avg_engagement_rate or 0.0
        if avg_engagement > 0.02:
            engagement_level = "high"
        elif avg_engagement > 0.01:
            engagement_level = "medium"
        else:
            engagement_level = "low"
        
        # Content quality heuristics
        educational_ratio = result.educational_content_ratio or 0.0
        technical_score = min(int(educational_ratio * 10), 10)
        
        # Analyze titles for quality indicators
        all_titles = " ".join([v.title.lower() for v in videos])
        quality_score = 5  # Start with neutral
        
        # Check for quality indicators
        for indicator in self.quality_indicators['high_quality']:
            if indicator in all_titles:
                quality_score += 1
        
        for indicator in self.quality_indicators['low_quality']:
            if indicator in all_titles:
                quality_score -= 1
        
        quality_score = max(1, min(10, quality_score))
        
        # Technical depth from titles and tags
        all_text = all_titles + " " + " ".join([" ".join(v.tags) for v in videos]).lower()
        technical_mentions = sum(1 for indicator in self.technical_indicators if indicator in all_text)
        tech_depth = min(int(technical_mentions / 2), 10)
        
        # Red flags detection
        red_flags = []
        for flag in self.red_flag_indicators:
            if flag in all_text:
                red_flags.append(f"Suspicious content: {flag}")
        
        # Positive indicators
        positive_indicators = []
        if educational_ratio > 0.3:
            positive_indicators.append("High educational content ratio")
        if result.upload_frequency_score and result.upload_frequency_score > 1.0:
            positive_indicators.append("Consistent upload schedule")
        if avg_engagement > 0.015:
            positive_indicators.append("Strong community engagement")
        if channel_info and channel_info.subscriber_count > 10000:
            positive_indicators.append(f"Significant following ({channel_info.subscriber_count:,} subscribers)")
        
        return {
            'channel_summary': f"YouTube channel with {len(videos)} recent videos, primary focus on {', '.join(primary_content_types[:2])}",
            'communication_style': primary_content_types[0] if primary_content_types else 'unknown',
            'content_quality_score': quality_score,
            'educational_value_score': int(educational_ratio * 10),
            'technical_depth_score': tech_depth,
            'primary_content_types': primary_content_types,
            'topics_covered': self._extract_topics_from_metadata(videos),
            'target_audience': self._determine_target_audience(videos),
            'update_frequency_pattern': update_pattern,
            'project_focus_areas': self._extract_focus_areas_from_metadata(videos),
            'development_activity_indicators': self._get_dev_indicators_from_metadata(videos),
            'community_engagement_style': engagement_level,
            'transparency_level': self._assess_transparency_from_metadata(videos),
            'information_density': 'medium',  # Default for metadata analysis
            'marketing_vs_substance_ratio': self._calculate_marketing_ratio(videos),
            'consistency_score': int(result.content_consistency_score or 5),
            'red_flags': red_flags,
            'positive_indicators': positive_indicators,
            'confidence_score': 0.6,  # Lower confidence for metadata-only analysis
            'analysis_method': 'metadata_only'
        }
    
    def _get_empty_metadata_analysis(self) -> Dict[str, Any]:
        """Return empty analysis structure."""
        return {
            'channel_summary': "No recent content available for analysis",
            'communication_style': 'unknown',
            'content_quality_score': 5,
            'educational_value_score': 5,
            'technical_depth_score': 5,
            'primary_content_types': [],
            'topics_covered': [],
            'target_audience': 'unknown',
            'update_frequency_pattern': 'inactive',
            'project_focus_areas': [],
            'development_activity_indicators': [],
            'community_engagement_style': 'unknown',
            'transparency_level': 'unknown',
            'information_density': 'unknown',
            'marketing_vs_substance_ratio': 0.5,
            'consistency_score': 5,
            'red_flags': ['No recent content available'],
            'positive_indicators': [],
            'confidence_score': 0.1,
            'analysis_method': 'no_content'
        }
    
    def _extract_topics_from_metadata(self, videos: List[YouTubeVideo]) -> List[str]:
        """Extract topics from video titles and tags."""
        topics = set()
        
        for video in videos:
            # Extract from title
            title_words = re.findall(r'\b\w+\b', video.title.lower())
            
            # Common crypto topics
            crypto_topics = [
                'defi', 'nft', 'dao', 'staking', 'yield', 'governance', 'tokenomics',
                'blockchain', 'smart contract', 'protocol', 'dapp', 'wallet',
                'trading', 'mining', 'consensus', 'layer 2', 'bridge', 'oracle'
            ]
            
            for topic in crypto_topics:
                if topic in video.title.lower() or topic in " ".join(video.tags).lower():
                    topics.add(topic)
        
        return list(topics)[:10]  # Return top 10 topics
    
    def _determine_target_audience(self, videos: List[YouTubeVideo]) -> str:
        """Determine target audience from content."""
        beginner_indicators = ['beginner', 'introduction', 'basics', 'getting started', 'how to']
        advanced_indicators = ['advanced', 'deep dive', 'technical', 'developer', 'architecture']
        
        all_content = " ".join([v.title.lower() + " " + " ".join(v.tags).lower() for v in videos])
        
        beginner_score = sum(1 for indicator in beginner_indicators if indicator in all_content)
        advanced_score = sum(1 for indicator in advanced_indicators if indicator in all_content)
        
        if beginner_score > advanced_score * 2:
            return 'beginners'
        elif advanced_score > beginner_score * 2:
            return 'advanced'
        elif beginner_score > 0 or advanced_score > 0:
            return 'mixed'
        else:
            return 'general'
    
    def _extract_focus_areas_from_metadata(self, videos: List[YouTubeVideo]) -> List[str]:
        """Extract project focus areas from video content."""
        focus_areas = set()
        
        focus_keywords = {
            'technology': ['blockchain', 'protocol', 'consensus', 'architecture', 'technical'],
            'defi': ['defi', 'yield', 'liquidity', 'farming', 'staking', 'lending'],
            'nft': ['nft', 'collectibles', 'marketplace', 'art', 'gaming'],
            'governance': ['governance', 'dao', 'voting', 'proposals', 'community'],
            'development': ['development', 'coding', 'sdk', 'api', 'developer'],
            'education': ['tutorial', 'guide', 'education', 'learn', 'explained'],
            'partnerships': ['partnership', 'collaboration', 'integration', 'alliance'],
            'community': ['community', 'event', 'meetup', 'ama', 'discussion']
        }
        
        all_content = " ".join([v.title.lower() + " " + v.description[:200].lower() + " " + " ".join(v.tags).lower() for v in videos])
        
        for area, keywords in focus_keywords.items():
            if any(keyword in all_content for keyword in keywords):
                focus_areas.add(area)
        
        return list(focus_areas)
    
    def _get_dev_indicators_from_metadata(self, videos: List[YouTubeVideo]) -> List[str]:
        """Get development activity indicators from video metadata."""
        indicators = []
        
        dev_keywords = [
            'update', 'release', 'launch', 'development', 'progress',
            'milestone', 'roadmap', 'feature', 'upgrade', 'testnet', 'mainnet'
        ]
        
        recent_videos = sorted(videos, key=lambda v: v.published_at, reverse=True)[:5]
        
        for keyword in dev_keywords:
            matching_videos = [v for v in recent_videos if keyword in v.title.lower()]
            if matching_videos:
                indicators.append(f"Recent {keyword} content ({len(matching_videos)} videos)")
        
        return indicators[:5]  # Return top 5 indicators
    
    def _assess_transparency_from_metadata(self, videos: List[YouTubeVideo]) -> str:
        """Assess transparency level from video content."""
        transparency_keywords = [
            'roadmap', 'progress', 'update', 'milestone', 'development',
            'team', 'behind the scenes', 'transparency', 'open source'
        ]
        
        all_content = " ".join([v.title.lower() + " " + v.description[:200].lower() for v in videos])
        transparency_mentions = sum(1 for keyword in transparency_keywords if keyword in all_content)
        
        if transparency_mentions >= 5:
            return 'high'
        elif transparency_mentions >= 2:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_marketing_ratio(self, videos: List[YouTubeVideo]) -> float:
        """Calculate marketing vs substance ratio."""
        marketing_indicators = [
            'buy', 'price', 'pump', 'moon', 'profit', 'investment',
            'hype', 'exclusive', 'limited', 'opportunity'
        ]
        
        substance_indicators = [
            'technical', 'analysis', 'education', 'tutorial', 'guide',
            'development', 'protocol', 'architecture', 'research'
        ]
        
        all_content = " ".join([v.title.lower() + " " + " ".join(v.tags).lower() for v in videos])
        
        marketing_score = sum(1 for indicator in marketing_indicators if indicator in all_content)
        substance_score = sum(1 for indicator in substance_indicators if indicator in all_content)
        
        total_score = marketing_score + substance_score
        if total_score == 0:
            return 0.5  # Neutral if no clear indicators
        
        return marketing_score / total_score
    
    def _analyze_with_llm(self, result: YouTubeAnalysisResult) -> Dict[str, Any]:
        """Analyze YouTube content using LLM."""
        if not self.llm_available or not result.videos_analyzed:
            return self._analyze_metadata_patterns(result)
        
        try:
            # Extract content for LLM analysis
            content_summary = self._extract_video_content_summary(result.videos_analyzed)
            
            if not content_summary:
                return self._analyze_metadata_patterns(result)
            
            # Prepare analysis prompt
            channel_info_text = ""
            if result.channel_info:
                channel_info_text = f"""
Channel: {result.channel_info.title}
Subscribers: {result.channel_info.subscriber_count:,}
Total Videos: {result.channel_info.video_count}
Channel Description: {result.channel_info.description[:200]}...
"""
            
            analysis_prompt = f"""
Analyze this cryptocurrency project's YouTube channel content and provide insights:

{channel_info_text}

Recent Video Content:
{content_summary}

Channel Metrics:
- Upload Frequency Score: {result.upload_frequency_score:.2f}/10
- Engagement Quality Score: {result.engagement_quality_score:.2f}/10
- Educational Content Ratio: {result.educational_content_ratio:.2%}
- Content Types: {result.content_type_distribution}

Please analyze and provide:

1. Channel Summary (2-3 sentences about the channel's purpose and approach)
2. Communication Style (educational/promotional/technical/mixed)
3. Content Quality Score (1-10)
4. Educational Value Score (1-10)
5. Technical Depth Score (1-10)
6. Primary Content Types (list top 3)
7. Topics Covered (list main topics)
8. Target Audience (beginners/advanced/developers/mixed)
9. Update Frequency Pattern (regular/sporadic/burst/inactive)
10. Project Focus Areas (list main focus areas)
11. Development Activity Indicators (evidence of active development)
12. Community Engagement Style (description)
13. Transparency Level (high/medium/low)
14. Information Density (high/medium/low)
15. Marketing vs Substance Ratio (0.0-1.0, where 1.0 is pure marketing)
16. Consistency Score (1-10)
17. Red Flags (any concerning patterns)
18. Positive Indicators (strengths and good practices)

Focus on cryptocurrency and blockchain project analysis. Be objective and evidence-based.
"""
            
            # Configure LLM analysis
            config = AnalysisConfig(
                analysis_type="youtube_content",
                max_tokens=1000,
                temperature=0.3,
                focus_areas=["content_quality", "technical_depth", "community_engagement"]
            )
            
            # Run LLM analysis
            llm_result = self.llm_pipeline.analyze_content(analysis_prompt, config)
            
            if llm_result and llm_result.get('analysis_successful'):
                # Parse LLM response and structure the data
                parsed_analysis = self._parse_llm_response(llm_result['content'], result)
                parsed_analysis['analysis_method'] = 'llm'
                parsed_analysis['confidence_score'] = 0.85  # Higher confidence for LLM analysis
                return parsed_analysis
            else:
                logger.warning("LLM analysis failed, falling back to metadata analysis")
                return self._analyze_metadata_patterns(result)
                
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}")
            return self._analyze_metadata_patterns(result)
    
    def _parse_llm_response(self, llm_response: str, result: YouTubeAnalysisResult) -> Dict[str, Any]:
        """Parse LLM response into structured data."""
        try:
            # Try to extract structured information from LLM response
            # This is a simplified parser - in practice, you might want more sophisticated parsing
            
            response_lower = llm_response.lower()
            
            # Extract scores (look for patterns like "score: 8" or "8/10")
            def extract_score(pattern: str, default: int = 5) -> int:
                import re
                match = re.search(rf"{pattern}.*?(\d+)", response_lower)
                if match:
                    return min(10, max(1, int(match.group(1))))
                return default
            
            content_quality = extract_score("content quality", 6)
            educational_value = extract_score("educational value", 5)
            technical_depth = extract_score("technical depth", 5)
            consistency = extract_score("consistency", 6)
            
            # Extract marketing ratio (look for decimal values)
            marketing_ratio = 0.4  # Default
            ratio_match = re.search(r"marketing.*?ratio.*?(\d+\.?\d*)", response_lower)
            if ratio_match:
                marketing_ratio = min(1.0, max(0.0, float(ratio_match.group(1))))
            
            # Extract lists (red flags, positive indicators, etc.)
            def extract_list_items(section_name: str) -> List[str]:
                items = []
                lines = llm_response.split('\n')
                in_section = False
                for line in lines:
                    if section_name.lower() in line.lower():
                        in_section = True
                        continue
                    elif in_section and line.strip():
                        if line.strip().startswith(('-', '•', '*', str(len(items)+1))):
                            items.append(line.strip().lstrip('-•*0123456789. '))
                        elif not line[0].isspace():  # New section started
                            break
                return items[:5]  # Limit to 5 items
            
            red_flags = extract_list_items("red flags")
            positive_indicators = extract_list_items("positive indicators")
            focus_areas = extract_list_items("focus areas")
            topics = extract_list_items("topics covered")
            
            # Fallback to metadata analysis for missing fields
            metadata_analysis = self._analyze_metadata_patterns(result)
            
            return {
                'channel_summary': self._extract_summary_from_llm(llm_response) or metadata_analysis['channel_summary'],
                'communication_style': self._extract_style_from_llm(llm_response) or metadata_analysis['communication_style'],
                'content_quality_score': content_quality,
                'educational_value_score': educational_value,
                'technical_depth_score': technical_depth,
                'primary_content_types': metadata_analysis['primary_content_types'],  # Keep from metadata
                'topics_covered': topics or metadata_analysis['topics_covered'],
                'target_audience': self._extract_audience_from_llm(llm_response) or metadata_analysis['target_audience'],
                'update_frequency_pattern': self._extract_pattern_from_llm(llm_response) or metadata_analysis['update_frequency_pattern'],
                'project_focus_areas': focus_areas or metadata_analysis['project_focus_areas'],
                'development_activity_indicators': extract_list_items("development activity") or metadata_analysis['development_activity_indicators'],
                'community_engagement_style': self._extract_engagement_from_llm(llm_response) or metadata_analysis['community_engagement_style'],
                'transparency_level': self._extract_transparency_from_llm(llm_response) or metadata_analysis['transparency_level'],
                'information_density': self._extract_density_from_llm(llm_response) or 'medium',
                'marketing_vs_substance_ratio': marketing_ratio,
                'consistency_score': consistency,
                'red_flags': red_flags or metadata_analysis['red_flags'],
                'positive_indicators': positive_indicators or metadata_analysis['positive_indicators']
            }
            
        except Exception as e:
            logger.warning(f"Error parsing LLM response, using metadata analysis: {e}")
            return self._analyze_metadata_patterns(result)
    
    def _extract_summary_from_llm(self, response: str) -> Optional[str]:
        """Extract channel summary from LLM response."""
        lines = response.split('\n')
        for i, line in enumerate(lines):
            if 'channel summary' in line.lower() and i + 1 < len(lines):
                summary = lines[i + 1].strip()
                if summary and len(summary) > 10:
                    return summary
        return None
    
    def _extract_style_from_llm(self, response: str) -> Optional[str]:
        """Extract communication style from LLM response."""
        styles = ['educational', 'promotional', 'technical', 'mixed']
        response_lower = response.lower()
        for style in styles:
            if f'communication style' in response_lower and style in response_lower:
                return style
        return None
    
    def _extract_audience_from_llm(self, response: str) -> Optional[str]:
        """Extract target audience from LLM response."""
        audiences = ['beginners', 'advanced', 'developers', 'mixed', 'general']
        response_lower = response.lower()
        for audience in audiences:
            if 'target audience' in response_lower and audience in response_lower:
                return audience
        return None
    
    def _extract_pattern_from_llm(self, response: str) -> Optional[str]:
        """Extract update pattern from LLM response."""
        patterns = ['regular', 'sporadic', 'burst', 'inactive']
        response_lower = response.lower()
        for pattern in patterns:
            if 'frequency pattern' in response_lower and pattern in response_lower:
                return pattern
        return None
    
    def _extract_engagement_from_llm(self, response: str) -> Optional[str]:
        """Extract engagement style from LLM response."""
        response_lower = response.lower()
        if 'engagement style' in response_lower:
            # Extract the line after "engagement style"
            lines = response.split('\n')
            for i, line in enumerate(lines):
                if 'engagement style' in line.lower() and i + 1 < len(lines):
                    return lines[i + 1].strip()[:100]  # Limit length
        return None
    
    def _extract_transparency_from_llm(self, response: str) -> Optional[str]:
        """Extract transparency level from LLM response."""
        levels = ['high', 'medium', 'low']
        response_lower = response.lower()
        for level in levels:
            if 'transparency' in response_lower and level in response_lower:
                return level
        return None
    
    def _extract_density_from_llm(self, response: str) -> Optional[str]:
        """Extract information density from LLM response."""
        densities = ['high', 'medium', 'low']
        response_lower = response.lower()
        for density in densities:
            if 'information density' in response_lower and density in response_lower:
                return density
        return None
    
    def analyze_youtube_content(self, result: YouTubeAnalysisResult) -> YouTubeContentAnalysis:
        """
        Analyze YouTube channel content and return structured analysis.
        
        Args:
            result: YouTubeAnalysisResult from scraper
            
        Returns:
            YouTubeContentAnalysis with comprehensive analysis results
        """
        logger.info(f"Analyzing YouTube content for channel: {result.channel_id}")
        
        if not result.scrape_success:
            logger.warning(f"Cannot analyze failed scrape result: {result.error_message}")
            # Return minimal analysis for failed scrapes
            return YouTubeContentAnalysis(
                channel_summary=f"Analysis failed: {result.error_message}",
                communication_style="unknown",
                content_quality_score=1,
                educational_value_score=1,
                technical_depth_score=1,
                primary_content_types=[],
                topics_covered=[],
                target_audience="unknown",
                update_frequency_pattern="inactive",
                project_focus_areas=[],
                development_activity_indicators=[],
                community_engagement_style="unknown",
                transparency_level="unknown",
                information_density="unknown",
                marketing_vs_substance_ratio=0.5,
                consistency_score=1,
                red_flags=[f"Analysis failed: {result.error_message}"],
                positive_indicators=[],
                confidence_score=0.0,
                analysis_timestamp=datetime.now(UTC),
                videos_analyzed_count=0,
                analysis_method="failed"
            )
        
        # Perform analysis (LLM or metadata-based)
        if self.llm_available and result.videos_analyzed:
            analysis_data = self._analyze_with_llm(result)
        else:
            analysis_data = self._analyze_metadata_patterns(result)
        
        # Create structured analysis result
        content_analysis = YouTubeContentAnalysis(
            channel_summary=analysis_data['channel_summary'],
            communication_style=analysis_data['communication_style'],
            content_quality_score=analysis_data['content_quality_score'],
            educational_value_score=analysis_data['educational_value_score'],
            technical_depth_score=analysis_data['technical_depth_score'],
            primary_content_types=analysis_data['primary_content_types'],
            topics_covered=analysis_data['topics_covered'],
            target_audience=analysis_data['target_audience'],
            update_frequency_pattern=analysis_data['update_frequency_pattern'],
            project_focus_areas=analysis_data['project_focus_areas'],
            development_activity_indicators=analysis_data['development_activity_indicators'],
            community_engagement_style=analysis_data['community_engagement_style'],
            transparency_level=analysis_data['transparency_level'],
            information_density=analysis_data['information_density'],
            marketing_vs_substance_ratio=analysis_data['marketing_vs_substance_ratio'],
            consistency_score=analysis_data['consistency_score'],
            red_flags=analysis_data['red_flags'],
            positive_indicators=analysis_data['positive_indicators'],
            confidence_score=analysis_data['confidence_score'],
            analysis_timestamp=datetime.now(UTC),
            videos_analyzed_count=len(result.videos_analyzed),
            analysis_method=analysis_data['analysis_method']
        )
        
        logger.success(f"YouTube content analysis complete: {analysis_data['analysis_method']} method, confidence {analysis_data['confidence_score']:.2f}")
        
        return content_analysis
    
    def format_analysis_for_storage(self, analysis: YouTubeContentAnalysis) -> Dict[str, Any]:
        """Format analysis results for database storage."""
        return {
            'summary': analysis.channel_summary,
            'technical_depth_score': analysis.technical_depth_score,
            'content_quality_score': analysis.content_quality_score,
            'marketing_vs_tech_ratio': analysis.marketing_vs_substance_ratio,
            'confidence_score': analysis.confidence_score,
            
            # YouTube-specific fields
            'communication_style': analysis.communication_style,
            'educational_value_score': analysis.educational_value_score,
            'target_audience': analysis.target_audience,
            'update_frequency_pattern': analysis.update_frequency_pattern,
            'community_engagement_style': analysis.community_engagement_style,
            'transparency_level': analysis.transparency_level,
            'information_density': analysis.information_density,
            'consistency_score': analysis.consistency_score,
            
            # Structured data as JSON
            'primary_content_types': json.dumps(analysis.primary_content_types),
            'topics_covered': json.dumps(analysis.topics_covered),
            'project_focus_areas': json.dumps(analysis.project_focus_areas),
            'development_activity_indicators': json.dumps(analysis.development_activity_indicators),
            'red_flags': json.dumps(analysis.red_flags),
            'positive_indicators': json.dumps(analysis.positive_indicators),
            
            # Metadata
            'analysis_version': '1.0',
            'model_used': 'youtube_analyzer',
            'videos_analyzed_count': analysis.videos_analyzed_count,
            'analysis_method': analysis.analysis_method
        }


# Test functionality
if __name__ == "__main__":
    from scrapers.youtube_scraper import YouTubeScraper
    
    analyzer = YouTubeAnalyzer()
    scraper = YouTubeScraper(recent_days=30, max_videos=10)
    
    # Test with a known channel
    test_url = "https://www.youtube.com/@ethereum"
    
    print(f"Testing YouTube analysis for: {test_url}")
    
    # First scrape the channel
    scrape_result = scraper.scrape_youtube_channel(test_url)
    print(f"Scrape success: {scrape_result.scrape_success}")
    
    if scrape_result.scrape_success:
        print(f"Videos found: {len(scrape_result.videos_analyzed)}")
        
        # Then analyze the content
        analysis = analyzer.analyze_youtube_content(scrape_result)
        
        print(f"\nAnalysis Results:")
        print(f"Summary: {analysis.channel_summary}")
        print(f"Communication Style: {analysis.communication_style}")
        print(f"Content Quality: {analysis.content_quality_score}/10")
        print(f"Educational Value: {analysis.educational_value_score}/10")
        print(f"Technical Depth: {analysis.technical_depth_score}/10")
        print(f"Primary Content Types: {analysis.primary_content_types}")
        print(f"Topics Covered: {analysis.topics_covered}")
        print(f"Target Audience: {analysis.target_audience}")
        print(f"Red Flags: {analysis.red_flags}")
        print(f"Positive Indicators: {analysis.positive_indicators}")
        print(f"Confidence: {analysis.confidence_score:.2f}")
        print(f"Analysis Method: {analysis.analysis_method}")
    else:
        print(f"Scrape failed: {scrape_result.error_message}")