"""
Reddit Content Analyzer using LLM

This module handles:
- LLM-based analysis of Reddit community discussions for crypto projects
- Community sentiment analysis and engagement assessment
- Post type classification and content quality evaluation
- Moderator activity and community management assessment
- Cross-community mention frequency analysis
- Hype vs technical discussion ratio analysis
"""

import json
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger
import openai
from anthropic import Anthropic
import requests
import json as json_lib
from models.database import DatabaseManager, APIUsage

# Load environment variables
config_path = Path(__file__).parent.parent.parent / "config" / "env"
load_dotenv(config_path)

# Import our scraped data structures
from scrapers.reddit_scraper import RedditPost, RedditAnalysisResult, SubredditInfo


@dataclass
class RedditAnalysis:
    """Structured analysis result for Reddit community content."""
    
    # Community overview
    subreddit_name: str
    subreddit_url: str
    total_posts_analyzed: int
    analysis_period_days: int
    subscriber_count: int
    
    # Community health and engagement
    community_health_score: int  # 1-10 overall community health
    engagement_authenticity_score: int  # 1-10 genuine vs artificial engagement
    discussion_quality_score: int  # 1-10 quality of discussions
    moderator_effectiveness_score: int  # 1-10 moderation quality
    
    # Content analysis
    content_type_breakdown: Dict[str, int]  # Count by type: technical, hype, news, discussion, etc.
    technical_discussion_percentage: float  # % of content that's technical
    hype_content_percentage: float  # % of content that's hype/speculation
    news_content_percentage: float  # % of content that's news/announcements
    
    # Sentiment and community mood
    overall_sentiment_score: float  # -1 to 1 (negative to positive)
    community_confidence_level: str  # "very_low", "low", "moderate", "high", "very_high"
    fud_indicators: List[str]  # Signs of FUD (fear, uncertainty, doubt)
    fomo_indicators: List[str]  # Signs of FOMO (fear of missing out)
    
    # Community dynamics
    newcomer_friendliness_score: int  # 1-10 how welcoming to new users
    echo_chamber_risk: str  # "low", "moderate", "high" - risk of echo chamber
    tribalism_indicators: List[str]  # Signs of toxic tribalism
    constructive_criticism_presence: bool  # Presence of balanced criticism
    
    # Development and project focus
    development_awareness_score: int  # 1-10 community awareness of development
    project_milestone_discussions: List[str]  # Discussions about project milestones
    technical_literacy_level: str  # "low", "moderate", "high"
    roadmap_awareness_indicators: List[str]  # Evidence of roadmap awareness
    
    # Red flags and concerns
    red_flags: List[str]  # Community red flags
    manipulation_indicators: List[str]  # Signs of price/sentiment manipulation
    misinformation_presence: List[str]  # Misinformation or false claims
    
    # Competitive landscape awareness
    competitive_discussions: List[str]  # Discussions comparing to competitors
    market_position_awareness: str  # "poor", "fair", "good", "excellent"
    partnership_discussions: List[str]  # Partnership and collaboration discussions
    
    # Activity patterns
    posting_frequency_trend: str  # "increasing", "stable", "decreasing"
    user_retention_indicators: List[str]  # Signs of good user retention
    seasonal_activity_patterns: Dict[str, Any]  # Activity pattern insights
    
    # Analysis metadata
    confidence_score: float  # 0-1, confidence in analysis
    analysis_timestamp: datetime
    model_used: str
    posts_with_detailed_analysis: int  # How many posts had full content analysis


