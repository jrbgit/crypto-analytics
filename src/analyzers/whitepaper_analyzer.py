"""
Whitepaper Content Analyzer using LLM

This module handles:
- LLM-based analysis of whitepaper content (PDF and webpage)
- Technical depth scoring and quality assessment
- Tokenomics analysis and use case viability
- Competitive analysis detection
- Red flag identification (plagiarism, vague claims)
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
class WhitepaperAnalysis:
    """Structured analysis result for a cryptocurrency whitepaper."""
    
    # Core technical assessment
    technical_depth_score: int  # 1-10, depth of technical detail
    content_quality_score: int  # 1-10, overall content quality
    document_structure_score: int  # 1-10, organization and clarity
    
    # Tokenomics and economics
    has_tokenomics: bool
    tokenomics_summary: Optional[str]
    token_distribution_described: bool
    economic_model_clarity: int  # 1-10, how clear the economic model is
    
    # Use case and value proposition
    use_cases_described: List[str]
    use_case_viability_score: int  # 1-10, how viable the use cases are
    target_market_defined: bool
    unique_value_proposition: Optional[str]
    
    # Technical innovation
    innovations_claimed: List[str]
    technical_innovations_score: int  # 1-10, novelty of technical approach
    implementation_details: int  # 1-10, level of implementation detail provided
    
    # Competitive analysis
    has_competitive_analysis: bool
    competitors_mentioned: List[str]
    competitive_advantages_claimed: List[str]
    
    # Team and development
    team_described: bool
    team_expertise_apparent: bool
    development_roadmap_present: bool
    roadmap_specificity: int  # 1-10, how specific the roadmap is
    
    # Risk and validation
    red_flags: List[str]
    plagiarism_indicators: List[str]
    vague_claims: List[str]
    unrealistic_promises: List[str]
    
    # Market and adoption
    market_size_analysis: bool
    adoption_strategy_described: bool
    partnerships_mentioned: List[str]
    
    # Document metadata
    document_type: str  # 'pdf' or 'webpage'
    word_count: int
    page_count: Optional[int]
    analysis_timestamp: datetime
    model_used: str
    confidence_score: float  # 0-1, confidence in the analysis


class WhitepaperContentAnalyzer:
    """LLM-powered whitepaper content analyzer for cryptocurrency projects."""
    
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
        """Build the comprehensive whitepaper analysis prompt."""
        return """
You are a cryptocurrency and blockchain analyst specializing in whitepaper analysis. Analyze the provided whitepaper content and provide a comprehensive structured assessment.

Please analyze the content and provide a JSON response with the following structure:

{
    "technical_depth_score": score_1_to_10_for_technical_depth,
    "content_quality_score": score_1_to_10_for_overall_quality,
    "document_structure_score": score_1_to_10_for_organization_and_clarity,
    
    "has_tokenomics": true_if_tokenomics_discussed,
    "tokenomics_summary": "brief summary of token economics if present",
    "token_distribution_described": true_if_token_distribution_explained,
    "economic_model_clarity": score_1_to_10_for_economic_model_clarity,
    
    "use_cases_described": ["list of use cases mentioned"],
    "use_case_viability_score": score_1_to_10_for_use_case_viability,
    "target_market_defined": true_if_target_market_clearly_defined,
    "unique_value_proposition": "what makes this project unique",
    
    "innovations_claimed": ["list of claimed innovations"],
    "technical_innovations_score": score_1_to_10_for_technical_novelty,
    "implementation_details": score_1_to_10_for_implementation_detail_level,
    
    "has_competitive_analysis": true_if_competitive_analysis_present,
    "competitors_mentioned": ["list of competitors mentioned"],
    "competitive_advantages_claimed": ["list of claimed advantages"],
    
    "team_described": true_if_team_information_provided,
    "team_expertise_apparent": true_if_team_expertise_is_evident,
    "development_roadmap_present": true_if_roadmap_included,
    "roadmap_specificity": score_1_to_10_for_roadmap_detail_level,
    
    "red_flags": ["potential concerns or warning signs"],
    "plagiarism_indicators": ["signs of copied content"],
    "vague_claims": ["vague or unsubstantiated claims"],
    "unrealistic_promises": ["promises that seem unrealistic"],
    
    "market_size_analysis": true_if_market_size_discussed,
    "adoption_strategy_described": true_if_adoption_strategy_present,
    "partnerships_mentioned": ["partnerships or collaborations mentioned"],
    
    "confidence_score": confidence_0_to_1_in_this_analysis
}

