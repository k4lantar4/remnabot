# API Contracts - Main

## Overview

This project implements a comprehensive REST API using FastAPI framework. The API provides administrative endpoints for managing the Telegram bot, users, subscriptions, payments, and integrations.

**Base URL:** `http://{WEB_API_HOST}:{WEB_API_PORT}` (default: `http://0.0.0.0:8080`)

**Authentication:** Token-based via `X-API-Key` header or `Authorization: Bearer <token>`

**API Version:** Defined in `WEB_API_VERSION` setting

## API Routes

The API is organized into the following route modules:

### Health & Monitoring

**Base Path:** `/health`

- `GET /health` - Health check endpoint, returns API status and version
- `GET /health/database` - Detailed database connection status
- `GET /metrics/pool` - Database connection pool metrics

### Statistics

**Base Path:** `/stats`

- `GET /stats/overview` - Aggregated statistics for users, subscriptions, support tickets, and payments

### Settings & Configuration

**Base Path:** `/settings`

- `GET /settings/categories` - List all setting categories
- `GET /settings` - Get all system settings with current and default values
- `GET /settings/{key}` - Get a specific setting by key
- `PUT /settings/{key}` - Update a setting value
- `DELETE /settings/{key}` - Reset a setting to default value

### Users Management

**Base Path:** `/users`

- `GET /users` - List users with pagination and filters (search, status, promo_group)
- `GET /users/{id}` - Get user details by ID (supports both internal ID and Telegram ID)
- `POST /users` - Create a new user
- `PATCH /users/{id}` - Update user profile or status
- `POST /users/{id}/balance` - Adjust user balance with transaction creation

### Subscriptions

**Base Path:** `/subscriptions`

- `GET /subscriptions` - List subscriptions with filters
- `POST /subscriptions` - Create trial or paid subscription
- `POST /subscriptions/{id}/extend` - Extend subscription by N days
- `POST /subscriptions/{id}/traffic` - Add traffic (GB) to subscription
- `POST /subscriptions/{id}/devices` - Add devices to subscription
- `POST /subscriptions/{id}/squads` - Attach squad to subscription
- `DELETE /subscriptions/{id}/squads/{uuid}` - Remove squad from subscription

### Support Tickets

**Base Path:** `/tickets`

- `GET /tickets` - List support tickets with pagination and filters
- `GET /tickets/{id}` - Get ticket details with message history
- `POST /tickets/{id}/status` - Update ticket status
- `POST /tickets/{id}/priority` - Update ticket priority
- `POST /tickets/{id}/reply-block` - Block user replies to ticket
- `DELETE /tickets/{id}/reply-block` - Unblock user replies

### Transactions

**Base Path:** `/transactions`

- `GET /transactions` - List transactions with filters (user_id, type, payment_method, date range)

### Promo Groups

**Base Path:** `/promo-groups`

- `GET /promo-groups` - List promo groups with member counts
- `POST /promo-groups` - Create new promo group
- `PATCH /promo-groups/{id}` - Update promo group
- `DELETE /promo-groups/{id}` - Delete promo group

### Promo Offers

**Base Path:** `/promo-offers`

- `GET /promo-offers` - List promo offers with filters (user, status, notification type)
- `POST /promo-offers` - Create or update personal promo offer for user
- `GET /promo-offers/{id}` - Get promo offer details
- `GET /promo-offers/templates` - List promo offer templates
- `GET /promo-offers/templates/{id}` - Get template details
- `PATCH /promo-offers/templates/{id}` - Update template (text, buttons, parameters)
- `GET /promo-offers/logs` - View promo offer operation log (activations, deductions, deactivations)

### Promo Codes

**Base Path:** `/promo-codes`

- `GET /promo-codes` - List promo codes with pagination
- `POST /promo-codes` - Create new promo code
- `PATCH /promo-codes/{id}` - Update promo code
- `GET /promo-codes/{id}` - Get promo code details

### Servers & Squads

**Base Path:** `/servers`

- Server management endpoints for RemnaWave integration

### RemnaWave Integration

**Base Path:** `/remnawave`

