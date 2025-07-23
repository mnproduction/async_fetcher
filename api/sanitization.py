"""
Input Sanitization Module for Async HTML Fetcher Service

This module provides comprehensive input sanitization functions to ensure
data quality, security, and consistency across the application.

Features:
- HTML content sanitization and escaping
- URL normalization and validation
- String sanitization and length limits
- Character set validation and filtering
- Security-focused input cleaning

Author: Async HTML Fetcher Service
Version: 1.0.0
"""

import html
import re
import unicodedata
from typing import List
from urllib.parse import urlparse, urlunparse


# =============================================================================
# CHARACTER SET VALIDATION
# =============================================================================

def is_safe_character(char: str) -> bool:
    """
    Check if a character is safe for general string input.
    
    Args:
        char: Single character to validate
        
    Returns:
        bool: True if character is safe, False otherwise
    """
    # Allow alphanumeric, common punctuation, and whitespace
    safe_chars = set(
        'abcdefghijklmnopqrstuvwxyz'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        '0123456789'
        ' .,!?;:()[]{}"\'-_/@#$%^&*+=|\\~`'
    )
    return char in safe_chars or unicodedata.category(char).startswith('L')


def sanitize_string(value: str, max_length: int = 1000, allow_html: bool = False) -> str:
    """
    Sanitize a string input with comprehensive cleaning.
    
    Args:
        value: Raw string input
        max_length: Maximum allowed length
        allow_html: Whether to allow HTML content
        
    Returns:
        str: Sanitized string
        
    Raises:
        ValueError: If string is too long or contains unsafe content
    """
    if not isinstance(value, str):
        raise ValueError(f'Expected string, got {type(value).__name__}')
    
    # Trim whitespace
    value = value.strip()
    
    # Check length
    if len(value) > max_length:
        raise ValueError(f'String too long (max {max_length} characters): {value[:50]}...')
    
    # Handle empty strings
    if not value:
        return value
    
    if allow_html:
        # For HTML content, only escape dangerous characters
        value = html.escape(value, quote=True)
    else:
        # For regular strings, filter unsafe characters
        safe_chars = []
        for char in value:
            if is_safe_character(char):
                safe_chars.append(char)
            else:
                # Replace unsafe characters with space
                safe_chars.append(' ')
        
        value = ''.join(safe_chars)
        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value).strip()
    
    return value


# =============================================================================
# URL SANITIZATION
# =============================================================================

def sanitize_url(url: str, max_length: int = 2000) -> str:
    """
    Comprehensive URL sanitization and normalization.
    
    Args:
        url: Raw URL string
        max_length: Maximum URL length
        
    Returns:
        str: Sanitized and normalized URL
        
    Raises:
        ValueError: If URL is invalid or too long
    """
    if not isinstance(url, str):
        raise ValueError(f'Expected string, got {type(url).__name__}')
    
    # Trim whitespace
    url = url.strip()
    
    # Check length
    if len(url) > max_length:
        raise ValueError(f'URL too long (max {max_length} characters): {url[:50]}...')
    
    # Handle empty URLs
    if not url:
        raise ValueError('URL cannot be empty')
    
    # Add scheme if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Parse and validate URL
    try:
        parsed = urlparse(url)
        
        # Validate required components
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f'Invalid URL format: {url}')
        
        # Only allow HTTP/HTTPS schemes
        if parsed.scheme not in ('http', 'https'):
            raise ValueError(f'Unsupported URL scheme: {parsed.scheme}')
        
        # Security checks
        if 'javascript:' in url.lower() or 'data:' in url.lower():
            raise ValueError(f'Potentially dangerous URL scheme: {url}')
        
        # Normalize URL
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),  # Normalize hostname
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        return normalized
        
    except Exception as e:
        raise ValueError(f'Invalid URL {url}: {str(e)}')


