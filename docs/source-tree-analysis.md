# Source Tree Analysis

## Project Root Structure

```
remnabot/
├── app/                    # Main application package
├── tests/                  # Test suite
├── migrations/             # Database migrations (Alembic)
├── docs/                   # Project documentation
├── miniapp/                # Telegram Mini App static files
├── data/                   # Application data (backups, QR codes)
├── logs/                   # Application logs
├── assets/                 # Static assets (images, logos)
├── locales/                # Localization files (JSON)
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker container definition
├── docker-compose.yml      # Docker Compose configuration
├── alembic.ini            # Alembic migration configuration
├── README.md              # Project documentation
└── CONTRIBUTING.md        # Contribution guidelines
```

## Application Package (`app/`)

### Core Application Files

- **`bot.py`** - Bot initialization and setup
- **`config.py`** - Configuration management (Settings class with 100+ settings)
- **`states.py`** - FSM (Finite State Machine) states for user interactions

### Database Layer (`app/database/`)

```
database/
├── __init__.py            # Database package initialization
├── database.py            # Database connection and session management
├── models.py              # SQLAlchemy ORM models (46+ models)
├── universal_migration.py # Universal database migration system
└── crud/                  # CRUD operations (33 modules)
    ├── user.py
    ├── subscription.py
    ├── transaction.py
    ├── promo_group.py
    ├── promo_code.py
    ├── server_squad.py
    ├── ticket.py
    └── ... (26 more)
```

**Purpose**: Data persistence layer with PostgreSQL/SQLite support, async operations, and comprehensive CRUD operations.

### Handlers (`app/handlers/`)

Telegram bot message and callback handlers organized by feature.

```
handlers/
├── __init__.py
├── start.py               # /start command and onboarding
├── menu.py                # Main menu and navigation
├── balance/               # Balance management (11 modules)
│   ├── topup.py
│   ├── history.py
│   └── ...
├── subscription/          # Subscription management (13 modules)
│   ├── purchase.py       # Subscription purchase flow
│   ├── countries.py      # Server selection
│   ├── devices.py         # Device management
│   ├── traffic.py         # Traffic package selection
│   ├── autopay.py         # Auto-renewal setup
│   └── ...
├── admin/                 # Admin panel handlers (31 modules)
│   ├── main.py           # Admin dashboard
│   ├── users.py          # User management
│   ├── subscriptions.py  # Subscription management
│   ├── statistics.py     # Analytics and reports
│   ├── payments.py       # Payment configuration
│   ├── promo_groups.py   # Promo group management
│   ├── promocodes.py     # Promo code management
│   ├── tickets.py        # Support ticket management
│   ├── campaigns.py       # Marketing campaigns
│   ├── remnawave.py      # RemnaWave integration
│   ├── backup.py         # Backup management
│   └── ...
├── support.py             # Support system
├── tickets.py             # Ticket handling
├── promocode.py          # Promo code redemption
├── referral.py           # Referral program
├── polls.py              # Poll participation
├── webhooks.py           # Webhook handlers
└── common.py             # Shared handler utilities
```

**Purpose**: User-facing and admin-facing bot interactions, organized by business domain.

### Services (`app/services/`)

Business logic layer - reusable services for core functionality.

```
services/
├── __init__.py
├── user_service.py                    # User management logic
├── subscription_service.py            # Subscription business logic
├── subscription_purchase_service.py   # Purchase flow
├── subscription_checkout_service.py   # Checkout process
├── subscription_auto_purchase_service.py  # Auto-renewal
├── subscription_renewal_service.py    # Renewal logic
├── payment_service.py                 # Payment processing
├── payment_verification_service.py    # Payment verification
├── promocode_service.py               # Promo code logic
├── promo_group_assignment.py         # Auto promo group assignment
├── promo_offer_service.py            # Promo offer management
├── referral_service.py                # Referral program logic
├── campaign_service.py                # Marketing campaigns
├── broadcast_service.py               # Message broadcasting
├── backup_service.py                  # Backup operations
├── reporting_service.py               # Report generation
├── monitoring_service.py              # System monitoring
├── maintenance_service.py             # Maintenance mode
├── version_service.py                 # Version checking
├── remnawave_service.py               # RemnaWave API integration
├── remnawave_sync_service.py         # Background sync
├── admin_notification_service.py      # Admin notifications
├── faq_service.py                     # FAQ management
├── privacy_policy_service.py         # Privacy policy
├── public_offer_service.py           # Terms of service
├── support_settings_service.py       # Support configuration
├── system_settings_service.py        # System settings
├── main_menu_button_service.py       # Menu button management
├── poll_service.py                   # Poll management
├── notification_settings_service.py  # Notification config
├── server_status_service.py          # Server status
├── user_cart_service.py              # Shopping cart (Redis)
├── web_api_token_service.py          # API token management
├── external_admin_service.py         # External admin integration
├── tribute_service.py                # Tribute payment
├── yookassa_service.py               # YooKassa payment
├── pal24_service.py                  # Pal24 payment
├── mulenpay_service.py              # MulenPay payment
├── platega_service.py                # Platega payment
└── wata_service.py                   # WATA payment
```

