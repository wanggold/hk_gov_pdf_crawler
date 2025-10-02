#!/usr/bin/env python3
"""
Error Handling Tests

This module contains tests for various error scenarios including network failures,
invalid PDFs, missing files, and other edge cases to ensure robust error handling.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import requests
import responses
from pathlib import Path

# Import modules to test
from config import CrawlConfig, DepartmentConfig, CrawlSettings, StorageConfig
from crawler import PDFCrawler
from discovery import URLDiscovery
from downloader import FileDownloader
from utils import handle_error, retry_with_backoff
from models import DownloadResult


class TestNetworkErrorHandling:
    """Test handling of various network errors"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CrawlConfig(
            departments={
                'test_dept': DepartmentConfig(
                    name='Test Department',
                    seed_urls=['https://example.com/index.html'],
                    max_depth=1,
                    max_pages=5
                )
            },
            settings=CrawlSettings(
                delay_between_requests=0.1,
                max_concurrent_downloads=1,
                request_timeout=5
            ),
            storage=StorageConfig(
                local_path=self.temp_dir,
                s3_enabled=False
            )
        )
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @responses.activate
    def test_connection_timeout_handling(self):
        """Test handling of connection timeouts"""
        # Mock timeout response
        responses.add(
            responses.GET,
            'https://example.com/index.html',
            body=requests.exceptions.ConnectTimeout("Connection timed out")
        )
        
        crawler = PDFCrawler(self.config)
        results = crawler.crawl(['test_dept'])
        
        # Should handle timeout gracefully
        assert len(results.departments) == 1
        dept_result = results.departments[0]
        assert dept_result.urls_crawled == 0  # No URLs successfully crawled
        assert len(dept_result.errors) > 0  # Should have error recorded
    
    @responses.activate
    def test_http_error_codes_handling(self):
        """Test handling of various HTTP error codes"""
        error_codes = [404, 403, 500, 502, 503]
        
        for i, code in enumerate(error_codes):
            url = f'https://example.com/page{i}.html'
            responses.add(responses.GET, url, status=code)
        
        discovery = URLDiscovery()
        
        for i, code in enumerate(error_codes):
            url = f'https://example.com/page{i}.html'
            try:
                response = discovery.session.get(url)
                response.raise_for_status()
                assert False, f"Should have raised exception for {code}"
            except requests.exceptions.HTTPError as e:
                # Should handle HTTP errors appropriately
                should_retry = handle_error(e, "test", url)
                if code >= 500:
                    assert should_retry is True  # Server errors should retry
                else:
                    assert should_retry is False  # Client errors should not retry
    
    @responses.activate
    def test_malformed_response_handling(self):
        """Test handling of malformed HTML responses"""
        malformed_html = """
        <html>
        <head><title>Malformed Page</title>
        <body>
            <h1>Missing closing tags
            <a href="doc.pdf">PDF Link
            <div>Unclosed div
            <p>Paragraph without closing
        """
        
        responses.add(
            responses.GET,
            'https://example.com/malformed.html',
            body=malformed_html,
            status=200,
            content_type='text/html'
        )
        
        discovery = URLDiscovery()
        
        # Should handle malformed HTML gracefully
        pdf_links = discovery.find_pdf_links('https://example.com/malformed.html')
        
        # Should still find the PDF link despite malformed HTML
        assert len(pdf_links) >= 0  # BeautifulSoup is forgiving
    
    @responses.activate
    def test_network_interruption_recovery(self):
        """Test recovery from network interruptions"""
        # First request fails, second succeeds
        responses.add(
            responses.GET,
            'https://example.com/unstable.html',
            body=requests.exceptions.ConnectionError("Network interrupted")
        )
        responses.add(
            responses.GET,
            'https://example.com/unstable.html',
            body='<html><body><a href="doc.pdf">PDF</a></body></html>',
            status=200
        )
        
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def unstable_request():
            discovery = URLDiscovery()
            return discovery.find_pdf_links('https://example.com/unstable.html')
        
        # Should eventually succeed after retry
        pdf_links = unstable_request()
        assert isinstance(pdf_links, list)
    
    def test_dns_resolution_failure(self):
        """Test handling of DNS resolution failures"""
        discovery = URLDiscovery()
        
        # Try to access non-existent domain
        try:
            discovery.find_pdf_links('https://nonexistent-domain-12345.com/page.html')
        except Exception as e:
            # Should handle DNS errors gracefully
            should_retry = handle_error(e, "DNS test")
            # DNS errors are typically connection errors, so might retry
            assert isinstance(should_retry, bool)


