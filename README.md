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

#### Register New User
**POST** `/api/v1/auth/register`

**Request Body:**
```json
{
  "username": "string (1-255 chars)",
  "password": "string (8-128 chars)"
}
```

**Success Response (201 Created):**
```json
{
  "message": "User registered successfully",
  "username": "john_doe"
}
```

**Error Responses:**
- `409 Conflict` - Username already registered
```json
{
  "code": "CONFLICT",
  "message": "Username already registered",
  "trace_id": "uuid-string",
  "details": null
}
```

---

#### Login (OAuth2)
**POST** `/api/v1/auth/login`

**Request Body (form-data):**
```
username: string
password: string
```

**Success Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid credentials
```json
{
  "code": "INVALID_CREDENTIALS",
  "message": "Incorrect username or password",
  "trace_id": "uuid-string",
  "details": null
}
```
- `401 Unauthorized` - User inactive
```json
{
  "code": "USER_INACTIVE",
  "message": "User account is deactivated",
  "trace_id": "uuid-string",
  "details": null
}
```

---

#### Refresh Token
**POST** `/api/v1/auth/refresh`

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Success Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid refresh token
```json
{
  "code": "MISSING_REFRESH_TOKEN",
  "message": "Refresh token required",
  "trace_id": "uuid-string",
  "details": null
}
```

---

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

#### Create New Account
**POST** `/api/v1/accounts/`

**Request Body:**
```json
{
  "user_id": "string (1-255 chars)",
  "currency": "USD",
  "initial_balance": "0.00"
}
```

**Field Descriptions:**
- `user_id`: Unique user identifier (required)
- `currency`: ISO 4217 currency code, default "USD" (3 characters)
- `initial_balance`: Initial deposit amount, must be >= 0 (decimal with 2 places)

