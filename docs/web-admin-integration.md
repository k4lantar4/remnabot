# Web admin integration

This document describes how to run the bot’s built-in admin web API and a typical integration with an external web admin.
The API is deployed with the bot, uses FastAPI, and is protected by access tokens.

## 1. Architecture overview

- The web API runs in the same process as the bot, through the embedded `uvicorn` server.
- Authorization uses a token: `X-API-Key` or `Authorization: Bearer <token>`.
- All endpoints work over HTTPS/HTTP and return JSON structures.
- The built-in migration mechanism creates the `web_api_tokens` table and a bootstrap token if one is configured.

## 2. Environment setup

Add variables to `.env` (or another configuration system):

| Variable | Purpose | Default / example |
|----------|---------|-------------------|
| `WEB_API_ENABLED` | Enables the web API. | `true`
| `WEB_API_HOST` | IP/hostname the API listens on. | `0.0.0.0`
| `WEB_API_PORT` | Web API port. | `8080`
| `WEB_API_ALLOWED_ORIGINS` | Comma-separated CORS domain list. `*` allows everything. | `https://admin.example.com`
| `WEB_API_DOCS_ENABLED` | Enable `/docs`, `/doc` (redirect), `/redoc`, and `/openapi.json`. Prefer `false` in production. | `false`
| `WEB_API_WORKERS` | Number of uvicorn workers. In embed mode this is always forced to `1`. | `1`
| `WEB_API_REQUEST_LOGGING` | Log every API request. | `true`
| `WEB_API_DEFAULT_TOKEN` | Bootstrap token created during migration. | `super-secret-token`
| `WEB_API_DEFAULT_TOKEN_NAME` | Display name of the created token. | `Bootstrap Token`
| `WEB_API_TOKEN_HASH_ALGORITHM` | Token hashing algorithm (`sha256`, `sha512`, …). | `sha256`

> If you store configuration in Kubernetes/Ansible/other systems, update the secrets so the bot sees these variables.

### Enabling Swagger (interactive docs)

To open Swagger UI at `/docs`, set both environment variables:

1. `WEB_API_ENABLED=true` — enables the web API itself.
2. `WEB_API_DOCS_ENABLED=true` — publishes `/docs`, `/doc` (redirect for old links), `/redoc`, and `/openapi.json`.

Restart the bot after changing the values. The UI is available at `http://<WEB_API_HOST>:<WEB_API_PORT>/docs`.

## 3. Preparing the database

1. Confirm the DB settings are correct (`DATABASE_URL` or PostgreSQL/SQLite parameters).
2. On bot startup Alembic migrations run automatically (`alembic upgrade head`) and create all required tables, including `web_api_tokens`.
3. The token from `WEB_API_DEFAULT_TOKEN` is activated automatically on startup.
4. To run the migration manually:

```bash
make migrate  # or: uv run alembic upgrade head
```

Or just run `python main.py` — the bot performs the same procedure automatically.

## 4. Starting the web API

```bash
# Create .env and enable the web API
cp .env.example .env
nano .env  # set WEB_API_* variables and BOT_TOKEN

# Start the bot (locally)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

In Docker it is enough to publish `WEB_API_PORT` from the bot container. After startup the API is available at `http://<WEB_API_HOST>:<WEB_API_PORT>`.

## 5. Authentication and tokens

- The first token is conveniently set via `WEB_API_DEFAULT_TOKEN`. It appears in the table when the migration runs and is automatically recreated/activated after the value is changed through the settings UI.
- Use the `/tokens` endpoints to manage tokens:
  - `GET /tokens` — list tokens.
  - `POST /tokens` — create a new token. Returns the plaintext value once.
  - `POST /tokens/{id}/revoke` and `/activate` — status management.
  - `DELETE /tokens/{id}` — delete.
- The authorization header can be passed in two ways:

```http
X-API-Key: <your_token>
# or
Authorization: Bearer <your_token>
```

Example request to create a token:

```bash
curl -X POST "http://127.0.0.1:8080/tokens" \
  -H "X-API-Key: super-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Web admin", "description": "UI token"}'
```

