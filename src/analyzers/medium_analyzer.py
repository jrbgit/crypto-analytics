"""
Medium Content Analyzer using LLM

This module handles:
- LLM-based analysis of Medium article content from crypto projects
- Sentiment analysis and content classification
- Community engagement assessment
- Publication pattern analysis
- Development vs marketing content categorization
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

# Load environment variables
config_path = Path(__file__).parent.parent.parent / "config" / "env"
load_dotenv(config_path)

# Import our scraped data structures
from scrapers.medium_scraper import MediumArticle, MediumAnalysisResult


@dataclass
class MediumAnalysis:
    """Structured analysis result for Medium publication content."""
    
    # Publication overview
    publication_name: str
    publication_url: str
    total_articles_analyzed: int
    analysis_period_days: int
    
    # Content classification and sentiment
    content_breakdown: Dict[str, int]  # Count by type: technical, announcement, marketing, update, other
    technical_content_percentage: float  # % of content that's technical
    marketing_content_percentage: float  # % of content that's marketing/promotional
    
    # Sentiment and engagement analysis  
    overall_sentiment_score: float  # -1 to 1 (negative to positive)
    community_engagement_score: float  # 0-10 based on frequency, quality, interaction
    content_quality_score: int  # 1-10 overall content quality
    
    # Development activity indicators
    development_activity_score: int  # 1-10 based on technical updates, progress reports
    recent_development_mentions: List[str]  # Recent technical/development topics
    roadmap_mentions: List[str]  # Roadmap or milestone mentions
    
    # Publication patterns
    publication_frequency: float  # Articles per week
    consistency_score: float  # 0-1, how consistent is the publishing schedule
    last_post_date: datetime
    post_frequency_trend: str  # "increasing", "stable", "decreasing"
    
    # Team and development insights
    team_activity_indicators: List[str]  # Signs of active team development
    partnership_announcements: List[str]  # Recent partnerships mentioned
    funding_mentions: List[str]  # Any funding/investment mentions
    
    # Community and market focus
    community_initiatives: List[str]  # Community-focused content
    educational_content: List[str]  # Educational posts, tutorials, explainers
    market_commentary: List[str]  # Market analysis, price discussions
    
    # Red flags and concerns
    red_flags: List[str]  # Concerning patterns or content
    spam_indicators: List[str]  # Signs of spam or low-quality content
    misleading_claims: List[str]  # Potentially misleading statements
    
    # Competitive analysis
    competitive_mentions: List[str]  # Mentions of competitors or comparisons
    positioning_statements: List[str]  # How they position themselves
    
    # Analysis metadata
    confidence_score: float  # 0-1, confidence in analysis
    analysis_timestamp: datetime
    model_used: str
    articles_with_detailed_analysis: int  # How many had full content analysis
    

class MediumContentAnalyzer:
    """LLM-powered Medium content analyzer for cryptocurrency projects."""
    
    def __init__(self, provider: str = "ollama", model: str = "llama3.1:latest", ollama_base_url: str = "http://localhost:11434"):
        """
        Initialize the analyzer.
        
        Args:
            provider: "anthropic", "openai", or "ollama"
            model: Model to use for analysis
            ollama_base_url: Base URL for Ollama server
        """
        self.provider = provider
        self.model = model
        self.ollama_base_url = ollama_base_url
        
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
        """Build the comprehensive Medium analysis prompt."""
        return """
You are a cryptocurrency and blockchain content analyst. Analyze the provided Medium publication content from a crypto project and extract structured insights about their communication strategy, development activity, and community engagement.

Please analyze the content and provide a JSON response with the following structure:

{
    "overall_sentiment_score": sentiment_score_from_negative_1_to_positive_1,
    "community_engagement_score": score_0_to_10_based_on_interaction_and_community_focus,
    "content_quality_score": score_1_to_10_for_writing_quality_and_informativeness,
    "development_activity_score": score_1_to_10_based_on_technical_updates_and_progress,
    "recent_development_mentions": ["recent technical topics", "development updates", "feature releases"],
    "roadmap_mentions": ["roadmap items mentioned", "milestones", "future plans"],
    "team_activity_indicators": ["signs of active development", "team member posts", "behind-the-scenes content"],
    "partnership_announcements": ["partnerships mentioned", "integrations", "collaborations"],
    "funding_mentions": ["investment rounds", "funding news", "financial milestones"],
    "community_initiatives": ["community programs", "events", "engagement activities"],
    "educational_content": ["tutorials", "explainer posts", "educational material"],
    "market_commentary": ["market analysis", "price discussions", "trading insights"],
    "red_flags": ["concerning patterns", "questionable claims", "potential issues"],
    "spam_indicators": ["repetitive content", "low-quality posts", "excessive promotion"],
    "misleading_claims": ["potentially misleading statements", "unsubstantiated claims"],
    "competitive_mentions": ["competitor comparisons", "competitive analysis"],
    "positioning_statements": ["how they position themselves", "value propositions"],
    "consistency_score": score_0_to_1_for_publishing_consistency,
    "post_frequency_trend": "one of: increasing, stable, decreasing",
    "confidence_score": confidence_0_to_1_in_this_analysis
}

