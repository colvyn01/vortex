# MIT License
# Copyright (c) 2024 Vortex Contributors
# See LICENSE file for full license text.

"""
Security layer for Vortex file gateway.

This module provides security features for public network deployments:
- Rate limiting to prevent abuse
- Token-based authentication
- Self-signed certificate generation for HTTPS
- Security headers for HTTP responses

All features use Python standard library only (no external dependencies).
"""

import os
import secrets
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Rate Limiter


class _RateLimiter:
    """
    Thread-safe rate limiter using sliding window algorithm.

    Tracks requests per IP address and blocks IPs that exceed
    the configured threshold within the time window.
    """

    def __init__(self, threshold: int = 200, window_seconds: int = 60) -> None:
        """
        Initialize rate limiter.

        Args:
            threshold: Maximum requests allowed per IP within the window.
            window_seconds: Time window in seconds for rate calculation.
        """
        self.threshold = threshold
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def check(self, client_ip: str) -> bool:
        """
        Check if a request from this IP should be allowed.

        Args:
            client_ip: The client's IP address.

        Returns:
            True if request is allowed, False if rate limited.
        """
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds

        with self._lock:
            # Get existing requests for this IP
            if client_ip not in self._requests:
                self._requests[client_ip] = []

            # Remove old requests outside the window
            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if t > cutoff_time
            ]

            # Check if under threshold
            if len(self._requests[client_ip]) >= self.threshold:
                return False

            # Record this request
            self._requests[client_ip].append(current_time)
            return True

    def get_request_count(self, client_ip: str) -> int:
        """Get current request count for an IP (for logging)."""
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds

        with self._lock:
            if client_ip not in self._requests:
                return 0
            return len([t for t in self._requests[client_ip] if t > cutoff_time])


# Token Manager


class _TokenManager:
    """
    Manages authentication tokens with persistent storage.

    Tokens are stored in ~/.vortex/token.txt and persist across
    server restarts to maintain QR code compatibility.
    """

    def __init__(self, token_dir: Optional[Path] = None) -> None:
        """
        Initialize token manager.

        Args:
            token_dir: Directory for token storage. Defaults to ~/.vortex
        """
        if token_dir is None:
            token_dir = Path.home() / ".vortex"
        self.token_dir = token_dir
        self.token_file = token_dir / "token.txt"
        self._token: Optional[str] = None

    def load_or_generate(self) -> str:
        """
        Load existing token or generate a new one.

        Returns:
            The authentication token (16 hex characters).
        """
        if self._token is not None:
            return self._token

        # Try to load existing token
        try:
            if self.token_file.exists():
                token = self.token_file.read_text().strip()
                if len(token) >= 16:
                    self._token = token
                    return self._token
        except OSError:
            pass

        # Generate new token
        return self.regenerate()

    def regenerate(self) -> str:
        """
        Generate and save a new token.

        Returns:
            The new authentication token.
        """
        self._token = secrets.token_hex(8)  # 16 hex characters

        # Save to file
        try:
            self.token_dir.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(self._token)
        except OSError:
            pass  # Non-critical if we can't persist

        return self._token

    def validate(self, provided_token: Optional[str]) -> bool:
        """
        Validate a provided token against the stored token.

        Args:
            provided_token: Token to validate.

        Returns:
            True if token matches, False otherwise.
        """
        if self._token is None:
            self.load_or_generate()
        return secrets.compare_digest(provided_token or "", self._token or "")


# Certificate Manager


