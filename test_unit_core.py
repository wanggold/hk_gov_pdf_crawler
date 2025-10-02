#!/usr/bin/env python3
"""
Unit Tests for Core Functions

This module contains unit tests for the core functionality of the HK PDF Crawler,
including PDF detection, configuration loading, URL discovery, and utility functions.
"""

import pytest
import tempfile
import os
import yaml
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import modules to test
from config import (
    load_config, create_config_from_markdown, save_config_to_yaml,
    CrawlConfig, DepartmentConfig, CrawlSettings, StorageConfig
)
from discovery import URLDiscovery
from utils import (
    handle_error, retry_with_backoff, normalize_url, extract_domain,
    is_valid_url, sanitize_filename, UserAgentRotator, SessionManager
)
from models import DownloadResult, DepartmentResults, CrawlResults


class TestConfigurationLoading:
    """Test configuration loading and validation"""
    
    def test_load_valid_yaml_config(self):
        """Test loading a valid YAML configuration"""
        config_data = {
            'departments': {
                'test_dept': {
                    'name': 'Test Department',
                    'seed_urls': ['https://example.com'],
                    'max_depth': 2,
                    'max_pages': 100
                }
            },
            'settings': {
                'delay_between_requests': 1.5,
                'max_concurrent_downloads': 3
            },
            'storage': {
                'local_path': './test_downloads',
                's3_enabled': False
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = load_config(config_path)
            
            assert isinstance(config, CrawlConfig)
            assert len(config.departments) == 1
            assert 'test_dept' in config.departments
            
            dept = config.departments['test_dept']
            assert dept.name == 'Test Department'
            assert dept.seed_urls == ['https://example.com']
            assert dept.max_depth == 2
            assert dept.max_pages == 100
            
            assert config.settings.delay_between_requests == 1.5
            assert config.settings.max_concurrent_downloads == 3
            assert config.storage.local_path == './test_downloads'
            assert config.storage.s3_enabled is False
            
        finally:
            os.unlink(config_path)
    
    def test_load_config_missing_file(self):
        """Test loading configuration from non-existent file"""
        with pytest.raises(FileNotFoundError):
            load_config('/nonexistent/config.yaml')
    
    def test_load_config_invalid_yaml(self):
        """Test loading invalid YAML configuration"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('invalid: yaml: content: [')
            config_path = f.name
        
        try:
            with pytest.raises(yaml.YAMLError):
                load_config(config_path)
        finally:
            os.unlink(config_path)
    
    def test_load_config_missing_departments(self):
        """Test loading configuration without departments section"""
        config_data = {
            'settings': {'delay_between_requests': 1.0},
            'storage': {'local_path': './downloads'}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            with pytest.raises(ValueError, match="must contain 'departments'"):
                load_config(config_path)
        finally:
            os.unlink(config_path)
    
    def test_load_config_empty_departments(self):
        """Test loading configuration with empty departments"""
        config_data = {
            'departments': {},
            'settings': {'delay_between_requests': 1.0}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            with pytest.raises(ValueError, match="At least one department must be configured"):
                load_config(config_path)
        finally:
            os.unlink(config_path)
    
    def test_create_config_from_markdown(self):
        """Test creating configuration from markdown file"""
        markdown_content = """# Hong Kong Government Department PDF Resources

## 1. Buildings Department (BD):
1. **CoP**: https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html
2. **PNAP**: https://www.bd.gov.hk/en/resources/codes-and-references/practice-notes-and-circular-letters/index_pnap.html

## 2. Labour Department (LD):
1. **OSH Legislation**: https://www.labour.gov.hk/eng/legislat/contentB3.htm
2. **Occupational Safety**: https://www.labour.gov.hk/eng/public/content2_8.htm
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(markdown_content)
            markdown_path = f.name
        
        try:
            config = create_config_from_markdown(markdown_path)
            
            assert isinstance(config, CrawlConfig)
            assert len(config.departments) == 2
            
            # Check Buildings Department
            bd_key = 'buildings_department'
            assert bd_key in config.departments
            bd_dept = config.departments[bd_key]
            assert bd_dept.name == 'Buildings Department'
            assert len(bd_dept.seed_urls) == 2
            assert 'www.bd.gov.hk' in bd_dept.seed_urls[0]
            
            # Check Labour Department
            ld_key = 'labour_department'
            assert ld_key in config.departments
            ld_dept = config.departments[ld_key]
            assert ld_dept.name == 'Labour Department'
            assert len(ld_dept.seed_urls) == 2
            assert 'www.labour.gov.hk' in ld_dept.seed_urls[0]
            
        finally:
            os.unlink(markdown_path)
    
    def test_create_config_from_empty_markdown(self):
        """Test creating configuration from empty markdown file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Empty file\n\nNo departments here.")
            markdown_path = f.name
        
        try:
            with pytest.raises(ValueError, match="No departments found"):
                create_config_from_markdown(markdown_path)
        finally:
            os.unlink(markdown_path)
    
    def test_save_config_to_yaml(self):
        """Test saving configuration to YAML file"""
        config = CrawlConfig(
            departments={
                'test_dept': DepartmentConfig(
                    name='Test Department',
                    seed_urls=['https://example.com'],
                    max_depth=2
                )
            },
            settings=CrawlSettings(delay_between_requests=1.5),
            storage=StorageConfig(local_path='./test')
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            output_path = f.name
        
        try:
            save_config_to_yaml(config, output_path)
            
            # Verify file was created and can be loaded back
            assert os.path.exists(output_path)
            loaded_config = load_config(output_path)
            
            assert len(loaded_config.departments) == 1
            assert loaded_config.departments['test_dept'].name == 'Test Department'
            assert loaded_config.settings.delay_between_requests == 1.5
            
        finally:
            os.unlink(output_path)


class TestPDFDetection:
    """Test PDF link detection functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.discovery = URLDiscovery()
    
    def test_is_pdf_link_direct_extension(self):
        """Test PDF detection by file extension"""
        assert self.discovery.is_pdf_link("https://example.com/document.pdf")
        assert self.discovery.is_pdf_link("https://example.com/report.PDF")
        assert not self.discovery.is_pdf_link("https://example.com/page.html")
        assert not self.discovery.is_pdf_link("https://example.com/image.jpg")
    
    def test_is_pdf_link_url_patterns(self):
        """Test PDF detection by URL patterns"""
        assert self.discovery.is_pdf_link("https://example.com/download/file.pdf?version=1")
        assert self.discovery.is_pdf_link("https://example.com/documents/report.pdf&lang=en")
        assert self.discovery.is_pdf_link("https://example.com/files/doc?filetype=pdf")
        assert self.discovery.is_pdf_link("https://example.com/get?format=pdf&id=123")
    
    def test_is_pdf_link_text_analysis(self):
        """Test PDF detection by link text"""
        assert self.discovery.is_pdf_link("https://example.com/download", "Download PDF")
        assert self.discovery.is_pdf_link("https://example.com/doc", "View Document")
        assert self.discovery.is_pdf_link("https://example.com/report", "Annual Report")
        assert self.discovery.is_pdf_link("https://example.com/manual", "User Manual")
        
        # Should not match HTML-related text
        assert not self.discovery.is_pdf_link("https://example.com/page", "HTML Page")
        assert not self.discovery.is_pdf_link("https://example.com/web", "Webpage Content")
    
    def test_is_pdf_link_combined_criteria(self):
        """Test PDF detection with multiple criteria"""
        # URL pattern + text
        assert self.discovery.is_pdf_link("https://example.com/documents/file", "PDF Guide")
        
        # Extension takes precedence
        assert self.discovery.is_pdf_link("https://example.com/file.pdf", "HTML Content")
    
    @patch('discovery.URLDiscovery.session')
    def test_validate_pdf_url_success(self, mock_session):
        """Test PDF URL validation with successful response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_session.head.return_value = mock_response
        
        assert self.discovery.validate_pdf_url("https://example.com/test.pdf")
        mock_session.head.assert_called_once()
    
    @patch('discovery.URLDiscovery.session')
    def test_validate_pdf_url_wrong_content_type(self, mock_session):
        """Test PDF URL validation with wrong content type"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/html'}
        mock_session.head.return_value = mock_response
        
        # Should try GET request for further validation
        mock_get_response = Mock()
        mock_get_response.iter_content.return_value = [b'<html>']
        mock_session.get.return_value = mock_get_response
        
        assert not self.discovery.validate_pdf_url("https://example.com/test.html")
    
    @patch('discovery.URLDiscovery.session')
    def test_validate_pdf_url_pdf_signature(self, mock_session):
        """Test PDF URL validation with PDF signature check"""
        mock_head_response = Mock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {'content-type': 'application/octet-stream'}
        mock_session.head.return_value = mock_head_response
        
        mock_get_response = Mock()
        mock_get_response.iter_content.return_value = [b'%PDF-1.4']
        mock_session.get.return_value = mock_get_response
        
        assert self.discovery.validate_pdf_url("https://example.com/test.bin")


class TestURLDiscovery:
    """Test URL discovery functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.discovery = URLDiscovery()
    
    def test_reset_visited_urls(self):
        """Test resetting visited URLs"""
        self.discovery.visited_urls.add("https://example.com")
        assert len(self.discovery.visited_urls) == 1
        
        self.discovery.reset_visited_urls()
        assert len(self.discovery.visited_urls) == 0
    
    def test_get_visited_count(self):
        """Test getting visited URL count"""
        assert self.discovery.get_visited_count() == 0
        
        self.discovery.visited_urls.add("https://example.com")
        self.discovery.visited_urls.add("https://test.com")
        assert self.discovery.get_visited_count() == 2
    
    def test_check_robots_txt_hk_government(self):
        """Test robots.txt checking for HK government sites"""
        # Should allow HK government sites regardless of robots.txt
        assert self.discovery.check_robots_txt("www.bd.gov.hk")
        assert self.discovery.check_robots_txt("labour.gov.hk")
        assert self.discovery.check_robots_txt("www.fehd.gov.hk")
    
    @patch('discovery.RobotFileParser')
    def test_check_robots_txt_other_sites(self, mock_robot_parser):
        """Test robots.txt checking for non-government sites"""
        mock_rp = Mock()
        mock_rp.can_fetch.return_value = True
        mock_robot_parser.return_value = mock_rp
        
        result = self.discovery.check_robots_txt("example.com", "https://example.com/page")
        assert result is True
        mock_rp.can_fetch.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_handle_error_network_errors(self):
        """Test error handling for network errors"""
        import requests
        
        # Should retry network errors
        assert handle_error(requests.ConnectionError(), "test", "https://example.com") is True
        assert handle_error(requests.Timeout(), "test") is True
        
        # Should retry server errors
        mock_response = Mock()
        mock_response.status_code = 500
        http_error = requests.HTTPError()
        http_error.response = mock_response
        assert handle_error(http_error, "test") is True
        
        # Should not retry client errors
        mock_response.status_code = 404
        assert handle_error(http_error, "test") is False
        
        # Should not retry other errors
        assert handle_error(ValueError("test"), "test") is False
    
    def test_retry_with_backoff_decorator(self):
        """Test retry decorator with backoff"""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = failing_function()
        assert result == "success"
        assert call_count == 3
    
    def test_retry_with_backoff_max_retries(self):
        """Test retry decorator reaches max retries"""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            always_failing_function()
        
        assert call_count == 2
    
    def test_normalize_url(self):
        """Test URL normalization"""
        assert normalize_url("page.html", "https://example.com/") == "https://example.com/page.html"
        assert normalize_url("https://example.com/page.html") == "https://example.com/page.html"
        assert normalize_url("  https://example.com/page.html  ") == "https://example.com/page.html"
    
    def test_extract_domain(self):
        """Test domain extraction from URLs"""
        assert extract_domain("https://www.example.com/path") == "www.example.com"
        assert extract_domain("http://subdomain.example.com:8080/path") == "subdomain.example.com:8080"
        assert extract_domain("https://example.com") == "example.com"
    
    def test_is_valid_url(self):
        """Test URL validation"""
        assert is_valid_url("https://example.com") is True
        assert is_valid_url("http://example.com/path") is True
        assert is_valid_url("ftp://example.com") is False
        assert is_valid_url("not-a-url") is False
        assert is_valid_url("") is False
    
    def test_sanitize_filename(self):
        """Test filename sanitization"""
        assert sanitize_filename("normal_file.pdf") == "normal_file.pdf"
        assert sanitize_filename("file<with>bad:chars.pdf") == "file_with_bad_chars.pdf"
        assert sanitize_filename("file/with\\path|chars.pdf") == "file_with_path_chars.pdf"
        
        # Test length limiting
        long_name = "a" * 300 + ".pdf"
        sanitized = sanitize_filename(long_name)
        assert len(sanitized) <= 255
        assert sanitized.endswith(".pdf")
    
    def test_user_agent_rotator(self):
        """Test user agent rotation"""
        rotator = UserAgentRotator()
        
        # Test random user agent
        ua1 = rotator.get_random_user_agent()
        ua2 = rotator.get_random_user_agent()
        assert isinstance(ua1, str)
        assert len(ua1) > 0
        
        # Test sequential rotation
        ua_seq1 = rotator.get_next_user_agent()
        ua_seq2 = rotator.get_next_user_agent()
        assert ua_seq1 != ua_seq2  # Should be different (unless we're unlucky)
    
    def test_session_manager(self):
        """Test session manager"""
        manager = SessionManager(max_sessions=2)
        
        # Test session creation
        session1 = manager.get_session()
        assert session1 is not None
        assert hasattr(session1, 'headers')
        
        # Test session rotation
        session2 = manager.rotate_session()
        assert session2 is not None
        
        # Test random session
        random_session = manager.get_random_session()
        assert random_session is not None
        
        # Test user agent refresh
        old_ua = session1.headers.get('User-Agent')
        manager.refresh_user_agents()
        new_ua = session1.headers.get('User-Agent')
        # UA might be the same due to randomness, but method should not fail


class TestDataModels:
    """Test data model classes"""
    
    def test_download_result_creation(self):
        """Test DownloadResult model"""
        result = DownloadResult(
            url="https://example.com/test.pdf",
            success=True,
            file_path="/downloads/test.pdf",
            file_size=1024
        )
        
        assert result.url == "https://example.com/test.pdf"
        assert result.success is True
        assert result.file_path == "/downloads/test.pdf"
        assert result.file_size == 1024
        assert result.error is None
    
    def test_department_results_creation(self):
        """Test DepartmentResults model"""
        result = DepartmentResults(
            department="Test Department",
            urls_crawled=10,
            pdfs_found=5,
            pdfs_downloaded=4,
            pdfs_failed=1,
            pdfs_skipped=0,
            total_size=2048,
            duration=30.5,
            errors=["Error 1", "Error 2"]
        )
        
        assert result.department == "Test Department"
        assert result.urls_crawled == 10
        assert result.pdfs_found == 5
        assert result.pdfs_downloaded == 4
        assert result.pdfs_failed == 1
        assert result.pdfs_skipped == 0
        assert result.total_size == 2048
        assert result.duration == 30.5
        assert len(result.errors) == 2
    
    def test_crawl_results_creation(self):
        """Test CrawlResults model"""
        dept_result = DepartmentResults(
            department="Test",
            urls_crawled=5,
            pdfs_found=3,
            pdfs_downloaded=2,
            pdfs_failed=1,
            pdfs_skipped=0,
            total_size=1024,
            duration=15.0,
            errors=[]
        )
        
        result = CrawlResults(
            departments=[dept_result],
            total_pdfs_found=3,
            total_pdfs_downloaded=2,
            total_duration=15.0,
            success_rate=66.7
        )
        
        assert len(result.departments) == 1
        assert result.total_pdfs_found == 3
        assert result.total_pdfs_downloaded == 2
        assert result.total_duration == 15.0
        assert result.success_rate == 66.7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])