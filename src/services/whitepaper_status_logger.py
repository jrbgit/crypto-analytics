"""
Whitepaper status logging service for comprehensive document health tracking.
Converts whitepaper extraction errors into valuable status data.
"""

import time
import hashlib
from datetime import datetime, UTC
from typing import Optional, Dict, Any
from loguru import logger

# Import models and constants
from src.models.whitepaper_status import WhitepaperStatusType, WhitepaperErrorType


class WhitepaperStatusLogger:
    """Service for logging whitepaper status and health information."""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def log_whitepaper_status(
        self,
        link_id: int,
        status_type: str,
        status_message: str = None,
        document_type: str = None,
        document_size_bytes: Optional[int] = None,
        pages_extracted: Optional[int] = None,
        word_count: int = 0,
        http_status_code: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        dns_resolved: Optional[bool] = None,
        ssl_valid: Optional[bool] = None,
        extraction_method: Optional[str] = None,
        extraction_success: Optional[bool] = None,
        content_quality_score: Optional[int] = None,
        has_meaningful_content: Optional[bool] = None,
        min_word_threshold_met: Optional[bool] = None,
        detected_language: Optional[str] = None,
        detected_format: Optional[str] = None,
        requires_authentication: Optional[bool] = None,
        behind_paywall: Optional[bool] = None,
        cloudflare_protected: Optional[bool] = None,
        javascript_required: Optional[bool] = None,
        error_type: Optional[str] = None,
        error_details: Optional[str] = None,
        file_hash: Optional[str] = None,
    ):
        """Log comprehensive whitepaper status information."""

        try:
            with self.db_manager.get_session() as session:
                from sqlalchemy import text

                # Insert into whitepaper_status_log table
                session.execute(
                    text(
                        """
                    INSERT INTO whitepaper_status_log (
                        link_id, status_type, status_message, document_type, document_size_bytes,
                        pages_extracted, word_count, http_status_code, response_time_ms,
                        dns_resolved, ssl_valid, extraction_method, extraction_success,
                        content_quality_score, has_meaningful_content, min_word_threshold_met,
                        detected_language, detected_format, requires_authentication, behind_paywall,
                        cloudflare_protected, javascript_required, error_type, error_details, file_hash
                    ) VALUES (
                        :link_id, :status_type, :status_message, :document_type, :document_size_bytes,
                        :pages_extracted, :word_count, :http_status_code, :response_time_ms,
                        :dns_resolved, :ssl_valid, :extraction_method, :extraction_success,
                        :content_quality_score, :has_meaningful_content, :min_word_threshold_met,
                        :detected_language, :detected_format, :requires_authentication, :behind_paywall,
                        :cloudflare_protected, :javascript_required, :error_type, :error_details, :file_hash
                    )
                """
                    ),
                    {
                        "link_id": link_id,
                        "status_type": status_type,
                        "status_message": status_message,
                        "document_type": document_type,
                        "document_size_bytes": document_size_bytes,
                        "pages_extracted": pages_extracted,
                        "word_count": word_count,
                        "http_status_code": http_status_code,
                        "response_time_ms": response_time_ms,
                        "dns_resolved": dns_resolved,
                        "ssl_valid": ssl_valid,
                        "extraction_method": extraction_method,
                        "extraction_success": extraction_success,
                        "content_quality_score": content_quality_score,
                        "has_meaningful_content": has_meaningful_content,
                        "min_word_threshold_met": min_word_threshold_met,
                        "detected_language": detected_language,
                        "detected_format": detected_format,
                        "requires_authentication": requires_authentication,
                        "behind_paywall": behind_paywall,
                        "cloudflare_protected": cloudflare_protected,
                        "javascript_required": javascript_required,
                        "error_type": error_type,
                        "error_details": error_details,
                        "file_hash": file_hash,
                    },
                )

                # Update current status in project_links
                self._update_link_current_status(
                    session, link_id, status_type, document_type
                )

                session.commit()

                logger.debug(
                    f"Logged whitepaper status: {status_type} for link_id {link_id}"
                )

        except Exception as e:
            logger.error(f"Failed to log whitepaper status: {e}")

    def _update_link_current_status(
        self, session, link_id: int, status_type: str, document_type: str = None
    ):
        """Update the current whitepaper status in project_links table."""

        # Determine if this is a failure
        is_failure = status_type in [
            WhitepaperStatusType.ACCESS_DENIED,
            WhitepaperStatusType.NOT_FOUND,
            WhitepaperStatusType.AUTHENTICATION_REQUIRED,
            WhitepaperStatusType.INSUFFICIENT_CONTENT,
            WhitepaperStatusType.NO_CONTENT_EXTRACTED,
            WhitepaperStatusType.DNS_FAILURE,
            WhitepaperStatusType.SERVER_ERROR,
            WhitepaperStatusType.TIMEOUT,
            WhitepaperStatusType.SSL_ERROR,
            WhitepaperStatusType.CONNECTION_ERROR,
            WhitepaperStatusType.PDF_EXTRACTION_FAILED,
            WhitepaperStatusType.WEBPAGE_PARSING_FAILED,
            WhitepaperStatusType.UNKNOWN_ERROR,
        ]

        from sqlalchemy import text

        if is_failure:
            # Increment consecutive failures
            session.execute(
                text(
                    """
                UPDATE project_links 
                SET current_whitepaper_status = :status_type,
                    last_whitepaper_check = NOW(),
                    whitepaper_consecutive_failures = whitepaper_consecutive_failures + 1,
                    whitepaper_first_failure_date = COALESCE(whitepaper_first_failure_date, NOW()),
                    whitepaper_access_restricted = CASE WHEN :status_type2 IN ('access_denied', 'authentication_required', 'paywall_detected') THEN TRUE ELSE whitepaper_access_restricted END,
                    whitepaper_format_detected = COALESCE(:document_type, whitepaper_format_detected)
                WHERE id = :link_id
            """
                ),
                {
                    "status_type": status_type,
                    "status_type2": status_type,
                    "document_type": document_type,
                    "link_id": link_id,
                },
            )
        else:
            # Reset failure counters on success
            session.execute(
                text(
                    """
                UPDATE project_links 
                SET current_whitepaper_status = :status_type,
                    last_whitepaper_check = NOW(),
                    whitepaper_consecutive_failures = 0,
                    whitepaper_first_failure_date = NULL,
                    whitepaper_last_successful_extraction = NOW(),
                    whitepaper_format_detected = COALESCE(:document_type, whitepaper_format_detected)
                WHERE id = :link_id
            """
                ),
                {
                    "status_type": status_type,
                    "document_type": document_type,
                    "link_id": link_id,
                },
            )

    def log_extraction_success(
        self,
        link_id: int,
        url: str,
        document_type: str,
        word_count: int,
        pages_extracted: int = None,
        extraction_method: str = None,
        document_size_bytes: int = None,
        response_time_ms: int = None,
        file_hash: str = None,
    ):
        """Log successful whitepaper extraction."""

        # Determine specific success type
        if document_type == "pdf":
            status_type = WhitepaperStatusType.PDF_EXTRACTION_SUCCESS
        else:
            status_type = WhitepaperStatusType.WEBPAGE_EXTRACTION_SUCCESS

        # Calculate content quality score based on word count
        if word_count >= 1000:
            content_quality = 10
        elif word_count >= 500:
            content_quality = 8
        elif word_count >= 200:
            content_quality = 6
        elif word_count >= 100:
            content_quality = 4
        elif word_count >= 20:
            content_quality = 2
        else:
            content_quality = 1

        self.log_whitepaper_status(
            link_id=link_id,
            status_type=status_type,
            status_message=f"Successfully extracted {word_count} words from {document_type} document: {url}",
            document_type=document_type,
            document_size_bytes=document_size_bytes,
            pages_extracted=pages_extracted,
            word_count=word_count,
            extraction_method=extraction_method,
            extraction_success=True,
            content_quality_score=content_quality,
            has_meaningful_content=word_count >= 20,
            min_word_threshold_met=word_count >= 20,
            response_time_ms=response_time_ms,
            file_hash=file_hash,
        )

        logger.success(f"Whitepaper extraction successful: {url} ({word_count} words)")

    def log_access_denied(
        self, link_id: int, url: str, http_status_code: int, error_details: str = None
    ):
        """Log when whitepaper access is denied (403, 401, etc.)."""

        if http_status_code == 401:
            status_type = WhitepaperStatusType.AUTHENTICATION_REQUIRED
            message = f"Authentication required to access whitepaper: {url}"
        else:
            status_type = WhitepaperStatusType.ACCESS_DENIED
            message = f"Access denied ({http_status_code}) to whitepaper: {url}"

        self.log_whitepaper_status(
            link_id=link_id,
            status_type=status_type,
            status_message=message,
            http_status_code=http_status_code,
            extraction_success=False,
            requires_authentication=http_status_code == 401,
            error_type=WhitepaperErrorType.ACCESS_FORBIDDEN,
            error_details=error_details,
        )

        logger.warning(f"Whitepaper access denied: {url} ({http_status_code})")

    def log_not_found(self, link_id: int, url: str, error_details: str = None):
        """Log when whitepaper is not found (404)."""

        self.log_whitepaper_status(
            link_id=link_id,
            status_type=WhitepaperStatusType.NOT_FOUND,
            status_message=f"Whitepaper not found (404): {url}",
            http_status_code=404,
            extraction_success=False,
            error_type=WhitepaperErrorType.ACCESS_FORBIDDEN,
            error_details=error_details,
        )

        logger.warning(f"Whitepaper not found: {url}")

    def log_insufficient_content(
        self,
        link_id: int,
        url: str,
        word_count: int,
        document_type: str,
        extraction_method: str = None,
    ):
        """Log when insufficient content is extracted (<20 words)."""

        self.log_whitepaper_status(
            link_id=link_id,
            status_type=WhitepaperStatusType.INSUFFICIENT_CONTENT,
            status_message=f"Insufficient content extracted from {url}: {word_count} words (minimum 20 required)",
            document_type=document_type,
            word_count=word_count,
            extraction_method=extraction_method,
            extraction_success=False,
            has_meaningful_content=False,
            min_word_threshold_met=False,
            javascript_required=document_type == "webpage",  # Likely JS-heavy site
            error_type=WhitepaperErrorType.MINIMAL_CONTENT,
            error_details=f"Only {word_count} words extracted, likely dynamic content or access restrictions",
        )

        logger.warning(f"Insufficient whitepaper content: {url} ({word_count} words)")

    def log_pdf_extraction_failed(
        self,
        link_id: int,
        url: str,
        error_message: str,
        document_size_bytes: int = None,
    ):
        """Log when PDF extraction fails."""

        # Categorize PDF error
        if "password" in error_message.lower() or "encrypted" in error_message.lower():
            error_type = WhitepaperErrorType.PDF_PASSWORD_PROTECTED
            status_message = f"PDF is password protected: {url}"
        elif "corrupted" in error_message.lower() or "invalid" in error_message.lower():
            error_type = WhitepaperErrorType.PDF_CORRUPTED
            status_message = f"PDF file is corrupted or invalid: {url}"
        else:
            error_type = WhitepaperErrorType.PDF_EXTRACTION_ERROR
            status_message = f"PDF extraction failed for: {url}"

        self.log_whitepaper_status(
            link_id=link_id,
            status_type=WhitepaperStatusType.PDF_EXTRACTION_FAILED,
            status_message=status_message,
            document_type="pdf",
            document_size_bytes=document_size_bytes,
            extraction_success=False,
            error_type=error_type,
            error_details=error_message,
        )

        logger.warning(f"PDF extraction failed: {url} - {error_message[:100]}...")

    def log_connection_error(self, link_id: int, url: str, error_message: str):
        """Log connection/network errors."""

        # Categorize connection error
        if "timeout" in error_message.lower():
            status_type = WhitepaperStatusType.TIMEOUT
            error_type = WhitepaperErrorType.TIMEOUT_ERROR
        elif "dns" in error_message.lower() or "getaddrinfo" in error_message.lower():
            status_type = WhitepaperStatusType.DNS_FAILURE
            error_type = WhitepaperErrorType.DNS_RESOLUTION_ERROR
        elif "ssl" in error_message.lower() or "certificate" in error_message.lower():
            status_type = WhitepaperStatusType.SSL_ERROR
            error_type = WhitepaperErrorType.SSL_CERTIFICATE_ERROR
        else:
            status_type = WhitepaperStatusType.CONNECTION_ERROR
            error_type = WhitepaperErrorType.CONNECTION_ERROR

        self.log_whitepaper_status(
            link_id=link_id,
            status_type=status_type,
            status_message=f"Connection failed for whitepaper: {url}",
            extraction_success=False,
            error_type=error_type,
            error_details=error_message,
        )

        logger.warning(f"Whitepaper connection error: {url} - {error_message[:100]}...")


def create_whitepaper_status_logger(db_manager):
    """Factory function to create a WhitepaperStatusLogger instance."""
    return WhitepaperStatusLogger(db_manager)
