# Architecture & System Design — OrderTrofy

## 1. High-Level System Architecture

OrderTrofy is an automated, entitlement-bound verification and inventory delivery platform for store-managed Steam accounts.

```
                          ┌────────────────────────┐
                          │   Client Browser SPA   │
                          │   (React 19 + Vite)    │
                          └───────────┬────────────┘
                                      │
                   ┌──────────────────┴──────────────────┐
                   │                                     │
           Path: / (Customer)                  Path: /admin/* (Admin)
                   │                                     │
         ┌─────────▼────────┐                  ┌─────────▼────────┐
         │  CustomerLayout  │                  │   AdminLayout    │
         │ (CustomerPortal) │                  │  (Route Guards)  │
         └─────────┬────────┘                  └─────────┬────────┘
                   │                                     │
                   └──────────────────┬──────────────────┘
                                      │ HTTP /api/v1/* (Vite Proxy :5173 -> :8000)
                                      ▼
                        ┌───────────────────────────┐
                        │    FastAPI Application    │
                        │    (Uvicorn on :8000)     │
                        └─────────────┬─────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
    ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
    │  API Routers │          │  Core Auth   │          │ Background   │
    │  & Middleware│          │  & Security  │          │ Worker Loop  │
    └──────┬───────┘          └──────┬───────┘          └──────┬───────┘
           │                         │                         │
           └─────────────────────────┼─────────────────────────┘
                                     │ AsyncPG / SQLAlchemy
                                     ▼
                        ┌───────────────────────────┐
                        │   PostgreSQL 18 (:5433)   │
                        │   Database: steam_codes   │
                        └───────────────────────────┘
```

---

## 2. Directory Structure

```
ordertrofy/
├── app/                        # FastAPI Application Core
│   ├── api/                    # HTTP Layer
│   │   ├── deps.py             # Dependency Injection (Auth, DB Sessions, Roles)
│   │   └── routers/            # Focused HTTP Route Handlers
│   │       ├── auth.py         # Admin authentication & session lifecycle
│   │       ├── customer.py     # Customer portal access, session, & code requests
│   │       ├── dashboard.py    # Admin analytics & metric aggregations
│   │       ├── orders.py       # Order management & status transitions
│   │       ├── accounts.py     # Steam inventory account management
│   │       ├── customers.py    # Customer records & assignment lookups
│   │       ├── mailboxes.py    # IMAP / Graph mailbox credentials
│   │       ├── platforms.py    # Platform catalogs & email regex trust profiles
│   │       ├── import_csv.py   # Bulk inventory CSV ingestion
│   │       ├── audit.py        # Centralized immutable audit trail
│   │       ├── salla_admin.py  # Salla webhook and merchant configuration
│   │       └── salla_public.py # Public non-sensitive quota services
│   ├── services/               # Business Logic Layer
│   │   ├── access.py           # Admin authentication & database-backed rate limiting
│   │   ├── customer.py         # Customer order verification & session tokens
│   │   ├── inventory.py        # Account reservation, assignment, & verification requests
│   │   ├── verification.py     # OTP retrieval, mailbox polling, & cryptographic storage
│   │   ├── local_access.py     # Atomic usage counters, cooldowns, & replay protection
│   │   ├── salla.py            # Salla OAuth, token rotation, & webhook processing
│   │   ├── salla_notifications.py # Merchant notification matching
│   │   ├── csv_import.py       # Streaming CSV inventory parser
│   │   └── non_sensitive_services.py # Registered service handlers
│   ├── models.py               # Declarative SQLAlchemy ORM Models (22 Entities)
│   ├── config.py               # Pydantic BaseSettings & Environment Loading
│   ├── security.py             # Argon2 Password Hashing & Fernet Ciphertext
│   ├── db.py                   # Async Engine, NullPool for tests, & SessionLocal
│   ├── i18n.py                 # Arabic / English Translation Catalogs
│   ├── audit.py                # Database-Backed Audit Event Recorder
│   ├── worker.py               # Background Task Processor (Steam Polling & Expiration)
│   ├── cli.py                  # CLI commands (`create-admin`, `change-password`)
│   └── main.py                 # FastAPI Application Factory, CORS, & Security Headers
├── alembic/                    # Database Migrations (10 Idempotent Revisions)
├── frontend/                   # React 19 + Vite Frontend SPA
│   ├── src/
│   │   ├── context/
│   │   │   ├── AuthContext.jsx   # Admin and Customer authentication state
│   │   │   ├── LangContext.jsx   # UI Language (Arabic/English) context
│   │   │   └── RouterContext.jsx # Zero-dependency HTML5 History API routing
│   │   ├── layouts/
│   │   │   ├── CustomerLayout.jsx# Public layout (NO admin controls or links)
│   │   │   └── AdminLayout.jsx   # Protected admin layout with sidebar & route guards
│   │   ├── pages/
│   │   │   ├── customer/         # CustomerPortal view
│   │   │   └── admin/            # AdminLogin, Dashboard, Orders, Accounts, etc.
│   │   ├── components/           # Reusable UI controls (AdminNavbar, CustomerNavbar, Sidebar)
│   │   └── api/client.js         # Centralized API fetch wrapper with session headers
│   └── Caddyfile               # Production SPA server configuration
├── tests/                      # Automated Test Suite (22 passing unit & integration tests)
├── deploy/                     # Caddyfile and deployment configurations
├── compose.yaml                # Production Docker Compose orchestration
├── compose.dev.yaml            # Local development Compose port bindings
└── pyproject.toml              # Python project metadata and dependencies
```

---

## 3. Core Architectural Boundaries

### 3.1 HTTP Layer vs. Service Layer
- **Routers (`app/api/routers/`)**: Validate request payloads using Pydantic schemas, extract credentials/tokens, handle HTTP status codes, and delegate all business decisions to services.
- **Services (`app/services/`)**: Enforce business rules, atomic database transactions, cryptographic encryption/decryption, rate limits, and event logging.

### 3.2 Frontend Route Separation
- **Customer Portal (`/`)**: Rendered inside `CustomerLayout`. Contains only client-facing verification controls. Displays masked Steam accounts (`ste***unt`) and delivery countdown timers. **Contains zero administrative navigation links or references.**
- **Administrator Portal (`/admin/*`)**: Rendered inside `AdminLayout`. Guarded by client-side router checks and strictly verified server-side on every REST call. Unauthenticated requests are immediately bounced to `/admin/login`.

### 3.3 Database Sessions & Concurrency
- **Read Operations**: Handled via `Depends(get_db_session)`.
- **Mutating Operations**: Handled via `Depends(get_db_session_commit)` utilizing `SessionLocal.begin()` to guarantee atomic commit or rollback.
- **Race Condition Prevention**: Rate limits, inventory assignment, and OTP claim operations utilize PostgreSQL row-level locks (`with_for_update()`) and unique constraints to ensure that concurrent requests cannot double-spend or bypass cooldowns.
