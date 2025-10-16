"""
Website status tracking models for comprehensive domain health monitoring.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class WebsiteStatusLog(Base):
    """Detailed log of website status checks and scraping attempts."""
    
    __tablename__ = 'website_status_log'
    
    id = Column(Integer, primary_key=True)
    link_id = Column(Integer, ForeignKey('project_links.id'), nullable=False)
    
    # Status information
    status_type = Column(String(50), nullable=False)  # success, robots_blocked, parked_domain, etc.
    status_message = Column(Text)  # Detailed status message
    
    # Scraping results
    pages_attempted = Column(Integer, default=0)
    pages_successful = Column(Integer, default=0) 
    pages_parked = Column(Integer, default=0)  # Parked/for-sale pages detected
    total_content_length = Column(Integer, default=0)
    
    # HTTP/Network details
    http_status_code = Column(Integer)
    response_time_ms = Column(Integer)
    dns_resolved = Column(Boolean)
    ssl_valid = Column(Boolean)
    
    # Content analysis
    has_robots_txt = Column(Boolean)
    robots_allows_scraping = Column(Boolean)
    detected_cms = Column(String(100))  # WordPress, Squarespace, etc.
    detected_parking_service = Column(String(100))  # GoDaddy, Sedo, etc.
    
    # Error details
    error_type = Column(String(100))  # connection_error, parse_error, etc.
    error_details = Column(Text)
    
    # Timestamps
    checked_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    link = relationship("ProjectLink", back_populates="status_logs")


# Update the ProjectLink model by adding this to the existing model
"""
Add these fields to the existing ProjectLink class in database.py:

# Website status tracking
current_website_status = Column(String(50), default='unknown')
last_status_check = Column(DateTime)
consecutive_failures = Column(Integer, default=0)
first_failure_date = Column(DateTime)
domain_parked_detected = Column(Boolean, default=False)
robots_txt_blocks_scraping = Column(Boolean, default=False)

# Add this relationship
status_logs = relationship("WebsiteStatusLog", back_populates="link", cascade="all, delete-orphan")
"""


class WebsiteStatusType:
    """Constants for website status types."""
    
    SUCCESS = 'success'
    ROBOTS_BLOCKED = 'robots_blocked'
    PARKED_DOMAIN = 'parked_domain'
    DNS_FAILURE = 'dns_failure'
    SERVER_ERROR = 'server_error'
    TIMEOUT = 'timeout'
    CONTENT_ERROR = 'content_error'
    SSL_ERROR = 'ssl_error'
    CONNECTION_ERROR = 'connection_error'
    UNKNOWN_ERROR = 'unknown_error'


class WebsiteErrorType:
    """Constants for website error types."""
    
    CONNECTION_ERROR = 'connection_error'
    PARSE_ERROR = 'parse_error'
    CONTENT_CORRUPTION = 'content_corruption'
    NUL_CHARACTER_ERROR = 'nul_character_error'
    ENCODING_ERROR = 'encoding_error'
    TIMEOUT_ERROR = 'timeout_error'
    SSL_CERTIFICATE_ERROR = 'ssl_certificate_error'
    DNS_RESOLUTION_ERROR = 'dns_resolution_error'