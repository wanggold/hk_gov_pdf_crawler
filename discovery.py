"""
URL Discovery and PDF Detection Module

This module handles discovering URLs from seed pages and identifying PDF links
using various detection methods including URL patterns, link text, and content validation.
"""

from typing import List, Set, Optional, Dict
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging
import time
import re
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET
from utils import SessionManager, normalize_url, extract_domain


class URLDiscovery:
    """Handles URL discovery and PDF link identification"""
    
    def __init__(self, session: requests.Session = None):
        self.session_manager = SessionManager() if session is None else None
        self.session = session or self.session_manager.get_session()
        self.visited_urls: Set[str] = set()
        self.robots_cache: dict = {}
        self.sitemap_cache: dict = {}
        self.logger = logging.getLogger(__name__)
        
    def discover_urls(self, seed_url: str, max_depth: int) -> List[str]:
        """
        Discover URLs from seed URL with depth limits
        
        Args:
            seed_url: Starting URL for discovery
            max_depth: Maximum crawling depth
            
        Returns:
            List of discovered URLs
        """
        discovered_urls = []
        urls_to_process = [(seed_url, 0)]  # (url, depth)
        
        while urls_to_process:
            current_url, depth = urls_to_process.pop(0)
            
            # Skip if already visited or depth exceeded
            if current_url in self.visited_urls or depth > max_depth:
                continue
                
            self.visited_urls.add(current_url)
            discovered_urls.append(current_url)
            
            try:
                # Check robots.txt before crawling
                domain = urlparse(current_url).netloc
                if not self.check_robots_txt(domain, current_url):
                    self.logger.info(f"Robots.txt disallows crawling: {current_url}")
                    continue
                
                # Fetch the page
                response = self.session.get(current_url, timeout=30)
                response.raise_for_status()
                
                # Parse HTML and find links
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all links on the page
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    absolute_url = urljoin(current_url, href)
                    
                    # Only follow links within the same domain
                    if urlparse(absolute_url).netloc == domain:
                        # Add to processing queue if not visited and within depth limit
                        if absolute_url not in self.visited_urls and depth < max_depth:
                            urls_to_process.append((absolute_url, depth + 1))
                
                # Add small delay to be respectful
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error crawling {current_url}: {str(e)}")
                continue
        
        return discovered_urls
        
    def find_pdf_links(self, url: str) -> List[str]:
        """
        Find PDF links on a page using BeautifulSoup
        
        Args:
            url: URL of the page to scan for PDF links
            
        Returns:
            List of PDF URLs found on the page
        """
        pdf_links = []
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text(strip=True)
                
                # Handle JavaScript links that contain PDF URLs
                if href.startswith('javascript:'):
                    # Extract PDF URL from JavaScript function calls
                    import re
                    # Look for PDF paths in the JavaScript code
                    pdf_matches = re.findall(r'["\']([^"\']*\.pdf[^"\']*)["\']', href, re.IGNORECASE)
                    for pdf_path in pdf_matches:
                        # Skip if it's just a variable name or function parameter name
                        if '/' in pdf_path or pdf_path.startswith('http'):
                            absolute_url = urljoin(url, pdf_path)
                            if self.is_pdf_link(absolute_url, link_text):
                                pdf_links.append(absolute_url)
                    continue
                
                # Skip empty hrefs and anchors
                if href.startswith('#') or not href.strip():
                    continue
                
                # Convert to absolute URL
                absolute_url = urljoin(url, href)
                
                # Extract PDF from viewer URLs (e.g., PDF.js viewer with file= parameter)
                if 'viewer.html' in absolute_url.lower() or 'pdfjs' in absolute_url.lower():
                    import re
                    from urllib.parse import urlparse, parse_qs, unquote
                    # Try to extract PDF URL from query parameters
                    parsed = urlparse(absolute_url)
                    params = parse_qs(parsed.query)
                    if 'file' in params:
                        pdf_url = unquote(params['file'][0])
                        # Make it absolute if needed
                        if pdf_url.startswith('http'):
                            pdf_links.append(pdf_url)
                        else:
                            pdf_links.append(urljoin(absolute_url, pdf_url))
                        continue
                
                # Check if this is a PDF link
                if self.is_pdf_link(absolute_url, link_text):
                    pdf_links.append(absolute_url)
            
            # Also check for embedded PDF viewers or iframes
            for iframe in soup.find_all('iframe', src=True):
                src = iframe['src']
                absolute_url = urljoin(url, src)
                if self.is_pdf_link(absolute_url):
                    pdf_links.append(absolute_url)
            
            # Check for data attributes that might contain PDF URLs
            for element in soup.find_all(attrs={'data-url': True}):
                data_url = element['data-url']
                absolute_url = urljoin(url, data_url)
                if self.is_pdf_link(absolute_url):
                    pdf_links.append(absolute_url)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_pdf_links = []
            for link in pdf_links:
                if link not in seen:
                    seen.add(link)
                    unique_pdf_links.append(link)
            
            self.logger.info(f"Found {len(unique_pdf_links)} PDF links on {url}")
            return unique_pdf_links
            
        except Exception as e:
            self.logger.error(f"Error finding PDF links on {url}: {str(e)}")
            return []
        
    def is_pdf_link(self, url: str, link_text: str = "") -> bool:
        """
        Check if URL points to a PDF using multiple methods
        
        Args:
            url: URL to check
            link_text: Text content of the link (optional)
            
        Returns:
            True if URL likely points to a PDF
        """
        # Basic URL pattern matching - check file extension
        if url.lower().endswith('.pdf'):
            return True
        
        # Check for PDF in URL path or query parameters
        if '.pdf' in url.lower():
            return True
        
        # Check for PDF in URL path or query parameters
        if '.pdf' in url.lower():
            return True
        
        # Link text analysis - look for PDF-related keywords
        if link_text:
            pdf_keywords = [
                'pdf', 'download', 'document', 'report', 'manual', 
                'guide', 'handbook', 'publication', 'brochure',
                'leaflet', 'circular', 'notice', 'code', 'standard'
            ]
            link_text_lower = link_text.lower()
            
            # Check if link text contains PDF keyword
            for keyword in pdf_keywords:
                if keyword in link_text_lower:
                    # Additional validation - avoid false positives
                    if any(exclude in link_text_lower for exclude in ['html', 'webpage', 'page']):
                        continue
                    return True
        
        # Check URL patterns that commonly indicate PDFs
        pdf_url_patterns = [
            r'/download/',
            r'/documents?/',
            r'/files?/',
            r'/publications?/',
            r'/resources?/',
            r'/attachments?/',
            r'\.pdf\?',
            r'\.pdf&',
            r'filetype=pdf',
            r'format=pdf',
            r'type=pdf'
        ]
        
        for pattern in pdf_url_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        
        return False
        
    def validate_pdf_url(self, url: str) -> bool:
        """
        Validate that URL actually points to a PDF using HEAD request
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL points to a valid PDF
        """
        try:
            # Use HEAD request to check content type without downloading
            response = self.session.head(url, timeout=10, allow_redirects=True)
            
            # Check if request was successful
            if response.status_code != 200:
                return False
            
            # Check content type header
            content_type = response.headers.get('content-type', '').lower()
            if 'application/pdf' in content_type:
                return True
            
            # Some servers don't set proper content-type, check content-disposition
            content_disposition = response.headers.get('content-disposition', '').lower()
            if '.pdf' in content_disposition:
                return True
            
            # If HEAD request doesn't work, try a small GET request
            if not content_type or content_type == 'application/octet-stream':
                response = self.session.get(url, timeout=10, stream=True)
                
                # Read first few bytes to check PDF signature
                chunk = next(response.iter_content(chunk_size=8), b'')
                if chunk.startswith(b'%PDF'):
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error validating PDF URL {url}: {str(e)}")
            return False
        
    def check_robots_txt(self, domain: str, url: str = None) -> bool:
        """
        Check robots.txt for crawling permissions with override for government sites
        
        Args:
            domain: Domain to check robots.txt for
            url: Specific URL to check (optional)
            
        Returns:
            True if crawling is allowed
        """
        # Override for Hong Kong government sites
        hk_gov_domains = [
            'gov.hk', 'labour.gov.hk', 'bd.gov.hk', 'fehd.gov.hk',
            'epd.gov.hk', 'fsd.gov.hk', 'landsd.gov.hk', 'devb.gov.hk'
        ]
        
        if any(gov_domain in domain for gov_domain in hk_gov_domains):
            self.logger.info(f"Allowing crawling of HK government site: {domain}")
            return True
        
        # Check cache first
        if domain in self.robots_cache:
            rp = self.robots_cache[domain]
        else:
            # Fetch and parse robots.txt
            try:
                rp = RobotFileParser()
                robots_url = f"https://{domain}/robots.txt"
                rp.set_url(robots_url)
                rp.read()
                self.robots_cache[domain] = rp
                
            except Exception as e:
                self.logger.warning(f"Could not fetch robots.txt for {domain}: {str(e)}")
                # If we can't fetch robots.txt, assume crawling is allowed
                return True
        
        # Check if our user agent can fetch the URL
        user_agent = self.session.headers.get('User-Agent', '*')
        
        if url:
            return rp.can_fetch(user_agent, url)
        else:
            return rp.can_fetch(user_agent, f"https://{domain}/")
    
    def reset_visited_urls(self):
        """Reset the visited URLs set for a new crawling session"""
        self.visited_urls.clear()
        
    def get_visited_count(self) -> int:
        """Get the number of visited URLs"""
        return len(self.visited_urls)
    
    def discover_urls_from_sitemap(self, domain: str) -> List[str]:
        """
        Discover URLs from sitemap.xml files
        
        Args:
            domain: Domain to check for sitemaps
            
        Returns:
            List of URLs found in sitemaps
        """
        if domain in self.sitemap_cache:
            return self.sitemap_cache[domain]
        
        sitemap_urls = []
        
        # Common sitemap locations
        sitemap_locations = [
            f"https://{domain}/sitemap.xml",
            f"https://{domain}/sitemap_index.xml",
            f"https://{domain}/sitemaps.xml",
            f"http://{domain}/sitemap.xml",
        ]
        
        for sitemap_url in sitemap_locations:
            try:
                self.logger.info(f"Checking sitemap: {sitemap_url}")
                response = self.session.get(sitemap_url, timeout=15)
                
                if response.status_code == 200:
                    urls = self._parse_sitemap(response.content, domain)
                    sitemap_urls.extend(urls)
                    self.logger.info(f"Found {len(urls)} URLs in sitemap: {sitemap_url}")
                    break  # Use first successful sitemap
                    
            except Exception as e:
                self.logger.debug(f"Could not fetch sitemap {sitemap_url}: {e}")
                continue
        
        # Cache results
        self.sitemap_cache[domain] = sitemap_urls
        return sitemap_urls
    
    def _parse_sitemap(self, content: bytes, domain: str) -> List[str]:
        """
        Parse sitemap XML content and extract URLs
        
        Args:
            content: XML content of the sitemap
            domain: Domain to filter URLs
            
        Returns:
            List of URLs from the sitemap
        """
        urls = []
        
        try:
            root = ET.fromstring(content)
            
            # Handle sitemap index files
            for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                loc_elem = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc_elem is not None:
                    # Recursively parse nested sitemaps
                    try:
                        response = self.session.get(loc_elem.text, timeout=15)
                        if response.status_code == 200:
                            nested_urls = self._parse_sitemap(response.content, domain)
                            urls.extend(nested_urls)
                    except Exception as e:
                        self.logger.debug(f"Could not fetch nested sitemap {loc_elem.text}: {e}")
            
            # Handle regular sitemap URLs
            for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc_elem is not None:
                    url = loc_elem.text
                    # Only include URLs from the same domain
                    if extract_domain(url) == domain:
                        urls.append(url)
        
        except ET.ParseError as e:
            self.logger.warning(f"Could not parse sitemap XML: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing sitemap: {e}")
        
        return urls
    
    def discover_archive_sections(self, base_url: str) -> List[str]:
        """
        Discover archive and historical sections
        
        Args:
            base_url: Base URL to search for archives
            
        Returns:
            List of archive URLs found
        """
        archive_urls = []
        
        try:
            response = self.session.get(base_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for archive-related links
            archive_keywords = [
                'archive', 'archives', 'historical', 'history', 'past',
                'previous', 'old', 'legacy', 'back-issues', 'publications'
            ]
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text(strip=True).lower()
                
                # Check if link text or href contains archive keywords
                for keyword in archive_keywords:
                    if keyword in link_text or keyword in href.lower():
                        absolute_url = urljoin(base_url, href)
                        if extract_domain(absolute_url) == extract_domain(base_url):
                            archive_urls.append(absolute_url)
                        break
            
            # Look for year-based navigation (common in government sites)
            year_pattern = r'\b(19|20)\d{2}\b'
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text(strip=True)
                
                if re.search(year_pattern, link_text) or re.search(year_pattern, href):
                    absolute_url = urljoin(base_url, href)
                    if extract_domain(absolute_url) == extract_domain(base_url):
                        archive_urls.append(absolute_url)
        
        except Exception as e:
            self.logger.error(f"Error discovering archive sections from {base_url}: {e}")
        
        return list(set(archive_urls))  # Remove duplicates
    
    def search_for_pdfs(self, base_url: str, search_terms: List[str] = None) -> List[str]:
        """
        Search for PDFs using search forms with keywords
        
        Args:
            base_url: Base URL to search from
            search_terms: List of search terms to use
            
        Returns:
            List of PDF URLs found through search
        """
        if search_terms is None:
            search_terms = [
                'PDF', 'document', 'publication', 'report', 'manual',
                'guide', 'handbook', 'circular', 'notice', 'code'
            ]
        
        pdf_urls = []
        
        try:
            response = self.session.get(base_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for search forms
            search_forms = soup.find_all('form')
            
            for form in search_forms:
                # Check if this looks like a search form
                search_inputs = form.find_all('input', {'type': ['search', 'text']})
                if not search_inputs:
                    continue
                
                # Try to identify the search input field
                search_input = None
                for inp in search_inputs:
                    name = inp.get('name', '').lower()
                    placeholder = inp.get('placeholder', '').lower()
                    
                    if any(keyword in name or keyword in placeholder 
                           for keyword in ['search', 'query', 'q', 'keyword']):
                        search_input = inp
                        break
                
                if search_input:
                    # Try searching with each term
                    for term in search_terms[:3]:  # Limit to avoid overwhelming the server
                        try:
                            search_results = self._perform_search(form, search_input, term, base_url)
                            pdf_urls.extend(search_results)
                            time.sleep(2)  # Be respectful with search requests
                        except Exception as e:
                            self.logger.debug(f"Search failed for term '{term}': {e}")
                            continue
        
        except Exception as e:
            self.logger.error(f"Error searching for PDFs from {base_url}: {e}")
        
        return list(set(pdf_urls))  # Remove duplicates
    
    def _perform_search(self, form, search_input, term: str, base_url: str) -> List[str]:
        """
        Perform a search using a form and extract PDF links from results
        
        Args:
            form: BeautifulSoup form element
            search_input: Search input field
            term: Search term to use
            base_url: Base URL for resolving relative URLs
            
        Returns:
            List of PDF URLs found in search results
        """
        pdf_urls = []
        
        try:
            # Prepare form data
            form_data = {}
            
            # Add all hidden inputs
            for hidden_input in form.find_all('input', {'type': 'hidden'}):
                name = hidden_input.get('name')
                value = hidden_input.get('value', '')
                if name:
                    form_data[name] = value
            
            # Add search term
            search_name = search_input.get('name')
            if search_name:
                form_data[search_name] = term
            
            # Determine form action and method
            action = form.get('action', '')
            method = form.get('method', 'get').lower()
            
            # Resolve form action URL
            if action:
                form_url = urljoin(base_url, action)
            else:
                form_url = base_url
            
            # Submit the form
            if method == 'post':
                response = self.session.post(form_url, data=form_data, timeout=30)
            else:
                response = self.session.get(form_url, params=form_data, timeout=30)
            
            response.raise_for_status()
            
            # Parse search results for PDF links
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text(strip=True)
                
                absolute_url = urljoin(form_url, href)
                
                if self.is_pdf_link(absolute_url, link_text):
                    pdf_urls.append(absolute_url)
        
        except Exception as e:
            self.logger.debug(f"Form search failed: {e}")
        
        return pdf_urls
    
    def discover_comprehensive_urls(self, seed_url: str, max_depth: int = 3) -> List[str]:
        """
        Comprehensive URL discovery using multiple strategies
        
        Args:
            seed_url: Starting URL
            max_depth: Maximum crawling depth
            
        Returns:
            List of all discovered URLs
        """
        all_urls = []
        domain = extract_domain(seed_url)
        
        # Strategy 1: Regular crawling
        self.logger.info(f"Starting regular URL discovery for {domain}")
        crawled_urls = self.discover_urls(seed_url, max_depth)
        all_urls.extend(crawled_urls)
        
        # Strategy 2: Sitemap discovery
        self.logger.info(f"Checking sitemaps for {domain}")
        sitemap_urls = self.discover_urls_from_sitemap(domain)
        all_urls.extend(sitemap_urls)
        
        # Strategy 3: Archive section discovery
        self.logger.info(f"Discovering archive sections for {domain}")
        archive_urls = self.discover_archive_sections(seed_url)
        all_urls.extend(archive_urls)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in all_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        self.logger.info(f"Comprehensive discovery found {len(unique_urls)} unique URLs for {domain}")
        return unique_urls