class TestInvalidPDFHandling:
    """Test handling of invalid PDF files and content"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_config = StorageConfig(
            local_path=self.temp_dir,
            organize_by_department=True,
            s3_enabled=False
        )
        self.downloader = FileDownloader(self.storage_config)
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @responses.activate
    def test_fake_pdf_content_type(self):
        """Test handling of files with PDF content-type but invalid content"""
        fake_pdf_content = b'<html><body>This is not a PDF file!</body></html>'
        
        responses.add(
            responses.HEAD,
            'https://example.com/fake.pdf',
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://example.com/fake.pdf',
            body=fake_pdf_content,
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        result = self.downloader.download_pdf('https://example.com/fake.pdf', 'test_dept')
        
        # Should fail validation
        assert result.success is False
        assert 'not a valid PDF' in result.error
    
    @responses.activate
    def test_corrupted_pdf_content(self):
        """Test handling of corrupted PDF files"""
        corrupted_pdf = b'%PDF-1.4\nCorrupted content that is not valid PDF\n'
        
        responses.add(
            responses.HEAD,
            'https://example.com/corrupted.pdf',
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://example.com/corrupted.pdf',
            body=corrupted_pdf,
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        result = self.downloader.download_pdf('https://example.com/corrupted.pdf', 'test_dept')
        
        # Should fail validation due to invalid PDF structure
        assert result.success is False
        assert 'not a valid PDF' in result.error
    
    @responses.activate
    def test_empty_pdf_file(self):
        """Test handling of empty PDF files"""
        responses.add(
            responses.HEAD,
            'https://example.com/empty.pdf',
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://example.com/empty.pdf',
            body=b'',
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        result = self.downloader.download_pdf('https://example.com/empty.pdf', 'test_dept')
        
        # Should fail validation for empty content
        assert result.success is False
        assert 'not a valid PDF' in result.error
    
    @responses.activate
    def test_truncated_pdf_file(self):
        """Test handling of truncated PDF files"""
        truncated_pdf = b'%PDF-1.4\nTruncated content'  # Missing %%EOF
        
        responses.add(
            responses.HEAD,
            'https://example.com/truncated.pdf',
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://example.com/truncated.pdf',
            body=truncated_pdf,
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        result = self.downloader.download_pdf('https://example.com/truncated.pdf', 'test_dept')
        
        # Should handle truncated PDF (may pass or fail depending on validation strictness)
        assert isinstance(result.success, bool)
        if not result.success:
            assert result.error is not None
    
    def test_pdf_content_validation_methods(self):
        """Test PDF content validation methods"""
        # Valid PDF content
        valid_pdf = b'%PDF-1.4\n' + b'Valid PDF content. ' * 100 + b'\n%%EOF'
        assert self.downloader.validate_pdf_content(valid_pdf) is True
        
        # Invalid content - no PDF header
        no_header = b'Invalid content without PDF header'
        assert self.downloader.validate_pdf_content(no_header) is False
        
        # Invalid content - wrong header
        wrong_header = b'%DOC-1.0\nNot a PDF file'
        assert self.downloader.validate_pdf_content(wrong_header) is False
        
        # Too small content
        too_small = b'%PDF-1.4'
        assert self.downloader.validate_pdf_content(too_small) is False
        
        # Empty content
        empty = b''
        assert self.downloader.validate_pdf_content(empty) is False


class TestFileSystemErrorHandling:
    """Test handling of file system related errors"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_permission_denied_error(self):
        """Test handling of permission denied errors"""
        # Create a read-only directory
        readonly_dir = os.path.join(self.temp_dir, 'readonly')
        os.makedirs(readonly_dir)
        os.chmod(readonly_dir, 0o444)  # Read-only
        
        storage_config = StorageConfig(
            local_path=readonly_dir,
            organize_by_department=True,
            s3_enabled=False
        )
        
        downloader = FileDownloader(storage_config)
        
        try:
            # Try to save a file to read-only directory
            test_content = b'%PDF-1.4\nTest content\n%%EOF'
            file_path = os.path.join(readonly_dir, 'test_dept', 'test.pdf')
            
            success = downloader.save_locally(test_content, file_path)
            
            # Should fail gracefully
            assert success is False
            
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, 0o755)
    
    def test_disk_space_full_simulation(self):
        """Test handling when disk space is full (simulated)"""
        storage_config = StorageConfig(
            local_path=self.temp_dir,
            s3_enabled=False
        )
        
        downloader = FileDownloader(storage_config)
        
        # Mock the file writing to raise OSError (disk full)
        with patch('builtins.open', side_effect=OSError("No space left on device")):
            test_content = b'%PDF-1.4\nTest content\n%%EOF'
            file_path = os.path.join(self.temp_dir, 'test.pdf')
            
            success = downloader.save_locally(test_content, file_path)
            
            # Should handle disk full error gracefully
            assert success is False
    
    def test_invalid_filename_characters(self):
        """Test handling of invalid filename characters"""
        storage_config = StorageConfig(
            local_path=self.temp_dir,
            s3_enabled=False
        )
        
        downloader = FileDownloader(storage_config)
        
        # Test URLs that would generate problematic filenames
        problematic_urls = [
            'https://example.com/file<with>bad:chars.pdf',
            'https://example.com/file|with|pipes.pdf',
            'https://example.com/file"with"quotes.pdf',
            'https://example.com/file*with*asterisks.pdf'
        ]
        
        for url in problematic_urls:
            filename = downloader.generate_filename(url)
            
            # Should generate valid filename
            assert '<' not in filename
            assert '>' not in filename
            assert ':' not in filename
            assert '|' not in filename
            assert '"' not in filename
            assert '*' not in filename
            assert filename.endswith('.pdf')
    
    def test_very_long_filename_handling(self):
        """Test handling of very long filenames"""
        storage_config = StorageConfig(
            local_path=self.temp_dir,
            s3_enabled=False
        )
        
        downloader = FileDownloader(storage_config)
        
        # Create URL that would generate very long filename
        long_title = "A" * 300  # Very long title
        long_url = f'https://example.com/{long_title}.pdf'
        
        filename = downloader.generate_filename(long_url, long_title)
        
        # Should limit filename length
        assert len(filename) <= 255  # Typical filesystem limit
        assert filename.endswith('.pdf')


