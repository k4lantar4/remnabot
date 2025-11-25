# Project Overview

## Project Information

**Name**: RemnaWave Bedolaga Bot  
**Type**: Backend API Server (Monolith)  
**Primary Language**: Python 3.13  
**Architecture**: Layered Architecture  
**Repository Structure**: Monolith  

## Executive Summary

The RemnaWave Bedolaga Bot is a comprehensive Telegram bot application designed for managing VPN subscriptions through the RemnaWave API. It provides a complete solution for subscription management, payment processing, user administration, and integration with the RemnaWave VPN panel.

## Technology Stack Summary

| Category | Technologies |
|----------|-------------|
| **Runtime** | Python 3.13+ |
| **Bot Framework** | aiogram 3.22.0 |
| **Web Framework** | FastAPI 0.115.6 |
| **Database** | PostgreSQL 15+ / SQLite |
| **Cache** | Redis 7+ |
| **ORM** | SQLAlchemy 2.0.43 |
| **Migrations** | Alembic 1.16.5 |
| **Validation** | Pydantic 2.11.9 |
| **Container** | Docker + Docker Compose |

## Architecture Type

**Pattern**: Layered Architecture

- **Presentation Layer**: Bot handlers (aiogram), REST API (FastAPI)
- **Business Logic Layer**: Services (30+ services)
- **Data Access Layer**: Database models and CRUD operations
- **Integration Layer**: External APIs (RemnaWave, payment providers)

## Repository Structure

**Type**: Monolith  
**Parts**: 1 (single cohesive codebase)

The project is organized as a single Python package (`app/`) with clear module separation:
- Handlers for bot interactions
- Services for business logic
- Database layer for persistence
- Web API for external integrations
- External clients for third-party services

## Key Features

### User Features
- Subscription management (trial and paid)
- Multiple payment methods (9 providers)
- Referral program
- Promo code system
- Support ticket system
- Mini App interface
- Multi-language support (RU/EN)

### Admin Features
- Comprehensive admin panel
- User management
- Subscription management
- Payment configuration
- Promo system management
- Analytics and reporting
- Backup and restore
- System monitoring

### Technical Features
- REST API (50+ endpoints)
- Webhook support (Telegram + payments)
- Database migrations
- Auto-sync with RemnaWave
- Background services
- Health monitoring
- Maintenance mode

## Entry Points

- **Main Entry**: `main.py` - Application orchestrator
- **Bot Entry**: `app/bot.py` - Bot initialization
- **API Entry**: `app/webapi/app.py` - FastAPI application
- **Web Server**: `app/webserver/unified_app.py` - Unified web server

## Quick Reference

### Tech Stack
- **Framework**: aiogram 3, FastAPI
- **Database**: PostgreSQL 15, SQLite (dev)
- **Cache**: Redis 7
- **Architecture Pattern**: Layered Architecture

### Entry Points
- **Bot**: Telegram bot via aiogram
- **API**: REST API on port 8080
- **Webhooks**: Unified webhook server

### Architecture Pattern
- **Type**: Layered Architecture
- **Services**: 30+ business logic services
- **Models**: 46+ database models
- **API Routes**: 22 route modules

## Links to Detailed Documentation

- [Architecture Documentation](./architecture.md) - System architecture and design
- [API Contracts](./api-contracts.md) - REST API endpoints
- [Data Models](./data-models.md) - Database schema
- [Source Tree Analysis](./source-tree-analysis.md) - Project structure
- [Development Guide](./development-guide.md) - Development setup
- [Deployment Guide](./deployment-guide.md) - Production deployment

## Getting Started

1. **Setup**: See [Development Guide](./development-guide.md)
2. **Configuration**: Copy `.env.example` to `.env` and configure
3. **Run**: `make up` or `docker compose up -d`
4. **API Docs**: Visit `/docs` when API is enabled

## Project Statistics

- **Database Models**: 46+
- **API Endpoints**: 50+
- **Services**: 30+
- **Handlers**: 100+
- **Payment Providers**: 9
- **Supported Languages**: 2 (RU, EN)

## Repository Information

- **GitHub**: [remnawave-bedolaga-telegram-bot](https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot)
- **License**: MIT
- **Main Language**: Python
- **Documentation**: Comprehensive docs in `docs/` directory

