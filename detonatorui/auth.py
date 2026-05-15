from flask import session

from detonatorapi.settings import AUTH_PASSWORD


def is_auth_enabled() -> bool:
    """Check if authentication is enabled (AUTH_PASSWORD is configured)."""
    if AUTH_PASSWORD and AUTH_PASSWORD != "":
        return True
    else:
        return False


def api_headers() -> dict:
    """Return headers for proxying requests to the FastAPI backend.

    Only includes X-Auth-Password if the user session is authenticated.
    Uses the server-side AUTH_PASSWORD, so the browser never sees it.
    """
    headers = {}
    if AUTH_PASSWORD and session.get("authenticated"):
        headers["X-Auth-Password"] = AUTH_PASSWORD
    return headers