## 6. Main endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | API status, bot version, enabled-service flags.
| `GET` | `/stats/overview` | Summary statistics for users, subscriptions, payments, and tickets.
| `GET` | `/settings/categories` | System setting categories.
| `GET` | `/settings` | Full settings list (with current and default values).
| `GET` | `/settings/{key}` | Get one setting.
| `PUT` | `/settings/{key}` | Update a setting value.
| `DELETE` | `/settings/{key}` | Reset a setting to its default value.
| `GET` | `/users` | User list with filters and pagination.
| `GET` | `/users/{id}` | User details. ID may be internal (`user.id`) or Telegram ID (`user.telegram_id`).
| `POST` | `/users` | Create a user (for example, for manual access grant).
| `PATCH` | `/users/{id}` | Update user profile or status. ID may be internal (`user.id`) or Telegram ID (`user.telegram_id`).
| `POST` | `/users/{id}/balance` | Low-level balance adjustment (can also debit). No idempotency and no notifications — for manual edits, not automation. ID may be internal (`user.id`) or Telegram ID (`user.telegram_id`).
| `POST` | `/users/{id}/deposit` | **Manual top-up** — a full analogue of a gateway payment, with idempotency. For automatic integrations (support agent). See the section below.
| `GET` | `/subscriptions` | Subscription list with filters.
| `POST` | `/subscriptions` | Create a trial or paid subscription.
| `POST` | `/subscriptions/{id}/extend` | Extend a subscription by N days.
| `POST` | `/subscriptions/{id}/traffic` | Add traffic (GB).
| `POST` | `/subscriptions/{id}/devices` | Add devices.
| `POST` | `/subscriptions/{id}/squads` | Attach a squad.
| `DELETE` | `/subscriptions/{id}/squads/{uuid}` | Remove a squad.
| `GET` | `/transactions` | Transaction history.
| `GET` | `/tickets` | Support ticket list.
| `GET` | `/tickets/{id}` | Ticket with conversation.
| `POST` | `/tickets/{id}/status` | Change ticket status.
| `POST` | `/tickets/{id}/priority` | Change priority.
| `POST` | `/tickets/{id}/reply-block` | Block user replies.
| `DELETE` | `/tickets/{id}/reply-block` | Remove the block.
| `GET` | `/promo-groups` | Promo-group list with member counts.
| `POST` | `/promo-groups` | Create a promo group.
| `PATCH` | `/promo-groups/{id}` | Update a promo group.
| `DELETE` | `/promo-groups/{id}` | Delete a promo group.
| `GET` | `/promo-offers` | Promo-offer list with filters by user, status, and notification type.
| `POST` | `/promo-offers` | Create or update a personal promo offer for a user. ID may be internal (`user.id`) or Telegram ID (`user.telegram_id`).
| `GET` | `/promo-offers/{id}` | Details of a specific promo offer.
| `GET` | `/promo-offers/templates` | Promo-offer template list.
| `GET` | `/promo-offers/templates/{id}` | Get promo-offer template data.
| `PATCH` | `/promo-offers/templates/{id}` | Update template text, buttons, and parameters.
| `GET` | `/promo-offers/logs` | Promo-offer operations log (activations, charges, disables).
| `GET` | `/tokens` | Access-token management.
| `GET` | `/polls` | Poll list with pagination.
| `GET` | `/polls/{id}` | Poll details with questions and options.
| `POST` | `/polls` | Create a poll: title, description, questions, and options.
| `DELETE` | `/polls/{id}` | Delete an entire poll.
| `GET` | `/polls/{id}/stats` | Summary statistics for answers and granted rewards.
| `GET` | `/polls/{id}/responses` | User responses with per-question detail.
| `GET` | `/logs/monitoring` | Bot monitoring logs with pagination and event-type filters.
| `GET` | `/logs/monitoring/event-types` | Catalog of available monitoring event types.
| `GET` | `/logs/support` | Support moderator action log (blocks, ticket closures).
| `GET` | `/logs/support/actions` | Catalog of possible support-audit actions.
| `GET` | `/logs/system` | Preview of the bot system log file with metadata.
| `GET` | `/logs/system/download` | Download the full bot log file (`text/plain`).

> The **promo-offers** Swagger section covers personal offers: granting discounts/bonuses to users, configuring template texts, and viewing the operations log (activations, auto-charges, disabling expired campaigns).

### Bot logs

The admin API includes a **logs** section. It lets you:

- View general monitoring logs (`GET /logs/monitoring`) with pagination (`limit`, `offset`) and an event-type filter (`event_type`).
- Get a catalog of available event types (`GET /logs/monitoring/event-types`). Useful for building filters in an external admin.
- Track support moderator actions (`GET /logs/support`) with pagination and an optional filter by a specific action (`action`).
- Request the list of possible actions for the UI (`GET /logs/support/actions`).
- Preview the bot system log file (`GET /logs/system`). The endpoint returns metadata (path, modification time, size in bytes/characters) and a tail fragment whose size can be controlled with `preview_limit` (from 500 to 20,000 characters).
- Download the full system log as text (`GET /logs/system/download`).