def sanitize_proxy_url(proxy: str, max_length: int = 500) -> str:
    """
    Sanitize and validate proxy URL format.
    
    Args:
        proxy: Raw proxy URL string
        max_length: Maximum proxy URL length
        
    Returns:
        str: Sanitized proxy URL
        
    Raises:
        ValueError: If proxy URL is invalid
    """
    if not isinstance(proxy, str):
        raise ValueError(f'Expected string, got {type(proxy).__name__}')
    
    # Trim whitespace
    proxy = proxy.strip()
    
    # Check length
    if len(proxy) > max_length:
        raise ValueError(f'Proxy URL too long (max {max_length} characters): {proxy[:50]}...')
    
    # Handle empty proxy
    if not proxy:
        raise ValueError('Proxy URL cannot be empty')
    
    # Validate proxy format with regex
    proxy_pattern = r'^(http|https|socks4|socks5)://([\w\-\.]+)(:\d+)?(/.*)?$'
    if not re.match(proxy_pattern, proxy):
        raise ValueError(f'Invalid proxy URL format: {proxy}')
    
    # Security checks
    if '..' in proxy or '//' in proxy.split('://', 1)[1]:
        raise ValueError(f'Potentially malicious proxy URL: {proxy}')
    
    # Block dangerous schemes
    if 'javascript:' in proxy.lower() or 'data:' in proxy.lower():
        raise ValueError(f'Potentially dangerous proxy URL scheme: {proxy}')
    
    return proxy


# =============================================================================
# HTML CONTENT SANITIZATION
# =============================================================================

def sanitize_html_content(html_content: str, max_length: int = 10_000_000) -> str:
    """
    Sanitize HTML content for safe storage and display.
    
    Args:
        html_content: Raw HTML content
        max_length: Maximum content length (10MB default)
        
    Returns:
        str: Sanitized HTML content
        
    Raises:
        ValueError: If content is too long or invalid
    """
    if not isinstance(html_content, str):
        raise ValueError(f'Expected string, got {type(html_content).__name__}')
    
    # Check length
    if len(html_content) > max_length:
        raise ValueError(f'HTML content too long (max {max_length} characters): {html_content[:100]}...')
    
    # Handle empty content
    if not html_content:
        return html_content
    
    # Basic HTML sanitization
    # Remove potentially dangerous script tags and attributes
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'<iframe[^>]*>.*?</iframe>',  # Iframe tags
        r'<object[^>]*>.*?</object>',  # Object tags
        r'<embed[^>]*>',               # Embed tags
        r'javascript:',                # JavaScript protocol
        r'data:',                      # Data protocol
        r'on\w+\s*=',                  # Event handlers
    ]
    
    sanitized = html_content
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    
    # Normalize whitespace in HTML
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    return sanitized.strip()


# =============================================================================
# ERROR MESSAGE SANITIZATION
# =============================================================================

def sanitize_error_message(error_msg: str, max_length: int = 1000) -> str:
    """
    Sanitize error messages for safe logging and display.
    
    Args:
        error_msg: Raw error message
        max_length: Maximum message length
        
    Returns:
        str: Sanitized error message
        
    Raises:
        ValueError: If message is too long
    """
    if not isinstance(error_msg, str):
        raise ValueError(f'Expected string, got {type(error_msg).__name__}')
    
    # Trim whitespace
    error_msg = error_msg.strip()
    
    # Check length
    if len(error_msg) > max_length:
        raise ValueError(f'Error message too long (max {max_length} characters): {error_msg[:50]}...')
    
    # Handle empty messages
    if not error_msg:
        raise ValueError('Error message cannot be empty')
    
    # Sanitize as regular string (no HTML allowed)
    sanitized = sanitize_string(error_msg, max_length, allow_html=False)
    
    # Remove any remaining potentially dangerous content
    dangerous_patterns = [
        r'javascript:',                # JavaScript protocol
        r'data:',                      # Data protocol
        r'<script[^>]*>',              # Script tags
        r'<iframe[^>]*>',              # Iframe tags
    ]
    
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '[REMOVED]', sanitized, flags=re.IGNORECASE)
    
    return sanitized


