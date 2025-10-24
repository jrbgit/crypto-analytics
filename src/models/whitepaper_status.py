"""
Whitepaper status tracking models for comprehensive document health monitoring.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class WhitepaperStatusLog(Base):
    """Detailed log of whitepaper status checks and extraction attempts."""

    __tablename__ = "whitepaper_status_log"

    id = Column(Integer, primary_key=True)
    link_id = Column(Integer, ForeignKey("project_links.id"), nullable=False)

    # Status information
    status_type = Column(
        String(50), nullable=False
    )  # success, access_denied, not_found, etc.
    status_message = Column(Text)  # Detailed status message

    # Document details
    document_type = Column(String(20))  # pdf, webpage, doc, etc.
    document_size_bytes = Column(Integer)
    pages_extracted = Column(Integer)
    word_count = Column(Integer, default=0)

    # HTTP/Network details
    http_status_code = Column(Integer)
    response_time_ms = Column(Integer)
    dns_resolved = Column(Boolean)
    ssl_valid = Column(Boolean)

    # Extraction details
    extraction_method = Column(String(50))  # pymupdf, pdfplumber, beautifulsoup, etc.
    extraction_success = Column(Boolean)
    content_quality_score = Column(Integer)  # 1-10 based on content completeness

    # Document analysis
    has_meaningful_content = Column(Boolean)
    min_word_threshold_met = Column(Boolean)
    detected_language = Column(String(10))
    detected_format = Column(String(50))  # academic_paper, wiki, blog_post, etc.

    # Access and security
    requires_authentication = Column(Boolean)
    behind_paywall = Column(Boolean)
    cloudflare_protected = Column(Boolean)
    javascript_required = Column(Boolean)

    # Error details
    error_type = Column(String(100))  # pdf_extraction_error, access_denied, etc.
    error_details = Column(Text)

    # Processing metadata
    file_hash = Column(String(64))  # SHA256 hash of original document
    processed_at = Column(DateTime, default=datetime.utcnow)

    # Timestamps
    checked_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    link = relationship("ProjectLink", back_populates="whitepaper_status_logs")


# Update the ProjectLink model by adding these fields to the existing model
"""
Add these fields to the existing ProjectLink class in database.py:

# Whitepaper status tracking
current_whitepaper_status = Column(String(50), default='unknown')
last_whitepaper_check = Column(DateTime)
whitepaper_consecutive_failures = Column(Integer, default=0)
whitepaper_first_failure_date = Column(DateTime)
whitepaper_access_restricted = Column(Boolean, default=False)
whitepaper_format_detected = Column(String(20))  # pdf, webpage, etc.
whitepaper_last_successful_extraction = Column(DateTime)

# Add this relationship
whitepaper_status_logs = relationship("WhitepaperStatusLog", back_populates="link", cascade="all, delete-orphan")
"""


class WhitepaperStatusType:
    """Constants for whitepaper status types."""

    SUCCESS = "success"
    PDF_EXTRACTION_SUCCESS = "pdf_extraction_success"
    WEBPAGE_EXTRACTION_SUCCESS = "webpage_extraction_success"

    # Access issues
    ACCESS_DENIED = "access_denied"  # 403 Forbidden
    NOT_FOUND = "not_found"  # 404 Not Found
    AUTHENTICATION_REQUIRED = "authentication_required"  # 401
    PAYWALL_DETECTED = "paywall_detected"

    # Content issues
    INSUFFICIENT_CONTENT = "insufficient_content"  # <20 words extracted
    NO_CONTENT_EXTRACTED = "no_content_extracted"  # 0 words
    DYNAMIC_CONTENT = "dynamic_content"  # JavaScript-heavy, requires rendering
    CORRUPTED_DOCUMENT = "corrupted_document"

    # Technical issues
    DNS_FAILURE = "dns_failure"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    SSL_ERROR = "ssl_error"
    CONNECTION_ERROR = "connection_error"

    # Document format issues
    UNSUPPORTED_FORMAT = "unsupported_format"
    PDF_EXTRACTION_FAILED = "pdf_extraction_failed"
    WEBPAGE_PARSING_FAILED = "webpage_parsing_failed"

    # Unknown/other
    UNKNOWN_ERROR = "unknown_error"


class WhitepaperErrorType:
    """Constants for whitepaper error types."""

    # PDF-specific errors
    PDF_EXTRACTION_ERROR = "pdf_extraction_error"
    PDF_CORRUPTED = "pdf_corrupted"
    PDF_PASSWORD_PROTECTED = "pdf_password_protected"
    PDF_NO_TEXT_CONTENT = "pdf_no_text_content"

    # Webpage-specific errors
    WEBPAGE_PARSING_ERROR = "webpage_parsing_error"
    JAVASCRIPT_REQUIRED = "javascript_required"
    MINIMAL_CONTENT = "minimal_content"
    DYNAMIC_LOADING = "dynamic_loading"

    # Access errors
    ACCESS_FORBIDDEN = "access_forbidden"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMITED = "rate_limited"
    CLOUDFLARE_BLOCKED = "cloudflare_blocked"

    # Network errors
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    SSL_CERTIFICATE_ERROR = "ssl_certificate_error"
    DNS_RESOLUTION_ERROR = "dns_resolution_error"

    # Content processing errors
    ENCODING_ERROR = "encoding_error"
    CONTENT_CORRUPTION = "content_corruption"
    NUL_CHARACTER_ERROR = "nul_character_error"
    FILE_TOO_LARGE = "file_too_large"
