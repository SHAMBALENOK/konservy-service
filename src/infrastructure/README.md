# Infrastructure Layer (External Services)

Реализация технических деталей и интеграций с внешними системами.

## Здесь
- **Database**: Создание engine, session factory, подключение к PostgreSQL.
- **Cache**: Клиент Redis для кэширования и хранения idempotency keys.
- **External APIs**: Клиенты для платежных шлюзов, SMS-провайдеров, KYC-сервисов.
- **Audit & Logging**: Настройка структурированного логирования с маскированием PII.
- **Tasks**: Конфигурация Celery/ARQ для фоновых задач.