# =============================================================================
# LIST SANITIZATION
# =============================================================================

def sanitize_url_list(urls: List[str], max_urls: int = 1000, max_length: int = 2000) -> List[str]:
    """
    Sanitize a list of URLs with deduplication.
    
    Args:
        urls: List of raw URL strings
        max_urls: Maximum number of URLs allowed
        max_length: Maximum length per URL
        
    Returns:
        List[str]: List of sanitized URLs
        
    Raises:
        ValueError: If list is too long or contains invalid URLs
    """
    if not isinstance(urls, list):
        raise ValueError(f'Expected list, got {type(urls).__name__}')
    
    # Check list length
    if len(urls) > max_urls:
        raise ValueError(f'Too many URLs (max {max_urls}): {len(urls)}')
    
    # Sanitize and deduplicate URLs
    sanitized_urls = []
    seen_urls = set()
    
    for url in urls:
        # Sanitize individual URL
        sanitized_url = sanitize_url(url, max_length)
        
        # Check for duplicates
        if sanitized_url in seen_urls:
            raise ValueError(f'Duplicate URL found: {url}')
        
        seen_urls.add(sanitized_url)
        sanitized_urls.append(sanitized_url)
    
    return sanitized_urls


def sanitize_proxy_list(proxies: List[str], max_proxies: int = 50, max_length: int = 500) -> List[str]:
    """
    Sanitize a list of proxy URLs with deduplication.
    
    Args:
        proxies: List of raw proxy URL strings
        max_proxies: Maximum number of proxies allowed
        max_length: Maximum length per proxy URL
        
    Returns:
        List[str]: List of sanitized proxy URLs
        
    Raises:
        ValueError: If list is too long or contains invalid proxies
    """
    if not isinstance(proxies, list):
        raise ValueError(f'Expected list, got {type(proxies).__name__}')
    
    # Check list length
    if len(proxies) > max_proxies:
        raise ValueError(f'Too many proxies (max {max_proxies}): {len(proxies)}')
    
    # Sanitize and deduplicate proxies
    sanitized_proxies = []
    seen_proxies = set()
    
    for proxy in proxies:
        # Sanitize individual proxy
        sanitized_proxy = sanitize_proxy_url(proxy, max_length)
        
        # Check for duplicates
        if sanitized_proxy in seen_proxies:
            raise ValueError(f'Duplicate proxy URL found: {proxy}')
        
        seen_proxies.add(sanitized_proxy)
        sanitized_proxies.append(sanitized_proxy)
    
    return sanitized_proxies


# =============================================================================
# UUID VALIDATION
# =============================================================================

def sanitize_uuid(uuid_str: str) -> str:
    """
    Validate and sanitize UUID format.
    
    Args:
        uuid_str: Raw UUID string
        
    Returns:
        str: Validated UUID string
        
    Raises:
        ValueError: If UUID format is invalid
    """
    if not isinstance(uuid_str, str):
        raise ValueError(f'Expected string, got {type(uuid_str).__name__}')
    
    # Trim whitespace
    uuid_str = uuid_str.strip()
    
    # Check length (UUID should be exactly 36 characters)
    if len(uuid_str) != 36:
        raise ValueError(f'Invalid UUID length: {len(uuid_str)} (expected 36)')
    
    # Validate UUID format
    try:
        import uuid
        uuid.UUID(uuid_str)
        return uuid_str
    except ValueError:
        raise ValueError(f'Invalid UUID format: {uuid_str}')


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'sanitize_string',
    'sanitize_url',
    'sanitize_proxy_url',
    'sanitize_html_content',
    'sanitize_error_message',
    'sanitize_url_list',
    'sanitize_proxy_list',
    'sanitize_uuid',
    'is_safe_character'
] 