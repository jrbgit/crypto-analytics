"""
Reddit status tracking models for community activity and accessibility.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class RedditStatusLog(Base):
    """Detailed log of Reddit community status checks and scraping attempts."""

    __tablename__ = "reddit_status_log"

    id = Column(Integer, primary_key=True)
    link_id = Column(Integer, ForeignKey("project_links.id"), nullable=False)

    # Status information
    status_type = Column(
        String(50), nullable=False
    )  # success, inactive_90d, access_denied, not_found, private, rate_limited, error
    status_message = Column(Text)

    # Community details
    posts_found = Column(Integer, default=0)
    subscriber_count = Column(Integer)
    last_post_date = Column(DateTime)

    # Error details
    error_type = Column(String(100))
    error_details = Column(Text)

    # Timestamps
    checked_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    link = relationship("ProjectLink", back_populates="reddit_status_logs")


class RedditStatusType:
    SUCCESS = "success"
    INACTIVE_90D = "inactive_90d"
    ACCESS_DENIED = "access_denied"
    NOT_FOUND = "not_found"
    PRIVATE = "private"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
