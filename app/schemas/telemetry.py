from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SessionTelemetry(BaseModel):
    user_id: int = Field(..., example=1, description="The user ID associated with this telemetry")
    session_id: str = Field(..., example="sess_abc123", description="Unique session identifier")
    ip_address: str = Field(..., example="192.168.1.100", description="Client IP address")
    user_agent: str = Field(..., example="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", description="Client user agent")
    device_fingerprint: Optional[str] = Field(None, example="fp_xyz789", description="Device fingerprint for fraud detection")
    location: Optional[str] = Field(None, example="New York, NY", description="Geographic location")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the telemetry event")
    risk_score: Optional[float] = Field(None, ge=0.0, le=1.0, example=0.2, description="Calculated risk score (0-1)")


class SecurityHistory(BaseModel):
    event_id: str = Field(..., example="EVT001", description="Unique event identifier")
    timestamp: datetime = Field(..., example="2026-05-20T10:00:00Z", description="Event timestamp")
    event_type: str = Field(..., example="LOGIN_SUCCESS", description="Type of security event")
    details: dict = Field(..., example={"method": "password", "ip_address": "192.168.1.1"}, description="Event details")