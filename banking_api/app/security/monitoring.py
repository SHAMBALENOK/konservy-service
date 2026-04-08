"""
Модуль мониторинга и обратной связи (Observability & Feedback)

Обеспечивает прозрачность работы систем безопасности для поддержки и пользователей.
"""

import structlog
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


logger = structlog.get_logger(__name__)


class SecurityEventType(Enum):
    """Типы событий безопасности."""
    # Аутентификация
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    FIDO2_REGISTERED = "fido2_registered"
    FIDO2_LOGIN = "fido2_login"
    
    # Риски и мошенничество
    HIGH_RISK_TRANSACTION = "high_risk_transaction"
    TRANSACTION_BLOCKED = "transaction_blocked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    UNKNOWN_DEVICE_LOGIN = "unknown_device_login"
    UNKNOWN_LOCATION_ACCESS = "unknown_location_access"
    
    # Защита данных
    ENCRYPTION_ERROR = "encryption_error"
    DECRYPTION_ERROR = "decryption_error"
    
    # RASP
    INJECTION_ATTEMPT = "injection_attempt"
    DEBUG_MODE_DETECTED = "debug_mode_detected"
    XSS_ATTEMPT = "xss_attempt"
    
    # Управление доступом
    DEVICE_ADDED = "device_added"
    DEVICE_REVOKED = "device_revoked"
    SESSION_TERMINATED = "session_terminated"


@dataclass
class SecurityEvent:
    """Событие безопасности для логирования в SIEM."""
    event_type: SecurityEventType
    user_id: str | None = None
    device_id: str | None = None
    ip_address: str | None = None
    risk_score: float | None = None
    risk_factors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    severity: str = "info"  # info, warning, error, critical

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать для отправки в SIEM."""
        return {
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "ip_address": self.ip_address,
            "risk_score": self.risk_score,
            "risk_factors": self.risk_factors,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
        }

    @classmethod
    def determine_severity(cls, event_type: SecurityEventType, risk_score: float | None = None) -> str:
        """Определить уровень серьезности события."""
        high_severity_events = {
            SecurityEventType.TRANSACTION_BLOCKED,
            SecurityEventType.INJECTION_ATTEMPT,
            SecurityEventType.XSS_ATTEMPT,
            SecurityEventType.DEBUG_MODE_DETECTED,
        }
        
        if event_type in high_severity_events:
            return "critical"
        
        if risk_score is not None:
            if risk_score >= 60:
                return "critical"
            elif risk_score >= 25:
                return "warning"
        
        medium_severity_events = {
            SecurityEventType.LOGIN_FAILED,
            SecurityEventType.UNKNOWN_DEVICE_LOGIN,
            SecurityEventType.UNKNOWN_LOCATION_ACCESS,
            SecurityEventType.HIGH_RISK_TRANSACTION,
        }
        
        if event_type in medium_severity_events:
            return "warning"
        
        return "info"


class SecurityEventLogger:
    """
    Логгер событий безопасности.
    
    Отправляет события в SIEM-систему с полным контекстом.
    """

    def __init__(self, siem_endpoint: str | None = None, redis_client=None):
        self.siem_endpoint = siem_endpoint
        self.redis_client = redis_client
        self._buffer: list[SecurityEvent] = []

    async def log_event(self, event: SecurityEvent) -> None:
        """
        Записать событие безопасности.
        
        Все события с высоким risk_score логируются в SIEM.
        """
        # Автоматически определить severity
        if event.severity == "info":
            event.severity = SecurityEvent.determine_severity(
                event.event_type,
                event.risk_score,
            )
        
        # Добавить в буфер
        self._buffer.append(event)
        
        # Логировать локально (структурированный лог)
        log_method = getattr(logger, event.severity)
        log_method(
            f"Security event: {event.event_type.value}",
            user_id=event.user_id,
            device_id=event.device_id,
            ip_address=event.ip_address,
            risk_score=event.risk_score,
            risk_factors=event.risk_factors,
            **event.metadata,
        )
        
        # Отправить в SIEM если настроено
        if self.siem_endpoint:
            await self._send_to_siem(event)
        
        # Flush буфера если заполнен
        if len(self._buffer) >= 100:
            await self._flush_buffer()

    async def _send_to_siem(self, event: SecurityEvent) -> None:
        """Отправить событие в SIEM-систему."""
        try:
            # В продакшене здесь будет HTTP запрос к SIEM
            # Например: Splunk, ELK, Datadog Security
            event_data = event.to_dict()
            
            if self.redis_client:
                # Буферизация через Redis
                await self.redis_client.lpush(
                    "siem_events",
                    str(event_data),
                )
            
            logger.debug("Event sent to SIEM", event_type=event.event_type.value)
            
        except Exception as e:
            logger.error("Failed to send event to SIEM", error=str(e))

    async def _flush_buffer(self) -> None:
        """Отправить накопленные события."""
        if not self._buffer:
            return
        
        try:
            # Пакетная отправка в SIEM
            events_data = [e.to_dict() for e in self._buffer]
            
            # Здесь была бы пакетная отправка
            logger.info("Flushed security events", count=len(events_data))
            
        except Exception as e:
            logger.error("Failed to flush security events", error=str(e))
        finally:
            self._buffer.clear()

    async def get_user_security_history(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        Получить историю событий безопасности пользователя.
        
        Используется для раздела "Безопасность" в приложении.
        """
        # В реальности запрос к БД
        # SELECT * FROM security_events WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
        return []


