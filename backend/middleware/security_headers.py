"""
Advanced security headers middleware with CSP nonce generation.

Implements:
- Content Security Policy with per-request nonces
- COOP/COEP cross-origin isolation
- Strict transport security
- X-Content-Type-Options
- Frame-ancestors restrictions
- Permissions-Policy hardening
"""

import logging
import secrets
from typing import Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("TitleTrust-SecurityHeaders")


class CSPNonceGenerator:
    """Generate and track CSP nonces per request."""

    @staticmethod
    def generate_nonce(length: int = 32) -> str:
        """Generate cryptographically secure nonce."""
        return secrets.token_urlsafe(length)


class AdvancedSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add enterprise-grade security headers to all responses.

    Includes:
    - Content-Security-Policy with script nonces
    - Cross-Origin-Opener-Policy (COOP)
    - Cross-Origin-Embedder-Policy (COEP)
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Permissions-Policy
    """

    def __init__(self, app):
        super().__init__(app)
        self.is_production = False  # Set based on environment

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate per-request nonce for inline scripts/styles
        nonce = CSPNonceGenerator.generate_nonce()
        request.state.csp_nonce = nonce

        # Call the actual endpoint
        response = await call_next(request)

        # Add security headers
        self._add_csp_header(response, nonce)
        self._add_coop_coep_headers(response)
        self._add_hsts_header(response)
        self._add_content_type_options(response)
        self._add_frame_options(response)
        self._add_xss_protection(response)
        self._add_referrer_policy(response)
        self._add_permissions_policy(response)

        return response

    def _add_csp_header(self, response: Response, nonce: str) -> None:
        """Add Content-Security-Policy header with nonce."""
        csp_directives = [
            # Only allow scripts from same origin or with nonce
            f"script-src 'self' 'nonce-{nonce}'",
            # Styles from same origin or with nonce
            f"style-src 'self' 'nonce-{nonce}'",
            # Fonts from same origin and Google Fonts (common)
            "font-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com",
            # Images from same origin, data URIs, https
            "img-src 'self' data: https:",
            # Only same-origin forms
            "form-action 'self'",
            # Restrict frame origins to self
            "frame-ancestors 'self'",
            # No plugins
            "object-src 'none'",
            # Restrict base URL
            "base-uri 'self'",
            # Block all <object>, <embed>, <applet>
            "default-src 'self'",
            # Upgrade insecure requests in production
            "upgrade-insecure-requests",
            # Restrict frame loading
            "frame-src 'self'",
            # Only allow secure connections for nested browsing contexts
            "child-src 'self'",
            # Reporting endpoint (implement if needed)
            "report-uri /api/security/csp-report",
        ]

        csp_header = "; ".join(csp_directives)

        # Use report-only mode for rollout, strict mode in production
        if self.is_production:
            response.headers["Content-Security-Policy"] = csp_header
            logger.debug("Applied strict CSP policy")
        else:
            # Development: use report-only for testing without breaking things
            response.headers["Content-Security-Policy-Report-Only"] = csp_header
            logger.debug("Applied CSP report-only policy (development)")

    def _add_coop_coep_headers(self, response: Response) -> None:
        """Add COOP/COEP headers for cross-origin isolation."""
        # Cross-Origin-Opener-Policy: restricts window.open() relationships
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"

        # Cross-Origin-Embedder-Policy: requires CORS headers for embedded content
        response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"

        # Cross-Origin-Resource-Policy: restricts who can embed this resource
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        logger.debug("Applied COOP/COEP headers")

    def _add_hsts_header(self, response: Response) -> None:
        """Add HTTP Strict-Transport-Security header."""
        # 1 year max age, include subdomains, enable preload
        hsts = "max-age=31536000; includeSubDomains; preload"
        response.headers["Strict-Transport-Security"] = hsts
        logger.debug("Applied HSTS header")

    def _add_content_type_options(self, response: Response) -> None:
        """Prevent MIME sniffing."""
        response.headers["X-Content-Type-Options"] = "nosniff"

    def _add_frame_options(self, response: Response) -> None:
        """Restrict frame embedding."""
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

    def _add_xss_protection(self, response: Response) -> None:
        """Add XSS protection header (legacy but still useful)."""
        response.headers["X-XSS-Protection"] = "1; mode=block"

    def _add_referrer_policy(self, response: Response) -> None:
        """Control referrer information leakage."""
        # Only send referrer to same-origin requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    def _add_permissions_policy(self, response: Response) -> None:
        """Control browser features/APIs."""
        permissions = [
            # Disable camera/microphone by default
            'camera=()',
            'microphone=()',
            # Disable geolocation
            'geolocation=()',
            # Restrict payment request API
            'payment=()',
            # Restrict USB access
            'usb=()',
            # Disable FPS counter/performance observer
            'accelerometer=()',
            'ambient-light-sensor=()',
            'gyroscope=()',
            'magnetometer=()',
            # Disable fullscreen
            'fullscreen=()',
            # Restrict MIDI
            'midi=()',
            # Only allow VR in same-origin
            'xr-spatial-tracking=()',
        ]
        
        response.headers["Permissions-Policy"] = ", ".join(permissions)
        logger.debug("Applied Permissions-Policy header")


class CSPReportRouter:
    """Handle CSP violation reports for monitoring."""

    @staticmethod
    async def report_csp_violation(request: Request) -> Dict[str, Any]:
        """
        Handle CSP violation reports.

        CSP sends violation reports in format:
        {
            "csp-report": {
                "document-uri": "...",
                "violated-directive": "...",
                "original-policy": "...",
                "blocked-uri": "...",
                "source-file": "...",
                "line-number": ...,
                "status-code": ...
            }
        }
        """
        try:
            body = await request.json()
            report = body.get("csp-report", {})

            logger.warning(
                f"CSP Violation: {report.get('violated-directive')} "
                f"on {report.get('document-uri')} "
                f"blocked: {report.get('blocked-uri')} "
                f"from {report.get('source-file')}:{report.get('line-number')}"
            )

            # In production, send to security monitoring service
            # Examples: Sentry, Datadog, Splunk, etc.

            return {"status": "received"}

        except Exception as exc:
            logger.error(f"Error processing CSP report: {exc}")
            return {"status": "error"}
