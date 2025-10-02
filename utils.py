"""
Common Utilities Module

This module contains helper functions and utilities used across the PDF crawler,
including URL parsing, file handling, error handling, and retry logic.
"""

import time
import logging
import random
from functools import wraps
from typing import Callable, Any, List
from urllib.parse import urlparse, urljoin
import requests


def handle_error(error: Exception, context: str, url: str = None) -> bool:
    """
    Simple error handling with logging and retry logic
    Returns True if should retry, False if should skip
    """
    error_msg = f"{context}: {str(error)}"
    if url:
        error_msg += f" (URL: {url})"
    
    logging.error(error_msg)
    
    # Simple retry logic for network errors
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return True  # Retry network errors
    elif isinstance(error, requests.HTTPError):
        if error.response.status_code >= 500:
            return True  # Retry server errors
    
    return False  # Skip other errors


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Simple exponential backoff retry decorator"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    logging.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {str(e)}")
                    time.sleep(delay)
        return wrapper
    return decorator


def normalize_url(url: str, base_url: str = None) -> str:
    """
    Normalize and resolve relative URLs to absolute URLs
    
    Args:
        url: URL to normalize (can be relative or absolute)
        base_url: Base URL to resolve relative URLs against
        
    Returns:
        Normalized absolute URL
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # If already absolute, return as-is (after basic cleanup)
    if url.startswith(('http://', 'https://')):
        return url
    
    # If base_url provided, resolve relative URL
    if base_url:
        from urllib.parse import urljoin
        return urljoin(base_url, url)
    
    return url


def extract_domain(url: str) -> str:
    """
    Extract domain name from URL
    
    Args:
        url: URL to extract domain from
        
    Returns:
        Domain name (e.g., 'example.com')
    """
    if not url:
        return ""
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Remove 'www.' prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
            
        return domain
    except Exception:
        return ""


def is_valid_url(url: str) -> bool:
    """
    Check if URL is valid and properly formatted
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    try:
        parsed = urlparse(url.strip())
        return bool(parsed.netloc and parsed.scheme in ('http', 'https'))
    except Exception:
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for filesystem compatibility across platforms
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem use
    """
    if not filename:
        return f"unnamed_file_{int(time.time())}"
    
    import re
    
    # Remove or replace invalid characters for Windows/Unix filesystems
    # Invalid characters: < > : " / \ | ? * and control characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove control characters (0x00-0x1f, 0x7f-0x9f)
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    
    # Replace multiple consecutive spaces/underscores with single underscore
    filename = re.sub(r'[_\s]+', '_', filename)
    
    # Remove leading/trailing spaces and dots (Windows doesn't like these)
    filename = filename.strip(' .')
    
    # Handle reserved names on Windows
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    name_part = filename.split('.')[0].upper()
    if name_part in reserved_names:
        filename = f"_{filename}"
    
    # Limit total length (most filesystems support 255 chars)
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = 255 - len(ext) - 1 if ext else 255
        filename = name[:max_name_length] + ('.' + ext if ext else '')
    
    # Ensure filename is not empty after sanitization
    if not filename or filename in ('_', '.', ''):
        filename = f"unnamed_file_{int(time.time())}"
    
    return filename


class UserAgentRotator:
    """Manages user agent rotation for requests"""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
        ]
        self.current_index = 0
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent string"""
        return random.choice(self.user_agents)
    
    def get_next_user_agent(self) -> str:
        """Get the next user agent in rotation"""
        user_agent = self.user_agents[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.user_agents)
        return user_agent