**Purpose**: Encapsulates business logic, external API integrations, and reusable functionality.

### Web API (`app/webapi/`)

FastAPI REST API for administrative operations and Mini App.

```
webapi/
├── __init__.py
├── app.py                 # FastAPI application factory
├── server.py             # Web API server wrapper
├── dependencies.py        # Dependency injection (auth, DB)
├── middleware.py          # Request logging middleware
├── routes/                # API route modules (22 files)
│   ├── health.py         # Health checks
│   ├── users.py          # User management API
│   ├── subscriptions.py  # Subscription API
│   ├── transactions.py   # Transaction API
│   ├── promo_groups.py   # Promo group API
│   ├── promo_offers.py   # Promo offer API
│   ├── promocodes.py     # Promo code API
│   ├── servers.py        # Server management API
│   ├── remnawave.py     # RemnaWave integration API
│   ├── tickets.py        # Support ticket API
│   ├── campaigns.py      # Campaign API
│   ├── polls.py          # Poll API
│   ├── pages.py          # Content pages API
│   ├── main_menu_buttons.py  # Menu button API
│   ├── miniapp.py        # Mini App API
│   ├── stats.py          # Statistics API
│   ├── config.py         # Settings API
│   ├── broadcasts.py     # Broadcast API
│   ├── backups.py        # Backup API
│   ├── logs.py           # Log access API
│   └── tokens.py         # Token management API
├── schemas/              # Pydantic request/response schemas (21 files)
│   ├── users.py
│   ├── subscriptions.py
│   ├── transactions.py
│   └── ...
└── background/            # Background task utilities
    ├── tasks.py
    └── ...
```

**Purpose**: RESTful API for external integrations, admin panel, and Mini App backend.

### Web Server (`app/webserver/`)

Unified web server combining Telegram webhooks, payment webhooks, and static file serving.

```
webserver/
├── __init__.py
├── unified_app.py        # Unified FastAPI app factory
├── telegram.py           # Telegram webhook handlers
└── payments.py           # Payment webhook handlers
```

**Purpose**: Single HTTP server handling all webhook endpoints and static file serving.

### External Integrations (`app/external/`)

External service clients and webhook handlers.

```
external/
├── remnawave_api.py      # RemnaWave API client
├── telegram_stars.py     # Telegram Stars payment
├── tribute.py            # Tribute payment
├── yookassa_webhook.py   # YooKassa webhook handler
├── cryptobot.py          # CryptoBot payment
├── heleket.py            # Heleket payment service
├── heleket_webhook.py    # Heleket webhook handler
├── pal24_client.py       # Pal24 API client
├── pal24_webhook.py      # Pal24 webhook handler (Flask)
├── wata_webhook.py       # WATA webhook handler
└── webhook_server.py     # Generic webhook server
```

**Purpose**: Integration with payment providers and external services.

### Middlewares (`app/middlewares/`)

Request processing middleware for bot handlers.

```
middlewares/
├── __init__.py
├── auth.py               # Admin authentication
├── channel_checker.py    # Channel subscription verification
├── display_name_restriction.py  # Username validation
├── global_error.py       # Global error handler
├── logging.py            # Request logging
├── maintenance.py         # Maintenance mode check
├── subscription_checker.py  # Subscription status check
└── throttling.py         # Rate limiting
```

**Purpose**: Cross-cutting concerns: authentication, validation, error handling, logging.

### Keyboards (`app/keyboards/`)

Telegram inline and reply keyboard builders.

```
keyboards/
├── admin.py              # Admin panel keyboards
├── inline.py             # Inline button keyboards
└── reply.py              # Reply button keyboards
```

**Purpose**: Reusable keyboard components for bot interfaces.

### Localization (`app/localization/`)

Multi-language support system.

```
localization/
├── loader.py             # Locale loading and management
├── texts.py              # Text content management
├── default_locales/      # Default locale templates (YAML)
│   ├── ru.yml
│   └── en.yml
└── locales/              # Runtime locale files (JSON)
    ├── ru.json
    ├── en.json
    └── ...
```

