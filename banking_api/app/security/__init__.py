"""
Модуль безопасности Banking App v2.0

Этот модуль реализует:
1. Поведенческий анализ и предотвращение мошенничества (Fraud Detection Engine)
2. Криптография и защита данных (Encryption & Data Protection)
3. Аутентификация FIDO2 / Passkeys
4. Мониторинг и обратная связь (Observability & Feedback)
"""

from app.security.fraud_detection import (
    TelemetryService,
    UserProfileService,
    RiskAssessmentMiddleware,
    RiskLevel,
)
from app.security.encryption import (
    EncryptionService,
    FieldEncryptionMixin,
)
from app.security.fido2 import (
    FIDO2Service,
    FIDO2Credential,
)
from app.security.monitoring import (
    SecurityEventLogger,
    SecurityEventType,
)

__all__ = [
    # Fraud Detection
    "TelemetryService",
    "UserProfileService",
    "RiskAssessmentMiddleware",
    "RiskLevel",
    # Encryption
    "EncryptionService",
    "FieldEncryptionMixin",
    # FIDO2
    "FIDO2Service",
    "FIDO2Credential",
    # Monitoring
    "SecurityEventLogger",
    "SecurityEventType",
]