class RedditContentAnalyzer:
    """LLM-powered Reddit content analyzer for cryptocurrency projects."""
    
    def __init__(self, provider: str = "ollama", model: str = "llama3.1:latest", ollama_base_url: str = "http://localhost:11434", db_manager: DatabaseManager = None):
        """
        Initialize the analyzer.
        
        Args:
            provider: "anthropic", "openai", or "ollama"
            model: Model to use for analysis
            ollama_base_url: Base URL for Ollama server
            db_manager: Database manager for usage tracking
        """
        self.provider = provider
        self.model = model
        self.ollama_base_url = ollama_base_url
        self.db_manager = db_manager
        
        # Initialize clients
        if provider == "anthropic":
            self.anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        elif provider == "openai":
            self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif provider == "ollama":
            # Test Ollama connection
            self._test_ollama_connection()
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        # Analysis prompts
        self.analysis_prompt = self._build_analysis_prompt()
        
    def _test_ollama_connection(self):
        """Test connection to Ollama server."""
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                available_models = response.json().get('models', [])
                model_names = [model['name'] for model in available_models]
                logger.info(f"Connected to Ollama server. Available models: {model_names}")
                
                # Check if our model is available
                if not any(self.model in name for name in model_names):
                    logger.warning(f"Model {self.model} not found. Available models: {model_names}")
                    logger.info(f"You can pull the model with: ollama pull {self.model}")
                else:
                    logger.success(f"Model {self.model} is available")
            else:
                logger.error(f"Failed to connect to Ollama: HTTP {response.status_code}")
                raise ConnectionError(f"Ollama server returned {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Cannot connect to Ollama server at {self.ollama_base_url}: {e}")
            raise ConnectionError(f"Ollama connection failed: {e}")
        
    def _build_analysis_prompt(self) -> str:
        """Build the comprehensive Reddit analysis prompt."""
        return """
You are a cryptocurrency community and social media analyst. Analyze the provided Reddit community data from a crypto project and extract structured insights about community health, engagement, sentiment, and overall project perception.

Please analyze the content and provide a JSON response with the following structure:

{
    "community_health_score": score_1_to_10_for_overall_community_health,
    "engagement_authenticity_score": score_1_to_10_for_genuine_vs_artificial_engagement,
    "discussion_quality_score": score_1_to_10_for_quality_of_discussions,
    "moderator_effectiveness_score": score_1_to_10_for_moderation_quality,
    "technical_discussion_percentage": percentage_of_technical_content,
    "hype_content_percentage": percentage_of_hype_speculation_content,
    "news_content_percentage": percentage_of_news_announcements,
    "overall_sentiment_score": sentiment_score_from_negative_1_to_positive_1,
    "community_confidence_level": "one of: very_low, low, moderate, high, very_high",
    "fud_indicators": ["signs of fear uncertainty doubt", "negative sentiment patterns"],
    "fomo_indicators": ["signs of fear of missing out", "hype patterns"],
    "newcomer_friendliness_score": score_1_to_10_for_welcoming_new_users,
    "echo_chamber_risk": "one of: low, moderate, high",
    "tribalism_indicators": ["signs of toxic tribalism", "us vs them mentality"],
    "constructive_criticism_presence": true_or_false_for_balanced_criticism,
    "development_awareness_score": score_1_to_10_for_development_awareness,
    "project_milestone_discussions": ["milestone discussions", "development updates"],
    "technical_literacy_level": "one of: low, moderate, high",
    "roadmap_awareness_indicators": ["evidence of roadmap knowledge", "future planning discussions"],
    "red_flags": ["community red flags", "concerning patterns"],
    "manipulation_indicators": ["signs of manipulation", "coordinated behavior"],
    "misinformation_presence": ["false claims", "misleading information"],
    "competitive_discussions": ["competitor comparisons", "market positioning talks"],
    "market_position_awareness": "one of: poor, fair, good, excellent",
    "partnership_discussions": ["partnership talks", "collaboration mentions"],
    "posting_frequency_trend": "one of: increasing, stable, decreasing",
    "user_retention_indicators": ["signs of good retention", "community stickiness"],
    "seasonal_activity_patterns": {"key": "activity insights", "pattern": "seasonal trends"},
    "confidence_score": confidence_0_to_1_in_this_analysis
}

Analysis Guidelines:
1. Focus on genuine community health vs artificial metrics
2. Distinguish between authentic engagement and bot/shill activity
3. Assess the balance between technical discussion and pure speculation
4. Look for signs of healthy skepticism vs blind faith
5. Evaluate moderator presence and community management quality
6. Identify manipulation patterns, coordinated messaging, or astroturfing
7. Assess technical literacy and understanding of the project
8. Look for evidence of actual project usage vs just price speculation
9. Consider community resilience during market downturns
10. Evaluate diversity of opinions and discussion quality

Community Health Indicators:
- High: Active development discussions, balanced criticism, diverse viewpoints, good moderation
- Medium: Some technical content, mixed sentiment, moderate engagement
- Low: Mostly price speculation, echo chamber behavior, poor moderation, manipulation signs

Sentiment Scoring:
- Positive (0.5 to 1.0): Optimistic, constructive, solution-focused, realistic enthusiasm
- Neutral (-0.5 to 0.5): Balanced, informative, mixed opinions
- Negative (-1.0 to -0.5): Pessimistic, FUD-driven, panic, excessive criticism

Reddit community data to analyze:
"""

    def _call_anthropic(self, content: str) -> Dict[str, Any]:
        """Make API call to Anthropic."""
        try:
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=2500,
                messages=[
                    {
                        "role": "user", 
                        "content": self.analysis_prompt + "\n\n" + content
                    }
                ]
            )
            
            # Extract JSON from response
            response_text = response.content[0].text
            
            # Try to find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error("No JSON found in response")
                return None
            
            json_str = response_text[start_idx:end_idx]
            return json.loads(json_str)
            
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            return None
    
    def _call_openai(self, content: str) -> Dict[str, Any]:
        """Make API call to OpenAI."""
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": self.analysis_prompt + "\n\n" + content
                    }
                ],
                max_tokens=2500,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content
            
            # Try to find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error("No JSON found in response")
                return None
            
            json_str = response_text[start_idx:end_idx]
            return json.loads(json_str)
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return None
    
    def _call_ollama(self, content: str) -> Dict[str, Any]:
        """Make API call to Ollama with usage tracking."""
        start_time = time.time()
        try:
            full_prompt = self.analysis_prompt + "\n\n" + content + "\n\nIMPORTANT: Respond ONLY with valid JSON, no additional text or explanation."
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2500
                },
                "format": "json"  # Force JSON format
            }
            
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json=payload,
                timeout=180  # Longer timeout for complex analysis
            )
            
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                # Log failed request
                if self.db_manager:
                    try:
                        with self.db_manager.get_session() as session:
                            self.db_manager.log_api_usage(
                                session=session,
                                provider='ollama',
                                endpoint=f'{self.model}/generate',
                                status=response.status_code,
                                response_size=0,
                                response_time=response_time,
                                credits_used=0,
                                error_message=f"HTTP {response.status_code}: {response.text[:200]}"
                            )
                            session.commit()
                    except Exception as e:
                        logger.warning(f"Failed to log Ollama error: {e}")
                
                logger.error(f"Ollama API returned {response.status_code}: {response.text}")
                return None
            
            response_data = response.json()
            response_text = response_data.get('response', '').strip()
            
            # Estimate token usage and log successful request
            if self.db_manager:
                try:
                    prompt_tokens = len(full_prompt.split()) // 0.75
                    response_tokens = len(response_text.split()) // 0.75 if response_text else 0
                    estimated_tokens = int(prompt_tokens + response_tokens)
                    
                    with self.db_manager.get_session() as session:
                        self.db_manager.log_api_usage(
                            session=session,
                            provider='ollama',
                            endpoint=f'{self.model}/generate',
                            status=response.status_code,
                            response_size=estimated_tokens,
                            response_time=response_time,
                            credits_used=1
                        )
                        session.commit()
                        logger.debug(f"Ollama reddit usage: {estimated_tokens} tokens, {response_time:.2f}s")
                except Exception as e:
                    logger.warning(f"Failed to log Ollama usage: {e}")
            
            # Log raw response for debugging
            logger.debug(f"Raw Ollama response: {response_text[:200]}...")
            
            # Try to find and extract JSON
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error("No JSON found in Ollama response")
                logger.error(f"Full response: {response_text}")
                # Return a fallback analysis
                return self._create_fallback_analysis()
            
            json_str = response_text[start_idx:end_idx]
            
            # Clean up common JSON issues
            json_str = json_str.replace('\n', ' ').replace('\t', ' ')
            # Fix common quote issues
            json_str = json_str.replace('\\"', '"').replace("\'", "\"")
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.error(f"Problematic JSON: {json_str[:200]}...")
                # Try to fix common JSON issues and retry
                return self._try_fix_json(json_str)
            
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            if self.db_manager:
                try:
                    with self.db_manager.get_session() as session:
                        self.db_manager.log_api_usage(
                            session=session,
                            provider='ollama',
                            endpoint=f'{self.model}/generate',
                            status=0,
                            response_size=0,
                            response_time=response_time,
                            credits_used=0,
                            error_message=str(e)
                        )
                        session.commit()
                except Exception as log_error:
                    logger.warning(f"Failed to log Ollama request error: {log_error}")
            
            logger.error(f"Ollama API request failed: {e}")
            return self._create_fallback_analysis()
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            return self._create_fallback_analysis()
    
    def _try_fix_json(self, json_str: str) -> Dict[str, Any]:
        """Try to fix common JSON parsing issues."""
        try:
            # Common fixes
            fixes = [
                lambda x: x.replace(',]', ']'),
                lambda x: x.replace(',}', '}'),
                lambda x: x.replace(',,', ','),
                lambda x: x.replace('""', '"'),
                lambda x: x.replace(': """', ': "'),
                lambda x: x.replace('""",', '",'),
            ]
            
            fixed_json = json_str
            for fix in fixes:
                fixed_json = fix(fixed_json)
            
            return json.loads(fixed_json)
        except:
            logger.warning("Could not fix JSON, returning fallback analysis")
            return self._create_fallback_analysis()
    
    def _create_fallback_analysis(self) -> Dict[str, Any]:
        """Create a fallback analysis when LLM fails."""
        return {
            "community_health_score": 5,
            "engagement_authenticity_score": 5,
            "discussion_quality_score": 5,
            "moderator_effectiveness_score": 5,
            "technical_discussion_percentage": 20.0,
            "hype_content_percentage": 40.0,
            "news_content_percentage": 20.0,
            "overall_sentiment_score": 0.0,
            "community_confidence_level": "moderate",
            "fud_indicators": ["LLM analysis failed - using fallback"],
            "fomo_indicators": [],
            "newcomer_friendliness_score": 5,
            "echo_chamber_risk": "moderate",
            "tribalism_indicators": [],
            "constructive_criticism_presence": False,
            "development_awareness_score": 5,
            "project_milestone_discussions": [],
            "technical_literacy_level": "moderate",
            "roadmap_awareness_indicators": [],
            "red_flags": ["Analysis incomplete due to technical issues"],
            "manipulation_indicators": [],
            "misinformation_presence": [],
            "competitive_discussions": [],
            "market_position_awareness": "fair",
            "partnership_discussions": [],
            "posting_frequency_trend": "stable",
            "user_retention_indicators": [],
            "seasonal_activity_patterns": {"status": "analysis_failed"},
            "confidence_score": 0.1
        }
    
    def _prepare_content_for_analysis(self, scrape_result: RedditAnalysisResult) -> str:
        """Prepare Reddit content for LLM analysis."""
        
        if not scrape_result.scrape_success or not scrape_result.posts_analyzed:
            return ""
        
        # Build content summary for analysis
        content_parts = [
            f"Subreddit: r/{scrape_result.subreddit_name}",
            f"URL: {scrape_result.subreddit_url}",
            f"Total posts analyzed: {scrape_result.total_posts}",
            f"Community activity: {scrape_result.community_activity_score:.1f}/10 posts per day",
            f"Engagement quality: {scrape_result.engagement_quality_score:.1f}/10",
            f"Discussion depth: {scrape_result.discussion_depth_score:.1f}/10 comments per post",
            f"Moderator activity: {scrape_result.moderator_activity_score:.1f}/10",
            f"Average upvote ratio: {scrape_result.avg_upvote_ratio:.2f}",
            f"Content distribution: {scrape_result.content_type_distribution}",
            f"Sentiment indicators: {scrape_result.sentiment_indicators}",
            ""
        ]
        
        # Add subreddit information if available
        if scrape_result.subreddit_info:
            content_parts.extend([
                f"SUBREDDIT INFO:",
                f"Subscribers: {scrape_result.subreddit_info.subscribers:,}",
                f"Active users: {scrape_result.subreddit_info.active_users}",
                f"Moderator count: {scrape_result.subreddit_info.moderator_count}",
                f"Rules count: {scrape_result.subreddit_info.rules_count}",
                f"Created: {scrape_result.subreddit_info.created_utc.strftime('%Y-%m-%d')}",
                f"Description: {scrape_result.subreddit_info.description[:200]}...",
                ""
            ])
        
        content_parts.append("RECENT POSTS SAMPLE:")
        
        # Include post summaries (first 10 with details, then just titles)
        for i, post in enumerate(scrape_result.posts_analyzed[:15]):
            if i < 10:  # Detailed analysis for first 10
                post_summary = [
                    f"\n--- Post {i+1}: {post.title[:100]} ---",
                    f"Author: {post.author}",
                    f"Score: {post.score} (upvote ratio: {post.upvote_ratio:.2f})",
                    f"Comments: {post.num_comments}",
                    f"Type: {post.post_type}",
                    f"Posted: {post.created_utc.strftime('%Y-%m-%d')}",
                    f"Flair: {post.flair}" if post.flair else "",
                    f"Moderator post: {post.is_moderator_post}",
                    f"Content preview: {post.content[:300]}..." if len(post.content) > 300 else f"Content: {post.content}" if post.content else "No content"
                ]
            else:  # Just title and basic info for the rest
                post_summary = [
                    f"\n--- Post {i+1}: {post.title[:100]} ---",
                    f"Score: {post.score}, Comments: {post.num_comments}, Type: {post.post_type}"
                ]
            
            content_parts.extend(post_summary)
        
        return "\n".join(content_parts)
    
    def analyze_reddit_community(self, scrape_result: RedditAnalysisResult) -> Optional[RedditAnalysis]:
        """
        Analyze Reddit community content using LLM.
        
        Args:
            scrape_result: Result from RedditScraper
            
        Returns:
            RedditAnalysis with structured insights
        """
        if not scrape_result.scrape_success:
            logger.error(f"Cannot analyze failed scrape: {scrape_result.error_message}")
            return None
        
        if not scrape_result.posts_analyzed:
            logger.warning("No posts found to analyze")
            return None
        
        logger.info(f"Starting LLM analysis of r/{scrape_result.subreddit_name} with {len(scrape_result.posts_analyzed)} posts")
        
        # Prepare content for analysis
        content_for_analysis = self._prepare_content_for_analysis(scrape_result)
        
        if not content_for_analysis:
            logger.error("No content prepared for analysis")
            return None
        
        # Make LLM API call
        if self.provider == "anthropic":
            analysis_result = self._call_anthropic(content_for_analysis)
        elif self.provider == "openai":
            analysis_result = self._call_openai(content_for_analysis)
        elif self.provider == "ollama":
            analysis_result = self._call_ollama(content_for_analysis)
        else:
            logger.error(f"Unsupported provider: {self.provider}")
            return None
        
        if not analysis_result:
            logger.error("LLM analysis failed")
            return None
        
        # Calculate additional metrics from scrape data
        content_breakdown = scrape_result.content_type_distribution or {}
        total_posts = scrape_result.total_posts
        
        technical_percentage = content_breakdown.get('technical', 0) / total_posts * 100 if total_posts > 0 else 0
        hype_percentage = content_breakdown.get('hype', 0) / total_posts * 100 if total_posts > 0 else 0
        news_percentage = content_breakdown.get('news', 0) / total_posts * 100 if total_posts > 0 else 0
        
        # Build final analysis object
        try:
            analysis = RedditAnalysis(
                subreddit_name=scrape_result.subreddit_name,
                subreddit_url=scrape_result.subreddit_url,
                total_posts_analyzed=total_posts,
                analysis_period_days=30,  # Based on scraper default
                subscriber_count=scrape_result.subreddit_info.subscribers if scrape_result.subreddit_info else 0,
                
                # From LLM analysis
                community_health_score=analysis_result.get('community_health_score', 5),
                engagement_authenticity_score=analysis_result.get('engagement_authenticity_score', 5),
                discussion_quality_score=analysis_result.get('discussion_quality_score', 5),
                moderator_effectiveness_score=analysis_result.get('moderator_effectiveness_score', 5),
                
                # Content breakdown (combine scrape data with LLM insights)
                content_type_breakdown=content_breakdown,
                technical_discussion_percentage=analysis_result.get('technical_discussion_percentage', technical_percentage),
                hype_content_percentage=analysis_result.get('hype_content_percentage', hype_percentage),
                news_content_percentage=analysis_result.get('news_content_percentage', news_percentage),
                
                # Sentiment and mood
                overall_sentiment_score=analysis_result.get('overall_sentiment_score', 0.0),
                community_confidence_level=analysis_result.get('community_confidence_level', 'moderate'),
                fud_indicators=analysis_result.get('fud_indicators', []),
                fomo_indicators=analysis_result.get('fomo_indicators', []),
                
                # Community dynamics
                newcomer_friendliness_score=analysis_result.get('newcomer_friendliness_score', 5),
                echo_chamber_risk=analysis_result.get('echo_chamber_risk', 'moderate'),
                tribalism_indicators=analysis_result.get('tribalism_indicators', []),
                constructive_criticism_presence=analysis_result.get('constructive_criticism_presence', True),
                
                # Development focus
                development_awareness_score=analysis_result.get('development_awareness_score', 5),
                project_milestone_discussions=analysis_result.get('project_milestone_discussions', []),
                technical_literacy_level=analysis_result.get('technical_literacy_level', 'moderate'),
                roadmap_awareness_indicators=analysis_result.get('roadmap_awareness_indicators', []),
                
                # Red flags
                red_flags=analysis_result.get('red_flags', []),
                manipulation_indicators=analysis_result.get('manipulation_indicators', []),
                misinformation_presence=analysis_result.get('misinformation_presence', []),
                
                # Competitive awareness
                competitive_discussions=analysis_result.get('competitive_discussions', []),
                market_position_awareness=analysis_result.get('market_position_awareness', 'fair'),
                partnership_discussions=analysis_result.get('partnership_discussions', []),
                
                # Activity patterns
                posting_frequency_trend=analysis_result.get('posting_frequency_trend', 'stable'),
                user_retention_indicators=analysis_result.get('user_retention_indicators', []),
                seasonal_activity_patterns=analysis_result.get('seasonal_activity_patterns', {}),
                
                # Analysis metadata
                confidence_score=analysis_result.get('confidence_score', 0.7),
                analysis_timestamp=datetime.now(UTC),
                model_used=f"{self.provider}:{self.model}",
                posts_with_detailed_analysis=min(10, len(scrape_result.posts_analyzed))  # We analyze first 10 in detail
            )
            
            logger.success(f"Reddit analysis complete for r/{scrape_result.subreddit_name}")
            logger.info(f"Community health: {analysis.community_health_score}/10, Discussion quality: {analysis.discussion_quality_score}/10")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to construct analysis object: {e}")
            return None


