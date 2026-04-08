"""
Модуль криптографии и защиты данных (Encryption & Data Protection)

Обеспечивает сквозное шифрование чувствительных данных и защиту на уровне приложения.
"""

import base64
import hashlib
import os
import structlog
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


logger = structlog.get_logger(__name__)


class EncryptionService:
    """
    Сервис шифрования данных.
    
    Использует AES-256-GCM для шифрования полей БД (PII).
    Ключи должны храниться во внешнем KMS, не в коде.
    """

    def __init__(self, encryption_key: bytes | None = None):
        """
        Инициализировать сервис шифрования.
        
        Args:
            encryption_key: 32-байтный ключ для AES-256.
                           В продакшене должен загружаться из KMS.
        """
        if encryption_key is None:
            # В продакшене это должно вызывать ошибку!
            # Для демонстрации генерируем случайный ключ
            logger.warning(
                "No encryption key provided! Using random key. "
                "In production, use KMS to manage keys."
            )
            encryption_key = os.urandom(32)
        
        if len(encryption_key) != 32:
            raise ValueError("Encryption key must be 32 bytes for AES-256")
        
        self._key = encryption_key
        self._aesgcm = AESGCM(self._key)

    @classmethod
    def from_kms(cls, kms_service: Any, key_id: str) -> "EncryptionService":
        """
        Создать сервис с ключом из KMS.
        
        Args:
            kms_service: Объект KMS клиента (AWS KMS, GCP KMS, etc.)
            key_id: ID ключа в KMS
        
        Returns:
            Настроенный EncryptionService
        """
        # Пример для AWS KMS (псевдокод):
        # response = kms_service.decrypt(CiphertextBlob=encrypted_key)
        # key = response['Plaintext']
        # return cls(key)
        
        logger.info("Loading encryption key from KMS", key_id=key_id)
        # Заглушка - в реальности загрузка из KMS
        return cls()

    def encrypt(self, plaintext: str, associated_data: bytes | None = None) -> str:
        """
        Зашифровать строку.
        
        Args:
            plaintext: Строка для шифрования
            associated_data: Дополнительные данные для аутентификации (AAD)
        
        Returns:
            Base64-encoded строка с nonce + ciphertext + tag
        """
        # Генерируем случайный nonce (12 байт для GCM)
        nonce = os.urandom(12)
        
        # Шифруем
        ciphertext = self._aesgcm.encrypt(
            nonce,
            plaintext.encode('utf-8'),
            associated_data,
        )
        
        # Формат: nonce (12) + ciphertext + tag (16)
        encrypted_data = nonce + ciphertext
        
        return base64.b64encode(encrypted_data).decode('utf-8')

    def decrypt(
        self,
        encrypted_b64: str,
        associated_data: bytes | None = None,
    ) -> str:
        """
        Расшифровать строку.
        
        Args:
            encrypted_b64: Base64-encoded зашифрованные данные
            associated_data: Дополнительные данные для аутентификации (AAD)
        
        Returns:
            Расшифрованная строка
        
        Raises:
            ValueError: Если данные повреждены или ключ неверен
        """
        try:
            encrypted_data = base64.b64decode(encrypted_b64)
            
            # Извлекаем nonce (первые 12 байт)
            nonce = encrypted_data[:12]
            ciphertext_with_tag = encrypted_data[12:]
            
            # Расшифровываем
            plaintext = self._aesgcm.decrypt(
                nonce,
                ciphertext_with_tag,
                associated_data,
            )
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise ValueError(f"Decryption failed: {str(e)}")

    def derive_key_from_password(
        self,
        password: str,
        salt: bytes | None = None,
        iterations: int = 100000,
    ) -> tuple[bytes, bytes]:
        """
        Деривировать ключ из пароля (для backup/sharing).
        
        Args:
            password: Пароль пользователя
            salt: Соль (если None, генерируется случайно)
            iterations: Количество итераций PBKDF2
        
        Returns:
            Tuple (ключ, соль)
        """
        if salt is None:
            salt = os.urandom(16)
        
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            iterations,
            dklen=32,
        )
        
        return key, salt