class SessionManager:
    """Manages HTTP sessions with rotation and persistence"""
    
    def __init__(self, max_sessions: int = 3):
        self.max_sessions = max_sessions
        self.sessions = []
        self.user_agent_rotator = UserAgentRotator()
        self.current_session_index = 0
        self._initialize_sessions()
    
    def _initialize_sessions(self):
        """Initialize multiple sessions with different configurations"""
        for i in range(self.max_sessions):
            session = requests.Session()
            
            # Set different user agent for each session
            session.headers.update({
                'User-Agent': self.user_agent_rotator.get_next_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            
            # Configure retry strategy
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            self.sessions.append(session)
    
    def get_session(self) -> requests.Session:
        """Get the current session"""
        return self.sessions[self.current_session_index]
    
    def rotate_session(self) -> requests.Session:
        """Rotate to the next session"""
        self.current_session_index = (self.current_session_index + 1) % len(self.sessions)
        return self.get_session()
    
    def get_random_session(self) -> requests.Session:
        """Get a random session"""
        return random.choice(self.sessions)
    
    def refresh_user_agents(self):
        """Refresh user agents for all sessions"""
        for session in self.sessions:
            session.headers['User-Agent'] = self.user_agent_rotator.get_random_user_agent()


def normalize_url(url: str, base_url: str = None) -> str:
    """Normalize and resolve relative URLs"""
    if base_url and not url.startswith(('http://', 'https://')):
        return urljoin(base_url, url)
    return url.strip()


def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    parsed = urlparse(url)
    return parsed.netloc


def is_valid_url(url: str) -> bool:
    """Check if URL is valid and accessible"""
    try:
        parsed = urlparse(url)
        return bool(parsed.netloc and parsed.scheme in ('http', 'https'))
    except Exception:
        return False





def setup_logging(log_level: str = "INFO", log_file: str = None):
    """
    Set up comprehensive logging configuration for the crawler
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    # Configure logging format with more detail
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    
    # Set up handlers
    handlers = []
    
    # Console handler with color support if available
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Use simpler format for console
    console_format = '%(asctime)s - %(levelname)s - %(message)s'
    console_handler.setFormatter(logging.Formatter(console_format, datefmt='%H:%M:%S'))
    handlers.append(console_handler)
    
    # File handler with detailed format
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always debug level for file
        file_handler.setFormatter(logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S'))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,  # Set to DEBUG, handlers will filter
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    # Set up logger for the crawler
    logger = logging.getLogger('hk_pdf_crawler')
    logger.info(f"Logging initialized at {log_level} level" + (f" (file: {log_file})" if log_file else ""))
    
    # Reduce noise from third-party libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string (e.g., "1.5 MB", "234 KB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string (e.g., "2h 15m 30s", "45s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"
    
    hours = int(minutes // 60)
    remaining_minutes = int(minutes % 60)
    
    if hours < 24:
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
    
    days = int(hours // 24)
    remaining_hours = int(hours % 24)
    
    return f"{days}d {remaining_hours}h {remaining_minutes}m"


def clean_text(text: str) -> str:
    """
    Clean and normalize text content
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    import re
    
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove common HTML entities
    html_entities = {
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&nbsp;': ' '
    }
    
    for entity, replacement in html_entities.items():
        text = text.replace(entity, replacement)
    
    return text


def is_government_domain(url: str) -> bool:
    """
    Check if URL belongs to Hong Kong government domain
    
    Args:
        url: URL to check
        
    Returns:
        True if it's a HK government domain
    """
    if not url:
        return False
    
    domain = extract_domain(url).lower()
    
    # Known HK government domains
    gov_domains = [
        'gov.hk',
        'labour.gov.hk',
        'bd.gov.hk',
        'fehd.gov.hk',
        'epd.gov.hk',
        'fsd.gov.hk',
        'landsd.gov.hk',
        'devb.gov.hk',
        'hkfsd.gov.hk',
        'info.gov.hk',
        'had.gov.hk',
        'td.gov.hk',
        'immd.gov.hk',
        'ird.gov.hk',
        'customs.gov.hk'
    ]
    
    return any(domain.endswith(gov_domain) for gov_domain in gov_domains)


def get_url_file_extension(url: str) -> str:
    """
    Extract file extension from URL
    
    Args:
        url: URL to analyze
        
    Returns:
        File extension (without dot) or empty string
    """
    if not url:
        return ""
    
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        path = unquote(parsed.path)
        
        if '.' in path:
            return path.split('.')[-1].lower()
    except Exception:
        pass
    
    return ""


def create_directory_safely(directory_path: str) -> bool:
    """
    Create directory with proper error handling
    
    Args:
        directory_path: Path to create
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from pathlib import Path
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Failed to create directory {directory_path}: {e}")
        return False


def safe_json_dump(data: Any, file_path: str) -> bool:
    """
    Safely write JSON data to file with error handling
    
    Args:
        data: Data to write
        file_path: File path to write to
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import json
        from pathlib import Path
        
        # Create directory if needed
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        logging.error(f"Failed to write JSON to {file_path}: {e}")
        return False


def safe_json_load(file_path: str) -> Any:
    """
    Safely load JSON data from file with error handling
    
    Args:
        file_path: File path to read from
        
    Returns:
        Loaded data or None if failed
    """
    try:
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.debug(f"Failed to load JSON from {file_path}: {e}")
        return None


def get_timestamp() -> str:
    """
    Get current timestamp in ISO format
    
    Returns:
        ISO formatted timestamp string
    """
    from datetime import datetime
    return datetime.now().isoformat()


def get_file_timestamp() -> str:
    """
    Get current timestamp suitable for filenames
    
    Returns:
        Timestamp string safe for filenames (YYYYMMDD_HHMMSS)
    """
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")