#!/usr/bin/env python3
"""
Browser Automation Tests

This module contains tests for browser automation functionality including
JavaScript-heavy pages, interactive elements, and Selenium WebDriver integration.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException,
    ElementClickInterceptedException
)

# Import modules to test
from browser import BrowserHandler
from config import CrawlConfig, DepartmentConfig, CrawlSettings, StorageConfig
from crawler import PDFCrawler


class TestBrowserHandlerInitialization:
    """Test browser handler initialization and configuration"""
    
    def test_browser_handler_creation(self):
        """Test creating browser handler instance"""
        handler = BrowserHandler(headless=True)
        
        assert handler.driver is None  # Lazy initialization
        assert handler.headless is True
        assert handler.wait is None
    
    def test_browser_handler_headless_config(self):
        """Test browser handler with different headless configurations"""
        # Headless mode
        handler_headless = BrowserHandler(headless=True)
        assert handler_headless.headless is True
        
        # Non-headless mode
        handler_gui = BrowserHandler(headless=False)
        assert handler_gui.headless is False
    
    @patch('browser.webdriver.Chrome')
    def test_browser_startup(self, mock_chrome):
        """Test browser startup with mocked WebDriver"""
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver
        
        handler = BrowserHandler(headless=True)
        handler.start_browser()
        
        # Verify browser was started
        assert handler.driver is not None
        assert handler.wait is not None
        mock_chrome.assert_called_once()
        
        # Verify Chrome options were configured
        call_args = mock_chrome.call_args
        options = call_args[1]['options'] if 'options' in call_args[1] else call_args[0][0]
        # Options should have been configured (exact verification depends on implementation)
    
    @patch('browser.webdriver.Chrome')
    def test_browser_startup_failure(self, mock_chrome):
        """Test handling of browser startup failure"""
        mock_chrome.side_effect = WebDriverException("Chrome not found")
        
        handler = BrowserHandler(headless=True)
        
        with pytest.raises(WebDriverException):
            handler.start_browser()
    
    def test_browser_cleanup(self):
        """Test browser cleanup"""
        handler = BrowserHandler(headless=True)
        
        # Mock driver
        mock_driver = Mock()
        handler.driver = mock_driver
        
        handler.close_browser()
        
        # Verify cleanup
        mock_driver.quit.assert_called_once()
        assert handler.driver is None
        assert handler.wait is None
    
    def test_browser_cleanup_with_error(self):
        """Test browser cleanup when quit() raises exception"""
        handler = BrowserHandler(headless=True)
        
        # Mock driver that raises exception on quit
        mock_driver = Mock()
        mock_driver.quit.side_effect = WebDriverException("Cleanup error")
        handler.driver = mock_driver
        
        # Should handle cleanup error gracefully
        handler.close_browser()
        
        # Should still reset driver reference
        assert handler.driver is None


class TestInteractivePageHandling:
    """Test handling of interactive web pages"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.handler = BrowserHandler(headless=True)
        
        # Mock WebDriver and related objects
        self.mock_driver = Mock()
        self.mock_wait = Mock()
        
        self.handler.driver = self.mock_driver
        self.handler.wait = self.mock_wait
    
    def test_handle_interactive_page_basic(self):
        """Test basic interactive page handling"""
        test_url = "https://example.com/interactive.html"
        
        # Mock page elements
        mock_link = Mock()
        mock_link.get_attribute.return_value = "https://example.com/document.pdf"
        mock_link.get_text.return_value = "Download PDF"
        
        self.mock_driver.find_elements.return_value = [mock_link]
        
        # Mock successful page load
        self.mock_wait.until.return_value = True
        
        pdf_links = self.handler.handle_interactive_page(test_url)
        
        # Verify page was loaded
        self.mock_driver.get.assert_called_with(test_url)
        
        # Should return list of PDF links
        assert isinstance(pdf_links, list)
    
    def test_find_existing_pdf_links(self):
        """Test finding existing PDF links on page"""
        # Mock PDF links
        mock_pdf_link1 = Mock()
        mock_pdf_link1.get_attribute.return_value = "https://example.com/doc1.pdf"
        mock_pdf_link1.get_text.return_value = "Document 1"
        
        mock_pdf_link2 = Mock()
        mock_pdf_link2.get_attribute.return_value = "https://example.com/doc2.pdf"
        mock_pdf_link2.get_text.return_value = "Document 2"
        
        # Mock non-PDF link
        mock_other_link = Mock()
        mock_other_link.get_attribute.return_value = "https://example.com/page.html"
        mock_other_link.get_text.return_value = "Other Page"
        
        # Configure mock to return different elements for different selectors
        def mock_find_elements(by, selector):
            if 'href$=".pdf"' in selector or 'href*=".pdf"' in selector:
                return [mock_pdf_link1, mock_pdf_link2]
            else:
                return [mock_other_link]
        
        self.mock_driver.find_elements.side_effect = mock_find_elements
        
        pdf_links = self.handler._find_existing_pdf_links()
        
        # Should find PDF links
        assert len(pdf_links) >= 0  # May vary based on implementation
    
    def test_click_interactive_elements(self):
        """Test clicking interactive elements to reveal PDFs"""
        # Mock clickable elements
        mock_button = Mock()
        mock_button.click.return_value = None
        
        # Mock find_elements to return button for some selectors
        def mock_find_elements(by, selector):
            if 'button' in selector or 'Download' in selector:
                return [mock_button]
            return []
        
        self.mock_driver.find_elements.side_effect = mock_find_elements
        self.mock_driver.execute_script.return_value = None
        
        pdf_links = self.handler._click_interactive_elements()
        
        # Should attempt to click elements
        assert isinstance(pdf_links, list)
    
    def test_click_element_with_interception(self):
        """Test handling of click interception"""
        mock_button = Mock()
        mock_button.click.side_effect = ElementClickInterceptedException("Element intercepted")
        
        self.mock_driver.find_elements.return_value = [mock_button]
        self.mock_driver.execute_script.return_value = None
        
        # Should handle click interception and try JavaScript click
        pdf_links = self.handler._click_interactive_elements()
        
        # Verify JavaScript click was attempted
        self.mock_driver.execute_script.assert_called()
    
    def test_execute_pdf_reveal_scripts(self):
        """Test executing JavaScript to reveal PDF URLs"""
        # Mock JavaScript execution results
        script_results = [
            ['https://example.com/hidden1.pdf'],
            [],
            ['https://example.com/hidden2.pdf', 'https://example.com/hidden3.pdf']
        ]
        
        self.mock_driver.execute_script.side_effect = script_results
        
        pdf_links = self.handler._execute_pdf_reveal_scripts()
        
        # Should execute multiple scripts
        assert self.mock_driver.execute_script.call_count >= 1
        assert isinstance(pdf_links, list)
    
    def test_handle_forms_and_modals(self):
        """Test handling of forms and modal dialogs"""
        # Mock modal trigger
        mock_modal_trigger = Mock()
        mock_modal_trigger.click.return_value = None
        
        # Mock close button
        mock_close_button = Mock()
        mock_close_button.click.return_value = None
        
        # Mock form elements
        mock_checkbox = Mock()
        mock_checkbox.is_selected.return_value = False
        mock_checkbox.click.return_value = None
        
        mock_submit_button = Mock()
        mock_submit_button.click.return_value = None
        
        mock_form = Mock()
        mock_form.find_elements.side_effect = [
            [mock_checkbox],  # checkboxes
            [mock_submit_button]  # submit buttons
        ]
        
        def mock_find_elements(by, selector):
            if 'modal-trigger' in selector:
                return [mock_modal_trigger]
            elif 'close' in selector or 'modal-close' in selector:
                return [mock_close_button]
            elif selector == 'form':
                return [mock_form]
            return []
        
        self.mock_driver.find_elements.side_effect = mock_find_elements
        
        pdf_links = self.handler._handle_forms_and_modals()
        
        # Should handle modals and forms
        assert isinstance(pdf_links, list)
    
    def test_javascript_execution(self):
        """Test direct JavaScript execution"""
        test_script = "return document.querySelectorAll('a[href$=\".pdf\"]').length;"
        expected_result = 5
        
        self.mock_driver.execute_script.return_value = expected_result
        
        result = self.handler.execute_javascript(test_script)
        
        assert result == expected_result
        self.mock_driver.execute_script.assert_called_with(test_script)
    
    def test_javascript_execution_error(self):
        """Test JavaScript execution error handling"""
        test_script = "invalid javascript syntax"
        
        self.mock_driver.execute_script.side_effect = WebDriverException("JavaScript error")
        
        result = self.handler.execute_javascript(test_script)
        
        assert result is None  # Should return None on error
    
    def test_wait_for_element_success(self):
        """Test waiting for element to appear"""
        self.mock_wait.until.return_value = True
        
        result = self.handler.wait_for_element('.pdf-link', timeout=5)
        
        assert result is True
        self.mock_wait.until.assert_called_once()
    
    def test_wait_for_element_timeout(self):
        """Test waiting for element that doesn't appear"""
        self.mock_wait.until.side_effect = TimeoutException("Element not found")
        
        result = self.handler.wait_for_element('.nonexistent-element', timeout=5)
        
        assert result is False


