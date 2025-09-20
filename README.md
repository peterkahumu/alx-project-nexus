# 🛍️ E-Commerce Platform
![Django](https://img.shields.io/badge/Django-5.2.4-green)  ![Python](https://img.shields.io/badge/Python-3.12-blue)  ![License](https://img.shields.io/badge/license-MIT-blue)

---
## Video Demo

[![Ecommerce](ecommerce.jpg)](https://youtu.be/ryWBLfCvIAE)
---

## 📌 Quick summary
The project is a simple yet complete e-commerce platform with the following functionality:

> 1. **Product Browsing** --> Users can view available items on the platform.
> 2. **Shopping Cart** --> Registered users can add items to their cart.
> 3. **Order Management** --> Registered users can place and manage their orders.
> 4. **Secure Payments** --> Users can pay using bank cards or mobile money services.

On the **Admin side**, administrators have full **CRUD operations**, enabling them to manage products, orders, users, and payments, as well as customize the platform to meet specific business needs.

---

## 📋 Table of contents

* [Microservices layout](#-microservices-layout)
* [Architecture overview (detailed)](#-architecture-overview-detailed)

  * [High-level component diagram](#high-level-component-diagram)
  * [Checkout & payment sequence](#checkout--payment-sequence)
  * [Order / Payment state machine](#order--payment-state-machine)
  * [Data ownership & boundaries](#data-ownership--boundaries)
  * [Synchronous vs asynchronous flows](#synchronous-vs-asynchronous-flows)
  * [Deployment patterns & suggestions](#deployment-patterns--suggestions)
  * [Security & Operational considerations](#security--operational-considerations)
  * [Observability & monitoring](#observability--monitoring)
  * [Env var checklist & CI/CD notes](#env-var-checklist--cicd-notes)
* [Links to app READMEs](#links-to-app-readmes)

---

## 🔀 Microservices layout

This repo is a single Django project arranged as modular apps (microservices-style):

* `users/` — auth, registration, JWT, email verification, rate limiting
* `products/` — categories, products, images, admin-only writes
* `cart/` — user carts & items, cart business rules
* `orders/` — convert cart → order, order lifecycle, tax & shipping
* `payments/` — payment initiation, verification, webhooks, providers

Each app owns its models, serializers, and viewsets. Cross-app interactions happen through DB ownership, Django signals, and Celery tasks (asynchronously).
---

## 🏗️ Architecture overview (detailed)

### High-level component diagram

```mermaid
flowchart LR
  subgraph client_side[Client]
    A[Browser / Mobile App]
  end

  subgraph edge[Edge]
    NGINX[NGINX / ALB]
  end

  subgraph web[Web Tier]
    G[Gunicorn / Uvicorn]
    DJ[ecommerce Django app]
  end

  subgraph apps[App Modules]
    U[Users App]
    P[Products App]
    C[Cart App]
    O[Orders App]
    M[Payments App]
  end

  subgraph infra[Infrastructure]
    PG[(Postgres DB)]
    REDIS[(Redis — cache & broker)]
    CELERY[Celery Workers]
    S3[(S3 / Object Storage)]
    SMTP[SMTP / Transactional Email]
    PP[Payment Providers]
    CDN[CDN — Static & Media]
    SENTRY[Sentry / Error Tracking]
    PROM[Prometheus]
  end

  A -->|HTTPS| NGINX --> G --> DJ
  DJ --> U & P & C & O & M
  DJ --> PG
  DJ --> REDIS
  DJ --> S3
  DJ --> SMTP
  M --> PP
  CELERY --> PG
  CELERY --> SMTP
  DJ -->|metrics| PROM
  DJ -->|errors| SENTRY
  S3 --> CDN
```

*Notes:*

* All app URLs are routed by the Django project `urls.py`; apps expose DRF viewsets under their API namespaces (`/api/...`).
* Static/media served via CDN/S3 in prod; locally via `MEDIA_ROOT`.

---

### Checkout & payment sequence (detailed)

```mermaid
sequenceDiagram
    participant U as User
    participant B as Browser
    participant API as Django API
    participant PG as Postgres
    participant Cel as Celery
    participant Provider as Payment Provider

    U->>B: Click "Checkout"
    B->>API: POST /orders/create-order/ (auth)
    API->>PG: Validate cart & create Order (atomic)
    API-->>B: 200 OK {order_id, order_total}
    B->>API: POST /payments/initiate/<order_id>/ {provider}
    API->>M: Payments app validates order & creates Payment record (pending)
    API->>Provider: Create transaction (redirect/checkout url)
    Provider-->>B: Provides checkout URL (or inline widget)
    B->>Provider: User pays
    Provider-->>API: Webhook POST /payments/verify/<provider>/ (signed)
    API->>M: Verify webhook signature & amount
    alt verification ok
      API->>PG: mark Payment.success, update Order.payment_status (atomic)
      API->>Cel: queue order fulfillment tasks
      Cel->>SMTP: send receipt email
      API-->>Provider: 200 OK
    else failed
      API->>PG: mark Payment.failed, Order.payment_status=failed
      API-->>Provider: 200 OK
    end
    API-->>B: User sees updated order status via polling or websocket
```

**Idempotency & Safety:** Webhook handling must be idempotent (use `tx_ref` + DB unique constraint) and verify signatures.

---

### Order / Payment state machine

```mermaid
stateDiagram-v2
    [*] --> pending: order created
    pending --> processing: payment initiated
    processing --> success: payment verified
    processing --> failed: payment failed or timeout
    success --> shipped: fulfillment done
    shipped --> delivered
    pending --> cancelled: user cancel (rules)
    processing --> cancelled: only if provider allows
```

**Notes:**

> * Cancellation rules: only `pending` or `processing` may be cancelled depending on payment/provider and order warehouse state.
> * Use `transaction.atomic()` for transitions that touch Order + Payment.

---

### Data ownership & boundaries

| App        | Models (examples)            | Primary responsibility                          |
| ---------- | ---------------------------- | ----------------------------------------------- |
| `users`    | `User (UUID)`, `UserProfile` | Auth, registration, tokens, roles               |
| `products` | `Category`, `Product`        | Catalog, pricing, images, slugs                 |
| `cart`     | `Cart`, `CartItem`           | In-memory shopping session persisted to DB      |
| `orders`   | `Order`, `OrderItem`         | Order lifecycle, taxes, shipping                |
| `payments` | `Payment`, `PaymentAttempt`  | Provider integration, webhooks, reconciliations |

*Principle:* each app owns its DB tables and logic. Cross-app reads are allowed, writes should be done by owning app or via well-defined APIs/tasks.

---

### Synchronous vs asynchronous flows

**Synchronous**

* Product listing, cart CRUD, auth endpoints (fast API responses)
* Order creation: validate cart synchronously and persist order record

**Asynchronous**

* Email sending (Celery)
* Payment reconciliation and retries
* Order fulfillment (warehouse integration)
* Heavy reconciliation or report generation

Use Celery with Redis as broker. Keep worker tasks idempotent and short.

---

## 🚢 Deployment patterns & suggestions

Two recommended approaches:

### 1) Docker Compose — local / staging (simple)

* Services: `web` (gunicorn), `worker` (celery), `postgres`, `redis`, `minio` (local S3), `smtp` (mailhog)
* Volumes for media in dev, use S3 in production
* `supervisord` used in Dockerfile to run multiple processes if needed (web + celery cron), but prefer separate containers per process in prod

### 2) Kubernetes — production (recommended for scale)

* Deployments: `web` (replicas 2+), `worker` (autoscale), `cronworker`
* StatefulSet or managed RDS for Postgres with read replicas
* Managed Redis (AWS Elasticache / GCP Memorystore)
* Use HorizontalPodAutoscaler, liveness/readiness probes
* Ingress (NGINX / managed LB), TLS via cert-manager
* Secrets stored in K8s Secret or cloud secret manager

**Storage & Media**

* Use S3/Cloud object storage + CDN for static & media
* Avoid storing media on the web pod filesystem in prod

**Scaling tips**

* Cache product lists & category endpoints (use Redis) with short TTLs and cache invalidation on updates
* Move long-running tasks to celery workers
* Read replicas for heavy read load


## ⚠️ Failure modes & mitigations (practical)

* **Duplicate webhooks / retries**: enforce idempotency via `tx_ref` unique index + upsert semantics
* **Provider downtime**: queue payment attempts, fallback to manual reconciliation; fail fast UX message
* **Partial failures (order created but payment failed)**: mark `order.payment_status=failed`; enable retry flow
* **Large DB writes during peak**: throttle writes (rate limit checkout), use queueing

---

## 🔁 CI/CD & local developer ergonomics

* Pre-commit: `black`, `isort`, `flake8`, `mypy` (configured in `.pre-commit-config.yaml`)
* GitHub Actions / GitLab CI: tests on PR, lint, mypy, build docker image
* DB migrations in CI: run `python manage.py migrate --check` or use `django-test-migrations` for safe migrations
* Use ephemeral review apps for PR previews

---

## 🧾 Env var checklist

Minimum envs to set (in `.env` or secret manager):

```
SECRET_KEY=
DATABASE_URL=postgres://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0
CELERY_BROKER_URL=${REDIS_URL}
ALLOWED_HOSTS=example.com
DEBUG=False
EMAIL_HOST=mail.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=hello@example.com
AWS_S3_BUCKET_NAME=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
PAYMENTS_CHAPA_KEY=
PAYMENTS_PAYSTACK_KEY=
PAYMENTS_MPESA_KEY=
```

---

## 🔗 Links to app READMEs (detailed docs live there)

* [Users](users/README.md) — Auth, registration, tokens, tests
* [Products](products/README.md) — Catalog, slugs, admin-only writes
* [Cart](cart/README.md) — Cart endpoints, item rules
* [Orders](orders/README.md) — Checkout, taxes, cancellations
* [Payments](payments/README.md) — Providers, webhooks, reconciliation

---