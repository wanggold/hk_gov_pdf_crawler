# Implementation Plan

- [x] 1. Set up basic project structure and dependencies
  - Create simple directory structure with 8 core Python files as per design
  - Set up requirements.txt with minimal essential dependencies (requests, beautifulsoup4, selenium, pyyaml, tqdm, boto3, lxml)
  - Create basic logging setup using Python's standard logging module
  - Initialize empty module files with basic docstrings
  - _Requirements: 1.1, 9.4_

- [x] 2. Create configuration system with dual input support
  - Implement dataclasses for CrawlConfig, DepartmentConfig, CrawlSettings, StorageConfig as shown in design
  - Create load_config() function to read YAML files with basic validation
  - Implement create_config_from_markdown() function to parse the provided hk-government-pdf-resources.md file
  - Add markdown parsing logic to extract department names and URLs from the structured format
  - Build sample config.yaml using the HK government URLs from the provided markdown file
  - Add error handling for missing or invalid configuration files
  - Test both YAML and markdown input methods
  - _Requirements: 9.1, 9.2, 9.4_

- [x] 3. Build URL discovery and PDF detection in discovery.py
  - Create URLDiscovery class with simple requests.Session for HTTP requests
  - Implement discover_urls() method for basic recursive URL crawling with depth limits
  - Add find_pdf_links() method using BeautifulSoup to extract PDF links from HTML
  - Create is_pdf_link() method with simple URL pattern matching (.pdf extension, link text analysis)
  - Add basic robots.txt checking with override capability for government sites
  - Implement visited URL set to prevent infinite loops
  - Test with sample HTML pages containing PDF links
  - _Requirements: 1.1, 1.8, 1.9, 2.1, 2.2, 2.3, 7.1, 12.5_

- [x] 4. Create file downloader with local and S3 storage
  - Implement FileDownloader class in downloader.py with streaming download capability
  - Add download_pdf() method with HEAD request validation for PDF content-type
  - Create save_locally() method with department-based directory organization
  - Implement upload_to_s3() method using boto3 with error handling and retries
  - Add file existence checking to skip already downloaded PDFs
  - Create meaningful filename generation from URLs and document titles
  - Test download functionality with sample PDF URLs
  - _Requirements: 1.6, 1.7, 1.11, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [x] 5. Implement browser automation for JavaScript sites
  - Create BrowserHandler class in browser.py using Selenium WebDriver
  - Add start_browser() method with headless Chrome configuration
  - Implement handle_interactive_page() method for button clicks and form submissions
  - Add simple JavaScript execution for revealing PDF download URLs
  - Create close_browser() method for proper resource cleanup
  - Add lazy browser initialization (only start when needed)
  - Test with JavaScript-heavy government websites
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 12.2_

- [x] 6. Build simple concurrent downloads with rate limiting
  - Create SimpleConcurrency class using ThreadPoolExecutor as shown in design
  - Implement download_pdfs_concurrently() method with configurable max_workers (default 5)
  - Add download_with_rate_limit() method using threading.Lock per domain
  - Create simple rate limiting with minimum 1-second delay between requests to same domain
  - Add basic retry logic with exponential backoff for failed downloads
  - Test concurrent downloads with multiple PDF URLs
  - _Requirements: 1.10, 8.5, 12.3, 13.1, 13.2_

- [x] 7. Create progress reporting and statistics tracking
  - Implement ProgressReporter class in reporter.py with simple console output
  - Add update_progress() method for real-time status updates during crawling
  - Create statistics tracking using defaultdict for URLs crawled, PDFs found, downloaded, failed, skipped
  - Implement generate_report() method to create final summary with success rates and file sizes
  - Add save_report() method to export statistics as JSON/CSV files
  - Use tqdm for progress bars during download operations
  - Test reporting with sample crawl data
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 11.1, 11.2, 11.3, 11.6_

- [x] 8. Build main crawler orchestration class
  - Create PDFCrawler class in crawler.py as the main coordinator
  - Implement crawl() method that orchestrates URL discovery, PDF detection, and downloading
  - Add crawl_department() method to process individual departments
  - Create simple error handling using the handle_error() function from design
  - Integrate all components (URLDiscovery, FileDownloader, BrowserHandler, ProgressReporter)
  - Add basic logging throughout the crawling process
  - Test end-to-end crawling with a single department
  - _Requirements: 1.1, 1.6, 1.7, 8.6, 11.4, 11.5, 13.1, 13.2, 13.3, 13.4_

- [x] 9. Implement dry-run analysis functionality
  - Add dry_run() method to PDFCrawler class using the design's simple analysis approach
  - Create analyze_department() method to check seed URL accessibility and estimate PDF counts
  - Implement print_dry_run_report() function for console output as shown in design
  - Add basic issue detection (JavaScript requirements, rate limiting, inaccessible URLs)
  - Generate simple recommendations based on analysis results
  - Create DryRunReport and DepartmentAnalysis dataclasses
  - Test dry-run mode with HK government department URLs
  - _Requirements: All requirements for validation and analysis_

- [x] 10. Create main CLI interface with dual input support
  - Implement main.py with argparse CLI interface exactly as shown in design
  - Add command-line arguments for --config, --input-urls, --dry-run, and --departments
  - Create main() function that handles both YAML config and markdown URL file inputs
  - Implement logic to choose between load_config() and create_config_from_markdown() based on arguments
  - Add print_final_report() and print_dry_run_report() functions for displaying results
  - Implement comprehensive error handling and user-friendly error messages
  - Add logging configuration with file and console output
  - Test complete CLI workflow with both input methods from command line
  - _Requirements: 8.6, 9.1, 9.2, 11.4, 11.5_

- [x] 11. Add essential advanced features
  - Implement basic user-agent rotation and session management
  - Add simple sitemap.xml parsing for comprehensive URL discovery
  - Create basic search form handling for keyword-based PDF discovery
  - Add incremental update capability by checking existing files before download
  - Implement simple archive and historical section exploration
  - Create basic retry logic with exponential backoff as shown in design
  - Test advanced features with real HK government websites
  - _Requirements: 7.2, 7.3, 7.4, 7.5, 12.1, 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.4, 15.5_

- [x] 12. Add basic testing and validation
  - Write simple unit tests for core functions (PDF detection, configuration loading, URL discovery)
  - Create integration test using responses library to mock HTTP requests as shown in design
  - Add basic end-to-end test with sample configuration and mock websites
  - Test error handling scenarios (network failures, invalid PDFs, missing files)
  - Validate browser automation with JavaScript-heavy test pages
  - Test S3 upload functionality with mock AWS services
  - _Requirements: All requirements for validation and reliability_

- [x] 13. Create documentation and final polish
  - Write clear README.md with installation instructions and usage examples for both input methods
  - Document CLI usage: `python main.py --config config.yaml` and `python main.py --input-urls hk-government-pdf-resources.md`
  - Create sample configuration files for different HK government departments
  - Add basic troubleshooting guide for common issues (network errors, browser setup, S3 configuration)
  - Create utils.py with common helper functions used across modules (URL parsing, file handling, etc.)
  - Add proper docstrings and comments throughout the codebase
  - Test complete workflow with actual HK government websites using both input methods
  - Validate that the script works correctly with the provided hk-government-pdf-resources.md file
  - _Requirements: User experience and maintainability_