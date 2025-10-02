#!/usr/bin/env python3
"""
HK Government PDF Crawler - Main Entry Point

This module provides the command-line interface and orchestrates the PDF crawling process
for Hong Kong government department websites. It supports two input methods:
1. YAML configuration files with detailed settings
2. Direct markdown files with department URLs

The crawler handles JavaScript-heavy sites, provides real-time progress tracking,
and supports both local and cloud storage options.

Usage Examples:
    python main.py --config config.yaml
    python main.py --input-urls hk-government-pdf-resources.md --dry-run
    python main.py --config config.yaml --departments buildings_department --log-level DEBUG

Author: HK PDF Crawler Team
Version: 1.0.0
"""

import argparse
import logging
import sys
from typing import List, Optional

from utils import setup_logging
from config import load_config, create_config_from_markdown
from crawler import PDFCrawler
from models import DryRunReport, CrawlResults

def print_dry_run_report(report: DryRunReport):
    """Print comprehensive dry-run analysis report to console"""
    print("\n" + "="*60)
    print("DRY-RUN ANALYSIS RESULTS")
    print("="*60)
    
    # Department-by-department analysis
    for analysis in report.department_analyses:
        print(f"\n📋 {analysis.department}:")
        print(f"   Accessible URLs: {analysis.seed_urls_accessible}/{analysis.seed_urls_total}")
        print(f"   Estimated PDFs: {analysis.estimated_pdfs}")
        
        # Status indicators
        if analysis.requires_browser:
            print(f"   ⚠️  Requires browser automation")
        if analysis.rate_limit_detected:
            print(f"   ⚠️  Rate limiting detected")
        
        # Issues
        if analysis.issues:
            print(f"   Issues found:")
            for issue in analysis.issues:
                print(f"     ❌ {issue}")
        else:
            print(f"   ✅ No issues detected")
    
    # Overall summary
    print(f"\n" + "="*60)
    print("OVERALL SUMMARY")
    print("="*60)
    print(f"Total Estimated PDFs: {report.total_estimated_pdfs}")
    print(f"Estimated Duration: {report.estimated_duration/60:.1f} minutes")
    
    # Issues summary
    if report.issues_found:
        print(f"\nIssues Found ({len(report.issues_found)}):")
        for issue in report.issues_found:
            print(f"  ❌ {issue}")
    else:
        print(f"\n✅ No major issues detected")
    
    # Recommendations
    if report.recommendations:
        print(f"\nRecommendations ({len(report.recommendations)}):")
        for rec in report.recommendations:
            print(f"  💡 {rec}")
    else:
        print(f"\n✅ No specific recommendations")
    
    print("\n" + "="*60)


def print_final_report(results: CrawlResults):
    """Print comprehensive final crawling report to console"""
    print("\n" + "="*60)
    print("CRAWLING RESULTS")
    print("="*60)
    
    # Department-by-department results
    for dept_result in results.departments:
        print(f"\n📁 {dept_result.department}:")
        print(f"   URLs Crawled: {dept_result.urls_crawled}")
        print(f"   PDFs Found: {dept_result.pdfs_found}")
        print(f"   PDFs Downloaded: {dept_result.pdfs_downloaded}")
        print(f"   PDFs Failed: {dept_result.pdfs_failed}")
        print(f"   PDFs Skipped: {dept_result.pdfs_skipped}")
        print(f"   Total Size: {dept_result.total_size/(1024*1024):.2f} MB")
        print(f"   Duration: {dept_result.duration/60:.2f} minutes")
        
        if dept_result.errors:
            print(f"   Errors ({len(dept_result.errors)}):")
            for error in dept_result.errors[:5]:  # Show first 5 errors
                print(f"     ❌ {error}")
            if len(dept_result.errors) > 5:
                print(f"     ... and {len(dept_result.errors) - 5} more errors")
    
    # Overall summary
    print(f"\n" + "="*60)
    print("OVERALL SUMMARY")
    print("="*60)
    print(f"Total PDFs Found: {results.total_pdfs_found}")
    print(f"Total PDFs Downloaded: {results.total_pdfs_downloaded}")
    print(f"Success Rate: {results.success_rate:.1f}%")
    print(f"Total Duration: {results.total_duration/60:.2f} minutes")
    print(f"Average Speed: {results.total_pdfs_downloaded/(results.total_duration/60):.1f} PDFs/minute")
    
    print("\n" + "="*60)


