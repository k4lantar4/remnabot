# Tenant Management API Documentation

**Author:** Architecture Team  
**Date:** 2025-11-21  
**Version:** 1.0

---

## Overview

This document defines the REST API endpoints for managing tenants (representative bots) in the multi-tenant system. All endpoints require authentication and tenant context awareness.

---

## Base URL

- **Development**: `http://localhost:8080`
- **Production**: Configured via `WEB_API_HOST` and `WEB_API_PORT` settings

---

## Authentication

All endpoints require API token authentication:

- **Header**: `Authorization: Bearer <token>` or `X-Api-Key: <token>`
- **Tenant Context**: Extracted from token (tokens are tenant-scoped)
- **System Admin**: Special tokens can access all tenants

---

## API Endpoints

### 1. Tenant Management (System Admin Only)

**Base Path**: `/api/tenants`

#### 1.1 List Tenants

**Endpoint**: `GET /api/tenants`

**Description**: List all tenants with filtering and pagination. System admin only.

**Query Parameters**:
- `status` (optional, string): Filter by status (`pending_approval`, `active`, `suspended`, `rejected`)
- `limit` (optional, int, default=50): Number of results per page (1-200)
- `offset` (optional, int, default=0): Pagination offset
- `search` (optional, string): Search by tenant name or bot username

**Response**: `200 OK`

