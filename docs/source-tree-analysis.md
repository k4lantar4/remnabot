# Source Tree Analysis

## Project Root Structure

```
remnabot/
├── main.py                          # Application entry point - initializes bot, services, and web server
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker container definition
├── docker-compose.yml               # Multi-container orchestration (bot, postgres, redis)
├── docker-compose.local.yml         # Local development configuration
├── alembic.ini                      # Alembic migration configuration
├── app-config.json                 # Mini app configuration
├── .env.example                     # Environment variables template
│
├── app/                             # Main application package
│   ├── bot.py                       # Bot setup and dispatcher configuration
│   ├── config.py                    # Settings class with 103+ configuration methods
│   ├── states.py                    # FSM state definitions for user flows
│   │
│   ├── database/                    # Database layer
│   │   ├── database.py             # Database initialization and connection management
│   │   ├── models.py               # SQLAlchemy models (40+ tables)
│   │   ├── universal_migration.py  # Universal migration runner
│   │   └── crud/                   # CRUD operations for each model
│   │       ├── user.py
│   │       ├── subscription.py
│   │       ├── transaction.py
│   │       ├── promocode.py
│   │       ├── ticket.py
│   │       └── [30+ more CRUD modules]
│   │
│   ├── handlers/                    # Telegram bot message handlers
│   │   ├── start.py                # /start command and registration flow
│   │   ├── menu.py                 # Main menu display and navigation
│   │   ├── balance.py              # Balance management handlers
│   │   ├── promocode.py            # Promo code activation
│   │   ├── referral.py             # Referral program handlers
│   │   ├── support.py              # Support system handlers
│   │   ├── tickets.py              # Ticket system handlers
│   │   ├── server_status.py        # Server status display
│   │   ├── stars_payments.py       # Telegram Stars payment handlers
│   │   ├── simple_subscription.py  # Simple subscription flow
│   │   ├── polls.py                # Poll handlers
│   │   ├── common.py               # Common utility handlers
│   │   ├── webhooks.py             # Webhook handlers
│   │   │
│   │   ├── admin/                  # Administrative handlers
│   │   │   ├── main.py             # Admin panel main menu
│   │   │   ├── users.py            # User management
│   │   │   ├── subscriptions.py    # Subscription management
│   │   │   ├── promocodes.py       # Promo code management
│   │   │   ├── promo_groups.py     # Promo group management
│   │   │   ├── promo_offers.py     # Promo offer management
│   │   │   ├── campaigns.py        # Advertising campaign management
│   │   │   ├── messages.py         # Broadcast message management
│   │   │   ├── monitoring.py       # Monitoring and logs
│   │   │   ├── remnawave.py        # RemnaWave integration management
│   │   │   ├── statistics.py       # Statistics and analytics
│   │   │   ├── servers.py          # Server/squad management
│   │   │   ├── maintenance.py      # Maintenance mode management
│   │   │   ├── backup.py           # Backup management
│   │   │   ├── tickets.py          # Admin ticket management
│   │   │   ├── reports.py          # Automated reports
│   │   │   ├── bot_configuration.py # Bot settings management
│   │   │   ├── pricing.py          # Pricing configuration
│   │   │   ├── rules.py             # Service rules management
│   │   │   ├── privacy_policy.py   # Privacy policy management
│   │   │   ├── public_offer.py     # Public offer management
│   │   │   ├── faq.py              # FAQ management
│   │   │   ├── welcome_text.py      # Welcome text management
│   │   │   ├── user_messages.py    # Custom message management
│   │   │   ├── polls.py            # Poll management
│   │   │   ├── payments.py         # Payment system management
│   │   │   ├── trials.py           # Trial subscription management
│   │   │   ├── updates.py          # Version update management
│   │   │   ├── system_logs.py      # System log viewing
│   │   │   └── support_settings.py  # Support system settings
│   │   │
│   │   ├── subscription/           # Subscription flow handlers
│   │   │   ├── purchase.py         # Subscription purchase flow
│   │   │   ├── countries.py        # Server country selection
│   │   │   ├── devices.py          # Device management
│   │   │   ├── traffic.py          # Traffic package selection
│   │   │   ├── autopay.py          # Auto-renewal configuration
│   │   │   ├── promo.py            # Promo group selection
│   │   │   ├── happ.py             # Happ app integration
│   │   │   ├── links.py            # Subscription link management
│   │   │   ├── notifications.py   # Subscription notifications
│   │   │   ├── pricing.py         # Pricing display and calculation
│   │   │   ├── common.py          # Common subscription utilities
│   │   │   └── summary.py         # Subscription summary
│   │   │
│   │   └── balance/                # Payment method handlers
│   │       ├── main.py            # Balance top-up entry point
│   │       ├── stars.py           # Telegram Stars payments
│   │       ├── yookassa.py        # YooKassa payments
│   │       ├── cryptobot.py       # CryptoBot payments
│   │       ├── heleket.py         # Heleket payments
│   │       ├── mulenpay.py        # MulenPay payments
│   │       ├── pal24.py           # Pal24/PayPalych payments
│   │       ├── platega.py         # Platega payments
│   │       ├── wata.py            # WATA payments
│   │       └── tribute.py        # Tribute payments
│   │
│   ├── services/                   # Business logic services
│   │   ├── payment_service.py      # Unified payment processing
│   │   ├── payment_verification_service.py  # Payment verification automation
│   │   ├── subscription_service.py # Subscription business logic
│   │   ├── subscription_purchase_service.py  # Purchase flow logic
│   │   ├── subscription_renewal_service.py  # Auto-renewal logic
│   │   ├── subscription_checkout_service.py # Checkout cart logic
│   │   ├── subscription_auto_purchase_service.py  # Auto-purchase logic
│   │   ├── trial_activation_service.py      # Trial activation logic
│   │   ├── user_service.py         # User management logic
│   │   ├── user_cart_service.py    # Persistent cart service
│   │   ├── promocode_service.py    # Promo code validation
│   │   ├── promo_offer_service.py   # Promo offer management
│   │   ├── referral_service.py    # Referral program logic
│   │   ├── remnawave_service.py    # RemnaWave API integration
│   │   ├── remnawave_sync_service.py  # RemnaWave synchronization
│   │   ├── server_status_service.py  # Server status monitoring
│   │   ├── monitoring_service.py  # Bot monitoring
│   │   ├── maintenance_service.py # Maintenance mode management
│   │   ├── backup_service.py       # Database backup management
│   │   ├── reporting_service.py    # Automated reporting
│   │   ├── broadcast_service.py    # Message broadcasting
│   │   ├── campaign_service.py     # Advertising campaign logic
│   │   ├── admin_notification_service.py  # Admin notifications
│   │   ├── version_service.py      # Version checking
│   │   ├── system_settings_service.py  # Runtime settings management
│   │   ├── support_settings_service.py  # Support system settings
│   │   ├── notification_settings_service.py  # Notification configuration
│   │   ├── faq_service.py          # FAQ management
│   │   ├── privacy_policy_service.py  # Privacy policy management
│   │   ├── public_offer_service.py # Public offer management
│   │   ├── main_menu_button_service.py  # Main menu button management
│   │   ├── web_api_token_service.py  # API token management
│   │   ├── poll_service.py         # Poll management
│   │   ├── promo_group_assignment.py  # Auto promo group assignment
│   │   ├── external_admin_service.py  # External admin token sync
│   │   └── payment/                # Payment provider services
│   │       ├── stars.py           # Telegram Stars
│   │       ├── cryptobot.py       # CryptoBot
│   │       └── pal24.py          # Pal24
│   │
│   ├── external/                   # External API integrations
│   │   ├── remnawave_api.py       # RemnaWave API client
│   │   ├── telegram_stars.py      # Telegram Stars API
│   │   ├── tribute.py             # Tribute API
│   │   ├── cryptobot.py           # CryptoBot API
│   │   ├── heleket.py             # Heleket API
│   │   ├── pal24_client.py        # Pal24 API client
│   │   ├── yookassa_webhook.py    # YooKassa webhook handler
│   │   ├── pal24_webhook.py       # Pal24 webhook handler (Flask)
│   │   ├── heleket_webhook.py     # Heleket webhook handler
│   │   └── webhook_server.py      # Generic webhook server
│   │
│   ├── webapi/                     # REST API (FastAPI)
│   │   ├── app.py                 # FastAPI application factory
│   │   ├── server.py              # Uvicorn server wrapper
│   │   ├── dependencies.py       # API dependencies (auth, DB session)
│   │   ├── middleware.py         # Request logging middleware
│   │   ├── routes/                # API route handlers
│   │   │   ├── health.py          # Health check endpoints
│   │   │   ├── stats.py           # Statistics endpoints
│   │   │   ├── config.py          # Settings endpoints
│   │   │   ├── users.py           # User management endpoints
│   │   │   ├── subscriptions.py   # Subscription endpoints
│   │   │   ├── tickets.py         # Support ticket endpoints
│   │   │   ├── transactions.py    # Transaction endpoints
│   │   │   ├── promo_groups.py    # Promo group endpoints
│   │   │   ├── promo_offers.py    # Promo offer endpoints
│   │   │   ├── promocodes.py      # Promo code endpoints
│   │   │   ├── servers.py         # Server management endpoints
│   │   │   ├── remnawave.py       # RemnaWave integration endpoints
│   │   │   ├── miniapp.py         # Mini app endpoints
│   │   │   ├── tokens.py          # API token management
│   │   │   ├── pages.py           # Content page endpoints
│   │   │   ├── broadcasts.py      # Broadcast endpoints
│   │   │   ├── backups.py         # Backup endpoints
│   │   │   ├── campaigns.py       # Campaign endpoints
│   │   │   ├── polls.py           # Poll endpoints
│   │   │   ├── logs.py            # Log viewing endpoints
│   │   │   ├── partners.py        # Referral/partner endpoints
│   │   │   ├── main_menu_buttons.py  # Main menu button endpoints
│   │   │   ├── user_messages.py   # User message endpoints
│   │   │   ├── welcome_texts.py   # Welcome text endpoints
│   │   │   ├── media.py           # Media upload endpoints
│   │   │   └── subscription_events.py  # Subscription event endpoints
│   │   └── schemas/               # Pydantic request/response schemas
│   │       ├── users.py
│   │       ├── subscriptions.py
│   │       ├── tickets.py
│   │       ├── transactions.py
│   │       ├── miniapp.py
│   │       └── [20+ more schema modules]
│   │
│   ├── webserver/                  # Unified web server
│   │   ├── unified_app.py         # Combines FastAPI + Telegram webhook + payment webhooks
│   │   ├── telegram.py             # Telegram webhook routes
│   │   └── payments.py             # Payment webhook routes
│   │
│   ├── keyboards/                  # Inline and reply keyboard builders
│   │   ├── inline.py              # Inline keyboard builders
│   │   ├── reply.py               # Reply keyboard builders
│   │   └── admin.py               # Admin panel keyboards
│   │
│   ├── middlewares/                # aiogram middlewares
│   │   ├── auth.py                # Admin authentication
│   │   ├── logging.py             # Request logging
│   │   ├── throttling.py         # Rate limiting
│   │   ├── subscription_checker.py  # Subscription status checking
│   │   ├── maintenance.py         # Maintenance mode
│   │   ├── channel_checker.py    # Channel subscription checking
│   │   ├── display_name_restriction.py  # Display name validation
│   │   └── global_error.py       # Global error handling
│   │
│   ├── utils/                      # Utility functions
│   │   ├── formatters.py         # Text formatting utilities
│   │   ├── validators.py          # Input validation
│   │   ├── cache.py               # Caching utilities
│   │   ├── decorators.py          # Common decorators
│   │   ├── pagination.py          # Pagination helpers
│   │   ├── pricing_utils.py      # Price calculation utilities
│   │   ├── subscription_utils.py  # Subscription utilities
│   │   ├── user_utils.py          # User utilities
│   │   ├── promo_offer.py         # Promo offer utilities
│   │   ├── payment_utils.py      # Payment utilities
│   │   ├── message_patch.py       # Message method patching
│   │   ├── photo_message.py       # Photo message utilities
│   │   ├── miniapp_buttons.py     # Mini app button builders
│   │   ├── telegram_webapp.py     # Telegram WebApp validation
│   │   ├── currency_converter.py  # Currency conversion
│   │   ├── security.py            # Security utilities (token hashing)
│   │   ├── startup_timeline.py   # Startup progress tracking
│   │   ├── timezone.py            # Timezone-aware formatting
│   │   └── check_reg_process.py  # Registration process checking
│   │
│   └── localization/               # Localization system
│       ├── loader.py              # Locale file loading
│       ├── texts.py               # Text retrieval system
│       ├── default_locales/      # Default locale files (en.yml, ru.yml)
│       └── locales/               # User locale overrides
│
├── migrations/                     # Database migrations
│   └── alembic/                    # Alembic migration files
│       ├── env.py                 # Alembic environment
│       └── versions/              # Migration version files
│
├── tests/                          # Test suite
│   ├── conftest.py                # Pytest configuration
│   ├── external/                  # External API tests
│   ├── services/                  # Service layer tests
│   └── utils/                     # Utility function tests
│
├── docs/                           # Project documentation
│   ├── miniapp-setup.md           # Mini app setup guide
│   ├── web-admin-integration.md   # Web API integration guide
│   ├── project_structure_reference.md  # Project structure reference
│   ├── persistent_cart_system.md  # Cart system documentation
│   ├── referral_program_setting.md  # Referral program docs
│   ├── api-contracts-main.md      # API contracts (generated)
│   ├── data-models-main.md        # Data models (generated)
│   └── project-scan-report.json   # Workflow state file
│
├── locales/                        # Localization files
│   ├── ru.json                    # Russian translations
│   └── en.json                    # English translations
│
├── miniapp/                        # Telegram Mini App static files
│   ├── index.html                 # Mini app HTML
│   ├── app-config.json            # App configuration
│   └── redirect/                  # Redirect pages
│
├── assets/                         # Static assets
│   ├── bedolaga_app3.svg          # Logo
│   └── logo2.svg                  # Alternative logo
│
├── data/                           # Runtime data
│   ├── bot.db                     # SQLite database (if used)
│   └── backups/                   # Database backups
│
└── logs/                           # Application logs
    └── bot.log                     # Main log file
```

