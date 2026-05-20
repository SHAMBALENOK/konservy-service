from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas.telemetry import SessionTelemetry, SecurityHistory
from ..core.exceptions import raise_not_found, raise_forbidden
from ..core.security import decode_token
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["Telemetry & Security"])

# Dependency to get the database session (will be overridden in main.py)
async def get_db():
    raise NotImplementedError("Database session not configured")

# Dependency to get the current user from token (simplified)
async def get_current_user(token: str = Depends(lambda: None)) -> int:
    # This is a simplified dependency. In a real system, we would get the token from the header.
    # For now, we'll assume it's passed as a dependency that extracts it from the request.
    # We'll need to adjust this to actually get the token from the Authorization header.
    # Since we can't access the request directly in a dependency without Request, we'll do it differently.
    # Let's create a dependency that gets the token from the header.
    raise NotImplementedError("Current user dependency not configured")

# Better approach: create a dependency that gets the token from the Authorization header
async def get_token_from_header(authorization: str = Depends(lambda: None)) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Remove 'Bearer ' prefix if present
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return authorization

async def get_current_user_from_token(token: str = Depends(get_token_from_header)) -> int:
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return int(user_id)

@router.post("/session")
async def collect_session_telemetry(
    telemetry: SessionTelemetry,
    current_user: int = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    # Verify that the telemetry belongs to the current user
    if telemetry.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to submit telemetry for another user"
        )
    
    # In a real system, we would store this telemetry data in a database
    # and potentially feed it to an ML model for risk scoring.
    # For now, we'll just log it and return a success message.
    logger.info(f"Received session telemetry for user {current_user}: {telemetry.dict()}")
    
    return {
        "status": "Telemetry collected successfully",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/security/history")
async def get_security_history(
    current_user: int = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    # In a real system, we would fetch security events from a database
    # For now, we'll return some mock data
    return [
        {
            "event_id": "EVT001",
            "timestamp": "2026-05-20T10:00:00Z",
            "event_type": "LOGIN_SUCCESS",
            "details": {"method": "password", "ip_address": "192.168.1.1"}
        },
        {
            "event_id": "EVT002",
            "timestamp": "2026-05-20T14:30:00Z",
            "event_type": "FIDO2_REGISTRATION",
            "details": {"credential_id": "cred_123"}
        }
    ]

@router.get("/devices")
async def list_devices(
    current_user: int = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    # In a real system, we would fetch user devices from a database
    # For now, we'll return some mock data
    return [
        {
            "device_id": "dev_001",
            "device_name": "iPhone 13",
            "device_type": "mobile",
            "is_trusted": True,
            "last_seen": "2026-05-20T09:00:00Z"
        },
        {
            "device_id": "dev_002",
            "device_name": "MacBook Pro",
            "device_type": "laptop",
            "is_trusted": True,
            "last_seen": "2026-05-19T16:00:00Z"
        }
    ]

@router.delete("/devices/{device_id}")
async def revoke_device_access(
    device_id: str,
    current_user: int = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    # In a real system, we would update the device status in a database
    # For now, we'll just return a success message
    logger.info(f"Revoking access for device {device_id} for user {current_user}")
    return {
        "message": f"Access to device {device_id} revoked",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/devices/{device_id}/trust")
async def trust_device(
    device_id: str,
    current_user: int = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    # In a real system, we would update the device trust status in a database
    # For now, we'll just return a success message
    logger.info(f"Marking device {device_id} as trusted for user {current_user}")
    return {
        "message": f"Device {device_id} marked as trusted",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/certificate-pinning")
async def get_cert_pinning_config(
    current_user: int = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    # In a real system, we would retrieve the certificate pinning configuration
    # For now, we'll return some mock data that indicates quantum-safe readiness
    return {
        "pinning_status": "quantum_safe",
        "algorithm": "CRYSTALS-Dilithium",
        "public_key": "dummy_public_key_for_demo",
        "valid_until": "2030-01-01T00:00:00Z"
    }