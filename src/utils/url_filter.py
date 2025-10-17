#!/usr/bin/env python3
"""
URL filtering utility to identify and skip URLs that are unlikely to contain useful content
or are known to cause issues during scraping.
"""

import re
from urllib.parse import urlparse, parse_qs
from typing import Tuple, Optional, Dict, Any

class URLFilter:
    """Filters URLs to avoid scraping problematic or non-content URLs"""
    
    # File extensions to skip - non-LLM-analyzable files
    SKIP_EXTENSIONS = {
        # Archives
        '.zip', '.tar', '.tar.gz', '.tgz', '.rar', '.7z', '.bz2', '.xz', '.gz',
        # Executables and installers
        '.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm', '.appimage', '.run',
        '.bat', '.sh', '.command', '.scr', '.com',
        # Mobile apps
        '.apk', '.ipa', '.aab', '.xap',
        # Media files
        '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac', '.jpg', '.jpeg', '.png', 
        '.gif', '.svg', '.ico', '.webp', '.tiff', '.bmp', '.mkv', '.flv', '.webm',
        '.ogg', '.m4a', '.aac', '.wma', '.m4v', '.wmv', '.3gp',
        # Documents (that are better handled specifically)
        '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.odt', '.ods', '.odp',
        # Development files
        '.jar', '.war', '.ear', '.class', '.so', '.dll', '.dylib', '.a', '.lib',
        '.obj', '.o', '.pyc', '.pyo', '.cache',
        # Database files
        '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb',
        # Configuration/data files that aren't readable
        '.dat', '.log', '.tmp', '.temp', '.bak', '.old', '.orig',
        # Other binary formats
        '.bin', '.img', '.iso', '.torrent', '.cab', '.msp', '.patch'
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
        
        # API endpoints and feeds (be more specific)
        r'/api/',
        r'/v\d+/',
        r'/api/.*\.json$',  # API JSON endpoints
        r'/feed\.xml$',     # RSS/XML feeds (exact match)
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
        
        # Social media (these have dedicated scrapers, so don't skip)
        r'facebook\.com',
        r'twitter\.com',
        r'instagram\.com',
        r'linkedin\.com',
        
        # File hosting without direct content (Note: Google Drive handled specially for PDFs)
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
        'premium domain',
        'domain expired',
        'renew your domain',
        'click here to renew',
        'buy now',
        'make an offer',
        'contact owner',
        'inquire about this domain',
        'domain auction',
        'this domain may be for sale',
        'registrar suspension',
        'temporary landing page',
        'placeholder page',
        'default page',
        'website coming soon',
        'site under maintenance',
        'maintenance mode'
    ]
    
    # Known parking service providers
    PARKING_SERVICE_INDICATORS = [
        'godaddy',
        'sedo',
        'namecheap',
        'domain.com',
        'park by',
        'courtesy of',
        'powered by',
        'parked by',
        'hosted by',
        'registrar',
        'underdeveloped'
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
        
        # IMPORTANT: Never filter PDF files - they are valuable whitepaper content
        # regardless of what directory they're in
        if parsed.path.lower().endswith('.pdf'):
            return False, None
        
        # IMPORTANT: Allow Google Drive file links - common for whitepapers
        if 'drive.google.com' in parsed.netloc and '/file/d/' in parsed.path:
            return False, None
        
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
    
    def is_likely_parked_domain(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        Check if page content indicates a parked or for-sale domain
        
        Args:
            content: Page content to analyze
            
        Returns:
            Tuple of (is_parked: bool, parking_service: Optional[str])
        """
        if not content:
            return False, None
        
        content_lower = content.lower()
        
        # Check for domain sale indicators
        parked_score = 0
        detected_service = None
        
        for indicator in self.DOMAIN_SALE_INDICATORS:
            if indicator in content_lower:
                parked_score += 2
                
        # Check for parking service providers
        for service in self.PARKING_SERVICE_INDICATORS:
            if service in content_lower:
                parked_score += 3
                if not detected_service:  # Store first detected service
                    detected_service = service.title()
        
        # Content length analysis with more nuance
        content_length = len(content.strip())
        word_count = len(content.split())
        
        # Very minimal content is suspicious
        if content_length < 200 and word_count < 50:
            parked_score += 1
            
            # Look for specific short content patterns
            short_domain_phrases = [
                'domain for', 'buy domain', 'domain sale', 'domain parking',
                'contact us', 'make offer', 'inquire', 'coming soon'
            ]
            
            if any(phrase in content_lower for phrase in short_domain_phrases):
                parked_score += 2
        
        # Check for repetitive or templated content patterns
        if self._has_templated_content_pattern(content_lower):
            parked_score += 1
        
        # Check for absence of substantial content
        if not self._has_substantial_content(content_lower):
            parked_score += 1
        
        # Threshold for parking detection
        is_parked = parked_score >= 3
        
        return is_parked, detected_service
    
    def _has_templated_content_pattern(self, content_lower: str) -> bool:
        """Check if content follows common parking page templates."""
        template_patterns = [
            'privacy policy',
            'terms and conditions', 
            'copyright',
            'all rights reserved',
            'disclaimer'
        ]
        
        # If content is short but has multiple template elements, likely parked
        template_count = sum(1 for pattern in template_patterns if pattern in content_lower)
        return len(content_lower) < 1000 and template_count >= 2
    
    def _has_substantial_content(self, content_lower: str) -> bool:
        """Check if content has substantial, unique information."""
        # Look for indicators of real content
        substantial_indicators = [
            'about us',
            'our mission',
            'technology',
            'blockchain',
            'cryptocurrency',
            'token',
            'whitepaper',
            'roadmap',
            'team',
            'partnership',
            'documentation',
            'api',
            'tutorial',
            'guide'
        ]
        
        return any(indicator in content_lower for indicator in substantial_indicators)
    
    def assess_content_quality(self, content: str, title: str = '') -> Dict[str, Any]:
        """
        Assess the quality and type of content for minimal content handling.
        
        Args:
            content: Page content to assess
            title: Page title (if available)
            
        Returns:
            Dict with quality assessment information
        """
        if not content:
            return {
                'quality_score': 0,
                'content_type': 'empty',
                'issues': ['no_content'],
                'word_count': 0,
                'is_dynamic': False,
                'is_blocked': False
            }
        
        content_lower = content.lower()
        word_count = len(content.split())
        char_count = len(content.strip())
        
        quality_score = 5  # Start with neutral score
        issues = []
        content_type = 'unknown'
        
        # Assess content length
        if word_count < 20:
            quality_score -= 3
            issues.append('very_minimal_content')
        elif word_count < 50:
            quality_score -= 2
            issues.append('minimal_content')
        elif word_count < 100:
            quality_score -= 1
            issues.append('limited_content')
        
        # Check for dynamic content indicators
        dynamic_indicators = [
            'javascript is required',
            'enable javascript',
            'please enable javascript',
            'this site requires javascript',
            'loading...',
            'please wait',
            'redirecting',
            'if you are not redirected'
        ]
        
        is_dynamic = any(indicator in content_lower for indicator in dynamic_indicators)
        if is_dynamic:
            quality_score -= 2
            issues.append('dynamic_content')
            content_type = 'dynamic'
        
        # Check for access restrictions
        access_indicators = [
            'access denied',
            'unauthorized',
            'forbidden',
            'login required',
            'please log in',
            'subscription required',
            'premium content',
            'members only'
        ]
        
        is_blocked = any(indicator in content_lower for indicator in access_indicators)
        if is_blocked:
            quality_score -= 2
            issues.append('access_restricted')
            content_type = 'restricted'
        
        # Check for error pages
        error_indicators = [
            '404',
            'page not found',
            'not found',
            'error',
            'something went wrong',
            'oops'
        ]
        
        is_error = any(indicator in content_lower for indicator in error_indicators)
        if is_error:
            quality_score -= 3
            issues.append('error_page')
            content_type = 'error'
        
        # Check for substantial content
        if self._has_substantial_content(content_lower):
            quality_score += 2
            content_type = 'substantial' if content_type == 'unknown' else content_type
        
        # Check for parked domain
        is_parked, parking_service = self.is_likely_parked_domain(content)
        if is_parked:
            quality_score -= 4
            issues.append('parked_domain')
            content_type = 'parked'
        
        # Ensure score is within bounds
        quality_score = max(0, min(10, quality_score))
        
        return {
            'quality_score': quality_score,
            'content_type': content_type,
            'issues': issues,
            'word_count': word_count,
            'char_count': char_count,
            'is_dynamic': is_dynamic,
            'is_blocked': is_blocked,
            'is_error': is_error,
            'is_parked': is_parked,
            'parking_service': parking_service if is_parked else None
        }
    
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
    
    def extract_youtube_channel_id(self, youtube_url: str) -> Optional[str]:
        """
        Extract YouTube channel ID from various URL formats for validation.
        
        Args:
            youtube_url: YouTube channel URL
            
        Returns:
            Channel ID or None if extraction fails
        """
        try:
            parsed = urlparse(youtube_url)
            
            # Only process YouTube URLs
            if 'youtube.com' not in parsed.netloc and 'youtu.be' not in parsed.netloc:
                return None
            
            # Handle different YouTube URL formats:
            # https://youtube.com/channel/UCxxxxx
            # https://youtube.com/@username
            # https://youtube.com/c/channelname
            # https://youtube.com/user/username
            
            if '/channel/' in parsed.path:
                # Direct channel ID URL
                channel_id = parsed.path.split('/channel/')[1].split('/')[0]
                # Validate channel ID format (should start with UC and be 24 characters)
                if len(channel_id) == 24 and channel_id.startswith('UC'):
                    return channel_id
            elif parsed.path.startswith('/@'):
                # Handle @username format - return username without @
                username = parsed.path[2:].split('/')[0]
                return f"@{username}" if username else None
            elif '/c/' in parsed.path:
                # Custom channel URL
                channel_name = parsed.path.split('/c/')[1].split('/')[0]
                return f"c/{channel_name}" if channel_name else None
            elif '/user/' in parsed.path:
                # Legacy user URL
                username = parsed.path.split('/user/')[1].split('/')[0]
                return f"user/{username}" if username else None
            
            return None
            
        except Exception:
            return None
    
    def is_valid_youtube_channel_url(self, url: str) -> bool:
        """
        Check if URL is a valid YouTube channel URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if valid YouTube channel URL
        """
        return self.extract_youtube_channel_id(url) is not None


# Global instance for easy importing
url_filter = URLFilter()