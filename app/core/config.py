from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@db/dbname")
    
    # Security Configuration (JWT, FIDO2)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "SUPER_SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 3600

    # FIDO2/Passkey Configuration (Placeholders for actual implementation details)
    FIDO2_VERIFICATION_URL: str = "http://localhost:8000/api/v1/auth/fido/register/challenge"
    
    # Rate Limiting Configuration
    RATE_LIMIT_MAX_REQUESTS: int = 100
    RATE_LIMIT_PERIOD_SECONDS: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()