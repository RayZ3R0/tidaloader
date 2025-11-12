"""
Simple but secure authentication using HTTP Basic Auth
"""
import os
import secrets
import base64
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from dotenv import load_dotenv

load_dotenv()

# Load credentials from environment
AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")

if not AUTH_USERNAME or not AUTH_PASSWORD:
    raise RuntimeError(
        "AUTH_USERNAME and AUTH_PASSWORD must be set in .env file!\n"
        "Example:\n"
        "AUTH_USERNAME=admin\n"
        "AUTH_PASSWORD=your-secure-password"
    )

def verify_credentials(authorization: Optional[str] = Header(None)) -> str:
    """
    Verify HTTP Basic Auth credentials from Authorization header.
    Uses constant-time comparison to prevent timing attacks.
    Returns username if valid, raises HTTPException if not.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    # Check if it's Basic auth
    if not authorization.startswith("Basic "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
        )

    # Decode the base64 credentials
    try:
        encoded_credentials = authorization.replace("Basic ", "")
        decoded = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials format",
        )

    # Constant-time comparison to prevent timing attacks
    is_correct_username = secrets.compare_digest(
        username.encode("utf8"),
        AUTH_USERNAME.encode("utf8")
    )
    is_correct_password = secrets.compare_digest(
        password.encode("utf8"),
        AUTH_PASSWORD.encode("utf8")
    )

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return username

# Dependency for protected endpoints
def require_auth(username: str = Depends(verify_credentials)) -> str:
    """Dependency to require authentication on endpoints"""
    return username