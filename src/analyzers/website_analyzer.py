"""
Website Content Analyzer using LLM

This module handles:
- LLM-based analysis of website content
- Extraction of structured data: tech stack, team, partnerships, etc.
- Cost-optimized prompting strategies
- Batch processing capabilities
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


@dataclass
class WebsiteAnalysis:
    """Structured analysis result for a cryptocurrency website."""
    
    # Core technology information
    technology_stack: List[str]  # e.g., ["Ethereum", "Solidity", "React"]
    blockchain_platform: Optional[str]  # e.g., "Ethereum", "Binance Smart Chain"
    consensus_mechanism: Optional[str]  # e.g., "Proof of Stake", "Proof of Work"
    
    # Key value propositions
    core_features: List[str]  # Main features/capabilities
    use_cases: List[str]  # Primary use cases
    unique_value_proposition: Optional[str]  # What makes it different
    target_audience: List[str]  # Who it's for
    
    # Team and organization
    team_members: List[Dict[str, str]]  # [{"name": "...", "role": "...", "background": "..."}]
    founders: List[str]  # Founder names
    team_size_estimate: Optional[int]  # Estimated team size
    advisors: List[str]  # Advisor names
    
    # Business information
    partnerships: List[str]  # Strategic partnerships
    investors: List[str]  # Investment firms/angels
    funding_raised: Optional[str]  # Funding information if mentioned
    
    # Development and innovation
    innovations: List[str]  # Novel approaches or features
    development_stage: str  # "concept", "development", "testnet", "mainnet", "mature"
    roadmap_items: List[str]  # Key roadmap milestones
    
    # Analysis metadata
    technical_depth_score: int  # 1-10, how technically detailed is the content
    marketing_vs_tech_ratio: float  # 0-1, 0=all marketing, 1=all technical
    content_quality_score: int  # 1-10, overall content quality
    red_flags: List[str]  # Potential concerns or warning signs
    confidence_score: float  # 0-1, how confident is the analysis
    
    # Processing info
    pages_analyzed: int
    total_word_count: int
    analysis_timestamp: datetime
    model_used: str


class WebsiteContentAnalyzer:
    """LLM-powered website content analyzer for cryptocurrency projects."""
    
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
        """Build the comprehensive analysis prompt."""
        return """
You are a blockchain and cryptocurrency analyst. Analyze the provided website content for a cryptocurrency/blockchain project and extract structured information.

Please analyze the content and provide a JSON response with the following structure:

{
    "technology_stack": ["list of technologies mentioned", "programming languages", "frameworks"],
    "blockchain_platform": "main blockchain platform if specified (e.g., Ethereum, Solana, etc.)",
    "consensus_mechanism": "consensus mechanism if mentioned (e.g., Proof of Stake, Proof of Work)",
    "core_features": ["main features", "key capabilities", "product offerings"],
    "use_cases": ["primary use cases", "target applications"],
    "unique_value_proposition": "what makes this project unique in 1-2 sentences",
    "target_audience": ["who this is for", "target market segments"],
    "team_members": [{"name": "Full Name", "role": "Position", "background": "Brief background"}],
    "founders": ["founder names"],
    "team_size_estimate": estimated_number_of_team_members,
    "advisors": ["advisor names"],
    "partnerships": ["strategic partnerships", "integrations", "collaborations"],
    "investors": ["investment firms", "VCs", "angel investors"],
    "funding_raised": "funding information if mentioned",
    "innovations": ["novel approaches", "unique technical features", "breakthrough innovations"],
    "development_stage": "one of: concept, development, testnet, mainnet, mature",
    "roadmap_items": ["key roadmap milestones", "future plans"],
    "technical_depth_score": score_1_to_10_for_technical_detail,
    "marketing_vs_tech_ratio": ratio_0_to_1_where_0_is_all_marketing_1_is_all_technical,
    "content_quality_score": score_1_to_10_for_overall_content_quality,
    "red_flags": ["potential concerns", "warning signs", "questionable claims"],
    "confidence_score": confidence_0_to_1_in_this_analysis
}

Guidelines:
1. Be conservative - only include information that's clearly stated or strongly implied
2. For team members, only include those with names and roles clearly mentioned
3. Look for technical depth vs marketing fluff
4. Identify any red flags like vague claims, plagiarism, unrealistic promises
5. Rate technical depth based on specificity of technical information
6. Rate content quality based on clarity, detail, and professionalism
7. If information isn't available, use null or empty arrays as appropriate
8. Development stage assessment: concept (just ideas), development (building), testnet (testing), mainnet (live but new), mature (established)