class _CertificateManager:
    """
    Manages self-signed certificates for HTTPS.

    Uses OpenSSL subprocess to generate certificates when not available.
    Falls back gracefully if OpenSSL is not installed.
    """

    def __init__(self, cert_dir: Optional[Path] = None) -> None:
        """
        Initialize certificate manager.

        Args:
            cert_dir: Directory for certificate storage. Defaults to ~/.vortex
        """
        if cert_dir is None:
            cert_dir = Path.home() / ".vortex"
        self.cert_dir = cert_dir
        self.cert_file = cert_dir / "certificate.pem"
        self.key_file = cert_dir / "private_key.pem"

    def get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """
        Get SSL context for HTTPS, generating certificate if needed.

        Returns:
            Configured SSLContext, or None if certificate generation fails.
        """
        # Generate certificate if it doesn't exist
        if not self.cert_file.exists() or not self.key_file.exists():
            if not self._generate_self_signed():
                return None

        # Create SSL context
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(self.cert_file), str(self.key_file))
            return context
        except ssl.SSLError:
            return None

    def _generate_self_signed(self) -> bool:
        """
        Generate a self-signed certificate using OpenSSL.

        Returns:
            True if generation succeeded, False otherwise.
        """
        try:
            self.cert_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False

        # Check if OpenSSL is available
        openssl_cmd = "openssl"
        if sys.platform == "win32":
            # Try common Windows OpenSSL locations
            possible_paths = [
                "openssl",
                r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
                r"C:\Program Files (x86)\OpenSSL-Win32\bin\openssl.exe",
                r"C:\OpenSSL-Win64\bin\openssl.exe",
            ]
            for path in possible_paths:
                try:
                    result = subprocess.run(
                        [path, "version"],
                        capture_output=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        openssl_cmd = path
                        break
                except (OSError, subprocess.TimeoutExpired):
                    continue
            else:
                return False
        else:
            # Unix: check if openssl is in PATH
            try:
                result = subprocess.run(
                    ["which", "openssl"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    return False
            except (OSError, subprocess.TimeoutExpired):
                return False

        # Generate self-signed certificate (valid for 365 days)
        try:
            result = subprocess.run(
                [
                    openssl_cmd,
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-keyout",
                    str(self.key_file),
                    "-out",
                    str(self.cert_file),
                    "-days",
                    "365",
                    "-nodes",
                    "-subj",
                    "/CN=localhost",
                ],
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


# Security Manager (Public API)


class SecurityManager:
    """
    Unified security manager for Vortex.

    Provides rate limiting, optional token authentication, and HTTPS support.
    This is the main public interface for security features.
    """

    def __init__(
        self,
        enable_auth: bool = False,
        rate_limit_threshold: int = 200,
        config_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize security manager.

        Args:
            enable_auth: Enable token-based authentication.
            rate_limit_threshold: Max requests per minute per IP.
            config_dir: Directory for tokens/certs. Defaults to ~/.vortex
        """
        if config_dir is None:
            config_dir = Path.home() / ".vortex"

        self._rate_limiter = _RateLimiter(threshold=rate_limit_threshold)
        self._token_manager = _TokenManager(config_dir) if enable_auth else None
        self._cert_manager = _CertificateManager(config_dir)
        self._enable_auth = enable_auth

    def validate_request(
        self, client_ip: str, provided_token: Optional[str] = None
    ) -> Tuple[bool, str, int]:
        """
        Validate an incoming request.

        Args:
            client_ip: Client's IP address.
            provided_token: Token from query string or header.

        Returns:
            Tuple of (allowed, error_message, status_code).
            If allowed is True, error_message is empty and status_code is 200.
        """
        # Check rate limit
        if not self._rate_limiter.check(client_ip):
            count = self._rate_limiter.get_request_count(client_ip)
            self._log_security_event("RATE", f"Blocked {client_ip} ({count} req/min)")
            return False, "Too many requests. Please slow down.", 429

        # Check authentication if enabled
        if self._enable_auth and self._token_manager:
            if not self._token_manager.validate(provided_token):
                self._log_security_event("AUTH", f"Invalid token from {client_ip}")
                return False, "Invalid or missing access token.", 403

        return True, "", 200

    def get_security_headers(self, is_https: bool = False) -> Dict[str, str]:
        """
        Get security headers for HTTP responses.

        Args:
            is_https: Whether the connection is HTTPS.

        Returns:
            Dictionary of header names to values.
        """
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "no-referrer",
            # Strict CSP: Allow inline scripts, jsdelivr CDN for HEIC converter
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
        }
        # Note: No HSTS - inappropriate for self-signed certs
        return headers

    def get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """
        Get SSL context for HTTPS.

        Returns:
            Configured SSLContext, or None if not available.
        """
        return self._cert_manager.get_ssl_context()

    def get_token(self) -> Optional[str]:
        """
        Get the current authentication token.

        Returns:
            The token if authentication is enabled, None otherwise.
        """
        if self._token_manager:
            return self._token_manager.load_or_generate()
        return None

    def regenerate_token(self) -> Optional[str]:
        """
        Regenerate the authentication token.

        Returns:
            The new token if authentication is enabled, None otherwise.
        """
        if self._token_manager:
            return self._token_manager.regenerate()
        return None

    @staticmethod
    def _log_security_event(event_type: str, message: str) -> None:
        """Log a security event to stderr."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{event_type}] {message}", file=sys.stderr)
