#!/usr/bin/env python3
"""
Comprehensive Error Reporter

This module collects, categorizes, and reports on errors encountered during analysis runs,
providing actionable insights and suggested fixes for common issues.
"""

import json
import time
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification"""

    NETWORK = "network"
    CONTENT = "content"
    PARSING = "parsing"
    API = "api"
    CONFIGURATION = "configuration"
    SYSTEM = "system"


@dataclass
class ErrorRecord:
    """Individual error record"""

    timestamp: str
    category: ErrorCategory
    severity: ErrorSeverity
    error_type: str
    url: Optional[str]
    message: str
    context: Dict[str, Any]
    suggested_fix: Optional[str] = None


@dataclass
class ErrorSummary:
    """Summary of errors by type"""

    error_type: str
    count: int
    severity: ErrorSeverity
    category: ErrorCategory
    first_seen: str
    last_seen: str
    affected_urls: List[str]
    suggested_fixes: List[str]
    resolution_tips: List[str]


class ErrorReporter:
    """Comprehensive error reporting and analysis system"""

    def __init__(self, report_file: Optional[str] = None):
        """
        Initialize the error reporter.

        Args:
            report_file: Path to save error reports (default: error_report.json)
        """
        self.report_file = (
            Path(report_file) if report_file else Path("error_report.json")
        )
        self.errors: List[ErrorRecord] = []
        self.session_start = datetime.now(timezone.utc).isoformat()

        # Error type mappings with suggested fixes
        self.error_mappings = {
            # Network errors
            "dns_resolution_error": {
                "category": ErrorCategory.NETWORK,
                "severity": ErrorSeverity.HIGH,
                "fixes": [
                    "Check internet connection",
                    "Verify domain name is correct",
                    "Domain may be expired or suspended",
                    "Try again later - could be temporary DNS issue",
                ],
                "tips": [
                    "Use nslookup or dig to verify DNS resolution",
                    "Check if domain exists on domain registrar sites",
                ],
            },
            "ssl_certificate_error": {
                "category": ErrorCategory.NETWORK,
                "severity": ErrorSeverity.MEDIUM,
                "fixes": [
                    "Website has SSL certificate issues",
                    "May need to add SSL verification bypass (use caution)",
                    "Contact website administrator about certificate",
                    "Try accessing site directly to verify SSL status",
                ],
                "tips": [
                    "Check SSL certificate status with SSL checker tools",
                    "Consider implementing SSL bypass for known safe sites",
                ],
            },
            "connection_timeout": {
                "category": ErrorCategory.NETWORK,
                "severity": ErrorSeverity.MEDIUM,
                "fixes": [
                    "Increase request timeout values",
                    "Server may be overloaded - try again later",
                    "Check network connectivity",
                    "Consider implementing retry with exponential backoff",
                ],
                "tips": [
                    "Monitor network latency",
                    "Implement progressive timeout increases for retries",
                ],
            },
            "connection_reset_by_peer": {
                "category": ErrorCategory.NETWORK,
                "severity": ErrorSeverity.MEDIUM,
                "fixes": [
                    "Server terminated connection - may be rate limiting",
                    "Implement longer delays between requests",
                    "Server may be blocking automated requests",
                    "Try with different user agents",
                ],
                "tips": [
                    "Check server logs if available",
                    "Implement request rate limiting",
                ],
            },
            "http_404_not_found": {
                "category": ErrorCategory.CONTENT,
                "severity": ErrorSeverity.MEDIUM,
                "fixes": [
                    "URL no longer exists or was moved",
                    "Check for redirects or alternative URLs",
                    "Content may have been moved to different location",
                    "Verify URL is still valid on website",
                ],
                "tips": [
                    "Implement alternative URL strategies",
                    "Check web archives for historical content",
                ],
            },
            "robots_blocked": {
                "category": ErrorCategory.CONTENT,
                "severity": ErrorSeverity.LOW,
                "fixes": [
                    "Website blocks scraping via robots.txt",
                    "Respect robots.txt restrictions",
                    "Contact website owner for permission",
                    "Look for official APIs or data feeds",
                ],
                "tips": [
                    "Check robots.txt file directly",
                    "Look for alternative data sources",
                ],
            },
            "parked_domain": {
                "category": ErrorCategory.CONTENT,
                "severity": ErrorSeverity.HIGH,
                "fixes": [
                    "Domain is parked or for sale",
                    "Project website no longer active",
                    "Look for official social media or alternative sites",
                    "Remove from analysis list",
                ],
                "tips": [
                    "Check domain registration status",
                    "Look for project updates on social media",
                ],
            },
            "minimal_content": {
                "category": ErrorCategory.CONTENT,
                "severity": ErrorSeverity.MEDIUM,
                "fixes": [
                    "Page has very little content to analyze",
                    "May be loading page or placeholder",
                    "Try different pages from same domain",
                    "Check if content loads dynamically",
                ],
                "tips": [
                    "Try scraping multiple pages from domain",
                    "Check for JavaScript-rendered content",
                ],
            },
            "dynamic_content": {
                "category": ErrorCategory.CONTENT,
                "severity": ErrorSeverity.MEDIUM,
                "fixes": [
                    "Content requires JavaScript to load",
                    "Consider using Selenium or similar for dynamic content",
                    "Look for static pages or API endpoints",
                    "Check page source for useful meta information",
                ],
                "tips": [
                    "Implement JavaScript rendering for critical sites",
                    "Look for alternative static content sources",
                ],
            },
            "pdf_extraction_failed": {
                "category": ErrorCategory.PARSING,
                "severity": ErrorSeverity.HIGH,
                "fixes": [
                    "PDF file is corrupted or password protected",
                    "Install additional PDF parsing libraries",
                    "Try different PDF extraction methods",
                    "Check if PDF is actually a PDF file",
                ],
                "tips": [
                    "Install PyPDF2 and pdfplumber for better extraction",
                    "Check PDF file integrity manually",
                ],
            },
            "json_parsing_error": {
                "category": ErrorCategory.PARSING,
                "severity": ErrorSeverity.HIGH,
                "fixes": [
                    "LLM returned invalid JSON format",
                    "Implement JSON repair mechanisms",
                    "Retry analysis with different parameters",
                    "Check LLM prompt for JSON format requirements",
                ],
                "tips": [
                    "Implement JSON validation and repair",
                    "Add more explicit JSON formatting in prompts",
                ],
            },
            "llm_analysis_failed": {
                "category": ErrorCategory.API,
                "severity": ErrorSeverity.CRITICAL,
                "fixes": [
                    "LLM API call failed - check connection",
                    "Verify API credentials and quotas",
                    "Check model availability",
                    "Implement fallback analysis methods",
                ],
                "tips": [
                    "Monitor API usage and limits",
                    "Implement alternative analysis providers",
                ],
            },
            "model_not_found": {
                "category": ErrorCategory.CONFIGURATION,
                "severity": ErrorSeverity.CRITICAL,
                "fixes": [
                    "Specified LLM model not available",
                    "Install or download missing model",
                    "Check model name spelling",
                    "Use alternative available model",
                ],
                "tips": [
                    "Run 'ollama list' to see available models",
                    "Install models with 'ollama pull [model-name]'",
                ],
            },
        }

    def log_error(
        self,
        error_type: str,
        message: str,
        url: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        severity: Optional[ErrorSeverity] = None,
    ) -> None:
        """
        Log an error with automatic categorization and suggestions.

        Args:
            error_type: Type/category of error
            message: Error message
            url: Associated URL if applicable
            context: Additional context information
            severity: Override default severity
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        context = context or {}

        # Get error mapping or use defaults
        mapping = self.error_mappings.get(
            error_type,
            {
                "category": ErrorCategory.SYSTEM,
                "severity": ErrorSeverity.MEDIUM,
                "fixes": ["Unknown error type - investigate manually"],
                "tips": ["Check logs for more details"],
            },
        )

        # Use provided severity or default from mapping
        error_severity = severity or mapping["severity"]

        # Create suggested fix from mapping
        suggested_fix = "; ".join(mapping.get("fixes", [])[:2])  # First 2 fixes

        error_record = ErrorRecord(
            timestamp=timestamp,
            category=mapping["category"],
            severity=error_severity,
            error_type=error_type,
            url=url,
            message=message,
            context=context,
            suggested_fix=suggested_fix,
        )

        self.errors.append(error_record)

    def generate_summary(self) -> Dict[str, Any]:
        """Generate comprehensive error summary with statistics and recommendations."""
        if not self.errors:
            return {
                "session_start": self.session_start,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_errors": 0,
                "summary": "No errors recorded",
                "recommendations": ["Continue monitoring for issues"],
                "success_rate": 100.0,
                "most_problematic_domains": [],
                "category_breakdown": {},
                "severity_breakdown": {},
                "error_summaries": [],
            }

        # Group errors by type
        error_groups = defaultdict(list)
        for error in self.errors:
            error_groups[error.error_type].append(error)

        # Create summaries
        summaries = []
        for error_type, error_list in error_groups.items():
            first_error = min(error_list, key=lambda x: x.timestamp)
            last_error = max(error_list, key=lambda x: x.timestamp)

            affected_urls = list(set(e.url for e in error_list if e.url))

            mapping = self.error_mappings.get(error_type, {})

            summary = ErrorSummary(
                error_type=error_type,
                count=len(error_list),
                severity=first_error.severity,
                category=first_error.category,
                first_seen=first_error.timestamp,
                last_seen=last_error.timestamp,
                affected_urls=affected_urls,
                suggested_fixes=mapping.get("fixes", []),
                resolution_tips=mapping.get("tips", []),
            )
            summaries.append(summary)

        # Sort by severity and count
        severity_order = {
            ErrorSeverity.CRITICAL: 0,
            ErrorSeverity.HIGH: 1,
            ErrorSeverity.MEDIUM: 2,
            ErrorSeverity.LOW: 3,
        }
        summaries.sort(key=lambda x: (severity_order[x.severity], -x.count))

        # Generate statistics
        total_errors = len(self.errors)
        category_counts = Counter(error.category.value for error in self.errors)
        severity_counts = Counter(error.severity.value for error in self.errors)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            summaries, category_counts, severity_counts
        )

        return {
            "session_start": self.session_start,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_errors": total_errors,
            "category_breakdown": dict(category_counts),
            "severity_breakdown": dict(severity_counts),
            "error_summaries": [asdict(s) for s in summaries],
            "recommendations": recommendations,
            "success_rate": self._calculate_success_rate(),
            "most_problematic_domains": self._get_problematic_domains(),
        }

    def _generate_recommendations(
        self,
        summaries: List[ErrorSummary],
        category_counts: Counter,
        severity_counts: Counter,
    ) -> List[str]:
        """Generate actionable recommendations based on error patterns."""
        recommendations = []

        # Critical errors
        critical_errors = [s for s in summaries if s.severity == ErrorSeverity.CRITICAL]
        if critical_errors:
            recommendations.append(
                f"🚨 {len(critical_errors)} critical error types need immediate attention"
            )
            for error in critical_errors[:3]:  # Top 3 critical
                recommendations.append(
                    f"  • {error.error_type}: {error.suggested_fixes[0] if error.suggested_fixes else 'Investigate immediately'}"
                )

        # Network issues
        if category_counts[ErrorCategory.NETWORK.value] > len(self.errors) * 0.3:
            recommendations.append(
                "🌐 High network error rate - check internet connection and target site availability"
            )

        # Content issues
        if category_counts[ErrorCategory.CONTENT.value] > len(self.errors) * 0.4:
            recommendations.append(
                "📄 Many content-related issues - consider updating URL lists and checking site status"
            )

        # API issues
        if category_counts[ErrorCategory.API.value] > 0:
            recommendations.append(
                "🤖 API-related errors detected - verify LLM service status and configuration"
            )

        # Configuration issues
        if category_counts[ErrorCategory.CONFIGURATION.value] > 0:
            recommendations.append(
                "⚙️ Configuration issues found - review setup and dependencies"
            )

        # High error rate
        if (
            severity_counts["high"] + severity_counts["critical"]
            > len(self.errors) * 0.2
        ):
            recommendations.append(
                "⚠️ High severity error rate - consider pausing analysis to fix major issues"
            )

        # Success rate recommendations
        success_rate = self._calculate_success_rate()
        if success_rate < 50:
            recommendations.append(
                "📉 Low success rate (<50%) - review error patterns and fix systematic issues"
            )
        elif success_rate < 75:
            recommendations.append(
                "📊 Moderate success rate - focus on fixing most common error types"
            )
        else:
            recommendations.append(
                "✅ Good success rate - continue monitoring and address remaining issues"
            )

        return recommendations

    def _calculate_success_rate(self) -> float:
        """Calculate approximate success rate based on errors vs total attempts."""
        # This is a rough estimate - in a real implementation you'd track total attempts
        # For now, assume high error counts indicate low success rates
        if not self.errors:
            return 100.0

        critical_errors = sum(
            1 for e in self.errors if e.severity == ErrorSeverity.CRITICAL
        )
        high_errors = sum(1 for e in self.errors if e.severity == ErrorSeverity.HIGH)

        # Rough calculation: assume each critical error represents 5 failed attempts
        # and each high error represents 2 failed attempts
        estimated_failures = (
            (critical_errors * 5) + (high_errors * 2) + len(self.errors)
        )
        estimated_attempts = estimated_failures * 2  # Assume 50% base success rate

        return max(
            0,
            min(
                100,
                ((estimated_attempts - estimated_failures) / estimated_attempts) * 100,
            ),
        )

    def _get_problematic_domains(self) -> List[Dict[str, Any]]:
        """Get domains with the most errors."""
        domain_errors = defaultdict(list)

        for error in self.errors:
            if error.url:
                from urllib.parse import urlparse

                try:
                    domain = urlparse(error.url).netloc
                    domain_errors[domain].append(error)
                except Exception:
                    continue

        # Sort by error count and severity
        problematic_domains = []
        for domain, errors in domain_errors.items():
            if len(errors) >= 2:  # Only include domains with multiple errors
                severity_score = sum(
                    (
                        4
                        if e.severity == ErrorSeverity.CRITICAL
                        else (
                            3
                            if e.severity == ErrorSeverity.HIGH
                            else 2 if e.severity == ErrorSeverity.MEDIUM else 1
                        )
                    )
                    for e in errors
                )

                error_types = list(set(e.error_type for e in errors))

                problematic_domains.append(
                    {
                        "domain": domain,
                        "error_count": len(errors),
                        "severity_score": severity_score,
                        "error_types": error_types,
                        "recommendation": "Review domain status and consider removing if consistently problematic",
                    }
                )

        return sorted(
            problematic_domains, key=lambda x: (-x["severity_score"], -x["error_count"])
        )[:10]

    def save_report(self, filename: Optional[str] = None) -> Path:
        """Save comprehensive error report to file."""
        report_file = Path(filename) if filename else self.report_file
        summary = self.generate_summary()

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        return report_file

    def print_summary(self, max_errors: int = 10) -> None:
        """Print a formatted summary to console."""
        summary = self.generate_summary()

        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE ERROR REPORT")
        print("=" * 60)
        print(f"Session started: {summary['session_start']}")
        print(f"Total errors: {summary['total_errors']}")
        print(f"Estimated success rate: {summary['success_rate']:.1f}%")

        if summary["total_errors"] == 0:
            print("\n✅ No errors recorded - excellent!")
            return

        print(f"\n📈 ERROR BREAKDOWN:")
        print(f"By Category: {summary['category_breakdown']}")
        print(f"By Severity: {summary['severity_breakdown']}")

        print(f"\n🔍 TOP ERROR TYPES:")
        for i, error_summary in enumerate(summary["error_summaries"][:max_errors]):
            severity_emoji = {
                "critical": "🚨",
                "high": "⚠️",
                "medium": "🟡",
                "low": "🔵",
            }
            emoji = severity_emoji.get(error_summary["severity"], "❓")

            print(
                f"{emoji} {error_summary['error_type']}: {error_summary['count']} occurrences"
            )
            if error_summary["suggested_fixes"]:
                print(f"   Fix: {error_summary['suggested_fixes'][0]}")

        if summary["most_problematic_domains"]:
            print(f"\n🌐 MOST PROBLEMATIC DOMAINS:")
            for domain_info in summary["most_problematic_domains"][:5]:
                print(
                    f"• {domain_info['domain']}: {domain_info['error_count']} errors ({', '.join(domain_info['error_types'])})"
                )

        print(f"\n💡 RECOMMENDATIONS:")
        for recommendation in summary["recommendations"]:
            print(f"• {recommendation}")

        print("\n" + "=" * 60)


# Global instance for easy access
error_reporter = ErrorReporter()


def log_error(error_type: str, message: str, url: Optional[str] = None, **kwargs):
    """Convenience function to log errors."""
    error_reporter.log_error(error_type, message, url, **kwargs)


def generate_error_report(
    save_to_file: bool = True, print_summary: bool = True
) -> Dict[str, Any]:
    """Generate and optionally save/print error report."""
    if print_summary:
        error_reporter.print_summary()

    if save_to_file:
        report_file = error_reporter.save_report()
        print(f"\n📄 Detailed report saved to: {report_file}")

    return error_reporter.generate_summary()


if __name__ == "__main__":
    # Test the error reporter
    error_reporter.log_error(
        "dns_resolution_error",
        "Failed to resolve domain",
        "https://nonexistent.example.com",
    )
    error_reporter.log_error(
        "llm_analysis_failed",
        "Ollama connection timeout",
        context={"model": "llama3.1:latest"},
    )
    error_reporter.log_error(
        "pdf_extraction_failed",
        "Corrupted PDF file",
        "https://example.com/whitepaper.pdf",
    )

    # Generate report
    generate_error_report()