Content to analyze:
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
                    {"role": "system", "content": "You are a blockchain and cryptocurrency analyst. Always respond with valid JSON only."},
                    {"role": "user", "content": self.analysis_prompt + "\n\n" + content}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            response_text = response.choices[0].message.content
            
            # Try to parse as JSON
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
        """Make API call to Ollama server."""
        try:
            # Prepare the request payload
            payload = {
                "model": self.model,
                "prompt": self.analysis_prompt + "\n\n" + content,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": 2000
                }
            }
            
            logger.debug(f"Making Ollama API call with model {self.model}")
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json=payload,
                timeout=120  # Longer timeout for local processing
            )
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get('response', '')
            
            # Try to parse the JSON response
            if response_text.strip():
                # Sometimes the model wraps JSON in markdown code blocks
                if '```json' in response_text:
                    start_idx = response_text.find('```json') + 7
                    end_idx = response_text.find('```', start_idx)
                    response_text = response_text[start_idx:end_idx]
                elif '```' in response_text:
                    start_idx = response_text.find('```') + 3
                    end_idx = response_text.rfind('```')
                    response_text = response_text[start_idx:end_idx]
                
                # Find JSON in the response
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    return json_lib.loads(json_str)
                else:
                    logger.error("No JSON found in Ollama response")
                    return None
            else:
                logger.error("Empty response from Ollama")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API request failed: {e}")
            return None
        except json_lib.JSONDecodeError as e:
            logger.error(f"Failed to parse Ollama response as JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            return None
    
    def _combine_page_contents(self, pages: List[Any]) -> str:
        """Combine content from multiple pages into analysis text."""
        combined_content = []
        
        for page in pages:
            page_header = f"\n=== {page.page_type.upper()} PAGE: {page.title} ===\n"
            combined_content.append(page_header)
            combined_content.append(page.content[:3000])  # Limit per page to control token usage
        
        full_content = "\n".join(combined_content)
        
        # Ensure we don't exceed token limits (roughly 12,000 characters for 3K tokens)
        if len(full_content) > 12000:
            full_content = full_content[:12000] + "\n[Content truncated for analysis]"
        
        return full_content
    
    def analyze_website(self, scraped_pages: List[Any], domain: str) -> Optional[WebsiteAnalysis]:
        """
        Analyze website content and return structured analysis.
        
        Args:
            scraped_pages: List of ScrapedPage objects
            domain: Domain name for context
            
        Returns:
            WebsiteAnalysis object or None if analysis failed
        """
        if not scraped_pages:
            logger.error("No pages provided for analysis")
            return None
        
        logger.info(f"Starting LLM analysis of {len(scraped_pages)} pages for {domain}")
        
        # Combine page contents
        combined_content = self._combine_page_contents(scraped_pages)
        total_word_count = len(combined_content.split())
        
        logger.debug(f"Combined content: {len(combined_content)} characters, ~{total_word_count} words")
        
        # Make LLM API call
        if self.provider == "anthropic":
            raw_analysis = self._call_anthropic(combined_content)
        elif self.provider == "openai":
            raw_analysis = self._call_openai(combined_content)
        elif self.provider == "ollama":
            raw_analysis = self._call_ollama(combined_content)
        else:
            logger.error(f"Unsupported provider: {self.provider}")
            return None
        
        if not raw_analysis:
            logger.error("LLM analysis failed")
            return None
        
        try:
            # Create WebsiteAnalysis object from the response
            analysis = WebsiteAnalysis(
                technology_stack=raw_analysis.get('technology_stack', []),
                blockchain_platform=raw_analysis.get('blockchain_platform'),
                consensus_mechanism=raw_analysis.get('consensus_mechanism'),
                core_features=raw_analysis.get('core_features', []),
                use_cases=raw_analysis.get('use_cases', []),
                unique_value_proposition=raw_analysis.get('unique_value_proposition'),
                target_audience=raw_analysis.get('target_audience', []),
                team_members=raw_analysis.get('team_members', []),
                founders=raw_analysis.get('founders', []),
                team_size_estimate=raw_analysis.get('team_size_estimate'),
                advisors=raw_analysis.get('advisors', []),
                partnerships=raw_analysis.get('partnerships', []),
                investors=raw_analysis.get('investors', []),
                funding_raised=raw_analysis.get('funding_raised'),
                innovations=raw_analysis.get('innovations', []),
                development_stage=raw_analysis.get('development_stage', 'unknown'),
                roadmap_items=raw_analysis.get('roadmap_items', []),
                technical_depth_score=raw_analysis.get('technical_depth_score', 5),
                marketing_vs_tech_ratio=raw_analysis.get('marketing_vs_tech_ratio', 0.5),
                content_quality_score=raw_analysis.get('content_quality_score', 5),
                red_flags=raw_analysis.get('red_flags', []),
                confidence_score=raw_analysis.get('confidence_score', 0.5),
                pages_analyzed=len(scraped_pages),
                total_word_count=total_word_count,
                analysis_timestamp=datetime.now(UTC),
                model_used=self.model
            )
            
            logger.success(f"Analysis complete for {domain} - Technical depth: {analysis.technical_depth_score}/10, Quality: {analysis.content_quality_score}/10")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to create WebsiteAnalysis object: {e}")
            logger.debug(f"Raw analysis data: {raw_analysis}")
            return None
    
    def batch_analyze_websites(self, website_data: List[Dict]) -> List[Optional[WebsiteAnalysis]]:
        """
        Analyze multiple websites in batch with rate limiting.
        
        Args:
            website_data: List of dicts with 'domain' and 'scraped_pages' keys
            
        Returns:
            List of WebsiteAnalysis objects (some may be None for failed analyses)
        """
        results = []
        
        for i, data in enumerate(website_data):
            domain = data['domain']
            pages = data['scraped_pages']
            
            logger.info(f"Batch analysis {i+1}/{len(website_data)}: {domain}")
            
            analysis = self.analyze_website(pages, domain)
            results.append(analysis)
            
            # Rate limiting between API calls
            if i < len(website_data) - 1:  # Don't sleep after the last item
                time.sleep(1)  # 1 second between calls
        
        successful_analyses = len([r for r in results if r is not None])
        logger.info(f"Batch analysis complete: {successful_analyses}/{len(website_data)} successful")
        
        return results


def main():
    """Test the website analyzer."""
    # This would typically be called with scraped page data
    analyzer = WebsiteContentAnalyzer(provider="ollama", model="llama3.1:latest")
    
    # Example test (would need actual scraped pages)
    print("Website Content Analyzer initialized successfully!")
    print(f"Provider: {analyzer.provider}")
    print(f"Model: {analyzer.model}")
    
    # Test prompt building
    print("\nSample analysis prompt:")
    print(analyzer.analysis_prompt[:500] + "...")


if __name__ == "__main__":
    main()