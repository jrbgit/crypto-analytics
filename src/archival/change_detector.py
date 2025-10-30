"""
Change Detection System

Compares website snapshots to detect changes in content, structure, and resources.
Computes significance scores and determines if LLM reanalysis is needed.
"""

import hashlib
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger
from bs4 import BeautifulSoup
import difflib

try:
    from Levenshtein import ratio as levenshtein_ratio

    HAS_LEVENSHTEIN = True
except ImportError:
    logger.warning("python-Levenshtein not installed. Using slower difflib instead.")
    HAS_LEVENSHTEIN = False


@dataclass
class ChangeMetrics:
    """Metrics describing changes between snapshots."""

    # Overall metrics
    change_score: float  # 0-1, how significant the change is
    similarity_score: float  # 0-1, how similar the snapshots are
    change_type: str  # content_added, content_removed, etc.

    # Content changes
    text_added_bytes: int = 0
    text_removed_bytes: int = 0
    text_changed_percentage: float = 0.0

    # Structure changes
    html_structure_diff_score: float = 0.0
    new_sections_count: int = 0
    removed_sections_count: int = 0

    # Resource changes
    resources_added_count: int = 0
    resources_removed_count: int = 0
    resources_changed_count: int = 0

    # Detailed changes
    changes_detected: Dict = None

    # Visual changes
    layout_changed: bool = False
    style_changed: bool = False

    # Pages
    pages_changed: List[str] = None
    pages_added: List[str] = None
    pages_removed: List[str] = None

    # Analysis flags
    is_significant_change: bool = False
    requires_reanalysis: bool = False


