# 🔐 E-Commerce Authentication Service

![Django](https://img.shields.io/badge/Django-5.2.4-green)
![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue)

## 📋 Table of Contents
- [Features](#-features)
- [Architecture](#-architecture)
- [API Documentation](#-api-documentation)
- [Testing](#-testing)
- [Security](#-security)

---

## ✨ Features

### User Management
| Feature | Endpoint | Description |
|---------|----------|-------------|
| **User Registration** | `POST /api/users/register/` | Create new accounts with email verification |
| **Email Verification** | `GET /api/users/confirm-email/` | Confirm email addresses with secure tokens |
| **Resend Activation** | `POST /api/users/resend-activation-email/` | Re-send verification emails |

### Authentication
| Feature | Endpoint | Description |
|---------|----------|-------------|
| **Dual Login** | `POST /api/users/login/` | Login via email OR username |
| **Token Refresh** | `POST /api/users/refresh-session/` | Renew expired access tokens |

### Password Management
| Feature | Endpoint | Description |
|---------|----------|-------------|
| **Password Reset** | `POST /api/users/password-reset/` | Initiate password reset flow |
| **Reset Confirmation** | `POST /api/users/password-reset-confirm/` | Complete password change |

### Security Features
- UUID primary keys
- Rate-limited endpoints
- JWT token encryption
- Soft delete functionality

---

## 🏗️ Architecture

### System Flow
```mermaid
sequenceDiagram
    participant User
    participant API
    participant DB
    participant Celery
    
    User->>API: POST /register/
    API->>DB: Save user (inactive)
    API->>Celery: Send verification email
    Celery->>User: Email with token
    User->>API: GET /confirm-email/?token=XYZ
    API->>DB: Activate user
```

### Component Diagram
```mermaid
flowchart LR
    A[Client] --> B[DRF API]
    B --> C[(PostgreSQL)]
    B --> D[Celery]
    D --> E[Redis]
    D --> F[SMTP]
```

---

## 📡 API Documentation

### Endpoint Reference
| Endpoint | Method | Parameters | Success Response |
|----------|--------|------------|------------------|
| `POST /api/users/register/` | POST | `email`, `username`, `password` | `201 Created` |
| `GET /api/users/confirm-email/` | GET | `uid`, `token` | `200 OK` |
| `POST /api/users/login/` | POST | `username`, `password` | JWT tokens |

**Example Login:**
```http
POST /api/users/login/
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "access": "eyJhb...",
  "refresh": "eyJhb...",
  "role": "customer"
}
```

---

## 🧪 Testing
```bash
# Run all tests
python manage.py test users

# run tests with coverage
pytest --cov=users --cov-fail-under=90
```

---

## 🔒 Security
- **Password Hashing**: PBKDF2 w/ 20k iterations
- **Token Lifetime**: 30m access, 24h refresh

---

**📜 License:** MIT  
**🔄 Last Updated:** August 2nd, 2025
