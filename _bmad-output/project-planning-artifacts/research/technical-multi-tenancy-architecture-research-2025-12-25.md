---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Multi-tenancy Architecture Patterns for Python/FastAPI Telegram Bots'
research_goals: 'Understanding best patterns for converting remnabot to SaaS multi-tenant platform with tenant isolation, bot_token routing, SQLAlchemy patterns, and per-tenant configuration'
user_name: 'K4lantar4'
date: '2025-12-25'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical - Multi-tenancy Architecture

**Date:** 2025-12-25
**Author:** K4lantar4
**Research Type:** Technical
**Topic:** Multi-tenancy Architecture Patterns for Python/FastAPI Telegram Bots

---

## Research Overview

This technical research focuses on identifying and analyzing the best multi-tenancy architecture patterns for converting an existing Python/FastAPI Telegram bot (remnabot) into a SaaS multi-tenant platform capable of supporting 100-200 tenant bots in the MVP phase.

**Key Research Areas:**
- Multi-tenancy database patterns (row-level, schema-level, database-per-tenant)
- Tenant routing strategies using bot_token
- SQLAlchemy multi-tenant implementations
- FastAPI dependency injection for tenant context
- Per-tenant configuration management
- Data isolation and security patterns

---

<!-- Content will be appended sequentially through research workflow steps -->

## Technical Research Scope Confirmation

**Research Topic:** Multi-tenancy Architecture Patterns for Python/FastAPI Telegram Bots
**Research Goals:** Understanding best patterns for converting remnabot to SaaS multi-tenant platform with tenant isolation, bot_token routing, SQLAlchemy patterns, and per-tenant configuration

**Technical Research Scope:**

- Architecture Analysis - design patterns, frameworks, system architecture
- Implementation Approaches - development methodologies, coding patterns
- Technology Stack - languages, frameworks, tools, platforms
- Integration Patterns - APIs, protocols, interoperability
- Performance Considerations - scalability, optimization, patterns

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2025-12-25

---

## Technology Stack Analysis

### Programming Languages

**Python 3.11+** بهترین انتخاب برای پروژه شماست به دلایل زیر:

| ویژگی | توضیح |
|-------|--------|
| **AsyncIO Native** | پشتیبانی کامل از async/await برای عملیات همزمان |
| **Type Hints** | بهبود خوانایی و IDE support |
| **Performance** | Python 3.11+ تا ۲۵٪ سریع‌تر از نسخه‌های قبلی |
| **Ecosystem** | کتابخانه‌های غنی برای Telegram و Web |

_منبع: python.org documentation, aiogram documentation_

### Development Frameworks and Libraries

#### Backend Frameworks

| فریم‌ورک | کاربرد | مزایا برای Multi-tenancy |
|---------|--------|--------------------------|
| **FastAPI** | REST API | Dependency Injection native، async، automatic docs |
| **aiogram 3.x** | Telegram Bot | Webhook support، async، middleware system |
| **Pydantic v2** | Data Validation | Settings management، schema validation |

#### Multi-tenancy Libraries

| کتابخانه | رویکرد | مناسب برای |
|---------|--------|-----------|
| **sqlalchemy-multi-tenant** | Row-level filtering | پروژه‌های کوچک-متوسط |
| **Custom Middleware** | Request-scoped tenant | انعطاف‌پذیری بالا |
| **PostgreSQL RLS** | Database-level security | امنیت بالا |

_منبع: fastapi.tiangolo.com, docs.aiogram.dev, sqlalchemy.org_

### Database and Storage Technologies

#### Multi-tenancy Database Patterns

| الگو | توضیح | مزایا | معایب |
|------|--------|-------|-------|
| **Row-Level (bot_id)** | یک دیتابیس، یک schema، ستون bot_id | ساده، کم‌هزینه، backup آسان | نیاز به فیلتر دقیق در همه queries |
| **Schema-per-Tenant** | یک دیتابیس، schema جدا برای هر tenant | جداسازی بهتر، migration مستقل | پیچیدگی مدیریت، connection pooling |
| **Database-per-Tenant** | دیتابیس مجزا برای هر tenant | جداسازی کامل، compliance | هزینه بالا، پیچیدگی عملیاتی |

**پیشنهاد برای remnabot (100-200 tenant):**

✅ **Row-Level با PostgreSQL RLS** - بهترین تعادل بین سادگی و امنیت

#### PostgreSQL Row Level Security (RLS)

