"""
Main Crawling Logic Module

This module contains the main PDFCrawler class that orchestrates the entire crawling process,
coordinating URL discovery, PDF detection, and file downloading.
"""

from dataclasses import dataclass
from typing import List, Optional, Set
import requests
import time
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import CrawlConfig, DepartmentConfig
from discovery import URLDiscovery
from downloader import FileDownloader
from browser import BrowserHandler
from reporter import ProgressReporter
from utils import handle_error, retry_with_backoff
from models import (
    DownloadResult, DepartmentResults, CrawlResults, 
    DepartmentAnalysis, DryRunReport
)


class PDFCrawler:
    """Main PDF crawler class that orchestrates the crawling process"""
    
    def __init__(self, config: CrawlConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.settings.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        # Initialize components with advanced features
        self.url_discovery = URLDiscovery(self.session)
        self.file_downloader = FileDownloader(
            config.storage, 
            config.settings.max_concurrent_downloads
        )
        self.browser_handler = None  # Lazy initialization
        self.progress_reporter = ProgressReporter()
        
        # Initialize discovery cache for incremental updates
        from discovery_cache import DiscoveryCache
        self.discovery_cache = DiscoveryCache()
        
        # Advanced features flags
        self.use_comprehensive_discovery = True
        self.use_incremental_updates = True
        self.cache_max_age_hours = getattr(config.settings, 'cache_max_age_hours', 24)
        
        # State tracking
        self.visited_urls: Set[str] = set()
        self.found_pdfs: List[str] = []
        
        self.logger.info("PDFCrawler initialized successfully")
        
    def crawl(self, departments: Optional[List[str]] = None) -> CrawlResults:
        """
        Main crawling method that orchestrates URL discovery, PDF detection, and downloading
        
        Args:
            departments: Optional list of specific departments to crawl
            
        Returns:
            CrawlResults with comprehensive crawling statistics
        """
        start_time = time.time()
        self.logger.info("Starting PDF crawling process")
        
        # Determine which departments to crawl
        departments_to_crawl = self._get_departments_to_crawl(departments)
        
        if not departments_to_crawl:
            self.logger.warning("No departments to crawl")
            return CrawlResults(
                departments=[],
                total_pdfs_found=0,
                total_pdfs_downloaded=0,
                total_duration=0,
                success_rate=0
            )
        
        self.logger.info(f"Crawling {len(departments_to_crawl)} departments: {list(departments_to_crawl.keys())}")
        
        # Crawl departments in parallel
        department_results = []
        total_pdfs_found = 0
        total_pdfs_downloaded = 0
        
        # Use ThreadPoolExecutor for parallel department processing
        max_parallel_departments = min(3, len(departments_to_crawl))  # Max 3 departments in parallel
        
        with ThreadPoolExecutor(max_workers=max_parallel_departments, thread_name_prefix="dept-crawler") as executor:
            # Submit all department crawling tasks
            future_to_dept = {
                executor.submit(self._crawl_department_wrapper, dept_key, dept_config): (dept_key, dept_config)
                for dept_key, dept_config in departments_to_crawl.items()
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_dept):
                dept_key, dept_config = future_to_dept[future]
                try:
                    dept_result = future.result()
                    department_results.append(dept_result)
                    
                    total_pdfs_found += dept_result.pdfs_found
                    total_pdfs_downloaded += dept_result.pdfs_downloaded
                    
                    self.logger.info(f"Completed crawl for {dept_config.name}: "
                                   f"{dept_result.pdfs_downloaded}/{dept_result.pdfs_found} PDFs downloaded")
                    
                except Exception as e:
                    error_msg = f"Failed to crawl department {dept_config.name}: {str(e)}"
                    self.logger.error(error_msg)
                    
                    # Create error result for failed department
                    dept_result = DepartmentResults(
                        department=dept_config.name,
                        urls_crawled=0,
                        pdfs_found=0,
                        pdfs_downloaded=0,
                        pdfs_failed=0,
                        pdfs_skipped=0,
                        total_size=0,
                    duration=0,
                    errors=[error_msg]
                )
                department_results.append(dept_result)
        
        # Calculate overall statistics
        total_duration = time.time() - start_time
        success_rate = (total_pdfs_downloaded / total_pdfs_found * 100) if total_pdfs_found > 0 else 0
        
        results = CrawlResults(
            departments=department_results,
            total_pdfs_found=total_pdfs_found,
            total_pdfs_downloaded=total_pdfs_downloaded,
            total_duration=total_duration,
            success_rate=success_rate
        )
        
        self.logger.info(f"Crawling completed in {total_duration/60:.2f} minutes. "
                        f"Downloaded {total_pdfs_downloaded}/{total_pdfs_found} PDFs ({success_rate:.1f}% success rate)")
        
        # Clean up browser if used
        self._cleanup_browser()
        
        return results
    
    def _crawl_department_wrapper(self, dept_key: str, dept_config: DepartmentConfig) -> DepartmentResults:
        """
        Wrapper method for department crawling to be used with ThreadPoolExecutor
        """
        self.logger.info(f"Starting crawl for department: {dept_config.name}")
        return self.crawl_department(dept_config)
        
    def crawl_department(self, dept_config: DepartmentConfig) -> DepartmentResults:
        """
        Crawl a single department with comprehensive error handling
        
        Args:
            dept_config: Configuration for the department to crawl
            
        Returns:
            DepartmentResults with detailed statistics
        """
        start_time = time.time()
        errors = []
        urls_crawled = 0
        all_pdf_urls = []
        
        self.logger.info(f"Starting department crawl: {dept_config.name}")
        self.progress_reporter.update_progress(dept_config.name, "started", "Beginning URL discovery")
        
        try:
            # Reset URL discovery state for this department
            self.url_discovery.reset_visited_urls()
            
            # Process each seed URL with advanced discovery
            for seed_url in dept_config.seed_urls:
                try:
                    self.logger.info(f"Processing seed URL: {seed_url}")
                    
                    # Check if we should skip this URL based on cache
                    if self.discovery_cache.should_skip_page(seed_url, self.cache_max_age_hours):
                        self.logger.info(f"⏭️  Skipping recently crawled URL: {seed_url}")
                        continue
                    
                    # Use comprehensive discovery if enabled
                    if self.use_comprehensive_discovery:
                        discovered_urls = self.url_discovery.discover_comprehensive_urls(
                            seed_url, dept_config.max_depth
                        )
                        
                        # Also try search-based discovery
                        search_pdf_urls = self.url_discovery.search_for_pdfs(seed_url)
                        all_pdf_urls.extend(search_pdf_urls)
                        
                    else:
                        # Standard discovery
                        discovered_urls = self.url_discovery.discover_urls(seed_url, dept_config.max_depth)
                    
                    urls_crawled += len(discovered_urls)
                    self.logger.info(f"Discovered {len(discovered_urls)} URLs from {seed_url}")
                    
                    # Find PDF links on each discovered URL with cache optimization
                    page_pdf_count = 0
                    for url in discovered_urls[:dept_config.max_pages]:  # Respect page limit
                        try:
                            # Skip recently crawled pages
                            if self.discovery_cache.should_skip_page(url, self.cache_max_age_hours):
                                continue
                            
                            pdf_links = self.url_discovery.find_pdf_links(url)
                            all_pdf_urls.extend(pdf_links)
                            page_pdf_count += len(pdf_links)
                            
                            # Cache the page crawl
                            self.discovery_cache.cache_page_crawl(url, len(pdf_links))
                            
                            # If no PDFs found and browser automation is enabled, try browser
                            if not pdf_links and self.config.settings.enable_browser_automation:
                                browser_pdf_links = self._try_browser_automation(url)
                                all_pdf_urls.extend(browser_pdf_links)
                            
                            # Add delay between requests
                            time.sleep(self.config.settings.delay_between_requests)
                            
                        except Exception as e:
                            error_msg = f"Error processing URL {url}: {str(e)}"
                            if handle_error(e, "URL processing", url):
                                self.logger.warning(f"Retrying URL processing: {url}")
                                # Simple retry logic with exponential backoff
                                try:
                                    time.sleep(2)
                                    pdf_links = self.url_discovery.find_pdf_links(url)
                                    all_pdf_urls.extend(pdf_links)
                                except Exception as retry_e:
                                    errors.append(f"Failed to process {url} after retry: {str(retry_e)}")
                            else:
                                errors.append(error_msg)
                            continue
                            
                except Exception as e:
                    error_msg = f"Error processing seed URL {seed_url}: {str(e)}"
                    if handle_error(e, "Seed URL processing", seed_url):
                        errors.append(f"Retryable error for {seed_url}: {str(e)}")
                    else:
                        errors.append(error_msg)
                    continue
            
            # Remove duplicate PDF URLs
            unique_pdf_urls = list(set(all_pdf_urls))
            
            # Filter to only new PDFs for incremental updates BEFORE caching
            if unique_pdf_urls:
                if self.use_incremental_updates:
                    new_pdf_urls = self.discovery_cache.get_new_pdfs_only(unique_pdf_urls)
                    skipped_count = len(unique_pdf_urls) - len(new_pdf_urls)
                    
                    if skipped_count > 0:
                        self.logger.info(f"⏭️  Skipped {skipped_count} previously discovered PDFs")
                    
                    validated_pdf_urls = new_pdf_urls
                else:
                    validated_pdf_urls = unique_pdf_urls
                
                # Cache discovered PDFs AFTER filtering
                self.discovery_cache.cache_discovered_pdfs(validated_pdf_urls, dept_config.name)
            else:
                validated_pdf_urls = []
            
            # Validate PDF URLs to get accurate count (only for new PDFs)
            if validated_pdf_urls:
                self.logger.info(f"Validating {len(validated_pdf_urls)} new PDF URLs for {dept_config.name}...")
                final_pdf_urls = []
                
                for url in validated_pdf_urls:
                    if self.file_downloader._validate_pdf_url(url):
                        final_pdf_urls.append(url)
                
                validated_pdf_urls = final_pdf_urls
            
            pdfs_found = len(validated_pdf_urls)
            
            self.logger.info(f"Found {pdfs_found} new valid PDF URLs for {dept_config.name}")
            
            # Output discovered PDF URLs for user review
            if validated_pdf_urls:
                self.logger.info(f"📋 New PDF URLs discovered for {dept_config.name}:")
                for i, url in enumerate(validated_pdf_urls[:10], 1):  # Show first 10
                    self.logger.info(f"  {i:2d}. {url}")
                if len(validated_pdf_urls) > 10:
                    self.logger.info(f"  ... and {len(validated_pdf_urls) - 10} more new PDFs")
                self.logger.info(f"📊 Total: {len(validated_pdf_urls)} new PDFs ready for download")
            
            self.progress_reporter.track_discovery(dept_config.name, urls_crawled, pdfs_found)
            
            # Download PDFs if any were found
            download_results = []
            if validated_pdf_urls:
                self.logger.info(f"Starting download of {pdfs_found} PDFs for {dept_config.name}")
                
                # Create progress bar for downloads
                progress_bar = self.progress_reporter.create_progress_bar(
                    dept_config.name, pdfs_found, "Downloading PDFs"
                )
                
                try:
                    # Use incremental downloads if enabled
                    if self.use_incremental_updates:
                        download_results = []
                        for pdf_url in validated_pdf_urls:
                            result = self.file_downloader.download_pdf_incremental(
                                pdf_url, dept_config.name
                            )
                            download_results.append(result)
                            self.progress_reporter.update_progress_bar(dept_config.name)
                    else:
                        download_results = self.file_downloader.download_pdfs_batch(
                            validated_pdf_urls, dept_config.name
                        )
                    
                    # Update progress bar as downloads complete
                    for result in download_results:
                        self.progress_reporter.update_progress_bar(dept_config.name)
                        
                        if result.success:
                            self.progress_reporter.track_download(dept_config.name, True, result.file_size)
                        else:
                            self.progress_reporter.track_download(dept_config.name, False)
                            if result.error:
                                errors.append(f"Download failed for {result.url}: {result.error}")
                                
                finally:
                    self.progress_reporter.close_progress_bar(dept_config.name)
            
            # Calculate statistics
            pdfs_downloaded = sum(1 for r in download_results if r.success)
            pdfs_failed = sum(1 for r in download_results if not r.success)
            pdfs_skipped = 0  # TODO: Implement skip tracking for existing files
            total_size = sum(r.file_size for r in download_results if r.success)
            duration = time.time() - start_time
            
            # Generate detailed reports for this department
            self._generate_department_reports(dept_config.name, download_results)
            
            result = DepartmentResults(
                department=dept_config.name,
                urls_crawled=urls_crawled,
                pdfs_found=pdfs_found,
                pdfs_downloaded=pdfs_downloaded,
                pdfs_failed=pdfs_failed,
                pdfs_skipped=pdfs_skipped,
                total_size=total_size,
                duration=duration,
                errors=errors
            )
            
            self.logger.info(f"Department crawl completed for {dept_config.name}: "
                           f"{pdfs_downloaded} downloaded, {pdfs_failed} failed, "
                           f"{total_size/(1024*1024):.2f} MB in {duration/60:.2f} minutes")
            
            return result
            
        except Exception as e:
            error_msg = f"Critical error crawling department {dept_config.name}: {str(e)}"
            self.logger.error(error_msg)
            errors.append(error_msg)
            
            return DepartmentResults(
                department=dept_config.name,
                urls_crawled=urls_crawled,
                pdfs_found=len(all_pdf_urls),
                pdfs_downloaded=0,
                pdfs_failed=0,
                pdfs_skipped=0,
                total_size=0,
                duration=time.time() - start_time,
                errors=errors
            )
        
    def dry_run(self, departments: Optional[List[str]] = None) -> DryRunReport:
        """
        Analyze departments without downloading to estimate scope and identify issues
        
        Args:
            departments: Optional list of specific departments to analyze
            
        Returns:
            DryRunReport with analysis results and recommendations
        """
        self.logger.info("Starting dry-run analysis")
        
        departments_to_analyze = self._get_departments_to_crawl(departments)
        analyses = []
        
        for dept_key, dept_config in departments_to_analyze.items():
            self.logger.info(f"Analyzing department: {dept_config.name}")
            analysis = self._analyze_department(dept_config)
            analyses.append(analysis)
        
        # Generate overall report
        total_estimated_pdfs = sum(a.estimated_pdfs for a in analyses)
        estimated_duration = total_estimated_pdfs * 2.0  # Estimate 2 seconds per PDF
        
        issues_found = []
        recommendations = []
        
        # Collect issues and generate recommendations
        for analysis in analyses:
            issues_found.extend(analysis.issues)
            
            if analysis.requires_browser:
                recommendations.append(f"Enable browser automation for {analysis.department}")
            
            if analysis.rate_limit_detected:
                recommendations.append(f"Increase delays for {analysis.department} to avoid rate limiting")
            
            if analysis.seed_urls_accessible < analysis.seed_urls_total:
                recommendations.append(f"Check inaccessible URLs for {analysis.department}")
        
        # Add general recommendations
        if total_estimated_pdfs > 1000:
            recommendations.append("Consider running crawl in smaller batches due to large number of PDFs")
        
        if estimated_duration > 3600:  # More than 1 hour
            recommendations.append("Estimated crawl time is over 1 hour - consider parallel processing")
        
        report = DryRunReport(
            department_analyses=analyses,
            total_estimated_pdfs=total_estimated_pdfs,
            estimated_duration=estimated_duration,
            issues_found=list(set(issues_found)),  # Remove duplicates
            recommendations=list(set(recommendations))  # Remove duplicates
        )
        
        self.logger.info(f"Dry-run analysis completed. Estimated {total_estimated_pdfs} PDFs, "
                        f"{estimated_duration/60:.1f} minutes duration")
        
        return report
    
    def _generate_department_reports(self, department_name: str, download_results: List) -> None:
        """
        Generate detailed success and failure reports for a department
        
        Args:
            department_name: Name of the department
            download_results: List of DownloadResult objects
        """
        from datetime import datetime
        
        # Create safe filename from department name
        safe_name = department_name.lower().replace(' ', '_').replace('(', '').replace(')', '')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Separate successful and failed downloads
        successful = [r for r in download_results if r.success]
        failed = [r for r in download_results if not r.success]
        
        # Generate success report
        if successful:
            success_file = f"{safe_name}_successful_downloads_{timestamp}.txt"
            with open(success_file, 'w', encoding='utf-8') as f:
                f.write(f"SUCCESSFUL DOWNLOADS - {department_name}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total: {len(successful)} PDFs\n")
                f.write("=" * 80 + "\n\n")
                
                for i, result in enumerate(successful, 1):
                    size_mb = result.file_size / (1024 * 1024) if result.file_size else 0
                    f.write(f"{i:3d}. {result.url}\n")
                    f.write(f"     File: {result.file_path}\n")
                    f.write(f"     Size: {size_mb:.2f} MB\n\n")
            
            self.logger.info(f"📄 Success report saved: {success_file}")
        
        # Generate failure report
        if failed:
            failure_file = f"{safe_name}_failed_downloads_{timestamp}.txt"
            with open(failure_file, 'w', encoding='utf-8') as f:
                f.write(f"FAILED DOWNLOADS - {department_name}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total: {len(failed)} URLs\n")
                f.write("=" * 80 + "\n\n")
                
                for i, result in enumerate(failed, 1):
                    f.write(f"{i:3d}. {result.url}\n")
                    f.write(f"     Reason: {result.error or 'Unknown error'}\n\n")
            
            self.logger.info(f"❌ Failure report saved: {failure_file}")
        
        # Print summary to console
        print(f"\n📊 {department_name} Reports Generated:")
        if successful:
            print(f"  ✅ Successful: {len(successful)} PDFs → {success_file}")
        if failed:
            print(f"  ❌ Failed: {len(failed)} URLs → {failure_file}")
    
    def _get_departments_to_crawl(self, departments: Optional[List[str]]) -> dict:
        """Get dictionary of departments to crawl based on input filter"""
        if departments:
            # Filter to specific departments
            return {
                dept_key: dept_config 
                for dept_key, dept_config in self.config.departments.items()
                if dept_key in departments or dept_config.name in departments
            }
        else:
            # Return all departments
            return self.config.departments
    
    def _analyze_department(self, dept_config: DepartmentConfig) -> DepartmentAnalysis:
        """Analyze a single department for dry-run report"""
        accessible_urls = 0
        estimated_pdfs = 0
        requires_browser = False
        rate_limit_detected = False
        issues = []
        
        for seed_url in dept_config.seed_urls:
            try:
                self.logger.debug(f"Testing accessibility of {seed_url}")
                response = self.session.get(seed_url, timeout=10)
                
                if response.status_code == 200:
                    accessible_urls += 1
                    
                    # Quick PDF count estimation
                    pdf_links = self.url_discovery.find_pdf_links(seed_url)
                    estimated_pdfs += len(pdf_links)
                    
                    # Check if JavaScript is heavily used (simple heuristic)
                    content_lower = response.text.lower()
                    js_indicators = ['<script', 'javascript:', 'onclick=', 'onload=']
                    js_count = sum(content_lower.count(indicator) for indicator in js_indicators)
                    
                    if js_count > 10 and len(pdf_links) == 0:
                        requires_browser = True
                        
                elif response.status_code == 429:
                    rate_limit_detected = True
                    issues.append(f"Rate limiting detected on {seed_url}")
                    
                else:
                    issues.append(f"HTTP {response.status_code} error for {seed_url}")
                    
            except requests.exceptions.Timeout:
                issues.append(f"Timeout accessing {seed_url}")
            except requests.exceptions.ConnectionError:
                issues.append(f"Connection error for {seed_url}")
            except Exception as e:
                issues.append(f"Error accessing {seed_url}: {str(e)}")
        
        return DepartmentAnalysis(
            department=dept_config.name,
            seed_urls_accessible=accessible_urls,
            seed_urls_total=len(dept_config.seed_urls),
            estimated_pdfs=estimated_pdfs,
            requires_browser=requires_browser,
            rate_limit_detected=rate_limit_detected,
            issues=issues
        )
    
    def _try_browser_automation(self, url: str) -> List[str]:
        """Try browser automation to find PDFs on JavaScript-heavy pages"""
        try:
            if not self.browser_handler:
                self.browser_handler = BrowserHandler(headless=True)
            
            self.logger.debug(f"Trying browser automation for {url}")
            pdf_links = self.browser_handler.handle_interactive_page(url)
            
            if pdf_links:
                self.logger.info(f"Browser automation found {len(pdf_links)} PDF links on {url}")
            
            return pdf_links
            
        except Exception as e:
            self.logger.warning(f"Browser automation failed for {url}: {str(e)}")
            return []
    
    def _cleanup_browser(self):
        """Clean up browser resources"""
        if self.browser_handler:
            try:
                self.browser_handler.close_browser()
                self.logger.info("Browser resources cleaned up")
            except Exception as e:
                self.logger.warning(f"Error cleaning up browser: {str(e)}")
            finally:
                self.browser_handler = None