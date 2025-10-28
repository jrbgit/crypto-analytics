"""
Generate CDX Indexes

CLI tool for generating CDX indexes from existing WARC files.
Can process single files or batch process all unindexed WARCs.
"""

import sys
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Load environment variables from config/.env
config_dir = Path(__file__).parent.parent.parent / "config"
load_dotenv(config_dir / ".env")

from loguru import logger

from models.database import DatabaseManager
from archival import CDXIndexer, batch_index_warcs


def setup_logging(verbose: bool = False):
    """Configure logging."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )


def index_single_warc(db_manager: DatabaseManager, warc_file_id: int) -> bool:
    """
    Index a single WARC file.
    
    Args:
        db_manager: Database manager
        warc_file_id: WARC file ID
    
    Returns:
        True if successful
    """
    indexer = CDXIndexer(db_manager)
    
    with db_manager.get_session() as session:
        from models.archival_models import WARCFile
        
        warc_file = session.query(WARCFile).get(warc_file_id)
        if not warc_file:
            logger.error(f"WARC file not found: {warc_file_id}")
            return False
        
        if not warc_file.snapshot_id:
            logger.error(f"WARC file {warc_file_id} has no snapshot_id")
            return False
        
        logger.info(f"Indexing WARC {warc_file_id}: {warc_file.filename}")
        
        success = indexer.generate_and_store_index(
            warc_file_id,
            warc_file.snapshot_id
        )
        
        return success


def index_snapshot_warcs(db_manager: DatabaseManager, snapshot_id: int) -> bool:
    """
    Index all WARCs for a snapshot.
    
    Args:
        db_manager: Database manager
        snapshot_id: Snapshot ID
    
    Returns:
        True if all successful
    """
    indexer = CDXIndexer(db_manager)
    
    with db_manager.get_session() as session:
        from models.archival_models import WARCFile
        
        warc_files = session.query(WARCFile)\
            .filter_by(snapshot_id=snapshot_id)\
            .all()
        
        if not warc_files:
            logger.error(f"No WARC files found for snapshot {snapshot_id}")
            return False
        
        logger.info(f"Found {len(warc_files)} WARCs for snapshot {snapshot_id}")
        
        success_count = 0
        for warc_file in warc_files:
            if warc_file.has_cdx_index:
                logger.info(f"WARC {warc_file.id} already indexed, skipping")
                success_count += 1
                continue
            
            success = indexer.generate_and_store_index(
                warc_file.id,
                snapshot_id
            )
            
            if success:
                success_count += 1
        
        logger.info(f"Indexed {success_count}/{len(warc_files)} WARCs")
        return success_count == len(warc_files)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate CDX indexes from WARC files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index all unindexed WARCs
  python generate_cdx_indexes.py --batch

  # Index specific WARC file
  python generate_cdx_indexes.py --warc-id 123

  # Index all WARCs for a snapshot
  python generate_cdx_indexes.py --snapshot-id 456

  # Batch with limit
  python generate_cdx_indexes.py --batch --limit 100
        """
    )
    
    parser.add_argument(
        '--batch', '-b',
        action='store_true',
        help='Batch index all unindexed WARCs'
    )
    
    parser.add_argument(
        '--warc-id', '-w',
        type=int,
        help='Index specific WARC file by ID'
    )
    
    parser.add_argument(
        '--snapshot-id', '-s',
        type=int,
        help='Index all WARCs for a snapshot'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        help='Limit number of WARCs to process (for batch mode)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not found in environment. Please check config/.env file.")
        sys.exit(1)
    
    db_manager = DatabaseManager(database_url)
    
    # Process based on arguments
    if args.batch:
        # Batch indexing
        logger.info("Starting batch CDX indexing")
        stats = batch_index_warcs(db_manager, limit=args.limit)
        
        print("\n=== CDX Indexing Results ===")
        print(f"Total found: {stats['total_found']}")
        print(f"Successful: {stats['successful']}")
        print(f"Failed: {stats['failed']}")
        print(f"Skipped: {stats['skipped']}")
        
        success_rate = stats['successful'] / stats['total_found'] * 100 if stats['total_found'] > 0 else 0
        print(f"Success rate: {success_rate:.1f}%")
        
        sys.exit(0 if stats['failed'] == 0 else 1)
    
    elif args.warc_id:
        # Index single WARC
        success = index_single_warc(db_manager, args.warc_id)
        sys.exit(0 if success else 1)
    
    elif args.snapshot_id:
        # Index snapshot WARCs
        success = index_snapshot_warcs(db_manager, args.snapshot_id)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
