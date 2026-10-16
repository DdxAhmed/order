# OrderTrofy Technical Handoff

This handoff describes the safe, non-sensitive production behavior. It intentionally contains no passwords, OAuth secrets, tokens, private keys, database dumps, or authentication-code content.

## Scope and safe boundary

OrderTrofy is a FastAPI/Jinja2 application backed by PostgreSQL and Docker Compose. It manages inventory, orders, mail connection metadata, and a local customer usage session. No document in this handoff authorizes extracting, parsing, displaying, forwarding, or delivering OTPs, Steam Guard codes, login codes, recovery codes, passwords, or other credentials.

## Production entry points

- Public site: <https://ordertrofy.store/>
- Simplified local-reference page: <https://ordertrofy.store/salla>
- Admin login: <https://ordertrofy.store/admin/login>
- Liveness: `/health/live`
- Readiness: `/health/ready`
- Production directory: `/opt/steam-codes`

## Local order-reference flow

`GET /salla` renders a mobile-first form with `order_reference` and `account_alias`; `POST /salla/access` normalizes, validates, and creates or updates a local identity. The value is deliberately not a Salla order proof. **The reference can be any value entered by the user; the application does not verify it through Salla.** It is an unverified external reference/local usage key and must never be labelled a “verified order”. Salla API and Salla notification email are not called by this flow.

The identity stores only the normalized reference and ordinary alias metadata. The session token is random, stored as a hash, delivered in an HttpOnly/Secure cookie, and bounded by the configured session lifetime. Errors are generic and do not reveal whether another user has already used a reference.

## Usage policy

Defaults are five successful permitted uses per reference in a rolling 24-hour period and a 30-second cooldown. Counters are independent per reference and service key. PostgreSQL row locking and unique idempotency records protect concurrent requests and duplicate submissions. A secondary rate limiter applies to IP and session. The current production database has no public non-sensitive service mapping by default; sessions are not an authorization path for credentials.

Relevant settings: `SALLA_USAGE_MAX`, `SALLA_USAGE_PERIOD_SECONDS`, `SALLA_USAGE_COOLDOWN_SECONDS`, and `SALLA_CUSTOMER_SESSION_MINUTES`.

## Application architecture

```text
Browser -> web (FastAPI/Jinja2) -> PostgreSQL
                         ^
worker (safe background jobs) -- IMAP TLS / Microsoft Graph read-only
caddy -> HTTPS reverse proxy
```

- `app/main.py`: routes, admin/customer pages, health checks.
- `app/models.py`: SQLAlchemy models.
- `app/services/`: local usage, inventory, Salla compatibility services.
- `app/mail/`: IMAP and Microsoft Graph providers.
- `app/web/templates/`: Jinja templates.
- `app/static/app.css`: shared responsive styles.
- `alembic/`: migrations.
- `tests/`: unit, integration, parser, concurrency, and platform tests.

## Platforms and inventory

Stable catalog identifiers are `steam`, `ubisoft`, and `rockstar`; labels are Steam, Ubisoft, and Rockstar Games. Steam remains the existing platform. Ubisoft and Rockstar are first-class safe inventory/taxonomy entries: create/edit/filter/assign/status/audit are supported, but no email adapter, code parser, customer credential flow, or code delivery exists for them. Inventory fields are generic (`platform`, identifier, status, mailbox reference, notes) and must never contain passwords or secrets.

## Admin operations

- `/admin/accounts`: add/edit/filter inventory records and manage status.
- `/admin/orders`: create internal orders and assign available inventory.
- `/admin/mailboxes`: IMAP configuration and Outlook OAuth connection/re-authorize.
- `/admin/platforms`: catalog and safe Steam profile metadata.
- `/admin/audit`: safe management audit events.
- `/admin/salla`: preserved Salla authorization/mapping/policy administration; not used for `/salla` local access.

CSV import expects `platform,account_identifier,mailbox_reference,status,notes`. Import validation rejects unknown platforms and unsafe/malformed rows. Do not put secrets in CSV or notes.

## Outlook OAuth2 / Graph

One Microsoft Entra Web App registration is shared by mailbox connections. The implementation uses authority `consumers`, PKCE S256, the exact callback configured in `MICROSOFT_REDIRECT_URI` (production: `https://ordertrofy.store/admin/mailboxes/oauth/callback`), and delegated scopes `openid profile email offline_access Mail.Read`. A confidential production flow requires the client secret; it is never logged. Each mailbox has its own encrypted refresh-token ciphertext, and rotated refresh tokens replace the stored ciphertext inside a transaction.

The worker and connection test use Graph read-only access. Safe testing may use a benign subject such as `test mailbox connection` and metadata-only selection. The implementation must not add `Mail.ReadWrite`, `Mail.Send`, application permissions, or `User.Read` merely to make `/me` convenient. A Graph `/me` call can return 403 when only `Mail.Read` is granted; that is expected and is not evidence that Mail.Read message reads failed.

## Gmail / IMAP

IMAP uses TLS and an app password where the provider requires one. The password is encrypted with `MAIL_CREDENTIALS_KEY`; it is not written to logs or documentation. Outlook OAuth mailboxes use the Graph provider and do not use a mailbox password.

## Salla compatibility integration

