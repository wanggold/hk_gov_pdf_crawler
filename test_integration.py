"""
Integration test for FileDownloader with SimpleConcurrency

This test verifies that the FileDownloader correctly uses the SimpleConcurrency
class for concurrent downloads with rate limiting.
"""

import os
import tempfile
import logging
from unittest.mock import Mock, patch
import requests_mock

from downloader import FileDownloader
from config import StorageConfig
from crawler import DownloadResult


# Configure logging for testing
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def test_batch_download_integration():
    """Test FileDownloader batch download with concurrent functionality"""
    print("\n=== Testing FileDownloader Batch Download Integration ===")
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Configure storage to use temp directory
        storage_config = StorageConfig(
            local_path=temp_dir,
            organize_by_department=True,
            s3_enabled=False
        )
        
        # Create FileDownloader with concurrency
        downloader = FileDownloader(storage_config, max_concurrent_downloads=3)
        
        # Test URLs from different domains
        test_urls = [
            "https://example.com/doc1.pdf",
            "https://test.gov.hk/doc2.pdf", 
            "https://another.com/doc3.pdf"
        ]
        
        # Mock PDF content (more realistic PDF structure)
        pdf_content = b'%PDF-1.4\n' + b'A' * 2000 + b'\n%%EOF'  # Minimum 1KB with proper PDF markers
        
        # Use requests_mock to mock HTTP responses
        with requests_mock.Mocker() as m:
            # Mock HEAD requests for validation
            for url in test_urls:
                m.head(url, headers={'content-type': 'application/pdf'})
                m.get(url, content=pdf_content, headers={'content-type': 'application/pdf'})
            
            # Test batch download
            results = downloader.download_pdfs_batch(test_urls, "test_department")
            
            # Verify results
            assert len(results) == len(test_urls), f"Expected {len(test_urls)} results, got {len(results)}"
            
            successful_downloads = [r for r in results if r.success]
            assert len(successful_downloads) == len(test_urls), f"Expected all downloads to succeed, got {len(successful_downloads)}/{len(test_urls)}"
            
            # Verify files were created
            for result in successful_downloads:
                assert result.file_path is not None, "File path should be set for successful downloads"
                assert os.path.exists(result.file_path), f"Downloaded file should exist: {result.file_path}"
                assert result.file_size > 0, "File size should be greater than 0"
            
            # Verify department organization
            dept_dir = os.path.join(temp_dir, "test_department")
            assert os.path.exists(dept_dir), "Department directory should be created"
            
            pdf_files = [f for f in os.listdir(dept_dir) if f.endswith('.pdf')]
            assert len(pdf_files) == len(test_urls), f"Expected {len(test_urls)} PDF files, found {len(pdf_files)}"
            
            print(f"✓ Successfully downloaded {len(successful_downloads)} PDFs to {dept_dir}")
            print(f"✓ Files created: {pdf_files}")


def test_empty_batch_download():
    """Test batch download with empty URL list"""
    print("\n=== Testing Empty Batch Download ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_config = StorageConfig(local_path=temp_dir, s3_enabled=False)
        downloader = FileDownloader(storage_config, max_concurrent_downloads=3)
        
        results = downloader.download_pdfs_batch([], "test_department")
        
        assert len(results) == 0, "Empty URL list should return empty results"
        print("✓ Empty batch download handled correctly")


def test_concurrent_stats():
    """Test that concurrency stats are accessible"""
    print("\n=== Testing Concurrency Stats Access ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_config = StorageConfig(local_path=temp_dir, s3_enabled=False)
        downloader = FileDownloader(storage_config, max_concurrent_downloads=2)
        
        # Get stats from the concurrency handler
        stats = downloader.concurrency.get_stats()
        
        assert stats['max_workers'] == 2, "Max workers should match configuration"
        assert 'domains_tracked' in stats, "Stats should include domains tracked"
        assert 'active_domains' in stats, "Stats should include active domains"
        
        print(f"✓ Concurrency stats accessible: {stats}")


def main():
    """Run all integration tests"""
    print("Starting FileDownloader + SimpleConcurrency integration tests...")
    
    try:
        test_batch_download_integration()
        test_empty_batch_download()
        test_concurrent_stats()
        
        print("\n🎉 All integration tests passed!")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise


if __name__ == "__main__":
    main()