## Critical Directories

### Entry Points

- **`main.py`** - Application entry point
  - Initializes database
  - Sets up bot and dispatcher
  - Starts web server (if enabled)
  - Configures services and background tasks
  - Handles graceful shutdown

- **`app/bot.py`** - Bot setup
  - Creates Bot and Dispatcher instances
  - Configures FSM storage (Redis or Memory)
  - Registers all handlers
  - Sets up middlewares
  - Entry point: `setup_bot()`

### Core Application Structure

#### `app/database/`
- **Purpose:** Data persistence layer
- **Key Files:**
  - `models.py` - All SQLAlchemy models (40+ tables)
  - `database.py` - Database connection management
  - `universal_migration.py` - Migration runner
  - `crud/` - CRUD operations for each model

#### `app/handlers/`
- **Purpose:** Telegram bot message and callback handlers
- **Structure:**
  - Root level: User-facing handlers (start, menu, balance, etc.)
  - `admin/`: Administrative handlers (30+ modules)
  - `subscription/`: Subscription flow handlers
  - `balance/`: Payment method handlers

#### `app/services/`
- **Purpose:** Business logic layer
- **Key Services:**
  - Payment processing and verification
  - Subscription management
  - RemnaWave integration
  - Monitoring and maintenance
  - Backup and reporting
  - User and referral management

