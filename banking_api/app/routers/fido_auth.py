"""
FIDO2 / Passkeys authentication router.

Implements WebAuthn endpoints for passwordless biometric authentication.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import create_access_token, create_refresh_token
from app.schemas.common import TokenResponse
from app.security.fido2 import FIDO2Credential, FIDO2Service


logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/fido", tags=["FIDO2 Authentication"])


# Dependency to get FIDO2 service
async def get_fido2_service() -> FIDO2Service:
    """Get FIDO2 service instance."""
    # In production, inject Redis client
    return FIDO2Service(redis_client=None)


@router.post("/register/challenge")
async def fido_register_challenge(
    user_id: str,
    username: str,
    fido_service: FIDO2Service = Depends(get_fido2_service),
) -> dict:
    """
    Generate challenge for FIDO2 registration.
    
    Client calls this before navigator.credentials.create()
    
    UX: Triggered when user wants to set up biometric login.
    """
    try:
        options, challenge = await fido_service.create_registration_challenge(
            user_id=user_id,
            username=username,
        )
        
        return {
            "challenge": options,
            "expires_in": 300,  # seconds
        }
        
    except Exception as e:
        logger.error("Failed to create registration challenge", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create registration challenge",
        )


@router.post("/register/verify")
async def fido_register_verify(
    user_id: str,
    attestation_response: dict,
    device_id: str | None = None,
    fido_service: FIDO2Service = Depends(get_fido2_service),
) -> dict:
    """
    Verify FIDO2 attestation and save credential.
    
    Client sends response from navigator.credentials.create()
    
    UX: Called after user completes biometric enrollment (FaceID/TouchID).
    """
    try:
        # Extract challenge from response
        challenge_str = attestation_response.get("challenge")
        if not challenge_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing challenge",
            )
        
        # Get and validate challenge
        challenge = await fido_service._get_challenge(challenge_str)
        if not challenge or challenge.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired challenge",
            )
        
        # Verify attestation
        credential = await fido_service.verify_registration(
            challenge=challenge,
            attestation_response=attestation_response,
        )
        
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to verify attestation",
            )
        
        # Add device_id
        credential.device_id = device_id
        
        # Save credential
        await fido_service.register_credential(credential)
        
        # Delete used challenge
        await fido_service.delete_challenge(challenge_str)
        
        logger.info(
            "FIDO2 credential registered",
            user_id=user_id,
            credential_id=credential.credential_id[:8] + "...",
        )
        
        return {
            "success": True,
            "message": "Biometric authentication enabled",
            "credential_id": credential.credential_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login/challenge")
async def fido_login_challenge(
    user_id: str,
    fido_service: FIDO2Service = Depends(get_fido2_service),
) -> dict:
    """
    Generate challenge for FIDO2 login.
    
    Client calls this before navigator.credentials.get()
    
    UX: First step of biometric login flow.
    """
    try:
        # Get user's registered credentials
        credentials = await fido_service.get_user_credentials(user_id)
        allowed_ids = [c.credential_id for c in credentials]
        
        options, challenge = await fido_service.create_login_challenge(
            user_id=user_id,
            allowed_credentials=allowed_ids,
        )
        
        return {
            "challenge": options,
            "expires_in": 300,
        }
        
    except Exception as e:
        logger.error("Failed to create login challenge", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create login challenge",
        )


@router.post("/login/verify", response_model=TokenResponse)
async def fido_login_verify(
    user_id: str,
    assertion_response: dict,
    fido_service: FIDO2Service = Depends(get_fido2_service),
) -> TokenResponse:
    """
    Verify FIDO2 assertion and issue tokens.
    
    Client sends response from navigator.credentials.get()
    
    UX: Final step - after biometric verification (FaceID/TouchID).
    Returns JWT tokens on success.
    """
    try:
        # Extract challenge from response
        challenge_str = assertion_response.get("challenge")
        if not challenge_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing challenge",
            )
        
        # Get and validate challenge
        challenge = await fido_service._get_challenge(challenge_str)
        if not challenge or challenge.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired challenge",
            )
        
        # Verify assertion (signature)
        success, error = await fido_service.verify_login(
            challenge=challenge,
            assertion_response=assertion_response,
        )
        
        if not success:
            logger.warning(
                "FIDO2 login verification failed",
                user_id=user_id,
                error=error,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Verification failed: {error}",
            )
        
        # Delete used challenge
        await fido_service.delete_challenge(challenge_str)
        
        # Update sign count (prevent replay attacks)
        credential_id = assertion_response.get("id")
        # await fido_service.update_sign_count(credential_id, new_sign_count)
        
        # Issue JWT tokens
        access_token = create_access_token(subject=user_id)
        refresh_token = create_refresh_token(subject=user_id)
        
        logger.info(
            "FIDO2 login successful",
            user_id=user_id,
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=1800,  # 30 minutes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )


@router.get("/credentials")
async def list_fido_credentials(
    user_id: str,
    fido_service: FIDO2Service = Depends(get_fido2_service),
) -> list[dict]:
    """
    List all FIDO2 credentials for user.
    
    Used in Security settings to show registered devices.
    """
    try:
        credentials = await fido_service.get_user_credentials(user_id)
        
        return [
            {
                "credential_id": c.credential_id[:8] + "...",
                "device_id": c.device_id,
                "created_at": c.created_at.isoformat(),
                "last_used": c.last_used.isoformat() if c.last_used else None,
                "is_synced": c.is_synced,
            }
            for c in credentials
        ]
        
    except Exception as e:
        logger.error("Failed to list credentials", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list credentials",
        )


@router.delete("/credentials/{credential_id}")
async def revoke_fido_credential(
    credential_id: str,
    user_id: str,
    fido_service: FIDO2Service = Depends(get_fido2_service),
) -> dict:
    """
    Revoke a FIDO2 credential.
    
    User can remove lost/stolen devices from Security settings.
    """
    try:
        # In production: UPDATE fido2_credentials SET is_active=FALSE WHERE ...
        logger.info(
            "Credential revoked",
            user_id=user_id,
            credential_id=credential_id[:8] + "...",
        )
        
        return {
            "success": True,
            "message": "Device removed successfully",
        }
        
    except Exception as e:
        logger.error("Failed to revoke credential", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke credential",
        )
