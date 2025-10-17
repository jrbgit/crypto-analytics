"""
Twitter Analysis Metrics for Cryptocurrency Projects

This module defines comprehensive metrics for evaluating Twitter accounts of crypto projects,
including scoring algorithms, red flags detection, and quality indicators.
"""

import math
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class TwitterHealthStatus(Enum):
    """Overall health status of a Twitter account."""
    EXCELLENT = "excellent"    # High-quality, trusted account
    GOOD = "good"             # Solid account with minor issues
    AVERAGE = "average"       # Decent but some concerns
    POOR = "poor"            # Multiple red flags
    SUSPICIOUS = "suspicious" # Likely fake or scam


@dataclass
class TwitterMetrics:
    """Core Twitter metrics for analysis."""
    
    # Basic account info
    username: str
    account_age_days: int
    verified: bool
    verified_type: Optional[str]
    protected: bool
    
    # Follower metrics
    followers_count: int
    following_count: int
    listed_count: int
    
    # Content metrics
    tweet_count: int
    tweets_per_day: float
    
    # Profile quality
    has_profile_image: bool
    has_bio: bool
    has_location: bool
    has_website_url: bool
    bio_length: int
    
    # Derived metrics (calculated)
    follower_following_ratio: float
    profile_completeness_score: int  # 0-10
    
    
@dataclass
class TwitterAnalysisResult:
    """Complete analysis result for a Twitter account."""
    
    # Input data
    metrics: TwitterMetrics
    
    # Calculated scores (0-10)
    authenticity_score: float      # How authentic/real the account appears
    engagement_quality_score: float # Quality of engagement patterns  
    professional_score: float     # How professional/legitimate it looks
    activity_score: float         # Account activity and recency
    community_score: float        # Community building indicators
    
    # Overall assessment
    overall_score: float          # Weighted average of all scores
    health_status: TwitterHealthStatus
    confidence_score: float       # 0-1, confidence in the analysis
    
    # Red flags and concerns
    red_flags: List[str]
    positive_indicators: List[str]
    
    # Analysis metadata
    analysis_timestamp: datetime
    analyst_version: str = "1.0"


