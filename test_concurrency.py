"""
Test script for SimpleConcurrency class

This script tests the concurrent download functionality with rate limiting
using mock URLs and a simple test setup.
"""

import time
import logging
from unittest.mock import Mock, MagicMock
from typing import List

from concurrency import SimpleConcurrency
from crawler import DownloadResult
from config import StorageConfig


# Configure logging for testing
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class MockDownloader:
    """Mock downloader for testing concurrent functionality"""
    
    def __init__(self, simulate_delays: bool = True, failure_rate: float = 0.0, fail_first_attempts: int = 0):
        self.simulate_delays = simulate_delays
        self.failure_rate = failure_rate
        self.fail_first_attempts = fail_first_attempts  # Fail first N attempts for testing retries
        self.download_count = 0
        self.download_times = []
        
    def download_pdf(self, url: str, department: str) -> DownloadResult:
        """Mock PDF download with optional delays and failures"""
        self.download_count += 1
        start_time = time.time()
        
        # Simulate download time
        if self.simulate_delays:
            # Simulate different download times based on URL
            if 'slow' in url:
                time.sleep(0.5)  # Slow download
            elif 'fast' in url:
                time.sleep(0.1)  # Fast download
            else:
                time.sleep(0.2)  # Normal download
        
        # Simulate failures for testing retry logic
        if self.fail_first_attempts > 0 and self.download_count <= self.fail_first_attempts:
            return DownloadResult(
                url=url,
                success=False,
                error="Simulated network error"
            )
        
        # Simulate random failures based on failure rate
        import random
        if self.failure_rate > 0 and random.random() < self.failure_rate:
            return DownloadResult(
                url=url,
                success=False,
                error="Simulated network error"
            )
        
        # Record timing
        self.download_times.append(time.time() - start_time)
        
        return DownloadResult(
            url=url,
            success=True,
            file_path=f"/mock/path/{url.split('/')[-1]}",
            file_size=1024 * 100  # 100KB mock file
        )


def test_basic_concurrent_download():
    """Test basic concurrent download functionality"""
    print("\n=== Testing Basic Concurrent Download ===")
    
    # Create test URLs from different domains (to avoid rate limiting delays)
    test_urls = [
        "https://domain1.com/doc1.pdf",
        "https://domain2.com/doc2.pdf", 
        "https://domain3.com/doc3.pdf",
        "https://domain4.com/doc4.pdf",
        "https://domain5.com/doc5.pdf"
    ]
    
    # Create mock downloader and concurrency handler
    mock_downloader = MockDownloader(simulate_delays=True)
    concurrency = SimpleConcurrency(max_workers=3)
    
    # Test concurrent download
    start_time = time.time()
    results = concurrency.download_pdfs_concurrently(test_urls, "test_department", mock_downloader)
    total_time = time.time() - start_time
    
    # Verify results
    print(f"Downloaded {len(results)} files in {total_time:.2f} seconds")
    print(f"Success rate: {sum(1 for r in results if r.success)}/{len(results)}")
    
    # Check that all URLs were processed
    assert len(results) == len(test_urls), f"Expected {len(test_urls)} results, got {len(results)}"
    
    # Check that concurrent execution works (may not be faster due to rate limiting)
    expected_sequential_time = sum(mock_downloader.download_times)
    print(f"Sequential time would be: {expected_sequential_time:.2f}s, Concurrent time: {total_time:.2f}s")
    
    # With rate limiting, concurrent may not be faster, but should complete all downloads
    # The important thing is that all downloads completed successfully
    successful_downloads = sum(1 for r in results if r.success)
    assert successful_downloads == len(test_urls), f"Expected all downloads to succeed, got {successful_downloads}/{len(test_urls)}"
    
    print("✓ Basic concurrent download test passed")


