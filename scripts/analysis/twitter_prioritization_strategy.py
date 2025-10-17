#!/usr/bin/env python3
"""
Twitter Link Prioritization Strategy

This script creates a prioritization algorithm for Twitter account analysis
given the 100 API calls/month limitation on the free tier.

Strategy:
1. Tier 1 (40 calls): Top 50 by market cap with Twitter links
2. Tier 2 (25 calls): Rank 51-200 with high analysis scores 
3. Tier 3 (20 calls): Promising smaller projects
4. Tier 4 (15 calls): Buffer for re-analysis and new projects
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths, get_config_path

# Set up project paths
project_root = setup_project_paths()

from src.models.database import DatabaseManager
from dotenv import load_dotenv
from sqlalchemy import text, and_, or_

# Load environment variables
load_dotenv(get_config_path() / ".env")


class PriorityTier(Enum):
    TIER_1_TOP_MARKET_CAP = 1      # Top market cap projects
    TIER_2_HIGH_QUALITY = 2        # High-quality mid-tier projects  
    TIER_3_PROMISING = 3           # Smaller but promising projects
    TIER_4_BUFFER = 4              # Buffer for re-analysis


@dataclass
class TwitterPriorityProject:
    """Project prioritized for Twitter analysis."""
    project_id: int
    project_name: str
    project_code: str
    twitter_link_id: int
    twitter_url: str
    priority_tier: PriorityTier
    priority_score: float
    selection_reason: str
    
    # Key metrics for prioritization
    market_cap: float = None
    rank: int = None
    has_website_analysis: bool = False
    website_quality_score: float = None
    
    
class TwitterPrioritizationStrategy:
    """Strategy for prioritizing Twitter accounts for analysis."""
    
    def __init__(self, database_url: str):
        self.db_manager = DatabaseManager(database_url)
        self.monthly_api_limit = 100
        
        # Allocation by tier
        self.tier_allocations = {
            PriorityTier.TIER_1_TOP_MARKET_CAP: 40,
            PriorityTier.TIER_2_HIGH_QUALITY: 25,
            PriorityTier.TIER_3_PROMISING: 20,
            PriorityTier.TIER_4_BUFFER: 15
        }
        
    def get_unanalyzed_twitter_projects(self) -> List[Dict]:
        """Get all projects with Twitter links that haven't been analyzed."""
        
        with self.db_manager.get_session() as session:
            query = text("""
                SELECT DISTINCT
                    cp.id as project_id,
                    cp.name as project_name,
                    cp.code as project_code,
                    cp.rank,
                    cp.market_cap,
                    cp.current_price,
                    cp.volume_24h,
                    pl.id as twitter_link_id,
                    pl.url as twitter_url,
                    pl.created_at as link_created_at,
                    -- Check if we have website analysis
                    CASE 
                        WHEN wl.id IS NOT NULL THEN 1 
                        ELSE 0 
                    END as has_website_analysis,
                    wlca.technical_depth_score,
                    wlca.content_quality_score,
                    wlca.confidence_score as website_confidence
                FROM crypto_projects cp
                JOIN project_links pl ON cp.id = pl.project_id
                LEFT JOIN project_links wl ON cp.id = wl.project_id AND wl.link_type = 'website'
                LEFT JOIN link_content_analysis wlca ON wl.id = wlca.link_id
                WHERE pl.link_type = 'twitter'
                    AND pl.url IS NOT NULL
                    AND pl.url != ''
                    -- Exclude already analyzed Twitter accounts
                    AND NOT EXISTS (
                        SELECT 1 FROM link_content_analysis lca 
                        WHERE lca.link_id = pl.id
                    )
                ORDER BY cp.market_cap DESC NULLS LAST, cp.rank ASC NULLS LAST
            """)
            
            results = session.execute(query).fetchall()
            
            return [dict(row._mapping) for row in results]
    
    def calculate_priority_score(self, project: Dict) -> float:
        """Calculate priority score for a project."""
        score = 0.0
        
        # Market cap component (40% weight)
        if project['market_cap']:
            # Normalize market cap to 0-100 scale (log scale)
            import math
            market_cap_score = min(100, math.log10(max(1, project['market_cap'])) * 10)
            score += market_cap_score * 0.4
        
        # Rank component (30% weight) - lower rank = higher score
        if project['rank']:
            rank_score = max(0, 100 - (project['rank'] / 10))  # Top 10 = 99, rank 1000 = 0
            score += rank_score * 0.3
        
        # Website analysis quality component (20% weight)
        if project['has_website_analysis'] and project['content_quality_score']:
            website_score = min(100, project['content_quality_score'] * 10)  # Scale to 0-100
            score += website_score * 0.2
        
        # Volume component (10% weight) - indicates active trading
        if project['volume_24h']:
            import math
            volume_score = min(100, math.log10(max(1, project['volume_24h'])) * 10)
            score += volume_score * 0.1
            
        return score
    
    def assign_priority_tier(self, project: Dict, priority_score: float, tier_counts: Dict) -> Tuple[PriorityTier, str]:
        """Assign priority tier to a project."""
        
        # Tier 1: Top market cap projects
        if (project['market_cap'] and project['market_cap'] > 1000000000 and  # $1B+ market cap
            tier_counts[PriorityTier.TIER_1_TOP_MARKET_CAP] < self.tier_allocations[PriorityTier.TIER_1_TOP_MARKET_CAP]):
            return PriorityTier.TIER_1_TOP_MARKET_CAP, "Large market cap ($1B+)"
        
        # Tier 1: Top ranked projects (even if smaller market cap)
        if (project['rank'] and project['rank'] <= 100 and
            tier_counts[PriorityTier.TIER_1_TOP_MARKET_CAP] < self.tier_allocations[PriorityTier.TIER_1_TOP_MARKET_CAP]):
            return PriorityTier.TIER_1_TOP_MARKET_CAP, "Top 100 ranked"
            
        # Tier 2: High-quality projects with good website analysis
        if (project['has_website_analysis'] and project['content_quality_score'] and
            project['content_quality_score'] >= 7.0 and  # High quality website content
            tier_counts[PriorityTier.TIER_2_HIGH_QUALITY] < self.tier_allocations[PriorityTier.TIER_2_HIGH_QUALITY]):
            return PriorityTier.TIER_2_HIGH_QUALITY, f"High website quality ({project['content_quality_score']:.1f})"
        
        # Tier 2: Mid-tier ranked projects
        if (project['rank'] and 101 <= project['rank'] <= 500 and
            tier_counts[PriorityTier.TIER_2_HIGH_QUALITY] < self.tier_allocations[PriorityTier.TIER_2_HIGH_QUALITY]):
            return PriorityTier.TIER_2_HIGH_QUALITY, f"Mid-tier ranked ({project['rank']})"
        
        # Tier 3: Smaller projects with decent metrics
        if (priority_score >= 50 and  # Decent overall score
            tier_counts[PriorityTier.TIER_3_PROMISING] < self.tier_allocations[PriorityTier.TIER_3_PROMISING]):
            return PriorityTier.TIER_3_PROMISING, f"Good metrics (score: {priority_score:.1f})"
        
        # Tier 4: Everything else goes to buffer
        if tier_counts[PriorityTier.TIER_4_BUFFER] < self.tier_allocations[PriorityTier.TIER_4_BUFFER]:
            return PriorityTier.TIER_4_BUFFER, "Buffer allocation"
            
        # If all tiers are full, don't prioritize
        return None, "All tiers full"
    
    def create_priority_list(self) -> List[TwitterPriorityProject]:
        """Create prioritized list of Twitter accounts for analysis."""
        
        print("🔍 Analyzing Twitter links for prioritization...")
        
        # Get all unanalyzed Twitter projects
        projects = self.get_unanalyzed_twitter_projects()
        print(f"📊 Found {len(projects)} projects with unanalyzed Twitter accounts")
        
        if not projects:
            print("✅ All Twitter accounts have been analyzed!")
            return []
        
        # Calculate priority scores
        for project in projects:
            project['priority_score'] = self.calculate_priority_score(project)
        
        # Sort by priority score (highest first)
        projects.sort(key=lambda x: x['priority_score'], reverse=True)
        
        # Assign tiers
        tier_counts = {tier: 0 for tier in PriorityTier}
        priority_projects = []
        
        for project in projects:
            tier, reason = self.assign_priority_tier(project, project['priority_score'], tier_counts)
            
            if tier is None:
                continue  # Skip if all tiers are full
                
            priority_project = TwitterPriorityProject(
                project_id=project['project_id'],
                project_name=project['project_name'],
                project_code=project['project_code'],
                twitter_link_id=project['twitter_link_id'],
                twitter_url=project['twitter_url'],
                priority_tier=tier,
                priority_score=project['priority_score'],
                selection_reason=reason,
                market_cap=project['market_cap'],
                rank=project['rank'],
                has_website_analysis=bool(project['has_website_analysis']),
                website_quality_score=project['content_quality_score']
            )
            
            priority_projects.append(priority_project)
            tier_counts[tier] += 1
            
            # Stop when we've allocated our monthly limit
            if len(priority_projects) >= self.monthly_api_limit:
                break
        
        return priority_projects
    
    def display_priority_summary(self, priority_projects: List[TwitterPriorityProject]):
        """Display summary of prioritization strategy."""
        
        print(f"\n{'='*60}")
        print("🎯 TWITTER ANALYSIS PRIORITY LIST")
        print(f"{'='*60}")
        print(f"📅 Monthly API Limit: {self.monthly_api_limit} calls")
        print(f"📋 Projects Selected: {len(priority_projects)}")
        
        # Summary by tier
        tier_summary = {}
        for tier in PriorityTier:
            count = len([p for p in priority_projects if p.priority_tier == tier])
            allocated = self.tier_allocations[tier]
            tier_summary[tier] = {'count': count, 'allocated': allocated}
        
        print(f"\n📊 TIER ALLOCATION:")
        for tier, data in tier_summary.items():
            tier_name = tier.name.replace('_', ' ').title()
            print(f"  {tier_name}: {data['count']}/{data['allocated']} slots used")
        
        # Top projects by tier
        print(f"\n🏆 TOP PRIORITIES BY TIER:")
        
        for tier in [PriorityTier.TIER_1_TOP_MARKET_CAP, PriorityTier.TIER_2_HIGH_QUALITY, 
                     PriorityTier.TIER_3_PROMISING]:
            tier_projects = [p for p in priority_projects if p.priority_tier == tier][:5]
            if tier_projects:
                tier_name = tier.name.replace('_', ' ').title()
                print(f"\n  {tier_name}:")
                for i, project in enumerate(tier_projects[:5], 1):
                    market_cap_str = f"${project.market_cap/1e9:.1f}B" if project.market_cap else "N/A"
                    rank_str = f"#{project.rank}" if project.rank else "N/A"
                    print(f"    {i}. {project.project_name} ({project.project_code})")
                    print(f"       Rank: {rank_str} | Market Cap: {market_cap_str} | Score: {project.priority_score:.1f}")
                    print(f"       Reason: {project.selection_reason}")
        
        print(f"\n✅ Priority list complete! Ready for Twitter API analysis.")
        
    def save_priority_list(self, priority_projects: List[TwitterPriorityProject], output_file: str = None):
        """Save priority list to file for batch processing."""
        
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"twitter_priority_list_{timestamp}.json"
        
        import json
        
        # Convert to serializable format
        priority_data = []
        for project in priority_projects:
            priority_data.append({
                'project_id': project.project_id,
                'project_name': project.project_name,
                'project_code': project.project_code,
                'twitter_link_id': project.twitter_link_id,
                'twitter_url': project.twitter_url,
                'priority_tier': project.priority_tier.value,
                'priority_score': project.priority_score,
                'selection_reason': project.selection_reason,
                'market_cap': project.market_cap,
                'rank': project.rank,
                'has_website_analysis': project.has_website_analysis,
                'website_quality_score': project.website_quality_score
            })
        
        output_path = Path(__file__).parent / output_file
        with open(output_path, 'w') as f:
            json.dump({
                'created_at': datetime.now().isoformat(),
                'monthly_limit': self.monthly_api_limit,
                'projects_selected': len(priority_projects),
                'tier_allocations': {tier.name: allocation for tier, allocation in self.tier_allocations.items()},
                'priority_projects': priority_data
            }, f, indent=2)
        
        print(f"💾 Priority list saved to: {output_path}")
        return output_path


def main():
    """Generate Twitter analysis priority list."""
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    
    print("🚀 Twitter Prioritization Strategy")
    print(f"Database: {database_url}")
    
    strategy = TwitterPrioritizationStrategy(database_url)
    
    # Create priority list
    priority_projects = strategy.create_priority_list()
    
    if priority_projects:
        # Display summary
        strategy.display_priority_summary(priority_projects)
        
        # Save to file
        strategy.save_priority_list(priority_projects)
        
        print(f"\n🎯 Next Steps:")
        print("1. Set up Twitter API credentials")
        print("2. Implement Twitter API client")
        print("3. Run batch analysis using this priority list")
        print("4. Monitor API usage to stay within 100 calls/month")
        
    else:
        print("ℹ️  No Twitter accounts need analysis at this time.")


if __name__ == "__main__":
    main()