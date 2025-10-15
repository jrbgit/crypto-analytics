"""
LiveCoinWatch API data collector with rate limiting and change tracking.
"""

import os
import time
import json
import hashlib
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger
from dotenv import load_dotenv

# Import our database models
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.database import (
    DatabaseManager, CryptoProject, ProjectLink, ProjectImage, 
    ProjectChange, APIUsage
)


@dataclass
class RateLimit:
    """Rate limiting configuration."""
    requests_per_minute: int = 60
    daily_limit: int = 10000
    current_usage: int = 0
    last_reset: datetime = datetime.now(UTC)


class LiveCoinWatchClient:
    """Client for LiveCoinWatch API with comprehensive data collection."""
    
    BASE_URL = "https://api.livecoinwatch.com"
    
    def __init__(self, api_key: str, database_manager: DatabaseManager):
        self.api_key = api_key
        self.db_manager = database_manager
        self.rate_limit = RateLimit()
        
        # Setup HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Default headers
        self.session.headers.update({
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'CryptoAnalytics/1.0'
        })
        
        logger.info("LiveCoinWatch client initialized")
    
    def _check_rate_limit(self) -> bool:
        """Check if we can make a request within rate limits."""
        now = datetime.now(UTC)
        
        # Reset daily counter if it's a new day
        if now.date() > self.rate_limit.last_reset.date():
            self.rate_limit.current_usage = 0
            self.rate_limit.last_reset = now
            logger.info("Daily rate limit reset")
        
        # Check daily limit
        if self.rate_limit.current_usage >= self.rate_limit.daily_limit:
            logger.error("Daily rate limit exceeded")
            return False
            
        return True
    
    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limits."""
        # Simple rate limiting - wait 1 second between requests
        time.sleep(1)
    
    def _make_request(self, endpoint: str, payload: Dict) -> Optional[Dict]:
        """Make a request to the API with error handling and logging."""
        
        if not self._check_rate_limit():
            return None
        
        self._wait_for_rate_limit()
        
        url = f"{self.BASE_URL}{endpoint}"
        start_time = time.time()
        
        try:
            logger.debug(f"Making request to {endpoint}")
            response = self.session.post(url, json=payload, timeout=30)
            response_time = time.time() - start_time
            
            # Log API usage
            with self.db_manager.get_session() as session:
                self.db_manager.log_api_usage(
                    session=session,
                    provider='livecoinwatch',
                    endpoint=endpoint,
                    status=response.status_code,
                    response_size=len(response.content),
                    response_time=response_time
                )
                session.commit()
            
            self.rate_limit.current_usage += 1
            
            if response.status_code == 200:
                logger.success(f"Request successful: {endpoint}")
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limit hit, backing off")
                time.sleep(60)  # Wait 1 minute
                return None
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def get_coins_list(self, limit: int = 100, offset: int = 0, 
                      currency: str = "USD", sort: str = "rank") -> Optional[List[Dict]]:
        """Get list of cryptocurrencies with metadata."""
        
        payload = {
            "currency": currency,
            "sort": sort,
            "order": "ascending",
            "offset": offset,
            "limit": limit,
            "meta": True  # Include metadata like links
        }
        
        response = self._make_request("/coins/list", payload)
        if response:
            # Handle both dictionary and list responses
            if isinstance(response, dict):
                return response.get('data', [])
            elif isinstance(response, list):
                return response
        return None
    
    def get_single_coin(self, code: str, currency: str = "USD") -> Optional[Dict]:
        """Get detailed data for a single cryptocurrency."""
        
        payload = {
            "currency": currency,
            "code": code,
            "meta": True
        }
        
        response = self._make_request("/coins/single", payload)
        return response if response else None
    
    def _sanitize_string_value(self, value, max_length: int, field_name: str = "field"):
        """Sanitize string values to prevent PostgreSQL string truncation.
        
        Truncates strings that exceed the maximum allowed length.
        """
        if value is None:
            return None
            
        try:
            # Convert to string if it's not already
            str_value = str(value)
            
            # Check if the string exceeds the maximum length
            if len(str_value) > max_length:
                logger.warning(f"String value '{str_value[:50]}...' for {field_name} exceeds {max_length} chars, truncating")
                return str_value[:max_length]
            
            return str_value
            
        except Exception as e:
            logger.warning(f"Error processing string value {value} for {field_name}: {e}")
            return None
    
    def _sanitize_numeric_value(self, value, field_name: str = "field"):
        """Sanitize numeric values to prevent PostgreSQL overflow.
        
        Different fields have different precision limits:
        - current_price, ath_usd: NUMERIC(50,20) - up to ~10^30
        - total_supply, max_supply: NUMERIC(80,8) - up to ~10^72 
        - Other fields: NUMERIC(40,8) - up to ~10^32
        """
        if value is None:
            return None
            
        try:
            # Convert to float if it's not already
            if isinstance(value, str):
                value = float(value)
            
            # Define precision limits for different field types
            if field_name in ['current_price', 'ath_usd']:
                # NUMERIC(50,20) - can handle values up to ~10^30
                max_value = 9.9999999e29
                precision_limit = 1e-20
                precision_desc = "NUMERIC(50,20)"
            elif field_name in ['total_supply', 'max_supply']:
                # NUMERIC(80,8) - can handle values up to ~10^72
                max_value = 9.9999999e71
                precision_limit = 1e-8
                precision_desc = "NUMERIC(80,8)"
            else:
                # NUMERIC(40,8) - can handle values up to ~10^32
                max_value = 9.9999999e31
                precision_limit = 1e-8
                precision_desc = "NUMERIC(40,8)"
            
            # Check for values exceeding the maximum
            if abs(value) >= max_value:
                logger.warning(f"Value {value} for {field_name} exceeds database limits ({precision_desc}), setting to None")
                return None
            
            # Check for extremely small values (precision issues)
            if abs(value) > 0 and abs(value) < precision_limit:
                logger.debug(f"Very small value {value} for {field_name}, approaching {precision_desc} precision limits")
                # Still keep it, but note the potential precision loss
            
            return value
            
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(f"Error processing numeric value {value} for {field_name}: {e}")
            return None
    
    def process_coin_data(self, coin_data: Dict) -> CryptoProject:
        """Process API response data and update/create project in database."""
        
        with self.db_manager.get_session() as session:
            # Check if project exists
            existing_project = session.query(CryptoProject).filter_by(code=coin_data['code']).first()
            
            is_new_project = existing_project is None
            
            if existing_project:
                project = existing_project
                # Track changes for existing project
                self._track_changes(session, project, coin_data)
            else:
                # Create new project (no need to sanitize code anymore with larger database limit)
                project = CryptoProject(code=coin_data['code'])
                session.add(project)
                logger.info(f"Creating new project: {coin_data['name']} ({coin_data['code']})")
            
            # Update project data (sanitize string fields)
            project.name = self._sanitize_string_value(coin_data.get('name'), 255, 'project_name')
            project.rank = coin_data.get('rank')
            project.age = coin_data.get('age')
            project.color = self._sanitize_string_value(coin_data.get('color'), 50, 'project_color')
            
            # Supply data (sanitize large values)
            project.circulating_supply = self._sanitize_numeric_value(coin_data.get('circulatingSupply'), 'circulating_supply')
            project.total_supply = self._sanitize_numeric_value(coin_data.get('totalSupply'), 'total_supply')
            project.max_supply = self._sanitize_numeric_value(coin_data.get('maxSupply'), 'max_supply')
            
            # Market data (sanitize large values)
            project.current_price = self._sanitize_numeric_value(coin_data.get('rate'), 'current_price')
            project.market_cap = self._sanitize_numeric_value(coin_data.get('cap'), 'market_cap')
            project.volume_24h = self._sanitize_numeric_value(coin_data.get('volume'), 'volume_24h')
            project.ath_usd = self._sanitize_numeric_value(coin_data.get('allTimeHighUSD'), 'ath_usd')
            
            # Price deltas (sanitize percentage values)
            delta = coin_data.get('delta', {})
            project.price_change_1h = self._sanitize_numeric_value(delta.get('hour'), 'price_change_1h')
            project.price_change_24h = self._sanitize_numeric_value(delta.get('day'), 'price_change_24h')
            project.price_change_7d = self._sanitize_numeric_value(delta.get('week'), 'price_change_7d')
            project.price_change_30d = self._sanitize_numeric_value(delta.get('month'), 'price_change_30d')
            project.price_change_90d = self._sanitize_numeric_value(delta.get('quarter'), 'price_change_90d')
            project.price_change_1y = self._sanitize_numeric_value(delta.get('year'), 'price_change_1y')
            
            # Exchange data
            project.exchanges_count = coin_data.get('exchanges')
            project.markets_count = coin_data.get('markets')
            project.pairs_count = coin_data.get('pairs')
            
            # Categories
            project.categories = coin_data.get('categories')
            project.last_api_fetch = datetime.now(UTC)
            
            # Flush to get the project ID before processing related data
            session.flush()
            
            # Track new project creation
            if is_new_project:
                self._track_new_project_creation(session, project, coin_data)
            
            # Process links
            self._process_links(session, project, coin_data.get('links', {}))
            
            # Process images
            self._process_images(session, project, coin_data)
            
            session.commit()
            logger.success(f"Updated project: {project.name}")
            
            return project
    
    def _track_changes(self, session, project: CryptoProject, new_data: Dict):
        """Track changes to project data."""
        
        # Define fields to track for changes
        field_mappings = {
            'rank': 'rank',
            'rate': 'current_price',
            'cap': 'market_cap',
            'volume': 'volume_24h',
            'circulatingSupply': 'circulating_supply',
            'totalSupply': 'total_supply',
            'maxSupply': 'max_supply',
            'exchanges': 'exchanges_count',
            'markets': 'markets_count',
            'pairs': 'pairs_count'
        }
        
        for api_field, db_field in field_mappings.items():
            old_value = getattr(project, db_field)
            new_value = new_data.get(api_field)
            
            if old_value != new_value and new_value is not None:
                self.db_manager.track_change(
                    session, project, db_field, old_value, new_value
                )
        
        # Track delta changes
        delta = new_data.get('delta', {})
        delta_mappings = {
            'hour': 'price_change_1h',
            'day': 'price_change_24h',
            'week': 'price_change_7d',
            'month': 'price_change_30d',
            'quarter': 'price_change_90d',
            'year': 'price_change_1y'
        }
        
        for delta_field, db_field in delta_mappings.items():
            old_value = getattr(project, db_field)
            new_value = delta.get(delta_field)
            
            if old_value != new_value and new_value is not None:
                self.db_manager.track_change(
                    session, project, db_field, old_value, new_value
                )
    
    def _track_new_project_creation(self, session, project: CryptoProject, coin_data: Dict):
        """Track the creation of a new cryptocurrency project."""
        
        # Log the project creation as an INSERT change
        self.db_manager.track_change(
            session=session,
            project=project,
            field_name='project_created',
            old_value=None,
            new_value=f"New cryptocurrency project: {coin_data.get('name', 'Unknown')} ({project.code})",
            change_type='INSERT'
        )
        
        # Optionally track key initial values as INSERT changes
        initial_fields = {
            'name': coin_data.get('name'),
            'rank': coin_data.get('rank'),
            'current_price': coin_data.get('rate'),
            'market_cap': coin_data.get('cap'),
            'volume_24h': coin_data.get('volume')
        }
        
        for field_name, value in initial_fields.items():
            if value is not None:
                self.db_manager.track_change(
                    session=session,
                    project=project,
                    field_name=field_name,
                    old_value=None,
                    new_value=value,
                    change_type='INSERT'
                )
    
    def _process_links(self, session, project: CryptoProject, links_data: Dict):
        """Process and update project links."""
        
        for link_type, url in links_data.items():
            if url:  # Skip null values
                # Check if link already exists
                existing_link = session.query(ProjectLink).filter_by(
                    project_id=project.id, 
                    link_type=link_type
                ).first()
                
                if existing_link:
                    if existing_link.url != url:
                        # URL changed, update and mark for re-analysis
                        existing_link.url = url
                        existing_link.needs_analysis = True
                        existing_link.updated_at = datetime.now(UTC)
                else:
                    # Create new link
                    new_link = ProjectLink(
                        project_id=project.id,
                        link_type=link_type,
                        url=url,
                        needs_analysis=True
                    )
                    session.add(new_link)
    
    def _process_images(self, session, project: CryptoProject, coin_data: Dict):
        """Process and update project images."""
        
        image_fields = ['png32', 'png64', 'webp32', 'webp64']
        
        for image_type in image_fields:
            url = coin_data.get(image_type)
            if url:
                # Check if image already exists
                existing_image = session.query(ProjectImage).filter_by(
                    project_id=project.id,
                    image_type=image_type
                ).first()
                
                if not existing_image:
                    new_image = ProjectImage(
                        project_id=project.id,
                        image_type=image_type,
                        url=url
                    )
                    session.add(new_image)
                elif existing_image.url != url:
                    existing_image.url = url
    
    def collect_top_coins(self, limit: int = 100) -> List[CryptoProject]:
        """Collect data for top coins by market cap."""
        
        logger.info(f"Starting collection of top {limit} coins")
        projects = []
        
        # Get coins in batches to stay within rate limits
        batch_size = 100  # LiveCoinWatch API limit
        for offset in range(0, limit, batch_size):
            current_batch_size = min(batch_size, limit - offset)
            
            logger.info(f"Fetching batch: {offset + 1} to {offset + current_batch_size}")
            
            coins_data = self.get_coins_list(
                limit=current_batch_size, 
                offset=offset
            )
            
            if not coins_data:
                logger.error(f"Failed to fetch batch at offset {offset}")
                break
            
            for coin_data in coins_data:
                try:
                    project = self.process_coin_data(coin_data)
                    projects.append(project)
                except Exception as e:
                    logger.error(f"Failed to process {coin_data.get('name', 'Unknown')}: {e}")
                    continue
            
            # Pause between batches
            time.sleep(2)
        
        logger.success(f"Collected data for {len(projects)} projects")
        return projects
    
    def collect_all_coins(self, max_coins: int = None, start_offset: int = 0) -> List[CryptoProject]:
        """Collect data for all available cryptocurrencies.
        
        Args:
            max_coins: Maximum number of coins to collect (None for all available)
            start_offset: Starting offset (useful for resuming interrupted collections)
        
        Returns:
            List of processed CryptoProject objects
        """
        
        logger.info(f"Starting collection of all available coins (starting from offset {start_offset})")
        projects = []
        batch_size = 100  # LiveCoinWatch API limit per request
        offset = start_offset
        consecutive_empty_batches = 0
        max_empty_batches = 3  # Stop after 3 consecutive empty batches
        
        while True:
            # Check rate limits before continuing
            stats = self.get_usage_stats()
            remaining = stats['remaining']
            
            if remaining <= 10:  # Keep some buffer
                logger.warning(f"Approaching daily rate limit. Only {remaining} requests remaining.")
                logger.info("Stopping collection to preserve rate limit for other operations.")
                break
            
            # Check if we've hit the max_coins limit
            if max_coins and len(projects) >= max_coins:
                logger.info(f"Reached maximum coin limit of {max_coins}")
                break
            
            # Calculate current batch size
            current_batch_size = batch_size
            if max_coins:
                remaining_coins = max_coins - len(projects)
                current_batch_size = min(batch_size, remaining_coins)
            
            logger.info(f"Fetching batch: {offset + 1} to {offset + current_batch_size} (Total collected: {len(projects)})")
            
            coins_data = self.get_coins_list(
                limit=current_batch_size,
                offset=offset
            )
            
            if not coins_data or len(coins_data) == 0:
                consecutive_empty_batches += 1
                logger.warning(f"Empty batch at offset {offset} (consecutive empty: {consecutive_empty_batches})")
                
                if consecutive_empty_batches >= max_empty_batches:
                    logger.info("Multiple consecutive empty batches. Assuming we've reached the end.")
                    break
                    
                # Skip ahead a bit in case of gaps
                offset += batch_size
                continue
            else:
                consecutive_empty_batches = 0  # Reset counter on successful batch
            
            # Process coins in current batch
            batch_processed = 0
            for coin_data in coins_data:
                try:
                    project = self.process_coin_data(coin_data)
                    projects.append(project)
                    batch_processed += 1
                except Exception as e:
                    logger.error(f"Failed to process {coin_data.get('name', 'Unknown')}: {e}")
                    continue
            
            logger.success(f"Processed {batch_processed}/{len(coins_data)} coins in batch")
            
            # Check if we got fewer results than requested (possible end of data)
            if len(coins_data) < current_batch_size:
                logger.info(f"Received {len(coins_data)} coins, less than requested {current_batch_size}. Likely at end of data.")
                break
            
            offset += len(coins_data)
            
            # Pause between batches to respect rate limits
            time.sleep(2)
            
            # Progress update every 10 batches
            if (offset // batch_size) % 10 == 0:
                current_stats = self.get_usage_stats()
                logger.info(f"Progress update: {len(projects)} coins collected, {current_stats['remaining']} API calls remaining")
        
        logger.success(f"Collection complete! Processed {len(projects)} total projects")
        return projects
    
    def get_usage_stats(self) -> Dict:
        """Get current API usage statistics."""
        
        with self.db_manager.get_session() as session:
            today = datetime.now(UTC).date()
            
            # Count today's usage
            today_usage = session.query(APIUsage).filter(
                APIUsage.api_provider == 'livecoinwatch',
                APIUsage.request_timestamp >= datetime.combine(today, datetime.min.time())
            ).count()
            
            return {
                'daily_limit': self.rate_limit.daily_limit,
                'today_usage': today_usage,
                'remaining': self.rate_limit.daily_limit - today_usage,
                'current_session_usage': self.rate_limit.current_usage,
                'last_reset': self.rate_limit.last_reset
            }


def main():
    """Main function for the collector with command line argument support."""
    
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LiveCoinWatch Data Collector')
    parser.add_argument('--all', action='store_true', 
                       help='Collect all available cryptocurrencies (default: top 100)')
    parser.add_argument('--limit', type=int, default=100,
                       help='Maximum number of coins to collect (default: 100)')
    parser.add_argument('--max-coins', type=int,
                       help='Maximum coins when using --all (overrides API limits)')
    parser.add_argument('--offset', type=int, default=0,
                       help='Starting offset for collection (useful for resuming)')
    
    args = parser.parse_args()
    
    # Load environment variables from the config directory
    config_path = Path(__file__).parent.parent.parent / "config" / "env"
    load_dotenv(config_path)
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    db_manager.create_tables()
    
    # Initialize API client
    api_key = os.getenv('LIVECOINWATCH_API_KEY')
    if not api_key:
        logger.error("LIVECOINWATCH_API_KEY environment variable not set")
        return
    
    client = LiveCoinWatchClient(api_key, db_manager)
    
    # Show current usage
    stats = client.get_usage_stats()
    logger.info(f"Usage stats: {stats}")
    
    if stats['remaining'] <= 10:
        logger.error(f"Insufficient API calls remaining: {stats['remaining']}")
        logger.info("Please wait until tomorrow or upgrade your API plan.")
        return
    
    # Collect data based on arguments
    if args.all:
        logger.info("Starting collection of ALL available cryptocurrencies")
        projects = client.collect_all_coins(
            max_coins=args.max_coins, 
            start_offset=args.offset
        )
    else:
        logger.info(f"Starting collection of top {args.limit} cryptocurrencies")
        projects = client.collect_top_coins(limit=args.limit)
    
    logger.info(f"Collection complete! Processed {len(projects)} projects")
    
    # Show final usage
    final_stats = client.get_usage_stats()
    logger.info(f"Final usage stats: {final_stats}")
    
    # Summary statistics
    if projects:
        logger.info(f"\n=== Collection Summary ===")
        logger.info(f"Total projects collected: {len(projects)}")
        logger.info(f"API calls used this session: {final_stats['current_session_usage']}")
        logger.info(f"API calls remaining today: {final_stats['remaining']}")
        
        # Show some sample data
        logger.info(f"\nSample projects collected:")
        for i, project in enumerate(projects[:5]):
            logger.info(f"  {i+1}. {project.name} ({project.code}) - Rank: {project.rank}")
        
        if len(projects) > 5:
            logger.info(f"  ... and {len(projects) - 5} more")


if __name__ == "__main__":
    main()