**Success Response (201 Created):**
```json
{
  "id": 1,
  "account_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "account_number": "ACC-2024-0001",
  "balance": "1000.00",
  "currency": "USD",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
- `422 Unprocessable Entity` - Validation error
```json
{
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "trace_id": "uuid-string",
  "details": {
    "errors": [
      {
        "field": "body.initial_balance",
        "message": "ensure this value is greater than or equal to 0",
        "type": "greater_than_equal"
      }
    ]
  }
}
```

---

#### Get Account Details
**GET** `/api/v1/accounts/{account_id}`

**Path Parameters:**
- `account_id`: UUID of the account

**Success Response (200 OK):**
```json
{
  "id": 1,
  "account_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "account_number": "ACC-2024-0001",
  "balance": "1000.00",
  "currency": "USD",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
- `404 Not Found` - Account not found
```json
{
  "code": "NOT_FOUND",
  "message": "Account not found",
  "trace_id": "uuid-string",
  "details": null
}
```

---

#### Get Account by User ID
**GET** `/api/v1/accounts/user/{user_id}`

**Success Response (200 OK):**
```json
{
  "id": 1,
  "account_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "account_number": "ACC-2024-0001",
  "balance": "1000.00",
  "currency": "USD",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

#### List All Accounts (Paginated)
**GET** `/api/v1/accounts/`

**Query Parameters:**
- `skip`: Offset (default: 0, >= 0)
- `limit`: Limit (default: 100, 1-1000)

**Success Response (200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "account_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "user_123",
      "account_number": "ACC-2024-0001",
      "balance": "1000.00",
      "currency": "USD",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 100
}
```

---

#### Update Account
**PATCH** `/api/v1/accounts/{account_id}`

**Request Body:**
```json
{
  "is_active": false
}
```

**Success Response (200 OK):**
```json
{
  "id": 1,
  "account_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "account_number": "ACC-2024-0001",
  "balance": "1000.00",
  "currency": "USD",
  "is_active": false,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

---

#### Deposit Funds
**POST** `/api/v1/accounts/{account_id}/deposit`

**Required Headers:**
- `X-Idempotency-Key`: Unique key to prevent duplicate deposits

**Request Body:**
```json
{
  "amount": "100.00",
  "description": "Salary deposit",
  "reference": "SAL-2024-01"
}
```

**Field Descriptions:**
- `amount`: Amount to deposit (required, > 0, 2 decimal places)
- `description`: Optional description (max 500 chars)
- `reference`: Optional external reference (max 255 chars)

**Success Response (200 OK):**
```json
{
  "id": 1,
  "account_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "account_number": "ACC-2024-0001",
  "balance": "1100.00",
  "currency": "USD",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

**Error Responses:**
- `422 Unprocessable Entity` - Validation error (e.g., negative amount)

---

#### Withdraw Funds
**POST** `/api/v1/accounts/{account_id}/withdraw`

**Required Headers:**
- `X-Idempotency-Key`: Unique key to prevent duplicate withdrawals

**Request Body:**
```json
{
  "amount": "50.00",
  "description": "ATM withdrawal",
  "reference": "ATM-2024-01"
}
```

**Success Response (200 OK):**
```json
{
  "id": 1,
  "account_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "account_number": "ACC-2024-0001",
  "balance": "950.00",
  "currency": "USD",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:30:00Z"
}
```

**Error Responses:**
- `422 Unprocessable Entity` - Insufficient funds
```json
{
  "code": "INSUFFICIENT_FUNDS",
  "message": "Insufficient funds",
  "trace_id": "uuid-string",
  "details": null
}
```

---

#### Deactivate Account
**DELETE** `/api/v1/accounts/{account_id}`

**Success Response (204 No Content):**
No content returned.

**Error Responses:**
- `422 Unprocessable Entity` - Account has non-zero balance

---

### 💸 Transactions (`/api/v1/transactions`)

#### Transfer Funds Between Accounts
**POST** `/api/v1/transactions/transfer`

**Required Headers:**
- `X-Idempotency-Key`: Unique key to prevent duplicate transfers

**Query Parameters:**
- `current_user`: Source user ID (required)

**Request Body:**
```json
{
  "destination_account_id": "660e8400-e29b-41d4-a716-446655440001",
  "amount": "250.00",
  "currency": "USD",
  "description": "Payment for services",
  "reference": "PAY-2024-001"
}
```

**Field Descriptions:**
- `destination_account_id`: Target account UUID (required)
- `amount`: Transfer amount (required, > 0, 2 decimal places)
- `currency`: ISO 4217 currency code (optional, defaults to source account currency)
- `description`: Transfer description (optional, max 500 chars)
- `reference`: External reference number (optional, max 255 chars)

**Success Response (201 Created):**
```json
{
  "id": 1,
  "transaction_id": "770e8400-e29b-41d4-a716-446655440002",
  "type": "TRANSFER",
  "status": "PENDING",
  "source_account_id": "550e8400-e29b-41d4-a716-446655440000",
  "destination_account_id": "660e8400-e29b-41d4-a716-446655440001",
  "amount": "250.00",
  "currency": "USD",
  "description": "Payment for services",
  "reference": "PAY-2024-001",
  "idempotency_key": "unique-key-123",
  "failure_reason": null,
  "created_at": "2024-01-15T12:00:00Z",
  "updated_at": "2024-01-15T12:00:00Z",
  "processed_at": null
}
```

**Error Responses:**
- `404 Not Found` - Source account not found
- `422 Unprocessable Entity` - Insufficient funds or validation error

---

#### Deposit Funds to Account
**POST** `/api/v1/transactions/deposit`

**Required Headers:**
- `X-Idempotency-Key`: Unique key to prevent duplicate deposits

**Query Parameters:**
- `account_id`: Target account UUID (required)
- `amount`: Deposit amount (required, > 0)
- `currency`: Currency code (default: USD)
- `description`: Description (optional)
- `reference`: Reference (optional)

**Success Response (201 Created):**
```json
{
  "id": 1,
  "transaction_id": "770e8400-e29b-41d4-a716-446655440002",
  "type": "DEPOSIT",
  "status": "COMPLETED",
  "source_account_id": null,
  "destination_account_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": "500.00",
  "currency": "USD",
  "description": "Wire transfer deposit",
  "reference": "WIRE-2024-001",
  "idempotency_key": "unique-key-456",
  "failure_reason": null,
  "created_at": "2024-01-15T12:30:00Z",
  "updated_at": "2024-01-15T12:30:00Z",
  "processed_at": "2024-01-15T12:30:01Z"
}
```

---

#### Get Transaction Details
**GET** `/api/v1/transactions/{transaction_id}`

**Success Response (200 OK):**
```json
{
  "id": 1,
  "transaction_id": "770e8400-e29b-41d4-a716-446655440002",
  "type": "TRANSFER",
  "status": "COMPLETED",
  "source_account_id": "550e8400-e29b-41d4-a716-446655440000",
  "destination_account_id": "660e8400-e29b-41d4-a716-446655440001",
  "amount": "250.00",
  "currency": "USD",
  "description": "Payment for services",
  "reference": "PAY-2024-001",
  "idempotency_key": "unique-key-123",
  "failure_reason": null,
  "created_at": "2024-01-15T12:00:00Z",
  "updated_at": "2024-01-15T12:00:05Z",
  "processed_at": "2024-01-15T12:00:05Z"
}
```

---

#### List All Transactions (Paginated)
**GET** `/api/v1/transactions/`

**Query Parameters:**
- `skip`: Offset (default: 0, >= 0)
- `limit`: Limit (default: 100, 1-1000)

**Success Response (200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "transaction_id": "770e8400-e29b-41d4-a716-446655440002",
      "type": "TRANSFER",
      "status": "COMPLETED",
      "source_account_id": "550e8400-e29b-41d4-a716-446655440000",
      "destination_account_id": "660e8400-e29b-41d4-a716-446655440001",
      "amount": "250.00",
      "currency": "USD",
      "description": "Payment for services",
      "reference": "PAY-2024-001",
      "idempotency_key": "unique-key-123",
      "failure_reason": null,
      "created_at": "2024-01-15T12:00:00Z",
      "updated_at": "2024-01-15T12:00:05Z",
      "processed_at": "2024-01-15T12:00:05Z"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 100
}
```

---

#### Get Account Transactions
**GET** `/api/v1/transactions/account/{account_id}`

**Query Parameters:**
- `skip`: Offset (default: 0, >= 0)
- `limit`: Limit (default: 100, 1-1000)

**Success Response (200 OK):**
Same format as "List All Transactions"

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

## 📋 Standard Error Response Format

All errors follow a consistent format:

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "trace_id": "uuid-string-for-debugging",
  "details": {
    "additional": "error details if available"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NOT_FOUND` | 404 | Resource not found |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `CONFLICT` | 409 | Resource conflict (duplicate) |
| `BAD_REQUEST` | 400 | Invalid request |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `INSUFFICIENT_FUNDS` | 422 | Not enough funds |
| `INTERNAL_ERROR` | 500 | Server error |
| `DATABASE_ERROR` | 500 | Database operation failed |

---

## 🔑 Authentication

Most endpoints require authentication via JWT Bearer token. Include the token in the `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
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
