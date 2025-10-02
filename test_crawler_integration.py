#!/usr/bin/env python3
"""
Integration test for the PDFCrawler main orchestration class.

This test verifies that the crawler can successfully orchestrate all components
and perform end-to-end crawling with a single department.
"""

import logging
import tempfile
import os
from pathlib import Path

from config import CrawlConfig, DepartmentConfig, CrawlSettings, StorageConfig
from crawler import PDFCrawler
from utils import setup_logging


def test_crawler_integration():
    """Test end-to-end crawling with a single department"""
    
    # Set up logging for the test
    setup_logging("INFO")
    logger = logging.getLogger(__name__)
    
    logger.info("Starting PDFCrawler integration test")
    
    # Create temporary directory for downloads
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Using temporary directory: {temp_dir}")
        
        # Create test configuration with a single HK government department
        test_config = CrawlConfig(
            departments={
                'buildings_department_test': DepartmentConfig(
                    name="Buildings Department (Test)",
                    seed_urls=[
                        "https://www.bd.gov.hk/en/resources/codes-and-references/codes-and-design-manuals/index.html"
                    ],
                    max_depth=1,  # Limit depth for test
                    max_pages=5,  # Limit pages for test
                    time_limit=300  # 5 minutes max
                )
            },
            settings=CrawlSettings(
                delay_between_requests=2.0,  # Be respectful during test
                max_concurrent_downloads=2,  # Limit concurrency for test
                respect_robots_txt=True,
                user_agent="HK-PDF-Crawler-Test/1.0",
                enable_browser_automation=False,  # Disable for simple test
                request_timeout=30
            ),
            storage=StorageConfig(
                local_path=temp_dir,
                organize_by_department=True,
                s3_enabled=False  # Disable S3 for test
            )
        )
        
        # Initialize crawler
        logger.info("Initializing PDFCrawler")
        crawler = PDFCrawler(test_config)
        
        # Test dry-run first
        logger.info("Running dry-run analysis")
        try:
            dry_run_report = crawler.dry_run(['buildings_department_test'])
            
            logger.info("Dry-run completed successfully")
            logger.info(f"Estimated PDFs: {dry_run_report.total_estimated_pdfs}")
            logger.info(f"Estimated duration: {dry_run_report.estimated_duration/60:.1f} minutes")
            
            if dry_run_report.issues_found:
                logger.warning(f"Issues found: {dry_run_report.issues_found}")
            
            if dry_run_report.recommendations:
                logger.info(f"Recommendations: {dry_run_report.recommendations}")
                
        except Exception as e:
            logger.error(f"Dry-run failed: {e}")
            return False
        
        # Test actual crawling (limited scope)
        logger.info("Starting actual crawl test")
        try:
            results = crawler.crawl(['buildings_department_test'])
            
            logger.info("Crawl completed successfully")
            logger.info(f"Total PDFs found: {results.total_pdfs_found}")
            logger.info(f"Total PDFs downloaded: {results.total_pdfs_downloaded}")
            logger.info(f"Success rate: {results.success_rate:.1f}%")
            logger.info(f"Total duration: {results.total_duration/60:.2f} minutes")
            
            # Check if any files were downloaded
            download_dir = Path(temp_dir) / "buildings-department-test"
            if download_dir.exists():
                pdf_files = list(download_dir.glob("*.pdf"))
                logger.info(f"Downloaded {len(pdf_files)} PDF files to {download_dir}")
                
                # Log first few filenames as examples
                for i, pdf_file in enumerate(pdf_files[:3]):
                    logger.info(f"  Example file {i+1}: {pdf_file.name} ({pdf_file.stat().st_size} bytes)")
            else:
                logger.info("No files downloaded (this may be expected for a limited test)")
            
            # Print department-specific results
            for dept_result in results.departments:
                logger.info(f"Department: {dept_result.department}")
                logger.info(f"  URLs crawled: {dept_result.urls_crawled}")
                logger.info(f"  PDFs found: {dept_result.pdfs_found}")
                logger.info(f"  PDFs downloaded: {dept_result.pdfs_downloaded}")
                logger.info(f"  PDFs failed: {dept_result.pdfs_failed}")
                logger.info(f"  Total size: {dept_result.total_size/(1024*1024):.2f} MB")
                
                if dept_result.errors:
                    logger.warning(f"  Errors: {len(dept_result.errors)}")
                    for error in dept_result.errors[:3]:  # Show first 3 errors
                        logger.warning(f"    - {error}")
            
            logger.info("Integration test completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Crawl test failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False


def test_crawler_components():
    """Test that all crawler components can be initialized"""
    
    logger = logging.getLogger(__name__)
    logger.info("Testing crawler component initialization")
    
    try:
        # Create minimal config
        config = CrawlConfig(
            departments={
                'test_dept': DepartmentConfig(
                    name="Test Department",
                    seed_urls=["https://example.com"]
                )
            },
            settings=CrawlSettings(),
            storage=StorageConfig()
        )
        
        # Initialize crawler
        crawler = PDFCrawler(config)
        
        # Test that all components are properly initialized
        assert crawler.url_discovery is not None, "URLDiscovery not initialized"
        assert crawler.file_downloader is not None, "FileDownloader not initialized"
        assert crawler.progress_reporter is not None, "ProgressReporter not initialized"
        assert crawler.session is not None, "Session not initialized"
        
        logger.info("All crawler components initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Component initialization test failed: {e}")
        return False


if __name__ == "__main__":
    # Run the integration tests
    print("Running PDFCrawler Integration Tests")
    print("=" * 50)
    
    # Test 1: Component initialization
    print("\n1. Testing component initialization...")
    if test_crawler_components():
        print("✓ Component initialization test passed")
    else:
        print("✗ Component initialization test failed")
        exit(1)
    
    # Test 2: End-to-end integration (limited scope)
    print("\n2. Testing end-to-end crawling (limited scope)...")
    print("Note: This test will make actual HTTP requests to HK government websites")
    print("and may take a few minutes to complete.")
    
    if test_crawler_integration():
        print("✓ Integration test passed")
    else:
        print("✗ Integration test failed")
        exit(1)
    
    print("\n" + "=" * 50)
    print("All tests passed! PDFCrawler is working correctly.")