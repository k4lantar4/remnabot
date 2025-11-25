# API Contracts Documentation

## Overview

This project exposes a comprehensive REST API built with FastAPI for administrative and user-facing operations. The API is organized into multiple route modules covering all aspects of the Telegram bot management system.

## Base URL

- **Development**: `http://localhost:8080`
- **Production**: Configured via `WEB_API_HOST` and `WEB_API_PORT` settings

## Authentication

All API endpoints require authentication via API token:

- **Header**: `Authorization: Bearer <token>` or `X-Api-Key: <token>`
- Token management: `/tokens` endpoints

## API Route Modules

### Health & Monitoring

**Base Path**: `/health`

- `GET /health` - Unified health check
- `GET /health/database` - Database connection status
- `GET /health/unified` - Aggregated system status
- `GET /health/telegram-webhook` - Telegram webhook queue status
- `GET /health/payment-webhooks` - Payment webhook status

### Statistics

**Base Path**: `/stats`

- `GET /stats/overview` - Comprehensive statistics dashboard
- Statistics include: users, subscriptions, transactions, revenue, conversion metrics

### Settings & Configuration

**Base Path**: `/settings`

- `GET /settings` - Get all bot configuration
- `PUT /settings` - Update bot configuration
- Configuration includes: pricing, traffic packages, device limits, promo groups, payment methods

### Users Management

**Base Path**: `/users`

- `GET /users` - List users with filtering and pagination
- `GET /users/{user_id}` - Get user details
- `POST /users` - Create new user
- `PUT /users/{user_id}` - Update user
- `POST /users/{user_id}/balance` - Update user balance
- Search filters: ID, username, Telegram ID, referral code, balance range, subscription status

### Subscriptions

**Base Path**: `/subscriptions`

- `GET /subscriptions` - List all subscriptions
- `GET /subscriptions/{subscription_id}` - Get subscription details
- `POST /subscriptions` - Create new subscription (trial or paid)
- `POST /subscriptions/{subscription_id}/extend` - Extend subscription period
- `POST /subscriptions/{subscription_id}/devices` - Add devices to subscription
- `POST /subscriptions/{subscription_id}/traffic` - Add traffic to subscription
- `POST /subscriptions/{subscription_id}/squads` - Add server squad to subscription
- `DELETE /subscriptions/{subscription_id}/squads` - Remove server squad

### Transactions

**Base Path**: `/transactions`

- `GET /transactions` - List transactions with filtering
- Transaction types: deposit, withdrawal, subscription_payment, refund, referral_reward, poll_reward
- Filters: user_id, type, date range, payment method

### Promo Groups

**Base Path**: `/promo-groups`

- `GET /promo-groups` - List all promo groups
- `GET /promo-groups/{group_id}` - Get promo group details
- `POST /promo-groups` - Create promo group
- `PUT /promo-groups/{group_id}` - Update promo group
- `DELETE /promo-groups/{group_id}` - Delete promo group
- Promo groups provide discounts on: servers, traffic, devices

### Promo Offers

**Base Path**: `/promo-offers`

- `GET /promo-offers` - List promo offers
- `GET /promo-offers/{offer_id}` - Get offer details
- `POST /promo-offers` - Create promo offer
- `PUT /promo-offers/{offer_id}` - Update offer
- `DELETE /promo-offers/{offer_id}` - Delete offer
- Promo offers: personal discounts, trial activations, balance bonuses

### Promo Codes

**Base Path**: `/promo-codes`

- `GET /promo-codes` - List promo codes
- `GET /promo-codes/{code_id}` - Get code details
- `POST /promo-codes` - Create promo code
- `PUT /promo-codes/{code_id}` - Update code
- `DELETE /promo-codes/{code_id}` - Delete code
- Code types: balance, subscription_days, trial_subscription, promo_group

### Servers & RemnaWave Integration

**Base Path**: `/servers`

