"""
Data Models Module

This module contains all the dataclass definitions used throughout the PDF crawler,
including results, configurations, and analysis structures.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DownloadResult:
    """Result of a single PDF download attempt"""
    url: str
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None
    file_size: int = 0


@dataclass
class DepartmentResults:
    """Results for crawling a single department"""
    department: str
    urls_crawled: int
    pdfs_found: int
    pdfs_downloaded: int
    pdfs_failed: int
    pdfs_skipped: int
    total_size: int
    duration: float
    errors: List[str]


@dataclass
class CrawlResults:
    """Overall crawling results"""
    departments: List[DepartmentResults]
    total_pdfs_found: int
    total_pdfs_downloaded: int
    total_duration: float
    success_rate: float


@dataclass
class DepartmentAnalysis:
    """Analysis results for a single department"""
    department: str
    seed_urls_accessible: int
    seed_urls_total: int
    estimated_pdfs: int
    requires_browser: bool
    rate_limit_detected: bool
    issues: List[str]


@dataclass
class DryRunReport:
    """Dry-run analysis report"""
    department_analyses: List[DepartmentAnalysis]
    total_estimated_pdfs: int
    estimated_duration: float
    issues_found: List[str]
    recommendations: List[str]