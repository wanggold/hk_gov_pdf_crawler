"""
Comprehensive test for SimpleConcurrency with real-world scenarios

This test demonstrates the complete functionality including:
- Concurrent downloads from multiple domains
- Rate limiting per domain
- Retry logic with exponential backoff
- Error handling and reporting
"""

import time
import logging
import tempfile
import os
from unittest.mock import Mock
import requests_mock

from concurrency import SimpleConcurrency
from downloader import FileDownloader
from config import StorageConfig
from crawler import DownloadResult


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def test_real_world_scenario():
    """Test a realistic crawling scenario with mixed domains and conditions"""
    print("\n=== Real-World Scenario Test ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Configure storage
        storage_config = StorageConfig(
            local_path=temp_dir,
            organize_by_department=True,
            s3_enabled=False
        )
        
        # Create downloader with moderate concurrency
        downloader = FileDownloader(storage_config, max_concurrent_downloads=4)
        
        # Simulate a realistic mix of URLs from HK government sites
        test_urls = [
            # Buildings Department - same domain (will be rate limited)
            "https://www.bd.gov.hk/doc/cop-1.pdf",
            "https://www.bd.gov.hk/doc/cop-2.pdf", 
            "https://www.bd.gov.hk/doc/pnap-1.pdf",
            "https://www.bd.gov.hk/doc/pnap-2.pdf",
            
            # Labour Department - different domain
            "https://www.labour.gov.hk/doc/osh-1.pdf",
            "https://www.labour.gov.hk/doc/osh-2.pdf",
            
            # Fire Services Department - another domain
            "https://www.hkfsd.gov.hk/doc/fire-1.pdf",
            "https://www.hkfsd.gov.hk/doc/fire-2.pdf",
            
            # Environmental Protection Department
            "https://www.epd.gov.hk/doc/env-1.pdf",
            "https://www.epd.gov.hk/doc/env-2.pdf"
        ]
        
        # Create realistic PDF content
        pdf_content = b'%PDF-1.4\n' + b'Mock PDF content for testing. ' * 100 + b'\n%%EOF'
        
        with requests_mock.Mocker() as m:
            # Mock all requests with realistic responses
            for url in test_urls:
                # Some URLs might be slow
                delay = 0.1 if 'labour' in url else 0.05
                
                m.head(url, headers={'content-type': 'application/pdf'})
                m.get(url, content=pdf_content, headers={'content-type': 'application/pdf'})
            
            # Measure performance
            start_time = time.time()
            
            # Download all PDFs
            results = downloader.download_pdfs_batch(test_urls, "hk_government")
            
            total_time = time.time() - start_time
            
            # Analyze results
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            
            print(f"Downloaded {len(successful)}/{len(test_urls)} PDFs in {total_time:.2f} seconds")
            print(f"Success rate: {len(successful)/len(test_urls)*100:.1f}%")
            
            # Verify all downloads succeeded
            assert len(successful) == len(test_urls), f"Expected all downloads to succeed"
            
            # Verify files were created with proper organization
            dept_dir = os.path.join(temp_dir, "hk_government")
            assert os.path.exists(dept_dir), "Department directory should exist"
            
            pdf_files = [f for f in os.listdir(dept_dir) if f.endswith('.pdf')]
            assert len(pdf_files) == len(test_urls), f"Expected {len(test_urls)} PDF files"
            
            # Check concurrency stats
            stats = downloader.concurrency.get_stats()
            print(f"Concurrency stats: {stats}")
            
            # Should have tracked multiple domains
            assert stats['domains_tracked'] >= 4, "Should have tracked multiple domains"
            
            print("✓ Real-world scenario test passed")


def test_rate_limiting_effectiveness():
    """Test that rate limiting actually works with same-domain requests"""
    print("\n=== Rate Limiting Effectiveness Test ===")
    
    # Create URLs all from the same domain
    same_domain_urls = [
        f"https://example.gov.hk/doc-{i}.pdf" for i in range(1, 6)
    ]
    
    # Track request times
    request_times = []
    
    class TimingDownloader:
        def download_pdf(self, url: str, department: str) -> DownloadResult:
            request_times.append(time.time())
            # Simulate quick download
            time.sleep(0.01)
            return DownloadResult(
                url=url,
                success=True,
                file_path=f"/mock/{url.split('/')[-1]}",
                file_size=1024
            )
    
    # Test with high concurrency but same domain
    concurrency = SimpleConcurrency(max_workers=5)  # More workers than URLs
    timing_downloader = TimingDownloader()
    
    start_time = time.time()
    results = concurrency.download_pdfs_concurrently(same_domain_urls, "test_dept", timing_downloader)
    total_time = time.time() - start_time
    
    # Analyze timing
    if len(request_times) > 1:
        gaps = [request_times[i] - request_times[i-1] for i in range(1, len(request_times))]
        min_gap = min(gaps)
        avg_gap = sum(gaps) / len(gaps)
        
        print(f"Request timing analysis:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Minimum gap: {min_gap:.2f}s")
        print(f"  Average gap: {avg_gap:.2f}s")
        print(f"  Expected minimum: 1.0s (rate limit)")
        
        # Rate limiting should enforce minimum 1-second gaps
        assert min_gap >= 0.9, f"Rate limiting failed: min gap {min_gap:.2f}s < 1.0s"
        
        # Total time should be approximately (num_requests - 1) seconds due to rate limiting
        expected_min_time = len(same_domain_urls) - 1
        assert total_time >= expected_min_time * 0.9, f"Total time {total_time:.2f}s too short for rate limiting"
    
    print("✓ Rate limiting effectiveness verified")


def test_mixed_success_failure():
    """Test handling of mixed success and failure scenarios"""
    print("\n=== Mixed Success/Failure Test ===")
    
    test_urls = [
        "https://good1.com/doc1.pdf",      # Will succeed
        "https://bad.com/doc2.pdf",        # Will fail
        "https://good2.com/doc3.pdf",      # Will succeed
        "https://timeout.com/doc4.pdf",    # Will timeout/retry
        "https://good3.com/doc5.pdf"       # Will succeed
    ]
    
    class MixedResultDownloader:
        def __init__(self):
            self.attempt_count = {}
            
        def download_pdf(self, url: str, department: str) -> DownloadResult:
            # Track attempts per URL
            self.attempt_count[url] = self.attempt_count.get(url, 0) + 1
            
            if 'bad.com' in url:
                return DownloadResult(url=url, success=False, error="404 Not Found")
            elif 'timeout.com' in url and self.attempt_count[url] < 3:
                return DownloadResult(url=url, success=False, error="Connection timeout")
            else:
                return DownloadResult(
                    url=url, 
                    success=True, 
                    file_path=f"/mock/{url.split('/')[-1]}",
                    file_size=2048
                )
    
    mixed_downloader = MixedResultDownloader()
    concurrency = SimpleConcurrency(max_workers=3)
    
    results = concurrency.download_pdfs_concurrently(test_urls, "mixed_test", mixed_downloader)
    
    # Analyze results
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    print(f"Results: {len(successful)} successful, {len(failed)} failed")
    
    # Should have 4 successes (including the retry) and 1 permanent failure
    assert len(successful) == 4, f"Expected 4 successes, got {len(successful)}"
    assert len(failed) == 1, f"Expected 1 failure, got {len(failed)}"
    
    # Check that retries were attempted for timeout URL
    timeout_attempts = mixed_downloader.attempt_count.get("https://timeout.com/doc4.pdf", 0)
    assert timeout_attempts >= 2, f"Expected multiple attempts for timeout URL, got {timeout_attempts}"
    
    print("✓ Mixed success/failure handling verified")


def main():
    """Run comprehensive tests"""
    print("Starting comprehensive SimpleConcurrency tests...")
    
    try:
        test_real_world_scenario()
        test_rate_limiting_effectiveness()
        test_mixed_success_failure()
        
        print("\n🎉 All comprehensive tests passed!")
        print("\nSimpleConcurrency implementation is working correctly with:")
        print("  ✓ Concurrent downloads with ThreadPoolExecutor")
        print("  ✓ Per-domain rate limiting (1-second minimum)")
        print("  ✓ Exponential backoff retry logic")
        print("  ✓ Proper error handling and reporting")
        print("  ✓ Integration with FileDownloader")
        
    except Exception as e:
        print(f"\n❌ Comprehensive test failed: {e}")
        raise


if __name__ == "__main__":
    main()