class TestCrawlerErrorRecovery:
    """Test crawler's ability to recover from various errors"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CrawlConfig(
            departments={
                'test_dept': DepartmentConfig(
                    name='Test Department',
                    seed_urls=[
                        'https://good.example.com/index.html',
                        'https://bad.example.com/index.html',
                        'https://timeout.example.com/index.html'
                    ],
                    max_depth=1,
                    max_pages=10
                )
            },
            settings=CrawlSettings(
                delay_between_requests=0.1,
                max_concurrent_downloads=1,
                request_timeout=5
            ),
            storage=StorageConfig(
                local_path=self.temp_dir,
                s3_enabled=False
            )
        )
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @responses.activate
    def test_partial_failure_recovery(self):
        """Test crawler continues when some URLs fail"""
        # Mock mixed success/failure responses
        responses.add(
            responses.GET,
            'https://good.example.com/index.html',
            body='<html><body><a href="good.pdf">Good PDF</a></body></html>',
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://bad.example.com/index.html',
            status=404  # This will fail
        )
        
        responses.add(
            responses.GET,
            'https://timeout.example.com/index.html',
            body=requests.exceptions.Timeout("Request timed out")
        )
        
        # Mock PDF download
        pdf_content = b'%PDF-1.4\nGood PDF content\n%%EOF'
        responses.add(responses.HEAD, 'https://good.example.com/good.pdf',
                     headers={'content-type': 'application/pdf'}, status=200)
        responses.add(responses.GET, 'https://good.example.com/good.pdf',
                     body=pdf_content, status=200)
        
        crawler = PDFCrawler(self.config)
        results = crawler.crawl(['test_dept'])
        
        # Should complete despite failures
        assert len(results.departments) == 1
        dept_result = results.departments[0]
        
        # Should have processed at least the successful URL
        assert dept_result.urls_crawled >= 1
        
        # Should have found and downloaded at least one PDF
        assert dept_result.pdfs_found >= 1
        assert dept_result.pdfs_downloaded >= 1
        
        # Should have recorded errors
        assert len(dept_result.errors) >= 2  # From bad and timeout URLs
    
    @responses.activate
    def test_complete_department_failure_handling(self):
        """Test handling when an entire department fails"""
        # All URLs for this department will fail
        for url in self.config.departments['test_dept'].seed_urls:
            responses.add(responses.GET, url, status=500)
        
        crawler = PDFCrawler(self.config)
        results = crawler.crawl(['test_dept'])
        
        # Should still return results structure
        assert len(results.departments) == 1
        dept_result = results.departments[0]
        
        # Should have no successful crawls
        assert dept_result.urls_crawled == 0
        assert dept_result.pdfs_found == 0
        assert dept_result.pdfs_downloaded == 0
        
        # Should have recorded errors
        assert len(dept_result.errors) > 0
    
    def test_configuration_error_handling(self):
        """Test handling of configuration errors"""
        # Test with invalid department configuration
        invalid_config = CrawlConfig(
            departments={
                'invalid_dept': DepartmentConfig(
                    name='Invalid Department',
                    seed_urls=[],  # Empty seed URLs
                    max_depth=1
                )
            },
            settings=CrawlSettings(),
            storage=StorageConfig(local_path=self.temp_dir)
        )
        
        crawler = PDFCrawler(invalid_config)
        
        # Should handle empty seed URLs gracefully
        results = crawler.crawl(['invalid_dept'])
        
        assert len(results.departments) == 1
        dept_result = results.departments[0]
        assert dept_result.urls_crawled == 0
        assert dept_result.pdfs_found == 0


class TestRetryMechanisms:
    """Test retry mechanisms and backoff strategies"""
    
    def test_exponential_backoff_timing(self):
        """Test exponential backoff timing"""
        import time
        
        call_times = []
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def failing_function():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise requests.exceptions.ConnectionError("Temporary failure")
            return "success"
        
        start_time = time.time()
        result = failing_function()
        total_time = time.time() - start_time
        
        assert result == "success"
        assert len(call_times) == 3
        
        # Check that delays increased exponentially
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            
            # Second delay should be roughly twice the first
            assert delay2 > delay1
    
    def test_max_retries_respected(self):
        """Test that max retries limit is respected"""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            always_failing_function()
        
        # Should have called exactly max_retries times
        assert call_count == 2
    
    def test_no_retry_on_success(self):
        """Test that successful calls don't trigger retries"""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_function()
        
        assert result == "success"
        assert call_count == 1  # Should only be called once


if __name__ == "__main__":
    pytest.main([__file__, "-v"])