class TwitterAnalysisMetrics:
    """Core class for analyzing Twitter accounts of crypto projects."""
    
    def __init__(self):
        self.version = "1.0"
        
        # Scoring weights for overall score calculation
        self.score_weights = {
            'authenticity': 0.30,    # Most important - is it real?
            'professional': 0.25,    # Professional appearance
            'community': 0.20,       # Community engagement
            'activity': 0.15,        # Recent activity
            'engagement_quality': 0.10  # Engagement patterns
        }
        
        # Define thresholds for various metrics
        self.thresholds = {
            'min_account_age_days': 180,        # 6 months minimum
            'min_followers_for_credibility': 1000,  # Minimum for serious project
            'max_following_ratio': 2.0,         # Following/followers ratio
            'min_tweets_for_activity': 50,      # Minimum tweet count
            'max_tweets_per_day': 20,           # Suspicious if too high
            'min_tweets_per_day': 0.1,          # Too inactive if too low
        }
    
    def analyze_account(self, profile_data: Dict) -> TwitterAnalysisResult:
        """Perform comprehensive analysis of a Twitter account."""
        
        # Extract and normalize metrics
        metrics = self._extract_metrics(profile_data)
        
        # Calculate individual scores
        authenticity_score = self._calculate_authenticity_score(metrics)
        engagement_quality_score = self._calculate_engagement_quality_score(metrics)
        professional_score = self._calculate_professional_score(metrics)
        activity_score = self._calculate_activity_score(metrics)
        community_score = self._calculate_community_score(metrics)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score({
            'authenticity': authenticity_score,
            'engagement_quality': engagement_quality_score,
            'professional': professional_score,
            'activity': activity_score,
            'community': community_score
        })
        
        # Determine health status
        health_status = self._determine_health_status(overall_score, metrics)
        
        # Identify red flags and positive indicators
        red_flags = self._identify_red_flags(metrics, profile_data)
        positive_indicators = self._identify_positive_indicators(metrics, profile_data)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(metrics, profile_data)
        
        return TwitterAnalysisResult(
            metrics=metrics,
            authenticity_score=authenticity_score,
            engagement_quality_score=engagement_quality_score,
            professional_score=professional_score,
            activity_score=activity_score,
            community_score=community_score,
            overall_score=overall_score,
            health_status=health_status,
            confidence_score=confidence_score,
            red_flags=red_flags,
            positive_indicators=positive_indicators,
            analysis_timestamp=datetime.now(timezone.utc)
        )
    
    def _extract_metrics(self, profile_data: Dict) -> TwitterMetrics:
        """Extract and normalize metrics from profile data."""
        
        # Handle different data formats
        followers_count = profile_data.get('followers_count', 0)
        following_count = profile_data.get('following_count', 0)
        
        # Calculate follower/following ratio
        if following_count > 0:
            follower_following_ratio = followers_count / following_count
        else:
            follower_following_ratio = followers_count if followers_count > 0 else 0
        
        # Bio analysis
        bio = profile_data.get('description', '') or ''
        bio_length = len(bio.strip())
        
        # Profile completeness
        completeness_score = 0
        if profile_data.get('name'): completeness_score += 1
        if bio_length > 10: completeness_score += 2  # Meaningful bio
        if profile_data.get('location'): completeness_score += 1
        if profile_data.get('url'): completeness_score += 2
        if profile_data.get('profile_image_url') and 'default' not in profile_data.get('profile_image_url', ''): completeness_score += 1
        if profile_data.get('verified'): completeness_score += 2
        if followers_count > 100: completeness_score += 1
        
        return TwitterMetrics(
            username=profile_data.get('username', '').lower(),
            account_age_days=profile_data.get('account_age_days', 0),
            verified=profile_data.get('verified', False),
            verified_type=profile_data.get('verified_type'),
            protected=profile_data.get('protected', False),
            followers_count=followers_count,
            following_count=following_count,
            listed_count=profile_data.get('listed_count', 0),
            tweet_count=profile_data.get('tweet_count', 0),
            tweets_per_day=profile_data.get('tweets_per_day', 0),
            has_profile_image=bool(profile_data.get('profile_image_url')),
            has_bio=bio_length > 0,
            has_location=bool(profile_data.get('location')),
            has_website_url=bool(profile_data.get('url')),
            bio_length=bio_length,
            follower_following_ratio=follower_following_ratio,
            profile_completeness_score=completeness_score
        )
    
    def _calculate_authenticity_score(self, metrics: TwitterMetrics) -> float:
        """Calculate how authentic/real the account appears (0-10)."""
        score = 5.0  # Start with neutral
        
        # Account age - older is more authentic
        if metrics.account_age_days >= self.thresholds['min_account_age_days']:
            score += 2.0
        elif metrics.account_age_days >= 90:  # 3 months
            score += 1.0
        elif metrics.account_age_days < 30:  # Very new account
            score -= 2.0
        
        # Verification status
        if metrics.verified:
            score += 2.0
        elif metrics.verified_type == 'blue':
            score += 1.5  # Paid verification, less valuable but still something
        
        # Follower/following ratio patterns
        if metrics.follower_following_ratio >= 1.0:
            score += 1.0  # More followers than following
        elif metrics.follower_following_ratio >= 0.1:
            score += 0.5  # Reasonable ratio
        else:
            score -= 1.0  # Following too many people
        
        # Suspicious following patterns
        if metrics.following_count > metrics.followers_count * 5:  # Following 5x more than followers
            score -= 2.0
        
        # Profile completeness indicates real effort
        if metrics.profile_completeness_score >= 7:
            score += 1.0
        elif metrics.profile_completeness_score <= 3:
            score -= 1.0
        
        # Tweet activity patterns
        if metrics.tweets_per_day > self.thresholds['max_tweets_per_day']:
            score -= 1.5  # Suspiciously active
        elif metrics.tweets_per_day < self.thresholds['min_tweets_per_day'] and metrics.account_age_days > 90:
            score -= 1.0  # Too inactive for an old account
        
        return max(0.0, min(10.0, score))
    
    def _calculate_engagement_quality_score(self, metrics: TwitterMetrics) -> float:
        """Calculate engagement quality score (0-10)."""
        score = 5.0
        
        # Listed count indicates people find the account valuable
        if metrics.followers_count > 0:
            listed_ratio = metrics.listed_count / metrics.followers_count
            if listed_ratio > 0.01:  # 1% listed ratio is excellent
                score += 2.0
            elif listed_ratio > 0.005:  # 0.5% is good
                score += 1.0
        
        # Reasonable follower count for credibility
        if metrics.followers_count >= self.thresholds['min_followers_for_credibility']:
            score += 1.5
        elif metrics.followers_count >= 500:
            score += 1.0
        elif metrics.followers_count < 100:
            score -= 1.0
        
        # Balanced following approach
        if 0.1 <= metrics.follower_following_ratio <= 10:
            score += 1.0
        else:
            score -= 0.5
        
        # Tweet frequency indicates engagement
        if 0.5 <= metrics.tweets_per_day <= 5:  # 1 tweet every 2 days to 5 per day
            score += 1.0
        elif metrics.tweets_per_day > 10:
            score -= 1.0  # Too much noise
        
        return max(0.0, min(10.0, score))
    
    def _calculate_professional_score(self, metrics: TwitterMetrics) -> float:
        """Calculate professional appearance score (0-10)."""
        score = 3.0  # Start lower for professional assessment
        
        # Profile completeness is crucial for professional appearance
        score += (metrics.profile_completeness_score / 10) * 3.0  # Up to 3 points
        
        # Having a website URL is professional
        if metrics.has_website_url:
            score += 1.5
        
        # Bio length indicates effort in description
        if metrics.bio_length > 100:
            score += 1.0
        elif metrics.bio_length > 50:
            score += 0.5
        
        # Profile image shows professionalism
        if metrics.has_profile_image:
            score += 0.5
        
        # Location adds credibility
        if metrics.has_location:
            score += 0.5
        
        # Not being protected (unless there's a good reason) is more professional
        if not metrics.protected:
            score += 0.5
        else:
            score -= 1.0  # Protected accounts are less accessible
        
        # Username professionalism (basic check)
        if not any(char.isdigit() for char in metrics.username[-4:]):  # No numbers at end
            score += 0.5
        
        return max(0.0, min(10.0, score))
    
    def _calculate_activity_score(self, metrics: TwitterMetrics) -> float:
        """Calculate account activity score (0-10)."""
        score = 5.0
        
        # Tweet count indicates activity over time
        if metrics.tweet_count >= 1000:
            score += 2.0
        elif metrics.tweet_count >= 500:
            score += 1.5
        elif metrics.tweet_count >= 100:
            score += 1.0
        elif metrics.tweet_count < self.thresholds['min_tweets_for_activity']:
            score -= 2.0
        
        # Tweets per day indicates current activity level
        if 0.5 <= metrics.tweets_per_day <= 3:  # Optimal range
            score += 2.0
        elif 0.1 <= metrics.tweets_per_day < 0.5:  # Moderate activity
            score += 1.0
        elif metrics.tweets_per_day > 10:
            score -= 1.0  # Too active might be spam
        elif metrics.tweets_per_day < 0.05:  # Very inactive
            score -= 1.5
        
        # Account age vs activity
        if metrics.account_age_days > 0:
            tweets_per_day_since_creation = metrics.tweet_count / metrics.account_age_days
            if 0.2 <= tweets_per_day_since_creation <= 2:  # Consistent activity
                score += 1.0
        
        return max(0.0, min(10.0, score))
    
    def _calculate_community_score(self, metrics: TwitterMetrics) -> float:
        """Calculate community building score (0-10)."""
        score = 4.0
        
        # Follower count indicates community size
        if metrics.followers_count >= 100000:  # 100K+ followers
            score += 3.0
        elif metrics.followers_count >= 10000:  # 10K+ followers
            score += 2.5
        elif metrics.followers_count >= 5000:   # 5K+ followers
            score += 2.0
        elif metrics.followers_count >= 1000:   # 1K+ followers
            score += 1.5
        elif metrics.followers_count >= 500:    # 500+ followers
            score += 1.0
        elif metrics.followers_count < 100:
            score -= 1.0
        
        # Listed count shows community value
        if metrics.listed_count >= 100:
            score += 1.5
        elif metrics.listed_count >= 50:
            score += 1.0
        elif metrics.listed_count >= 10:
            score += 0.5
        
        # Healthy follower/following ratio
        if metrics.follower_following_ratio >= 2:  # More followers than following
            score += 1.0
        elif metrics.follower_following_ratio >= 1:
            score += 0.5
        
        return max(0.0, min(10.0, score))
    
    def _calculate_overall_score(self, scores: Dict[str, float]) -> float:
        """Calculate weighted overall score."""
        total_score = 0.0
        for category, score in scores.items():
            weight = self.score_weights.get(category, 0)
            total_score += score * weight
        
        return min(10.0, max(0.0, total_score))
    
    def _determine_health_status(self, overall_score: float, metrics: TwitterMetrics) -> TwitterHealthStatus:
        """Determine overall health status based on scores and red flags."""
        
        # Check for immediate disqualifiers
        if metrics.account_age_days < 30:
            return TwitterHealthStatus.SUSPICIOUS
        
        if metrics.followers_count < 50 and metrics.account_age_days > 365:
            return TwitterHealthStatus.POOR
        
        # Score-based classification
        if overall_score >= 8.5:
            return TwitterHealthStatus.EXCELLENT
        elif overall_score >= 7.0:
            return TwitterHealthStatus.GOOD
        elif overall_score >= 5.0:
            return TwitterHealthStatus.AVERAGE
        elif overall_score >= 3.0:
            return TwitterHealthStatus.POOR
        else:
            return TwitterHealthStatus.SUSPICIOUS
    
    def _identify_red_flags(self, metrics: TwitterMetrics, profile_data: Dict) -> List[str]:
        """Identify potential red flags or concerns."""
        red_flags = []
        
        # Account age red flags
        if metrics.account_age_days < 90:
            red_flags.append(f"Very new account ({metrics.account_age_days} days old)")
        
        # Follower patterns
        if metrics.followers_count < 100 and metrics.account_age_days > 365:
            red_flags.append("Old account with very few followers")
        
        if metrics.following_count > metrics.followers_count * 10:
            red_flags.append("Following far more accounts than followers")
        
        # Activity patterns
        if metrics.tweets_per_day > 20:
            red_flags.append("Suspiciously high tweet frequency")
        
        if metrics.tweet_count < 10 and metrics.account_age_days > 180:
            red_flags.append("Very few tweets for account age")
        
        # Profile completeness
        if not metrics.has_bio:
            red_flags.append("No profile bio")
        
        if not metrics.has_profile_image:
            red_flags.append("Using default profile image")
        
        # Bio content analysis
        bio = profile_data.get('description', '').lower()
        if any(word in bio for word in ['investment', 'financial advice', 'guaranteed', '100%', 'risk-free']):
            red_flags.append("Bio contains financial advice language")
        
        # Protected account for crypto project is unusual
        if metrics.protected:
            red_flags.append("Protected account (unusual for crypto projects)")
        
        return red_flags
    
    def _identify_positive_indicators(self, metrics: TwitterMetrics, profile_data: Dict) -> List[str]:
        """Identify positive indicators and strengths."""
        positive_indicators = []
        
        # Verification
        if metrics.verified:
            positive_indicators.append("Verified account")
        
        # Account maturity
        if metrics.account_age_days >= 365:
            positive_indicators.append(f"Mature account ({metrics.account_age_days // 365} years old)")
        
        # Community size
        if metrics.followers_count >= 10000:
            positive_indicators.append(f"Large community ({metrics.followers_count:,} followers)")
        elif metrics.followers_count >= 1000:
            positive_indicators.append(f"Solid community ({metrics.followers_count:,} followers)")
        
        # Profile quality
        if metrics.profile_completeness_score >= 8:
            positive_indicators.append("Complete and professional profile")
        
        # Engagement indicators
        if metrics.listed_count >= 50:
            positive_indicators.append(f"High list inclusion ({metrics.listed_count} lists)")
        
        # Activity patterns
        if 0.5 <= metrics.tweets_per_day <= 3:
            positive_indicators.append("Consistent, balanced posting frequency")
        
        # URL presence
        if metrics.has_website_url:
            positive_indicators.append("Links to official website")
        
        # Bio quality
        bio = profile_data.get('description', '')
        if len(bio) > 80:
            positive_indicators.append("Detailed profile description")
        
        return positive_indicators
    
    def _calculate_confidence_score(self, metrics: TwitterMetrics, profile_data: Dict) -> float:
        """Calculate confidence in the analysis (0-1)."""
        confidence = 0.7  # Base confidence
        
        # More data = higher confidence
        if metrics.account_age_days >= 180:
            confidence += 0.1
        
        if metrics.tweet_count >= 100:
            confidence += 0.1
        
        if metrics.profile_completeness_score >= 6:
            confidence += 0.1
        
        # Less confidence for edge cases
        if metrics.account_age_days < 30:
            confidence -= 0.2
        
        if metrics.followers_count == 0:
            confidence -= 0.1
        
        return max(0.1, min(1.0, confidence))


