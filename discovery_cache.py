#!/usr/bin/env python3
"""
Discovery Cache for Incremental Updates

Tracks discovered URLs across crawl runs to enable delta updates.
Only crawls new/changed content on subsequent runs.
"""

import json
import os
import time
import hashlib
from typing import Dict, Set, List, Optional
from datetime import datetime, timedelta


class DiscoveryCache:
    """Manages cache of discovered URLs for incremental updates"""
    
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "discovery_cache.json")
        self.url_cache_file = os.path.join(cache_dir, "url_discovery_cache.json")
        
        # Ensure cache directory exists
        os.makedirs(cache_dir, exist_ok=True)
        
        # Load existing caches
        self.pdf_cache = self._load_cache(self.cache_file)
        self.url_cache = self._load_cache(self.url_cache_file)
    
    def _load_cache(self, file_path: str) -> Dict:
        """Load cache from file"""
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load cache {file_path}: {e}")
        return {}
    
    def _save_cache(self, cache_data: Dict, file_path: str):
        """Save cache to file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            print(f"Error saving cache {file_path}: {e}")
    
    def _get_url_hash(self, url: str) -> str:
        """Get hash for URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def is_pdf_cached(self, pdf_url: str) -> bool:
        """Check if PDF URL was discovered in previous runs"""
        url_hash = self._get_url_hash(pdf_url)
        return url_hash in self.pdf_cache
    
    def is_page_recently_crawled(self, page_url: str, max_age_hours: int = 24) -> bool:
        """Check if page was crawled recently"""
        url_hash = self._get_url_hash(page_url)
        
        if url_hash not in self.url_cache:
            return False
        
        last_crawled = self.url_cache[url_hash].get('last_crawled', 0)
        age_hours = (time.time() - last_crawled) / 3600
        
        return age_hours < max_age_hours
    
    def cache_discovered_pdfs(self, pdf_urls: List[str], source_page: str):
        """Cache discovered PDF URLs"""
        current_time = time.time()
        
        for pdf_url in pdf_urls:
            url_hash = self._get_url_hash(pdf_url)
            self.pdf_cache[url_hash] = {
                'url': pdf_url,
                'discovered_time': current_time,
                'source_page': source_page,
                'last_seen': current_time
            }
        
        self._save_cache(self.pdf_cache, self.cache_file)
    
    def cache_page_crawl(self, page_url: str, pdf_count: int):
        """Cache that a page was crawled"""
        url_hash = self._get_url_hash(page_url)
        current_time = time.time()
        
        self.url_cache[url_hash] = {
            'url': page_url,
            'last_crawled': current_time,
            'pdf_count': pdf_count,
            'crawl_count': self.url_cache.get(url_hash, {}).get('crawl_count', 0) + 1
        }
        
        self._save_cache(self.url_cache, self.url_cache_file)
    
    def get_new_pdfs_only(self, discovered_pdfs: List[str]) -> List[str]:
        """Filter to only new PDFs not seen before"""
        new_pdfs = []
        
        for pdf_url in discovered_pdfs:
            if not self.is_pdf_cached(pdf_url):
                new_pdfs.append(pdf_url)
            else:
                # Update last_seen time for existing PDFs
                url_hash = self._get_url_hash(pdf_url)
                if url_hash in self.pdf_cache:
                    self.pdf_cache[url_hash]['last_seen'] = time.time()
        
        # Save updated cache
        if discovered_pdfs:  # Only save if we processed some PDFs
            self._save_cache(self.pdf_cache, self.cache_file)
        
        return new_pdfs
    
    def should_skip_page(self, page_url: str, max_age_hours: int = 24) -> bool:
        """Determine if page should be skipped based on cache"""
        return self.is_page_recently_crawled(page_url, max_age_hours)
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about cached data"""
        current_time = time.time()
        
        # PDF cache stats
        total_pdfs = len(self.pdf_cache)
        recent_pdfs = sum(1 for entry in self.pdf_cache.values() 
                         if (current_time - entry.get('last_seen', 0)) < 86400)  # 24 hours
        
        # URL cache stats
        total_pages = len(self.url_cache)
        recent_pages = sum(1 for entry in self.url_cache.values()
                          if (current_time - entry.get('last_crawled', 0)) < 86400)
        
        return {
            'total_cached_pdfs': total_pdfs,
            'recent_pdfs': recent_pdfs,
            'total_cached_pages': total_pages,
            'recent_pages': recent_pages,
            'cache_age_hours': (current_time - min([entry.get('discovered_time', current_time) 
                                                   for entry in self.pdf_cache.values()], 
                                                  default=current_time)) / 3600
        }
    
    def cleanup_old_entries(self, max_age_days: int = 30):
        """Remove old cache entries"""
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        
        # Clean PDF cache
        old_pdf_keys = [
            key for key, entry in self.pdf_cache.items()
            if (current_time - entry.get('last_seen', 0)) > max_age_seconds
        ]
        
        for key in old_pdf_keys:
            del self.pdf_cache[key]
        
        # Clean URL cache
        old_url_keys = [
            key for key, entry in self.url_cache.items()
            if (current_time - entry.get('last_crawled', 0)) > max_age_seconds
        ]
        
        for key in old_url_keys:
            del self.url_cache[key]
        
        # Save cleaned caches
        self._save_cache(self.pdf_cache, self.cache_file)
        self._save_cache(self.url_cache, self.url_cache_file)
        
        return len(old_pdf_keys), len(old_url_keys)