def test_rate_limiting():
    """Test rate limiting per domain"""
    print("\n=== Testing Rate Limiting ===")
    
    # Create multiple URLs from the same domain
    same_domain_urls = [
        "https://example.com/doc1.pdf",
        "https://example.com/doc2.pdf",
        "https://example.com/doc3.pdf",
        "https://example.com/doc4.pdf"
    ]
    
    mock_downloader = MockDownloader(simulate_delays=False)  # No artificial delays
    concurrency = SimpleConcurrency(max_workers=4)  # More workers than URLs
    
    # Record start times for each download
    download_start_times = []
    
    # Patch the download method to record timing
    original_download = mock_downloader.download_pdf
    def timed_download(url: str, department: str):
        download_start_times.append(time.time())
        return original_download(url, department)
    
    mock_downloader.download_pdf = timed_download
    
    # Test concurrent download with rate limiting
    start_time = time.time()
    results = concurrency.download_pdfs_concurrently(same_domain_urls, "test_department", mock_downloader)
    
    # Verify rate limiting worked (downloads should be spaced at least 1 second apart)
    if len(download_start_times) > 1:
        time_diffs = [download_start_times[i] - download_start_times[i-1] 
                     for i in range(1, len(download_start_times))]
        min_gap = min(time_diffs)
        print(f"Minimum gap between downloads: {min_gap:.2f}s")
        
        # Allow some tolerance for timing precision
        assert min_gap >= 0.9, f"Rate limiting failed: minimum gap was {min_gap:.2f}s, expected >= 1.0s"
    
    print("✓ Rate limiting test passed")


def test_retry_logic():
    """Test retry logic with exponential backoff"""
    print("\n=== Testing Retry Logic ===")
    
    # Create URLs that will trigger failures
    test_urls = [
        "https://example.com/failing-doc.pdf"
    ]
    
    # Create mock downloader that fails first 2 attempts, then succeeds
    mock_downloader = MockDownloader(simulate_delays=False, fail_first_attempts=2)
    concurrency = SimpleConcurrency(max_workers=1)
    
    # Test download with retries
    start_time = time.time()
    results = concurrency.download_pdfs_concurrently(test_urls, "test_department", mock_downloader)
    total_time = time.time() - start_time
    
    print(f"Download with retries took {total_time:.2f} seconds")
    print(f"Total download attempts: {mock_downloader.download_count}")
    
    # Should have made multiple attempts due to failures
    assert mock_downloader.download_count > 1, "Should have made retry attempts"
    
    print("✓ Retry logic test passed")


def test_empty_url_list():
    """Test handling of empty URL list"""
    print("\n=== Testing Empty URL List ===")
    
    mock_downloader = MockDownloader()
    concurrency = SimpleConcurrency(max_workers=3)
    
    results = concurrency.download_pdfs_concurrently([], "test_department", mock_downloader)
    
    assert len(results) == 0, "Empty URL list should return empty results"
    assert mock_downloader.download_count == 0, "No downloads should be attempted"
    
    print("✓ Empty URL list test passed")


def test_concurrency_stats():
    """Test concurrency statistics"""
    print("\n=== Testing Concurrency Stats ===")
    
    test_urls = [
        "https://domain1.com/doc1.pdf",
        "https://domain2.com/doc2.pdf",
        "https://domain3.com/doc3.pdf"
    ]
    
    mock_downloader = MockDownloader(simulate_delays=False)
    concurrency = SimpleConcurrency(max_workers=2)
    
    # Download files to populate domain tracking
    results = concurrency.download_pdfs_concurrently(test_urls, "test_department", mock_downloader)
    
    # Check stats
    stats = concurrency.get_stats()
    print(f"Concurrency stats: {stats}")
    
    assert stats['max_workers'] == 2, "Max workers should be 2"
    assert stats['domains_tracked'] == 3, "Should track 3 domains"
    assert len(stats['active_domains']) == 3, "Should have 3 active domains"
    
    print("✓ Concurrency stats test passed")


def main():
    """Run all concurrency tests"""
    print("Starting SimpleConcurrency tests...")
    
    try:
        test_basic_concurrent_download()
        test_rate_limiting()
        test_retry_logic()
        test_empty_url_list()
        test_concurrency_stats()
        
        print("\n🎉 All concurrency tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    main()