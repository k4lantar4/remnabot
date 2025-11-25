# Architecture Documentation

## Executive Summary

The RemnaWave Bedolaga Bot is a comprehensive Telegram bot application for managing VPN subscriptions through the RemnaWave API. It follows a layered architecture pattern with clear separation of concerns: presentation layer (bot handlers and REST API), business logic layer (services), data access layer (database), and integration layer (external services).

## Technology Stack

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Language** | Python | 3.13+ | Core runtime |
| **Bot Framework** | aiogram | 3.22.0 | Telegram Bot API |
| **Web Framework** | FastAPI | 0.115.6 | REST API and webhooks |
| **Database** | PostgreSQL | 15+ | Primary data store |
| **Cache** | Redis | 7+ | Session storage, cart |
| **ORM** | SQLAlchemy | 2.0.43 | Database abstraction |
| **Migrations** | Alembic | 1.16.5 | Schema management |
| **Validation** | Pydantic | 2.11.9 | Data validation |
| **Async HTTP** | aiohttp | 3.12.15 | External API calls |
| **Container** | Docker | Latest | Deployment |

## Architecture Pattern

### Layered Architecture

The application follows a **layered architecture** with the following layers:

```
┌─────────────────────────────────────┐
│   Presentation Layer                │
│   - Bot Handlers (aiogram)          │
│   - REST API (FastAPI)              │
│   - Webhooks                        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Business Logic Layer               │
│   - Services (30+ services)          │
│   - Business rules                   │
│   - Workflow orchestration           │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Data Access Layer                  │
│   - SQLAlchemy Models (46+ models)   │
│   - CRUD Operations (33 modules)     │
│   - Database connections             │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Integration Layer                  │
│   - RemnaWave API                    │
│   - Payment Providers (9 providers)  │
│   - External services                │
└─────────────────────────────────────┘
```

### Design Patterns

1. **Service Layer Pattern** - Business logic encapsulated in services
2. **Repository Pattern** - Data access abstracted through CRUD modules
3. **Dependency Injection** - FastAPI dependencies for DB, auth
4. **Middleware Pattern** - Cross-cutting concerns (auth, logging, validation)
5. **Factory Pattern** - App factories for bot and web server
6. **Strategy Pattern** - Multiple payment providers, database modes

## System Architecture

### Component Overview

```
                    ┌─────────────┐
                    │   Telegram   │
                    │     API      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Bot (aiogram)│
                    │   Handlers    │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌───────▼──────┐  ┌────────▼────────┐
│   Services    │  │   Database    │  │  External APIs  │
│  (Business    │  │  (PostgreSQL)│  │  (RemnaWave,    │
│   Logic)      │  │              │  │   Payments)     │
└───────┬───────┘  └───────┬──────┘  └─────────────────┘
        │                  │
        └──────────────────┼──────────────────┐
                           │                  │
                    ┌──────▼───────┐  ┌───────▼──────┐
                    │     Redis    │  │  REST API    │
                    │   (Cache)    │  │  (FastAPI)   │
                    └──────────────┘  └──────────────┘
```

### Core Components

#### 1. Bot Application (`app/bot.py`)

- Initializes aiogram bot and dispatcher
- Registers all message and callback handlers
- Configures FSM (Finite State Machine) for user flows
- Sets up middleware chain

#### 2. Web Server (`app/webserver/unified_app.py`)

- Unified FastAPI application
- Handles Telegram webhooks
- Processes payment webhooks
- Serves REST API endpoints
- Serves static files (Mini App)

#### 3. Database Layer (`app/database/`)

- **Models** (`models.py`): 46+ SQLAlchemy models
- **CRUD** (`crud/`): 33 modules for data operations
- **Connection** (`database.py`): Async database sessions
- **Migrations** (`universal_migration.py`): Schema management

#### 4. Service Layer (`app/services/`)

30+ services handling business logic:
- User management
- Subscription lifecycle
- Payment processing
- Promo system
- Referral program
- Monitoring and maintenance
- Reporting

#### 5. External Integrations (`app/external/`)

- RemnaWave API client
- 9 payment provider integrations
- Webhook handlers

## Data Architecture

### Database Schema

**Core Entities:**
- Users (1:1 with Subscriptions)
- Subscriptions (trial/paid lifecycle)
- Transactions (all financial operations)
- Payment records (per provider)

**Promotional System:**
- PromoGroups (discount groups)
- PromoCodes (redeemable codes)
- PromoOffers (personal offers)
- DiscountOffers (active discounts)

**Support System:**
- Tickets (support requests)
- TicketMessages (conversation history)
- SupportAuditLog (action tracking)

**Marketing:**
- AdvertisingCampaigns (deeplink campaigns)
- Polls (user engagement)
- BroadcastHistory (message delivery)

**Infrastructure:**
- ServerSquads (RemnaWave servers)
- SystemSettings (configuration)
- WebApiTokens (API authentication)

### Data Flow

```
User Action → Handler → Service → CRUD → Database
                                    ↓
                              External API
                                    ↓
                              Update Database
                                    ↓
                              Notify User
```

## API Architecture

### REST API Structure

**Base URL**: `http://localhost:8080` (development) or configured domain (production)

**Authentication**: Bearer token or API key header

**Route Organization:**
- `/health` - System health checks
- `/users` - User management
- `/subscriptions` - Subscription operations
- `/transactions` - Financial operations
- `/promo-*` - Promotional system
- `/servers` - Server management
- `/tickets` - Support system
- `/stats` - Analytics
- `/settings` - Configuration

