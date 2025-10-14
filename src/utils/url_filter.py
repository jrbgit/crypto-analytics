#!/usr/bin/env python3
"""
URL filtering utility to identify and skip URLs that are unlikely to contain useful content
or are known to cause issues during scraping.
"""

import re
from urllib.parse import urlparse, parse_qs
from typing import Tuple, Optional

class URLFilter:
    """Filters URLs to avoid scraping problematic or non-content URLs"""
    
    # File extensions to skip
    SKIP_EXTENSIONS = {
        # Archives
        '.zip', '.tar', '.tar.gz', '.tgz', '.rar', '.7z', '.bz2', '.xz',
        # Executables
        '.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm', '.appimage',
        # Media files
        '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac', '.jpg', '.jpeg', '.png', 
        '.gif', '.svg', '.ico', '.webp', '.tiff', '.bmp',
        # Documents (that are better handled specifically)
        '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',
        # Other binary formats
        '.bin', '.img', '.iso', '.torrent'
    }
    
    # URL patterns that indicate non-content pages
    SKIP_PATTERNS = [
        # CDN and protection services
        r'/cdn-cgi/',
        r'cloudflare',
        r'/email-protection',
        
        # Common non-content directories
        r'/admin/',
        r'/wp-admin/',
        r'/wp-content/uploads/',
        r'/assets/',
        r'/static/',
        r'/css/',
        r'/js/',
        r'/images/',
        r'/img/',
        r'/fonts/',
        
        # API endpoints
        r'/api/',
        r'/v\d+/',
        r'\.json$',
        r'\.xml$',
        r'\.rss$',
        
        # Login/account pages
        r'/login',
        r'/signup',
        r'/register',
        r'/account',
        r'/profile',
        r'/dashboard',
        
        # Commercial/tracking
        r'/affiliate',
        r'/tracking',
        r'/analytics',
        r'utm_',
        r'/ads/',
        
        # Development/testing
        r'/test/',
        r'/dev/',
        r'/staging/',
        r'/debug/',
        
        # Fragment identifiers alone (these often don't change content)
        r'^[^#]*#[^/]*$'
    ]
    
    # Domain patterns that indicate problematic sites
    PROBLEMATIC_DOMAINS = [
        # Domain parking/for sale
        r'domains\.atom\.com',
        r'sedo\.com',
        r'underdeveloped\.com',
        r'parked\.com',
        r'bodis\.com',
        
        # CDNs and services (not primary content)
        r'amazonaws\.com',
        r'cloudfront\.net',
        r'jsdelivr\.net',
        r'unpkg\.com',
        
        # Social media (handled separately)
        r'facebook\.com',
        r'twitter\.com',
        r'instagram\.com',
        r'linkedin\.com',
        
        # File hosting without direct content
        r'drive\.google\.com',
        r'dropbox\.com',
        r'onedrive\.com'
    ]
    
    # Indicators of domain-for-sale or parked domains
    DOMAIN_SALE_INDICATORS = [
        'this domain is for sale',
        'domain for sale',
        'buy this domain',
        'domain parking',
        'coming soon',
        'under construction',
        'parked free',
        'expired domain',
        'premium domain'
    ]
    
    def __init__(self):
        self.skip_patterns_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.SKIP_PATTERNS]
        self.domain_patterns_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.PROBLEMATIC_DOMAINS]
    
    def should_skip_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Determine if a URL should be skipped during scraping.
        
        Args:
            url: The URL to check
            
        Returns:
            Tuple of (should_skip: bool, reason: str)
        """
        if not url or not url.strip():
            return True, "Empty URL"
        
        try:
            parsed = urlparse(url.strip())
        except Exception:
            return True, "Invalid URL format"
        
        # Check file extension
        skip_reason = self._check_file_extension(parsed.path)
        if skip_reason:
            return True, skip_reason
        
        # Check problematic domain patterns
        skip_reason = self._check_domain_patterns(parsed.netloc)
        if skip_reason:
            return True, skip_reason
        
        # Check URL patterns
        skip_reason = self._check_url_patterns(url)
        if skip_reason:
            return True, skip_reason
        
        # Check query parameters for tracking/redirects
        skip_reason = self._check_query_parameters(parsed.query)
        if skip_reason:
            return True, skip_reason
        
        return False, None
    
    def _check_file_extension(self, path: str) -> Optional[str]:
        """Check if the path ends with a problematic file extension"""
        path_lower = path.lower()
        for ext in self.SKIP_EXTENSIONS:
            if path_lower.endswith(ext):
                return f"File extension {ext} not suitable for content analysis"
        return None
    
    def _check_domain_patterns(self, netloc: str) -> Optional[str]:
        """Check if the domain matches problematic patterns"""
        for pattern in self.domain_patterns_compiled:
            if pattern.search(netloc):
                return f"Problematic domain pattern: {netloc}"
        return None
    
    def _check_url_patterns(self, url: str) -> Optional[str]:
        """Check if the URL matches skip patterns"""
        for pattern in self.skip_patterns_compiled:
            if pattern.search(url):
                return f"URL pattern indicates non-content: {pattern.pattern}"
        return None
    
    def _check_query_parameters(self, query: str) -> Optional[str]:
        """Check query parameters for tracking/redirect indicators"""
        if not query:
            return None
        
        # Parse query parameters
        try:
            params = parse_qs(query)
        except Exception:
            return None
        
        # Check for common tracking parameters
        tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'fbclid', 'gclid', 'ref', 'referrer'}
        param_keys = set(params.keys())
        
        if param_keys & tracking_params:
            return "URL contains tracking parameters"
        
        return None
    
    def is_likely_parked_domain(self, content: str) -> bool:
        """
        Check if page content indicates a parked or for-sale domain
        
        Args:
            content: Page content to analyze
            
        Returns:
            True if content indicates parked/for-sale domain
        """
        if not content:
            return False
        
        content_lower = content.lower()
        
        # Check for domain sale indicators
        for indicator in self.DOMAIN_SALE_INDICATORS:
            if indicator in content_lower:
                return True
        
        # Check content length - parked domains often have minimal content
        if len(content.strip()) < 100:
            # Look for very short content with domain-related keywords
            if any(phrase in content_lower for phrase in ['domain for', 'buy domain', 'domain sale', 'domain parking']):
                return True
        
        return False
    
    def get_clean_url(self, url: str) -> str:
        """
        Clean URL by removing tracking parameters and fragments
        
        Args:
            url: Original URL
            
        Returns:
            Cleaned URL
        """
        try:
            parsed = urlparse(url)
            
            # Remove fragment
            parsed = parsed._replace(fragment='')
            
            # Remove tracking parameters
            if parsed.query:
                params = parse_qs(parsed.query)
                tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'fbclid', 'gclid'}
                clean_params = {k: v for k, v in params.items() if k not in tracking_params}
                
                # Rebuild query string
                if clean_params:
                    import urllib.parse
                    query_parts = []
                    for key, values in clean_params.items():
                        for value in values:
                            query_parts.append(f"{key}={urllib.parse.quote_plus(str(value))}")
                    parsed = parsed._replace(query='&'.join(query_parts))
                else:
                    parsed = parsed._replace(query='')
            
            return parsed.geturl()
        except Exception:
            return url  # Return original if parsing fails


# Global instance for easy importing
url_filter = URLFilter()