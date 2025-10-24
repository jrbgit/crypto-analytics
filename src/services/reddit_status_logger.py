"""
Reddit status logging service for community activity tracking.
Converts Reddit scraping outcomes into structured status data.
"""

from datetime import datetime, UTC
from typing import Optional
from loguru import logger

from src.models.reddit_status import RedditStatusType


class RedditStatusLogger:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def log_reddit_status(
        self,
        link_id: int,
        status_type: str,
        status_message: str = None,
        posts_found: int = 0,
        subscriber_count: Optional[int] = None,
        last_post_date: Optional[datetime] = None,
        error_type: Optional[str] = None,
        error_details: Optional[str] = None,
    ):
        try:
            with self.db_manager.get_session() as session:
                from sqlalchemy import text

                session.execute(
                    text(
                        """
                    INSERT INTO reddit_status_log (
                        link_id, status_type, status_message, posts_found, subscriber_count,
                        last_post_date, error_type, error_details
                    ) VALUES (
                        :link_id, :status_type, :status_message, :posts_found, :subscriber_count,
                        :last_post_date, :error_type, :error_details
                    )
                """
                    ),
                    {
                        "link_id": link_id,
                        "status_type": status_type,
                        "status_message": status_message,
                        "posts_found": posts_found,
                        "subscriber_count": subscriber_count,
                        "last_post_date": last_post_date,
                        "error_type": error_type,
                        "error_details": error_details,
                    },
                )
                session.commit()
                logger.debug(
                    f"Logged reddit status: {status_type} for link_id {link_id}"
                )
        except Exception as e:
            logger.error(f"Failed to log reddit status: {e}")

    def log_inactive(
        self,
        link_id: int,
        url: str,
        recent_days: int,
        subscriber_count: Optional[int] = None,
    ):
        self.log_reddit_status(
            link_id=link_id,
            status_type=RedditStatusType.INACTIVE_90D,
            status_message=f"No recent posts within last {recent_days} days: {url}",
            posts_found=0,
            subscriber_count=subscriber_count,
        )
        logger.info(f"Reddit community inactive ({recent_days}d): {url}")

    def log_success(
        self,
        link_id: int,
        url: str,
        posts_found: int,
        subscriber_count: Optional[int] = None,
    ):
        self.log_reddit_status(
            link_id=link_id,
            status_type=RedditStatusType.SUCCESS,
            status_message=f"Successfully scraped {posts_found} posts from {url}",
            posts_found=posts_found,
            subscriber_count=subscriber_count,
        )
        logger.success(f"Reddit scraping successful: {url} ({posts_found} posts)")

    def log_not_found(
        self,
        link_id: int,
        url: str,
        subreddit_name: str,
        error_details: str,
        error_type: str = "not_found",
    ):
        """Log when a Reddit community cannot be found or accessed."""
        self.log_reddit_status(
            link_id=link_id,
            status_type=RedditStatusType.ERROR,
            status_message=f"Reddit community not found: r/{subreddit_name}",
            posts_found=0,
            error_type=error_type,
            error_details=error_details,
        )
        logger.warning(
            f"Reddit community not found: {url} (r/{subreddit_name}) - {error_details}"
        )

    def log_access_denied(
        self,
        link_id: int,
        url: str,
        subreddit_name: str,
        http_status_code: int,
        error_details: str,
    ):
        """Log when access to a Reddit community is denied (private, restricted, etc.)."""
        self.log_reddit_status(
            link_id=link_id,
            status_type=RedditStatusType.ERROR,
            status_message=f"Access denied to r/{subreddit_name} (HTTP {http_status_code})",
            posts_found=0,
            error_type="access_denied",
            error_details=error_details,
        )
        logger.warning(
            f"Access denied to Reddit community: {url} (r/{subreddit_name}) - {error_details}"
        )

    def log_community_unavailable(
        self, link_id: int, url: str, subreddit_name: str, reason: str
    ):
        """Log when a Reddit community is unavailable (banned, quarantined, etc.)."""
        self.log_reddit_status(
            link_id=link_id,
            status_type=RedditStatusType.ERROR,
            status_message=f"Reddit community unavailable: r/{subreddit_name}",
            posts_found=0,
            error_type="community_unavailable",
            error_details=reason,
        )
        logger.warning(
            f"Reddit community unavailable: {url} (r/{subreddit_name}) - {reason}"
        )


def create_reddit_status_logger(db_manager) -> RedditStatusLogger:
    return RedditStatusLogger(db_manager)
