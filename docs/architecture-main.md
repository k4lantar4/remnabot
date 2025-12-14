# Architecture Documentation - Main

## Executive Summary

**RemnaWave Bedolaga Bot** is a comprehensive Telegram bot application for managing VPN subscriptions through the RemnaWave API. The system provides automated user management, payment processing, subscription lifecycle management, and administrative capabilities.

**Architecture Type:** Service-Oriented Architecture (Layered)

**Repository Type:** Monolith

**Primary Technology:** Python 3.13+ with AsyncIO

## Technology Stack

### Core Framework
- **Python:** 3.13+
- **AsyncIO:** Native async/await throughout
- **aiogram:** 3.22.0 - Telegram Bot Framework
- **FastAPI:** 0.115.6 - REST API Framework
- **Flask:** 3.1.0 - Webhook server for Pal24

### Database Layer
- **PostgreSQL:** 15+ (primary, via asyncpg 0.30.0)
- **SQLite:** Fallback/development (via aiosqlite 0.21.0)
- **SQLAlchemy:** 2.0.43 - ORM
- **Alembic:** 1.16.5 - Database migrations

### Caching & State
- **Redis:** 5.0.1 - Session storage, FSM state, cart persistence

### HTTP & Networking
- **uvicorn:** 0.32.1 - ASGI server
- **aiohttp:** 3.12.15 - Async HTTP client

### Data Validation
- **Pydantic:** 2.11.9 - Data validation
- **pydantic-settings:** 2.10.1 - Settings management

### Payment Integration
- **yookassa:** 3.7.0 - YooKassa SDK
- Custom integrations for: CryptoBot, Heleket, MulenPay, Pal24, Platega, WATA, Tribute, Telegram Stars

### Utilities
- **structlog:** 23.2.0 - Structured logging
- **APScheduler:** 3.11.0 - Task scheduling
- **cryptography:** >=41.0.0 - Security operations
- **python-dotenv:** 1.1.1 - Environment management

### Containerization
- **Docker** - Application containerization
- **docker-compose** - Multi-container orchestration

## Architecture Pattern

### Service-Oriented Architecture (Layered)

The application follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  (Handlers, WebAPI Routes, Keyboards)   │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Business Logic Layer            │
│           (Services)                    │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Data Access Layer               │
│      (CRUD Operations)                 │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Data Persistence Layer          │
│    (Database Models, Migrations)        │
└─────────────────────────────────────────┘
```

### Component Organization

1. **Handlers Layer** (`app/handlers/`)
   - User-facing message handlers
   - Admin panel handlers
   - Payment flow handlers
   - Subscription flow handlers

2. **Services Layer** (`app/services/`)
   - Business logic encapsulation
   - External API coordination
   - Background task management
   - State management

3. **Database Layer** (`app/database/`)
   - Models (SQLAlchemy ORM)
   - CRUD operations
   - Migration management

4. **External Integration Layer** (`app/external/`)
   - Payment provider clients
   - RemnaWave API client
   - Webhook handlers

5. **API Layer** (`app/webapi/`)
   - REST API endpoints
   - Request/response schemas
   - Authentication middleware

6. **Web Server Layer** (`app/webserver/`)
   - Unified FastAPI application
   - Telegram webhook routing
   - Payment webhook routing
   - Static file serving

## Data Architecture

### Database Design

**Primary Database:** PostgreSQL 15+
**Fallback:** SQLite (development)

**Key Design Principles:**
- Async/await throughout
- Connection pooling (20 base, 30 overflow)
- Read-committed isolation level
- Query performance monitoring
- Automatic connection health checks

### Core Entities

1. **User** - Central entity
   - One-to-One with Subscription
   - One-to-Many with Transactions
   - Many-to-Many with PromoGroups

2. **Subscription** - VPN subscription management
   - Trial and paid subscriptions
   - Traffic and device limits
   - Auto-renewal support

3. **Transaction** - Financial operations
   - Links to payment provider records
   - Supports multiple payment methods

4. **PromoGroup** - Discount management
   - Configurable discounts (servers, traffic, devices, periods)
   - Auto-assignment based on spending

### Data Flow

**User Registration:**
1. User sends /start → Handler
2. Service creates User record
3. Service creates Trial Subscription
4. Service syncs with RemnaWave API
5. Response sent to user

**Payment Processing:**
1. User initiates payment → Handler
2. Service creates payment record
3. Service calls payment provider API
4. Webhook receives confirmation
5. Service updates Transaction
6. Service updates User balance
7. Notification sent to user

**Subscription Purchase:**
1. User selects parameters → Handler
2. Service calculates price (with discounts)
3. Service checks balance
4. Service creates/updates Subscription
5. Service syncs with RemnaWave
6. Service creates Transaction
7. Response sent to user

## API Design

### REST API (FastAPI)

**Base URL:** `http://{WEB_API_HOST}:{WEB_API_PORT}` (default: 8080)

**Authentication:** Token-based (`X-API-Key` or `Authorization: Bearer`)

**Key Endpoint Categories:**
- Health & Monitoring (`/health`, `/stats`)
- User Management (`/users`)
- Subscription Management (`/subscriptions`)
- Support Tickets (`/tickets`)
- Payment Transactions (`/transactions`)
- Promo System (`/promo-groups`, `/promo-offers`, `/promo-codes`)
- RemnaWave Integration (`/remnawave/*`)
- Mini App (`/miniapp/*`)
- Content Management (`/pages`, `/welcome-texts`)
- System Management (`/settings`, `/tokens`, `/backups`, `/logs`)

**Total Routes:** 27 route modules with 100+ endpoints

### Unified Web Server

Single FastAPI application serves:
- Admin REST API
- Telegram webhook handler
- Payment webhook handlers (9 providers)
- Mini app static files
- Health check endpoints

**Port:** 8080 (configurable)

## Component Overview

### Telegram Bot Components

**Bot Setup** (`app/bot.py`):
- Creates Bot and Dispatcher
- Configures FSM storage (Redis/Memory)
- Registers all handlers
- Sets up middlewares

**Handlers** (`app/handlers/`):
- **User Handlers:** Start, menu, balance, promocode, referral, support, tickets
- **Admin Handlers:** 30+ modules for comprehensive admin panel
- **Subscription Handlers:** Purchase flow, settings, management
- **Payment Handlers:** Provider-specific payment flows

**Middlewares** (`app/middlewares/`):
- Authentication (admin check)
- Logging
- Throttling (rate limiting)
- Subscription status checking
- Maintenance mode
- Channel subscription checking
- Display name restrictions
- Global error handling

### Service Components

**Core Services:**
- `PaymentService` - Unified payment processing
- `SubscriptionService` - Subscription business logic
- `UserService` - User management
- `RemnaWaveService` - RemnaWave API integration
- `MonitoringService` - Bot health monitoring
- `MaintenanceService` - Maintenance mode management
- `BackupService` - Database backup management
- `ReportingService` - Automated reporting

**Specialized Services:**
- `PaymentVerificationService` - Automatic payment verification
- `SubscriptionPurchaseService` - Purchase flow logic
- `SubscriptionRenewalService` - Auto-renewal logic
- `TrialActivationService` - Trial activation
- `UserCartService` - Persistent cart (Redis)
- `PromoCodeService` - Promo code validation
- `ReferralService` - Referral program logic

### External Integration Components

**RemnaWave Integration:**
- `RemnaWaveAPI` - API client
- `RemnaWaveService` - Business logic wrapper
- `RemnaWaveSyncService` - Background synchronization

**Payment Providers:**
- YooKassa (SDK + webhook)
- CryptoBot (custom client + webhook)
- Pal24/PayPalych (custom client + Flask webhook)
- MulenPay (custom client + webhook)
- Heleket (custom client + webhook)
- WATA (custom client + webhook)
- Platega (custom client + webhook)
- Tribute (custom client + webhook)
- Telegram Stars (native integration)

## Source Tree

See `source-tree-analysis.md` for complete annotated directory tree.

### Critical Directories

- **`app/handlers/`** - All bot message handlers
- **`app/services/`** - Business logic services
- **`app/database/`** - Data models and CRUD
- **`app/webapi/`** - REST API implementation
- **`app/webserver/`** - Unified web server
- **`app/external/`** - External API clients
- **`app/middlewares/`** - Request processing middleware
- **`app/utils/`** - Utility functions

## Development Workflow

### Local Development

