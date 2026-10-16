# Security Architecture & Hardening Guide — OrderTrofy

## 1. Authentication & Session Management

### 1.1 Password Security
- All administrator passwords are authenticated using **Argon2id** (`argon2-cffi`).
- Passwords are never stored in plaintext, never logged, and never included in error messages or response bodies.
- Enforced minimum entropy: passwords must satisfy complexity requirements and are hashed with a unique salt per account.

### 1.2 Session Token Lifecycle
- Admin sessions (`AdminSession`) and customer web sessions (`CustomerSession`) utilize cryptographically secure 256-bit random tokens generated via `secrets.token_urlsafe(32)`.
- Tokens are stored in the database exclusively as **SHA-256 hashes** (`token_hash`), preventing session hijacking even in the event of database exfiltration.
- Sessions include mandatory expiration dates (`expires_at`) and can be immediately invalidated via explicit revocation (`revoked_at`).

---

## 2. Authorization & Privilege Enforcement

### 2.1 Role-Based Access Control (RBAC)
Administrator permissions are enforced server-side using FastAPI dependency injection (`require_admin_roles`):
- **`owner`**: Full unrestricted administrative authority (user management, settings, credentials, audits).
- **`operator` / `admin`**: Inventory management, order processing, and verification monitoring.
- **`support`**: Read-only and customer support workflows. Prohibited from modifying mailbox configurations or platform trust profiles.

### 2.2 Object-Level Authorization
- Customer portal endpoints enforce strict ownership:
  ```python
  AccountAssignment.customer_id == customer.id
  ```
- A customer cannot access, query, or trigger verification codes for accounts or orders assigned to another customer. Inquiries for mismatched IDs return `404 Not Found`.

---

## 3. Cryptographic Storage & OTP Isolation

### 3.1 Fernet Secret Encryption
- Mailbox passwords, OAuth refresh tokens, and retrieved Steam Guard verification codes are encrypted at rest using **Fernet symmetric encryption** (`cryptography.fernet`).
- Encryption keys are derived from `SECRET_KEY` via HKDF SHA-256.

### 3.2 Steam Guard OTP Lifecycle
- Extracted codes are stored only as ciphertext (`result_ciphertext`).
- Retention is strictly limited by `result_retention_seconds` (default: 300 seconds), after which the background worker purges the code ciphertext.
- **Mail Message Claims**: Each incoming email is claimed by a unique constraint on `(mailbox_id, uidvalidity, uid)`. A single email can never be claimed more than once or by multiple concurrent requests.

---

## 4. Rate Limiting, Cooldowns, & Concurrency Protection

### 4.1 Login Protection
- Admin login is rate-limited per IP and email combination (maximum 10 attempts per hour).
- Failed logins are recorded in `audit_events` with client IP and user agent.

### 4.2 Code Request Limits
- Verification requests are limited to **5 requests per 600-second rolling window** per customer session.
- A **30-second cooldown** is strictly enforced between code retrieval attempts.
- **Concurrency Safety**: Quota checking and usage tracking utilize PostgreSQL row-level locks:
  ```sql
  SELECT ... FROM usage_policies WHERE service_key = :key FOR UPDATE;
  ```
  Concurrent requests executed at the exact same millisecond are serialized at the database transaction layer. Requests exceeding the rate or cooldown receive HTTP `429 Too Many Requests`.

---

## 5. Network & HTTP Hardening

### 5.1 Security Headers
All HTTP responses include protective headers:
- `X-Content-Type-Options: nosniff` (Prevents MIME-sniffing)
- `X-Frame-Options: DENY` (Clickjacking defense)
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- In production: `Strict-Transport-Security: max-age=31536000; includeSubDomains`

### 5.2 Request Size Caps
- The HTTP layer rejects incoming request payloads exceeding **10MB** with HTTP `413 Payload Too Large` to prevent denial-of-service memory exhaustion.

### 5.3 CORS Configuration
- Cross-Origin Resource Sharing is restricted to explicit, trusted origins:
  - `http://localhost:5173`, `http://127.0.0.1:5173`
  - `https://ordertrofy.store`
- Wildcard `*` origins are strictly prohibited when credentials are enabled.

---

## 6. Anti-Spoofing & Steam Email Verification
- The Steam mail adapter verifies:
  1. Sender address matches approved domains (`@steampowered.com`).
  2. `Authentication-Results` header contains verified DKIM signature (`dkim=pass`).
  3. The account username inside the email body strictly matches the assigned inventory account identifier.
- Spoofed emails, failed DKIM, or mismatched usernames are rejected and discarded.
