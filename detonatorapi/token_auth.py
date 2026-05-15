"""
Authentication module for Detonator API.

Two authentication paths are supported:

1. Browser → Flask (session cookie) → FastAPI (X-Auth-Password header)
   - Flask validates the user's password, sets a signed session cookie.
   - Flask proxies API calls to FastAPI, injecting X-Auth-Password with the
     server-side AUTH_PASSWORD value.
   - The browser never sees or stores the raw password.

2. curl / direct API → FastAPI (X-Auth-Password or Authorization header)
   - The user provides the password directly via X-Auth-Password header,
     Authorization: Bearer <password>, or Authorization: Basic <base64>.
   - Useful for scripting and direct API access.

When AUTH_PASSWORD is empty/None, authentication is disabled and all
requests are treated as admin.
"""

from dataclasses import dataclass
from typing import Optional
from fastapi import Request, HTTPException
import base64
import hmac

from .settings import AUTH_PASSWORD


def check_password_auth(request: Request) -> bool:
    """Check if request is authenticated via password"""
    if not AUTH_PASSWORD or AUTH_PASSWORD == "":
        # No password configured - allow all requests
        return True
    
    # Check for X-Auth-Password header
    # As used by DetonatorUi
    auth_password = request.headers.get("X-Auth-Password", "")
    if hmac.compare_digest(auth_password, AUTH_PASSWORD):
        return True
    
    # Check for Authorization header (Basic or Bearer)
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        # Support "Bearer <password>" format
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if hmac.compare_digest(token, AUTH_PASSWORD):
                return True
        # Support "Basic <base64>" format for curl compatibility
        elif auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                # Basic auth format is "username:password", we only care about password
                if ':' in decoded:
                    _, password = decoded.split(':', 1)
                    if hmac.compare_digest(password, AUTH_PASSWORD):
                        return True
                # Or just the password alone
                elif hmac.compare_digest(decoded, AUTH_PASSWORD):
                    return True
            except (ValueError, UnicodeDecodeError):
                pass
    
    return False


async def require_auth(request: Request) -> None:
    """FastAPI dependency that requires authentication for write operations"""
    if not check_password_auth(request):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide password via X-Auth-Password header or Authorization header."
        )


def get_user_from_request(request: Request) -> str:
    """Get user status from request: 'admin' if authenticated, 'guest' otherwise"""
    if check_password_auth(request):
        return "admin"
    return "guest"