1. Create virtual environment
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` file
4. Start PostgreSQL and Redis (or use Docker)
5. Run migrations
6. Start application: `python main.py`

### Docker Development

1. Configure `.env` file
2. Create required directories
3. Start services: `make up` or `docker compose up -d`
4. View logs: `docker compose logs -f bot`

### Testing

- Test framework: pytest
- Test location: `tests/` directory
- Run tests: `make test` or `pytest -v`

See `development-guide-main.md` for complete development instructions.

## Deployment Architecture

### Container Architecture

**Services:**
- `bot` - Main application (Python 3.13)
- `postgres` - PostgreSQL 15 database
- `redis` - Redis 7 cache

**Network:**
- Internal Docker network: `bot_network`
- Port exposure: 8080 (web API/webhooks)

### Deployment Options

1. **Docker Compose** (recommended)
   - Single command deployment
   - Health checks included
   - Volume persistence

2. **Manual Docker**
   - Custom orchestration
   - External database/Redis

3. **Local Development**
   - Direct Python execution
   - Local PostgreSQL/Redis

### Reverse Proxy Configuration

The unified web server (port 8080) should be proxied through:
- Nginx
- Caddy
- Traefik
- Or similar reverse proxy

All traffic (webhooks, API, static files) goes through single port.

## Testing Strategy

### Test Organization

- **Unit Tests:** Service layer logic
- **Integration Tests:** External API interactions
- **Utility Tests:** Helper function validation

### Test Coverage

- Payment service scenarios
- External API clients
- Utility functions
- Formatters and validators

### Test Execution

```bash
make test        # Run all tests
pytest -v        # Verbose output
pytest --cov     # With coverage
```

## Security Architecture

### Authentication & Authorization

**Telegram Bot:**
- Admin check via `ADMIN_IDS` configuration
- Middleware-based authentication

**REST API:**
- Token-based authentication
- Token hashing (SHA-256/SHA-512)
- CORS protection

### Data Protection

- SQL injection prevention via ORM
- Input validation via Pydantic
- Rate limiting via ThrottlingMiddleware
- Display name restrictions
- Channel subscription enforcement

### Payment Security

- Webhook signature verification
- Secure token storage
- Transaction audit trail
- Payment status validation

## Performance Considerations

### Database Optimization

- Connection pooling (20 base, 30 overflow)
- Query compilation caching
- Read-committed isolation
- Connection health monitoring
- Slow query logging

### Caching Strategy

- Redis for FSM state
- Redis for cart persistence
- Redis for rate limiting
- System cache for settings

### Async Architecture

- Full async/await throughout
- Non-blocking I/O operations
- Background task processing
- Concurrent request handling

## Monitoring & Observability

### Logging

- Structured logging via structlog
- File and console handlers
- Timezone-aware timestamps
- Log rotation support

### Health Checks

- Unified health endpoint: `/health/unified`
- Database health: `/health/database`
- Pool metrics: `/metrics/pool`
- Telegram webhook status
- Payment webhook status

### Monitoring Services

- `MonitoringService` - Bot health monitoring
- `MaintenanceService` - Automatic maintenance mode
- `VersionService` - Update checking
- `ReportingService` - Automated reports

## Scalability Considerations

### Horizontal Scaling

- Stateless application design
- Redis for shared state
- Database connection pooling
- Background task isolation

### Vertical Scaling

- Async architecture supports high concurrency
- Connection pool tuning
- Worker configuration (webhook workers)
- Resource monitoring

## Integration Points

### RemnaWave API

- User synchronization (bidirectional)
- Squad/server synchronization
- Subscription management
- Traffic monitoring

### Payment Providers

- 9 payment methods supported
- Webhook-based confirmation
- Automatic verification
- Manual verification fallback

### Telegram

- Bot API (polling/webhook)
- Mini App integration
- Stars payments
- Webhook processing

## Future Considerations

### Potential Improvements

- Horizontal scaling support
- Message queue for background tasks
- Read replicas for database
- CDN for static assets
- Microservices extraction (if needed)

### Architecture Evolution

Current monolith architecture is suitable for:
- Small to medium scale (up to 100K users)
- Single deployment
- Simplified operations

For larger scale, consider:
- Service extraction
- Message queue integration
- Distributed caching
- Database sharding
