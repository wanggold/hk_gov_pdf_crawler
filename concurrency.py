"""
Simple Concurrency Module

This module provides thread-based concurrent downloading with rate limiting
to respect website resources while improving download performance.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import logging
from typing import List
from urllib.parse import urlparse

from models import DownloadResult


class SimpleConcurrency:
    """Simple concurrent downloader with per-domain rate limiting"""
    
    def __init__(self, max_workers: int = 5):
        """
        Initialize concurrent downloader.
        
        Args:
            max_workers: Maximum number of concurrent download threads
        """
        self.max_workers = max_workers
        self.domain_locks = {}
        self.last_request_times = {}
        self._lock = threading.Lock()  # For thread-safe access to domain_locks
        
    def download_pdfs_concurrently(self, pdf_urls: List[str], department: str, downloader) -> List[DownloadResult]:
        """
        Download PDFs with simple thread pool and rate limiting.
        
        Args:
            pdf_urls: List of PDF URLs to download
            department: Department name for organization
            downloader: FileDownloader instance to use for actual downloads
            
        Returns:
            List of DownloadResult objects
        """
        if not pdf_urls:
            return []
            
        results = []
        
        logging.info(f"Starting concurrent download of {len(pdf_urls)} PDFs for {department} with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_url = {
                executor.submit(self.download_with_rate_limit, url, department, downloader): url 
                for url in pdf_urls
            }
            
            # Collect results as they complete
            completed_count = 0
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                completed_count += 1
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    status = "Success" if result.success else "Failed"
                    if result.error:
                        logging.info(f"[{completed_count}/{len(pdf_urls)}] Downloaded: {url} ({status}: {result.error})")
                    else:
                        size_mb = result.file_size / (1024 * 1024) if result.file_size > 0 else 0
                        logging.info(f"[{completed_count}/{len(pdf_urls)}] Downloaded: {url} ({status}, {size_mb:.2f} MB)")
                        
                except Exception as e:
                    logging.error(f"[{completed_count}/{len(pdf_urls)}] Unexpected error downloading {url}: {e}")
                    results.append(DownloadResult(url=url, success=False, error=str(e)))
                    
        logging.info(f"Completed concurrent download for {department}: {sum(1 for r in results if r.success)}/{len(results)} successful")
        return results
    
    def download_with_rate_limit(self, url: str, department: str, downloader) -> DownloadResult:
        """
        Download with simple rate limiting per domain.
        
        Args:
            url: URL to download
            department: Department name
            downloader: FileDownloader instance to use
            
        Returns:
            DownloadResult object
        """
        domain = urlparse(url).netloc
        
        # Get or create domain lock (thread-safe)
        with self._lock:
            if domain not in self.domain_locks:
                self.domain_locks[domain] = threading.Lock()
        
        domain_lock = self.domain_locks[domain]
        
        # Apply rate limiting per domain
        with domain_lock:
            # Ensure minimum delay between requests to same domain
            if domain in self.last_request_times:
                elapsed = time.time() - self.last_request_times[domain]
                if elapsed < 1.0:  # 1 second minimum delay
                    sleep_time = 1.0 - elapsed
                    logging.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for domain {domain}")
                    time.sleep(sleep_time)
            
            self.last_request_times[domain] = time.time()
            
            # Perform actual download with retry logic
            return self._download_with_retry(url, department, downloader)
    
    def _download_with_retry(self, url: str, department: str, downloader, max_retries: int = 3) -> DownloadResult:
        """
        Download with exponential backoff retry logic.
        
        Args:
            url: URL to download
            department: Department name
            downloader: FileDownloader instance
            max_retries: Maximum number of retry attempts
            
        Returns:
            DownloadResult object
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = downloader.download_pdf(url, department)
                
                # If successful or non-retryable error, return immediately
                if result.success or not self._should_retry_error(result.error):
                    return result
                
                last_error = result.error
                
                # If this isn't the last attempt, wait before retrying
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1.0  # Exponential backoff: 1s, 2s, 4s
                    logging.warning(f"Download attempt {attempt + 1} failed for {url}: {result.error}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                
            except Exception as e:
                last_error = str(e)
                
                # If this isn't the last attempt, wait before retrying
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1.0
                    logging.warning(f"Download attempt {attempt + 1} failed for {url}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        
        # All retries failed
        logging.error(f"Download failed after {max_retries} attempts for {url}: {last_error}")
        return DownloadResult(
            url=url,
            success=False,
            error=f"Failed after {max_retries} attempts: {last_error}"
        )
    
    def _should_retry_error(self, error: str) -> bool:
        """
        Determine if an error should trigger a retry.
        
        Args:
            error: Error message to analyze
            
        Returns:
            True if should retry, False otherwise
        """
        if not error:
            return False
        
        error_lower = error.lower()
        
        # Retry on network-related errors
        retryable_errors = [
            'timeout',
            'connection',
            'network',
            'temporary',
            'server error',
            '500',
            '502',
            '503',
            '504',
            '429'  # Rate limiting
        ]
        
        return any(retryable_error in error_lower for retryable_error in retryable_errors)
    
    def get_stats(self) -> dict:
        """
        Get statistics about concurrent downloads.
        
        Returns:
            Dictionary with concurrency statistics
        """
        return {
            'max_workers': self.max_workers,
            'domains_tracked': len(self.domain_locks),
            'active_domains': list(self.domain_locks.keys())
        }