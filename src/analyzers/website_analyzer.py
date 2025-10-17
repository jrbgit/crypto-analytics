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
    
    def _call_ollama(self, content: str, max_retries: int = 3) -> Dict[str, Any]:
        """Make API call to Ollama server with retry logic and enhanced error handling."""
        
        for attempt in range(max_retries + 1):
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
                
                if attempt > 0:
                    logger.debug(f"Making Ollama API call attempt {attempt + 1}/{max_retries + 1} with model {self.model}")
                else:
                    logger.debug(f"Making Ollama API call with model {self.model}")
                    
                response = requests.post(
                    f"{self.ollama_base_url}/api/generate",
                    json=payload,
                    timeout=120 + (attempt * 30)  # Progressive timeout increase
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Check for Ollama-specific error responses
                if 'error' in result:
                    error_msg = result['error']
                    if 'model not found' in error_msg.lower():
                        logger.error(f"Ollama model '{self.model}' not found. Available models can be checked with 'ollama list'")
                        return None  # Don't retry for model not found
                    elif 'out of memory' in error_msg.lower() or 'resource' in error_msg.lower():
                        if attempt < max_retries:
                            wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                            logger.warning(f"Ollama resource error, retrying in {wait_time}s: {error_msg}")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"Ollama resource error after {max_retries + 1} attempts: {error_msg}")
                            return None
                    else:
                        logger.error(f"Ollama API error: {error_msg}")
                        return None
                
                response_text = result.get('response', '')
                
                # Enhanced JSON extraction with multiple strategies
                parsed_json = self._extract_json_from_response(response_text, "Ollama")
                if parsed_json:
                    if attempt > 0:
                        logger.info(f"Ollama API call succeeded on attempt {attempt + 1}")
                    return parsed_json
                else:
                    if attempt < max_retries:
                        logger.warning(f"Failed to parse JSON from Ollama response on attempt {attempt + 1}, retrying...")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        logger.error(f"Failed to parse valid JSON from Ollama after {max_retries + 1} attempts")
                        return None
                        
            except requests.exceptions.ConnectionError as e:
                if 'connection refused' in str(e).lower():
                    logger.error("Ollama server not running or not accessible. Please ensure Ollama is running on {self.ollama_base_url}")
                    return None  # Don't retry connection refused
                elif attempt < max_retries:
                    wait_time = (2 ** attempt) * 1
                    logger.warning(f"Ollama connection error on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Ollama connection failed after {max_retries + 1} attempts: {e}")
                    return None
                    
            except requests.exceptions.Timeout as e:
                if attempt < max_retries:
                    timeout_increase = (attempt + 1) * 30
                    logger.warning(f"Ollama API timeout on attempt {attempt + 1}, retrying with longer timeout (+{timeout_increase}s)")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    logger.error(f"Ollama API timeout after {max_retries + 1} attempts: {e}")
                    return None
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.error(f"Ollama API endpoint not found: {self.ollama_base_url}/api/generate")
                    return None  # Don't retry 404
                elif e.response.status_code == 500 and attempt < max_retries:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"Ollama server error 500 on attempt {attempt + 1}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Ollama HTTP error: {e}")
                    return None
                    
            except json_lib.JSONDecodeError as e:
                logger.error(f"Ollama returned invalid JSON response: {e}")
                return None  # Don't retry JSON decode errors from server response
                
            except Exception as e:
                if attempt < max_retries:
                    wait_time = (2 ** attempt) * 1
                    logger.warning(f"Unexpected Ollama error on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Ollama API call failed after {max_retries + 1} attempts: {e}")
                    return None
        
        return None
    
    def _extract_json_from_response(self, response_text: str, provider_name: str) -> Optional[Dict[str, Any]]:
        """Extract and parse JSON from LLM response with multiple strategies."""
        if not response_text.strip():
            logger.warning(f"{provider_name} returned empty response")
            return None
        
        # Strategy 1: Look for markdown code blocks
        if '```json' in response_text:
            start_idx = response_text.find('```json') + 7
            end_idx = response_text.find('```', start_idx)
            if end_idx > start_idx:
                json_str = response_text[start_idx:end_idx].strip()
            else:
                json_str = response_text[start_idx:].strip()
        elif '```' in response_text:
            start_idx = response_text.find('```') + 3
            end_idx = response_text.rfind('```')
            if end_idx > start_idx:
                json_str = response_text[start_idx:end_idx].strip()
            else:
                json_str = response_text[start_idx:].strip()
        else:
            json_str = response_text
        
        # Strategy 2: Find JSON object boundaries
        start_brace = json_str.find('{')
        if start_brace == -1:
            logger.warning(f"No opening brace found in {provider_name} response")
            return None
        
        # Find matching closing brace
        brace_count = 0
        end_brace = -1
        
        for i in range(start_brace, len(json_str)):
            if json_str[i] == '{':
                brace_count += 1
            elif json_str[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_brace = i
                    break
        
        if end_brace == -1:
            # Fallback: use the last closing brace
            end_brace = json_str.rfind('}')
            if end_brace == -1:
                logger.warning(f"No closing brace found in {provider_name} response")
                return None
        
        json_str = json_str[start_brace:end_brace + 1]
        
        # Strategy 3: Attempt to parse JSON with error handling
        try:
            parsed_json = json_lib.loads(json_str)
            
            # Validate that it's the expected structure
            if isinstance(parsed_json, dict):
                return parsed_json
            else:
                logger.warning(f"{provider_name} returned non-dict JSON: {type(parsed_json)}")
                return None
                
        except json_lib.JSONDecodeError as e:
            logger.warning(f"JSON decode error from {provider_name}: {e}")
            logger.debug(f"Attempted to parse: {json_str[:200]}...")
            
            # Strategy 4: Try to fix common JSON issues
            try:
                # Fix common issues: trailing commas, single quotes, etc.
                fixed_json = json_str.replace("'", '"')  # Single to double quotes
                fixed_json = self._fix_trailing_commas(fixed_json)
                
                parsed_json = json_lib.loads(fixed_json)
                logger.debug(f"Successfully parsed {provider_name} JSON after fixes")
                return parsed_json
                
            except json_lib.JSONDecodeError:
                logger.error(f"Failed to parse {provider_name} JSON even after fixes")
                return None
        
        return None
    
    def _fix_trailing_commas(self, json_str: str) -> str:
        """Fix trailing commas in JSON string."""
        # Simple regex-based fix for trailing commas
        import re
        # Remove trailing commas before closing brackets/braces
        fixed = re.sub(r',\s*([}\]])', r'\1', json_str)
        return fixed
    
    def _create_minimal_content_summary(self, pages: List[Any]) -> str:
        """Create a minimal content summary for fallback analysis."""
        summary_parts = []
        
        for page in pages:
            # Extract key information: title and first few sentences
            title = page.title or "Untitled Page"
            content_words = page.content.split()
            
            # Get first 100 words or so
            excerpt = ' '.join(content_words[:100]) if len(content_words) > 100 else page.content
            
            summary_parts.append(f"=== {page.page_type.upper()}: {title} ===\n{excerpt}")
        
        minimal_summary = "\n\n".join(summary_parts)
        
        # Ensure it's not too long even for minimal analysis
        if len(minimal_summary) > 3000:
            minimal_summary = minimal_summary[:3000] + "\n[Minimal content truncated]"
            
        return minimal_summary
    
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
        
        # Make LLM API call with fallback strategies
        raw_analysis = None
        primary_error = None
        
        if self.provider == "anthropic":
            raw_analysis = self._call_anthropic(combined_content)
        elif self.provider == "openai":
            raw_analysis = self._call_openai(combined_content)
        elif self.provider == "ollama":
            raw_analysis = self._call_ollama(combined_content)
        else:
            logger.error(f"Unsupported provider: {self.provider}")
            return None
        
        # If primary analysis failed, try fallback strategies
        if not raw_analysis:
            logger.warning(f"Primary LLM analysis failed for {domain}, attempting fallback strategies")
            
            # Fallback 1: Try with reduced content if it was too long
            if len(combined_content) > 8000:
                logger.info("Attempting analysis with reduced content length")
                reduced_content = combined_content[:8000] + "\n[Content truncated for analysis]"
                
                if self.provider == "ollama":
                    raw_analysis = self._call_ollama(reduced_content)
                elif self.provider == "anthropic":
                    raw_analysis = self._call_anthropic(reduced_content)
                elif self.provider == "openai":
                    raw_analysis = self._call_openai(reduced_content)
                    
                if raw_analysis:
                    logger.success(f"Fallback analysis with reduced content succeeded for {domain}")
            
            # Fallback 2: Try minimal analysis if still failed
            if not raw_analysis:
                logger.info("Attempting minimal content analysis")
                minimal_content = self._create_minimal_content_summary(scraped_pages)
                
                if self.provider == "ollama":
                    raw_analysis = self._call_ollama(minimal_content)
                elif self.provider == "anthropic":
                    raw_analysis = self._call_anthropic(minimal_content)
                elif self.provider == "openai":
                    raw_analysis = self._call_openai(minimal_content)
                    
                if raw_analysis:
                    logger.success(f"Minimal content analysis succeeded for {domain}")
        
        if not raw_analysis:
            logger.error(f"All LLM analysis strategies failed for {domain}")
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
                time.sleep(0.2)  # 0.2 seconds between calls
        
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