```json
{
  "tenants": [
    {
      "id": 1,
      "name": "Main Bot",
      "status": "active",
      "bot_token": "***hidden***",
      "bot_username": "mainbot",
      "settings": {
        "limits": {
          "max_users": 1000,
          "max_active_subscriptions": 500
        },
        "features": {
          "miniapp_enabled": true,
          "referral_program_enabled": true
        }
      },
      "created_by_user_id": null,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z",
      "statistics": {
        "total_users": 150,
        "active_subscriptions": 45,
        "total_revenue_kopeks": 1250000,
        "monthly_revenue_kopeks": 250000
      }
    }
  ],
  "total": 10,
  "limit": 50,
  "offset": 0
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Token is not system admin token

---

#### 1.2 Get Tenant Details

**Endpoint**: `GET /api/tenants/{tenant_id}`

**Description**: Get detailed information about a specific tenant. System admin can access any tenant. Tenant admin can only access their own tenant.

**Path Parameters**:
- `tenant_id` (int): Tenant ID

**Response**: `200 OK`

```json
{
  "id": 2,
  "name": "Representative Bot ABC",
  "status": "active",
  "bot_token": "***hidden***",
  "bot_username": "repbot_abc",
  "settings": {
    "limits": {
      "max_users": 500,
      "max_active_subscriptions": 200,
      "daily_transaction_limit_kopeks": 500000,
      "monthly_revenue_limit_kopeks": 5000000
    },
    "features": {
      "miniapp_enabled": true,
      "referral_program_enabled": true,
      "promo_codes_enabled": true,
      "support_tickets_enabled": true,
      "broadcasts_enabled": false,
      "polls_enabled": false
    },
    "branding": {
      "bot_name": "ABC VPN Bot",
      "welcome_message": "Welcome to ABC VPN!",
      "logo_url": "https://example.com/logo.png"
    },
    "payment_providers": {
      "enabled": ["telegram_stars", "yookassa"],
      "disabled": ["cryptobot", "heleket"]
    }
  },
  "created_by_user_id": 123,
  "created_at": "2025-11-15T10:00:00Z",
  "updated_at": "2025-11-20T15:30:00Z",
  "statistics": {
    "total_users": 75,
    "active_users": 60,
    "active_subscriptions": 25,
    "total_revenue_kopeks": 750000,
    "monthly_revenue_kopeks": 150000,
    "daily_revenue_kopeks": 5000,
    "conversion_rate": 0.33
  }
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Tenant admin trying to access another tenant
- `404 Not Found`: Tenant not found

---

#### 1.3 Create Tenant

**Endpoint**: `POST /api/tenants`

**Description**: Create a new tenant. System admin only. Typically used for manual tenant creation or bot provisioning automation.

**Request Body**:

```json
{
  "name": "New Representative Bot",
  "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
  "bot_username": "newrepbot",
  "settings": {
    "limits": {
      "max_users": 1000,
      "max_active_subscriptions": 500
    },
    "features": {
      "miniapp_enabled": true,
      "referral_program_enabled": true
    }
  },
  "created_by_user_id": 123
}
```

**Response**: `201 Created`

```json
{
  "id": 3,
  "name": "New Representative Bot",
  "status": "pending_approval",
  "bot_token": "***hidden***",
  "bot_username": "newrepbot",
  "settings": {
    "limits": {
      "max_users": 1000,
      "max_active_subscriptions": 500
    },
    "features": {
      "miniapp_enabled": true,
      "referral_program_enabled": true
    }
  },
  "created_by_user_id": 123,
  "created_at": "2025-11-21T12:00:00Z",
  "updated_at": "2025-11-21T12:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid request data (duplicate bot_token, invalid settings)
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Not system admin

---

#### 1.4 Update Tenant

**Endpoint**: `PUT /api/tenants/{tenant_id}`

**Description**: Update tenant settings and configuration. System admin can update any tenant. Tenant admin can update their own tenant (limited fields).

**Path Parameters**:
- `tenant_id` (int): Tenant ID

**Request Body** (partial updates supported):

```json
{
  "name": "Updated Bot Name",
  "status": "active",
  "settings": {
    "limits": {
      "max_users": 2000
    },
    "features": {
      "broadcasts_enabled": true
    },
    "branding": {
      "bot_name": "Updated Bot Name",
      "welcome_message": "New welcome message"
    }
  }
}
```

**Response**: `200 OK`

```json
{
  "id": 2,
  "name": "Updated Bot Name",
  "status": "active",
  "bot_token": "***hidden***",
  "bot_username": "repbot_abc",
  "settings": {
    "limits": {
      "max_users": 2000,
      "max_active_subscriptions": 500
    },
    "features": {
      "miniapp_enabled": true,
      "referral_program_enabled": true,
      "broadcasts_enabled": true
    },
    "branding": {
      "bot_name": "Updated Bot Name",
      "welcome_message": "New welcome message"
    }
  },
  "updated_at": "2025-11-21T13:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid settings or status transition
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Tenant admin trying to update restricted fields
- `404 Not Found`: Tenant not found

**Note**: Tenant admins can only update:
- `settings.branding.*`
- `settings.features.*` (if allowed by system admin)
- Cannot update `status`, `limits`, or `bot_token`

---

#### 1.5 Activate Tenant

**Endpoint**: `POST /api/tenants/{tenant_id}/activate`

**Description**: Activate a pending or suspended tenant. System admin only.

**Path Parameters**:
- `tenant_id` (int): Tenant ID

**Response**: `200 OK`

```json
{
  "id": 2,
  "status": "active",
  "updated_at": "2025-11-21T14:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid status transition
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Not system admin
- `404 Not Found`: Tenant not found

---

#### 1.6 Suspend Tenant

**Endpoint**: `POST /api/tenants/{tenant_id}/suspend`

**Description**: Suspend an active tenant. System admin only. Suspended tenants cannot process new users or transactions.

**Path Parameters**:
- `tenant_id` (int): Tenant ID

**Request Body** (optional):

```json
{
  "reason": "Violation of terms of service"
}
```

**Response**: `200 OK`

```json
{
  "id": 2,
  "status": "suspended",
  "updated_at": "2025-11-21T15:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid status transition
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Not system admin
- `404 Not Found`: Tenant not found

---

#### 1.7 Reject Tenant Request

**Endpoint**: `POST /api/tenants/{tenant_id}/reject`

**Description**: Reject a pending tenant request. System admin only.

**Path Parameters**:
- `tenant_id` (int): Tenant ID

**Request Body** (optional):

```json
{
  "reason": "Incomplete information provided"
}
```

**Response**: `200 OK`

```json
{
  "id": 3,
  "status": "rejected",
  "updated_at": "2025-11-21T16:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid status transition
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Not system admin
- `404 Not Found`: Tenant not found

---

### 2. Tenant Statistics & Analytics

#### 2.1 Get Tenant Statistics

**Endpoint**: `GET /api/tenants/{tenant_id}/statistics`

**Description**: Get comprehensive statistics for a tenant. System admin can access any tenant. Tenant admin can only access their own tenant.

**Path Parameters**:
- `tenant_id` (int): Tenant ID

**Query Parameters**:
- `period` (optional, string): Time period (`day`, `week`, `month`, `year`, `all`), default=`all`
- `start_date` (optional, datetime): Start date for custom period
- `end_date` (optional, datetime): End date for custom period

**Response**: `200 OK`

```json
{
  "tenant_id": 2,
  "period": "month",
  "users": {
    "total": 150,
    "active": 120,
    "new_this_period": 25,
    "growth_rate": 0.20
  },
  "subscriptions": {
    "total": 45,
    "active": 35,
    "trial": 5,
    "expired": 5,
    "conversion_rate": 0.30
  },
  "revenue": {
    "total_kopeks": 1250000,
    "period_kopeks": 250000,
    "average_transaction_kopeks": 5000,
    "transactions_count": 50
  },
  "traffic": {
    "total_used_gb": 1250.5,
    "average_per_user_gb": 8.3
  },
  "engagement": {
    "tickets_created": 12,
    "tickets_resolved": 10,
    "polls_participated": 45,
    "referrals_created": 8
  }
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Tenant admin trying to access another tenant
- `404 Not Found`: Tenant not found

---

#### 2.2 Get Tenant Analytics Dashboard

**Endpoint**: `GET /api/tenants/{tenant_id}/analytics`

**Description**: Get analytics dashboard data with charts and trends. System admin can access any tenant. Tenant admin can only access their own tenant.

**Path Parameters**:
- `tenant_id` (int): Tenant ID

**Query Parameters**:
- `days` (optional, int, default=30): Number of days for trend data

**Response**: `200 OK`

```json
{
  "tenant_id": 2,
  "summary": {
    "total_users": 150,
    "active_subscriptions": 35,
    "monthly_revenue_kopeks": 250000,
    "growth_rate": 0.20
  },
  "trends": {
    "user_growth": [
      {"date": "2025-11-01", "count": 125},
      {"date": "2025-11-15", "count": 140},
      {"date": "2025-11-21", "count": 150}
    ],
    "revenue": [
      {"date": "2025-11-01", "kopeks": 200000},
      {"date": "2025-11-15", "kopeks": 225000},
      {"date": "2025-11-21", "kopeks": 250000}
    ],
    "subscriptions": [
      {"date": "2025-11-01", "active": 30},
      {"date": "2025-11-15", "active": 32},
      {"date": "2025-11-21", "active": 35}
    ]
  },
  "top_metrics": {
    "most_active_users": [
      {"user_id": 456, "subscription_days": 45, "traffic_gb": 120.5},
      {"user_id": 789, "subscription_days": 30, "traffic_gb": 95.2}
    ],
    "payment_methods": [
      {"method": "telegram_stars", "count": 20, "revenue_kopeks": 100000},
      {"method": "yookassa", "count": 15, "revenue_kopeks": 150000}
    ]
  }
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Tenant admin trying to access another tenant
- `404 Not Found`: Tenant not found

---

### 3. Bot Request Management (From Main Bot)

#### 3.1 Request Representative Bot

**Endpoint**: `POST /api/bot-requests`

**Description**: Create a bot request from the main bot. This endpoint is accessible from the main bot context (tenant_id=1) and creates a pending tenant request.

**Request Body**:

```json
{
  "representative_name": "John Doe",
  "contact_info": "john@example.com",
  "business_name": "ABC VPN Services",
  "website": "https://abcvpn.com",
  "expected_users": 500,
  "notes": "Looking to expand VPN services"
}
```

**Response**: `201 Created`

```json
{
  "request_id": 123,
  "status": "pending_approval",
  "tracking_code": "BR-2025-11-21-001",
  "message": "Your bot request has been submitted. Tracking code: BR-2025-11-21-001",
  "estimated_review_time": "24-48 hours"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Invalid or missing API token
- `429 Too Many Requests`: Too many requests from same user (rate limiting)

---

#### 3.2 Get Bot Request Status

**Endpoint**: `GET /api/bot-requests/{request_id}`

**Description**: Get status of a bot request. Accessible by the requesting user or system admin.

**Path Parameters**:
- `request_id` (int): Request ID

**Query Parameters**:
- `tracking_code` (optional, string): Alternative lookup by tracking code

**Response**: `200 OK`

```json
{
  "request_id": 123,
  "tracking_code": "BR-2025-11-21-001",
  "status": "approved",
  "representative_name": "John Doe",
  "business_name": "ABC VPN Services",
  "created_at": "2025-11-21T10:00:00Z",
  "reviewed_at": "2025-11-21T14:00:00Z",
  "tenant_id": 2,
  "bot_username": "repbot_abc",
  "bot_token": "***hidden***",
  "setup_instructions": "Your bot is ready! Use the following token..."
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: User trying to access another user's request
- `404 Not Found`: Request not found

---

### 4. Tenant Limits & Enforcement

#### 4.1 Check Tenant Limits

**Endpoint**: `GET /api/tenants/{tenant_id}/limits/check`

**Description**: Check if tenant has reached any limits. Used internally by services.

**Path Parameters**:
- `tenant_id` (int): Tenant ID

**Response**: `200 OK`

```json
{
  "tenant_id": 2,
  "limits_status": {
    "max_users": {
      "limit": 500,
      "current": 150,
      "remaining": 350,
      "reached": false,
      "percentage": 30
    },
    "max_active_subscriptions": {
      "limit": 200,
      "current": 45,
      "remaining": 155,
      "reached": false,
      "percentage": 22.5
    },
    "daily_transaction_limit_kopeks": {
      "limit": 500000,
      "current": 25000,
      "remaining": 475000,
      "reached": false,
      "percentage": 5
    }
  },
  "any_limit_reached": false
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing API token
- `404 Not Found`: Tenant not found

---

## Authentication & Authorization

### Token Types

1. **System Admin Token**: Can access all tenants, create/manage tenants
2. **Tenant Admin Token**: Can only access their own tenant, limited update permissions
3. **User Token**: Cannot access tenant management endpoints

### Tenant Context Extraction

- **From Bot Token**: For bot handlers, tenant is identified by bot token
- **From API Token**: For REST API, tenant_id is stored in token metadata
- **From Request**: System admin can specify tenant_id in query parameter (for cross-tenant queries)

---

## Error Codes

| Code | Description |
|------|-------------|
| `TENANT_NOT_FOUND` | Tenant with specified ID does not exist |
| `TENANT_ACCESS_DENIED` | User does not have permission to access this tenant |
| `TENANT_LIMIT_REACHED` | Tenant has reached a configured limit |
| `TENANT_SUSPENDED` | Tenant is suspended and cannot process requests |
| `INVALID_TENANT_STATUS` | Invalid status transition |
| `DUPLICATE_BOT_TOKEN` | Bot token already exists |
| `INVALID_TENANT_SETTINGS` | Tenant settings JSON is invalid |

---

## Rate Limiting

- **Bot Requests**: 1 request per user per 24 hours
- **Tenant Statistics**: 100 requests per hour per token
- **Tenant Updates**: 10 requests per hour per tenant

---

## Next Steps

1. Implement API route handlers in `app/webapi/routes/tenants.py`
2. Create Pydantic schemas in `app/webapi/schemas/tenants.py`
3. Implement tenant service in `app/services/tenant_service.py`
4. Add tenant context middleware
5. Update existing endpoints to filter by tenant_id
6. Add comprehensive tests

---

**Document Status**: Ready for Implementation  
**Review Required**: Yes - Architecture Team  
**Approval Required**: Yes - Technical Lead