**Purpose**: Internationalization (i18n) support for Russian and English.

### Utilities (`app/utils/`)

Shared utility functions and helpers.

```
utils/
├── __init__.py
├── cache.py              # Caching utilities
├── check_reg_process.py  # Registration process checks
├── currency_converter.py  # Currency conversion
├── decorators.py         # Common decorators
├── formatters.py         # Text formatting
├── message_patch.py      # Message patching utilities
├── miniapp_buttons.py    # Mini App button helpers
├── pagination.py         # Pagination utilities
├── payment_utils.py      # Payment helpers
├── photo_message.py      # Photo message handling
├── price_display.py      # Price formatting
├── pricing_utils.py      # Pricing calculations
├── promo_offer.py        # Promo offer utilities
├── security.py           # Security utilities
├── startup_timeline.py    # Startup progress tracking
├── subscription_utils.py # Subscription helpers
├── telegram_webapp.py    # Telegram WebApp utilities
├── timezone.py           # Timezone handling
├── user_utils.py         # User helpers
└── validators.py         # Input validation
```

**Purpose**: Reusable utility functions across the application.

## Test Suite (`tests/`)

```
tests/
├── conftest.py           # Pytest configuration and fixtures
├── crud/                 # CRUD operation tests
├── external/             # External service tests
├── fixtures/             # Test data fixtures
├── integration/          # Integration tests
├── services/             # Service layer tests (22 modules)
├── utils/                # Utility function tests
└── webserver/            # Web server tests
```

**Purpose**: Comprehensive test coverage for critical functionality.

## Configuration Files

### Root Level

- **`main.py`** - Application entry point, orchestrates bot, web server, and services
- **`requirements.txt`** - Python package dependencies
- **`Dockerfile`** - Multi-stage Docker build for production
- **`docker-compose.yml`** - Docker Compose stack (bot, PostgreSQL, Redis)
- **`alembic.ini`** - Alembic migration configuration
- **`.env.example`** - Environment variable template

### Application Config

- **`app/config.py`** - Centralized settings management (100+ configuration options)
- **`app-config.json`** - Mini App configuration

## Data Directories

- **`data/backups/`** - Database backup files
- **`data/referral_qr/`** - Generated referral QR codes
- **`logs/`** - Application log files
- **`assets/`** - Static assets (logos, images)
- **`locales/`** - Runtime localization files

## Mini App (`miniapp/`)

Telegram Mini App static files and payment flows.

```
miniapp/
├── index.html            # Mini App main page
├── app-config.json       # Mini App configuration
├── payment/              # Payment flow pages
└── redirect/             # Redirect pages
```

**Purpose**: Web-based user interface for Telegram Mini App.

## Entry Points

### Primary Entry Point

**`main.py`** - Main application orchestrator:
- Initializes database
- Sets up bot (aiogram)
- Configures web server (FastAPI)
- Starts background services (monitoring, maintenance, reporting)
- Manages graceful shutdown

### Application Initialization Flow

1. **Configuration Loading** - Load settings from environment and database
2. **Database Initialization** - Connect to PostgreSQL/SQLite, run migrations
3. **Bot Setup** - Initialize aiogram bot, register handlers, configure FSM
4. **Service Initialization** - Start monitoring, maintenance, reporting services
5. **Web Server Startup** - Launch FastAPI server for webhooks and API
6. **Background Tasks** - Start async tasks for auto-sync, version checking, etc.

## Critical Directories Summary

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `app/handlers/` | Bot message handlers | User interactions, admin panel |
| `app/services/` | Business logic | Core functionality, integrations |
| `app/database/` | Data layer | Models, CRUD operations |
| `app/webapi/` | REST API | Admin API, Mini App backend |
| `app/external/` | External integrations | Payment providers, RemnaWave |
| `app/middlewares/` | Request processing | Auth, validation, logging |
| `app/utils/` | Shared utilities | Helpers, formatters, validators |

## Architecture Pattern

**Layered Architecture**:
- **Presentation Layer**: Handlers (bot), Web API (REST)
- **Business Logic Layer**: Services
- **Data Access Layer**: Database (CRUD, Models)
- **Integration Layer**: External services

**Key Design Patterns**:
- **Service Layer Pattern** - Business logic in services
- **Repository Pattern** - CRUD operations abstracted
- **Dependency Injection** - FastAPI dependencies
- **Middleware Pattern** - Cross-cutting concerns
- **Factory Pattern** - App factories (bot, web server)

