# Project Overview

## Project Information

**Project Name:** RemnaWave Bedolaga Bot (remnabot)

**Project Type:** Backend (Python)

**Repository Type:** Monolith

**Primary Language:** Python 3.13+

**Architecture Pattern:** Service-Oriented Architecture (Layered: Handlers → Services → Database)

## Executive Summary

RemnaWave Bedolaga Bot is a comprehensive Telegram bot application for managing VPN subscriptions through the RemnaWave API. The system provides fully automated user management, multi-provider payment processing, subscription lifecycle management, and extensive administrative capabilities.

### Key Features

- **Automated VPN Subscription Management** - Trial and paid subscriptions
- **Multi-Provider Payments** - 9 payment methods (Stars, YooKassa, CryptoBot, Heleket, MulenPay, Pal24, Platega, WATA, Tribute)
- **RemnaWave Integration** - Full API integration for user and server management
- **Administrative Web API** - REST API for external integrations
- **Mini App** - Telegram WebApp for user self-service
- **Referral Program** - Automated referral tracking and commissions
- **Promo System** - Promo codes, groups, and personal offers
- **Support System** - Ticket-based support with SLA tracking
- **Monitoring & Maintenance** - Automated health checks and maintenance mode

## Technology Stack Summary

| Category | Technology | Version |
|----------|-----------|---------|
| Language | Python | 3.13+ |
| Bot Framework | aiogram | 3.22.0 |
| API Framework | FastAPI | 0.115.6 |
| Database | PostgreSQL | 15+ |
| Database (Dev) | SQLite | via aiosqlite |
| ORM | SQLAlchemy | 2.0.43 |
| Migrations | Alembic | 1.16.5 |
| Cache | Redis | 5.0.1 |
| HTTP Server | uvicorn | 0.32.1 |
| Validation | Pydantic | 2.11.9 |

## Architecture Type

**Service-Oriented Architecture** with clear layer separation:

- **Presentation Layer:** Handlers, WebAPI routes, Keyboards
- **Business Logic Layer:** Services
- **Data Access Layer:** CRUD operations
- **Data Persistence Layer:** Database models and migrations

## Repository Structure

**Type:** Monolith - Single cohesive codebase

**Main Components:**
- Telegram bot handlers
- REST API endpoints
- Database models and CRUD
- Business logic services
- External API integrations
- Web server (unified)

## Quick Reference

### Entry Points

- **Application:** `main.py`
- **Bot Setup:** `app/bot.py`
- **Web Server:** `app/webserver/unified_app.py`
- **API:** `app/webapi/app.py`

### Key Directories

- `app/handlers/` - Telegram bot handlers
- `app/services/` - Business logic services
- `app/database/` - Data models and CRUD
- `app/webapi/` - REST API
- `app/external/` - External API clients

### Configuration

- **Settings:** `app/config.py` (103+ configuration methods)
- **Environment:** `.env` file
- **Docker:** `docker-compose.yml`

## Links to Detailed Documentation

### Generated Documentation

- [Architecture Documentation](./architecture-main.md) - Complete architecture overview
- [API Contracts](./api-contracts-main.md) - REST API endpoint documentation
- [Data Models](./data-models-main.md) - Database schema documentation
- [Source Tree Analysis](./source-tree-analysis.md) - Complete directory structure
- [Development Guide](./development-guide-main.md) - Setup and development instructions

### Existing Documentation

- [README.md](../README.md) - Main project documentation (Russian)
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines (Russian)
- [Mini App Setup](./miniapp-setup.md) - Mini app configuration guide (Russian)
- [Web Admin Integration](./web-admin-integration.md) - Web API integration guide (Russian)
- [Project Structure Reference](./project_structure_reference.md) - Project structure reference (Russian)
- [Persistent Cart System](./persistent_cart_system.md) - Cart system docs (Russian)
- [Referral Program Setting](./referral_program_setting.md) - Referral program docs (Russian)

## Getting Started

### Quick Start

1. **Clone repository:**
   ```bash
   git clone https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot.git
   cd remnawave-bedolaga-telegram-bot
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Start with Docker:**
   ```bash
   make up
   ```

4. **Or start locally:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python main.py
   ```

For detailed instructions, see [Development Guide](./development-guide-main.md).

## Project Statistics

- **Total API Routes:** 27 route modules, 100+ endpoints
- **Database Tables:** 40+ models
- **Services:** 30+ business logic services
- **Handlers:** 50+ handler modules
- **Payment Providers:** 9 integrated providers
- **Languages Supported:** 2 (Russian, English)

## Next Steps

1. Review [Architecture Documentation](./architecture-main.md) for system design
2. Check [API Contracts](./api-contracts-main.md) for integration options
3. Read [Development Guide](./development-guide-main.md) for setup instructions
4. Explore [Data Models](./data-models-main.md) for database schema
5. Browse [Source Tree Analysis](./source-tree-analysis.md) for code navigation
