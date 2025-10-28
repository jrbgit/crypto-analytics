"""
CDX Indexer

Generates CDX (Capture Index) records from WARC files for fast lookups.
CDX format enables efficient URL → WARC location mapping for replay.
"""

import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from loguru import logger
from warcio.archiveiterator import ArchiveIterator

from models.database import DatabaseManager
from models.archival_models import CDXRecord, WARCFile, WebsiteSnapshot


@dataclass
class CDXEntry:
    """Single CDX index entry."""
    
    url_key: str  # SURT-formatted URL
    timestamp: str  # YYYYMMDDhhmmss
    original_url: str
    mime_type: str
    status_code: int
    digest: str  # Content hash
    redirect_url: Optional[str]
    warc_filename: str
    warc_record_offset: int
    warc_record_length: int
    content_length: int


class CDXIndexer:
    """Generates and manages CDX indexes from WARC files."""
    
    def __init__(self, db_manager: DatabaseManager = None):
        """
        Initialize the CDX indexer.
        
        Args:
            db_manager: Database manager for storing CDX records
        """
        self.db_manager = db_manager
    
    def generate_cdx_from_warc(
        self,
        warc_path: Path,
        output_path: Optional[Path] = None
    ) -> List[CDXEntry]:
        """
        Generate CDX entries from a WARC file.
        
        Args:
            warc_path: Path to WARC file
            output_path: Optional path to write CDX file
        
        Returns:
            List of CDX entries
        """
        logger.info(f"Generating CDX index from: {warc_path}")
        entries = []
        
        try:
            with open(warc_path, 'rb') as warc_file:
                offset = 0
                
                for record in ArchiveIterator(warc_file):
                    if record.rec_type == 'response':
                        entry = self._create_cdx_entry(
                            record,
                            warc_path.name,
                            offset
                        )
                        
                        if entry:
                            entries.append(entry)
                    
                    # Update offset for next record
                    offset = warc_file.tell()
            
            logger.success(f"Generated {len(entries)} CDX entries")
            
            # Write CDX file if output path provided
            if output_path:
                self._write_cdx_file(entries, output_path)
            
            return entries
            
        except Exception as e:
            logger.error(f"Failed to generate CDX from WARC: {e}")
            return []
    
    def _create_cdx_entry(
        self,
        record,
        warc_filename: str,
        offset: int
    ) -> Optional[CDXEntry]:
        """
        Create a CDX entry from a WARC record.
        
        Args:
            record: WARC record
            warc_filename: Name of WARC file
            offset: Byte offset in WARC file
        
        Returns:
            CDXEntry or None if invalid
        """
        try:
            # Get URL
            url = record.rec_headers.get_header('WARC-Target-URI')
            if not url:
                return None
            
            # Get timestamp
            warc_date = record.rec_headers.get_header('WARC-Date')
            if warc_date:
                timestamp = self._format_timestamp(warc_date)
            else:
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            
            # Get HTTP headers
            status_code = 200
            mime_type = 'application/octet-stream'
            content_length = 0
            
            if record.http_headers:
                status_line = record.http_headers.get_statuscode()
                if status_line:
                    status_code = int(status_line.split()[0]) if status_line.split() else 200
                
                mime_type = record.http_headers.get_header('Content-Type', 'application/octet-stream')
                if mime_type and ';' in mime_type:
                    mime_type = mime_type.split(';')[0].strip()
                
                content_length_str = record.http_headers.get_header('Content-Length', '0')
                try:
                    content_length = int(content_length_str)
                except (ValueError, TypeError):
                    content_length = 0
            
            # Get digest (content hash)
            digest = record.rec_headers.get_header('WARC-Payload-Digest', '')
            if digest.startswith('sha1:'):
                digest = digest[5:]  # Remove 'sha1:' prefix
            
            # Get redirect URL
            redirect_url = None
            if 300 <= status_code < 400 and record.http_headers:
                redirect_url = record.http_headers.get_header('Location')
            
            # Get record length
            record_length = int(record.rec_headers.get_header('Content-Length', 0))
            
            # Convert URL to SURT format
            url_key = self._url_to_surt(url)
            
            return CDXEntry(
                url_key=url_key,
                timestamp=timestamp,
                original_url=url,
                mime_type=mime_type,
                status_code=status_code,
                digest=digest,
                redirect_url=redirect_url,
                warc_filename=warc_filename,
                warc_record_offset=offset,
                warc_record_length=record_length,
                content_length=content_length
            )
            
        except Exception as e:
            logger.warning(f"Failed to create CDX entry: {e}")
            return None
    
    def _url_to_surt(self, url: str) -> str:
        """
        Convert URL to SURT (Sort-friendly URI Reordering Transform) format.
        
        SURT enables efficient sorting and prefix matching of URLs.
        Example: http://www.example.com/path -> com,example)/path
        
        Args:
            url: Original URL
        
        Returns:
            SURT-formatted URL
        """
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            
            # Reverse domain components
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            
            domain_parts = domain.split('.')
            reversed_domain = ','.join(reversed(domain_parts))
            
            # Build SURT
            path = parsed.path or '/'
            if parsed.query:
                path += f'?{parsed.query}'
            
            surt = f"{reversed_domain}){path}"
            
            return surt
            
        except Exception as e:
            logger.warning(f"Failed to convert URL to SURT: {e}")
            return url
    
    def _format_timestamp(self, warc_date: str) -> str:
        """
        Format WARC-Date to CDX timestamp format (YYYYMMDDhhmmss).
        
        Args:
            warc_date: WARC-Date string (ISO 8601)
        
        Returns:
            Formatted timestamp string
        """
        try:
            # Parse ISO 8601 format
            dt = datetime.fromisoformat(warc_date.replace('Z', '+00:00'))
            return dt.strftime('%Y%m%d%H%M%S')
        except Exception:
            return datetime.utcnow().strftime('%Y%m%d%H%M%S')
    
    def _write_cdx_file(self, entries: List[CDXEntry], output_path: Path):
        """
        Write CDX entries to a file.
        
        Args:
            entries: List of CDX entries
            output_path: Output file path
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write CDX header
                f.write(' CDX N b a m s k r M S V g\n')
                
                # Write entries
                for entry in entries:
                    line = self._format_cdx_line(entry)
                    f.write(line + '\n')
            
            logger.success(f"Wrote CDX file: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to write CDX file: {e}")
    
    def _format_cdx_line(self, entry: CDXEntry) -> str:
        """
        Format a CDX entry as a line in standard CDX format.
        
        Args:
            entry: CDX entry
        
        Returns:
            Formatted CDX line
        """
        redirect = entry.redirect_url or '-'
        
        return (
            f"{entry.url_key} {entry.timestamp} {entry.original_url} "
            f"{entry.mime_type} {entry.status_code} {entry.digest} "
            f"{redirect} - {entry.warc_record_offset} {entry.warc_filename} {entry.digest}"
        )
    
    def store_cdx_in_database(
        self,
        entries: List[CDXEntry],
        warc_file_id: int,
        snapshot_id: int
    ) -> int:
        """
        Store CDX entries in the database.
        
        Args:
            entries: List of CDX entries
            warc_file_id: WARC file ID
            snapshot_id: Snapshot ID
        
        Returns:
            Number of entries stored
        """
        if not self.db_manager:
            logger.warning("No database manager - skipping CDX storage")
            return 0
        
        logger.info(f"Storing {len(entries)} CDX entries in database")
        
        with self.db_manager.get_session() as session:
            count = 0
            
            for entry in entries:
                cdx_record = CDXRecord(
                    warc_file_id=warc_file_id,
                    snapshot_id=snapshot_id,
                    url_key=entry.url_key,
                    timestamp=entry.timestamp,
                    original_url=entry.original_url,
                    mime_type=entry.mime_type,
                    status_code=entry.status_code,
                    digest=entry.digest,
                    redirect_url=entry.redirect_url,
                    warc_filename=entry.warc_filename,
                    warc_record_offset=entry.warc_record_offset,
                    warc_record_length=entry.warc_record_length,
                    content_length=entry.content_length,
                    created_at=datetime.utcnow()
                )
                
                session.add(cdx_record)
                count += 1
            
            session.commit()
            logger.success(f"Stored {count} CDX records in database")
            
            return count
    
    def lookup_url(
        self,
        url: str,
        snapshot_id: Optional[int] = None,
        timestamp: Optional[str] = None
    ) -> Optional[CDXRecord]:
        """
        Look up a URL in the CDX index.
        
        Args:
            url: URL to look up
            snapshot_id: Optional snapshot ID to filter by
            timestamp: Optional timestamp to find closest match
        
        Returns:
            CDXRecord or None if not found
        """
        if not self.db_manager:
            return None
        
        url_key = self._url_to_surt(url)
        
        with self.db_manager.get_session() as session:
            query = session.query(CDXRecord).filter_by(url_key=url_key)
            
            if snapshot_id:
                query = query.filter_by(snapshot_id=snapshot_id)
            
            if timestamp:
                # Find closest timestamp
                query = query.order_by(
                    CDXRecord.timestamp.desc()
                ).filter(CDXRecord.timestamp <= timestamp)
            else:
                # Get most recent
                query = query.order_by(CDXRecord.timestamp.desc())
            
            return query.first()
    
    def get_snapshot_urls(self, snapshot_id: int) -> List[str]:
        """
        Get all URLs captured in a snapshot.
        
        Args:
            snapshot_id: Snapshot ID
        
        Returns:
            List of URLs
        """
        if not self.db_manager:
            return []
        
        with self.db_manager.get_session() as session:
            records = session.query(CDXRecord)\
                .filter_by(snapshot_id=snapshot_id)\
                .all()
            
            return [record.original_url for record in records]
    
    def generate_and_store_index(
        self,
        warc_file_id: int,
        snapshot_id: int
    ) -> bool:
        """
        Generate CDX index from WARC file and store in database.
        
        Args:
            warc_file_id: WARC file database ID
            snapshot_id: Snapshot database ID
        
        Returns:
            True if successful
        """
        if not self.db_manager:
            logger.error("No database manager configured")
            return False
        
        with self.db_manager.get_session() as session:
            # Get WARC file record
            warc_file = session.query(WARCFile).get(warc_file_id)
            if not warc_file:
                logger.error(f"WARC file not found: {warc_file_id}")
                return False
            
            warc_path = Path(warc_file.file_path)
            if not warc_path.exists():
                logger.error(f"WARC file does not exist: {warc_path}")
                return False
            
            # Generate CDX entries
            entries = self.generate_cdx_from_warc(warc_path)
            
            if not entries:
                logger.warning("No CDX entries generated")
                return False
            
            # Generate CDX file path
            cdx_path = warc_path.with_suffix('.cdx')
            
            # Write CDX file
            self._write_cdx_file(entries, cdx_path)
            
            # Store in database
            count = self.store_cdx_in_database(entries, warc_file_id, snapshot_id)
            
            # Update WARC file record
            warc_file.has_cdx_index = True
            warc_file.cdx_file_path = str(cdx_path)
            session.commit()
            
            # Update snapshot record
            snapshot = session.query(WebsiteSnapshot).get(snapshot_id)
            if snapshot:
                snapshot.index_generated = True
                session.commit()
            
            logger.success(
                f"CDX indexing complete: {count} entries, "
                f"file: {cdx_path}"
            )
            
            return True


def batch_index_warcs(
    db_manager: DatabaseManager,
    limit: Optional[int] = None
) -> Dict[str, int]:
    """
    Batch index all WARCs that don't have CDX indexes.
    
    Args:
        db_manager: Database manager
        limit: Optional limit on number to process
    
    Returns:
        Statistics dictionary
    """
    logger.info("Starting batch CDX indexing")
    indexer = CDXIndexer(db_manager)
    
    stats = {
        'total_found': 0,
        'successful': 0,
        'failed': 0,
        'skipped': 0
    }
    
    with db_manager.get_session() as session:
        # Find WARCs without indexes
        query = session.query(WARCFile)\
            .filter_by(has_cdx_index=False)\
            .order_by(WARCFile.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        warc_files = query.all()
        stats['total_found'] = len(warc_files)
        
        logger.info(f"Found {len(warc_files)} WARCs to index")
        
        for warc_file in warc_files:
            try:
                if not warc_file.snapshot_id:
                    logger.warning(f"WARC {warc_file.id} has no snapshot_id, skipping")
                    stats['skipped'] += 1
                    continue
                
                success = indexer.generate_and_store_index(
                    warc_file.id,
                    warc_file.snapshot_id
                )
                
                if success:
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to index WARC {warc_file.id}: {e}")
                stats['failed'] += 1
    
    logger.info(
        f"Batch indexing complete: {stats['successful']} successful, "
        f"{stats['failed']} failed, {stats['skipped']} skipped"
    )
    
    return stats
