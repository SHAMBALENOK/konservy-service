"""
Authentication router with JWT token endpoints.
"""

from datetime import timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.schemas.common import LoginRequest, TokenResponse

logger = structlog.get_logger(__name__)

router = APIRouter()


# Mock user database for demonstration
# In production, this would be a proper user repository
_mock_users: dict[str, dict] = {}


async def get_user_from_db(username: str) -> dict | None:
    """Get user from database by username."""
    return _mock_users.get(username)


async def create_user_in_db(username: str, password: str) -> dict:
    """Create user in database."""
    user = {
        "username": username,
        "hashed_password": get_password_hash(password),
        "is_active": True,
    }
    _mock_users[username] = user
    return user


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(user_data: LoginRequest) -> dict:
    """
    Register a new user account.
    
    Returns user info without tokens (login separately to get tokens).
    """
    existing = await get_user_from_db(user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )
    
    await create_user_in_db(user_data.username, user_data.password)
    
    logger.info("User registered", username=user_data.username)
    
    return {
        "message": "User registered successfully",
        "username": user_data.username,
    }


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """
    OAuth2 compatible token login.
    
    Returns access and refresh tokens for authenticated user.
    """
    user = await get_user_from_db(form_data.username)
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        logger.warning(
            "Login failed - invalid credentials",
            username=form_data.username,
        )
        raise UnauthorizedError(
            message="Incorrect username or password",
            error_code="INVALID_CREDENTIALS",
        )
    
    if not user.get("is_active", True):
        logger.warning(
            "Login failed - inactive user",
            username=form_data.username,
        )
        raise UnauthorizedError(
            message="User account is deactivated",
            error_code="USER_INACTIVE",
        )
    
    # Create tokens
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        subject=user["username"],
        expires_delta=access_token_expires,
    )
    
    refresh_token = create_refresh_token(subject=user["username"])
    
    logger.info(
        "User logged in",
        username=form_data.username,
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_request: dict) -> TokenResponse:
    """
    Refresh access token using refresh token.
    """
    from app.core.security import decode_token
    
    refresh_token = refresh_request.get("refresh_token")
    if not refresh_token:
        raise UnauthorizedError(
            message="Refresh token required",
            error_code="MISSING_REFRESH_TOKEN",
        )
    
    try:
        payload = decode_token(refresh_token, token_type="refresh")
        username = payload["sub"]
    except Exception as e:
        logger.warning(
            "Token refresh failed",
            error=str(e),
        )
        raise UnauthorizedError(
            message="Invalid or expired refresh token",
            error_code="INVALID_REFRESH_TOKEN",
        )
    
    # Create new access token
    access_token_expires = timedelta(minutes=30)
    new_access_token = create_access_token(
        subject=username,
        expires_delta=access_token_expires,
    )
    
    # Optionally rotate refresh token
    new_refresh_token = create_refresh_token(subject=username)
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
    )