All endpoints are protected by an API token and return a structure with the total record count, current `limit`/`offset`, and an array of objects. That simplifies tables and pagination in external admin UIs.

### Poll management

The **polls** section of the admin API lets you create and analyze polls that the bot sends to users.

#### List and details

- `GET /polls` — returns an array of objects with basic information: title, description, reward flags, question count, and response count.
- `GET /polls/{id}` — expands the structure of a specific poll, including ordered questions and options. Suitable for preview before publication.

#### Creating a poll

To create a poll, send JSON matching this schema:

```json
{
  "title": "New tariff feedback",
  "description": "Help us improve the product — it takes up to 2 minutes",
  "reward_enabled": true,
  "reward_amount_kopeks": 1000,
  "questions": [
    {
      "text": "How satisfied are you with connection speed?",
      "options": [
        { "text": "Very satisfied" },
        { "text": "Somewhat satisfied" },
        { "text": "Neutral" },
        { "text": "Somewhat dissatisfied" },
        { "text": "Very dissatisfied" }
      ]
    },
    {
      "text": "What improvements do you expect?",
      "options": [
        { "text": "Stability" },
        { "text": "Speed" },
        { "text": "Support" }
      ]
    }
  ]
}
```

Validation requirements:

- Title (`title`) — 1 to 255 characters, not empty after trimming whitespace.
- Description (`description`) — up to 4000 characters; leading/trailing whitespace is stripped.
- If `reward_enabled=true`, the reward amount (`reward_amount_kopeks`) must be positive. When `false`, the value is automatically reset to `0`.
- Each question contains at least two unique answer options.

The API returns the created poll with assigned identifiers and a `reward_amount_rubles` field that is convenient to show in the UI.

#### Deletion and statistics

- `DELETE /polls/{id}` — deletes the poll and its related questions/answers. Use with care; the operation is irreversible.
- `GET /polls/{id}/stats` — aggregated statistics: total answers, completed submissions, and the sum of granted rewards. For each question it returns choice counts per option.
- `GET /polls/{id}/responses` — user responses with pagination (`limit`, `offset`). Each item contains timestamps (`sent_at`, `started_at`, `completed_at`), user data (ID, username, Telegram ID), reward information, and an array of answers with question/option texts.

This format lets the frontend show detail or export CSV without extra requests.

### RemnaWave integration

After enabling the web API in Swagger (`WEB_API_DOCS_ENABLED=true`), a **remnawave** section appears. It groups endpoints for RemnaWave panel management and bot data sync:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/remnawave/status` | Check RemnaWave API configuration and availability. |
| `GET` | `/remnawave/system` | Aggregated statistics for users, nodes, and traffic. |
| `GET` | `/remnawave/nodes` | Node list and current state. |
| `GET` | `/remnawave/nodes/realtime` | Current node load (RemnaWave realtime metrics). |
| `GET` | `/remnawave/nodes/{uuid}` | Detailed information for a specific node. |
| `GET` | `/remnawave/nodes/{uuid}/statistics` | Aggregated statistics and load history for a node. |
| `GET` | `/remnawave/nodes/{uuid}/usage` | Node usage history by users for a selected period. |
| `POST` | `/remnawave/nodes/{uuid}/actions` | Enable, disable, or restart a node. |
| `POST` | `/remnawave/nodes/restart` | Bulk restart of all nodes in RemnaWave. |
| `GET` | `/remnawave/squads` | Internal squad list with membership and statistics. |
| `GET` | `/remnawave/squads/{uuid}` | Details of the selected squad. |
| `POST` | `/remnawave/squads` | Create a new squad and attach inbounds. |
| `PATCH` | `/remnawave/squads/{uuid}` | Update the squad name or inbound membership. |
| `POST` | `/remnawave/squads/{uuid}/actions` | Bulk operations: add/remove all, rename, update inbounds, delete. |
| `GET` | `/remnawave/inbounds` | List of available inbounds in the RemnaWave panel. |
| `GET` | `/remnawave/users/{telegram_id}/traffic` | Traffic usage of a specific RemnaWave user. |
| `POST` | `/remnawave/sync/from-panel` | Sync users and subscriptions from the panel into the bot. |
| `POST` | `/remnawave/sync/to-panel` | Reverse sync of bot data into the panel. |
| `POST` | `/remnawave/sync/subscriptions/validate` | Check and restore subscriptions in RemnaWave. |
| `POST` | `/remnawave/sync/subscriptions/cleanup` | Clean up orphaned subscriptions and users in RemnaWave. |
| `POST` | `/remnawave/sync/subscriptions/statuses` | Align subscription statuses in the bot and the panel. |
| `GET` | `/remnawave/sync/recommendations` | Sync recommendations: what to add, update, or delete. |

> All list endpoints support pagination (`limit`, `offset`) and the filters described in the OpenAPI specification. If `WEB_API_DOCS_ENABLED=true`, docs are available at `/docs`. In `/settings` responses the `choices` field is always an array: an empty list means there are no predefined values.

### Manual balance top-up (`POST /users/{id}/deposit`)

Endpoint for “credit a person by hand”: compensation, a lost payment, a contest prize. Designed for an automatic caller — for example a support AI agent.

```bash
curl -X POST https://bot.example.com/users/123456789/deposit \
  -H "X-API-Key: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"amount_kopeks": 50000, "idempotency_key": "ticket-8471", "description": "Compensation for ticket 8471"}'
