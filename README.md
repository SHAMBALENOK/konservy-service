# Banking API - Production-Ready FastAPI Backend

## 📁 Project Structure

```
/
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
│   │   ├── fido_auth.py       # FIDO2/WebAuthn endpoints
│   │   ├── accounts.py        # Account endpoints
│   │   ├── transactions.py    # Transaction endpoints
│   │   └── security.py        # Telemetry & Security endpoints
│   └── main.py                # App initialization
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── render.yaml
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🌐 API Endpoints

### Base URL
```
/api/v1
```

### Health & Root
```
GET  /health                    # Health check
GET  /                          # API information
GET  /docs                      # Swagger UI documentation
GET  /redoc                     # ReDoc documentation
GET  /openapi.json              # OpenAPI schema
```

---

### 🔐 Authentication (`/api/v1/auth`)

```
POST /api/v1/auth/register              # Register new user
POST /api/v1/auth/login                 # Login (OAuth2) - returns access & refresh tokens
POST /api/v1/auth/refresh               # Refresh access token
```

#### FIDO2 / Passkeys Authentication (`/api/v1/auth/fido`)

```
POST /api/v1/auth/fido/register/challenge      # Generate registration challenge
POST /api/v1/auth/fido/register/verify         # Verify FIDO2 attestation
POST /api/v1/auth/fido/login/challenge         # Generate login challenge
POST /api/v1/auth/fido/login/verify            # Verify FIDO2 assertion & get tokens
GET  /api/v1/auth/fido/credentials             # List user's FIDO2 credentials
DELETE /api/v1/auth/fido/credentials/{id}      # Revoke a credential
```

---

### 👤 Accounts (`/api/v1/accounts`)

```
POST   /api/v1/accounts/                       # Create new account
GET    /api/v1/accounts/                       # List all accounts (paginated)
GET    /api/v1/accounts/{account_id}           # Get account details
GET    /api/v1/accounts/user/{user_id}         # Get account by user ID
PATCH  /api/v1/accounts/{account_id}           # Update account
POST   /api/v1/accounts/{account_id}/deposit   # Deposit funds
POST   /api/v1/accounts/{account_id}/withdraw  # Withdraw funds
DELETE /api/v1/accounts/{account_id}           # Deactivate account
```

**Required Headers:**
- `X-Idempotency-Key` - Required for deposit/withdraw operations

---

### 💸 Transactions (`/api/v1/transactions`)

```
POST /api/v1/transactions/transfer              # Transfer funds between accounts
POST /api/v1/transactions/deposit               # Deposit funds to account
GET  /api/v1/transactions/                      # List all transactions (paginated)
GET  /api/v1/transactions/{transaction_id}      # Get transaction details
GET  /api/v1/transactions/account/{account_id}  # Get account transactions
```

**Required Headers:**
- `X-Idempotency-Key` - Required for transfer/deposit operations

**Query Parameters:**
- `current_user` - Source user ID (for transfers)

---

### 🛡️ Telemetry & Security (`/api/v1/telemetry`)

```
POST   /api/v1/telemetry/session                # Collect session telemetry
GET    /api/v1/telemetry/security/history       # Get security event history
GET    /api/v1/telemetry/devices                # List user devices
DELETE /api/v1/telemetry/devices/{device_id}    # Revoke device access
POST   /api/v1/telemetry/devices/{device_id}/trust  # Mark device as trusted
GET    /api/v1/telemetry/certificate-pinning    # Get certificate pinning config
```

---

## 🚀 Deployment

### Render Deployment

1. Connect your GitHub repository to [Render](https://render.com)
2. Create a new Web Service
3. Use the provided `render.yaml` configuration
4. Set required environment variables:
   - `DATABASE_URL` - PostgreSQL connection string
   - `REDIS_URL` - Redis connection string
   - `SECRET_KEY` - Random secret for JWT signing
   - `CORS_ORIGINS` - Comma-separated list of allowed origins

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `SECRET_KEY` | JWT signing secret | Required |
| `APP_NAME` | Application name | Banking API |
| `DEBUG` | Debug mode | false |
| `API_PREFIX` | API prefix | /api/v1 |
| `PORT` | Server port | 8000 |
| `CORS_ORIGINS` | Allowed CORS origins | [] |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiry | 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token expiry | 7 |

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t banking-api .
docker run -p 8000:8000 --env-file .env banking-api
```

---

## 📄 Core Configuration & Security

### `app/core/config.py`