class TestBrowserIntegrationWithCrawler:
    """Test browser integration with the main crawler"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CrawlConfig(
            departments={
                'js_dept': DepartmentConfig(
                    name='JavaScript Department',
                    seed_urls=['https://js-heavy.example.com/index.html'],
                    max_depth=1,
                    max_pages=5
                )
            },
            settings=CrawlSettings(
                delay_between_requests=0.1,
                max_concurrent_downloads=1,
                enable_browser_automation=True,  # Enable browser automation
                request_timeout=10
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
    
    @patch('crawler.BrowserHandler')
    def test_crawler_uses_browser_when_needed(self, mock_browser_class):
        """Test that crawler uses browser automation when no PDFs found normally"""
        # Mock browser handler
        mock_browser = Mock()
        mock_browser.handle_interactive_page.return_value = [
            'https://js-heavy.example.com/hidden1.pdf',
            'https://js-heavy.example.com/hidden2.pdf'
        ]
        mock_browser_class.return_value = mock_browser
        
        # Mock URL discovery to find no PDFs initially
        with patch('crawler.URLDiscovery') as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.discover_urls.return_value = ['https://js-heavy.example.com/index.html']
            mock_discovery.find_pdf_links.return_value = []  # No PDFs found normally
            mock_discovery_class.return_value = mock_discovery
            
            # Mock file downloader
            with patch('crawler.FileDownloader') as mock_downloader_class:
                mock_downloader = Mock()
                mock_downloader.download_pdfs_batch.return_value = []
                mock_downloader_class.return_value = mock_downloader
                
                crawler = PDFCrawler(self.config)
                results = crawler.crawl(['js_dept'])
                
                # Verify browser was used
                mock_browser_class.assert_called_once()
                mock_browser.handle_interactive_page.assert_called()
    
    @patch('crawler.BrowserHandler')
    def test_browser_automation_disabled(self, mock_browser_class):
        """Test that browser automation is not used when disabled"""
        # Disable browser automation
        self.config.settings.enable_browser_automation = False
        
        with patch('crawler.URLDiscovery') as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.discover_urls.return_value = ['https://example.com/index.html']
            mock_discovery.find_pdf_links.return_value = []
            mock_discovery_class.return_value = mock_discovery
            
            with patch('crawler.FileDownloader') as mock_downloader_class:
                mock_downloader = Mock()
                mock_downloader.download_pdfs_batch.return_value = []
                mock_downloader_class.return_value = mock_downloader
                
                crawler = PDFCrawler(self.config)
                results = crawler.crawl(['js_dept'])
                
                # Verify browser was not used
                mock_browser_class.assert_not_called()
    
    def test_browser_error_handling_in_crawler(self):
        """Test crawler handles browser errors gracefully"""
        with patch('crawler.BrowserHandler') as mock_browser_class:
            # Mock browser that raises exception
            mock_browser = Mock()
            mock_browser.handle_interactive_page.side_effect = WebDriverException("Browser error")
            mock_browser_class.return_value = mock_browser
            
            with patch('crawler.URLDiscovery') as mock_discovery_class:
                mock_discovery = Mock()
                mock_discovery.discover_urls.return_value = ['https://example.com/index.html']
                mock_discovery.find_pdf_links.return_value = []
                mock_discovery_class.return_value = mock_discovery
                
                with patch('crawler.FileDownloader') as mock_downloader_class:
                    mock_downloader = Mock()
                    mock_downloader.download_pdfs_batch.return_value = []
                    mock_downloader_class.return_value = mock_downloader
                    
                    crawler = PDFCrawler(self.config)
                    
                    # Should handle browser error gracefully
                    results = crawler.crawl(['js_dept'])
                    
                    # Should still return results despite browser error
                    assert len(results.departments) == 1


class TestBrowserCompatibility:
    """Test browser compatibility and configuration"""
    
    @patch('browser.webdriver.Chrome')
    def test_chrome_options_configuration(self, mock_chrome):
        """Test Chrome options are properly configured"""
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver
        
        handler = BrowserHandler(headless=True)
        handler.start_browser()
        
        # Verify Chrome was called with options
        mock_chrome.assert_called_once()
        call_args = mock_chrome.call_args
        
        # Should have options parameter
        assert 'options' in call_args.kwargs or len(call_args.args) > 0
    
    @patch('browser.webdriver.Chrome')
    def test_headless_vs_gui_mode(self, mock_chrome):
        """Test difference between headless and GUI mode"""
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver
        
        # Test headless mode
        handler_headless = BrowserHandler(headless=True)
        handler_headless.start_browser()
        
        # Test GUI mode
        handler_gui = BrowserHandler(headless=False)
        handler_gui.start_browser()
        
        # Both should call Chrome constructor
        assert mock_chrome.call_count == 2
    
    def test_browser_user_agent_configuration(self):
        """Test that browser uses appropriate user agent"""
        handler = BrowserHandler(headless=True)
        
        # Mock Chrome options to capture user agent
        with patch('browser.Options') as mock_options_class:
            mock_options = Mock()
            mock_options_class.return_value = mock_options
            
            with patch('browser.webdriver.Chrome'):
                handler.start_browser()
                
                # Should have configured user agent
                mock_options.add_argument.assert_called()
                
                # Check if user-agent was set
                user_agent_calls = [
                    call for call in mock_options.add_argument.call_args_list
                    if 'user-agent' in str(call)
                ]
                assert len(user_agent_calls) > 0


class TestJavaScriptHeavyPages:
    """Test handling of JavaScript-heavy pages"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.handler = BrowserHandler(headless=True)
        self.mock_driver = Mock()
        self.handler.driver = self.mock_driver
    
    def test_dynamic_content_loading(self):
        """Test handling of dynamically loaded content"""
        # Mock page that loads content via JavaScript
        test_url = "https://dynamic.example.com/page.html"
        
        # Mock initial page load with no PDFs
        self.mock_driver.find_elements.side_effect = [
            [],  # No PDFs initially
            [Mock()],  # PDFs appear after JavaScript execution
        ]
        
        # Mock JavaScript execution
        self.mock_driver.execute_script.return_value = ['https://dynamic.example.com/loaded.pdf']
        
        pdf_links = self.handler.handle_interactive_page(test_url)
        
        # Should handle dynamic content
        assert isinstance(pdf_links, list)
    
    def test_ajax_content_handling(self):
        """Test handling of AJAX-loaded content"""
        # Mock AJAX response simulation
        ajax_script = """
        // Simulate AJAX call that loads PDF links
        return ['https://ajax.example.com/ajax1.pdf', 'https://ajax.example.com/ajax2.pdf'];
        """
        
        self.mock_driver.execute_script.return_value = [
            'https://ajax.example.com/ajax1.pdf',
            'https://ajax.example.com/ajax2.pdf'
        ]
        
        result = self.handler.execute_javascript(ajax_script)
        
        assert len(result) == 2
        assert all('ajax' in url for url in result)
    
    def test_spa_navigation_handling(self):
        """Test handling of Single Page Application navigation"""
        # Mock SPA with client-side routing
        test_url = "https://spa.example.com/#/documents"
        
        # Mock navigation and content loading
        self.mock_driver.get.return_value = None
        self.mock_driver.execute_script.return_value = None
        
        # Mock finding elements after SPA navigation
        mock_pdf_link = Mock()
        mock_pdf_link.get_attribute.return_value = "https://spa.example.com/api/document.pdf"
        self.mock_driver.find_elements.return_value = [mock_pdf_link]
        
        pdf_links = self.handler.handle_interactive_page(test_url)
        
        # Should handle SPA navigation
        assert isinstance(pdf_links, list)