```sql
-- مثال پیاده‌سازی RLS
CREATE POLICY tenant_isolation ON users
    USING (bot_id = current_setting('app.current_tenant')::uuid);
```

| ویژگی | توضیح |
|-------|--------|
| **Automatic Filtering** | دیتابیس خودش queries رو فیلتر می‌کنه |
| **Security at DB Level** | حتی اگر application bug داشته باشه، داده‌ها امن هستن |
| **Performance** | ایندکس روی bot_id + query optimization |

_منبع: postgresql.org/docs/current/ddl-rowsecurity.html_

### Development Tools and Platforms

| ابزار | کاربرد |
|-------|--------|
| **Alembic** | Database migrations با multi-tenant support |
| **pytest-asyncio** | Testing async code |
| **Docker Compose** | Local development environment |
| **Redis** | Caching، session، tenant config cache |

### Cloud Infrastructure and Deployment

| گزینه | مناسب برای | هزینه |
|-------|-----------|--------|
| **Single VPS + Docker** | MVP (100-200 bots) | کم |
| **Kubernetes** | Scale بالا (1000+ bots) | متوسط-بالا |
| **Serverless** | Variable load | per-request |

**پیشنهاد برای MVP:**
- یک سرور با ۴-۸GB RAM
- PostgreSQL + Redis
- Docker Compose برای deployment
- Nginx برای reverse proxy و SSL

### Technology Adoption Trends

#### روندهای فعلی در Multi-tenant SaaS

| روند | توضیح |
|------|--------|
| **Row-Level Security** | افزایش استفاده از RLS بجای application-level filtering |
| **Tenant Context Middleware** | استاندارد شدن middleware pattern |
| **Config-as-Code per Tenant** | ذخیره config در دیتابیس بجای env vars |
| **Webhook-based Architecture** | برای Telegram bots، استفاده از webhook بجای polling |

_منبع: Web research 2024-2025, PostgreSQL documentation, FastAPI best practices_

---

## Integration Patterns Analysis

### Tenant Routing با Bot Token

برای پروژه remnabot که از Telegram Bot استفاده می‌کنه، الگوی routing با `bot_token` بهترین انتخابه:

#### Webhook URL Pattern

```
POST https://api.example.com/webhook/{bot_token}
```

| مزیت | توضیح |
|------|--------|
| **Tenant Identification** | `bot_token` خودش unique identifier هر tenant هست |
| **No Extra Auth** | Telegram خودش token رو verify می‌کنه |
| **Simple Routing** | Path parameter extraction در FastAPI |

#### پیاده‌سازی در FastAPI

```python
from fastapi import FastAPI, Path, Depends
from sqlalchemy.orm import Session

app = FastAPI()

async def get_tenant_from_token(
    bot_token: str = Path(..., description="Telegram Bot Token")
) -> Tenant:
    """Extract tenant from bot_token in URL path"""
    tenant = await get_tenant_by_bot_token(bot_token)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return tenant

@app.post("/webhook/{bot_token}")
async def telegram_webhook(
    update: dict,
    tenant: Tenant = Depends(get_tenant_from_token)
):
    # tenant context is now available
    await process_update(update, tenant)
```

_منبع: fastapi.tiangolo.com, core.telegram.org/bots/api_

### FastAPI Dependency Injection برای Tenant Context

#### الگوی Tenant Context Manager

```python
from contextvars import ContextVar
from typing import Optional

# Thread-safe tenant context
current_tenant: ContextVar[Optional[Tenant]] = ContextVar('current_tenant', default=None)

class TenantContext:
    """Request-scoped tenant context"""
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self._token = None
    
    def __enter__(self):
        self._token = current_tenant.set(self.tenant)
        return self
    
    def __exit__(self, *args):
        current_tenant.reset(self._token)

def get_current_tenant() -> Tenant:
    """Get tenant from context - use in any function"""
    tenant = current_tenant.get()
    if not tenant:
        raise RuntimeError("No tenant in context")
    return tenant
```

#### Middleware Pattern

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract tenant from path or header
        bot_token = request.path_params.get('bot_token')
        if bot_token:
            tenant = await get_tenant_by_bot_token(bot_token)
            with TenantContext(tenant):
                response = await call_next(request)
                return response
        return await call_next(request)
```

_منبع: fastapi.tiangolo.com/fa/features, Python contextvars documentation_

### Database Session Management per Tenant

#### SQLAlchemy Session با Tenant Filter

```python
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import event

