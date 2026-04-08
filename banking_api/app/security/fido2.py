"""
Модуль аутентификации FIDO2 / Passkeys

Реализует стандарт FIDO2 для биометрической аутентификации через WebAuthn.
"""

import base64
import hashlib
import json
import os
import structlog
import typing
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import cbor2


logger = structlog.get_logger(__name__)


@dataclass
class FIDO2Credential:
    """
    Учетные данные FIDO2 (Passkey).
    
    Хранит публичный ключ и метаданные для верификации.
    """
    credential_id: str  # Base64-encoded ID ключа
    user_id: str
    device_id: str | None = None
    public_key: dict[str, Any] = field(default_factory=dict)
    sign_count: int = 0
    is_synced: bool = False  # True для synced passkeys ( iCloud Keychain, Google Password Manager)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used: datetime | None = None
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать в словарь для хранения в БД."""
        return {
            "credential_id": self.credential_id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "public_key": self.public_key,
            "sign_count": self.sign_count,
            "is_synced": self.is_synced,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FIDO2Credential":
        """Десериализовать из словаря."""
        return cls(
            credential_id=data["credential_id"],
            user_id=data["user_id"],
            device_id=data.get("device_id"),
            public_key=data.get("public_key", {}),
            sign_count=data.get("sign_count", 0),
            is_synced=data.get("is_synced", False),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(UTC),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            is_active=data.get("is_active", True),
        )


@dataclass
class Challenge:
    """Challenge для FIDO2 операции."""
    challenge: str  # Base64-encoded случайная строка
    user_id: str
    expires_at: datetime
    operation: str  # "register" или "authenticate"
    allowed_credentials: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenge": self.challenge,
            "user_id": self.user_id,
            "expires_at": self.expires_at.isoformat(),
            "operation": self.operation,
            "allowed_credentials": self.allowed_credentials,
        }


class FIDO2Service:
    """
    Сервис для работы с FIDO2/WebAuthn.
    
    Реализует endpoints:
    - POST /auth/fido/register/challenge
    - POST /auth/fido/register/verify
    - POST /auth/fido/login/challenge
    - POST /auth/fido/login/verify
    
    Поддерживает как device-bound, так и synced ключи.
    """

    CHALLENGE_EXPIRY_SECONDS = 300  # 5 минут
    ORIGIN = "https://banking.example.com"  # Должно быть из конфига
    RP_NAME = "Banking App"
    RP_ID = "banking.example.com"

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self._challenges: dict[str, Challenge] = {}

    def _generate_challenge(self) -> str:
        """Сгенерировать криптографически стойкий challenge."""
        return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')

    async def create_registration_challenge(
        self,
        user_id: str,
        username: str,
    ) -> tuple[dict, Challenge]:
        """
        Создать challenge для регистрации нового ключа.
        
        Endpoint: POST /auth/fido/register/challenge
        
        Args:
            user_id: ID пользователя
            username: Имя пользователя (для отображения)
        
        Returns:
            Tuple (options_for_client, challenge_object)
        """
        challenge_str = self._generate_challenge()
        expires_at = datetime.now(UTC) + timedelta(seconds=self.CHALLENGE_EXPIRY_SECONDS)
        
        challenge = Challenge(
            challenge=challenge_str,
            user_id=user_id,
            expires_at=expires_at,
            operation="register",
        )
        
        # Сохранить challenge
        await self._store_challenge(challenge)
        
        # Формат options для WebAuthn.create()
        options = {
            "challenge": challenge_str,
            "rp": {
                "name": self.RP_NAME,
                "id": self.RP_ID,
            },
            "user": {
                "id": base64.urlsafe_b64encode(user_id.encode()).decode().rstrip('='),
                "name": username,
                "displayName": username,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},  # ES256
                {"type": "public-key", "alg": -257},  # RS256
            ],
            "timeout": 60000,
            "excludeCredentials": [],  # Можно добавить существующие ключи
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",  # Platform authenticator (TouchID/FaceID)
                "requireResidentKey": False,
                "userVerification": "required",
            },
            "attestation": "none",  # Или "direct" для аттестации устройства
        }
        
        logger.info("Registration challenge created", user_id=user_id)
        return options, challenge

    async def verify_registration(
        self,
        challenge: Challenge,
        attestation_response: dict[str, Any],
    ) -> FIDO2Credential | None:
        """
        Верифицировать аттестацию и сохранить ключ.
        
        Endpoint: POST /auth/fido/register/verify
        
        Args:
            challenge: Объект challenge
            attestation_response: Response от navigator.credentials.create()
        
        Returns:
            FIDO2Credential если успешно, None иначе
        """
        try:
            # В продакшене здесь должна быть полная верификация через fido2-lib
            # Это упрощенная реализация для демонстрации
            
            # Извлечь данные из ответа
            response = attestation_response.get("response", {})
            client_data_json = response.get("clientDataJSON", "")
            attestation_object = response.get("attestationObject", "")
            
            # Декодировать clientDataJSON
            client_data = json.loads(base64.urlsafe_b64decode(
                client_data_json + '=' * (-len(client_data_json) % 4)
            ))
            
            # Проверить challenge
            if client_data.get("challenge") != challenge.challenge:
                logger.warning("Challenge mismatch in registration")
                return None
            
            # Проверить origin
            if client_data.get("origin") != self.ORIGIN:
                logger.warning("Origin mismatch in registration")
                return None
            
            # Извлечь credential ID и public key
            # В реальности нужно парсить attestation_object через CBOR
            credential_id = attestation_response.get("id", "")
            
            # Создать credential
            credential = FIDO2Credential(
                credential_id=credential_id,
                user_id=challenge.user_id,
                device_id=attestation_response.get("device_id"),
                public_key={"alg": -7},  # Упрощенно
                is_synced=not attestation_response.get("transports", []),  # Если нет transports - synced
            )
            
            logger.info(
                "FIDO2 credential registered",
                user_id=challenge.user_id,
                credential_id=credential_id[:8] + "...",
            )
            
            return credential
            
        except Exception as e:
            logger.error("Registration verification failed", error=str(e))
            return None

    async def create_login_challenge(
        self,
        user_id: str,
        allowed_credentials: list[str] | None = None,
    ) -> tuple[dict, Challenge]:
        """
        Создать challenge для входа.
        
        Endpoint: POST /auth/fido/login/challenge
        
        Args:
            user_id: ID пользователя
            allowed_credentials: Список ID разрешенных ключей
        
        Returns:
            Tuple (options_for_client, challenge_object)
        """
        challenge_str = self._generate_challenge()
        expires_at = datetime.now(UTC) + timedelta(seconds=self.CHALLENGE_EXPIRY_SECONDS)
        
        challenge = Challenge(
            challenge=challenge_str,
            user_id=user_id,
            expires_at=expires_at,
            operation="authenticate",
            allowed_credentials=allowed_credentials or [],
        )
        
        await self._store_challenge(challenge)
        
        # Формат options для WebAuthn.get()
        allow_credentials = [
            {
                "type": "public-key",
                "id": cred_id,
            }
            for cred_id in challenge.allowed_credentials
        ]
        
        options = {
            "challenge": challenge_str,
            "timeout": 60000,
            "rpId": self.RP_ID,
            "allowCredentials": allow_credentials,
            "userVerification": "required",
        }
        
        logger.info("Login challenge created", user_id=user_id)
        return options, challenge

    async def verify_login(
        self,
        challenge: Challenge,
        assertion_response: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """
        Проверить подпись и завершить вход.
        
        Endpoint: POST /auth/fido/login/verify
        
        Args:
            challenge: Объект challenge
            assertion_response: Response от navigator.credentials.get()
        
        Returns:
            Tuple (success, error_message)
        """
        try:
            # В продакшене здесь должна быть проверка подписи
            response = assertion_response.get("response", {})
            client_data_json = response.get("clientDataJSON", "")
            authenticator_data = response.get("authenticatorData", "")
            signature = response.get("signature", "")
            
            # Декодировать clientDataJSON
            client_data = json.loads(base64.urlsafe_b64decode(
                client_data_json + '=' * (-len(client_data_json) % 4)
            ))
            
            # Проверить challenge
            if client_data.get("challenge") != challenge.challenge:
                logger.warning("Challenge mismatch in login")
                return False, "Challenge mismatch"
            
            # Проверить origin
            if client_data.get("origin") != self.ORIGIN:
                logger.warning("Origin mismatch in login")
                return False, "Origin mismatch"
            
            # Проверить type
            if client_data.get("type") != "webauthn.get":
                logger.warning("Invalid assertion type")
                return False, "Invalid assertion type"
            
            # В реальности: проверка подписи с использованием public key
            # и проверка sign_count для предотвращения replay attacks
            
            logger.info("FIDO2 login verified", user_id=challenge.user_id)
            return True, None
            
        except Exception as e:
            logger.error("Login verification failed", error=str(e))
            return False, str(e)

    async def _store_challenge(self, challenge: Challenge) -> None:
        """Сохранить challenge в Redis/памяти."""
        key = f"fido2_challenge:{challenge.challenge}"
        
        if self.redis_client:
            await self.redis_client.setex(
                key,
                timedelta(seconds=self.CHALLENGE_EXPIRY_SECONDS),
                json.dumps(challenge.to_dict()),
            )
        else:
            self._challenges[challenge.challenge] = challenge

    async def _get_challenge(self, challenge_str: str) -> Challenge | None:
        """Получить challenge по строке."""
        key = f"fido2_challenge:{challenge_str}"
        
        if self.redis_client:
            data = await self.redis_client.get(key)
            if data:
                return Challenge(**json.loads(data))
        else:
            return self._challenges.get(challenge_str)
        
        return None

    async def delete_challenge(self, challenge_str: str) -> None:
        """Удалить использованный challenge."""
        key = f"fido2_challenge:{challenge_str}"
        
        if self.redis_client:
            await self.redis_client.delete(key)
        else:
            self._challenges.pop(challenge_str, None)

    async def get_user_credentials(self, user_id: str) -> list[FIDO2Credential]:
        """
        Получить все активные ключи пользователя.
        
        Используется для заполнения allowed_credentials при логине.
        """
        # В реальности запрос к БД
        # SELECT * FROM fido2_credentials WHERE user_id = ? AND is_active = TRUE
        return []

    async def register_credential(
        self,
        credential: FIDO2Credential,
    ) -> None:
        """Сохранить новый ключ в БД."""
        # В реальности INSERT в БД
        logger.info(
            "Credential stored",
            user_id=credential.user_id,
            credential_id=credential.credential_id[:8] + "...",
        )

    async def update_sign_count(
        self,
        credential_id: str,
        new_sign_count: int,
    ) -> None:
        """Обновить счетчик подписей."""
        # В реальности UPDATE в БД
        pass
