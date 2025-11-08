"""
Simple but secure authentication using HTTP Basic Auth
"""
import os
import secrets
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv

load_dotenv()

security = HTTPBasic()

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

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """
    Verify HTTP Basic Auth credentials.
    Uses constant-time comparison to prevent timing attacks.
    Returns username if valid, raises HTTPException if not.
    """
    # Constant-time comparison to prevent timing attacks
    is_correct_username = secrets.compare_digest(
        credentials.username.encode("utf8"),
        AUTH_USERNAME.encode("utf8")
    )
    is_correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"),
        AUTH_PASSWORD.encode("utf8")
    )

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return credentials.username

# Dependency for protected endpoints
def require_auth(username: str = Depends(verify_credentials)) -> str:
    """Dependency to require authentication on endpoints"""
    return username