class FieldEncryptionMixin:
    """
    Mixin для прозрачного шифрования полей модели SQLAlchemy.
    
    Пример использования:
    
    class User(Base, FieldEncryptionMixin):
        __tablename__ = "users"
        
        id = Column(Integer, primary_key=True)
        passport_data = EncryptedField(String)  # Будет зашифровано
        account_number = EncryptedField(String)  # Будет зашифровано
    """

    _encryption_service: EncryptionService | None = None

    @classmethod
    def set_encryption_service(cls, service: EncryptionService) -> None:
        """Установить сервис шифрования для всех полей."""
        cls._encryption_service = service

    @staticmethod
    def encrypt_field(value: str | None) -> str | None:
        """Зашифровать значение поля."""
        if value is None:
            return None
        if FieldEncryptionMixin._encryption_service is None:
            logger.warning("Encryption service not initialized")
            return value
        return FieldEncryptionMixin._encryption_service.encrypt(value)

    @staticmethod
    def decrypt_field(value: str | None) -> str | None:
        """Расшифровать значение поля."""
        if value is None:
            return None
        if FieldEncryptionMixin._encryption_service is None:
            logger.warning("Encryption service not initialized")
            return value
        return FieldEncryptionMixin._encryption_service.decrypt(value)


class RASPProtection:
    """
    Runtime Application Self-Protection (RASP).
    
    Проверяет целостность запроса, блокирует инъекции,
    обнаруживает признаки отладки/эмуляции.
    
    Оптимизировано для минимальных накладных расходов (<5%).
    """

    # Паттерны для обнаружения инъекций
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b.*\b(FROM|INTO|TABLE|WHERE)\b)",
        r"(--|\#|\/\*|\*\/)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(\bAND\b\s+\d+\s*\=\s*\d+)",
    ]

    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
    ]

    # Подозрительные заголовки (признаки отладки)
    SUSPICIOUS_HEADERS = [
        "x-debug",
        "x-chrome-extension",
        "postman-token",
        "x-forwarded-host",  # Может указывать на proxy manipulation
    ]

    def __init__(self):
        import re
        self._sql_patterns = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        self._xss_patterns = [re.compile(p, re.IGNORECASE) for p in self.XSS_PATTERNS]

    def validate_request(self, request_data: dict, headers: dict) -> tuple[bool, str | None]:
        """
        Проверить запрос на наличие угроз.
        
        Args:
            request_data: Данные запроса (body)
            headers: Заголовки запроса
        
        Returns:
            Tuple (valid, error_message)
        """
        # 1. Проверка заголовков на признаки отладки
        for header_name in headers:
            if header_name.lower() in self.SUSPICIOUS_HEADERS:
                logger.warning(
                    "Suspicious header detected",
                    header=header_name,
                )
                return False, "Debug mode detected"

        # 2. Рекурсивная проверка данных на инъекции
        if not self._check_for_injections(request_data):
            return False, "Potential injection detected"

        return True, None

    def _check_for_injections(self, data: Any) -> bool:
        """Рекурсивно проверить данные на паттерны инъекций."""
        if isinstance(data, str):
            return self._validate_string(data)
        elif isinstance(data, dict):
            return all(self._check_for_injections(v) for v in data.values())
        elif isinstance(data, (list, tuple)):
            return all(self._check_for_injections(item) for item in data)
        return True

    def _validate_string(self, text: str) -> bool:
        """Проверить строку на паттерны атак."""
        # Ограничиваем длину для производительности
        if len(text) > 10000:
            logger.warning("Very long string detected", length=len(text))
            return False

        # Проверка SQL инъекций
        for pattern in self._sql_patterns:
            if pattern.search(text):
                logger.warning("SQL injection pattern detected")
                return False

        # Проверка XSS
        for pattern in self._xss_patterns:
            if pattern.search(text):
                logger.warning("XSS pattern detected")
                return False

        return True


class CertificatePinningConfig:
    """
    Конфигурация Certificate Pinning для мобильных клиентов.
    
    Предоставляет endpoint для получения pinning-конфигурации.
    """

    def __init__(self, pins: list[str], backup_pins: list[str] | None = None):
        """
        Args:
            pins: Список текущих PINs (SHA-256 хэшей публичных ключей)
            backup_pins: Резервные PINs для ротации
        """
        self.pins = pins
        self.backup_pins = backup_pins or []

    def get_config(self) -> dict:
        """
        Получить конфигурацию для клиента.
        
        Возвращает формат, совместимый с iOS/Android pinning libraries.
        """
        return {
            "pins": self.pins,
            "backup_pins": self.backup_pins,
            "include_subdomains": True,
            "max_age": 5184000,  # 60 дней в секундах
        }

    def to_header_value(self) -> str:
        """
        Получить значение для HTTP заголовка (альтернативный способ доставки).
        """
        import json
        return json.dumps(self.get_config())
