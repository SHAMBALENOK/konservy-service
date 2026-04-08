# Banking API - Production-Ready FastAPI Backend

## 📁 Project Structure

```
banking_api/
├── alembic/
│   ├── versions/
│   │   └── 001_initial_schema.py
│   ├── env.py
│   └── script.py.mako
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Pydantic Settings
│   │   ├── security.py        # JWT, password hashing
│   │   └── exceptions.py      # Custom error handlers
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── idempotency.py     # Idempotency middleware
│   │   └── rate_limiter.py    # Rate limiting
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py            # SQLAlchemy base
│   │   ├── account.py         # Account model
│   │   └── transaction.py     # Transaction model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── account.py         # Pydantic schemas for accounts
│   │   ├── transaction.py     # Pydantic schemas for transactions
│   │   └── common.py          # Common response schemas
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py            # Generic repository
│   │   ├── account.py         # Account repository
│   │   └── transaction.py     # Transaction repository
│   ├── services/
│   │   ├── __init__.py
│   │   ├── account.py         # Account business logic
│   │   └── transaction.py     # Transaction business logic
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── accounts.py        # Account endpoints
│   │   └── transactions.py    # Transaction endpoints
│   └── main.py                # App initialization
├── alembic.ini
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```

---

## 📄 Core Configuration & Security

### `app/core/config.py`