Analysis Guidelines:
1. Technical Depth (1-10): Rate based on specificity of technical details, algorithm descriptions, implementation specifics
2. Content Quality (1-10): Rate based on clarity, professionalism, comprehensiveness
3. Document Structure (1-10): Rate organization, flow, and presentation quality
4. Economic Model Clarity (1-10): How well the tokenomics and economic model are explained
5. Use Case Viability (1-10): How realistic and valuable the proposed use cases are
6. Technical Innovation (1-10): How novel and innovative the technical approach is
7. Implementation Details (1-10): Level of detail about how the system will be built
8. Roadmap Specificity (1-10): How detailed and specific the development roadmap is

Red Flags to Look For:
- Copied sections from other whitepapers
- Vague technical descriptions without specifics
- Unrealistic performance claims (e.g., "infinite scalability")
- No mention of known technical challenges
- Overly promotional language without substance
- Missing critical technical details
- Unrealistic timelines
- Claims without evidence or citations

Be conservative and objective in your analysis. Only include information that is clearly stated or strongly implied in the document.

Content to analyze:
"""

    def _call_anthropic(self, content: str) -> Dict[str, Any]:
        """Make API call to Anthropic."""
        try:
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=3000,
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
                max_tokens=3000,
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
                    "num_predict": 3000
                }
            }
            
            logger.debug(f"Making Ollama API call with model {self.model}")
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json=payload,
                timeout=180  # Longer timeout for whitepaper analysis
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
    
    def analyze_whitepaper(self, content: str, document_type: str, word_count: int, page_count: Optional[int] = None) -> Optional[WhitepaperAnalysis]:
        """
        Analyze whitepaper content and return structured analysis.
        
        Args:
            content: The whitepaper text content
            document_type: 'pdf' or 'webpage'
            word_count: Number of words in the content
            page_count: Number of pages (for PDFs)
            
        Returns:
            WhitepaperAnalysis object or None if analysis failed
        """
        if not content or not content.strip():
            logger.warning("No content provided for analysis - likely empty webpage or failed extraction")
            return None
        
        logger.info(f"Starting LLM analysis of {document_type} whitepaper ({word_count} words)")
        
        # Limit content size for API calls (roughly 15,000 characters for 4K tokens)
        if len(content) > 15000:
            content = content[:15000] + "\n[Content truncated for analysis]"
            logger.debug("Content truncated for LLM analysis")
        
        # Make LLM API call
        if self.provider == "anthropic":
            raw_analysis = self._call_anthropic(content)
        elif self.provider == "openai":
            raw_analysis = self._call_openai(content)
        elif self.provider == "ollama":
            raw_analysis = self._call_ollama(content)
        else:
            logger.error(f"Unsupported provider: {self.provider}")
            return None
        
        if not raw_analysis:
            logger.error("LLM analysis failed")
            return None
        
        try:
            # Create WhitepaperAnalysis object from the response
            analysis = WhitepaperAnalysis(
                technical_depth_score=raw_analysis.get('technical_depth_score', 5),
                content_quality_score=raw_analysis.get('content_quality_score', 5),
                document_structure_score=raw_analysis.get('document_structure_score', 5),
                
                has_tokenomics=raw_analysis.get('has_tokenomics', False),
                tokenomics_summary=raw_analysis.get('tokenomics_summary'),
                token_distribution_described=raw_analysis.get('token_distribution_described', False),
                economic_model_clarity=raw_analysis.get('economic_model_clarity', 5),
                
                use_cases_described=raw_analysis.get('use_cases_described', []),
                use_case_viability_score=raw_analysis.get('use_case_viability_score', 5),
                target_market_defined=raw_analysis.get('target_market_defined', False),
                unique_value_proposition=raw_analysis.get('unique_value_proposition'),
                
                innovations_claimed=raw_analysis.get('innovations_claimed', []),
                technical_innovations_score=raw_analysis.get('technical_innovations_score', 5),
                implementation_details=raw_analysis.get('implementation_details', 5),
                
                has_competitive_analysis=raw_analysis.get('has_competitive_analysis', False),
                competitors_mentioned=raw_analysis.get('competitors_mentioned', []),
                competitive_advantages_claimed=raw_analysis.get('competitive_advantages_claimed', []),
                
                team_described=raw_analysis.get('team_described', False),
                team_expertise_apparent=raw_analysis.get('team_expertise_apparent', False),
                development_roadmap_present=raw_analysis.get('development_roadmap_present', False),
                roadmap_specificity=raw_analysis.get('roadmap_specificity', 5),
                
                red_flags=raw_analysis.get('red_flags', []),
                plagiarism_indicators=raw_analysis.get('plagiarism_indicators', []),
                vague_claims=raw_analysis.get('vague_claims', []),
                unrealistic_promises=raw_analysis.get('unrealistic_promises', []),
                
                market_size_analysis=raw_analysis.get('market_size_analysis', False),
                adoption_strategy_described=raw_analysis.get('adoption_strategy_described', False),
                partnerships_mentioned=raw_analysis.get('partnerships_mentioned', []),
                
                document_type=document_type,
                word_count=word_count,
                page_count=page_count,
                analysis_timestamp=datetime.now(UTC),
                model_used=self.model,
                confidence_score=raw_analysis.get('confidence_score', 0.5)
            )
            
            logger.success(f"Whitepaper analysis complete - Technical depth: {analysis.technical_depth_score}/10, Quality: {analysis.content_quality_score}/10")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to create WhitepaperAnalysis object: {e}")
            logger.debug(f"Raw analysis data: {raw_analysis}")
            return None


def main():
    """Test the whitepaper analyzer."""
    analyzer = WhitepaperContentAnalyzer()
    
    # Test with sample content
    sample_content = """
    Bitcoin: A Peer-to-Peer Electronic Cash System
    
    Abstract: A purely peer-to-peer version of electronic cash would allow online payments to be sent directly from one party to another without going through a financial institution. Digital signatures provide part of the solution, but the main benefits are lost if a trusted third party is still required to prevent double-spending. We propose a solution to the double-spending problem using a peer-to-peer network.
    
    1. Introduction
    Commerce on the Internet has come to rely almost exclusively on financial institutions serving as trusted third parties to process electronic payments. While the system works well enough for most transactions, it still suffers from the inherent weaknesses of the trust based model.
    
    2. Transactions
    We define an electronic coin as a chain of digital signatures. Each owner transfers the coin to the next by digitally signing a hash of the previous transaction and the public key of the next owner and adding these to the end of the coin.
    """
    
    print("=== Testing Whitepaper Analyzer ===")
    result = analyzer.analyze_whitepaper(sample_content, 'pdf', len(sample_content.split()), 9)
    
    if result:
        print(f"Technical Depth: {result.technical_depth_score}/10")
        print(f"Content Quality: {result.content_quality_score}/10")
        print(f"Has Tokenomics: {result.has_tokenomics}")
        print(f"Use Cases: {result.use_cases_described}")
        print(f"Innovations: {result.innovations_claimed}")
        print(f"Red Flags: {result.red_flags}")
        print(f"Confidence: {result.confidence_score}")
    else:
        print("Analysis failed")


if __name__ == "__main__":
    main()