```

```json
{
  "success": true, "duplicate": false,
  "user_id": 42, "telegram_id": 123456789, "transaction_id": 90112,
  "amount_kopeks": 50000, "old_balance_kopeks": 0,
  "new_balance_kopeks": 50000, "new_balance_rubles": 500.0
}
```

What the integrator needs to know:

- **Always send `idempotency_key`.** A repeat request with the same key credits nothing and returns the original transaction with `duplicate: true`. Without a key, a normal network timeout plus an agent retry produces a double credit. Any stable key works: ticket number, attempt UUID. Keys are global — the same key with a different amount **or** for a different user is a caller error, response `409 Conflict` (otherwise a reused ticket number would “credit” money to someone else — in the response, though not in reality).
- **This is a full top-up, not a number edit.** The same pipeline as a gateway payment runs: referral commission, first-top-up mark, user notification, resume of a paused daily subscription, auto-purchase of a saved cart. Disable bonuses with `apply_topup_bonuses: false`, notification with `notify_user: false`.
- **Credit only.** There is nothing to debit with — that remains `POST /users/{id}/balance` (low-level adjustment, no idempotency and no notifications).
- **Per-operation ceiling** — `WEB_API_MANUAL_DEPOSIT_MAX_KOPEKS` (default 1,000,000 kopeks = 10,000 ₽; `0` removes the limit). A safeguard against an agent adding two extra zeros; exceeding it returns `400`.
- **Verify who was credited from the response.** `{id}` in the path is treated first as Telegram ID, then as internal `user.id`; the response returns both.
- **The API token is full access.** There are no separate operation permissions: the same token can do everything else in this API. For a support agent, create a separate token, keep it out of the model prompt, and audit `/tokens`.

## 7. Web admin integration scenario

1. **Health-check** — before authorization the UI calls `GET /health` to show bot status and version.
2. **UI settings** — loads categories via `GET /settings/categories`, then renders a form from `GET /settings`.
3. **Dashboard statistics** — `GET /stats/overview` for metric cards.
4. **Users section** — `GET /users` with search (`search`) and filters by status or promo group. For a detail card use `GET /users/{id}` (ID may be internal `user.id` or the user’s `telegram_id`).
5. **Subscription operations** — use `POST /subscriptions/{id}/...` endpoints for extension, traffic, and devices.
6. **Support** — ticket list (`GET /tickets`), status change (`POST /tickets/{id}/status`), reply block (`POST /tickets/{id}/reply-block`).
7. **Operation history** — `GET /transactions` with filters by user, type, and period.

## 8. CORS, security, and logging

- Allowed domains are set in `WEB_API_ALLOWED_ORIGINS`. For several domains, list them comma-separated.
- In production, disable public documentation (`WEB_API_DOCS_ENABLED=false`).
- `WEB_API_REQUEST_LOGGING=true` adds middleware that logs method, path, and response status. Use it for audit, or disable it in production if reverse-proxy logs are enough.
- All tokens are stored in the database hashed. Do not store plaintext values in code.

## 9. Troubleshooting

| Symptom | Possible cause | What to check |
|---------|----------------|---------------|
| 401 Unauthorized | Invalid or expired token. | Recreate the token via `/tokens` and update the UI. |
| 403/404 when working with settings | Wrong setting key. | Get the list of available keys via `GET /settings`. |
| 422 Unprocessable Entity | Wrong data type in the request body. | Check types (numbers, booleans, strings) and JSON format. |
| API does not start | Port in use or invalid environment variables. | Check the bot container logs and `WEB_API_HOST`/`PORT` values. |

## 10. Operations recommendations

- Regularly review the list of active tokens and disable unused ones.
- For external admins, place the API behind a reverse proxy (nginx, Caddy, Traefik) with TLS.
- Enable availability monitoring (for example curl on `/health`) in the observability system.
- Update the bot and the admin together so new API fields are used.
