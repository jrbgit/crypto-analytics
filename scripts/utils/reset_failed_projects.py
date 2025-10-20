#!/usr/bin/env python3
"""
Reset Failed Projects Utility

This script allows manual intervention to reset failure counts and retry delays
for specific projects, domains, or link types. This is useful when:

1. External issues have been resolved (e.g., websites came back online)
2. DNS or network issues were temporary
3. You want to force retry of specific projects
4. Testing changes to scraping logic

Usage examples:
    python reset_failed_projects.py --all                           # Reset all failures
    python reset_failed_projects.py --domain "bitcoin.org"          # Reset specific domain
    python reset_failed_projects.py --project-code "BTC"            # Reset specific project
    python reset_failed_projects.py --link-type "whitepaper"        # Reset all whitepapers
    python reset_failed_projects.py --failures-gte 3               # Reset projects with 3+ failures
    python reset_failed_projects.py --list-failed --failures-gte 3  # Just list, don't reset
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths, get_config_path

# Set up project paths
project_root = setup_project_paths()

from src.models.database import DatabaseManager, CryptoProject, ProjectLink
from dotenv import load_dotenv
from sqlalchemy import and_, or_

# Load environment variables
load_dotenv(get_config_path() / ".env")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Reset failure counts and retry delays for crypto project links',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --all                              # Reset all failed projects
  %(prog)s --domain "bitcoin.org"             # Reset specific domain
  %(prog)s --project-code "BTC"               # Reset Bitcoin project
  %(prog)s --link-type "whitepaper"           # Reset all whitepapers
  %(prog)s --failures-gte 3                  # Reset projects with 3+ failures
  %(prog)s --list-failed --failures-gte 2    # List projects with 2+ failures
  %(prog)s --dry-run --all                   # Show what would be reset
        '''
    )
    
    # Selection criteria (at least one required)
    selection = parser.add_argument_group('selection criteria')
    selection.add_argument(
        '--all', 
        action='store_true', 
        help='Reset all failed projects'
    )
    selection.add_argument(
        '--domain', 
        type=str, 
        help='Reset projects matching specific domain (e.g., "bitcoin.org")'
    )
    selection.add_argument(
        '--project-code', 
        type=str, 
        help='Reset specific project by code (e.g., "BTC", "ETH")'
    )
    selection.add_argument(
        '--link-type', 
        type=str, 
        choices=['website', 'whitepaper', 'medium', 'reddit', 'youtube'],
        help='Reset all projects of specific link type'
    )
    selection.add_argument(
        '--failures-gte', 
        type=int, 
        help='Reset projects with consecutive failures >= this number'
    )
    selection.add_argument(
        '--url-contains', 
        type=str, 
        help='Reset projects whose URL contains this string'
    )
    
    # Actions
    parser.add_argument(
        '--list-failed', 
        action='store_true', 
        help='List failed projects instead of resetting them'
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Show what would be reset without making changes'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true', 
        help='Show detailed information'
    )
    
    return parser.parse_args()


def get_domain_from_url(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return url.lower()


def build_query_filters(args, session):
    """Build SQLAlchemy filters based on command line arguments."""
    filters = []
    
    if args.domain:
        # Filter by domain in URL
        domain_filter = ProjectLink.url.ilike(f'%{args.domain}%')
        filters.append(domain_filter)
    
    if args.project_code:
        # Join with CryptoProject to filter by code
        filters.append(CryptoProject.code.ilike(args.project_code))
    
    if args.link_type:
        filters.append(ProjectLink.link_type == args.link_type)
    
    if args.url_contains:
        filters.append(ProjectLink.url.ilike(f'%{args.url_contains}%'))
    
    if args.failures_gte is not None:
        # Filter by failure count (handle both whitepaper and general failures)
        failure_filter = or_(
            and_(
                ProjectLink.link_type == 'whitepaper',
                ProjectLink.whitepaper_consecutive_failures >= args.failures_gte
            ),
            and_(
                ProjectLink.link_type != 'whitepaper',
                ProjectLink.consecutive_failures >= args.failures_gte
            )
        )
        filters.append(failure_filter)
    
    if not args.all and not filters:
        # If no specific criteria provided, show failed projects only
        failure_exists_filter = or_(
            and_(
                ProjectLink.link_type == 'whitepaper',
                ProjectLink.whitepaper_consecutive_failures > 0
            ),
            and_(
                ProjectLink.link_type != 'whitepaper',
                ProjectLink.consecutive_failures > 0
            ),
            ProjectLink.scrape_success == False
        )
        filters.append(failure_exists_filter)
    
    return filters


def format_project_info(project: CryptoProject, link: ProjectLink, verbose: bool = False) -> str:
    """Format project information for display."""
    # Get failure count
    if link.link_type == 'whitepaper':
        failure_count = link.whitepaper_consecutive_failures or 0
        first_failure = link.whitepaper_first_failure_date
    else:
        failure_count = link.consecutive_failures or 0
        first_failure = link.first_failure_date
    
    # Basic info
    domain = get_domain_from_url(link.url)
    last_scraped = link.last_scraped.strftime('%Y-%m-%d %H:%M') if link.last_scraped else 'Never'
    success_status = '✓' if link.scrape_success else '✗' if link.scrape_success is False else '?'
    
    base_info = f"{project.code:<8} {link.link_type:<10} {success_status} {failure_count:>2} failures | {domain:<25} | Last: {last_scraped}"
    
    if verbose:
        first_fail_str = first_failure.strftime('%Y-%m-%d %H:%M') if first_failure else 'None'
        return f"{base_info}\n         First failure: {first_fail_str} | URL: {link.url}"
    
    return base_info


def list_failed_projects(args, db_manager):
    """List failed projects matching criteria."""
    print("🔍 SEARCHING FOR FAILED PROJECTS")
    print("=" * 80)
    
    with db_manager.get_session() as session:
        # Build query
        query = session.query(CryptoProject, ProjectLink).join(
            ProjectLink, CryptoProject.id == ProjectLink.project_id
        ).filter(ProjectLink.is_active == True)
        
        # Apply filters
        filters = build_query_filters(args, session)
        if filters:
            query = query.filter(and_(*filters))
        
        # Order by failure count (highest first)
        if args.link_type == 'whitepaper' or not args.link_type:
            query = query.order_by(
                ProjectLink.whitepaper_consecutive_failures.desc().nullslast(),
                ProjectLink.consecutive_failures.desc().nullslast(),
                CryptoProject.rank.asc().nullslast()
            )
        else:
            query = query.order_by(
                ProjectLink.consecutive_failures.desc().nullslast(),
                CryptoProject.rank.asc().nullslast()
            )
        
        results = query.all()
        
        if not results:
            print("No projects match the specified criteria.")
            return
        
        print(f"Found {len(results)} projects:")
        print()
        print(f"{'CODE':<8} {'TYPE':<10} {'S'} {'FAIL':<4} | {'DOMAIN':<25} | LAST SCRAPED")
        print("-" * 80)
        
        total_failures = 0
        for project, link in results:
            print(format_project_info(project, link, args.verbose))
            if args.verbose:
                print()
            
            # Count total failures
            if link.link_type == 'whitepaper':
                total_failures += link.whitepaper_consecutive_failures or 0
            else:
                total_failures += link.consecutive_failures or 0
        
        print()
        print(f"Total projects: {len(results)}")
        print(f"Total cumulative failures: {total_failures}")


def reset_failed_projects(args, db_manager):
    """Reset failed projects matching criteria."""
    if args.dry_run:
        print("🧪 DRY RUN MODE - No changes will be made")
    else:
        print("🔧 RESETTING FAILED PROJECTS")
    print("=" * 80)
    
    with db_manager.get_session() as session:
        # Build query
        query = session.query(CryptoProject, ProjectLink).join(
            ProjectLink, CryptoProject.id == ProjectLink.project_id
        ).filter(ProjectLink.is_active == True)
        
        # Apply filters
        filters = build_query_filters(args, session)
        if filters:
            query = query.filter(and_(*filters))
        
        results = query.all()
        
        if not results:
            print("No projects match the specified criteria.")
            return
        
        print(f"Found {len(results)} projects to reset:")
        print()
        
        if not args.dry_run:
            # Confirm before proceeding
            if not args.all and len(results) > 10:
                response = input(f"This will reset {len(results)} projects. Continue? (y/N): ")
                if response.lower() != 'y':
                    print("Operation cancelled.")
                    return
        
        reset_count = 0
        
        for project, link in results:
            print(f"{'[DRY RUN] ' if args.dry_run else ''}Resetting: {format_project_info(project, link)}")
            
            if not args.dry_run:
                # Reset failure counters and dates
                if link.link_type == 'whitepaper':
                    link.whitepaper_consecutive_failures = 0
                    link.whitepaper_first_failure_date = None
                else:
                    link.consecutive_failures = 0
                    link.first_failure_date = None
                
                # Optionally reset scrape status to retry
                if args.all or args.failures_gte:
                    link.needs_analysis = True
                    link.scrape_success = None  # Reset to unknown status
                
                reset_count += 1
        
        if not args.dry_run:
            session.commit()
            print()
            print(f"✅ Successfully reset {reset_count} projects.")
            print("These projects will be retried in the next analysis run.")
        else:
            print()
            print(f"Would reset {len(results)} projects.")


def main():
    """Main function."""
    args = parse_arguments()
    
    # Validate arguments
    if not any([args.all, args.domain, args.project_code, args.link_type, 
               args.failures_gte, args.url_contains]):
        if not args.list_failed:
            print("Error: Must specify at least one selection criteria or use --list-failed")
            sys.exit(1)
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    print("🚀 FAILED PROJECTS UTILITY")
    print(f"Database: {database_url}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        if args.list_failed:
            list_failed_projects(args, db_manager)
        else:
            reset_failed_projects(args, db_manager)
            
    except KeyboardInterrupt:
        print("\n\nOperation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
    
    print()
    print("✅ Operation completed successfully.")


if __name__ == "__main__":
    main()