"""
Telemetry and Security router.

Endpoints for:
- Collecting session telemetry
- Security settings management
- Device management
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.security.fraud_detection import TelemetryData, TelemetryService
from app.security.monitoring import (
    DeviceInfo,
    DeviceManagementService,
    SecurityEvent,
    SecurityEventLogger,
    SecurityEventType,
)


logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/telemetry", tags=["Telemetry & Security"])


# Dependencies
async def get_telemetry_service() -> TelemetryService:
    """Get telemetry service instance."""
    return TelemetryService(redis_client=None)


async def get_device_service() -> DeviceManagementService:
    """Get device management service."""
    return DeviceManagementService(redis_client=None)


async def get_security_logger() -> SecurityEventLogger:
    """Get security event logger."""
    return SecurityEventLogger(siem_endpoint=None, redis_client=None)


@router.post("/session", status_code=status.HTTP_202_ACCEPTED)
async def collect_session_telemetry(
    request: Request,
    telemetry_data: dict,
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
):
    """
    Collect session telemetry from client.
    
    Accepts metrics: device_id, geo_location, user_agent, typing_speed,
    time_of_day, ip_address.
    
    Data is collected asynchronously without blocking main request flow.
    
    UX: Called periodically in background by mobile app.
    """
    try:
        # Parse telemetry data
        telemetry = TelemetryData(
            device_id=telemetry_data.get("device_id", "unknown"),
            geo_location=telemetry_data.get("geo_location"),
            user_agent=telemetry_data.get("user_agent"),
            typing_speed=telemetry_data.get("typing_speed"),
            time_of_day=telemetry_data.get("time_of_day"),
            ip_address=telemetry_data.get("ip_address") or request.client.host if request.client else None,
            session_id=telemetry_data.get("session_id"),
        )
        
        # Collect asynchronously (non-blocking)
        await telemetry_service.collect_telemetry(telemetry)
        
        return {
            "status": "accepted",
            "message": "Telemetry received",
        }
        
    except Exception as e:
        logger.error("Failed to collect telemetry", error=str(e))
        # Don't fail the request - telemetry is non-critical
        return {
            "status": "error",
            "message": "Telemetry collection failed",
        }


@router.get("/security/history")
async def get_security_history(
    user_id: str,
    limit: int = 50,
    security_logger: SecurityEventLogger = Depends(get_security_logger),
) -> list[dict]:
    """
    Get user's security event history.
    
    Used in Security section of the app to show login history,
    suspicious activity, etc.
    
    UX: Displayed in \"Security\" tab with timeline view.
    """
    try:
        events = await security_logger.get_user_security_history(
            user_id=user_id,
            limit=limit,
        )
        
        return events
        
    except Exception as e:
        logger.error("Failed to get security history", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security history",
        )


@router.get("/devices")
async def list_devices(
    user_id: str,
    device_service: DeviceManagementService = Depends(get_device_service),
) -> list[dict]:
    """
    List all devices associated with user account.
    
    Shows device name, type, last seen, trust status.
    
    UX: Security settings page - allows reviewing active sessions.
    """
    try:
        devices = await device_service.get_user_devices(user_id)
        
        return [
            {
                "device_id": d.device_id,
                "device_name": d.device_name,
                "device_type": d.device_type,
                "os": d.os,
                "browser": d.browser,
                "first_seen": d.first_seen.isoformat(),
                "last_seen": d.last_seen.isoformat(),
                "is_trusted": d.is_trusted,
                "ip_address": d.ip_address,
            }
            for d in devices
        ]
        
    except Exception as e:
        logger.error("Failed to list devices", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve devices",
        )


@router.delete("/devices/{device_id}")
async def revoke_device(
    device_id: str,
    user_id: str,
    device_service: DeviceManagementService = Depends(get_device_service),
) -> dict:
    """
    Revoke access for a specific device.
    
    Forces logout on that device and invalidates its session.
    
    UX: User can remove lost/stolen devices from Security settings.
    """
    try:
        success = await device_service.revoke_device(
            user_id=user_id,
            device_id=device_id,
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found",
            )
        
        # Log security event
        event = SecurityEvent(
            event_type=SecurityEventType.DEVICE_REVOKED,
            user_id=user_id,
            device_id=device_id,
            metadata={"revoked_by": user_id},
        )
        await device_service.redis_client.lpush("siem_events", str(event.to_dict())) if device_service.redis_client else None
        
        logger.info(
            "Device access revoked",
            user_id=user_id,
            device_id=device_id,
        )
        
        return {
            "success": True,
            "message": "Device access revoked successfully",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to revoke device", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke device",
        )


@router.post("/devices/{device_id}/trust")
async def mark_device_trusted(
    device_id: str,
    user_id: str,
    device_service: DeviceManagementService = Depends(get_device_service),
) -> dict:
    """
    Mark a device as trusted.
    
    Trusted devices may skip some verification steps.
    
    UX: User can mark their personal devices as trusted.
    """
    try:
        await device_service.mark_as_trusted(
            user_id=user_id,
            device_id=device_id,
        )
        
        logger.info(
            "Device marked as trusted",
            user_id=user_id,
            device_id=device_id,
        )
        
        return {
            "success": True,
            "message": "Device marked as trusted",
        }
        
    except Exception as e:
        logger.error("Failed to mark device as trusted", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark device as trusted",
        )


@router.get("/certificate-pinning")
async def get_certificate_pinning_config() -> dict:
    """
    Get certificate pinning configuration for mobile clients.
    
    Returns SHA-256 pins for TLS certificate validation.
    
    UX: Called by mobile app on startup to configure pinning.
    """
    # In production, load from secure config
    from app.security.encryption import CertificatePinningConfig
    
    config = CertificatePinningConfig(
        pins=[
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",  # Example pin
            "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",  # Backup pin
        ],
        backup_pins=[
            "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC=",  # Rotation pin
        ],
    )
    
    return config.get_config()
