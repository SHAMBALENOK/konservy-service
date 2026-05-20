from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.security import create_access_token, create_refresh_token, decode_token, get_password_hash, verify_password
from ..schemas.auth import UserRegister, UserLogin, TokenResponse, RefreshTokenRequest
from ..repositories.account import AccountRepository
from ..models.account import User
from ..core.exceptions import raise_not_found, raise_forbidden, raise_unauthorized
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Dependency to get the database session (will be overridden in main.py with actual implementation)
async def get_db():
    # This is a placeholder. In main.py, we will override this with a real session provider.
    raise NotImplementedError("Database session not configured")

# Dependency to get the account repository
async def get_account_repo(db: AsyncSession = Depends(get_db)):
    return AccountRepository(db)

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    account_repo: AccountRepository = Depends(get_account_repo)
):
    # Check if user already exists
    existing_user = await account_repo.session.execute(
        "SELECT id FROM users WHERE email = :email", {"email": user_data.email}
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash the password
    hashed_password = get_password_hash(user_data.password)
    
    # Create the user
    # Note: We are using the account_repo to access the session, but we don't have a user repository.
    # For simplicity, we'll create the user directly via the session.
    # In a real system, we would have a user repository.
    new_user = User(email=user_data.email, hashed_password=hashed_password)
    account_repo.session.add(new_user)
    await account_repo.session.commit()
    await account_repo.session.refresh(new_user)
    
    # Create access and refresh tokens
    access_token = create_access_token(data={"sub": str(new_user.id)})
    refresh_token = create_refresh_token(data={"sub": str(new_user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/login", response_model=TokenResponse)
async def login_user(
    user_data: UserLogin,
    account_repo: AccountRepository = Depends(get_account_repo)
):
    # Get the user by email
    result = await account_repo.session.execute(
        "SELECT id, hashed_password FROM users WHERE email = :email", {"email": user_data.email}
    )
    user = result.first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id, hashed_password = user
    
    # Verify the password
    if not verify_password(user_data.password, hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access and refresh tokens
    access_token = create_access_token(data={"sub": str(user_id)})
    refresh_token = create_refresh_token(data={"sub": str(user_id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token_request: RefreshTokenRequest,
    account_repo: AccountRepository = Depends(get_account_repo)
):
    # Decode the refresh token
    token_data = decode_token(refresh_token_request.refresh_token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = token_data.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if the user still exists and is active
    result = await account_repo.session.execute(
        "SELECT id FROM users WHERE id = :user_id AND is_active = TRUE", {"user_id": int(user_id)}
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create new access and refresh tokens
    new_access_token = create_access_token(data={"sub": user_id})
    new_refresh_token = create_refresh_token(data={"sub": user_id})
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )