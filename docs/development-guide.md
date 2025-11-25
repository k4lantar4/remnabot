# Development Guide

## Prerequisites

### Required Software

- **Python 3.13+** - Core runtime
- **PostgreSQL 15+** - Primary database (or SQLite for development)
- **Redis 7+** - Caching and cart storage
- **Docker & Docker Compose** - Containerized development (recommended)
- **Git** - Version control

### Optional Tools

- **Make** - For convenient command execution
- **pytest** - Testing framework
- **Alembic** - Database migrations

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot.git
cd remnawave-bedolaga-telegram-bot
```

### 2. Create Environment File

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Required Environment Variables

**Core Bot Configuration:**
- `BOT_TOKEN` - Telegram bot token from @BotFather
- `ADMIN_IDS` - Comma-separated list of admin Telegram IDs
- `BOT_RUN_MODE` - `polling`, `webhook`, or `both`

**Database Configuration:**
- `DATABASE_MODE` - `auto` (PostgreSQL/SQLite auto-detect), `postgres`, or `sqlite`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - PostgreSQL connection
- `SQLITE_PATH` - SQLite database path (if using SQLite)

**Redis Configuration:**
- `REDIS_URL` - Redis connection string (e.g., `redis://localhost:6379/0`)

**RemnaWave Integration:**
- `REMNAWAVE_API_URL` - RemnaWave panel URL
- `REMNAWAVE_API_KEY` - API authentication key
- `REMNAWAVE_SECRET_KEY` - Secret key for protected panels (optional)

**Web Server Configuration:**
- `WEB_API_ENABLED` - Enable/disable Web API
- `WEB_API_HOST` - API host (default: `0.0.0.0`)
- `WEB_API_PORT` - API port (default: `8080`)
- `WEB_API_DEFAULT_TOKEN` - Default API token
- `WEB_API_ALLOWED_ORIGINS` - CORS allowed origins

**Webhook Configuration:**
- `WEBHOOK_URL` - Public webhook URL
- `WEBHOOK_PATH` - Webhook path (default: `/webhook`)
- `WEBHOOK_SECRET_TOKEN` - Secret token for webhook validation

See `.env.example` for complete configuration options.

## Development Modes

### Docker Development (Recommended)

**Start services:**
```bash
make up              # Start in background
make up-follow       # Start with logs
```

**Stop services:**
```bash
make down
```

**Restart:**
```bash
make reload          # Restart in background
make reload-follow   # Restart with logs
```

**View logs:**
```bash
docker compose logs -f bot
```

### Local Development

**1. Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

**3. Setup local database:**

**Option A: PostgreSQL**
```bash
# Install PostgreSQL, then:
createdb remnawave_bot
# Update .env with PostgreSQL credentials
```

**Option B: SQLite (simpler for development)**
```bash
# Set in .env:
DATABASE_MODE=sqlite
SQLITE_PATH=./data/bot.db
```

**4. Setup Redis:**
```bash
# Install Redis, then:
redis-server
# Or use Docker:
docker run -d -p 6379:6379 redis:7-alpine
```

**5. Run migrations:**
```bash
# Automatic on startup, or manually:
alembic upgrade head
```

**6. Start application:**
```bash
python main.py
```

## Project Structure

See [Source Tree Analysis](./source-tree-analysis.md) for detailed structure.

### Key Directories

- **`app/handlers/`** - Bot message handlers
- **`app/services/`** - Business logic services
- **`app/database/`** - Database models and CRUD
- **`app/webapi/`** - REST API routes
- **`app/external/`** - External service integrations
- **`tests/`** - Test suite

## Development Workflow

### 1. Code Organization

**Adding a new feature:**
1. Create handler in `app/handlers/` (if user-facing)
2. Create service in `app/services/` (business logic)
3. Add CRUD operations in `app/database/crud/` (if needed)
4. Update models in `app/database/models.py` (if schema change)
5. Create migration: `alembic revision --autogenerate -m "description"`
6. Apply migration: `alembic upgrade head`

### 2. Database Migrations

**Create migration:**
```bash
alembic revision --autogenerate -m "Add new table"
```

**Review generated migration:**
```bash
# Check migrations/alembic/versions/ for new file
```

**Apply migration:**
```bash
alembic upgrade head
```

**Rollback:**
```bash
alembic downgrade -1
```

**Universal migration system:**
The app includes `app/database/universal_migration.py` for automatic schema updates.

### 3. Testing

**Run all tests:**
```bash
make test
# Or:
pytest -v
```

**Run specific test:**
```bash
pytest tests/services/test_user_service.py -v
```