Salla API authorization, webhook signature validation, product mappings, usage policy models, and notification ingestion remain preserved for administrative compatibility. The current simplified customer flow does not call them. `SALLA_API_VERIFICATION_ENABLED` defaults to false. Never insert synthetic paid orders into production and never expand a generic local reference into a claim of Salla ownership.

## Status model

Inventory records commonly use `available`, `assigned`, `disabled`, and `archived`. Assigned records are protected from a second active assignment. Platform entries may be disabled while records remain preserved. Audit events record safe management actions without secrets or message bodies.

## Backups and VPS operations

Run from `/opt/steam-codes`:

```bash
docker compose ps
curl -fsS https://ordertrofy.store/health/live
curl -fsS https://ordertrofy.store/health/ready
docker compose logs --since 15m web worker
```

Before deployment, create a controlled PostgreSQL backup outside the repository and keep its checksum. Protect `.env` with owner-only permissions and never copy it to a handoff archive. Restart only the affected services:

```bash
docker compose up -d web worker caddy
```

## Deployment and migrations

1. Review the diff and run the relevant tests, `ruff`, and `compileall`.
2. Back up PostgreSQL.
3. Run `docker compose run --rm web alembic upgrade head` when a migration exists.
4. Recreate/restart only `web` and `worker` (plus `caddy` for proxy changes).
5. Verify both health endpoints and the affected browser flow.
6. Keep the previous image available for rollback; never drop production tables as a rollback strategy.

Current Alembic head: `20261004_0009` (platform catalog). Check with:

```bash
docker compose run --rm web alembic current
docker compose run --rm web alembic heads
```

## Troubleshooting

| Symptom | Inspect | Safe action |
|---|---|---|
| Mobile form blank | `/salla`, CSS cache/version, DOM box sizes, console/network | Refresh the versioned CSS, verify 390/393/430 widths, and confirm no horizontal overflow |
| Outlook disconnected | Mailbox `auth_mode`, last error code, OAuth configuration | Use official reauthorization; do not paste a password/token |
| Mail.Read failure | OAuth scopes, Graph HTTP status, benign test metadata | Keep delegated `Mail.Read`; inspect sanitized status only |
| Worker stopped | `docker compose ps worker`, sanitized logs | Restart worker after checking database readiness |
| Health failure | web/postgres state and readiness log | Fix service/database health; preserve data |
| Database unavailable | postgres health and connection errors | Repair the service/network; do not recreate production storage |
| Migration mismatch | `alembic current` vs `heads` | Apply the reviewed migration, then recheck readiness |
| Local quota reached | counter window and cooldown | Wait for the rolling window or use a separate merchant-approved reference |
| Account disabled | inventory/platform status and audit event | Re-enable only after a safe metadata review |

No OTP/code-extraction troubleshooting is part of this system handoff.

## Security and maintenance

- Never send passwords, `.env`, client secrets, webhook secrets, OAuth codes, access tokens, or refresh tokens through chat or screenshots.
- Rotate a secret that was exposed, synchronizing the provider and server values.
- Review daily health; weekly backup verification, disk space, and sanitized errors; monthly security updates, unused mailbox/account cleanup, and audit review.
- Keep production data and test data separate; use disposable PostgreSQL databases for concurrency tests.

## Environment variable names

Names only (values belong in the protected runtime environment): `APP_ENV`, `APP_SECRET_KEY`, `DATABASE_URL`, `DATABASE_URL_SYNC`, `MAIL_CREDENTIALS_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_WEBHOOK_URL`, `PUBLIC_BASE_URL`, `COOKIE_SECURE`, `CADDY_DOMAIN`, `IMAP_LABEL`, `IMAP_HOST`, `IMAP_PORT`, `IMAP_USERNAME`, `IMAP_PASSWORD`, `MICROSOFT_CLIENT_ID`/`MICROSOFT_OAUTH_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`/`MICROSOFT_OAUTH_CLIENT_SECRET`, `MICROSOFT_AUTHORITY`/`MICROSOFT_OAUTH_TENANT`, `MICROSOFT_REDIRECT_URI`/`MICROSOFT_OAUTH_REDIRECT_URI`, `SALLA_CLIENT_ID`, `SALLA_CLIENT_SECRET`, `SALLA_WEBHOOK_SECRET`, `SALLA_TOKEN_KEY`, `SALLA_APP_ID`, `SALLA_API_VERIFICATION_ENABLED`, `SALLA_NOTIFICATION_POLL_SECONDS`, `SALLA_CUSTOMER_SESSION_MINUTES`, `SALLA_USAGE_MAX`, `SALLA_USAGE_PERIOD_SECONDS`, `SALLA_USAGE_COOLDOWN_SECONDS`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.

## Known limitations

The `/salla` reference is unverified and does not establish buyer ownership. No public non-sensitive service is currently mapped. Ubisoft/Rockstar support is inventory-only. Salla API and notification workflows remain separate compatibility features. Live approval of a new email-language profile requires a merchant-authorized sample and must not store sensitive message content. A tested backup restore is still an operational responsibility.

## Quick start

1. Check `health/live` and `health/ready`.
2. Use `/salla` with a local reference and alias.
3. Manage safe inventory under `/admin/accounts`.
4. Connect/re-authorize mailboxes only through the official OAuth/IMAP settings.
5. Back up before deployment and keep all secrets outside the repository.
