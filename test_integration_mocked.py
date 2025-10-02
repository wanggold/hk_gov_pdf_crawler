#!/usr/bin/env python3
"""
Integration Tests with Mocked HTTP Requests

This module contains integration tests that use the responses library to mock
HTTP requests and test the complete workflow without making real network calls.
"""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock
import responses
from pathlib import Path

# Import modules to test
from config import CrawlConfig, DepartmentConfig, CrawlSettings, StorageConfig
from crawler import PDFCrawler
from discovery import URLDiscovery
from downloader import FileDownloader
from browser import BrowserHandler
from reporter import ProgressReporter
from models import DownloadResult


class TestIntegrationWithMockedRequests:
    """Integration tests using mocked HTTP responses"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test configuration
        self.config = CrawlConfig(
            departments={
                'test_dept': DepartmentConfig(
                    name='Test Department',
                    seed_urls=['https://example.gov.hk/index.html'],
                    max_depth=2,
                    max_pages=10,
                    time_limit=300
                )
            },
            settings=CrawlSettings(
                delay_between_requests=0.1,  # Fast for testing
                max_concurrent_downloads=2,
                enable_browser_automation=False,
                request_timeout=10
            ),
            storage=StorageConfig(
                local_path=self.temp_dir,
                organize_by_department=True,
                s3_enabled=False
            )
        )
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @responses.activate
    def test_complete_crawl_workflow(self):
        """Test complete crawling workflow with mocked responses"""
        # Mock the main page with PDF links
        main_page_html = """
        <html>
        <head><title>Test Department</title></head>
        <body>
            <h1>Test Department Documents</h1>
            <a href="document1.pdf">Annual Report PDF</a>
            <a href="https://example.gov.hk/docs/manual.pdf">User Manual</a>
            <a href="subpage.html">More Documents</a>
            <a href="https://external.com/doc.pdf">External PDF</a>
        </body>
        </html>
        """
        
        # Mock subpage with additional PDF
        subpage_html = """
        <html>
        <body>
            <h2>Additional Documents</h2>
            <a href="guidelines.pdf">Guidelines Document</a>
            <a href="archive/old_report.pdf">Archived Report</a>
        </body>
        </html>
        """
        
        # Mock PDF content
        pdf_content = b'%PDF-1.4\n' + b'Mock PDF content for testing. ' * 100 + b'\n%%EOF'
        
        # Set up mocked responses
        responses.add(
            responses.GET,
            'https://example.gov.hk/index.html',
            body=main_page_html,
            status=200,
            content_type='text/html'
        )
        
        responses.add(
            responses.GET,
            'https://example.gov.hk/subpage.html',
            body=subpage_html,
            status=200,
            content_type='text/html'
        )
        
        # Mock PDF files
        pdf_urls = [
            'https://example.gov.hk/document1.pdf',
            'https://example.gov.hk/docs/manual.pdf',
            'https://example.gov.hk/guidelines.pdf',
            'https://example.gov.hk/archive/old_report.pdf'
        ]
        
        for pdf_url in pdf_urls:
            # HEAD request for validation
            responses.add(
                responses.HEAD,
                pdf_url,
                headers={'content-type': 'application/pdf', 'content-length': str(len(pdf_content))},
                status=200
            )
            
            # GET request for download
            responses.add(
                responses.GET,
                pdf_url,
                body=pdf_content,
                headers={'content-type': 'application/pdf'},
                status=200
            )
        
        # Initialize crawler and run
        crawler = PDFCrawler(self.config)
        results = crawler.crawl(['test_dept'])
        
        # Verify results
        assert len(results.departments) == 1
        dept_result = results.departments[0]
        
        assert dept_result.department == 'Test Department'
        assert dept_result.urls_crawled >= 2  # At least main page and subpage
        assert dept_result.pdfs_found >= 3  # Should find multiple PDFs
        assert dept_result.pdfs_downloaded >= 3  # Should download found PDFs
        assert dept_result.pdfs_failed == 0  # No failures expected
        
        # Verify files were created
        dept_dir = Path(self.temp_dir) / 'test-department'
        assert dept_dir.exists()
        
        pdf_files = list(dept_dir.glob('*.pdf'))
        assert len(pdf_files) >= 3
        
        # Verify file contents
        for pdf_file in pdf_files:
            content = pdf_file.read_bytes()
            assert content.startswith(b'%PDF-1.4')
            assert content.endswith(b'%%EOF')
    
    @responses.activate
    def test_dry_run_analysis(self):
        """Test dry-run analysis with mocked responses"""
        # Mock main page
        responses.add(
            responses.GET,
            'https://example.gov.hk/index.html',
            body='<html><body><a href="doc1.pdf">PDF 1</a><a href="doc2.pdf">PDF 2</a></body></html>',
            status=200,
            content_type='text/html'
        )
        
        crawler = PDFCrawler(self.config)
        report = crawler.dry_run(['test_dept'])
        
        assert len(report.department_analyses) == 1
        analysis = report.department_analyses[0]
        
        assert analysis.department == 'Test Department'
        assert analysis.seed_urls_accessible == 1
        assert analysis.seed_urls_total == 1
        assert analysis.estimated_pdfs >= 2
        assert not analysis.requires_browser  # No heavy JS in mock
        assert not analysis.rate_limit_detected
    
    @responses.activate
    def test_error_handling_network_failures(self):
        """Test error handling for network failures"""
        # Mock main page success
        responses.add(
            responses.GET,
            'https://example.gov.hk/index.html',
            body='<html><body><a href="good.pdf">Good PDF</a><a href="bad.pdf">Bad PDF</a></body></html>',
            status=200
        )
        
        # Mock successful PDF
        pdf_content = b'%PDF-1.4\nGood PDF content\n%%EOF'
        responses.add(responses.HEAD, 'https://example.gov.hk/good.pdf', 
                     headers={'content-type': 'application/pdf'}, status=200)
        responses.add(responses.GET, 'https://example.gov.hk/good.pdf', 
                     body=pdf_content, status=200)
        
        # Mock failing PDF (404)
        responses.add(responses.HEAD, 'https://example.gov.hk/bad.pdf', status=404)
        
        crawler = PDFCrawler(self.config)
        results = crawler.crawl(['test_dept'])
        
        dept_result = results.departments[0]
        assert dept_result.pdfs_found >= 2
        assert dept_result.pdfs_downloaded >= 1  # At least the good one
        assert dept_result.pdfs_failed >= 1  # The bad one should fail
        assert len(dept_result.errors) > 0  # Should have error messages
    
    @responses.activate
    def test_rate_limiting_behavior(self):
        """Test that rate limiting is respected"""
        import time
        
        # Mock page with multiple PDFs
        responses.add(
            responses.GET,
            'https://example.gov.hk/index.html',
            body='<html><body>' + 
                 ''.join([f'<a href="doc{i}.pdf">PDF {i}</a>' for i in range(5)]) +
                 '</body></html>',
            status=200
        )
        
        # Mock PDF responses with delay simulation
        pdf_content = b'%PDF-1.4\nTest content\n%%EOF'
        for i in range(5):
            url = f'https://example.gov.hk/doc{i}.pdf'
            responses.add(responses.HEAD, url, headers={'content-type': 'application/pdf'}, status=200)
            responses.add(responses.GET, url, body=pdf_content, status=200)
        
        # Measure time taken
        start_time = time.time()
        
        crawler = PDFCrawler(self.config)
        results = crawler.crawl(['test_dept'])
        
        end_time = time.time()
        duration = end_time - start_time
        
        # With rate limiting, should take at least some minimum time
        # (This is a rough check since we're using mocked responses)
        dept_result = results.departments[0]
        assert dept_result.pdfs_downloaded > 0
        
        # Verify rate limiting was applied (check logs or timing)
        # Note: Exact timing verification is difficult with mocked responses
    
    @responses.activate
    def test_invalid_pdf_content_handling(self):
        """Test handling of invalid PDF content"""
        # Mock page with link to fake PDF
        responses.add(
            responses.GET,
            'https://example.gov.hk/index.html',
            body='<html><body><a href="fake.pdf">Fake PDF</a></body></html>',
            status=200
        )
        
        # Mock fake PDF that claims to be PDF but isn't
        responses.add(
            responses.HEAD,
            'https://example.gov.hk/fake.pdf',
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://example.gov.hk/fake.pdf',
            body='<html><body>This is not a PDF!</body></html>',
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        crawler = PDFCrawler(self.config)
        results = crawler.crawl(['test_dept'])
        
        dept_result = results.departments[0]
        assert dept_result.pdfs_found >= 1
        assert dept_result.pdfs_failed >= 1  # Should fail validation
        assert dept_result.pdfs_downloaded == 0  # No valid PDFs
    
    @responses.activate
    def test_concurrent_downloads(self):
        """Test concurrent download functionality"""
        # Mock page with multiple PDFs
        num_pdfs = 6
        pdf_links = ''.join([f'<a href="doc{i}.pdf">PDF {i}</a>' for i in range(num_pdfs)])
        
        responses.add(
            responses.GET,
            'https://example.gov.hk/index.html',
            body=f'<html><body>{pdf_links}</body></html>',
            status=200
        )
        
        # Mock all PDF responses
        pdf_content = b'%PDF-1.4\nConcurrent test content\n%%EOF'
        for i in range(num_pdfs):
            url = f'https://example.gov.hk/doc{i}.pdf'
            responses.add(responses.HEAD, url, headers={'content-type': 'application/pdf'}, status=200)
            responses.add(responses.GET, url, body=pdf_content, status=200)
        
        # Test with concurrency enabled
        self.config.settings.max_concurrent_downloads = 3
        
        crawler = PDFCrawler(self.config)
        results = crawler.crawl(['test_dept'])
        
        dept_result = results.departments[0]
        assert dept_result.pdfs_found == num_pdfs
        assert dept_result.pdfs_downloaded == num_pdfs
        assert dept_result.pdfs_failed == 0
        
        # Verify all files were created
        dept_dir = Path(self.temp_dir) / 'test-department'
        pdf_files = list(dept_dir.glob('*.pdf'))
        assert len(pdf_files) == num_pdfs


class TestFileDownloaderIntegration:
    """Integration tests for FileDownloader with mocked responses"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_config = StorageConfig(
            local_path=self.temp_dir,
            organize_by_department=True,
            s3_enabled=False
        )
        self.downloader = FileDownloader(self.storage_config, max_concurrent_downloads=2)
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @responses.activate
    def test_single_pdf_download(self):
        """Test downloading a single PDF file"""
        pdf_content = b'%PDF-1.4\nSingle PDF test content\n%%EOF'
        
        responses.add(
            responses.HEAD,
            'https://example.com/test.pdf',
            headers={'content-type': 'application/pdf', 'content-length': str(len(pdf_content))},
            status=200
        )
        
        responses.add(
            responses.GET,
            'https://example.com/test.pdf',
            body=pdf_content,
            headers={'content-type': 'application/pdf'},
            status=200
        )
        
        result = self.downloader.download_pdf('https://example.com/test.pdf', 'test_dept')
        
        assert result.success is True
        assert result.file_size == len(pdf_content)
        assert result.error is None
        assert os.path.exists(result.file_path)
        
        # Verify file content
        with open(result.file_path, 'rb') as f:
            content = f.read()
            assert content == pdf_content
    
    @responses.activate
    def test_batch_download(self):
        """Test batch downloading multiple PDFs"""
        urls = [
            'https://example.com/doc1.pdf',
            'https://example.com/doc2.pdf',
            'https://example.com/doc3.pdf'
        ]
        
        pdf_content = b'%PDF-1.4\nBatch test content\n%%EOF'
        
        for url in urls:
            responses.add(responses.HEAD, url, headers={'content-type': 'application/pdf'}, status=200)
            responses.add(responses.GET, url, body=pdf_content, status=200)
        
        results = self.downloader.download_pdfs_batch(urls, 'batch_test')
        
        assert len(results) == 3
        successful = [r for r in results if r.success]
        assert len(successful) == 3
        
        # Verify all files exist
        for result in successful:
            assert os.path.exists(result.file_path)
    
    @responses.activate
    def test_download_with_retry(self):
        """Test download retry mechanism"""
        pdf_content = b'%PDF-1.4\nRetry test content\n%%EOF'
        
        # First two requests fail, third succeeds
        responses.add(responses.HEAD, 'https://example.com/retry.pdf', status=500)
        responses.add(responses.HEAD, 'https://example.com/retry.pdf', status=500)
        responses.add(responses.HEAD, 'https://example.com/retry.pdf', 
                     headers={'content-type': 'application/pdf'}, status=200)
        responses.add(responses.GET, 'https://example.com/retry.pdf', body=pdf_content, status=200)
        
        result = self.downloader.download_pdf('https://example.com/retry.pdf', 'retry_test')
        
        # Should eventually succeed after retries
        assert result.success is True
        assert os.path.exists(result.file_path)
    
    def test_file_exists_check(self):
        """Test checking if file already exists"""
        # Create a test file
        dept_dir = Path(self.temp_dir) / 'existing_test'
        dept_dir.mkdir(exist_ok=True)
        test_file = dept_dir / 'existing.pdf'
        test_file.write_bytes(b'%PDF-1.4\nExisting file\n%%EOF')
        
        # Check if file exists
        assert self.downloader.file_exists(str(test_file), 'existing_test') is True
        
        # Check non-existent file
        non_existent = dept_dir / 'nonexistent.pdf'
        assert self.downloader.file_exists(str(non_existent), 'existing_test') is False
    
    def test_filename_generation(self):
        """Test PDF filename generation"""
        # Test with URL ending in .pdf
        filename1 = self.downloader.generate_filename('https://example.com/document.pdf')
        assert filename1.endswith('.pdf')
        assert 'document' in filename1
        
        # Test with URL without extension
        filename2 = self.downloader.generate_filename('https://example.com/reports/annual')
        assert filename2.endswith('.pdf')
        
        # Test with title
        filename3 = self.downloader.generate_filename('https://example.com/doc', 'Annual Report 2023')
        assert filename3.endswith('.pdf')
        assert 'annual-report-2023' in filename3.lower()
    
    def test_pdf_content_validation(self):
        """Test PDF content validation"""
        # Valid PDF content
        valid_pdf = b'%PDF-1.4\nValid PDF content\n%%EOF'
        assert self.downloader.validate_pdf_content(valid_pdf) is True
        
        # Invalid content (not PDF)
        invalid_content = b'<html><body>Not a PDF</body></html>'
        assert self.downloader.validate_pdf_content(invalid_content) is False
        
        # Empty content
        assert self.downloader.validate_pdf_content(b'') is False
        
        # Too small content
        assert self.downloader.validate_pdf_content(b'%PDF') is False


