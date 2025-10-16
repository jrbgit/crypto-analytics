"""
Website status logging service for comprehensive domain health tracking.
Converts website analysis errors into valuable status data.
"""

import time
from datetime import datetime, UTC
from typing import Optional, Dict, Any
from loguru import logger

# Import models and constants
from src.models.website_status import WebsiteStatusType, WebsiteErrorType


class WebsiteStatusLogger:
    """Service for logging website status and health information."""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    def log_website_status(
        self,
        link_id: int,
        status_type: str,
        status_message: str = None,
        pages_attempted: int = 0,
        pages_successful: int = 0,
        pages_parked: int = 0,
        total_content_length: int = 0,
        http_status_code: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        dns_resolved: Optional[bool] = None,
        ssl_valid: Optional[bool] = None,
        has_robots_txt: Optional[bool] = None,
        robots_allows_scraping: Optional[bool] = None,
        detected_cms: Optional[str] = None,
        detected_parking_service: Optional[str] = None,
        error_type: Optional[str] = None,
        error_details: Optional[str] = None
    ):
        """Log comprehensive website status information."""
        
        try:
            with self.db_manager.get_session() as session:
                from sqlalchemy import text
                # Insert into website_status_log table
                session.execute(text("""
                    INSERT INTO website_status_log (
                        link_id, status_type, status_message, pages_attempted, pages_successful,
                        pages_parked, total_content_length, http_status_code, response_time_ms,
                        dns_resolved, ssl_valid, has_robots_txt, robots_allows_scraping,
                        detected_cms, detected_parking_service, error_type, error_details
                    ) VALUES (
                        :link_id, :status_type, :status_message, :pages_attempted, :pages_successful,
                        :pages_parked, :total_content_length, :http_status_code, :response_time_ms,
                        :dns_resolved, :ssl_valid, :has_robots_txt, :robots_allows_scraping,
                        :detected_cms, :detected_parking_service, :error_type, :error_details
                    )
                """), {
                    'link_id': link_id, 'status_type': status_type, 'status_message': status_message, 
                    'pages_attempted': pages_attempted, 'pages_successful': pages_successful,
                    'pages_parked': pages_parked, 'total_content_length': total_content_length, 
                    'http_status_code': http_status_code, 'response_time_ms': response_time_ms,
                    'dns_resolved': dns_resolved, 'ssl_valid': ssl_valid, 'has_robots_txt': has_robots_txt, 
                    'robots_allows_scraping': robots_allows_scraping, 'detected_cms': detected_cms, 
                    'detected_parking_service': detected_parking_service, 'error_type': error_type, 
                    'error_details': error_details
                })
                
                # Update current status in project_links
                self._update_link_current_status(session, link_id, status_type)
                
                session.commit()
                
                logger.debug(f"Logged website status: {status_type} for link_id {link_id}")
                
        except Exception as e:
            logger.error(f"Failed to log website status: {e}")
    
    def _update_link_current_status(self, session, link_id: int, status_type: str):
        """Update the current status in project_links table."""
        
        # Determine if this is a failure
        is_failure = status_type in [
            WebsiteStatusType.PARKED_DOMAIN,
            WebsiteStatusType.DNS_FAILURE, 
            WebsiteStatusType.SERVER_ERROR,
            WebsiteStatusType.TIMEOUT,
            WebsiteStatusType.CONTENT_ERROR,
            WebsiteStatusType.SSL_ERROR,
            WebsiteStatusType.CONNECTION_ERROR,
            WebsiteStatusType.UNKNOWN_ERROR
        ]
        
        from sqlalchemy import text
        
        if is_failure:
            # Increment consecutive failures
            session.execute(text("""
                UPDATE project_links 
                SET current_website_status = :status_type,
                    last_status_check = NOW(),
                    consecutive_failures = consecutive_failures + 1,
                    first_failure_date = COALESCE(first_failure_date, NOW()),
                    domain_parked_detected = CASE WHEN :status_type2 = 'parked_domain' THEN TRUE ELSE domain_parked_detected END,
                    robots_txt_blocks_scraping = CASE WHEN :status_type3 = 'robots_blocked' THEN TRUE ELSE robots_txt_blocks_scraping END
                WHERE id = :link_id
            """), {'status_type': status_type, 'status_type2': status_type, 'status_type3': status_type, 'link_id': link_id})
        else:
            # Reset failure counters on success
            session.execute(text("""
                UPDATE project_links 
                SET current_website_status = :status_type,
                    last_status_check = NOW(),
                    consecutive_failures = 0,
                    first_failure_date = NULL,
                    robots_txt_blocks_scraping = CASE WHEN :status_type2 = 'robots_blocked' THEN TRUE ELSE FALSE END
                WHERE id = :link_id
            """), {'status_type': status_type, 'status_type2': status_type, 'link_id': link_id})
    
    def log_robots_blocked(self, link_id: int, url: str, robots_message: str = None):
        """Log when robots.txt blocks scraping - this is NOT an error."""
        
        self.log_website_status(
            link_id=link_id,
            status_type=WebsiteStatusType.ROBOTS_BLOCKED,
            status_message=f"Robots.txt disallows scraping for {url}",
            has_robots_txt=True,
            robots_allows_scraping=False,
            error_details=robots_message
        )
        
        logger.info(f"Website respects robots.txt: {url} (link_id: {link_id})")
    
    def log_parked_domain(self, link_id: int, url: str, parking_service: str = None):
        """Log when domain is detected as parked/for-sale."""
        
        self.log_website_status(
            link_id=link_id,
            status_type=WebsiteStatusType.PARKED_DOMAIN,
            status_message=f"Domain appears to be parked/for-sale: {url}",
            detected_parking_service=parking_service,
            pages_attempted=1,
            pages_parked=1
        )
        
        logger.warning(f"Parked domain detected: {url} (link_id: {link_id})")
    
    def log_scraping_success(
        self, 
        link_id: int, 
        url: str, 
        pages_scraped: int,
        total_content_length: int,
        response_time_ms: int = None,
        detected_cms: str = None
    ):
        """Log successful website scraping."""
        
        self.log_website_status(
            link_id=link_id,
            status_type=WebsiteStatusType.SUCCESS,
            status_message=f"Successfully scraped {pages_scraped} pages from {url}",
            pages_attempted=pages_scraped,
            pages_successful=pages_scraped,
            total_content_length=total_content_length,
            response_time_ms=response_time_ms,
            detected_cms=detected_cms
        )
        
        logger.success(f"Website scraping successful: {url} ({pages_scraped} pages)")
    
    def log_content_error(self, link_id: int, url: str, error_message: str, error_type: str = None):
        """Log content processing errors (like NUL characters)."""
        
        # Determine specific error type
        if "NUL" in error_message or "0x00" in error_message:
            error_type = WebsiteErrorType.NUL_CHARACTER_ERROR
        elif "encoding" in error_message.lower():
            error_type = WebsiteErrorType.ENCODING_ERROR
        else:
            error_type = error_type or WebsiteErrorType.CONTENT_CORRUPTION
            
        self.log_website_status(
            link_id=link_id,
            status_type=WebsiteStatusType.CONTENT_ERROR,
            status_message=f"Content processing error for {url}",
            error_type=error_type,
            error_details=error_message
        )
        
        logger.warning(f"Content processing error: {url} - {error_message[:100]}...")
    
    def log_connection_error(self, link_id: int, url: str, error_message: str):
        """Log connection/network errors."""
        
        self.log_website_status(
            link_id=link_id,
            status_type=WebsiteStatusType.CONNECTION_ERROR,
            status_message=f"Connection failed for {url}",
            error_type=WebsiteErrorType.CONNECTION_ERROR,
            error_details=error_message,
            dns_resolved=False
        )
        
        logger.error(f"Connection error: {url} - {error_message}")
    
    def log_dns_error(self, link_id: int, url: str, error_message: str = None):
        """Log DNS resolution failures - quieter logging since domain may not exist."""
        
        self.log_website_status(
            link_id=link_id,
            status_type=WebsiteStatusType.DNS_FAILURE,
            status_message=f"DNS resolution failed for {url}",
            error_type=WebsiteErrorType.DNS_RESOLUTION_ERROR,
            error_details=error_message or "Domain not found",
            dns_resolved=False
        )
        
        logger.debug(f"DNS resolution failed: {url} - domain may not exist")
    
    def log_ssl_error(self, link_id: int, url: str, error_message: str = None):
        """Log SSL certificate errors - quieter logging since cert may be expired/invalid."""
        
        self.log_website_status(
            link_id=link_id,
            status_type=WebsiteStatusType.SSL_ERROR,
            status_message=f"SSL certificate error for {url}",
            error_type=WebsiteErrorType.SSL_CERTIFICATE_ERROR,
            error_details=error_message or "Certificate invalid or expired",
            ssl_valid=False
        )
        
        logger.debug(f"SSL certificate error: {url} - certificate invalid or expired")
    
    def log_no_pages_scraped(self, link_id: int, url: str, reason: str = None):
        """Log when no pages could be scraped (but without treating as error)."""
        
        self.log_website_status(
            link_id=link_id,
            status_type=WebsiteStatusType.SERVER_ERROR,
            status_message=f"No pages could be scraped from {url}",
            pages_attempted=1,
            pages_successful=0,
            error_details=reason
        )
        
        logger.info(f"No pages scraped: {url} - {reason or 'Unknown reason'}")
    
    def get_website_health_summary(self, project_id: int = None) -> Dict[str, Any]:
        """Get a summary of website health status."""
        
        try:
            with self.db_manager.get_session() as session:
                from sqlalchemy import text
                
                if project_id:
                    # Get status for specific project
                    result = session.execute(text("""
                        SELECT 
                            current_website_status,
                            COUNT(*) as count,
                            AVG(consecutive_failures) as avg_failures
                        FROM project_links pl
                        JOIN crypto_projects cp ON pl.project_id = cp.id
                        WHERE cp.id = :project_id AND pl.link_type = 'website'
                        GROUP BY current_website_status
                    """), {'project_id': project_id})
                else:
                    # Get overall status summary
                    result = session.execute(text("""
                        SELECT 
                            current_website_status,
                            COUNT(*) as count,
                            AVG(consecutive_failures) as avg_failures
                        FROM project_links 
                        WHERE link_type = 'website'
                        GROUP BY current_website_status
                    """))
                
                summary = {}
                for row in result:
                    summary[row[0]] = {
                        'count': row[1],
                        'avg_consecutive_failures': float(row[2] or 0)
                    }
                
                return summary
                
        except Exception as e:
            logger.error(f"Failed to get website health summary: {e}")
            return {}


def create_status_logger(db_manager) -> WebsiteStatusLogger:
    """Factory function to create a website status logger."""
    return WebsiteStatusLogger(db_manager)