- `GET /servers` - List server squads
- `GET /servers/{squad_id}` - Get squad details
- `POST /servers/sync` - Manual synchronization with RemnaWave
- `PUT /servers/{squad_id}` - Update squad settings
- Server management: availability, promo group assignments, country/region

**Base Path**: `/remnawave`

- `GET /remnawave/status` - RemnaWave panel status
- `GET /remnawave/nodes` - List nodes
- `GET /remnawave/squads` - List squads
- `POST /remnawave/sync` - Trigger synchronization

### Support & Tickets

**Base Path**: `/tickets`

- `GET /tickets` - List tickets with filtering
- `GET /tickets/{ticket_id}` - Get ticket details
- `GET /tickets/{ticket_id}/messages` - Get ticket messages
- `POST /tickets/{ticket_id}/messages` - Add message to ticket
- `PUT /tickets/{ticket_id}` - Update ticket status/priority
- Ticket statuses: open, answered, closed, pending
- Priorities: low, normal, high, urgent

### Broadcasts

**Base Path**: `/broadcasts`

- `GET /broadcasts` - List broadcast history
- `POST /broadcasts` - Create and send broadcast
- Broadcast targets: all users, segments, promo groups, specific users

### Campaigns

**Base Path**: `/campaigns`

- `GET /campaigns` - List advertising campaigns
- `GET /campaigns/{campaign_id}` - Get campaign details
- `POST /campaigns` - Create campaign
- Campaign features: deeplink tracking, automatic rewards, UTM parameters

### Polls

**Base Path**: `/polls`

- `GET /polls` - List polls
- `GET /polls/{poll_id}` - Get poll details with statistics
- `POST /polls` - Create poll
- `DELETE /polls/{poll_id}` - Delete poll
- Poll features: multiple questions, reward system, response tracking

### Pages & Content

**Base Path**: `/pages`

- `GET /pages` - List content pages
- `GET /pages/{page_id}` - Get page content
- `POST /pages` - Create page
- `PUT /pages/{page_id}` - Update page
- Page types: FAQ, Privacy Policy, Public Offer, Rules, Welcome Text

### Main Menu Buttons

**Base Path**: `/main-menu/buttons`

- `GET /main-menu/buttons` - List menu buttons
- `POST /main-menu/buttons` - Create button
- `PUT /main-menu/buttons/{button_id}` - Update button
- `DELETE /main-menu/buttons/{button_id}` - Delete button
- Button types: URL, Mini App
- Visibility: all, admins, subscribers

### Mini App

**Base Path**: `/miniapp`

- `GET /miniapp/user/{telegram_id}` - Get user subscription info for Mini App
- Returns subscription status, balance, active services

### Backups

**Base Path**: `/backups`

- `GET /backups` - List backup files
- `POST /backups` - Create backup
- `GET /backups/{backup_id}/download` - Download backup
- `POST /backups/{backup_id}/restore` - Restore from backup

### Logs

**Base Path**: `/logs`

- `GET /logs/monitoring` - Monitoring logs
- `GET /logs/support` - Support audit logs
- `GET /logs/system` - System log file access

### Token Management

**Base Path**: `/tokens`

- `GET /tokens` - List API tokens
- `POST /tokens` - Create new token
- `DELETE /tokens/{token_id}` - Revoke token
- `POST /tokens/{token_id}/reactivate` - Reactivate revoked token

## Response Formats

All endpoints return JSON responses. Standard response structure:

```json
{
  "data": {...},
  "message": "Success message",
  "status": "ok"
}
```

Error responses:

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

## Rate Limiting

Rate limiting is configured via middleware. Default limits:
- 100 requests per minute per token
- Burst: 10 requests per second

## CORS

CORS is configured via `WEB_API_ALLOWED_ORIGINS`. Supports:
- Specific origins
- Wildcard (`*`) for development

## OpenAPI Documentation

When `WEB_API_DOCS_ENABLED=true`:
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