def main():
    """Main entry point with CLI interface exactly as shown in design"""
    parser = argparse.ArgumentParser(
        description='HK Government PDF Crawler - Systematically download PDFs from HK government websites',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --config config.yaml
  %(prog)s --input-urls hk-government-pdf-resources.md
  %(prog)s --config config.yaml --dry-run
  %(prog)s --input-urls hk-government-pdf-resources.md --departments buildings_department
        """
    )
    
    # Command-line arguments exactly as specified in design
    parser.add_argument('--config', 
                       help='Configuration file path (YAML)')
    parser.add_argument('--input-urls', 
                       help='Path to markdown file with URLs (alternative to config)')
    parser.add_argument('--dry-run', 
                       action='store_true', 
                       help='Analyze without downloading')
    parser.add_argument('--departments', 
                       nargs='+', 
                       help='Specific departments to crawl')
    parser.add_argument('--log-level', 
                       default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Set logging level (default: INFO)')
    parser.add_argument('--log-file', 
                       default='hk_pdf_crawler.log', 
                       help='Log file path (default: hk_pdf_crawler.log)')
    parser.add_argument('--force-update', 
                       action='store_true',
                       help='Force re-download of all files (ignore incremental updates)')
    parser.add_argument('--disable-advanced', 
                       action='store_true',
                       help='Disable advanced discovery features (sitemap, search, archives)')
    parser.add_argument('--test-advanced', 
                       action='store_true',
                       help='Run tests for advanced features')
    
    args = parser.parse_args()
    
    # Validate input arguments with user-friendly error messages
    if not args.config and not args.input_urls:
        print("❌ Error: Either --config or --input-urls must be provided")
        print("\nUse one of these options:")
        print("  --config config.yaml                    (Load from YAML configuration)")
        print("  --input-urls hk-government-pdf-resources.md  (Parse from markdown file)")
        parser.print_help()
        sys.exit(1)
    
    if args.config and args.input_urls:
        print("❌ Error: Cannot use both --config and --input-urls at the same time")
        print("Please choose one input method.")
        sys.exit(1)
    
    # Set up logging with comprehensive configuration
    try:
        setup_logging(log_level=args.log_level, log_file=args.log_file)
        logger = logging.getLogger('hk_pdf_crawler')
        logger.info("="*60)
        logger.info("HK PDF Crawler starting...")
        logger.info(f"Command line: {' '.join(sys.argv)}")
        logger.info("="*60)
    except Exception as e:
        print(f"❌ Failed to set up logging: {str(e)}")
        sys.exit(1)
    
    try:
        # Load configuration with proper error handling and user feedback
        config = None
        if args.input_urls:
            print(f"📄 Creating configuration from markdown file: {args.input_urls}")
            logger.info(f"Creating configuration from markdown file: {args.input_urls}")
            try:
                config = create_config_from_markdown(args.input_urls)
                print(f"✅ Successfully parsed {len(config.departments)} departments from markdown")
                logger.info(f"Successfully parsed {len(config.departments)} departments from markdown")
            except FileNotFoundError:
                print(f"❌ Markdown file not found: {args.input_urls}")
                print("Please check the file path and try again.")
                sys.exit(1)
            except ValueError as e:
                print(f"❌ Failed to parse markdown file: {str(e)}")
                print("Please check the markdown file format and try again.")
                sys.exit(1)
        else:
            print(f"⚙️  Loading configuration from: {args.config}")
            logger.info(f"Loading configuration from: {args.config}")
            try:
                config = load_config(args.config)
                print(f"✅ Successfully loaded configuration with {len(config.departments)} departments")
                logger.info(f"Successfully loaded configuration with {len(config.departments)} departments")
            except FileNotFoundError:
                print(f"❌ Configuration file not found: {args.config}")
                print("Please check the file path and try again.")
                sys.exit(1)
            except Exception as e:
                print(f"❌ Failed to load configuration: {str(e)}")
                print("Please check the configuration file format and try again.")
                sys.exit(1)
        
        # Filter departments if specified
        if args.departments:
            available_depts = list(config.departments.keys())
            invalid_depts = [d for d in args.departments if d not in available_depts]
            if invalid_depts:
                print(f"❌ Invalid departments specified: {', '.join(invalid_depts)}")
                print(f"Available departments: {', '.join(available_depts)}")
                sys.exit(1)
            print(f"🎯 Filtering to specific departments: {', '.join(args.departments)}")
            logger.info(f"Filtering to specific departments: {', '.join(args.departments)}")
        
        # Handle test mode
        if args.test_advanced:
            print("🧪 Running advanced features test suite...")
            logger.info("Running advanced features test suite...")
            
            # Import and run test suite
            try:
                from test_advanced_features import main as run_tests
                success = run_tests()
                if success:
                    print("✅ All advanced features tests passed")
                    logger.info("All advanced features tests passed")
                else:
                    print("❌ Some advanced features tests failed")
                    logger.warning("Some advanced features tests failed")
                    sys.exit(1)
            except ImportError as e:
                print(f"❌ Could not import test suite: {e}")
                sys.exit(1)
            return
        
        # Initialize crawler
        print("🚀 Initializing PDF crawler...")
        logger.info("Initializing PDF crawler...")
        crawler = PDFCrawler(config)
        
        # Configure advanced features
        if args.disable_advanced:
            print("⚠️  Advanced discovery features disabled")
            logger.info("Advanced discovery features disabled")
            crawler.use_comprehensive_discovery = False
        
        if args.force_update:
            print("🔄 Force update mode enabled - will re-download all files")
            logger.info("Force update mode enabled")
            crawler.use_incremental_updates = False
        
        # Run dry-run analysis or actual crawling
        if args.dry_run:
            print("🔍 Running dry-run analysis...")
            logger.info("Running dry-run analysis...")
            report = crawler.dry_run(args.departments)
            print_dry_run_report(report)
            logger.info("Dry-run analysis completed successfully")
            print("✅ Dry-run analysis completed")
        else:
            print("📥 Starting PDF crawling...")
            logger.info("Starting PDF crawling...")
            results = crawler.crawl(args.departments)
            print_final_report(results)
            logger.info("PDF crawling completed successfully")
            print("✅ PDF crawling completed")
    
    except KeyboardInterrupt:
        logger.info("Crawling interrupted by user (Ctrl+C)")
        print("\n⚠️  Crawling interrupted by user")
        print("Partial results may be available in the downloads directory.")
        sys.exit(1)
    except ImportError as e:
        logger.error(f"Missing dependency: {str(e)}")
        print(f"❌ Missing dependency: {str(e)}")
        print("Please install required dependencies with: pip install -r requirements.txt")
        sys.exit(1)
    except PermissionError as e:
        logger.error(f"Permission error: {str(e)}")
        print(f"❌ Permission error: {str(e)}")
        print("Please check file/directory permissions and try again.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
        print(f"\n❌ Critical error: {str(e)}")
        print(f"Check the log file ({args.log_file}) for detailed error information")
        print("If the problem persists, please report this issue.")
        sys.exit(1)

if __name__ == "__main__":
    main()