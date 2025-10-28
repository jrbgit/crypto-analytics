"""
WARC Storage Manager

Handles storage, retrieval, and management of WARC files.
Supports multiple storage backends (local filesystem, S3, Azure).
"""

import os
import hashlib
import gzip
import shutil
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, BinaryIO
from dataclasses import dataclass

from loguru import logger
from warcio.warcwriter import WARCWriter
from warcio.statusandheaders import StatusAndHeaders


@dataclass
class StorageConfig:
    """Configuration for WARC storage."""
    
    backend: str = "local"  # local, s3, azure
    base_path: str = "./data/warcs"
    compression_enabled: bool = True
    compression_level: int = 6
    
    # S3 configuration
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_storage_class: str = "STANDARD_IA"
    
    # Azure configuration
    azure_container: Optional[str] = None
    azure_connection_string: Optional[str] = None


class WARCStorageManager:
    """Manages WARC file storage and retrieval."""
    
    def __init__(self, config: StorageConfig = None):
        """
        Initialize the WARC storage manager.
        
        Args:
            config: Storage configuration
        """
        self.config = config or StorageConfig()
        self._ensure_directories()
        
        # Initialize backend-specific clients
        if self.config.backend == "s3":
            self._init_s3_client()
        elif self.config.backend == "azure":
            self._init_azure_client()
    
    def _ensure_directories(self):
        """Create necessary directories for local storage."""
        if self.config.backend == "local":
            base_path = Path(self.config.base_path)
            (base_path / "raw").mkdir(parents=True, exist_ok=True)
            (base_path / "compressed").mkdir(parents=True, exist_ok=True)
            (base_path / "indexes").mkdir(parents=True, exist_ok=True)
    
    def _init_s3_client(self):
        """Initialize AWS S3 client."""
        try:
            import boto3
            self.s3_client = boto3.client('s3', region_name=self.config.s3_region)
            logger.info(f"S3 client initialized for bucket: {self.config.s3_bucket}")
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def _init_azure_client(self):
        """Initialize Azure Blob Storage client."""
        try:
            from azure.storage.blob import BlobServiceClient
            self.azure_client = BlobServiceClient.from_connection_string(
                self.config.azure_connection_string
            )
            logger.info(f"Azure client initialized for container: {self.config.azure_container}")
        except ImportError:
            logger.error("azure-storage-blob not installed. Install with: pip install azure-storage-blob")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Azure client: {e}")
            raise
    
    def generate_warc_filename(
        self,
        project_code: str,
        timestamp: datetime,
        sequence: int = 1
    ) -> str:
        """
        Generate a standardized WARC filename.
        
        Args:
            project_code: Cryptocurrency project code (e.g., 'BTC')
            timestamp: Timestamp of the crawl
            sequence: Sequence number for multi-file crawls
        
        Returns:
            WARC filename
        """
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        extension = ".warc.gz" if self.config.compression_enabled else ".warc"
        return f"{project_code}_{timestamp_str}_{sequence:03d}{extension}"
    
    def get_storage_path(
        self,
        filename: str,
        timestamp: datetime
    ) -> Path:
        """
        Get the storage path for a WARC file with date-based organization.
        
        Args:
            filename: WARC filename
            timestamp: Timestamp for organizing by date
        
        Returns:
            Full path to the WARC file
        """
        base = Path(self.config.base_path)
        year = timestamp.strftime("%Y")
        month = timestamp.strftime("%m")
        day = timestamp.strftime("%d")
        
        return base / year / month / day / filename
    
    def create_warc_writer(
        self,
        file_path: Path,
        warc_version: str = "1.1"
    ) -> WARCWriter:
        """
        Create a WARC writer for the specified file.
        
        Args:
            file_path: Path to write WARC file
            warc_version: WARC format version
        
        Returns:
            Configured WARCWriter instance
        """
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open file with optional compression
        if self.config.compression_enabled:
            file_handle = gzip.open(
                file_path,
                'wb',
                compresslevel=self.config.compression_level
            )
        else:
            file_handle = open(file_path, 'wb')
        
        writer = WARCWriter(file_handle, gzip=False)  # gzip handled by file_handle
        
        # Write warcinfo record
        headers = [
            ('WARC-Type', 'warcinfo'),
            ('WARC-Date', datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')),
            ('WARC-Filename', file_path.name),
            ('Content-Type', 'application/warc-fields'),
        ]
        
        warcinfo_payload = (b'software: Crypto Analytics Archival System\n'
                           b'format: WARC File Format ' + warc_version.encode() + b'\n'
                           b'conformsTo: http://bibnum.bnf.fr/WARC/WARC_ISO_28500_version1_latestdraft.pdf\n')
        
        info_record = writer.create_warc_record(
            str(file_path),
            'warcinfo',
            payload=BytesIO(warcinfo_payload),
            warc_headers_dict=dict(headers)
        )
        writer.write_record(info_record)
        
        logger.info(f"Created WARC writer for: {file_path}")
        return writer
    
    def write_response_record(
        self,
        writer: WARCWriter,
        url: str,
        response_headers: Dict,
        response_body: bytes,
        timestamp: datetime = None
    ) -> str:
        """
        Write an HTTP response record to the WARC file.
        
        Args:
            writer: WARCWriter instance
            url: URL that was captured
            response_headers: HTTP response headers
            response_body: HTTP response body (bytes)
            timestamp: Capture timestamp (default: now)
        
        Returns:
            WARC-Record-ID of the written record
        """
        timestamp = timestamp or datetime.utcnow()
        
        # Format HTTP response
        http_headers = StatusAndHeaders(
            f"{response_headers.get('status_code', 200)} OK",
            response_headers.get('headers', []),
            protocol='HTTP/1.1'
        )
        
        # Ensure response_body is a file-like object
        if isinstance(response_body, bytes):
            payload = BytesIO(response_body)
        else:
            payload = response_body
        
        # Create WARC record
        record = writer.create_warc_record(
            url,
            'response',
            payload=payload,
            http_headers=http_headers,
            warc_headers_dict={
                'WARC-Date': timestamp.strftime('%Y-%m-%dT%H:%M:%SZ'),
            }
        )
        
        writer.write_record(record)
        
        return record.rec_headers.get_header('WARC-Record-ID')
    
    def compute_file_hash(self, file_path: Path) -> str:
        """
        Compute SHA256 hash of a file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            Hexadecimal hash string
        """
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def store_warc_file(
        self,
        local_path: Path,
        remote_key: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Store WARC file to the configured backend.
        
        Args:
            local_path: Path to local WARC file
            remote_key: Remote storage key (for S3/Azure)
        
        Returns:
            Storage metadata dictionary
        """
        metadata = {
            'filename': local_path.name,
            'local_path': str(local_path),
            'file_size': local_path.stat().st_size,
            'file_hash': self.compute_file_hash(local_path),
            'storage_backend': self.config.backend,
        }
        
        if self.config.backend == "s3":
            remote_key = remote_key or local_path.name
            metadata['remote_key'] = remote_key
            metadata['s3_bucket'] = self.config.s3_bucket
            
            self.s3_client.upload_file(
                str(local_path),
                self.config.s3_bucket,
                remote_key,
                ExtraArgs={'StorageClass': self.config.s3_storage_class}
            )
            logger.info(f"Uploaded WARC to S3: s3://{self.config.s3_bucket}/{remote_key}")
            
        elif self.config.backend == "azure":
            remote_key = remote_key or local_path.name
            metadata['remote_key'] = remote_key
            metadata['azure_container'] = self.config.azure_container
            
            blob_client = self.azure_client.get_blob_client(
                container=self.config.azure_container,
                blob=remote_key
            )
            
            with open(local_path, 'rb') as data:
                blob_client.upload_blob(data, overwrite=True)
            
            logger.info(f"Uploaded WARC to Azure: {self.config.azure_container}/{remote_key}")
            
        else:  # local
            logger.info(f"WARC stored locally: {local_path}")
        
        return metadata
    
    def retrieve_warc_file(
        self,
        remote_key: str,
        local_path: Optional[Path] = None
    ) -> Path:
        """
        Retrieve WARC file from storage backend.
        
        Args:
            remote_key: Remote storage key
            local_path: Local path to save file (optional)
        
        Returns:
            Path to retrieved file
        """
        if self.config.backend == "local":
            return Path(remote_key)
        
        # Generate local path if not provided
        if local_path is None:
            local_path = Path(self.config.base_path) / "temp" / Path(remote_key).name
            local_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.config.backend == "s3":
            self.s3_client.download_file(
                self.config.s3_bucket,
                remote_key,
                str(local_path)
            )
            logger.info(f"Downloaded WARC from S3: {remote_key}")
            
        elif self.config.backend == "azure":
            blob_client = self.azure_client.get_blob_client(
                container=self.config.azure_container,
                blob=remote_key
            )
            
            with open(local_path, 'wb') as download_file:
                download_file.write(blob_client.download_blob().readall())
            
            logger.info(f"Downloaded WARC from Azure: {remote_key}")
        
        return local_path
    
    def list_warc_files(
        self,
        prefix: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        List WARC files in storage.
        
        Args:
            prefix: Filter by filename prefix
            start_date: Filter by date range start
            end_date: Filter by date range end
        
        Returns:
            List of file metadata dictionaries
        """
        files = []
        
        if self.config.backend == "local":
            base_path = Path(self.config.base_path)
            for warc_file in base_path.rglob("*.warc*"):
                if prefix and not warc_file.name.startswith(prefix):
                    continue
                
                files.append({
                    'filename': warc_file.name,
                    'path': str(warc_file),
                    'size': warc_file.stat().st_size,
                    'modified': datetime.fromtimestamp(warc_file.stat().st_mtime),
                })
        
        elif self.config.backend == "s3":
            response = self.s3_client.list_objects_v2(
                Bucket=self.config.s3_bucket,
                Prefix=prefix or ''
            )
            
            for obj in response.get('Contents', []):
                files.append({
                    'filename': obj['Key'].split('/')[-1],
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'modified': obj['LastModified'],
                })
        
        elif self.config.backend == "azure":
            container_client = self.azure_client.get_container_client(
                self.config.azure_container
            )
            
            for blob in container_client.list_blobs(name_starts_with=prefix or ''):
                files.append({
                    'filename': blob.name.split('/')[-1],
                    'key': blob.name,
                    'size': blob.size,
                    'modified': blob.last_modified,
                })
        
        # Apply date filtering
        if start_date or end_date:
            files = [
                f for f in files
                if (not start_date or f['modified'] >= start_date) and
                   (not end_date or f['modified'] <= end_date)
            ]
        
        return sorted(files, key=lambda x: x['modified'], reverse=True)
    
    def delete_warc_file(self, remote_key: str) -> bool:
        """
        Delete a WARC file from storage.
        
        Args:
            remote_key: Remote storage key or local path
        
        Returns:
            True if successful
        """
        try:
            if self.config.backend == "local":
                Path(remote_key).unlink()
                logger.info(f"Deleted local WARC: {remote_key}")
                
            elif self.config.backend == "s3":
                self.s3_client.delete_object(
                    Bucket=self.config.s3_bucket,
                    Key=remote_key
                )
                logger.info(f"Deleted S3 WARC: {remote_key}")
                
            elif self.config.backend == "azure":
                blob_client = self.azure_client.get_blob_client(
                    container=self.config.azure_container,
                    blob=remote_key
                )
                blob_client.delete_blob()
                logger.info(f"Deleted Azure WARC: {remote_key}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete WARC {remote_key}: {e}")
            return False
    
    def get_storage_stats(self) -> Dict:
        """
        Get storage usage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        stats = {
            'backend': self.config.backend,
            'total_files': 0,
            'total_size_bytes': 0,
            'total_size_gb': 0,
        }
        
        files = self.list_warc_files()
        stats['total_files'] = len(files)
        stats['total_size_bytes'] = sum(f['size'] for f in files)
        stats['total_size_gb'] = stats['total_size_bytes'] / (1024 ** 3)
        
        return stats