#### `app/webapi/`
- **Purpose:** REST API for external integrations
- **Structure:**
  - `routes/`: API endpoint handlers (27 route modules)
  - `schemas/`: Pydantic request/response models
  - `app.py`: FastAPI application factory
  - `server.py`: Uvicorn server wrapper

#### `app/webserver/`
- **Purpose:** Unified web server combining:
  - FastAPI (admin API)
  - Telegram webhook handler
  - Payment webhook handlers
  - Mini app static file serving

#### `app/external/`
- **Purpose:** External API clients and webhook handlers
- **Integrations:**
  - RemnaWave API
  - Payment providers (YooKassa, CryptoBot, Pal24, etc.)
  - Telegram Stars

### Integration Points

1. **RemnaWave Integration:**
   - `app/external/remnawave_api.py` - API client
   - `app/services/remnawave_service.py` - Business logic
   - `app/services/remnawave_sync_service.py` - Synchronization
   - `app/handlers/admin/remnawave.py` - Admin interface
   - `app/webapi/routes/remnawave.py` - API endpoints

2. **Payment Integration:**
   - `app/services/payment_service.py` - Unified payment service
   - `app/external/` - Provider-specific clients
   - `app/handlers/balance/` - Payment flow handlers
   - `app/webserver/payments.py` - Webhook handlers