@dataclass
class PushNotification:
    """Push-уведомление о событии безопасности."""
    user_id: str
    title: str
    body: str
    event_type: SecurityEventType
    action_url: str | None = None
    priority: str = "normal"  # normal, high
    data: dict[str, Any] = field(default_factory=dict)


class PushNotificationService:
    """
    Сервис push-уведомлений о событиях безопасности.
    
    Мгновенно оповещает пользователя о:
    - Входах с новых устройств
    - Подозрительных транзакциях
    - Изменениях настроек безопасности
    """

    def __init__(self, firebase_client=None, apns_client=None):
        self.firebase_client = firebase_client  # Для Android
        self.apns_client = apns_client  # Для iOS

    async def send_notification(self, notification: PushNotification) -> bool:
        """
        Отправить push-уведомление.
        
        Returns:
            True если успешно, False иначе
        """
        try:
            # Определить платформу пользователя (из БД)
            # platform = await self._get_user_platform(notification.user_id)
            
            message = {
                "title": notification.title,
                "body": notification.body,
                "data": {
                    "event_type": notification.event_type.value,
                    **(notification.data or {}),
                },
            }
            
            if notification.action_url:
                message["click_action"] = notification.action_url
            
            # Отправка через Firebase (Android)
            if self.firebase_client:
                await self._send_via_firebase(notification.user_id, message)
            
            # Отправка через APNS (iOS)
            if self.apns_client:
                await self._send_via_apns(notification.user_id, message)
            
            logger.info(
                "Push notification sent",
                user_id=notification.user_id,
                title=notification.title,
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to send push notification",
                user_id=notification.user_id,
                error=str(e),
            )
            return False

    async def _send_via_firebase(self, user_id: str, message: dict) -> None:
        """Отправить через Firebase Cloud Messaging."""
        # Получение token устройства из БД
        # device_token = await self._get_device_token(user_id)
        
        if self.firebase_client:
            # await self.firebase_client.send(device_token, message)
            pass

    async def _send_via_apns(self, user_id: str, message: dict) -> None:
        """Отправить через Apple Push Notification service."""
        # Получение device token из БД
        # device_token = await self._get_device_token(user_id)
        
        if self.apns_client:
            # await self.apns_client.send(device_token, message)
            pass

    async def notify_new_device_login(
        self,
        user_id: str,
        device_info: str,
        location: str | None = None,
    ) -> None:
        """Уведомить о входе с нового устройства."""
        location_text = f" из {location}" if location else ""
        
        notification = PushNotification(
            user_id=user_id,
            title="Новый вход в аккаунт",
            body=f"Вход выполнен с устройства{location_text}: {device_info}",
            event_type=SecurityEventType.UNKNOWN_DEVICE_LOGIN,
            action_url="/security/devices",
            priority="high",
            data={
                "device_info": device_info,
                "location": location,
            },
        )
        
        await self.send_notification(notification)

    async def notify_suspicious_transaction(
        self,
        user_id: str,
        amount: float,
        currency: str,
        recipient: str,
    ) -> None:
        """Уведомить о подозрительной транзакции."""
        notification = PushNotification(
            user_id=user_id,
            title="Подозрительная транзакция",
            body=f"Транзакция {amount} {currency} на {recipient} требует подтверждения",
            event_type=SecurityEventType.HIGH_RISK_TRANSACTION,
            action_url="/security/confirm-transaction",
            priority="high",
            data={
                "amount": amount,
                "currency": currency,
                "recipient": recipient,
            },
        )
        
        await self.send_notification(notification)


@dataclass
class DeviceInfo:
    """Информация об устройстве пользователя."""
    device_id: str
    device_name: str
    device_type: str  # mobile, desktop, tablet
    os: str
    browser: str | None = None
    first_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    ip_address: str | None = None
    is_trusted: bool = False


class DeviceManagementService:
    """
    Сервис управления доверенными устройствами.
    
    Позволяет пользователю:
    - Видеть историю входов и активные устройства
    - Удалять (отзывать) доступ устройств
    - Помечать устройства как доверенные
    """

    def __init__(self, redis_client=None):
        self.redis_client = redis_client

    async def get_user_devices(self, user_id: str) -> list[DeviceInfo]:
        """Получить все устройства пользователя."""
        # В реальности запрос к БД
        # SELECT * FROM devices WHERE user_id = ?
        return []

    async def add_device(
        self,
        user_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Добавить новое устройство."""
        # В реальности INSERT в БД
        logger.info(
            "Device added",
            user_id=user_id,
            device_id=device_info.device_id,
        )

    async def revoke_device(
        self,
        user_id: str,
        device_id: str,
    ) -> bool:
        """
        Отозвать доступ устройства.
        
        Returns:
            True если успешно
        """
        # В реальности UPDATE или DELETE в БД
        logger.info(
            "Device revoked",
            user_id=user_id,
            device_id=device_id,
        )
        return True

    async def mark_as_trusted(
        self,
        user_id: str,
        device_id: str,
    ) -> None:
        """Пометить устройство как доверенное."""
        # В реальности UPDATE в БД
        logger.info(
            "Device marked as trusted",
            user_id=user_id,
            device_id=device_id,
        )

    async def cleanup_inactive_devices(
        self,
        user_id: str,
        days_threshold: int = 90,
    ) -> int:
        """
        Удалить неактивные устройства.
        
        Args:
            user_id: ID пользователя
            days_threshold: Порог неактивности в днях
        
        Returns:
            Количество удаленных устройств
        """
        # В реальности DELETE WHERE last_seen < now - interval
        return 0