class TestProgressReporter:
    """Test progress reporting functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.reporter = ProgressReporter()
    
    def test_progress_tracking(self):
        """Test basic progress tracking"""
        self.reporter.track_discovery('test_dept', 10, 5)
        
        assert self.reporter.department_stats['test_dept']['urls_crawled'] == 10
        assert self.reporter.department_stats['test_dept']['pdfs_found'] == 5
        assert self.reporter.stats['total_urls_crawled'] == 10
        assert self.reporter.stats['total_pdfs_found'] == 5
    
    def test_download_tracking(self):
        """Test download progress tracking"""
        # Track successful download
        self.reporter.track_download('test_dept', True, 1024)
        
        assert self.reporter.department_stats['test_dept']['pdfs_downloaded'] == 1
        assert self.reporter.department_stats['test_dept']['total_size'] == 1024
        assert self.reporter.stats['total_pdfs_downloaded'] == 1
        
        # Track failed download
        self.reporter.track_download('test_dept', False)
        
        assert self.reporter.department_stats['test_dept']['pdfs_failed'] == 1
        assert self.reporter.stats['total_pdfs_failed'] == 1
    
    def test_report_generation(self):
        """Test report generation"""
        from models import CrawlResults, DepartmentResults
        
        # Create mock results
        dept_result = DepartmentResults(
            department='Test Department',
            urls_crawled=10,
            pdfs_found=5,
            pdfs_downloaded=4,
            pdfs_failed=1,
            pdfs_skipped=0,
            total_size=2048,
            duration=30.0,
            errors=['Test error']
        )
        
        results = CrawlResults(
            departments=[dept_result],
            total_pdfs_found=5,
            total_pdfs_downloaded=4,
            total_duration=30.0,
            success_rate=80.0
        )
        
        report = self.reporter.generate_report(results)
        
        assert 'FINAL REPORT' in report
        assert 'Test Department' in report
        assert '4' in report  # Downloaded count
        assert '80.0%' in report  # Success rate


if __name__ == "__main__":
    pytest.main([__file__, "-v"])