3. **Database Integration:**
   - `app/database/models.py` - All models
   - `app/database/crud/` - Data access layer
   - `app/database/database.py` - Connection management

## Key File Locations

### Configuration
- **Settings:** `app/config.py` (Settings class with 103+ methods)
- **Environment:** `.env.example` (template)
- **Docker:** `docker-compose.yml`, `Dockerfile`

### State Management
- **FSM States:** `app/states.py` (16 state classes)
- **Storage:** Redis (primary) or Memory (fallback)

### Localization
- **Loader:** `app/localization/loader.py`
- **Texts:** `app/localization/texts.py`
- **Files:** `locales/ru.json`, `locales/en.json`

### Testing
- **Tests:** `tests/` directory
- **Fixtures:** `tests/conftest.py`

## Architecture Notes

### Request Flow (Telegram Bot)
1. Message received → Middlewares (auth, logging, throttling, etc.)
2. → Handler (user or admin)
3. → Service layer (business logic)
4. → Database layer (CRUD operations)
5. → Response sent to user

### Request Flow (REST API)
1. HTTP request → CORS middleware
2. → Authentication middleware (token validation)
3. → Route handler
4. → Service layer
5. → Database layer
6. → JSON response

### Service Layer Pattern
Services encapsulate business logic and coordinate between:
- Database operations (via CRUD)
- External APIs
- Other services
- Bot instance (for notifications)

### Database Access Pattern
- Models defined in `app/database/models.py`
- CRUD operations in `app/database/crud/`
- Services use CRUD modules, not direct model access
- Async/await pattern throughout