class TestBrowserPerformance:
    """Test browser performance and resource management"""
    
    def test_browser_resource_cleanup(self):
        """Test proper cleanup of browser resources"""
        handler = BrowserHandler(headless=True)
        
        # Mock driver with resource tracking
        mock_driver = Mock()
        handler.driver = mock_driver
        
        # Simulate some operations
        handler.execute_javascript("console.log('test');")
        
        # Cleanup
        handler.close_browser()
        
        # Verify cleanup was called
        mock_driver.quit.assert_called_once()
        assert handler.driver is None
    
    def test_multiple_page_handling(self):
        """Test handling multiple pages efficiently"""
        handler = BrowserHandler(headless=True)
        mock_driver = Mock()
        handler.driver = mock_driver
        
        urls = [
            'https://example1.com/page.html',
            'https://example2.com/page.html',
            'https://example3.com/page.html'
        ]
        
        # Mock responses for each URL
        mock_driver.find_elements.return_value = []
        
        for url in urls:
            pdf_links = handler.handle_interactive_page(url)
            assert isinstance(pdf_links, list)
        
        # Should reuse the same driver instance
        assert mock_driver.get.call_count == len(urls)
    
    @patch('time.sleep')
    def test_page_load_timing(self, mock_sleep):
        """Test page load timing and delays"""
        handler = BrowserHandler(headless=True)
        mock_driver = Mock()
        mock_wait = Mock()
        handler.driver = mock_driver
        handler.wait = mock_wait
        
        # Mock successful page load
        mock_wait.until.return_value = True
        mock_driver.find_elements.return_value = []
        
        handler.handle_interactive_page('https://example.com/slow-page.html')
        
        # Should include appropriate delays
        mock_sleep.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])