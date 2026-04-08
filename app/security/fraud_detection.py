"""
Модуль поведенческого анализа и предотвращения мошенничества (Fraud Detection Engine)

Реализует систему оценки риска транзакций в реальном времени на основе поведения пользователя.
"""

import hashlib
import structlog
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from fastapi import Request


logger = structlog.get_logger(__name__)


class RiskLevel(Enum):
    """Уровни риска для транзакций."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TelemetryData:
    """Данные телеметрии сессии пользователя."""
    device_id: str
    geo_location: dict[str, float] | None = None  # {"lat": ..., "lon": ...}
    user_agent: str | None = None
    typing_speed: float | None = None  # символов в секунду
    time_of_day: int | None = None  # час дня (0-23)
    ip_address: str | None = None
    session_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "device_id": self.device_id,
            "geo_location": self.geo_location,
            "user_agent": self.user_agent,
            "typing_speed": self.typing_speed,
            "time_of_day": self.time_of_day,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class UserProfile:
    """Цифровой отпечаток пользователя (базовые паттерны)."""
    user_id: str
    # Обычные локации (список хэшей geo_location)
    known_locations: set[str] = field(default_factory=set)
    # Обычные устройства
    known_devices: set[str] = field(default_factory=set)
    # Обычное время активности (часы)
    active_hours: set[int] = field(default_factory=set)
    # Средние суммы транзакций
    avg_transaction_amount: float = 0.0
    # Максимальная типичная сумма
    max_typical_amount: float = 0.0
    # Количество транзакций для статистики
    transaction_count: int = 0
    # Последний вход
    last_login: datetime | None = None
    # IP адреса
    known_ips: set[str] = field(default_factory=set)

    def update_transaction_stats(self, amount: float) -> None:
        """Обновить статистику транзакций."""
        self.transaction_count += 1
        # Скользящее среднее
        self.avg_transaction_amount = (
            (self.avg_transaction_amount * (self.transaction_count - 1) + amount)
            / self.transaction_count
        )
        # Обновляем максимум
        if amount > self.max_typical_amount:
            self.max_typical_amount = amount

    def add_known_device(self, device_id: str) -> None:
        """Добавить известное устройство."""
        self.known_devices.add(device_id)

    def add_known_location(self, geo_hash: str) -> None:
        """Добавить известную локацию."""
        self.known_locations.add(geo_hash)

    def add_known_ip(self, ip: str) -> None:
        """Добавить известный IP."""
        self.known_ips.add(ip)

    def add_active_hour(self, hour: int) -> None:
        """Добавить час активности."""
        self.active_hours.add(hour)


class TelemetryService:
    """
    Сервис сбора телеметрии.
    
    Собирает метрики с клиента асинхронно, не блокируя основной поток.
    Endpoint: POST /api/v1/telemetry/session
    """

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self._telemetry_buffer: list[TelemetryData] = []

    async def collect_telemetry(self, telemetry: TelemetryData) -> None:
        """
        Асинхронный сбор телеметрии.
        
        Данные буферизируются и отправляются в фоновом режиме.
        """
        self._telemetry_buffer.append(telemetry)
        
        # Если буфер заполнен или прошло время - отправить
        if len(self._telemetry_buffer) >= 100:
            await self._flush_telemetry()

    async def _flush_telemetry(self) -> None:
        """Отправить накопленную телеметрию в хранилище."""
        if not self._telemetry_buffer:
            return

        try:
            # В продакшене здесь будет отправка в SIEM/аналитику
            for telemetry in self._telemetry_buffer:
                key = f"telemetry:{telemetry.device_id}:{telemetry.timestamp.timestamp()}"
                if self.redis_client:
                    await self.redis_client.setex(
                        key,
                        timedelta(days=7),
                        str(telemetry.to_dict()),
                    )
            
            logger.info(
                "Telemetry flushed",
                count=len(self._telemetry_buffer),
            )
        except Exception as e:
            logger.error("Failed to flush telemetry", error=str(e))
        finally:
            self._telemetry_buffer.clear()

    async def get_session_telemetry(self, device_id: str) -> list[dict]:
        """Получить историю телеметрии для устройства."""
        if not self.redis_client:
            return []

        # В реальном проекте здесь был бы запрос к БД/хранилищу
        return []


class UserProfileService:
    """
    Сервис профилирования пользователей.
    
    Хранит и обновляет цифровые отпечатки пользователей,
    сравнивает текущую сессию с базовым профилем.
    """

    # Пороги для эвристической оценки
    LOCATION_WEIGHT = 0.3
    DEVICE_WEIGHT = 0.25
    TIME_WEIGHT = 0.2
    IP_WEIGHT = 0.15
    AMOUNT_WEIGHT = 0.1

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self._profiles: dict[str, UserProfile] = {}

    def _geo_hash(self, geo_location: dict[str, float] | None) -> str | None:
        """Создать хэш геолокации для сравнения."""
        if not geo_location:
            return None
        lat = round(geo_location.get("lat", 0), 2)  # Округляем до ~1км
        lon = round(geo_location.get("lon", 0), 2)
        return hashlib.sha256(f"{lat}:{lon}".encode()).hexdigest()[:16]

    async def get_profile(self, user_id: str) -> UserProfile | None:
        """Получить профиль пользователя."""
        # Проверить кэш
        if user_id in self._profiles:
            return self._profiles[user_id]

        # Загрузить из Redis/БД
        if self.redis_client:
            try:
                data = await self.redis_client.get(f"profile:{user_id}")
                if data:
                    # Десериализация (упрощенно)
                    profile = UserProfile(user_id=user_id)
                    self._profiles[user_id] = profile
                    return profile
            except Exception as e:
                logger.error("Failed to load profile", user_id=user_id, error=str(e))

        return None

    async def create_or_update_profile(
        self,
        user_id: str,
        telemetry: TelemetryData,
    ) -> UserProfile:
        """Создать или обновить профиль пользователя."""
        profile = await self.get_profile(user_id)
        
        if not profile:
            profile = UserProfile(user_id=user_id)
        
        # Обновить профиль данными телеметрии
        if telemetry.device_id:
            profile.add_known_device(telemetry.device_id)
        
        if telemetry.geo_location:
            geo_hash = self._geo_hash(telemetry.geo_location)
            if geo_hash:
                profile.add_known_location(geo_hash)
        
        if telemetry.ip_address:
            profile.add_known_ip(telemetry.ip_address)
        
        if telemetry.time_of_day is not None:
            profile.add_active_hour(telemetry.time_of_day)

        # Сохранить
        self._profiles[user_id] = profile
        
        if self.redis_client:
            try:
                # Упрощенная сериализация
                await self.redis_client.setex(
                    f"profile:{user_id}",
                    timedelta(days=30),
                    user_id,  # В реальности - полный профиль
                )
            except Exception as e:
                logger.error("Failed to save profile", user_id=user_id, error=str(e))

        return profile

    def calculate_risk_score(
        self,
        profile: UserProfile | None,
        telemetry: TelemetryData,
        transaction_amount: float | None = None,
    ) -> tuple[float, dict[str, Any]]:
        """
        Рассчитать score риска на основе профиля и телеметрии.
        
        Возвращает score (0-100) и детали оценки.
        """
        risk_details: dict[str, Any] = {
            "factors": [],
            "score_breakdown": {},
        }
        
        if not profile:
            # Нет профиля - высокий риск
            risk_details["factors"].append("no_profile")
            return 75.0, risk_details

        total_score = 0.0

        # 1. Проверка устройства (вес 25%)
        device_known = telemetry.device_id in profile.known_devices
        if not device_known:
            total_score += 25.0
            risk_details["factors"].append("unknown_device")
        risk_details["score_breakdown"]["device"] = 0 if device_known else 25

        # 2. Проверка локации (вес 30%)
        geo_hash = self._geo_hash(telemetry.geo_location)
        location_known = geo_hash and geo_hash in profile.known_locations
        if not location_known:
            total_score += 30.0
            risk_details["factors"].append("unknown_location")
        risk_details["score_breakdown"]["location"] = 0 if location_known else 30

        # 3. Проверка времени активности (вес 20%)
        time_normal = (
            telemetry.time_of_day is None
            or telemetry.time_of_day in profile.active_hours
        )
        if not time_normal:
            total_score += 20.0
            risk_details["factors"].append("unusual_time")
        risk_details["score_breakdown"]["time"] = 0 if time_normal else 20

        # 4. Проверка IP (вес 15%)
        ip_known = (
            telemetry.ip_address is None
            or telemetry.ip_address in profile.known_ips
        )
        if not ip_known:
            total_score += 15.0
            risk_details["factors"].append("unknown_ip")
        risk_details["score_breakdown"]["ip"] = 0 if ip_known else 15

        # 5. Проверка суммы транзакции (вес 10%)
        if transaction_amount is not None and profile.transaction_count > 0:
            # Если сумма значительно превышает среднюю
            if transaction_amount > profile.max_typical_amount * 2:
                total_score += 10.0
                risk_details["factors"].append("unusual_amount")
            risk_details["score_breakdown"]["amount"] = (
                10 if transaction_amount > profile.max_typical_amount * 2 else 0
            )

        risk_details["total_score"] = total_score
        return min(total_score, 100.0), risk_details


@dataclass
class RiskAssessmentResult:
    """Результат оценки риска."""
    risk_level: RiskLevel
    risk_score: float
    requires_action: bool
    action_type: str | None = None  # "push_biometric", "strict_verification", "block"
    details: dict[str, Any] = field(default_factory=dict)


class RiskAssessmentMiddleware:
    """
    Middleware для адаптивной проверки рисков (Risk-Based Authentication).
    
    Логика:
    - risk_score < 25: пропускать без действий
    - 25 <= risk_score < 60: мягкое подтверждение (Push + биометрия)
    - risk_score >= 60: блокировка + строгая верификация
    """

    LOW_THRESHOLD = 25.0
    HIGH_THRESHOLD = 60.0

    def __init__(
        self,
        profile_service: UserProfileService,
        telemetry_service: TelemetryService,
    ):
        self.profile_service = profile_service
        self.telemetry_service = telemetry_service

    async def assess_request(
        self,
        request: Request,
        user_id: str,
        transaction_amount: float | None = None,
    ) -> RiskAssessmentResult:
        """
        Оценить риск запроса.
        
        Происходит прозрачно для пользователя.
        """
        # Извлечь телеметрию из запроса
        telemetry = self._extract_telemetry(request)
        
        # Получить или создать профиль
        profile = await self.profile_service.get_profile(user_id)
        if not profile:
            profile = await self.profile_service.create_or_update_profile(
                user_id, telemetry
            )

        # Рассчитать risk score
        risk_score, risk_details = self.profile_service.calculate_risk_score(
            profile, telemetry, transaction_amount
        )

        # Определить уровень риска и действие
        if risk_score < self.LOW_THRESHOLD:
            return RiskAssessmentResult(
                risk_level=RiskLevel.LOW,
                risk_score=risk_score,
                requires_action=False,
                details=risk_details,
            )
        elif risk_score < self.HIGH_THRESHOLD:
            # Мягкое подтверждение
            return RiskAssessmentResult(
                risk_level=RiskLevel.MEDIUM,
                risk_score=risk_score,
                requires_action=True,
                action_type="push_biometric",
                details=risk_details,
            )
        else:
            # Блокировка + строгая верификация
            return RiskAssessmentResult(
                risk_level=RiskLevel.HIGH,
                risk_score=risk_score,
                requires_action=True,
                action_type="strict_verification",
                details=risk_details,
            )

    def _extract_telemetry(self, request: Request) -> TelemetryData:
        """Извлечь данные телеметрии из запроса."""
        headers = request.headers
        client_ip = request.client.host if request.client else None
        
        # Время дня
        now = datetime.now(UTC)
        time_of_day = now.hour

        return TelemetryData(
            device_id=headers.get("x-device-id", "unknown"),
            user_agent=headers.get("user-agent"),
            ip_address=client_ip,
            time_of_day=time_of_day,
            # Geo-location может передаваться в заголовках или body
            geo_location=None,  # Заполняется клиентом
            typing_speed=None,  # Опционально
            session_id=headers.get("x-session-id"),
        )

    def get_block_message(self, risk_result: RiskAssessmentResult) -> str:
        """
        Получить понятное сообщение о блокировке.
        
        UX-требование: сообщение должно быть понятным, не техническим.
        """
        if risk_result.action_type == "strict_verification":
            return (
                "Мы заметили необычную активность. "
                "Для вашей безопасности подтвердите личность."
            )
        elif risk_result.action_type == "push_biometric":
            return (
                "Требуется дополнительное подтверждение. "
                "Проверьте Push-уведомление."
            )
        return "Требуется проверка безопасности."