Analysis Guidelines:
1. Focus on the overall communication strategy and patterns
2. Look for signs of active development vs pure marketing
3. Assess community engagement quality and authenticity
4. Identify educational vs promotional content
5. Note any red flags like spam, misleading claims, or concerning patterns
6. Evaluate consistency and professionalism of communication
7. Consider the balance between technical depth and accessibility
8. Look for genuine community building vs token promotion
9. Assess transparency about development progress and challenges
10. Consider the recency and relevance of content

Sentiment scoring:
- Positive (0.5 to 1.0): Optimistic, constructive, solution-focused
- Neutral (-0.5 to 0.5): Balanced, informative, matter-of-fact  
- Negative (-1.0 to -0.5): Pessimistic, critical, problem-focused

Publication data to analyze:
"""

    def _call_anthropic(self, content: str) -> Dict[str, Any]:
        """Make API call to Anthropic."""
        try:
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=2000,
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
                max_tokens=2000,
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
        """Make API call to Ollama."""
        try:
            payload = {
                "model": self.model,
                "prompt": self.analysis_prompt + "\n\n" + content + "\n\nIMPORTANT: Respond ONLY with valid JSON, no additional text or explanation.",
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2000
                },
                "format": "json"  # Force JSON format
            }
            
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json=payload,
                timeout=150  # Longer timeout for complex analysis
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama API returned {response.status_code}: {response.text}")
                return self._create_fallback_analysis()
            
            response_data = response.json()
            response_text = response_data.get('response', '').strip()
            
            # Log raw response for debugging
            logger.debug(f"Raw Ollama response: {response_text[:200]}...")
            
            # Try to find and extract JSON
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error("No JSON found in Ollama response")
                logger.error(f"Full response: {response_text}")
                return self._create_fallback_analysis()
            
            json_str = response_text[start_idx:end_idx]
            
            # Clean up common JSON issues
            json_str = json_str.replace('\n', ' ').replace('\t', ' ')
            json_str = json_str.replace('\\"', '"')
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.error(f"Problematic JSON: {json_str[:200]}...")
                return self._try_fix_json(json_str)
            
        except requests.exceptions.RequestException as e:
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
            "publication_name": "Unknown",
            "total_articles_analyzed": 0,
            "analysis_period_days": 90,
            "publication_frequency": 0.0,
            "content_quality_score": 5,
            "technical_content_percentage": 20.0,
            "marketing_content_percentage": 40.0,
            "announcement_content_percentage": 20.0,
            "development_activity_score": 5,
            "community_engagement_score": 5,
            "articles_with_detailed_analysis": 0,
            "partnership_announcements": ["Analysis failed - using fallback"],
            "roadmap_mentions": [],
            "recent_development_mentions": [],
            "team_activity_indicators": [],
            "educational_content": [],
            "competitive_mentions": [],
            "red_flags": ["Analysis incomplete due to technical issues"],
            "spam_indicators": [],
            "misleading_claims": [],
            "content_breakdown": {"technical": 1, "marketing": 2, "other": 2},
            "overall_sentiment_score": 0.0,
            "confidence_score": 0.1
        }
    
    def _prepare_content_for_analysis(self, scrape_result: MediumAnalysisResult) -> str:
        """Prepare Medium content for LLM analysis."""
        
        if not scrape_result.scrape_success or not scrape_result.articles_found:
            return ""
        
        # Build content summary for analysis
        content_parts = [
            f"Publication: {scrape_result.publication_name}",
            f"URL: {scrape_result.publication_url}",
            f"Total articles analyzed: {scrape_result.total_articles}",
            f"Publication frequency: {scrape_result.publication_frequency:.2f} articles/week",
            f"Last post date: {scrape_result.last_post_date}",
            f"Content distribution: {scrape_result.content_distribution}",
            f"Average reading time: {scrape_result.avg_reading_time:.1f} minutes",
            "",
            "RECENT ARTICLES SUMMARY:"
        ]
        
        # Include article summaries (first 5 with full content, then just titles)
        for i, article in enumerate(scrape_result.articles_found):
            if i < 5:  # Full analysis for first 5
                article_summary = [
                    f"\n--- Article {i+1}: {article.title} ---",
                    f"Published: {article.published_date.strftime('%Y-%m-%d')}",
                    f"Author: {article.author}",
                    f"Type: {article.article_type}",
                    f"Word count: {article.word_count}",
                    f"Reading time: {article.reading_time} min" if article.reading_time > 0 else "",
                    f"Tags: {', '.join(article.tags)}" if article.tags else "",
                    f"Content preview: {article.content[:1000]}..." if len(article.content) > 1000 else f"Content: {article.content}"
                ]
            else:  # Just title and basic info for the rest
                article_summary = [
                    f"\n--- Article {i+1}: {article.title} ---",
                    f"Published: {article.published_date.strftime('%Y-%m-%d')}",
                    f"Type: {article.article_type}",
                    f"Tags: {', '.join(article.tags)}" if article.tags else ""
                ]
            
            content_parts.extend(article_summary)
        
        return "\n".join(content_parts)
    
    def analyze_medium_publication(self, scrape_result: MediumAnalysisResult) -> Optional[MediumAnalysis]:
        """
        Analyze Medium publication content using LLM.
        
        Args:
            scrape_result: Result from MediumScraper
            
        Returns:
            MediumAnalysis with structured insights
        """
        if not scrape_result.scrape_success:
            logger.error(f"Cannot analyze failed scrape: {scrape_result.error_message}")
            return None
        
        if not scrape_result.articles_found:
            logger.warning("No articles found to analyze")
            return None
        
        logger.info(f"Starting LLM analysis of {scrape_result.publication_name} with {len(scrape_result.articles_found)} articles")
        
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
        content_breakdown = scrape_result.content_distribution or {}
        total_articles = scrape_result.total_articles
        
        technical_percentage = content_breakdown.get('technical', 0) / total_articles * 100 if total_articles > 0 else 0
        marketing_percentage = (content_breakdown.get('marketing', 0) + content_breakdown.get('announcement', 0)) / total_articles * 100 if total_articles > 0 else 0
        
        # Build final analysis object
        try:
            analysis = MediumAnalysis(
                publication_name=scrape_result.publication_name,
                publication_url=scrape_result.publication_url,
                total_articles_analyzed=total_articles,
                analysis_period_days=90,  # Based on scraper default
                content_breakdown=content_breakdown,
                technical_content_percentage=technical_percentage,
                marketing_content_percentage=marketing_percentage,
                
                # From LLM analysis
                overall_sentiment_score=analysis_result.get('overall_sentiment_score', 0.0),
                community_engagement_score=analysis_result.get('community_engagement_score', 5.0),
                content_quality_score=analysis_result.get('content_quality_score', 5),
                development_activity_score=analysis_result.get('development_activity_score', 5),
                recent_development_mentions=analysis_result.get('recent_development_mentions', []),
                roadmap_mentions=analysis_result.get('roadmap_mentions', []),
                team_activity_indicators=analysis_result.get('team_activity_indicators', []),
                partnership_announcements=analysis_result.get('partnership_announcements', []),
                funding_mentions=analysis_result.get('funding_mentions', []),
                community_initiatives=analysis_result.get('community_initiatives', []),
                educational_content=analysis_result.get('educational_content', []),
                market_commentary=analysis_result.get('market_commentary', []),
                red_flags=analysis_result.get('red_flags', []),
                spam_indicators=analysis_result.get('spam_indicators', []),
                misleading_claims=analysis_result.get('misleading_claims', []),
                competitive_mentions=analysis_result.get('competitive_mentions', []),
                positioning_statements=analysis_result.get('positioning_statements', []),
                
                # Publication metrics from scrape data
                publication_frequency=scrape_result.publication_frequency,
                consistency_score=analysis_result.get('consistency_score', 0.5),
                last_post_date=scrape_result.last_post_date or datetime.now(UTC),
                post_frequency_trend=analysis_result.get('post_frequency_trend', 'stable'),
                
                # Analysis metadata
                confidence_score=analysis_result.get('confidence_score', 0.7),
                analysis_timestamp=datetime.now(UTC),
                model_used=f"{self.provider}:{self.model}",
                articles_with_detailed_analysis=min(5, len(scrape_result.articles_found))  # We analyze first 5 in detail
            )
            
            logger.success(f"Medium analysis complete for {scrape_result.publication_name}")
            logger.info(f"Engagement score: {analysis.community_engagement_score}/10, Development activity: {analysis.development_activity_score}/10")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to construct analysis object: {e}")
            return None


# Test functionality
if __name__ == "__main__":
    from scrapers.medium_scraper import MediumScraper
    
    # Test the analyzer with real data
    scraper = MediumScraper(max_articles=10, recent_days=30)
    analyzer = MediumContentAnalyzer(provider="ollama", model="llama3.1:latest")
    
    test_urls = [
        "https://medium.com/@binance"
    ]
    
    for url in test_urls:
        print(f"\n=== Testing analysis for {url} ===")
        
        # First scrape the content
        scrape_result = scraper.scrape_medium_publication(url)
        
        if scrape_result.scrape_success:
            print(f"Scraped {scrape_result.total_articles} articles")
            
            # Then analyze it
            analysis = analyzer.analyze_medium_publication(scrape_result)
            
            if analysis:
                print(f"Analysis complete!")
                print(f"Engagement score: {analysis.community_engagement_score}/10")
                print(f"Development activity: {analysis.development_activity_score}/10") 
                print(f"Content quality: {analysis.content_quality_score}/10")
                print(f"Sentiment: {analysis.overall_sentiment_score}")
                print(f"Technical content: {analysis.technical_content_percentage:.1f}%")
                print(f"Recent development mentions: {len(analysis.recent_development_mentions)}")
            else:
                print("Analysis failed")
        else:
            print(f"Scraping failed: {scrape_result.error_message}")