- `GET /remnawave/status` - Check RemnaWave API configuration and availability
- `GET /remnawave/system` - Aggregated statistics (users, nodes, traffic)
- `GET /remnawave/nodes` - List nodes and their current state
- `GET /remnawave/nodes/realtime` - Current node load (realtime metrics)
- `GET /remnawave/nodes/{uuid}` - Get node details
- `GET /remnawave/nodes/{uuid}/statistics` - Node statistics and load history
- `GET /remnawave/nodes/{uuid}/usage` - Node usage history for selected period
- `POST /remnawave/nodes/{uuid}/actions` - Enable, disable, or restart node
- `POST /remnawave/nodes/restart` - Mass restart all nodes
- `GET /remnawave/squads` - List internal squads with composition and statistics
- `GET /remnawave/squads/{uuid}` - Get squad details
- `POST /remnawave/squads` - Create new squad and bind inbounds
- `PATCH /remnawave/squads/{uuid}` - Update squad name or inbound composition
- `POST /remnawave/squads/{uuid}/actions` - Bulk operations (add/remove all, rename, update inbounds, delete)
- `GET /remnawave/inbounds` - List available inbounds in RemnaWave panel
- `GET /remnawave/users/{telegram_id}/traffic` - Get user traffic usage in RemnaWave
- `POST /remnawave/sync/from-panel` - Sync users and subscriptions from panel to bot
- `POST /remnawave/sync/to-panel` - Reverse sync bot data to panel
- `POST /remnawave/sync/subscriptions/validate` - Validate and restore subscriptions in RemnaWave
- `POST /remnawave/sync/subscriptions/cleanup` - Cleanup orphaned subscriptions and users
- `POST /remnawave/sync/subscriptions/statuses` - Synchronize subscription statuses between bot and panel
- `GET /remnawave/sync/recommendations` - Get synchronization recommendations

### Mini App

**Base Path:** `/miniapp`

- `GET /miniapp/subscription` - Get user subscription information for Mini App
- `POST /miniapp/payments/methods` - Get available payment methods for Mini App
- `POST /miniapp/payments/create` - Create payment for Mini App
- `GET /miniapp/payments/status` - Check payment status
- `POST /miniapp/promo-codes/activate` - Activate promo code
- `GET /miniapp/promo-offers` - Get user's active promo offers
- `POST /miniapp/promo-offers/claim` - Claim promo offer
- `GET /miniapp/subscription/settings` - Get subscription settings
- `POST /miniapp/subscription/settings` - Update subscription settings
- `POST /miniapp/subscription/purchase` - Purchase subscription
- `POST /miniapp/subscription/trial` - Activate trial subscription
- `GET /miniapp/faq` - Get FAQ for Mini App
- `GET /miniapp/legal` - Get legal documents (privacy policy, public offer)
- `GET /miniapp/referral` - Get referral information and statistics

### Main Menu

**Base Path:** `/main-menu`

- `/main-menu/buttons` - Manage main menu buttons
- `/main-menu/messages` - Manage main menu messages

### Welcome Texts

**Base Path:** `/welcome-texts`

- Manage welcome text templates

### Pages & Content

**Base Path:** `/pages`

- Manage public pages: offer, policy, FAQ, rules

### Broadcasts

**Base Path:** `/broadcasts`

- Create and manage broadcast messages

### Backups

**Base Path:** `/backups`

- Create, list, and manage database backups

### Campaigns

**Base Path:** `/campaigns`

- Manage advertising campaigns

### Tokens (Authentication)

**Base Path:** `/tokens`

- `GET /tokens` - List API tokens
- `POST /tokens` - Create new API token
- `POST /tokens/{id}/revoke` - Revoke token
- `POST /tokens/{id}/activate` - Activate token
- `DELETE /tokens/{id}` - Delete token

### Partners (Referral Program)

**Base Path:** `/partners`

- View referral program participants, earnings, and referrals

### Polls

**Base Path:** `/polls`

- `GET /polls` - List polls
- `GET /polls/{id}` - Get poll details
- `POST /polls` - Create poll
- `DELETE /polls/{id}` - Delete poll
- `GET /polls/{id}/stats` - Get poll statistics
- `GET /polls/{id}/responses` - Get poll responses

### Logs

**Base Path:** `/logs`

- `GET /logs/monitoring` - Monitoring logs with pagination and event type filters
- `GET /logs/monitoring/event-types` - Available event types for filtering
- `GET /logs/support` - Support moderator action logs
- `GET /logs/support/actions` - Available support actions
- `GET /logs/system` - System log file preview
- `GET /logs/system/download` - Download full system log file

### Subscription Events (Notifications)

**Base Path:** `/notifications/subscriptions`

- Get subscription event notifications for admin panel

## Authentication

All endpoints require authentication via one of the following methods:

1. **X-API-Key header:**
   ```
   X-API-Key: your-token-here
   ```

2. **Authorization Bearer token:**
   ```
   Authorization: Bearer your-token-here
   ```

Tokens are managed through the `/tokens` endpoints. A bootstrap token can be configured via `WEB_API_DEFAULT_TOKEN` environment variable.

## Response Format

All endpoints return JSON responses. List endpoints typically include:
- `items`: Array of results
- `total`: Total count
- `limit`: Page size
- `offset`: Current offset

Error responses follow standard HTTP status codes:
- `200`: Success
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `422`: Unprocessable Entity
- `500`: Internal Server Error

## CORS

CORS is configured via `WEB_API_ALLOWED_ORIGINS` setting. Use `*` to allow all origins (not recommended for production).

## Documentation

When `WEB_API_DOCS_ENABLED=true`, interactive API documentation is available at:
- `/docs` - Swagger UI
- `/redoc` - ReDoc
- `/openapi.json` - OpenAPI specification