class ChangeDetector:
    """Detects and analyzes changes between website snapshots."""

    def __init__(
        self, significance_threshold: float = 0.3, reanalysis_threshold: float = 0.3
    ):
        """
        Initialize the change detector.

        Args:
            significance_threshold: Minimum score to mark as significant (0-1)
            reanalysis_threshold: Minimum score to trigger LLM reanalysis (0-1)
        """
        self.significance_threshold = significance_threshold
        self.reanalysis_threshold = reanalysis_threshold

    def detect_changes(self, old_snapshot: Dict, new_snapshot: Dict) -> ChangeMetrics:
        """
        Detect changes between two snapshots.

        Args:
            old_snapshot: Previous snapshot data
            new_snapshot: New snapshot data

        Returns:
            ChangeMetrics with detected changes
        """
        logger.info(
            f"Detecting changes between snapshots {old_snapshot.get('id')} and {new_snapshot.get('id')}"
        )
        start_time = time.time()

        # Quick hash-based comparison first
        if self._hashes_match(old_snapshot, new_snapshot):
            logger.info("Snapshots are identical (hash match)")
            return ChangeMetrics(
                change_score=0.0,
                similarity_score=1.0,
                change_type="no_change",
                is_significant_change=False,
                requires_reanalysis=False,
            )

        # Detailed comparison
        metrics = ChangeMetrics(
            change_score=0.0,
            similarity_score=1.0,
            change_type="no_change",
            changes_detected={},
            pages_changed=[],
            pages_added=[],
            pages_removed=[],
        )

        # Compare content
        content_changes = self._compare_content(
            old_snapshot.get("content", ""), new_snapshot.get("content", "")
        )
        metrics.text_added_bytes = content_changes["added_bytes"]
        metrics.text_removed_bytes = content_changes["removed_bytes"]
        metrics.text_changed_percentage = content_changes["change_percentage"]

        # Compare structure
        structure_changes = self._compare_structure(
            old_snapshot.get("html", ""), new_snapshot.get("html", "")
        )
        metrics.html_structure_diff_score = structure_changes["diff_score"]
        metrics.new_sections_count = structure_changes["new_sections"]
        metrics.removed_sections_count = structure_changes["removed_sections"]
        metrics.layout_changed = structure_changes["layout_changed"]

        # Compare resources
        resource_changes = self._compare_resources(
            old_snapshot.get("resources", []), new_snapshot.get("resources", [])
        )
        metrics.resources_added_count = resource_changes["added"]
        metrics.resources_removed_count = resource_changes["removed"]
        metrics.resources_changed_count = resource_changes["changed"]

        # Compare pages
        page_changes = self._compare_pages(
            old_snapshot.get("urls", []), new_snapshot.get("urls", [])
        )
        metrics.pages_added = page_changes["added"]
        metrics.pages_removed = page_changes["removed"]
        metrics.pages_changed = page_changes["changed"]

        # Aggregate changes
        metrics.changes_detected = {
            "content": content_changes,
            "structure": structure_changes,
            "resources": resource_changes,
            "pages": page_changes,
        }

        # Calculate overall scores
        metrics.change_score = self._calculate_change_score(metrics)
        metrics.similarity_score = 1.0 - metrics.change_score
        metrics.change_type = self._classify_change(metrics)

        # Set flags
        metrics.is_significant_change = (
            metrics.change_score >= self.significance_threshold
        )
        metrics.requires_reanalysis = metrics.change_score >= self.reanalysis_threshold

        duration = time.time() - start_time
        logger.info(
            f"Change detection complete: score={metrics.change_score:.3f}, "
            f"type={metrics.change_type}, reanalysis={metrics.requires_reanalysis} "
            f"({duration:.2f}s)"
        )

        return metrics

    def _hashes_match(self, old_snapshot: Dict, new_snapshot: Dict) -> bool:
        """Quick check if snapshots are identical using hashes."""
        old_hash = old_snapshot.get("content_hash_sha256") or old_snapshot.get(
            "full_site_hash_sha256"
        )
        new_hash = new_snapshot.get("content_hash_sha256") or new_snapshot.get(
            "full_site_hash_sha256"
        )

        return old_hash and new_hash and old_hash == new_hash

    def _compare_content(self, old_content: str, new_content: str) -> Dict:
        """
        Compare text content between snapshots.

        Args:
            old_content: Old content text
            new_content: New content text

        Returns:
            Dictionary with content change metrics
        """
        if not old_content or not new_content:
            return {
                "added_bytes": len(new_content) if new_content else 0,
                "removed_bytes": len(old_content) if old_content else 0,
                "change_percentage": 1.0 if old_content != new_content else 0.0,
                "similarity": 0.0,
            }

        # Compute similarity
        if HAS_LEVENSHTEIN:
            similarity = levenshtein_ratio(old_content, new_content)
        else:
            matcher = difflib.SequenceMatcher(None, old_content, new_content)
            similarity = matcher.ratio()

        # Compute byte changes
        old_len = len(old_content)
        new_len = len(new_content)

        added_bytes = max(0, new_len - old_len)
        removed_bytes = max(0, old_len - new_len)

        # Change percentage
        max_len = max(old_len, new_len)
        change_percentage = (1.0 - similarity) if max_len > 0 else 0.0

        return {
            "added_bytes": added_bytes,
            "removed_bytes": removed_bytes,
            "change_percentage": change_percentage,
            "similarity": similarity,
        }

    def _compare_structure(self, old_html: str, new_html: str) -> Dict:
        """
        Compare HTML structure between snapshots.

        Args:
            old_html: Old HTML content
            new_html: New HTML content

        Returns:
            Dictionary with structure change metrics
        """
        if not old_html or not new_html:
            return {
                "diff_score": 1.0 if old_html != new_html else 0.0,
                "new_sections": 0,
                "removed_sections": 0,
                "layout_changed": old_html != new_html,
            }

        try:
            old_soup = BeautifulSoup(old_html, "html.parser")
            new_soup = BeautifulSoup(new_html, "html.parser")

            # Extract structural elements
            old_sections = self._extract_sections(old_soup)
            new_sections = self._extract_sections(new_soup)

            # Compare sections
            old_ids = set(old_sections.keys())
            new_ids = set(new_sections.keys())

            new_section_ids = new_ids - old_ids
            removed_section_ids = old_ids - new_ids

            # Check for layout changes (major structural elements)
            old_layout = self._extract_layout_structure(old_soup)
            new_layout = self._extract_layout_structure(new_soup)
            layout_changed = old_layout != new_layout

            # Compute diff score
            if old_sections and new_sections:
                sections_changed = len(new_section_ids) + len(removed_section_ids)
                total_sections = max(len(old_sections), len(new_sections))
                diff_score = (
                    sections_changed / total_sections if total_sections > 0 else 0.0
                )
            else:
                diff_score = 1.0 if old_html != new_html else 0.0

            return {
                "diff_score": diff_score,
                "new_sections": len(new_section_ids),
                "removed_sections": len(removed_section_ids),
                "layout_changed": layout_changed,
                "new_section_ids": list(new_section_ids),
                "removed_section_ids": list(removed_section_ids),
            }

        except Exception as e:
            logger.warning(f"Error comparing HTML structure: {e}")
            return {
                "diff_score": 0.5,
                "new_sections": 0,
                "removed_sections": 0,
                "layout_changed": False,
            }

    def _extract_sections(self, soup: BeautifulSoup) -> Dict:
        """Extract major sections from HTML."""
        sections = {}

        # Look for sections with IDs
        for element in soup.find_all(["section", "div", "article", "main", "aside"]):
            elem_id = element.get("id")
            if elem_id:
                sections[elem_id] = {
                    "tag": element.name,
                    "classes": element.get("class", []),
                    "text_length": len(element.get_text(strip=True)),
                }

        return sections

    def _extract_layout_structure(self, soup: BeautifulSoup) -> str:
        """Extract high-level layout structure."""
        structure = []

        # Key structural elements
        for tag in ["header", "nav", "main", "aside", "footer"]:
            elements = soup.find_all(tag)
            if elements:
                structure.append(f"{tag}:{len(elements)}")

        return "|".join(structure)

    def _compare_resources(self, old_resources: List, new_resources: List) -> Dict:
        """
        Compare resources (CSS, JS, images) between snapshots.

        Args:
            old_resources: List of old resource URLs
            new_resources: List of new resource URLs

        Returns:
            Dictionary with resource change metrics
        """
        old_set = set(old_resources) if old_resources else set()
        new_set = set(new_resources) if new_resources else set()

        added = new_set - old_set
        removed = old_set - new_set
        common = old_set & new_set

        return {
            "added": len(added),
            "removed": len(removed),
            "changed": 0,  # Would need hash comparison
            "added_urls": list(added),
            "removed_urls": list(removed),
        }

    def _compare_pages(self, old_urls: List, new_urls: List) -> Dict:
        """
        Compare page URLs between snapshots.

        Args:
            old_urls: List of old URLs
            new_urls: List of new URLs

        Returns:
            Dictionary with page change metrics
        """
        old_set = set(old_urls) if old_urls else set()
        new_set = set(new_urls) if new_urls else set()

        added = new_set - old_set
        removed = old_set - new_set
        common = old_set & new_set

        return {
            "added": list(added),
            "removed": list(removed),
            "changed": list(common),  # Assume common pages might have changed
        }

    def _calculate_change_score(self, metrics: ChangeMetrics) -> float:
        """
        Calculate overall change score from component metrics.

        Args:
            metrics: Change metrics

        Returns:
            Change score between 0 (no change) and 1 (complete change)
        """
        # Weighted components
        content_weight = 0.4
        structure_weight = 0.3
        resources_weight = 0.2
        pages_weight = 0.1

        # Content score (based on text change percentage)
        content_score = min(1.0, metrics.text_changed_percentage)

        # Structure score
        structure_score = min(1.0, metrics.html_structure_diff_score)

        # Resources score
        total_resources = (
            metrics.resources_added_count
            + metrics.resources_removed_count
            + metrics.resources_changed_count
        )
        resources_score = min(
            1.0, total_resources / 50.0
        )  # Normalize to 50 resource changes = 1.0

        # Pages score
        total_page_changes = len(metrics.pages_added or []) + len(
            metrics.pages_removed or []
        )
        pages_score = min(
            1.0, total_page_changes / 20.0
        )  # Normalize to 20 page changes = 1.0

        # Weighted average
        overall_score = (
            content_weight * content_score
            + structure_weight * structure_score
            + resources_weight * resources_score
            + pages_weight * pages_score
        )

        return overall_score

    def _classify_change(self, metrics: ChangeMetrics) -> str:
        """
        Classify the type of change.

        Args:
            metrics: Change metrics

        Returns:
            Change type classification
        """
        if metrics.change_score < 0.05:
            return "no_change"

        # Major redesign detection
        if metrics.layout_changed and metrics.html_structure_diff_score > 0.7:
            return "major_redesign"

        # Structure-heavy changes
        if metrics.html_structure_diff_score > 0.5:
            return "structure_changed"

        # Resource-heavy changes
        if (metrics.resources_added_count + metrics.resources_removed_count) > 20:
            return "resources_changed"

        # Content changes
        if metrics.text_added_bytes > metrics.text_removed_bytes * 2:
            return "content_added"
        elif metrics.text_removed_bytes > metrics.text_added_bytes * 2:
            return "content_removed"
        else:
            return "content_modified"

    def compute_content_hash(self, content: str) -> str:
        """
        Compute SHA256 hash of content.

        Args:
            content: Content string

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def compute_structure_hash(self, html: str) -> str:
        """
        Compute hash of HTML structure (ignoring content).

        Args:
            html: HTML string

        Returns:
            Hexadecimal hash string
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Extract structural elements only
            structure_elements = []
            for element in soup.find_all():
                structure_elements.append(
                    f"{element.name}:{element.get('id', '')}:{'.'.join(element.get('class', []))}"
                )

            structure_str = "|".join(structure_elements)
            return hashlib.sha256(structure_str.encode("utf-8")).hexdigest()

        except Exception as e:
            logger.warning(f"Error computing structure hash: {e}")
            return hashlib.sha256(html.encode("utf-8")).hexdigest()


