# 💳 Payment Microservice

> A production-grade payment processing microservice built with **FastAPI**, **Event Sourcing**, **CQRS**, and **idempotency guarantees**.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────┐
│                   API Layer (FastAPI)                     │
│          POST /payments   GET /payments/:id/history       │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌─────────────┐ ┌────────────┐ ┌─────────────┐
   │ Idempotency │ │  Payment   │ │ Event Store  │
   │  (Redis)    │ │  Service   │ │ (PostgreSQL) │
   └─────────────┘ │  (CQRS)   │ └─────────────┘
                   └─────┬──────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       ┌─────────────┐     ┌──────────────┐
       │  PostgreSQL  │     │   RabbitMQ   │
       │  (payments + │     │  (domain     │
       │   events)    │     │   events)    │
       └─────────────┘     └──────────────┘
```

## ✨ Key Design Patterns

| Pattern | Implementation | Why |
|---|---|---|
| **Event Sourcing** | `PaymentEvent` append-only table | Full audit trail, time-travel queries |
| **CQRS** | Commands vs Queries in `PaymentService` | Separation of concerns, scalability |
| **Idempotency** | Redis distributed lock + cache | Safe retries, no duplicate payments |
| **Repository** | `PaymentRepository` | Testable, decoupled data access |

## 🚀 Quick Start
```bash
git clone https://github.com/Carlos-Maliqueo/payment-microservice
cd payment-microservice
docker-compose up --build
```

API docs: **http://localhost:8000/docs**
RabbitMQ UI: **http://localhost:15672** (guest/guest)

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/payments/` | Create a payment |
| GET | `/api/v1/payments/` | List payments |
| GET | `/api/v1/payments/{id}` | Get payment by ID |
| POST | `/api/v1/payments/{id}/process` | Process a payment |
| POST | `/api/v1/payments/{id}/refund` | Refund a payment |
| POST | `/api/v1/payments/{id}/cancel` | Cancel a payment |
| GET | `/api/v1/payments/{id}/history` | Full event history |

## 🔒 Idempotency Flow
```
Client sends POST /payments (idempotency_key: "order-123")
    │
    ├─► Redis cache hit? ──► Return cached response ✅
    │
    ├─► Acquire Redis lock ──► Lock busy? ──► 409 Conflict ❌
    │
    ├─► Create payment in DB
    ├─► Append PAYMENT_INITIATED event
    ├─► Commit transaction
    ├─► Publish to RabbitMQ
    └─► Cache response in Redis (TTL: 24h) ✅
```

## 🧪 Running Tests
```bash
pip install -r requirements.txt
pytest tests/ -v
```

## 📁 Project Structure
```
app/
├── api/v1/endpoints/    # FastAPI route handlers
├── core/                # Config, exceptions, logging
├── db/                  # SQLAlchemy engine & session
├── models/              # ORM models (Payment, PaymentEvent)
├── schemas/             # Pydantic request/response schemas
├── services/
│   ├── payment_service.py   ← Core orchestrator (CQRS)
│   ├── event_store.py       ← Event Sourcing engine
│   └── idempotency.py       ← Redis idempotency guard
├── repositories/        # Data access layer
└── events/              # RabbitMQ publisher
```

## 🛠️ Tech Stack

- **FastAPI** — Async REST API
- **PostgreSQL + SQLAlchemy 2.0** — Async ORM
- **Redis** — Idempotency cache & distributed locking
- **RabbitMQ + aio-pika** — Event messaging
- **structlog** — Structured JSON logging
- **pytest + pytest-asyncio** — Async test suite
- **Docker + docker-compose** — One-command setup
- **GitHub Actions** — CI/CD pipeline
