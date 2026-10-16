# Database & Migration Reference — OrderTrofy

## 1. Database Configuration

- **Engine:** PostgreSQL 18.6
- **Database Name:** `steam_codes`
- **Default Local Port:** `5433` (Chosen to avoid Windows OS TCP reserved ranges)
- **Encoding:** `UTF8` (`--locale=C`) — Ensures safe handling of Arabic and multilingual names without transcoding errors.
- **Connection Protocols:**
  - **Async (Application Runtime):** `postgresql+asyncpg://steam_codes:<password>@127.0.0.1:5433/steam_codes`
  - **Sync (Alembic Migrations / CLI):** `postgresql+psycopg://steam_codes:<password>@127.0.0.1:5433/steam_codes`

---

## 2. Table Schema Overview

| Table Name | Description | Key Constraints |
| :--- | :--- | :--- |
| `platforms` | Supported platform definitions (Steam, etc.) | `uq: code` |
| `mailboxes` | Mailbox credentials (IMAP / Graph) | `uq: label` |
| `mailbox_oauth_states` | Temporary PKCE state tokens for Graph OAuth | `pk: state_hash` |
| `customers` | Customer profiles (Arabic / English names) | `pk: id`, `idx: telegram_user_id` |
| `customer_sessions` | Web customer portal authentication sessions | `uq: token_hash` |
| `inventory_accounts` | Stored Steam accounts and credentials | `uq: (platform_id, normalized_identifier)` |
| `orders` | Customer purchase orders | `uq: external_reference` |
| `account_assignments` | Entitlement binding an account to an order | `uq: account_id (where revoked_at IS NULL)` |
| `activation_tokens` | Single-use order redemption links | `pk: token_hash` |
| `verification_requests` | Steam Guard OTP extraction requests | `ck: status in ('queued', 'processing', ...)` |
| `mail_message_claims` | Deduplication locks on extracted emails | `uq: (mailbox_id, uidvalidity, uid)` |
| `worker_jobs` | Idempotent asynchronous task queue | `uq: (kind, idempotency_key)` |
| `admin_users` | Administrator accounts and password hashes | `uq: email`, `ck: role` |
| `admin_sessions` | Authenticated administrator bearer tokens | `uq: token_hash` |
| `audit_events` | Immutable security and operational audit trail | `idx: (entity_type, entity_id)` |
| `rate_limit_windows` | Database-backed sliding rate limit buckets | `uq: (scope, subject_hash, window_start)` |
| `usage_policies` | Service quota, cooldown, and limits | `uq: service_key` |
| `local_usage_identities` | Local merchant-approved access identities | `uq: reference_key` |
| `local_usage_counters` | Rolling period usage counters | `uq: (identity_id, service_key, period_start)` |
| `local_usage_records` | Idempotency replay protection records | `uq: (identity_id, service_key, idempotency_key)` |

---

## 3. Alembic Migration History

All migrations are located in `alembic/versions/` and have been applied up to `head`:

1. `20260908_0001_initial`: Base schema (accounts, orders, platforms, mailboxes, admin users).
2. `20260911_0002_web_customer_sessions`: Customer web session and activation tokens.
3. `20260914_0003_mailbox_oauth2`: Added OAuth2 refresh tokens for Microsoft Graph.
4. `20260914_0004_oauth_pkce`: PKCE code challenge and verifier storage.
5. `20260918_0005_salla`: Salla merchant authorization and webhook events.
6. `20260923_0006_salla_email_entitlements`: Email-based Salla entitlement matching.
7. `20260926_0007_salla_entitlement_quantity`: Multi-item quantity support.
8. `20260927_0008_local_access`: Local non-sensitive access policies and counters.
9. `20261004_0009_platform_catalog`: Dynamic platform catalogs and metadata.
10. `20261015_0010_local_access_platform`: (Head) Added idempotent platform code references.

### Running Migrations
```powershell
# Upgrade to latest revision
.\.venv\Scripts\python.exe -m alembic upgrade head

# Check current migration revision
.\.venv\Scripts\python.exe -m alembic current
```
