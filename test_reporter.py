#!/usr/bin/env python3
"""
Test script for ProgressReporter functionality

This script tests the progress reporting and statistics tracking features
with sample crawl data to verify all functionality works correctly.
"""

import time
import os
from reporter import ProgressReporter
from crawler import CrawlResults, DepartmentResults, DryRunReport, DepartmentAnalysis


def test_progress_reporting():
    """Test real-time progress reporting"""
    print("Testing Progress Reporting...")
    print("=" * 40)
    
    reporter = ProgressReporter()
    
    # Simulate crawling progress for multiple departments
    departments = ["Buildings Department", "Labour Department", "Fire Services Department"]
    
    for dept in departments:
        print(f"\nStarting crawl for {dept}...")
        
        # Simulate discovery phase
        reporter.track_discovery(dept, urls_found=25, pdfs_found=8)
        time.sleep(0.5)
        
        # Create progress bar for downloads
        progress_bar = reporter.create_progress_bar(dept, total=8, description="Downloading PDFs")
        
        # Simulate downloads
        for i in range(8):
            if i < 6:  # 6 successful downloads
                reporter.track_download(dept, success=True, file_size=1024*1024*2)  # 2MB files
                reporter.update_progress_bar(dept)
            elif i < 7:  # 1 failed download
                reporter.track_download(dept, success=False)
                reporter.update_progress_bar(dept)
            else:  # 1 skipped download
                reporter.track_skip(dept, "already exists")
                reporter.update_progress_bar(dept)
            
            time.sleep(0.3)
        
        reporter.close_progress_bar(dept)
    
    print("\n" + "=" * 40)
    print("Progress reporting test completed!")
    return reporter


def test_report_generation():
    """Test report generation and saving"""
    print("\nTesting Report Generation...")
    print("=" * 40)
    
    # Create sample crawl results
    dept_results = [
        DepartmentResults(
            department="Buildings Department",
            urls_crawled=25,
            pdfs_found=8,
            pdfs_downloaded=6,
            pdfs_failed=1,
            pdfs_skipped=1,
            total_size=12*1024*1024,  # 12MB
            duration=180.5,  # 3 minutes
            errors=["Failed to download: timeout error"]
        ),
        DepartmentResults(
            department="Labour Department", 
            urls_crawled=30,
            pdfs_found=12,
            pdfs_downloaded=10,
            pdfs_failed=1,
            pdfs_skipped=1,
            total_size=20*1024*1024,  # 20MB
            duration=240.0,  # 4 minutes
            errors=["Network error on PDF download"]
        ),
        DepartmentResults(
            department="Fire Services Department",
            urls_crawled=15,
            pdfs_found=5,
            pdfs_downloaded=5,
            pdfs_failed=0,
            pdfs_skipped=0,
            total_size=8*1024*1024,  # 8MB
            duration=120.0,  # 2 minutes
            errors=[]
        )
    ]
    
    crawl_results = CrawlResults(
        departments=dept_results,
        total_pdfs_found=25,
        total_pdfs_downloaded=21,
        total_duration=540.5,  # 9 minutes
        success_rate=84.0
    )
    
    reporter = ProgressReporter()
    
    # Test report generation
    print("Generating text report...")
    report_text = reporter.generate_report(crawl_results)
    print(report_text)
    
    # Test saving reports
    print("\nSaving reports...")
    try:
        reporter.save_report(crawl_results, format="json")
        reporter.save_report(crawl_results, format="csv")
        print("✅ Reports saved successfully!")
    except Exception as e:
        print(f"❌ Error saving reports: {e}")
    
    return reporter


def test_dry_run_reporting():
    """Test dry-run analysis reporting"""
    print("\nTesting Dry-Run Reporting...")
    print("=" * 40)
    
    # Create sample dry-run analysis
    analyses = [
        DepartmentAnalysis(
            department="Buildings Department",
            seed_urls_accessible=2,
            seed_urls_total=2,
            estimated_pdfs=15,
            requires_browser=True,
            rate_limit_detected=False,
            issues=[]
        ),
        DepartmentAnalysis(
            department="Labour Department",
            seed_urls_accessible=1,
            seed_urls_total=2,
            estimated_pdfs=8,
            requires_browser=False,
            rate_limit_detected=True,
            issues=["Cannot access https://example.com/blocked: 403 Forbidden"]
        )
    ]
    
    dry_run_report = DryRunReport(
        department_analyses=analyses,
        total_estimated_pdfs=23,
        estimated_duration=46.0,  # seconds
        issues_found=["Rate limiting detected on Labour Department"],
        recommendations=[
            "Enable browser automation for Buildings Department",
            "Use longer delays for Labour Department due to rate limiting"
        ]
    )
    
    reporter = ProgressReporter()
    reporter.print_dry_run_report(dry_run_report)
    
    return reporter


def test_statistics_tracking():
    """Test statistics tracking functionality"""
    print("\nTesting Statistics Tracking...")
    print("=" * 40)
    
    reporter = ProgressReporter()
    
    # Test various tracking methods
    reporter.track_discovery("Test Dept", urls_found=10, pdfs_found=3)
    reporter.track_download("Test Dept", success=True, file_size=1024*1024)
    reporter.track_download("Test Dept", success=False)
    reporter.track_skip("Test Dept", "file already exists")
    
    # Check statistics
    print("Department Statistics:")
    for dept, stats in reporter.department_stats.items():
        print(f"  {dept}: {dict(stats)}")
    
    print("Global Statistics:")
    print(f"  {dict(reporter.stats)}")
    
    return reporter


def main():
    """Run all tests"""
    print("HK PDF CRAWLER - REPORTER TESTING")
    print("=" * 50)
    
    try:
        # Test 1: Progress reporting
        test_progress_reporting()
        
        # Test 2: Report generation
        test_report_generation()
        
        # Test 3: Dry-run reporting  
        test_dry_run_reporting()
        
        # Test 4: Statistics tracking
        test_statistics_tracking()
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        
        # List generated files
        print("\nGenerated files:")
        for file in os.listdir('.'):
            if file.startswith('crawl_report_'):
                print(f"  - {file}")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()