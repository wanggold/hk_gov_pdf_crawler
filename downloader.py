"""
File Download and Storage Module

This module handles downloading PDF files and managing both local and S3 storage,
including file organization, validation, and error handling.
"""

from typing import Optional, List, Dict
import os
import re
import time
import logging
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import StorageConfig
from models import DownloadResult
from concurrency import SimpleConcurrency
from utils import retry_with_backoff


class FileDownloader:
    """Handles PDF file downloading and storage management"""
    
    def __init__(self, config: StorageConfig, max_concurrent_downloads: int = 5):
        self.config = config
        self.s3_client = None
        
        # Initialize concurrent downloader
        self.concurrency = SimpleConcurrency(max_workers=max_concurrent_downloads)
        
        # Initialize S3 upload executor for parallel uploads
        self.s3_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="s3-upload")
        
        # Initialize file tracking for incremental updates
        self.file_registry_path = os.path.join(config.local_path, '.file_registry.json')
        self.file_registry = self._load_file_registry()
        
        # Initialize S3 client if enabled
        if config.s3_enabled:
            try:
                self.s3_client = boto3.client('s3')
                # Test S3 connection if bucket is specified
                if config.s3_bucket:
                    self.s3_client.head_bucket(Bucket=config.s3_bucket)
                    logging.info(f"S3 connection established to bucket: {config.s3_bucket}")
            except (ClientError, NoCredentialsError) as e:
                logging.warning(f"S3 initialization failed: {e}. S3 uploads will be disabled.")
                self.s3_client = None
        
        # Setup requests session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
    def download_pdf(self, url: str, department: str) -> DownloadResult:
        """
        Download a single PDF file with validation and streaming.
        
        Args:
            url: URL of the PDF to download
            department: Department name for organization
            
        Returns:
            DownloadResult with success status and details
        """
        try:
            # Generate filename and paths
            filename = self.generate_filename(url)
            local_path = self._get_local_path(filename, department)
            s3_key = self._get_s3_key(filename, department) if self.config.s3_enabled else None
            
            # Check if file already exists
            if self.file_exists(local_path, department):
                logging.info(f"File already exists, skipping: {filename}")
                return DownloadResult(
                    url=url,
                    success=True,
                    file_path=local_path,
                    file_size=os.path.getsize(local_path) if os.path.exists(local_path) else 0
                )
            
            # Validate PDF URL with HEAD request
            if not self._validate_pdf_url(url):
                return DownloadResult(
                    url=url,
                    success=False,
                    error="URL does not point to a valid PDF file"
                )
            
            # Download the file with streaming
            logging.info(f"Downloading PDF: {url}")
            response = self.session.get(
                url, 
                stream=True, 
                timeout=30,
                headers={'User-Agent': 'HK-PDF-Crawler/1.0'}
            )
            response.raise_for_status()
            
            # Read content and validate
            content = b''
            file_size = 0
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
                    file_size += len(chunk)
            
            # Validate PDF content
            if not self.validate_pdf_content(content):
                return DownloadResult(
                    url=url,
                    success=False,
                    error="Downloaded content is not a valid PDF file"
                )
            
            # Save locally if configured
            local_saved = True
            if not self.config.s3_enabled or self.config.local_path:
                local_saved = self.save_locally(content, local_path)
                if not local_saved:
                    return DownloadResult(
                        url=url,
                        success=False,
                        error="Failed to save file locally"
                    )
            
            # Upload to S3 if configured (async)
            s3_saved = True
            if self.config.s3_enabled and self.s3_client and s3_key:
                # Submit S3 upload to thread pool for parallel processing
                self.s3_executor.submit(self._async_upload_to_s3, content, s3_key, filename)
            
            success = local_saved or s3_saved
            final_path = local_path if local_saved else f"s3://{self.config.s3_bucket}/{s3_key}"
            
            logging.info(f"Successfully downloaded: {filename} ({file_size} bytes)")
            return DownloadResult(
                url=url,
                success=success,
                file_path=final_path,
                file_size=file_size
            )
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error downloading {url}: {e}")
            return DownloadResult(
                url=url,
                success=False,
                error=f"Network error: {str(e)}"
            )
        except Exception as e:
            logging.error(f"Unexpected error downloading {url}: {e}")
            return DownloadResult(
                url=url,
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def download_pdfs_batch(self, pdf_urls: List[str], department: str) -> List[DownloadResult]:
        """
        Download multiple PDFs concurrently with rate limiting.
        
        Args:
            pdf_urls: List of PDF URLs to download
            department: Department name for organization
            
        Returns:
            List of DownloadResult objects
        """
        if not pdf_urls:
            return []
        
        logging.info(f"Starting batch download of {len(pdf_urls)} PDFs for {department}")
        
        # Use concurrent downloader with rate limiting
        results = self.concurrency.download_pdfs_concurrently(pdf_urls, department, self)
        
        # Log summary statistics
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_size = sum(r.file_size for r in results if r.success)
        
        logging.info(f"Batch download completed for {department}: {successful} successful, {failed} failed, {total_size / (1024*1024):.2f} MB total")
        
        return results
    
    def save_locally(self, content: bytes, file_path: str) -> bool:
        """
        Save file to local storage with directory creation.
        
        Args:
            content: File content as bytes
            file_path: Full path where to save the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(content)
            
            logging.debug(f"Saved locally: {file_path}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to save file locally {file_path}: {e}")
            return False
    
    def _check_file_size_limit(self, response, url: str) -> Optional[DownloadResult]:
        """
        Check if file size exceeds limit and return error result if so
        
        Returns:
            DownloadResult with error if file is too large, None if size is acceptable
        """
        content_length = response.headers.get('Content-Length')
        if content_length:
            file_size_mb = int(content_length) / (1024 * 1024)
            if file_size_mb > 50:  # Skip files larger than 50MB
                logging.warning(f"Skipping large file: {url} ({file_size_mb:.1f}MB)")
                return DownloadResult(
                    url=url,
                    success=False,
                    error=f"File too large ({file_size_mb:.1f}MB), skipping"
                )
        return None
    
    def upload_to_s3(self, content: bytes, s3_key: str) -> bool:
        """
        Upload file to S3 with error handling and retries.
        
        Args:
            content: File content as bytes
            s3_key: S3 object key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.s3_client or not self.config.s3_bucket:
            logging.warning("S3 client not available or bucket not configured")
            return False
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.s3_client.put_object(
                    Bucket=self.config.s3_bucket,
                    Key=s3_key,
                    Body=content,
                    ContentType='application/pdf',
                    Metadata={
                        'source': 'hk-pdf-crawler',
                        'upload_time': str(int(time.time()))
                    }
                )
                
                logging.debug(f"Uploaded to S3: s3://{self.config.s3_bucket}/{s3_key}")
                return True
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code in ['NoSuchBucket', 'AccessDenied']:
                    logging.error(f"S3 error {error_code}: {e}")
                    return False
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logging.warning(f"S3 upload attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    logging.error(f"S3 upload failed after {max_retries} attempts: {e}")
                    return False
            except Exception as e:
                logging.error(f"Unexpected S3 upload error: {e}")
                return False
        
        # This should never be reached, but just in case
        logging.error("S3 upload failed: exhausted all retry attempts")
        return False
    
    def _async_upload_to_s3(self, content: bytes, s3_key: str, filename: str) -> None:
        """
        Async wrapper for S3 upload to be used with ThreadPoolExecutor
        """
        try:
            success = self.upload_to_s3(content, s3_key)
            if not success:
                logging.warning(f"S3 upload failed for {filename}, but local save succeeded")
        except Exception as e:
            logging.error(f"Async S3 upload error for {filename}: {e}")
    
    def generate_filename(self, url: str, title: str = "") -> str:
        """
        Generate meaningful filename from URL and document title.
        
        Args:
            url: Source URL
            title: Optional document title
            
        Returns:
            Generated filename with .pdf extension
        """
        # Start with title if provided
        if title:
            # Clean title for filename
            filename = re.sub(r'[^\w\s-]', '', title.strip())
            filename = re.sub(r'[-\s]+', '-', filename)
            filename = filename.strip('-')
        else:
            # Extract filename from URL
            parsed_url = urlparse(url)
            path = unquote(parsed_url.path)
            
            # Get the last part of the path
            filename = os.path.basename(path)
            
            # If no filename in path, use domain and path
            if not filename or filename == '/':
                domain = parsed_url.netloc.replace('www.', '')
                path_parts = [p for p in path.split('/') if p]
                if path_parts:
                    filename = f"{domain}-{'-'.join(path_parts[-2:])}"
                else:
                    filename = f"{domain}-document"
            
            # Remove existing extension
            filename = os.path.splitext(filename)[0]
        
        # Clean filename
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '-', filename)
        filename = filename.strip('-')
        
        # Ensure filename is not empty
        if not filename:
            filename = f"document-{int(time.time())}"
        
        # Limit length and add extension
        filename = filename[:100]  # Limit to 100 characters
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
        return filename
    
    def file_exists(self, file_path: str, department: str) -> bool:
        """
        Check if file already exists locally or in S3.
        
        Args:
            file_path: Local file path to check
            department: Department name for S3 key generation
            
        Returns:
            True if file exists, False otherwise
        """
        # Check local file
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return True
        
        # Check S3 if enabled
        if self.config.s3_enabled and self.s3_client and self.config.s3_bucket:
            filename = os.path.basename(file_path)
            s3_key = self._get_s3_key(filename, department)
            
            try:
                self.s3_client.head_object(Bucket=self.config.s3_bucket, Key=s3_key)
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != '404':
                    logging.warning(f"Error checking S3 object existence: {e}")
        
        return False
    
    def validate_pdf_content(self, content: bytes) -> bool:
        """
        Validate that downloaded content is actually a PDF.
        
        Args:
            content: File content as bytes
            
        Returns:
            True if content appears to be a valid PDF, False otherwise
        """
        if not content:
            return False
        
        # Check PDF magic number
        if not content.startswith(b'%PDF-'):
            return False
        
        # Check minimum size (PDFs should be at least 100 bytes, not 1KB)
        if len(content) < 100:
            return False
        
        # Check for PDF trailer (optional - some PDFs may not have it at the end)
        if b'%%EOF' not in content[-1024:]:
            logging.debug("PDF content missing EOF marker at end, but proceeding")
        
        return True
    
    def _validate_pdf_url(self, url: str) -> bool:
        """
        Validate PDF URL with HEAD request to check content-type.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL points to a PDF, False otherwise
        """
        try:
            response = self.session.head(
                url, 
                timeout=10,
                headers={'User-Agent': 'HK-PDF-Crawler/1.0'},
                allow_redirects=True
            )
            
            # Check status code
            if response.status_code != 200:
                logging.warning(f"HEAD request failed for {url}: {response.status_code}")
                return False  # Don't download if HEAD request fails
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'application/pdf' in content_type:
                return True
            
            # Some servers don't set proper content-type, check URL pattern
            if url.lower().endswith('.pdf'):
                logging.info(f"URL ends with .pdf, assuming PDF: {url}")
                return True
            
            # Check content-disposition for PDF filename
            content_disposition = response.headers.get('content-disposition', '').lower()
            if '.pdf' in content_disposition:
                return True
            
            logging.warning(f"URL may not be a PDF (content-type: {content_type}): {url}")
            return False  # Don't download non-PDF files
            
        except Exception as e:
            logging.warning(f"HEAD request failed for {url}: {e}")
            return False  # Don't download if validation fails
    
    def _get_local_path(self, filename: str, department: str) -> str:
        """
        Get local file path with department organization.
        
        Args:
            filename: Name of the file
            department: Department name
            
        Returns:
            Full local file path
        """
        base_path = Path(self.config.local_path)
        
        if self.config.organize_by_department:
            # Clean department name for directory
            dept_dir = re.sub(r'[^\w\s-]', '', department)
            dept_dir = re.sub(r'[-\s]+', '-', dept_dir).strip('-')
            return str(base_path / dept_dir / filename)
        else:
            return str(base_path / filename)
    
    def _get_s3_key(self, filename: str, department: str) -> str:
        """
        Get S3 object key with optional prefix and department organization.
        
        Args:
            filename: Name of the file
            department: Department name
            
        Returns:
            S3 object key
        """
        key_parts = []
        
        # Add prefix if configured
        if self.config.s3_prefix:
            key_parts.append(self.config.s3_prefix.strip('/'))
        
        # Add department if organizing by department
        if self.config.organize_by_department:
            dept_dir = re.sub(r'[^\w\s-]', '', department)
            dept_dir = re.sub(r'[-\s]+', '-', dept_dir).strip('-')
            key_parts.append(dept_dir)
        
        key_parts.append(filename)
        
        return '/'.join(key_parts)
    
    def _load_file_registry(self) -> Dict:
        """Load file registry for tracking downloaded files"""
        if os.path.exists(self.file_registry_path):
            try:
                with open(self.file_registry_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Could not load file registry: {e}")
        return {}
    
    def _save_file_registry(self):
        """Save file registry to disk"""
        try:
            os.makedirs(os.path.dirname(self.file_registry_path), exist_ok=True)
            with open(self.file_registry_path, 'w') as f:
                json.dump(self.file_registry, f, indent=2)
        except Exception as e:
            logging.error(f"Could not save file registry: {e}")
    
    def _get_file_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(content).hexdigest()
    
    def _get_url_hash(self, url: str) -> str:
        """Calculate hash of URL for registry key"""
        return hashlib.md5(url.encode()).hexdigest()
    
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def _check_remote_file_modified(self, url: str) -> Optional[Dict]:
        """
        Check if remote file has been modified using HEAD request
        
        Args:
            url: URL to check
            
        Returns:
            Dictionary with file info or None if check failed
        """
        try:
            response = self.session.head(url, timeout=15, allow_redirects=True)
            
            if response.status_code == 200:
                return {
                    'last_modified': response.headers.get('Last-Modified'),
                    'etag': response.headers.get('ETag'),
                    'content_length': response.headers.get('Content-Length')
                }
        except Exception as e:
            logging.debug(f"Could not check remote file modification for {url}: {e}")
        
        return None
    
    def should_download_file(self, url: str, local_path: str, force_update: bool = False) -> bool:
        """
        Determine if file should be downloaded based on incremental update logic
        
        Args:
            url: URL of the file
            local_path: Local path where file would be saved
            force_update: Force download regardless of existing file
            
        Returns:
            True if file should be downloaded, False otherwise
        """
        if force_update:
            return True
        
        # Check if file exists locally
        if not os.path.exists(local_path):
            return True
        
        # Check file registry for previous download info
        url_hash = self._get_url_hash(url)
        registry_entry = self.file_registry.get(url_hash)
        
        if not registry_entry:
            # File exists but not in registry, check if we should re-download
            return True
        
        # Check remote file modification
        remote_info = self._check_remote_file_modified(url)
        
        if remote_info:
            # Compare with registry info
            if (remote_info.get('last_modified') != registry_entry.get('last_modified') or
                remote_info.get('etag') != registry_entry.get('etag')):
                logging.info(f"Remote file modified, will re-download: {url}")
                return True
        
        # File appears unchanged
        logging.debug(f"File unchanged, skipping: {url}")
        return False
    
    def update_file_registry(self, url: str, local_path: str, content: bytes, remote_info: Dict = None):
        """
        Update file registry with download information
        
        Args:
            url: URL of the downloaded file
            local_path: Local path where file was saved
            content: File content for hash calculation
            remote_info: Remote file information from headers
        """
        url_hash = self._get_url_hash(url)
        
        registry_entry = {
            'url': url,
            'local_path': local_path,
            'download_time': time.time(),
            'file_size': len(content),
            'file_hash': self._get_file_hash(content)
        }
        
        if remote_info:
            registry_entry.update({
                'last_modified': remote_info.get('last_modified'),
                'etag': remote_info.get('etag'),
                'content_length': remote_info.get('content_length')
            })
        
        self.file_registry[url_hash] = registry_entry
        self._save_file_registry()
    
    def download_pdf_incremental(self, url: str, department: str, force_update: bool = False) -> DownloadResult:
        """
        Download PDF with incremental update support
        
        Args:
            url: URL of the PDF to download
            department: Department name for organization
            force_update: Force download even if file exists
            
        Returns:
            DownloadResult with success status and details
        """
        try:
            # Generate filename and paths
            filename = self.generate_filename(url)
            local_path = self._get_local_path(filename, department)
            
            # Check if we should download this file
            if not self.should_download_file(url, local_path, force_update):
                logging.info(f"File up to date, skipping: {filename}")
                return DownloadResult(
                    url=url,
                    success=True,
                    file_path=local_path,
                    file_size=os.path.getsize(local_path) if os.path.exists(local_path) else 0
                )
            
            # Get remote file info before downloading
            remote_info = self._check_remote_file_modified(url)
            
            # Validate PDF URL with HEAD request
            if not self._validate_pdf_url(url):
                return DownloadResult(
                    url=url,
                    success=False,
                    error="URL does not point to a valid PDF file"
                )
            
            # Download the file with streaming
            logging.info(f"Downloading PDF: {url}")
            response = self.session.get(
                url, 
                stream=True, 
                timeout=30,
                headers={'User-Agent': 'HK-PDF-Crawler/1.0'}
            )
            response.raise_for_status()
            
            # Read content and validate
            content = b''
            file_size = 0
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
                    file_size += len(chunk)
            
            # Validate PDF content
            if not self.validate_pdf_content(content):
                return DownloadResult(
                    url=url,
                    success=False,
                    error="Downloaded content is not a valid PDF file"
                )
            
            # Save locally if configured
            local_saved = True
            if not self.config.s3_enabled or self.config.local_path:
                local_saved = self.save_locally(content, local_path)
                if not local_saved:
                    return DownloadResult(
                        url=url,
                        success=False,
                        error="Failed to save file locally"
                    )
            
            # Upload to S3 if configured (async)
            s3_saved = True
            s3_key = self._get_s3_key(filename, department) if self.config.s3_enabled else None
            if self.config.s3_enabled and self.s3_client and s3_key:
                # Submit S3 upload to thread pool for parallel processing
                self.s3_executor.submit(self._async_upload_to_s3, content, s3_key, filename)
            
            # Update file registry
            if local_saved or s3_saved:
                self.update_file_registry(url, local_path, content, remote_info)
            
            success = local_saved or s3_saved
            final_path = local_path if local_saved else f"s3://{self.config.s3_bucket}/{s3_key}"
            
            logging.info(f"Successfully downloaded: {filename} ({file_size} bytes)")
            return DownloadResult(
                url=url,
                success=success,
                file_path=final_path,
                file_size=file_size
            )
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error downloading {url}: {e}")
            return DownloadResult(
                url=url,
                success=False,
                error=f"Network error: {str(e)}"
            )
        except Exception as e:
            logging.error(f"Unexpected error downloading {url}: {e}")
            return DownloadResult(
                url=url,
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def get_registry_stats(self) -> Dict:
        """Get statistics from the file registry"""
        if not self.file_registry:
            return {'total_files': 0, 'total_size': 0}
        
        total_files = len(self.file_registry)
        total_size = sum(entry.get('file_size', 0) for entry in self.file_registry.values())
        
        return {
            'total_files': total_files,
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024)
        }