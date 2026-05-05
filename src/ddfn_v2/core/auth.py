"""
Basic API key authentication for DDFN services.
"""
import os
import secrets
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

# API key header name
API_KEY_NAME = "X-API-Key"

# Security scheme
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Load API key from environment or generate a secure one
def get_api_key() -> str:
    """Get or generate the API key."""
    key = os.environ.get("DDFN_API_KEY")
    if not key:
        # Generate a secure key if not set (log warning)
        key = secrets.token_urlsafe(32)
        import logging
        logging.getLogger("auth").warning("DDFN_API_KEY not set. A temporary key was generated. Set DDFN_API_KEY to suppress this warning.")
    return key

API_KEY = get_api_key()

async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify the API key from the request header.
    Raises HTTPException if invalid.
    """
    # Read the current API key from environment (allows dynamic configuration)
    current_api_key = os.environ.get("DDFN_API_KEY", API_KEY)
    
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key header missing",
            headers={"WWW-Authenticate": f"Header {API_KEY_NAME}"},
        )
    
    if api_key != current_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    
    return api_key

# Optional: Allow unauthenticated access for health checks
def optional_auth(api_key: str = Security(api_key_header)) -> bool:
    """
    Optionally verify API key. Returns True if valid or no key provided.
    Used for public endpoints like health checks.
    """
    if api_key is None:
        return False
    return api_key == API_KEY