def format_change_report(metrics: ChangeMetrics) -> str:
    """
    Format change metrics into a human-readable report.

    Args:
        metrics: Change metrics

    Returns:
        Formatted report string
    """
    report = []
    report.append("=" * 60)
    report.append("SNAPSHOT CHANGE REPORT")
    report.append("=" * 60)
    report.append(f"Change Score: {metrics.change_score:.2%}")
    report.append(f"Similarity: {metrics.similarity_score:.2%}")
    report.append(f"Change Type: {metrics.change_type.replace('_', ' ').title()}")
    report.append(f"Significant: {'Yes' if metrics.is_significant_change else 'No'}")
    report.append(
        f"Requires Reanalysis: {'Yes' if metrics.requires_reanalysis else 'No'}"
    )
    report.append("")

    report.append("CONTENT CHANGES:")
    report.append(f"  Text Added: {metrics.text_added_bytes:,} bytes")
    report.append(f"  Text Removed: {metrics.text_removed_bytes:,} bytes")
    report.append(f"  Text Changed: {metrics.text_changed_percentage:.1%}")
    report.append("")

    report.append("STRUCTURE CHANGES:")
    report.append(f"  Structure Diff: {metrics.html_structure_diff_score:.2%}")
    report.append(f"  New Sections: {metrics.new_sections_count}")
    report.append(f"  Removed Sections: {metrics.removed_sections_count}")
    report.append(f"  Layout Changed: {'Yes' if metrics.layout_changed else 'No'}")
    report.append("")

    report.append("RESOURCE CHANGES:")
    report.append(f"  Added: {metrics.resources_added_count}")
    report.append(f"  Removed: {metrics.resources_removed_count}")
    report.append(f"  Changed: {metrics.resources_changed_count}")
    report.append("")

    report.append("PAGE CHANGES:")
    report.append(f"  Added: {len(metrics.pages_added or [])}")
    report.append(f"  Removed: {len(metrics.pages_removed or [])}")
    report.append(f"  Modified: {len(metrics.pages_changed or [])}")
    report.append("=" * 60)

    return "\n".join(report)
