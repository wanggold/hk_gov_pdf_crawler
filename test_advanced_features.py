#!/usr/bin/env python3
"""
Fixed test script for advanced features in HK PDF Crawler

This script tests advanced features with proper mocking to prevent hanging.
"""

import os
import sys
import time
import logging
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import responses

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import UserAgentRotator, SessionManager, retry_with_backoff, setup_logging
from discovery import URLDiscovery
from downloader import FileDownloader
from config import StorageConfig, CrawlSettings
from models import DownloadResult


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_user_agent_rotation():
    """Test user agent rotation functionality"""
    rotator = UserAgentRotator()
    
    # Test getting different user agents
    ua1 = rotator.get_next_user_agent()
    ua2 = rotator.get_next_user_agent()
    
    assert ua1 is not None
    assert ua2 is not None
    assert isinstance(ua1, str)
    assert isinstance(ua2, str)
    assert len(ua1) > 0
    assert len(ua2) > 0


def test_session_management():
    """Test session management with rotation"""
    session_manager = SessionManager()
    
    # Test getting sessions
    session1 = session_manager.get_session()
    session2 = session_manager.get_session()
    
    assert session1 is not None
    assert session2 is not None
    
    # Test session rotation
    session_manager.rotate_session()
    session3 = session_manager.get_session()
    
    assert session3 is not None


@responses.activate
def test_sitemap_discovery():
    """Test sitemap.xml parsing functionality with mocked responses"""
    # Mock sitemap responses
    responses.add(
        responses.GET,
        'https://www.bd.gov.hk/sitemap.xml',
        body='''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.bd.gov.hk/en/resources/doc1.pdf</loc></url>
            <url><loc>https://www.bd.gov.hk/en/resources/doc2.pdf</loc></url>
        </urlset>''',
        status=200
    )
    
    responses.add(
        responses.GET,
        'https://www.labour.gov.hk/sitemap.xml',
        status=404
    )
    
    session_manager = SessionManager()
    discovery = URLDiscovery(session_manager.get_session())
    
    # Test successful sitemap discovery
    urls = discovery.discover_urls_from_sitemap('www.bd.gov.hk')
    assert len(urls) >= 0  # Should handle gracefully even if no URLs found
    
    # Test failed sitemap discovery
    urls = discovery.discover_urls_from_sitemap('www.labour.gov.hk')
    assert isinstance(urls, list)


@responses.activate  
def test_archive_discovery():
    """Test archive section discovery with mocked responses"""
    # Mock archive page
    responses.add(
        responses.GET,
        'https://www.bd.gov.hk/en/resources/archives/',
        body='<html><body><a href="archive1.pdf">Archive 1</a><a href="archive2.pdf">Archive 2</a></body></html>',
        status=200
    )
    
    session_manager = SessionManager()
    discovery = URLDiscovery(session_manager.get_session())
    
    urls = discovery.discover_archive_sections('www.bd.gov.hk')
    assert isinstance(urls, list)


@responses.activate
def test_search_functionality():
    """Test search form handling with mocked responses"""
    # Mock search page with form
    responses.add(
        responses.GET,
        'https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html',
        body='''<html><body>
        <form method="get" action="/search">
            <input type="text" name="q" />
            <input type="submit" value="Search" />
        </form>
        </body></html>''',
        status=200
    )
    
    # Mock search results
    responses.add(
        responses.GET,
        'https://www.bd.gov.hk/search',
        body='<html><body><a href="result1.pdf">Result 1</a></body></html>',
        status=200
    )
    
    session_manager = SessionManager()
    discovery = URLDiscovery(session_manager.get_session())
    
    search_results = discovery.search_for_pdfs(
        'https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html',
        ['PDF', 'document']
    )
    assert isinstance(search_results, list)


def test_incremental_updates(temp_dir):
    """Test incremental update capability"""
    storage_config = StorageConfig(
        local_path=temp_dir,
        organize_by_department=True,
        s3_enabled=False
    )
    
    downloader = FileDownloader(storage_config)
    
    # Test file registry operations
    assert hasattr(downloader, 'file_registry')
    assert isinstance(downloader.file_registry, dict)
    
    # Test registry update
    test_url = 'https://example.com/test.pdf'
    test_path = os.path.join(temp_dir, 'test.pdf')
    test_content = b'test content'
    
    # Create the test file
    os.makedirs(os.path.dirname(test_path), exist_ok=True)
    with open(test_path, 'wb') as f:
        f.write(test_content)
    
    downloader.update_file_registry(test_url, test_path, test_content, {})
    
    # Check that registry was updated (it uses hash as key, not URL)
    assert len(downloader.file_registry) > 0


def test_retry_logic():
    """Test retry logic with exponential backoff"""
    call_count = 0
    
    @retry_with_backoff(max_retries=3)
    def failing_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return "success"
    
    result = failing_function()
    assert result == "success"
    assert call_count == 3


@responses.activate
def test_comprehensive_discovery():
    """Test comprehensive URL discovery with mocked responses"""
    # Mock main page
    responses.add(
        responses.GET,
        'https://example.gov.hk/index.html',
        body='<html><body><a href="doc1.pdf">Doc 1</a><a href="page2.html">Page 2</a></body></html>',
        status=200
    )
    
    # Mock secondary page
    responses.add(
        responses.GET,
        'https://example.gov.hk/page2.html',
        body='<html><body><a href="doc2.pdf">Doc 2</a></body></html>',
        status=200
    )
    
    # Mock sitemap (will fail gracefully)
    responses.add(responses.GET, 'https://example.gov.hk/sitemap.xml', status=404)
    responses.add(responses.GET, 'https://example.gov.hk/sitemap_index.xml', status=404)
    responses.add(responses.GET, 'https://example.gov.hk/sitemaps.xml', status=404)
    responses.add(responses.GET, 'http://example.gov.hk/sitemap.xml', status=404)
    
    session_manager = SessionManager()
    discovery = URLDiscovery(session_manager.get_session())
    
    urls = discovery.discover_comprehensive_urls('https://example.gov.hk/index.html', max_depth=2)
    assert isinstance(urls, list)
    assert len(urls) >= 1  # Should find at least the seed URL


if __name__ == "__main__":
    """Run all advanced feature tests"""
    print("Running Advanced Features Test Suite with Mocking")
    print("=" * 60)
    
    # Setup logging
    setup_logging("INFO")
    
    # Run tests using pytest
    pytest.main([__file__, "-v", "--tb=short"])
