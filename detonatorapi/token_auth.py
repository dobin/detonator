from dataclasses import dataclass
from typing import Optional
from fastapi import Request, HTTPException
import base64

from .settings import AUTH_PASSWORD


def check_password_auth(request: Request) -> bool:
    """Check if request is authenticated via password"""
    if not AUTH_PASSWORD or AUTH_PASSWORD == "":
        # No password configured - allow all requests
        return True
    
    # Check for X-Auth-Password header
    auth_password = request.headers.get("X-Auth-Password", "")
    if auth_password == AUTH_PASSWORD:
        return True
    
    # Check for Authorization header (Basic or Bearer)
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        # Support "Bearer <password>" format
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == AUTH_PASSWORD:
                return True
        # Support "Basic <base64>" format for curl compatibility
        elif auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                # Basic auth format is "username:password", we only care about password
                if ':' in decoded:
                    _, password = decoded.split(':', 1)
                    if password == AUTH_PASSWORD:
                        return True
                # Or just the password alone
                elif decoded == AUTH_PASSWORD:
                    return True
            except:
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
