# Project Documentation Index

## Project Overview

- **Type**: Monolith Backend
- **Primary Language**: Python 3.13
- **Architecture**: Layered Architecture
- **Framework**: aiogram 3.22, FastAPI 0.115.6

## Quick Reference

- **Tech Stack**: Python 3.13, aiogram, FastAPI, PostgreSQL 15, Redis 7
- **Entry Point**: `main.py` (application orchestrator)
- **Architecture Pattern**: Layered Architecture (Presentation → Business Logic → Data Access → Integration)

## Generated Documentation

### Core Documentation

- [Project Overview](./project-overview.md) - Executive summary and project information
- [Architecture](./architecture.md) - System architecture, design patterns, and component overview
- [Source Tree Analysis](./source-tree-analysis.md) - Complete project structure with annotations
- [API Contracts](./api-contracts.md) - Comprehensive REST API endpoint documentation
- [Data Models](./data-models.md) - Complete database schema and model documentation

### Operational Documentation

- [Development Guide](./development-guide.md) - Local development setup, workflows, and common tasks
- [Deployment Guide](./deployment-guide.md) - Production deployment, configuration, and operations

## Existing Documentation

- [README.md](../README.md) - Project introduction and quick start
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [web-admin-integration.md](./web-admin-integration.md) - Web admin panel integration guide
- [miniapp-setup.md](./miniapp-setup.md) - Telegram Mini App setup guide
- [project_structure_reference.md](./project_structure_reference.md) - Quick navigation reference
- [referral_program_setting.md](./referral_program_setting.md) - Referral program configuration
- [persistent_cart_system.md](./persistent_cart_system.md) - Shopping cart system documentation

## Getting Started

### For Developers

1. **Setup Environment**: See [Development Guide](./development-guide.md#environment-setup)
2. **Understand Architecture**: Read [Architecture](./architecture.md)
3. **Explore Codebase**: Review [Source Tree Analysis](./source-tree-analysis.md)
4. **API Development**: Reference [API Contracts](./api-contracts.md)

### For DevOps

1. **Deployment**: Follow [Deployment Guide](./deployment-guide.md)
2. **Configuration**: Review environment variables in deployment guide
3. **Monitoring**: Check health endpoints and logging setup

### For AI-Assisted Development

**Primary Entry Points:**
- **Architecture**: [architecture.md](./architecture.md) - Understand system design
- **API Reference**: [api-contracts.md](./api-contracts.md) - API endpoints and schemas
- **Data Models**: [data-models.md](./data-models.md) - Database schema and relationships
- **Source Structure**: [source-tree-analysis.md](./source-tree-analysis.md) - Code organization

**When Working On:**
- **New Features**: Start with architecture.md, then source-tree-analysis.md
- **API Changes**: Reference api-contracts.md and data-models.md
- **Database Changes**: See data-models.md, then development-guide.md for migrations
- **External Integrations**: Check architecture.md integration section
- **Bug Fixes**: Review relevant service in source-tree-analysis.md

## Project Structure Summary

```
remnabot/
├── app/                    # Main application package
│   ├── handlers/          # Bot message handlers
│   ├── services/          # Business logic (30+ services)
│   ├── database/          # Data layer (models, CRUD)
│   ├── webapi/            # REST API (22 route modules)
│   ├── external/          # External integrations
│   ├── middlewares/       # Request processing
│   └── utils/             # Shared utilities
├── tests/                  # Test suite
├── migrations/            # Database migrations
├── docs/                  # Documentation (this directory)
└── main.py               # Application entry point
```

## Key Components

### Application Layers

1. **Presentation Layer**
   - Bot handlers (`app/handlers/`)
   - REST API (`app/webapi/routes/`)
   - Webhooks (`app/webserver/`)

2. **Business Logic Layer**
   - Services (`app/services/`) - 30+ services
   - Business rules and workflows

3. **Data Access Layer**
   - Models (`app/database/models.py`) - 46+ models
   - CRUD operations (`app/database/crud/`) - 33 modules

4. **Integration Layer**
   - External APIs (`app/external/`)
   - Payment providers (9 providers)
   - RemnaWave API

### Database

- **Primary**: PostgreSQL 15+
- **Development**: SQLite (optional)
- **Cache**: Redis 7+
- **Models**: 46+ SQLAlchemy models
- **Migrations**: Alembic

### API

- **Framework**: FastAPI
- **Endpoints**: 50+ REST endpoints
- **Authentication**: Token-based
- **Documentation**: OpenAPI/Swagger (when enabled)

## Technology Stack Details

| Component | Technology | Version |
|-----------|-----------|---------|
| Python | 3.13+ | - |
| Bot Framework | aiogram | 3.22.0 |
| Web Framework | FastAPI | 0.115.6 |
| Database | PostgreSQL | 15+ |
| Cache | Redis | 7+ |
| ORM | SQLAlchemy | 2.0.43 |
| Migrations | Alembic | 1.16.5 |
| Validation | Pydantic | 2.11.9 |

## Common Development Tasks

### Adding a Feature

1. Review [Architecture](./architecture.md) for design patterns
2. Check [Source Tree Analysis](./source-tree-analysis.md) for module organization
3. Add handler in `app/handlers/` (if user-facing)
4. Add service in `app/services/` (business logic)
5. Update models if needed (see [Data Models](./data-models.md))
6. Create migration (see [Development Guide](./development-guide.md))

### Working with API

1. Review [API Contracts](./api-contracts.md) for endpoint structure
2. Check existing routes in `app/webapi/routes/`
3. Add schema in `app/webapi/schemas/`
4. Register route in `app/webapi/app.py`

### Database Changes

1. Review [Data Models](./data-models.md) for schema
2. Update model in `app/database/models.py`
3. Create migration: `alembic revision --autogenerate`
4. Apply: `alembic upgrade head`
5. Update CRUD if needed

## Documentation Map

```
index.md (this file)
│
├── project-overview.md          → High-level project info
├── architecture.md              → System design and patterns
├── source-tree-analysis.md      → Code structure
├── api-contracts.md             → REST API reference
├── data-models.md               → Database schema
├── development-guide.md         → Development setup
└── deployment-guide.md          → Production deployment
```

## Quick Links by Topic

### Architecture & Design
- [Architecture](./architecture.md) - System architecture
- [Source Tree Analysis](./source-tree-analysis.md) - Code organization

### API & Data
- [API Contracts](./api-contracts.md) - REST API endpoints
- [Data Models](./data-models.md) - Database schema

### Operations
- [Development Guide](./development-guide.md) - Local development
- [Deployment Guide](./deployment-guide.md) - Production setup

### Integration
- [web-admin-integration.md](./web-admin-integration.md) - Admin panel
- [miniapp-setup.md](./miniapp-setup.md) - Mini App setup

## Next Steps

1. **New to the project?** Start with [Project Overview](./project-overview.md)
2. **Understanding the system?** Read [Architecture](./architecture.md)
3. **Ready to code?** See [Development Guide](./development-guide.md)
4. **Deploying?** Follow [Deployment Guide](./deployment-guide.md)

---

**Last Updated**: 2025-11-21  
**Documentation Version**: 1.2.0  
**Project Type**: Backend Monolith