# Test functionality
if __name__ == "__main__":
    from scrapers.reddit_scraper import RedditScraper
    
    # Test the analyzer with real data
    scraper = RedditScraper(recent_days=7, max_posts=30)
    analyzer = RedditContentAnalyzer(provider="ollama", model="llama3.1:latest")
    
    test_urls = [
        "https://reddit.com/r/bitcoin"
    ]
    
    for url in test_urls:
        print(f"\n=== Testing analysis for {url} ===")
        
        # First scrape the content
        scrape_result = scraper.scrape_reddit_community(url)
        
        if scrape_result.scrape_success:
            print(f"Scraped {scrape_result.total_posts} posts")
            
            # Then analyze it
            analysis = analyzer.analyze_reddit_community(scrape_result)
            
            if analysis:
                print(f"Analysis complete!")
                print(f"Community health: {analysis.community_health_score}/10")
                print(f"Discussion quality: {analysis.discussion_quality_score}/10") 
                print(f"Sentiment: {analysis.overall_sentiment_score}")
                print(f"Technical discussion: {analysis.technical_discussion_percentage:.1f}%")
                print(f"Confidence level: {analysis.community_confidence_level}")
            else:
                print("Analysis failed")
        else:
            print(f"Scraping failed: {scrape_result.error_message}")