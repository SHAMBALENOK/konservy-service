# konservy-service
Bank actives safety application
```
src/
├── api/               # Маршруты, middleware, Pydantic-схемы запросов/ответов
├── core/              # Бизнес-логика, управление транзакциями, сервисы
├── models/            # SQLAlchemy-модели + DTO/схемы (Pydantic)
├── infrastructure/    # Сессии БД, кэш, внешние клиенты, audit-логгер, idempotency
├── config/            # Pydantic Settings, .env, feature-flags
└── main.py            # Factory приложения, DI, startup/shutdown
tests/
├── unit/              # core/ без внешних зависимостей
├── integration/       # БД, API-эндпоинты, транзакционные сценарии
└── conftest.py        # Фикстуры, тестовая БД, моки внешних сервисов
```
