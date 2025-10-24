"""
Website Analysis Pipeline

This module coordinates the complete website analysis process:
1. Discovery: Find projects that need website analysis
2. Scraping: Extract content from project websites
3. Analysis: Process content with LLM for structured insights
4. Storage: Save results to database with proper change tracking

Follows the strategy from docs/project_analysis_strategy.md
"""

import os
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, UTC, timedelta
from pathlib import Path
import sys
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import and_, or_, select

# Import our modules
from models.database import (
    DatabaseManager,
    CryptoProject,
    ProjectLink,
    LinkContentAnalysis,
    APIUsage,
)
from scrapers.website_scraper import WebsiteScraper, WebsiteAnalysisResult
from analyzers.website_analyzer import WebsiteContentAnalyzer, WebsiteAnalysis

# Load environment variables
config_path = Path(__file__).parent.parent.parent / "config" / "env"
load_dotenv(config_path)


class WebsiteAnalysisPipeline:
    """Complete pipeline for cryptocurrency website analysis."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        scraper_config: Dict = None,
        analyzer_config: Dict = None,
    ):
        """
        Initialize the website analysis pipeline.

        Args:
            db_manager: Database manager instance
            scraper_config: Configuration for website scraper
            analyzer_config: Configuration for LLM analyzer
        """
        self.db_manager = db_manager

        # Initialize scraper
        scraper_config = scraper_config or {}
        self.scraper = WebsiteScraper(
            max_pages=scraper_config.get("max_pages", 10),
            max_depth=scraper_config.get("max_depth", 3),
            delay=scraper_config.get("delay", 1.0),
        )

        # Initialize analyzer
        analyzer_config = analyzer_config or {}
        self.analyzer = WebsiteContentAnalyzer(
            provider=analyzer_config.get("provider", "ollama"),
            model=analyzer_config.get("model", "llama3.1:latest"),
            ollama_base_url=analyzer_config.get(
                "ollama_base_url", "http://localhost:11434"
            ),
        )

        # Analysis settings
        self.max_projects_per_run = 10  # Limit for cost control
        self.min_analysis_interval = timedelta(
            days=7
        )  # Minimum time between re-analysis

    def discover_projects_for_analysis(
        self, limit: int = None
    ) -> List[Tuple[CryptoProject, ProjectLink]]:
        """
        Find cryptocurrency projects that need website analysis.

        Args:
            limit: Maximum number of projects to return

        Returns:
            List of (project, website_link) tuples ready for analysis
        """
        with self.db_manager.get_session() as session:
            # Query for projects with website links that need analysis
            query = (
                session.query(CryptoProject, ProjectLink)
                .join(ProjectLink, CryptoProject.id == ProjectLink.project_id)
                .filter(
                    and_(
                        ProjectLink.link_type == "website",
                        ProjectLink.is_active == True,
                        or_(
                            ProjectLink.needs_analysis == True,
                            ProjectLink.last_scraped.is_(None),
                        ),
                    )
                )
            )

            # Prioritize by market cap (larger projects first) and exclude recently analyzed
            cutoff_time = datetime.now(UTC) - self.min_analysis_interval

            # Check for existing analysis
            analyzed_link_ids = select(LinkContentAnalysis.link_id).filter(
                LinkContentAnalysis.created_at > cutoff_time
            )

            query = query.filter(ProjectLink.id.notin_(analyzed_link_ids)).order_by(
                CryptoProject.market_cap.desc().nullslast(),
                CryptoProject.rank.asc().nullslast(),
            )

            if limit:
                query = query.limit(limit)

            results = query.all()

            logger.info(f"Found {len(results)} projects ready for website analysis")
            return results

    def scrape_and_analyze_website(
        self, project: CryptoProject, website_link: ProjectLink
    ) -> Optional[LinkContentAnalysis]:
        """
        Complete scraping and analysis workflow for a single website.

        Args:
            project: CryptoProject instance
            website_link: ProjectLink for the website

        Returns:
            LinkContentAnalysis instance if successful, None otherwise
        """
        logger.info(
            f"Starting analysis for {project.name} ({project.code}) - {website_link.url}"
        )

        try:
            # Step 1: Scrape the website
            scrape_result = self.scraper.scrape_website(website_link.url)

            if not scrape_result.scrape_success:
                logger.error(
                    f"Scraping failed for {website_link.url}: {scrape_result.error_message}"
                )
                self._update_scrape_status(
                    website_link, success=False, error=scrape_result.error_message
                )
                return None

            # Step 2: Analyze with LLM
            website_analysis = self.analyzer.analyze_website(
                scrape_result.pages_scraped, scrape_result.domain
            )

            if not website_analysis:
                logger.error(f"LLM analysis failed for {website_link.url}")
                self._update_scrape_status(
                    website_link, success=False, error="LLM analysis failed"
                )
                return None

            # Step 3: Store results in database
            analysis_record = self._store_analysis_results(
                website_link, scrape_result, website_analysis
            )

            # Step 4: Update scrape status
            self._update_scrape_status(website_link, success=True)

            # Step 5: Log API usage
            self._log_analysis_usage(website_analysis)

            logger.success(
                f"Analysis complete for {project.name}: Technical depth {website_analysis.technical_depth_score}/10"
            )

            return analysis_record

        except Exception as e:
            logger.error(f"Analysis failed for {project.name}: {e}")
            self._update_scrape_status(website_link, success=False, error=str(e))
            return None

    def _update_scrape_status(
        self, website_link: ProjectLink, success: bool, error: str = None
    ):
        """Update the scrape status for a project link."""
        with self.db_manager.get_session() as session:
            link = session.merge(website_link)
            link.last_scraped = datetime.now(UTC)
            link.scrape_success = success
            link.needs_analysis = False  # Mark as processed

            if not success and error:
                logger.warning(f"Scrape failed for {link.url}: {error}")

            session.commit()

    def _store_analysis_results(
        self,
        website_link: ProjectLink,
        scrape_result: WebsiteAnalysisResult,
        website_analysis: WebsiteAnalysis,
    ) -> LinkContentAnalysis:
        """Store the analysis results in the database."""

        with self.db_manager.get_session() as session:
            # Combine all page content for storage
            combined_content = "\n\n".join(
                [
                    f"=== {page.page_type.upper()}: {page.title} ===\n{page.content}"
                    for page in scrape_result.pages_scraped
                ]
            )

            # Calculate content hash
            content_hash = hashlib.sha256(combined_content.encode()).hexdigest()

            # Check if we already have analysis for this content
            existing = (
                session.query(LinkContentAnalysis)
                .filter(
                    and_(
                        LinkContentAnalysis.link_id == website_link.id,
                        LinkContentAnalysis.content_hash == content_hash,
                    )
                )
                .first()
            )

            if existing:
                logger.info(
                    f"Content unchanged for {website_link.url}, skipping analysis storage"
                )
                return existing

            # Create new analysis record
            analysis_record = LinkContentAnalysis(
                link_id=website_link.id,
                # Content metadata
                raw_content=combined_content[:50000],  # Limit size for database
                content_hash=content_hash,
                page_title=(
                    scrape_result.pages_scraped[0].title
                    if scrape_result.pages_scraped
                    else None
                ),
                pages_analyzed=len(scrape_result.pages_scraped),
                total_word_count=website_analysis.total_word_count,
                # Core technology information
                technology_stack=website_analysis.technology_stack,
                blockchain_platform=website_analysis.blockchain_platform,
                consensus_mechanism=website_analysis.consensus_mechanism,
                # Key value propositions
                core_features=website_analysis.core_features,
                use_cases=website_analysis.use_cases,
                unique_value_proposition=website_analysis.unique_value_proposition,
                target_audience=website_analysis.target_audience,
                # Team and organization
                team_members=website_analysis.team_members,
                founders=website_analysis.founders,
                team_size_estimate=website_analysis.team_size_estimate,
                advisors=website_analysis.advisors,
                # Business information
                partnerships=website_analysis.partnerships,
                investors=website_analysis.investors,
                funding_raised=website_analysis.funding_raised,
                # Development and innovation
                innovations=website_analysis.innovations,
                development_stage=website_analysis.development_stage,
                roadmap_items=website_analysis.roadmap_items,
                # Analysis scores
                technical_depth_score=website_analysis.technical_depth_score,
                marketing_vs_tech_ratio=website_analysis.marketing_vs_tech_ratio,
                content_quality_score=website_analysis.content_quality_score,
                red_flags=website_analysis.red_flags,
                confidence_score=website_analysis.confidence_score,
                # Legacy fields for summary
                summary=website_analysis.unique_value_proposition,
                key_points=(website_analysis.core_features or [])
                + (website_analysis.innovations or []),
                entities=(website_analysis.founders or [])
                + [tm.get("name", "") for tm in (website_analysis.team_members or [])],
                technical_summary=f"Tech stack: {', '.join(website_analysis.technology_stack or [])}. Platform: {website_analysis.blockchain_platform or 'Unknown'}. Stage: {website_analysis.development_stage}",
                # Analysis metadata
                model_used=website_analysis.model_used,
                analysis_version="2.0",
            )

            session.add(analysis_record)
            session.commit()

            logger.success(f"Stored analysis results for {website_link.url}")
            return analysis_record

    def _log_analysis_usage(self, website_analysis: WebsiteAnalysis):
        """Log LLM API usage for cost tracking."""
        with self.db_manager.get_session() as session:
            # Estimate token usage (rough calculation)
            estimated_tokens = int(
                website_analysis.total_word_count // 0.75
            )  # ~0.75 words per token

            usage = APIUsage(
                api_provider=self.analyzer.provider,
                endpoint="website_analysis",
                response_status=200,
                credits_used=1,
                response_size=estimated_tokens,
                response_time=0.0,  # We don't track this currently
            )

            session.add(usage)
            session.commit()

    def run_analysis_batch(self, max_projects: int = None) -> Dict[str, int]:
        """
        Run a batch of website analyses.

        Args:
            max_projects: Maximum number of projects to analyze (None for unlimited)

        Returns:
            Dictionary with analysis statistics
        """
        if max_projects is None:
            logger.info("Starting website analysis batch (processing ALL projects)")
        else:
            max_projects = max_projects or self.max_projects_per_run
            logger.info(
                f"Starting website analysis batch (max {max_projects} projects)"
            )

        # Discover projects for analysis
        projects_to_analyze = self.discover_projects_for_analysis(limit=max_projects)

        if not projects_to_analyze:
            logger.info("No projects need website analysis at this time")
            return {"projects_found": 0, "successful_analyses": 0, "failed_analyses": 0}

        # Process each project
        successful_analyses = 0
        failed_analyses = 0

        for i, (project, website_link) in enumerate(projects_to_analyze):
            logger.info(f"Processing {i+1}/{len(projects_to_analyze)}: {project.name}")

            analysis_result = self.scrape_and_analyze_website(project, website_link)

            if analysis_result:
                successful_analyses += 1
            else:
                failed_analyses += 1

            # Rate limiting between projects
            if i < len(projects_to_analyze) - 1:
                time.sleep(0.5)  # 0.5 seconds between projects

        # Summary
        stats = {
            "projects_found": len(projects_to_analyze),
            "successful_analyses": successful_analyses,
            "failed_analyses": failed_analyses,
        }

        logger.info(
            f"Batch complete: {successful_analyses} successful, {failed_analyses} failed"
        )
        return stats


def main():
    """Run the website analysis pipeline on all projects waiting for analysis."""
    # Initialize database
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/crypto_analytics.db")
    db_manager = DatabaseManager(database_url)

    # Initialize pipeline
    pipeline = WebsiteAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={"max_pages": 5, "max_depth": 2, "delay": 1.0},
        analyzer_config={
            "provider": "ollama",
            "model": "llama3.1:latest",
            "ollama_base_url": "http://localhost:11434",
        },
    )

    # First, check how many projects are waiting for analysis
    projects_waiting = pipeline.discover_projects_for_analysis()
    total_projects = len(projects_waiting)

    if total_projects == 0:
        print("No projects are waiting for website analysis.")
        return

    print(f"Found {total_projects} projects waiting for website analysis.")
    print(
        f"This will take approximately {total_projects * 15 // 60} minutes to complete."
    )

    # Run analysis on all projects (remove the limit)
    logger.info(f"Running website analysis pipeline on all {total_projects} projects")
    stats = pipeline.run_analysis_batch(max_projects=None)  # No limit - process all

    print(f"\n=== Final Analysis Results ===")
    print(f"Projects found: {stats['projects_found']}")
    print(f"Successful analyses: {stats['successful_analyses']}")
    print(f"Failed analyses: {stats['failed_analyses']}")
    print(
        f"Success rate: {stats['successful_analyses']/stats['projects_found']*100:.1f}%"
        if stats["projects_found"] > 0
        else "N/A"
    )


if __name__ == "__main__":
    main()
