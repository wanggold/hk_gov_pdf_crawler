"""
Configuration management for HK PDF Crawler.

This module handles loading configuration from YAML files and parsing
markdown files to create configuration objects.
"""

import yaml
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class DepartmentConfig:
    """Configuration for a single department."""
    name: str
    seed_urls: List[str]
    max_depth: int = 3
    max_pages: int = 1000
    time_limit: int = 1800  # 30 minutes
    document_types: Optional[List[str]] = None  # Filter by doc types


@dataclass
class CrawlSettings:
    """General crawling settings."""
    delay_between_requests: float = 0.3
    max_concurrent_downloads: int = 15
    respect_robots_txt: bool = True
    user_agent: str = "HK-PDF-Crawler/1.0"
    enable_browser_automation: bool = True
    request_timeout: int = 30


@dataclass
class StorageConfig:
    """Storage configuration for local and S3 storage."""
    local_path: str = "./downloads"
    organize_by_department: bool = True
    s3_enabled: bool = False
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = None


@dataclass
class CrawlConfig:
    """Main configuration object containing all settings."""
    departments: Dict[str, DepartmentConfig]
    settings: CrawlSettings = field(default_factory=CrawlSettings)
    storage: StorageConfig = field(default_factory=StorageConfig)


def load_config(config_path: str) -> CrawlConfig:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        CrawlConfig object with loaded configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        ValueError: If configuration is invalid
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to parse YAML configuration: {e}")
    
    if not data:
        raise ValueError("Configuration file is empty")
    
    # Validate required sections
    if 'departments' not in data:
        raise ValueError("Configuration must contain 'departments' section")
    
    if not data['departments']:
        raise ValueError("At least one department must be configured")
    
    # Parse departments
    departments = {}
    for dept_key, dept_data in data['departments'].items():
        if not isinstance(dept_data, dict):
            raise ValueError(f"Department '{dept_key}' configuration must be a dictionary")
        
        if 'name' not in dept_data:
            raise ValueError(f"Department '{dept_key}' must have a 'name' field")
        
        if 'seed_urls' not in dept_data:
            raise ValueError(f"Department '{dept_key}' must have 'seed_urls' field")
        
        if not dept_data['seed_urls']:
            raise ValueError(f"Department '{dept_key}' must have at least one seed URL")
        
        departments[dept_key] = DepartmentConfig(
            name=dept_data['name'],
            seed_urls=dept_data['seed_urls'],
            max_depth=dept_data.get('max_depth', 3),
            max_pages=dept_data.get('max_pages', 1000),
            time_limit=dept_data.get('time_limit', 1800),
            document_types=dept_data.get('document_types')
        )
    
    # Parse settings
    settings_data = data.get('settings', {})
    settings = CrawlSettings(
        delay_between_requests=settings_data.get('delay_between_requests', 0.3),
        max_concurrent_downloads=settings_data.get('max_concurrent_downloads', 15),
        respect_robots_txt=settings_data.get('respect_robots_txt', True),
        user_agent=settings_data.get('user_agent', "HK-PDF-Crawler/1.0"),
        enable_browser_automation=settings_data.get('enable_browser_automation', True),
        request_timeout=settings_data.get('request_timeout', 30)
    )
    
    # Parse storage
    storage_data = data.get('storage', {})
    storage = StorageConfig(
        local_path=storage_data.get('local_path', "./downloads"),
        organize_by_department=storage_data.get('organize_by_department', True),
        s3_enabled=storage_data.get('s3_enabled', False),
        s3_bucket=storage_data.get('s3_bucket'),
        s3_prefix=storage_data.get('s3_prefix')
    )
    
    return CrawlConfig(
        departments=departments,
        settings=settings,
        storage=storage
    )


def create_config_from_markdown(markdown_path: str) -> CrawlConfig:
    """
    Parse markdown file and create default configuration.
    
    Args:
        markdown_path: Path to the markdown file with department URLs
        
    Returns:
        CrawlConfig object with parsed departments and default settings
        
    Raises:
        FileNotFoundError: If markdown file doesn't exist
        ValueError: If markdown parsing fails or no departments found
    """
    markdown_file = Path(markdown_path)
    
    if not markdown_file.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_path}")
    
    try:
        with open(markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Failed to read markdown file: {e}")
    
    departments = {}
    current_dept = None
    current_dept_name = None
    
    # Parse markdown structure to extract department names and URLs
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Match department headers: ## 1. Department Name (ABBR):
        dept_match = re.match(r'^##\s+\d+\.\s+(.+?)(?:\s*\([^)]+\))?\s*:\s*$', line)
        if dept_match:
            dept_name = dept_match.group(1).strip()
            # Create department key from name (lowercase, replace spaces with underscores)
            current_dept = re.sub(r'[^\w\s]', '', dept_name.lower()).replace(' ', '_')
            current_dept_name = dept_name
            
            departments[current_dept] = DepartmentConfig(
                name=dept_name,
                seed_urls=[],
                max_depth=3,
                max_pages=500,
                time_limit=1800
            )
            continue
        
        # Match URL lines: 1. **Description**: https://...
        if current_dept and line:
            # Look for URLs in the line
            url_matches = re.findall(r'https?://[^\s\)]+', line)
            for url in url_matches:
                # Clean up URL (remove trailing punctuation)
                url = re.sub(r'[.,;]+$', '', url)
                if url not in departments[current_dept].seed_urls:
                    departments[current_dept].seed_urls.append(url)
    
    if not departments:
        raise ValueError("No departments found in markdown file")
    
    # Remove departments with no URLs
    departments = {k: v for k, v in departments.items() if v.seed_urls}
    
    if not departments:
        raise ValueError("No departments with valid URLs found in markdown file")
    
    return CrawlConfig(
        departments=departments,
        settings=CrawlSettings(),
        storage=StorageConfig(
            s3_enabled=True,
            s3_bucket="hk-gov-pdf-crawler-905418162919",
            s3_prefix="run4/"
        )
    )


def save_config_to_yaml(config: CrawlConfig, output_path: str) -> None:
    """
    Save configuration to YAML file.
    
    Args:
        config: CrawlConfig object to save
        output_path: Path where to save the YAML file
    """
    # Convert config to dictionary
    config_dict = {
        'departments': {},
        'settings': {
            'delay_between_requests': config.settings.delay_between_requests,
            'max_concurrent_downloads': config.settings.max_concurrent_downloads,
            'respect_robots_txt': config.settings.respect_robots_txt,
            'user_agent': config.settings.user_agent,
            'enable_browser_automation': config.settings.enable_browser_automation,
            'request_timeout': config.settings.request_timeout
        },
        'storage': {
            'local_path': config.storage.local_path,
            'organize_by_department': config.storage.organize_by_department,
            's3_enabled': config.storage.s3_enabled,
            's3_bucket': config.storage.s3_bucket,
            's3_prefix': config.storage.s3_prefix
        }
    }
    
    # Add departments
    for dept_key, dept_config in config.departments.items():
        config_dict['departments'][dept_key] = {
            'name': dept_config.name,
            'seed_urls': dept_config.seed_urls,
            'max_depth': dept_config.max_depth,
            'max_pages': dept_config.max_pages,
            'time_limit': dept_config.time_limit
        }
        if dept_config.document_types:
            config_dict['departments'][dept_key]['document_types'] = dept_config.document_types
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False, indent=2)