**Run with coverage:**
```bash
pytest --cov=app --cov-report=html
```

### 4. Code Style

**Linting:**
```bash
# Install linting tools:
pip install flake8 black isort mypy

# Format code:
black app/
isort app/

# Check types:
mypy app/
```

## Common Development Tasks

### Adding a New Payment Provider

1. **Create service** in `app/services/`:
   ```python
   # app/services/newprovider_service.py
   class NewProviderService:
       async def create_payment(self, ...):
           ...
   ```

2. **Create webhook handler** in `app/external/`:
   ```python
   # app/external/newprovider_webhook.py
   class NewProviderWebhookHandler:
       ...
   ```

3. **Add to payment service** in `app/services/payment_service.py`

4. **Add configuration** in `app/config.py`:
   ```python
   NEWPROVIDER_ENABLED: bool = False
   NEWPROVIDER_API_KEY: str = ""
   ```

5. **Add handler registration** in `app/handlers/webhooks.py`

6. **Update models** if needed (payment tracking)

### Adding a New Admin Feature

1. **Create handler** in `app/handlers/admin/`:
   ```python
   # app/handlers/admin/newfeature.py
   async def handle_new_feature(message: Message):
       ...
   ```

2. **Create service** in `app/services/` if business logic needed

3. **Add API route** in `app/webapi/routes/` if REST API needed

4. **Register handlers** in `app/handlers/admin/main.py`

### Adding a New Database Model

1. **Define model** in `app/database/models.py`:
   ```python
   class NewModel(Base):
       __tablename__ = "new_models"
       id = Column(Integer, primary_key=True)
       ...
   ```

2. **Create CRUD operations** in `app/database/crud/newmodel.py`:
   ```python
   async def create_new_model(db: AsyncSession, ...):
       ...
   ```

3. **Create migration:**
   ```bash
   alembic revision --autogenerate -m "Add new_model table"
   alembic upgrade head
   ```

## Debugging

### Enable Debug Logging

Set in `.env`:
```env
LOG_LEVEL=DEBUG
```

### View Logs

**Docker:**
```bash
docker compose logs -f bot
```

**Local:**
```bash
tail -f logs/bot.log
```

### Database Inspection

**PostgreSQL:**
```bash
docker compose exec postgres psql -U remnawave_user -d remnawave_bot
# Or locally:
psql -U remnawave_user -d remnawave_bot
```

**SQLite:**
```bash
sqlite3 data/bot.db
```

### Common Issues

**Bot not responding:**
- Check `BOT_TOKEN` is correct
- Verify bot is running: `docker compose ps`
- Check logs for errors

**Database connection errors:**
- Verify database is running
- Check connection credentials in `.env`
- Ensure migrations are applied

**Webhook not working:**
- Verify `WEBHOOK_URL` is publicly accessible
- Check `WEBHOOK_SECRET_TOKEN` matches
- Review webhook logs

## Localization

### Adding a New Language

1. **Create locale file** in `app/localization/default_locales/`:
   ```yaml
   # app/localization/default_locales/fr.yml
   start:
     welcome: "Bienvenue"
   ```

2. **Update loader** in `app/localization/loader.py` if needed

3. **Add language option** in start handler

### Updating Translations

Edit files in:
- `app/localization/default_locales/` (YAML templates)
- `app/localization/locales/` (JSON runtime files)

## Performance Optimization

### Database Queries

- Use `selectinload()` for eager loading relationships
- Add database indexes for frequently queried fields
- Use async queries (`AsyncSession`)

### Caching

- Redis is used for cart storage and session data
- Consider caching frequently accessed data in services

### Background Tasks

- Use `asyncio.create_task()` for non-blocking operations
- Background services run in separate tasks (monitoring, reporting)

## Security Considerations

### Environment Variables

- Never commit `.env` file
- Use strong secrets for `WEBHOOK_SECRET_TOKEN`, `WEB_API_DEFAULT_TOKEN`
- Rotate API tokens regularly

### Database Security

- Use strong PostgreSQL passwords
- Restrict database access to application only
- Enable SSL for production database connections

### API Security

- All API endpoints require authentication
- Use rate limiting for public endpoints
- Validate all input data

## Building and Deployment

See [Deployment Guide](./deployment-guide.md) for production deployment.

### Build Docker Image

```bash
docker build -t remnawave-bot:latest .
```

### Run Tests Before Deployment

```bash
make test
```

## Getting Help

- **Documentation**: Check `docs/` directory
- **Issues**: [GitHub Issues](https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot/issues)
- **Community**: [Telegram Chat](https://t.me/+wTdMtSWq8YdmZmVi)

