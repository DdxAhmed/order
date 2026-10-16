# Automated & Integration Testing Guide — OrderTrofy

## 1. Test Suite Overview

The repository contains **22 automated unit and integration tests** executing against the local PostgreSQL test engine using `pytest` and `pytest-asyncio`.

| Test Module | Test Count | Key Areas Covered |
| :--- | :--- | :--- |
| [`tests/test_security.py`](file:///c:/Users/symon/OneDrive/Desktop/ordertrofy/ordertrofy/tests/test_security.py) | 4 | Argon2id hashing, Fernet symmetric encryption, identifier masking (`ste***unt`), random token entropy. |
| [`tests/test_steam_parser.py`](file:///c:/Users/symon/OneDrive/Desktop/ordertrofy/ordertrofy/tests/test_steam_parser.py) | 4 | Steam Guard email extraction in English and Spanish, rejection of spoofed domains, failed DKIM rejection, username mismatch detection. |
| [`tests/test_admin_auth.py`](file:///c:/Users/symon/OneDrive/Desktop/ordertrofy/ordertrofy/tests/test_admin_auth.py) | 1 | Administrator login flow, password validation, bearer session token issuance, and `/auth/me` verification. |
| [`tests/test_customer_flow.py`](file:///c:/Users/symon/OneDrive/Desktop/ordertrofy/ordertrofy/tests/test_customer_flow.py) | 1 | Customer order access, portal state query, assigned account masking, and verification code request triggers. |
| [`tests/test_otp_workflow.py`](file:///c:/Users/symon/OneDrive/Desktop/ordertrofy/ordertrofy/tests/test_otp_workflow.py) | 5 | End-to-end OTP retrieval with synthetic email fixtures: matching Steam emails, waiting for missing emails, expired requests, cancelled/revoked orders, and malformed/spoofed email rejection. |
| [`tests/test_rate_limits.py`](file:///c:/Users/symon/OneDrive/Desktop/ordertrofy/ordertrofy/tests/test_rate_limits.py) | 3 | Database-backed rate limits, 5-request quota, 30-second cooldown enforcement, and concurrent request race-condition serialization. |
| [`tests/test_authorization_and_separation.py`](file:///c:/Users/symon/OneDrive/Desktop/ordertrofy/ordertrofy/tests/test_authorization_and_separation.py) | 4 | Cross-customer object-level authorization (Customer A cannot access Customer B's order), customer rejection from admin endpoints (401), unauthenticated rejection (401), and security response headers. |

---

## 2. Running Automated Tests

Run the full pytest suite from the project root using Windows PowerShell:

```powershell
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe -m pytest -v tests
```

### Running Specific Test Modules
```powershell
# Run only authorization and customer separation tests
.\.venv\Scripts\python.exe -m pytest -v tests/test_authorization_and_separation.py

# Run only OTP email fixture tests
.\.venv\Scripts\python.exe -m pytest -v tests/test_otp_workflow.py

# Run only rate limit and concurrency tests
.\.venv\Scripts\python.exe -m pytest -v tests/test_rate_limits.py
```

---

## 3. Asynchronous Connection Isolation (`NullPool`)

When testing async FastAPI applications with PostgreSQL and `asyncpg`:
- In standard test runners, connections pooled in one test function's event loop can cross into subsequent tests, resulting in `Event loop is closed` errors.
- In OrderTrofy, `app/db.py` automatically detects when running under `pytest` and configures `NullPool`. Each test session receives a fresh connection scoped strictly to its active event loop, preventing loop contamination.

---

## 4. Distinguishing Mocked / Synthetic Tests vs. Live Outlook Graph

- **Synthetic Email Fixtures (VERIFIED):** Tested in `test_otp_workflow.py` and `test_steam_parser.py` using complete RFC-compliant email message objects containing DKIM headers, message IDs, and localized bodies.
- **Live Microsoft Graph Mailbox (BLOCKED / NOT TESTED):** Requires an authorized Azure AD tenant registration with live delegated permissions (`Mail.Read`). Live Graph polling against an external mailbox cannot be executed without tenant credentials configured in `.env`.

---

## 5. Frontend Build Verification

To verify that the React 19 + Vite frontend builds cleanly without TypeScript or bundler errors:

```powershell
cd frontend
npm run build
```
*(Builds to `dist/index.html` in ~600ms).*
