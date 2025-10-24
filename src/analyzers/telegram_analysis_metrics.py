"""
Telegram Channel Analysis Metrics for Cryptocurrency Projects

This module provides comprehensive analysis metrics for Telegram channels/groups
to evaluate the quality, legitimacy, and community health of crypto projects.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum
import re


class TelegramHealthStatus(Enum):
    """Health status categories for Telegram channels."""

    EXCELLENT = "excellent"  # High quality, active, legitimate
    GOOD = "good"  # Good quality with minor issues
    FAIR = "fair"  # Average quality, some concerns
    POOR = "poor"  # Low quality or suspicious
    SUSPICIOUS = "suspicious"  # Likely scam or spam


@dataclass
class TelegramAnalysisResult:
    """Comprehensive analysis result for a Telegram channel."""

    # Channel identification
    channel_id: str
    channel_title: str
    channel_type: str

    # Basic metrics
    member_count: int
    has_username: bool
    has_description: bool

    # Analysis scores (0-10)
    authenticity_score: float  # How authentic/legitimate the channel appears
    community_score: float  # Community size and engagement quality
    content_score: float  # Content quality and professionalism
    activity_score: float  # Activity level indicators
    security_score: float  # Security and privacy settings
    overall_score: float  # Weighted overall score

    # Derived metrics
    size_category: str  # 'large', 'medium', 'small', 'tiny', 'minimal'
    type_appropriateness: float  # How appropriate the channel type is

    # Health assessment
    health_status: TelegramHealthStatus
    confidence_score: float  # Confidence in the analysis (0-1)

    # Qualitative indicators
    red_flags: List[str]  # Suspicious or negative indicators
    positive_indicators: List[str]  # Good quality indicators

    # Analysis metadata
    analysis_timestamp: datetime


class TelegramAnalysisMetrics:
    """Telegram channel analysis and scoring system."""

    def __init__(self):
        """Initialize the Telegram analysis metrics."""
        self.weights = {
            "authenticity": 0.30,  # Legitimacy is crucial for crypto projects
            "community": 0.25,  # Community size and quality matter
            "content": 0.20,  # Content professionalism
            "activity": 0.15,  # Activity level indicators
            "security": 0.10,  # Security/privacy settings
        }

    def analyze_channel(self, channel_data: Dict[str, Any]) -> TelegramAnalysisResult:
        """
        Perform comprehensive analysis of a Telegram channel.

        Args:
            channel_data: Dictionary containing channel information from API

        Returns:
            TelegramAnalysisResult with scores and analysis
        """

        # Calculate individual scores
        authenticity_score = self._calculate_authenticity_score(channel_data)
        community_score = self._calculate_community_score(channel_data)
        content_score = self._calculate_content_score(channel_data)
        activity_score = self._calculate_activity_score(channel_data)
        security_score = self._calculate_security_score(channel_data)

        # Calculate weighted overall score
        overall_score = (
            authenticity_score * self.weights["authenticity"]
            + community_score * self.weights["community"]
            + content_score * self.weights["content"]
            + activity_score * self.weights["activity"]
            + security_score * self.weights["security"]
        )

        # Determine health status
        health_status = self._determine_health_status(overall_score, channel_data)

        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(channel_data)

        # Identify qualitative indicators
        red_flags = self._identify_red_flags(channel_data)
        positive_indicators = self._identify_positive_indicators(channel_data)

        return TelegramAnalysisResult(
            channel_id=channel_data.get("channel_id", ""),
            channel_title=channel_data.get("title", ""),
            channel_type=channel_data.get("type", ""),
            member_count=channel_data.get("member_count", 0),
            has_username=bool(channel_data.get("username")),
            has_description=bool(channel_data.get("description")),
            authenticity_score=authenticity_score,
            community_score=community_score,
            content_score=content_score,
            activity_score=activity_score,
            security_score=security_score,
            overall_score=overall_score,
            size_category=channel_data.get("size_category", "unknown"),
            type_appropriateness=channel_data.get("type_score", 0) / 10.0,
            health_status=health_status,
            confidence_score=confidence_score,
            red_flags=red_flags,
            positive_indicators=positive_indicators,
            analysis_timestamp=datetime.now(timezone.utc),
        )

    def _calculate_authenticity_score(self, channel_data: Dict) -> float:
        """Calculate authenticity/legitimacy score (0-10)."""

        score = 5.0  # Base score

        # Username presence indicates legitimacy
        if channel_data.get("username"):
            score += 1.5

        # Channel type appropriateness
        channel_type = channel_data.get("type", "") or ""
        channel_type = channel_type.lower()
        if channel_type == "channel":
            score += 1.0  # Broadcast channels are good for projects
        elif channel_type == "supergroup":
            score += 0.5  # Supergroups can be legitimate

        # Description quality
        description = channel_data.get("description", "") or ""
        description = description.lower()
        if description:
            # Official indicators
            if any(
                word in description for word in ["official", "team", "announcement"]
            ):
                score += 1.5

            # Professional language
            if any(
                word in description
                for word in ["project", "blockchain", "development", "protocol"]
            ):
                score += 1.0

            # Technical terms
            if any(
                word in description
                for word in ["defi", "smart contract", "consensus", "node"]
            ):
                score += 0.5

            # Red flag terms
            if any(
                word in description
                for word in ["pump", "moon", "guaranteed", "profit", "100x"]
            ):
                score -= 2.0

            # Scam indicators
            if any(
                word in description for word in ["free money", "airdrop", "giveaway"]
            ):
                score -= 1.0

        # Member count legitimacy (very small or suspiciously round numbers)
        member_count = channel_data.get("member_count", 0)
        if member_count == 0:
            score -= 1.0
        elif member_count < 10:
            score -= 0.5
        elif str(member_count).endswith("000") and member_count > 10000:
            score -= 0.3  # Suspiciously round numbers

        # Protected content suggests legitimacy
        if channel_data.get("has_protected_content"):
            score += 0.5

        return max(0.0, min(10.0, score))

    def _calculate_community_score(self, channel_data: Dict) -> float:
        """Calculate community size and quality score (0-10)."""

        member_count = channel_data.get("member_count", 0)

        # Base score from member count
        if member_count >= 100000:
            base_score = 10.0
        elif member_count >= 50000:
            base_score = 9.0
        elif member_count >= 10000:
            base_score = 8.0
        elif member_count >= 5000:
            base_score = 7.0
        elif member_count >= 1000:
            base_score = 6.0
        elif member_count >= 500:
            base_score = 5.0
        elif member_count >= 100:
            base_score = 4.0
        elif member_count >= 50:
            base_score = 3.0
        elif member_count >= 10:
            base_score = 2.0
        else:
            base_score = 1.0

        # Channel type modifier
        channel_type = channel_data.get("type", "") or ""
        channel_type = channel_type.lower()
        if channel_type == "channel":
            # Channels are good for broadcasting
            return min(10.0, base_score)
        elif channel_type == "supergroup":
            # Supergroups allow more interaction
            return min(10.0, base_score + 0.5)
        else:
            return min(10.0, base_score - 0.5)

    def _calculate_content_score(self, channel_data: Dict) -> float:
        """Calculate content quality and professionalism score (0-10)."""

        score = 5.0  # Base score

        title = channel_data.get("title", "") or ""
        title = title.lower()
        description = channel_data.get("description", "") or ""
        description = description.lower()

        # Title quality
        if title:
            # Professional project names
            if any(
                word in title
                for word in ["protocol", "network", "blockchain", "coin", "token"]
            ):
                score += 1.0

            # Official indicators
            if any(word in title for word in ["official", "team"]):
                score += 0.5

            # Spam indicators in title
            if any(char in title for char in ["🚀", "💎", "🔥", "📈"]):
                score -= 1.0

        # Description quality
        if description:
            word_count = len(description.split())
            if word_count >= 20:
                score += 1.0  # Detailed description
            elif word_count >= 10:
                score += 0.5  # Basic description

            # Professional language
            if any(
                word in description
                for word in ["technology", "innovative", "decentralized"]
            ):
                score += 0.5

            # Links to official resources
            if "github" in description or "whitepaper" in description:
                score += 1.0

            # Website link
            if any(domain in description for domain in [".com", ".org", ".io"]):
                score += 0.5

        # Username professionalism
        username = channel_data.get("username", "") or ""
        username = username.lower()
        if username:
            # Clean, professional username
            if re.match(r"^[a-z][a-z0-9_]*$", username):
                score += 0.5

            # Project name consistency
            if title and username in title.replace(" ", ""):
                score += 0.5

        return max(0.0, min(10.0, score))

    def _calculate_activity_score(self, channel_data: Dict) -> float:
        """Calculate activity level indicators (0-10)."""

        score = 5.0  # Base score (neutral since we can't get message history)

        # Pinned message indicates activity
        if channel_data.get("pinned_message"):
            score += 2.0

        # Slow mode suggests moderated active community
        if channel_data.get("slow_mode_delay"):
            score += 1.0

        # Large communities are typically more active
        member_count = channel_data.get("member_count", 0)
        if member_count >= 10000:
            score += 1.0
        elif member_count >= 1000:
            score += 0.5

        # Channel type affects activity expectations
        channel_type = channel_data.get("type", "") or ""
        channel_type = channel_type.lower()
        if channel_type == "channel":
            # Channels are for broadcasting, less interactive
            score += 0.5
        elif channel_type == "supergroup":
            # Supergroups allow member interaction
            score += 1.0

        return max(0.0, min(10.0, score))

    def _calculate_security_score(self, channel_data: Dict) -> float:
        """Calculate security and privacy settings score (0-10)."""

        score = 5.0  # Base score

        # Protected content
        if channel_data.get("has_protected_content"):
            score += 2.0

        # Visible history settings
        if channel_data.get("has_visible_history"):
            score += 1.0  # Transparency is good

        # Anti-spam enabled
        if channel_data.get("has_aggressive_anti_spam_enabled"):
            score += 1.5

        # Slow mode for spam control
        if channel_data.get("slow_mode_delay"):
            score += 1.0

        # Username visibility (public channel)
        if channel_data.get("username"):
            score += 0.5  # Public channels are more transparent

        return max(0.0, min(10.0, score))

    def _determine_health_status(
        self, overall_score: float, channel_data: Dict
    ) -> TelegramHealthStatus:
        """Determine the overall health status of the channel."""

        # Check for immediate red flags
        red_flags = self._identify_red_flags(channel_data)
        if len(red_flags) >= 3:
            return TelegramHealthStatus.SUSPICIOUS

        # Score-based determination
        if overall_score >= 8.5:
            return TelegramHealthStatus.EXCELLENT
        elif overall_score >= 7.0:
            return TelegramHealthStatus.GOOD
        elif overall_score >= 5.5:
            return TelegramHealthStatus.FAIR
        elif overall_score >= 3.5:
            return TelegramHealthStatus.POOR
        else:
            return TelegramHealthStatus.SUSPICIOUS

    def _calculate_confidence_score(self, channel_data: Dict) -> float:
        """Calculate confidence in the analysis (0-1)."""

        confidence = 0.5  # Base confidence

        # More data = higher confidence
        if channel_data.get("description"):
            confidence += 0.15

        if channel_data.get("username"):
            confidence += 0.1

        if channel_data.get("member_count", 0) > 0:
            confidence += 0.1

        # Channel type known
        if channel_data.get("type") in ["channel", "group", "supergroup"]:
            confidence += 0.1

        # Additional metadata available
        if channel_data.get("pinned_message"):
            confidence += 0.05

        return min(1.0, confidence)

    def _identify_red_flags(self, channel_data: Dict) -> List[str]:
        """Identify red flags or suspicious indicators."""

        red_flags = []

        title = channel_data.get("title", "") or ""
        title = title.lower()
        description = channel_data.get("description", "") or ""
        description = description.lower()
        member_count = channel_data.get("member_count", 0)

        # Member count red flags
        if member_count == 0:
            red_flags.append("No members reported")
        elif member_count < 10:
            red_flags.append("Very low member count")

        # Title red flags
        if any(word in title for word in ["pump", "moon", "gem", "100x"]):
            red_flags.append("Pump/speculation language in title")

        if any(char in title for char in ["🚀", "💎", "🔥", "📈", "💰"]):
            red_flags.append("Excessive emoji use in title")

        # Description red flags
        if description:
            if any(
                word in description
                for word in ["guaranteed profit", "get rich", "easy money"]
            ):
                red_flags.append("Unrealistic profit promises")

            if any(
                word in description for word in ["airdrop", "free tokens", "giveaway"]
            ):
                red_flags.append("Potential airdrop scam indicators")

            if description.count("!") > 5:
                red_flags.append("Excessive exclamation marks")

        # No description
        if not description:
            red_flags.append("No channel description provided")

        # No username (private channel)
        if not channel_data.get("username") and member_count > 1000:
            red_flags.append("Large channel without public username")

        return red_flags

    def _identify_positive_indicators(self, channel_data: Dict) -> List[str]:
        """Identify positive quality indicators."""

        positive_indicators = []

        title = channel_data.get("title", "") or ""
        title = title.lower()
        description = channel_data.get("description", "") or ""
        description = description.lower()
        member_count = channel_data.get("member_count", 0)
        channel_type = channel_data.get("type", "") or ""
        channel_type = channel_type.lower()

        # Member count positives
        if member_count >= 50000:
            positive_indicators.append("Large, established community")
        elif member_count >= 10000:
            positive_indicators.append("Significant community size")
        elif member_count >= 1000:
            positive_indicators.append("Active community base")

        # Channel type positives
        if channel_type == "channel":
            positive_indicators.append("Professional broadcast channel format")

        # Title positives
        if any(word in title for word in ["official", "protocol", "network"]):
            positive_indicators.append("Professional project naming")

        # Description positives
        if description:
            if any(word in description for word in ["official", "team", "development"]):
                positive_indicators.append("Official team channel indicators")

            if "github" in description:
                positive_indicators.append("Links to code repository")

            if any(
                word in description
                for word in ["blockchain", "decentralized", "protocol"]
            ):
                positive_indicators.append("Technical blockchain project")

            if len(description.split()) >= 20:
                positive_indicators.append("Detailed channel description")

        # Username positives
        if channel_data.get("username"):
            positive_indicators.append("Public channel with username")

        # Security positives
        if channel_data.get("has_protected_content"):
            positive_indicators.append("Content protection enabled")

        if channel_data.get("has_aggressive_anti_spam_enabled"):
            positive_indicators.append("Anti-spam protection active")

        return positive_indicators


def main():
    """Test the Telegram analysis metrics."""

    analyzer = TelegramAnalysisMetrics()

    # Test with sample channel data
    test_channels = [
        {
            "name": "High Quality Project",
            "data": {
                "channel_id": "ethereum",
                "title": "Ethereum Official",
                "username": "ethereum",
                "type": "channel",
                "description": "Official Ethereum blockchain protocol announcements and development updates. Visit our GitHub for technical documentation.",
                "member_count": 150000,
                "has_protected_content": True,
                "has_aggressive_anti_spam_enabled": True,
                "pinned_message": {"text": "Welcome to Ethereum official channel"},
                "size_category": "large",
                "type_score": 10,
            },
        },
        {
            "name": "Suspicious Channel",
            "data": {
                "channel_id": "moonpump123",
                "title": "🚀MOONPUMP🚀 100x GUARANTEED 💎",
                "type": "group",
                "description": "GET RICH QUICK!!! Free money airdrop guaranteed profit 1000x!!!",
                "member_count": 0,
                "size_category": "minimal",
                "type_score": 6,
            },
        },
    ]

    for test_channel in test_channels:
        print(f"\n=== Testing {test_channel['name']} ===")

        result = analyzer.analyze_channel(test_channel["data"])

        print(f"Overall Score: {result.overall_score:.2f}/10")
        print(f"Health Status: {result.health_status.value.title()}")
        print(f"Confidence: {result.confidence_score:.2f}")
        print(f"Member Count: {result.member_count:,}")

        print(f"\nComponent Scores:")
        print(f"  Authenticity: {result.authenticity_score:.1f}/10")
        print(f"  Community: {result.community_score:.1f}/10")
        print(f"  Content: {result.content_score:.1f}/10")
        print(f"  Activity: {result.activity_score:.1f}/10")
        print(f"  Security: {result.security_score:.1f}/10")

        if result.positive_indicators:
            print(f"\nPositive Indicators:")
            for indicator in result.positive_indicators[:5]:
                print(f"  ✅ {indicator}")

        if result.red_flags:
            print(f"\nRed Flags:")
            for flag in result.red_flags[:5]:
                print(f"  🚩 {flag}")


if __name__ == "__main__":
    main()