def main():
    """Test the Twitter analysis metrics."""
    
    # Test with sample data
    test_profile = {
        'username': 'bitcoin',
        'account_age_days': 2500,  # ~7 years
        'verified': True,
        'verified_type': 'blue',
        'protected': False,
        'followers_count': 5500000,
        'following_count': 1,
        'listed_count': 100000,
        'tweet_count': 400,
        'tweets_per_day': 0.16,  # ~1 tweet per week
        'description': 'Bitcoin is a decentralized digital currency that enables instant payments to anyone, anywhere in the world.',
        'location': 'Worldwide',
        'url': 'https://bitcoin.org',
        'profile_image_url': 'https://pbs.twimg.com/profile_images/bitcoin.jpg'
    }
    
    analyzer = TwitterAnalysisMetrics()
    result = analyzer.analyze_account(test_profile)
    
    print("=== Twitter Analysis Results ===")
    print(f"Account: @{result.metrics.username}")
    print(f"Overall Score: {result.overall_score:.2f}/10")
    print(f"Health Status: {result.health_status.value.title()}")
    print(f"Confidence: {result.confidence_score:.2f}")
    
    print(f"\n--- Individual Scores ---")
    print(f"Authenticity: {result.authenticity_score:.1f}/10")
    print(f"Professional: {result.professional_score:.1f}/10")
    print(f"Community: {result.community_score:.1f}/10")
    print(f"Activity: {result.activity_score:.1f}/10")
    print(f"Engagement Quality: {result.engagement_quality_score:.1f}/10")
    
    if result.positive_indicators:
        print(f"\n--- Positive Indicators ---")
        for indicator in result.positive_indicators:
            print(f"✅ {indicator}")
    
    if result.red_flags:
        print(f"\n--- Red Flags ---")
        for flag in result.red_flags:
            print(f"🚩 {flag}")


if __name__ == "__main__":
    main()