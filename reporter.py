"""
Progress Reporting and Statistics Module

This module handles real-time progress reporting, statistics tracking,
and generation of comprehensive crawling reports.
"""

import time
import json
import csv
import os
from collections import defaultdict
from typing import Dict, Any, Optional
from datetime import datetime
from tqdm import tqdm

from models import CrawlResults, DepartmentResults, DryRunReport


class ProgressReporter:
    """Handles progress tracking and report generation"""
    
    def __init__(self):
        self.stats: Dict[str, Any] = defaultdict(int)
        self.start_time = time.time()
        self.department_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.current_progress_bars: Dict[str, tqdm] = {}
        
    def update_progress(self, department: str, action: str, details: str = ""):
        """Update and display real-time progress"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Update department statistics
        self.department_stats[department][f"{action}_count"] += 1
        
        # Display real-time update
        status_msg = f"[{timestamp}] {department}: {action}"
        if details:
            status_msg += f" - {details}"
        
        print(status_msg)
        
        # Update global statistics
        self.stats[f"total_{action}"] += 1
        
    def track_discovery(self, department: str, urls_found: int, pdfs_found: int):
        """Track URL discovery statistics"""
        self.department_stats[department]["urls_crawled"] += urls_found
        self.department_stats[department]["pdfs_found"] += pdfs_found
        
        # Update global stats
        self.stats["total_urls_crawled"] += urls_found
        self.stats["total_pdfs_found"] += pdfs_found
        
        self.update_progress(department, "discovery", 
                           f"Found {pdfs_found} PDFs from {urls_found} URLs")
        
    def track_download(self, department: str, success: bool, file_size: int = 0):
        """Track download statistics"""
        if success:
            self.department_stats[department]["pdfs_downloaded"] += 1
            self.department_stats[department]["total_size"] += file_size
            self.stats["total_pdfs_downloaded"] += 1
            self.stats["total_size"] += file_size
            
            size_mb = file_size / (1024 * 1024) if file_size > 0 else 0
            self.update_progress(department, "download_success", 
                               f"Downloaded PDF ({size_mb:.2f} MB)")
        else:
            self.department_stats[department]["pdfs_failed"] += 1
            self.stats["total_pdfs_failed"] += 1
            self.update_progress(department, "download_failed", "PDF download failed")
            
    def track_skip(self, department: str, reason: str = "already exists"):
        """Track skipped downloads"""
        self.department_stats[department]["pdfs_skipped"] += 1
        self.stats["total_pdfs_skipped"] += 1
        self.update_progress(department, "download_skipped", reason)
        
    def create_progress_bar(self, department: str, total: int, description: str) -> tqdm:
        """Create a progress bar for downloads"""
        progress_bar = tqdm(
            total=total,
            desc=f"{department}: {description}",
            unit="files",
            unit_scale=True,
            leave=True
        )
        self.current_progress_bars[department] = progress_bar
        return progress_bar
        
    def update_progress_bar(self, department: str, increment: int = 1):
        """Update progress bar for a department"""
        if department in self.current_progress_bars:
            self.current_progress_bars[department].update(increment)
            
    def close_progress_bar(self, department: str):
        """Close progress bar for a department"""
        if department in self.current_progress_bars:
            self.current_progress_bars[department].close()
            del self.current_progress_bars[department]
            
    def generate_report(self, results: CrawlResults) -> str:
        """Generate comprehensive final report"""
        total_duration = time.time() - self.start_time
        
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("HK PDF CRAWLER - FINAL REPORT")
        report_lines.append("=" * 60)
        report_lines.append(f"Crawl completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Total duration: {total_duration / 60:.2f} minutes")
        report_lines.append("")
        
        # Overall statistics
        report_lines.append("OVERALL STATISTICS")
        report_lines.append("-" * 30)
        report_lines.append(f"Total PDFs found: {results.total_pdfs_found}")
        report_lines.append(f"Total PDFs downloaded: {results.total_pdfs_downloaded}")
        report_lines.append(f"Total PDFs failed: {self.stats.get('total_pdfs_failed', 0)}")
        report_lines.append(f"Total PDFs skipped: {self.stats.get('total_pdfs_skipped', 0)}")
        report_lines.append(f"Success rate: {results.success_rate:.1f}%")
        
        total_size_mb = self.stats.get('total_size', 0) / (1024 * 1024)
        report_lines.append(f"Total size downloaded: {total_size_mb:.2f} MB")
        report_lines.append("")
        
        # Department breakdown
        report_lines.append("DEPARTMENT BREAKDOWN")
        report_lines.append("-" * 30)
        
        for dept_result in results.departments:
            report_lines.append(f"\n{dept_result.department}:")
            report_lines.append(f"  URLs crawled: {dept_result.urls_crawled}")
            report_lines.append(f"  PDFs found: {dept_result.pdfs_found}")
            report_lines.append(f"  PDFs downloaded: {dept_result.pdfs_downloaded}")
            report_lines.append(f"  PDFs failed: {dept_result.pdfs_failed}")
            report_lines.append(f"  PDFs skipped: {dept_result.pdfs_skipped}")
            
            dept_size_mb = dept_result.total_size / (1024 * 1024)
            report_lines.append(f"  Total size: {dept_size_mb:.2f} MB")
            report_lines.append(f"  Duration: {dept_result.duration / 60:.2f} minutes")
            
            if dept_result.pdfs_found > 0:
                dept_success_rate = (dept_result.pdfs_downloaded / dept_result.pdfs_found) * 100
                report_lines.append(f"  Success rate: {dept_success_rate:.1f}%")
            
            if dept_result.errors:
                report_lines.append(f"  Errors encountered: {len(dept_result.errors)}")
                for error in dept_result.errors[:3]:  # Show first 3 errors
                    report_lines.append(f"    - {error}")
                if len(dept_result.errors) > 3:
                    report_lines.append(f"    ... and {len(dept_result.errors) - 3} more")
        
        report_lines.append("")
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
        
    def save_report(self, results: CrawlResults, format: str = "json"):
        """Save report to file in JSON or CSV format"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format.lower() == "json":
            filename = f"crawl_report_{timestamp}.json"
            self._save_json_report(results, filename)
        elif format.lower() == "csv":
            filename = f"crawl_report_{timestamp}.csv"
            self._save_csv_report(results, filename)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'json' or 'csv'")
            
        print(f"Report saved to: {filename}")
        
    def _save_json_report(self, results: CrawlResults, filename: str):
        """Save report as JSON file"""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_duration": time.time() - self.start_time,
            "overall_stats": {
                "total_pdfs_found": results.total_pdfs_found,
                "total_pdfs_downloaded": results.total_pdfs_downloaded,
                "total_pdfs_failed": self.stats.get('total_pdfs_failed', 0),
                "total_pdfs_skipped": self.stats.get('total_pdfs_skipped', 0),
                "success_rate": results.success_rate,
                "total_size_bytes": self.stats.get('total_size', 0)
            },
            "departments": []
        }
        
        for dept_result in results.departments:
            dept_data = {
                "name": dept_result.department,
                "urls_crawled": dept_result.urls_crawled,
                "pdfs_found": dept_result.pdfs_found,
                "pdfs_downloaded": dept_result.pdfs_downloaded,
                "pdfs_failed": dept_result.pdfs_failed,
                "pdfs_skipped": dept_result.pdfs_skipped,
                "total_size_bytes": dept_result.total_size,
                "duration_seconds": dept_result.duration,
                "errors": dept_result.errors
            }
            report_data["departments"].append(dept_data)
            
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
            
    def _save_csv_report(self, results: CrawlResults, filename: str):
        """Save report as CSV file"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'Department', 'URLs_Crawled', 'PDFs_Found', 'PDFs_Downloaded',
                'PDFs_Failed', 'PDFs_Skipped', 'Total_Size_MB', 'Duration_Minutes',
                'Success_Rate_%', 'Error_Count'
            ])
            
            # Write department data
            for dept_result in results.departments:
                success_rate = 0
                if dept_result.pdfs_found > 0:
                    success_rate = (dept_result.pdfs_downloaded / dept_result.pdfs_found) * 100
                    
                writer.writerow([
                    dept_result.department,
                    dept_result.urls_crawled,
                    dept_result.pdfs_found,
                    dept_result.pdfs_downloaded,
                    dept_result.pdfs_failed,
                    dept_result.pdfs_skipped,
                    round(dept_result.total_size / (1024 * 1024), 2),
                    round(dept_result.duration / 60, 2),
                    round(success_rate, 1),
                    len(dept_result.errors)
                ])
                
    def print_final_summary(self, results: CrawlResults):
        """Print final summary to console"""
        report = self.generate_report(results)
        print(report)
        
    def print_dry_run_report(self, report: DryRunReport):
        """Print dry-run analysis report"""
        print("\n" + "=" * 50)
        print("DRY-RUN ANALYSIS RESULTS")
        print("=" * 50)
        
        for analysis in report.department_analyses:
            print(f"\n{analysis.department}:")
            print(f"  Accessible URLs: {analysis.seed_urls_accessible}/{analysis.seed_urls_total}")
            print(f"  Estimated PDFs: {analysis.estimated_pdfs}")
            
            if analysis.requires_browser:
                print("  ⚠️  Requires browser automation")
            if analysis.rate_limit_detected:
                print("  ⚠️  Rate limiting detected")
                
            for issue in analysis.issues:
                print(f"  ❌ {issue}")
        
        print(f"\nTotal Estimated PDFs: {report.total_estimated_pdfs}")
        print(f"Estimated Duration: {report.estimated_duration/60:.1f} minutes")
        
        if report.issues_found:
            print("\nIssues Found:")
            for issue in report.issues_found:
                print(f"  ❌ {issue}")
        
        if report.recommendations:
            print("\nRecommendations:")
            for rec in report.recommendations:
                print(f"  💡 {rec}")
                
        print("=" * 50)