See [API Contracts](./api-contracts.md) for detailed endpoint documentation.

### Webhook Architecture

**Telegram Webhook:**
- Receives updates from Telegram
- Validates secret token
- Processes through dispatcher
- Returns 200 OK

**Payment Webhooks:**
- Provider-specific handlers
- Validates signatures/credentials
- Updates payment status
- Triggers subscription activation

## Integration Architecture

### RemnaWave Integration

**Synchronization Flow:**
1. Fetch servers/squads from RemnaWave API
2. Update local ServerSquad records
3. Sync user subscriptions
4. Create/update RemnaWave users

**Auto-sync:**
- Scheduled background task
- Configurable times (e.g., 03:00, 15:00)
- Runs on startup
- Manual trigger via API

### Payment Provider Integration

**Supported Providers:**
1. Telegram Stars (native)
2. Tribute
3. YooKassa (SBP + cards)
4. CryptoBot (crypto)
5. Heleket (crypto)
6. MulenPay (SBP)
7. Pal24/PayPalych (SBP + cards)
8. Platega (SBP + cards)
9. WATA

**Payment Flow:**
1. User initiates payment
2. Service creates payment record
3. Redirect to provider
4. Provider webhook confirms
5. Update transaction status
6. Activate subscription

## Security Architecture

### Authentication & Authorization

**Bot Users:**
- Telegram ID-based authentication
- Admin check via ADMIN_IDS
- Channel subscription verification

**API Access:**
- Token-based authentication
- Token management via `/tokens` API
- Rate limiting per token

### Data Protection

- Environment variable secrets
- Encrypted database connections (production)
- Secure webhook validation
- Input validation (Pydantic)
- SQL injection prevention (ORM)

### Security Middleware

- `auth.py` - Admin authentication
- `channel_checker.py` - Subscription verification
- `display_name_restriction.py` - Username validation
- `throttling.py` - Rate limiting

## Scalability Considerations

### Current Architecture

- **Single instance** deployment
- **PostgreSQL** for persistence
- **Redis** for caching and cart
- **Async operations** throughout

### Scaling Options

**Vertical Scaling:**
- Increase container resources
- Optimize database queries
- Add database indexes

**Horizontal Scaling:**
- Multiple bot instances behind load balancer
- PostgreSQL read replicas
- Redis cluster
- Shared state via database/Redis

### Performance Optimizations

- Async/await throughout
- Database connection pooling
- Redis caching for hot data
- Eager loading for relationships
- Background task processing

## Deployment Architecture

### Container Structure

```
┌─────────────────────────────────┐
│      Docker Compose Stack       │
├─────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐   │
│  │   Bot    │  │ Postgres │   │
│  │ Container│  │ Container │   │
│  └────┬─────┘  └────┬─────┘   │
│       │             │          │
│  ┌────▼─────────────▼─────┐   │
│  │      Redis Container    │   │
│  └────────────────────────┘   │
└─────────────────────────────────┘
```

### Network Architecture

```
Internet
   │
   ▼
┌─────────────┐
│ Reverse     │  HTTPS (443)
│ Proxy       │
│ (nginx/     │
│  Caddy)     │
└──────┬──────┘
       │ HTTP (8080)
       ▼
┌─────────────┐
│  Bot App    │
│  (FastAPI)  │
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
┌──▼──┐ ┌─▼──┐
│Post │ │Redis│
│gres │ │     │
└─────┘ └─────┘
```

## Monitoring & Observability

### Health Checks

- `/health/unified` - Overall system status
- `/health/database` - Database connectivity
- `/health/telegram-webhook` - Webhook queue status
- `/health/payment-webhooks` - Payment system status

### Logging

- Structured logging via Python logging
- File-based logs: `logs/bot.log`
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request logging middleware (optional)

### Monitoring Services

- **MonitoringService**: RemnaWave panel health
- **MaintenanceService**: Auto-maintenance mode
- **ReportingService**: Scheduled reports
- **VersionService**: Update checking

## Error Handling

### Global Error Handler

- Catches unhandled exceptions
- Logs errors with context
- Returns user-friendly messages
- Prevents bot crashes

### Error Recovery

- Database connection retries
- External API retries with backoff
- Graceful degradation
- Automatic service restart (Docker)

## Future Architecture Considerations

### Potential Improvements

1. **Microservices**: Split into separate services (bot, API, payments)
2. **Message Queue**: Add RabbitMQ/Kafka for async processing
3. **Caching Layer**: Expand Redis usage
4. **CDN**: Static asset delivery
5. **Monitoring**: Prometheus + Grafana
6. **Tracing**: OpenTelemetry for distributed tracing

## Technology Decisions

### Why aiogram 3?

- Modern async/await support
- Type hints throughout
- Active development
- Excellent documentation

### Why FastAPI?

- High performance
- Automatic API documentation
- Type validation (Pydantic)
- Async support

### Why PostgreSQL?

- ACID compliance
- Rich feature set
- Excellent performance
- Production-ready

### Why Redis?

- Fast in-memory storage
- Perfect for sessions/cart
- Pub/sub capabilities
- Simple deployment

## Conclusion

The architecture is designed for:
- **Maintainability**: Clear separation of concerns
- **Scalability**: Async operations, horizontal scaling ready
- **Reliability**: Error handling, health checks, monitoring
- **Security**: Authentication, validation, secure defaults
- **Extensibility**: Modular design, easy to add features

The layered architecture provides a solid foundation for current needs while allowing for future growth and optimization.