def get_tenant_session(bot_id: uuid.UUID) -> Session:
    """Create session with automatic tenant filtering"""
    session = SessionLocal()
    
    # Set PostgreSQL session variable for RLS
    session.execute(
        text("SET app.current_tenant = :bot_id"),
        {"bot_id": str(bot_id)}
    )
    
    return session

# FastAPI Dependency
async def get_db(tenant: Tenant = Depends(get_current_tenant)):
    db = get_tenant_session(tenant.id)
    try:
        yield db
    finally:
        db.close()
```

#### الگوی Query Filter Automatic

```python
from sqlalchemy.orm import Query
from sqlalchemy import event

@event.listens_for(Query, "before_compile", retval=True)
def filter_by_tenant(query):
    """Automatically add bot_id filter to all queries"""
    tenant = current_tenant.get()
    if tenant:
        for desc in query.column_descriptions:
            entity = desc['entity']
            if hasattr(entity, 'bot_id'):
                query = query.filter(entity.bot_id == tenant.id)
    return query
```

_منبع: docs.sqlalchemy.org, PostgreSQL RLS documentation_

### API Authentication Patterns

#### JWT با Tenant Claim

```python
from jose import jwt
from datetime import datetime, timedelta

def create_tenant_token(user_id: int, bot_id: uuid.UUID) -> str:
    """Create JWT with tenant claim"""
    payload = {
        "sub": str(user_id),
        "bot_id": str(bot_id),
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

async def verify_tenant_token(token: str) -> dict:
    """Verify JWT and extract tenant"""
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return payload
```

#### سطوح دسترسی Multi-tenant

| نقش | دسترسی | توضیح |
|-----|--------|--------|
| **Super Admin** | همه tenantها | مدیر کل پلتفرم |
| **Tenant Admin** | فقط tenant خودش | مدیر ربات tenant |
| **Tenant User** | فقط داده‌های خودش | کاربر نهایی ربات |

```python
from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    TENANT_USER = "tenant_user"

def require_role(required_role: UserRole):
    """Dependency for role-based access"""
    async def check_role(
        current_user: User = Depends(get_current_user),
        tenant: Tenant = Depends(get_current_tenant)
    ):
        if current_user.role == UserRole.SUPER_ADMIN:
            return current_user
        if current_user.bot_id != tenant.id:
            raise HTTPException(403, "Access denied")
        if current_user.role.value < required_role.value:
            raise HTTPException(403, "Insufficient permissions")
        return current_user
    return check_role
```

_منبع: fastapi.tiangolo.com/fa/tutorial/security, OAuth2 specification_

### Webhook Handler Architecture

#### الگوی Webhook Processing

```
┌─────────────────────────────────────────────────────────────┐
│                    Incoming Webhook                          │
│              POST /webhook/{bot_token}                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    TenantMiddleware                          │
│         Extract tenant from bot_token                        │
│         Set tenant context (ContextVar)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database Session                          │
│         Set PostgreSQL session variable                      │
│         RLS policies automatically filter                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Bot Logic Layer                           │
│         aiogram handlers with tenant context                 │
│         All queries auto-filtered by tenant                  │
└─────────────────────────────────────────────────────────────┘
```

### Configuration per Tenant

#### Database-stored Config Pattern

```python
from pydantic import BaseModel
from typing import Optional

class TenantConfig(BaseModel):
    """Per-tenant configuration stored in database"""
    
    # Bot Settings
    bot_token: str
    bot_username: str
    
    # Payment Settings  
    zarinpal_merchant_id: Optional[str] = None
    card_to_card_enabled: bool = False
    card_number: Optional[str] = None
    
    # Feature Flags
    trial_enabled: bool = True
    trial_days: int = 7
    
    # Localization
    default_language: str = "fa"
    currency: str = "IRR"

# Load from database instead of env
async def get_tenant_config(bot_id: uuid.UUID) -> TenantConfig:
    config_row = await db.execute(
        select(TenantConfigModel).where(
            TenantConfigModel.bot_id == bot_id
        )
    )
    return TenantConfig(**config_row.to_dict())
```

_منبع: Pydantic documentation, FastAPI settings management_

### Event-Driven Integration

#### الگوی Publish-Subscribe برای Multi-tenant Events

```python
import redis.asyncio as redis

class TenantEventBus:
    """Redis-based event bus with tenant isolation"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def publish(self, bot_id: str, event_type: str, data: dict):
        """Publish event to tenant-specific channel"""
        channel = f"tenant:{bot_id}:{event_type}"
        await self.redis.publish(channel, json.dumps(data))
    
    async def subscribe(self, bot_id: str, event_type: str):
        """Subscribe to tenant-specific events"""
        channel = f"tenant:{bot_id}:{event_type}"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
```

_منبع: redis.io documentation, fadak.ir integration patterns_

---

## Architectural Patterns and Design

### System Architecture Pattern Selection

برای remnabot با هدف ۱۰۰-۲۰۰ tenant، معماری **Monolith با Multi-tenant Row-Level** بهترین انتخابه:

#### مقایسه معماری‌ها

| معماری | مناسب برای remnabot? | دلیل |
|--------|---------------------|------|
| **Monolith + Row-Level** | ✅ **بله** | ساده، کم‌هزینه، کافی برای ۲۰۰ tenant |
| Microservices | ❌ خیر | Overkill برای MVP، پیچیدگی بالا |
| Database-per-Tenant | ❌ خیر | هزینه بالا، مدیریت سخت |
| Schema-per-Tenant | ⚠️ احتمالی | پیچیده‌تر از Row-Level |

#### معماری پیشنهادی

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                     │
│              SSL Termination + Rate Limiting                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Webhook   │  │   REST API  │  │   Admin Panel API   │  │
│  │  Handlers   │  │   Endpoints │  │      Endpoints      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                              │                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Tenant Context Middleware               │    │
│  │         (Extract tenant from bot_token/JWT)          │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  Service Layer                       │    │
│  │    (Business Logic with tenant-aware operations)     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐
│   PostgreSQL    │  │    Redis    │  │   File Storage  │
│   (with RLS)    │  │   (Cache)   │  │   (per-tenant)  │
└─────────────────┘  └─────────────┘  └─────────────────┘
```

_منبع: fastapi.tiangolo.com, PostgreSQL documentation_

### Database Schema Design

#### Core Tables با bot_id

```sql
-- Tenant Table (Master)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_token VARCHAR(255) UNIQUE NOT NULL,
    bot_username VARCHAR(255) NOT NULL,
    owner_telegram_id BIGINT NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Subscription/Billing
    plan VARCHAR(50) DEFAULT 'free',
    plan_expires_at TIMESTAMP,
    
    -- Settings (JSON for flexibility)
    settings JSONB DEFAULT '{}'
);

-- Users Table (per-tenant)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    bot_id UUID NOT NULL REFERENCES tenants(id),
    telegram_id BIGINT NOT NULL,
    username VARCHAR(255),
    balance_tomans INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique per tenant
    UNIQUE(bot_id, telegram_id)
);

-- Subscriptions Table (per-tenant)
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    bot_id UUID NOT NULL REFERENCES tenants(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    
    -- VPN specific
    traffic_limit_gb INTEGER,
    traffic_used_gb FLOAT DEFAULT 0
);

-- Payments Table (per-tenant)
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    bot_id UUID NOT NULL REFERENCES tenants(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    amount_tomans INTEGER NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    
    -- Method-specific data
    payment_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Row Level Security Policies

```sql
-- Enable RLS on all tenant tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY tenant_isolation_users ON users
    USING (bot_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation_subscriptions ON subscriptions
    USING (bot_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation_payments ON payments
    USING (bot_id = current_setting('app.current_tenant')::uuid);

-- Super admin bypass (for platform admin)
CREATE POLICY super_admin_users ON users
    USING (current_setting('app.is_super_admin', true)::boolean = true);
```

#### ایندکس‌های بهینه

```sql
-- Composite indexes for common queries
CREATE INDEX idx_users_tenant_telegram ON users(bot_id, telegram_id);
CREATE INDEX idx_subscriptions_tenant_user ON subscriptions(bot_id, user_id);
CREATE INDEX idx_payments_tenant_status ON payments(bot_id, status);
CREATE INDEX idx_tenants_bot_token ON tenants(bot_token);
```

_منبع: postgresql.org/docs/current/ddl-rowsecurity.html_

### Migration Strategy: Single to Multi-tenant

#### فاز ۱: آماده‌سازی (بدون تغییر رفتار)

```python
# Step 1: Add bot_id column as nullable
ALTER TABLE users ADD COLUMN bot_id UUID;
ALTER TABLE subscriptions ADD COLUMN bot_id UUID;
ALTER TABLE payments ADD COLUMN bot_id UUID;

# Step 2: Create default tenant for existing data
INSERT INTO tenants (id, bot_token, bot_username, owner_telegram_id)
VALUES ('00000000-0000-0000-0000-000000000001', 'EXISTING_BOT_TOKEN', 'existing_bot', 123456);

# Step 3: Backfill bot_id for existing data
UPDATE users SET bot_id = '00000000-0000-0000-0000-000000000001' WHERE bot_id IS NULL;
UPDATE subscriptions SET bot_id = '00000000-0000-0000-0000-000000000001' WHERE bot_id IS NULL;
UPDATE payments SET bot_id = '00000000-0000-0000-0000-000000000001' WHERE bot_id IS NULL;
```

#### فاز ۲: اجباری کردن bot_id

```python
# Step 4: Make bot_id NOT NULL
ALTER TABLE users ALTER COLUMN bot_id SET NOT NULL;
ALTER TABLE subscriptions ALTER COLUMN bot_id SET NOT NULL;
ALTER TABLE payments ALTER COLUMN bot_id SET NOT NULL;

# Step 5: Add foreign key constraints
ALTER TABLE users ADD CONSTRAINT fk_users_tenant FOREIGN KEY (bot_id) REFERENCES tenants(id);
```

#### فاز ۳: فعال‌سازی RLS

```python
# Step 6: Enable RLS (after code is ready)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
# ... for other tables

# Step 7: Create policies
CREATE POLICY tenant_isolation_users ON users USING (...);
```

#### فاز ۴: حذف آثار روسی و تغییر واحد پول

```python
# Currency migration: kopeks to tomans
# Note: 1 kopek ≠ 1 toman, need conversion logic

# Option 1: Add new column, migrate, drop old
ALTER TABLE users ADD COLUMN balance_tomans INTEGER DEFAULT 0;
UPDATE users SET balance_tomans = balance_toman / 100; -- یا نرخ تبدیل مناسب
ALTER TABLE users DROP COLUMN balance_toman;

# Option 2: Rename and update values
ALTER TABLE users RENAME COLUMN balance_toman TO balance_tomans;
UPDATE users SET balance_tomans = balance_tomans / 100;
```

_منبع: PostgreSQL migration best practices_

### Scalability Patterns for 100-200 Tenants

#### Horizontal Scaling Strategy

| مرحله | تعداد Tenant | زیرساخت |
|-------|-------------|---------|
| **MVP** | ۱-۵۰ | Single VPS (4GB RAM, 2 vCPU) |
| **Growth** | ۵۰-۱۰۰ | Single VPS (8GB RAM, 4 vCPU) |
| **Scale** | ۱۰۰-۲۰۰ | 2 App Servers + Load Balancer |
| **Enterprise** | ۲۰۰+ | Kubernetes + Auto-scaling |

#### Performance Optimizations

```python
# 1. Connection Pooling
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,          # Base connections
    max_overflow=30,       # Extra connections under load
    pool_pre_ping=True     # Health check
)

# 2. Redis Caching for Tenant Config
class TenantConfigCache:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.ttl = 300  # 5 minutes
    
    async def get_config(self, bot_id: str) -> TenantConfig:
        cached = await self.redis.get(f"tenant:{bot_id}:config")
        if cached:
            return TenantConfig.parse_raw(cached)
        
        config = await db_get_tenant_config(bot_id)
        await self.redis.setex(
            f"tenant:{bot_id}:config",
            self.ttl,
            config.json()
        )
        return config

# 3. Batch Processing for Webhooks
async def process_webhook_batch(updates: list[Update]):
    """Process multiple updates concurrently"""
    async with asyncio.TaskGroup() as tg:
        for update in updates:
            tg.create_task(process_single_update(update))
```

_منبع: SQLAlchemy documentation, Redis best practices_

### Security Architecture

#### Tenant Data Isolation Layers

```
┌─────────────────────────────────────────────────────────────┐
│                Layer 1: Network Level                        │
│  - SSL/TLS encryption                                        │
│  - Rate limiting per tenant                                  │
│  - IP whitelisting (optional)                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                Layer 2: Application Level                    │
│  - JWT with bot_id claim                                  │
│  - Tenant context middleware                                 │
│  - Input validation per tenant rules                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                Layer 3: Database Level                       │
│  - PostgreSQL RLS policies                                   │
│  - Session-based tenant isolation                            │
│  - Audit logging per tenant                                  │
└─────────────────────────────────────────────────────────────┘
```

#### Security Checklist

| بررسی | وضعیت | توضیح |
|-------|--------|--------|
| RLS Policies | ✅ | همه جداول tenant-aware |
| JWT Validation | ✅ | bot_id در token |
| Input Sanitization | ✅ | Pydantic validation |
| SQL Injection | ✅ | SQLAlchemy ORM |
| Audit Logging | ✅ | Log همه عملیات حساس |
| Encryption at Rest | ⚠️ | اختیاری برای MVP |
| Backup per Tenant | ⚠️ | فاز بعدی |

_منبع: OWASP SaaS Security Guidelines_

### Deployment Architecture

#### Docker Compose برای MVP

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql+asyncpg://...
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
          cpus: '1'

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=remnabot
      - POSTGRES_USER=remnabot
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 2G

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    deploy:
      resources:
        limits:
          memory: 512M

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - app

volumes:
  postgres_data:
  redis_data:
```

#### Resource Estimation for 200 Tenants

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **RAM** | 4GB | 8GB |
| **CPU** | 2 vCPU | 4 vCPU |
| **Storage** | 50GB SSD | 100GB SSD |
| **Bandwidth** | 1TB/month | 2TB/month |
| **Cost (VPS)** | ~$40/month | ~$80/month |

_منبع: Docker documentation, PostgreSQL resource planning_

---

## Implementation Approaches and Technology Adoption

### Technology Adoption Strategy

#### استراتژی مهاجرت تدریجی (Strangler Fig Pattern)

برای remnabot، استراتژی **مهاجرت تدریجی** پیشنهاد می‌شه:

```
Phase 1: Foundation (هفته ۱-۲)
├── Add tenant table + bot_id columns
├── Create default tenant for existing data
└── No behavior change yet

Phase 2: Isolation (هفته ۳-۴)
├── Implement TenantMiddleware
├── Enable PostgreSQL RLS
└── Test with single tenant

Phase 3: Multi-bot Support (هفته ۵-۶)
├── Webhook routing by bot_token
├── Per-tenant config from database
└── First additional tenant

Phase 4: Payment Integration (هفته ۷-۸)
├── ZarinPal per-tenant
├── Card-to-card system
└── Remove Russian gateways

Phase 5: Cleanup & Polish (هفته ۹-۱۰)
├── Remove Russian language artifacts
├── Currency migration (kopeks→tomans)
└── Admin panel updates
```

_منبع: martinfowler.com Strangler Fig Application pattern_

### Development Workflow and Tooling

#### ابزارهای پیشنهادی

| ابزار | کاربرد | وضعیت فعلی |
|-------|--------|------------|
| **pytest-asyncio** | تست async | ✅ موجود |
| **Alembic** | DB migrations | ✅ موجود |
| **pre-commit** | Code quality | ⚠️ پیشنهادی |
| **GitHub Actions** | CI/CD | ⚠️ پیشنهادی |
| **Sentry** | Error tracking | ⚠️ پیشنهادی |

#### Git Workflow پیشنهادی

```
main (production)
  ↑
develop (staging)
  ↑
feature/multi-tenancy-phase-1
feature/multi-tenancy-phase-2
feature/zarinpal-integration
feature/card-to-card-payment
```

#### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/pycqa/isort
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    hooks:
      - id: flake8
  
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/ -x
        language: system
        pass_filenames: false
```

_منبع: pre-commit.com, GitHub Actions documentation_

### Testing and Quality Assurance

#### استراتژی تست Multi-tenant

```python
# tests/conftest.py
import pytest
from uuid import uuid4

@pytest.fixture
async def test_tenant(db_session):
    """Create isolated test tenant"""
    tenant = Tenant(
        id=uuid4(),
        bot_token=f"test_token_{uuid4().hex[:8]}",
        bot_username="test_bot"
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant

@pytest.fixture
async def tenant_context(test_tenant):
    """Set tenant context for test"""
    with TenantContext(test_tenant):
        yield test_tenant

# tests/test_multi_tenant.py
async def test_user_isolation(tenant_context, db_session):
    """Users from one tenant shouldn't see other tenant's users"""
    # Create user in current tenant
    user = User(bot_id=tenant_context.id, telegram_id=123)
    db_session.add(user)
    await db_session.commit()
    
    # Query should only return current tenant's users
    users = await db_session.execute(select(User))
    assert all(u.bot_id == tenant_context.id for u in users.scalars())

async def test_rls_enforcement(db_session, test_tenant, other_tenant):
    """RLS should prevent cross-tenant access"""
    # Create user in other tenant
    other_user = User(bot_id=other_tenant.id, telegram_id=456)
    db_session.add(other_user)
    await db_session.commit()
    
    # Switch to test_tenant context
    with TenantContext(test_tenant):
        users = await db_session.execute(select(User))
        # Should NOT include other_tenant's user
        assert other_user not in users.scalars().all()
```

#### Test Coverage Goals

| Phase | Coverage Target | Focus |
|-------|----------------|-------|
| Phase 1 | ۶۰٪ | Database models, migrations |
| Phase 2 | ۷۰٪ | Tenant isolation, RLS |
| Phase 3 | ۷۵٪ | Webhook routing, config |
| Phase 4 | ۸۰٪ | Payment flows |
| Phase 5 | ۸۵٪ | Integration tests |

_منبع: pytest documentation, testing best practices_

### Deployment and Operations

#### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=app

  deploy-staging:
    needs: test
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: |
          ssh staging "cd /app && git pull && docker-compose up -d"

  deploy-production:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: |
          ssh production "cd /app && git pull && docker-compose up -d"
```

#### Monitoring Setup

```python
# app/monitoring.py
import structlog
from prometheus_client import Counter, Histogram

# Metrics
requests_total = Counter(
    'requests_total',
    'Total requests',
    ['bot_id', 'endpoint', 'status']
)

request_latency = Histogram(
    'request_latency_seconds',
    'Request latency',
    ['bot_id', 'endpoint']
)

# Structured logging
logger = structlog.get_logger()

async def log_request(bot_id: str, endpoint: str, status: int, duration: float):
    requests_total.labels(bot_id, endpoint, status).inc()
    request_latency.labels(bot_id, endpoint).observe(duration)
    
    logger.info(
        "request_processed",
        bot_id=bot_id,
        endpoint=endpoint,
        status=status,
        duration_ms=duration * 1000
    )
```

_منبع: GitHub Actions documentation, Prometheus best practices_

### Team Organization and Skills

#### مهارت‌های مورد نیاز

| مهارت | سطح | توضیح |
|-------|-----|-------|
| **Python/FastAPI** | پیشرفته | ✅ موجود |
| **SQLAlchemy** | پیشرفته | ✅ موجود |
| **PostgreSQL RLS** | متوسط | 📚 نیاز به یادگیری |
| **aiogram** | پیشرفته | ✅ موجود |
| **Docker** | متوسط | ✅ موجود |
| **Redis** | متوسط | ✅ موجود |
| **ZarinPal API** | مبتدی | 📚 نیاز به یادگیری |

#### منابع یادگیری پیشنهادی

1. **PostgreSQL RLS:**
   - PostgreSQL Official Docs: Row Security Policies
   - "Multi-tenant Data Architecture" - AWS Whitepaper

2. **ZarinPal Integration:**
   - مستندات رسمی زرین‌پال
   - نمونه کدهای Python در GitHub

3. **Multi-tenant Patterns:**
   - fastapi-tenants library documentation
   - "Building Multi-Tenant SaaS Applications" - Martin Fowler

_منبع: pypi.org/project/fastapi-tenants, zarinpal.com/docs_

### Cost Optimization and Resource Management

#### تخمین هزینه‌های ماهانه

| آیتم | MVP (50 tenant) | Scale (200 tenant) |
|------|-----------------|-------------------|
| **VPS** | $40 (4GB/2vCPU) | $80 (8GB/4vCPU) |
| **Domain + SSL** | $15 | $15 |
| **Backup Storage** | $5 | $10 |
| **Monitoring** | Free (self-hosted) | $20 (managed) |
| **مجموع** | **~$60/month** | **~$125/month** |

#### Revenue Model Suggestion

| Plan | قیمت ماهانه | ویژگی‌ها |
|------|-------------|----------|
| **Free** | رایگان | ۱۰۰ کاربر، بدون پرداخت |
| **Starter** | ۵۰۰,۰۰۰ تومان | ۱۰۰۰ کاربر، کارت‌به‌کارت |
| **Pro** | ۱,۵۰۰,۰۰۰ تومان | نامحدود، زرین‌پال، پشتیبانی |

**Break-even:** با ۱۰ مشتری Starter = ~$125 → سودآوری

_منبع: VPS pricing comparison, SaaS pricing strategies_

### Risk Assessment and Mitigation

| ریسک | احتمال | تأثیر | کاهش |
|------|--------|-------|------|
| **Data Leak بین Tenants** | کم | بالا | RLS + تست‌های isolation |
| **Performance Degradation** | متوسط | متوسط | Caching + monitoring |
| **Migration Data Loss** | کم | بالا | Backup قبل از هر phase |
| **Payment Integration Bugs** | متوسط | بالا | Sandbox testing + logging |
| **Telegram API Changes** | کم | متوسط | aiogram updates tracking |

#### Rollback Strategy

```bash
# هر migration باید قابل rollback باشه
alembic downgrade -1

# Docker rollback
docker-compose down
docker tag app:current app:backup
docker-compose up -d --build

# Database rollback
pg_restore -d remnabot backup_before_phase_X.sql
```

---

## Technical Research Recommendations

### Implementation Roadmap

```
┌─────────────────────────────────────────────────────────────┐
│  Week 1-2: FOUNDATION                                        │
│  ├── Create tenants table                                    │
│  ├── Add bot_id to all models                             │
│  ├── Backfill existing data                                  │
│  └── ✅ Checkpoint: All data has bot_id                   │
├─────────────────────────────────────────────────────────────┤
│  Week 3-4: ISOLATION                                         │
│  ├── Implement TenantMiddleware                              │
│  ├── Enable PostgreSQL RLS                                   │
│  ├── Update all queries                                      │
│  └── ✅ Checkpoint: Single tenant works with RLS             │
├─────────────────────────────────────────────────────────────┤
│  Week 5-6: MULTI-BOT                                         │
│  ├── Webhook routing /webhook/{bot_token}                    │
│  ├── Per-tenant config from DB                               │
│  ├── Tenant admin panel basics                               │
│  └── ✅ Checkpoint: Second bot works independently           │
├─────────────────────────────────────────────────────────────┤
│  Week 7-8: PAYMENTS                                          │
│  ├── Remove Russian gateways (keep CryptoBot as example)     │
│  ├── Implement ZarinPal per-tenant                           │
│  ├── Implement Card-to-Card with admin approval              │
│  └── ✅ Checkpoint: Iranian payments working                 │
├─────────────────────────────────────────────────────────────┤
│  Week 9-10: CLEANUP                                          │
│  ├── Remove Russian language artifacts                       │
│  ├── Currency migration (kopeks → tomans)                    │
│  ├── English localization completion                         │
│  ├── Documentation update                                    │
│  └── ✅ Checkpoint: MVP Ready for beta testing               │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack Recommendations Summary

| Component | Current | Recommended | Action |
|-----------|---------|-------------|--------|
| **Database** | PostgreSQL | PostgreSQL + RLS | Enable RLS |
| **Cache** | Redis | Redis | No change |
| **API** | FastAPI | FastAPI | No change |
| **Bot** | aiogram 3 | aiogram 3 | No change |
| **Config** | .env | Database | Migrate |
| **Payment** | Russian gateways | ZarinPal + Card | Replace |
| **Currency** | Kopeks | Tomans | Migrate |

### Success Metrics and KPIs

| متریک | هدف MVP | هدف ۶ ماهه |
|--------|---------|------------|
| **Tenants فعال** | ۱۰ | ۵۰ |
| **Uptime** | ۹۹٪ | ۹۹.۵٪ |
| **Response Time** | <500ms | <200ms |
| **Test Coverage** | ۷۰٪ | ۸۵٪ |
| **Data Isolation Bugs** | ۰ | ۰ |
| **MRR** | $500 | $2,500 |

---

## Executive Summary

### 🎯 Key Findings

1. **Architecture:** Row-Level Multi-tenancy با PostgreSQL RLS بهترین انتخاب برای ۱۰۰-۲۰۰ tenant
2. **Routing:** Webhook-based tenant identification با `bot_token` در URL
3. **Migration:** استراتژی ۵ فازی با rollback capability
4. **Timeline:** ~۱۰ هفته برای MVP
5. **Cost:** ~$60-125/month زیرساخت

### ✅ Ready for Implementation

این تحقیق فنی پایه محکمی برای شروع پیاده‌سازی فراهم می‌کنه:

- [x] Technology Stack Analysis
- [x] Integration Patterns  
- [x] Architectural Patterns
- [x] Implementation Roadmap
- [x] Risk Assessment

### 📋 Next Steps

1. **بلافاصله:** شروع Phase 1 (Foundation)
2. **هفته آینده:** تنظیم CI/CD pipeline
3. **ماه آینده:** اولین tenant تست

---

*تحقیق فنی تکمیل شد - 2025-12-25*
*تولید شده توسط BMAD Research Workflow*
