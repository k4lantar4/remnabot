# Development Guide - Main

## Prerequisites

### System Requirements

**Minimum:**
- 1 vCPU
- 512 MB RAM
- 10 GB disk space
- Ubuntu 20.04+ or Debian 11+
- Docker and Docker Compose

**Recommended:**
- 2+ vCPU
- 2+ GB RAM
- 50+ GB SSD
- Stable internet connection

### Required Software

- **Python:** 3.13+ (for local development)
- **Docker:** Latest version
- **Docker Compose:** Latest version
- **PostgreSQL:** 15+ (if running without Docker)
- **Redis:** 7+ (if running without Docker)
- **Git:** For version control
- **Make:** For convenience commands

## Installation

### Docker-based Setup (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot.git
   cd remnawave-bedolaga-telegram-bot
   ```

2. **Create required directories:**
   ```bash
   mkdir -p ./logs ./data ./data/backups ./data/referral_qr
   chmod -R 755 ./logs ./data
   sudo chown -R 1000:1000 ./logs ./data
   ```

3. **Install Docker:**
   ```bash
   sudo curl -fsSL https://get.docker.com | sh
   ```

4. **Install Make:**
   ```bash
   apt install make -y
   ```

5. **Configure environment:**
   ```bash
   cp .env.example .env
   nano .env  # Fill in tokens and settings
   ```

6. **Start services:**
   ```bash
   make up             # Start containers (detached)
   make up-follow      # Start containers with logs
   ```

### Manual Docker Setup

If you prefer not to use Make:

```bash
# 1. Clone repository
git clone https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot.git
cd remnawave-bedolaga-telegram-bot

# 2. Configure
cp .env.example .env
nano .env  # Fill in tokens and settings

# 3. Create directories
mkdir -p ./logs ./data ./data/backups ./data/referral_qr
chmod -R 755 ./logs ./data
sudo chown -R 1000:1000 ./logs ./data

# 4. Start all services
docker compose up -d

# 5. Check status
docker compose logs
```

### Local Development Setup (Without Docker)

1. **Create virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate  # Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install --no-cache-dir --upgrade pip
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL and Redis:**
   - Install PostgreSQL 15+ and Redis 7+
   - Create database: `remnawave_bot`
   - Update `.env` with connection details

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run database migrations:**
   ```bash
   python -c "import asyncio; from app.database.universal_migration import run_universal_migration; asyncio.run(run_universal_migration())"
   ```

6. **Start the application:**
   ```bash
   python main.py
   ```

## Environment Configuration

### Required Environment Variables

**Core Bot Settings:**
- `BOT_TOKEN` - Telegram bot token from @BotFather
- `ADMIN_IDS` - Comma-separated list of admin Telegram IDs

**Database Configuration:**
- `DATABASE_MODE` - `auto`, `postgresql`, or `sqlite`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - PostgreSQL settings
- `SQLITE_PATH` - SQLite database path (if using SQLite)

**Redis:**
- `REDIS_URL` - Redis connection URL (e.g., `redis://localhost:6379/0`)

**RemnaWave Integration:**
- `REMNAWAVE_API_URL` - RemnaWave panel URL
- `REMNAWAVE_API_KEY` - API key
- `REMNAWAVE_AUTH_TYPE` - `api_key` or `basic_auth`

### Optional Configuration

See `.env.example` for complete list of 200+ configuration options including:
- Payment provider settings
- Subscription pricing
- Promo groups and discounts
- Notification settings
- Web API configuration
- Webhook settings

## Build Process

### Docker Build

```bash
# Build Docker image
docker compose build

# Or using Make
make up  # Automatically builds if needed
```

### Local Build

No build step required for Python. Just install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

### Docker

```bash
# Start in detached mode
make up
# or
docker compose up -d

# Start with logs
make up-follow
# or
docker compose up

# Stop
make down
# or
docker compose down

# Restart
make reload
# or
docker compose restart bot
```

### Local

```bash
# Activate virtual environment
source .venv/bin/activate

# Run application
python main.py
```

## Testing

### Run Tests

```bash
# Using Make
make test

# Or directly
pytest -v

# With coverage
pytest --cov=app --cov-report=html
```

### Test Structure

- **Location:** `tests/` directory
- **Test Types:**
  - Unit tests for services
  - Integration tests for external APIs
  - Utility function tests
- **Fixtures:** `tests/conftest.py`

## Development Workflow

### Code Style

- Follow **PEP 8** style guide
- Use type hints for all functions
- Write docstrings for all functions and classes
- Use `snake_case` for functions and variables
- Use `PascalCase` for classes

### Git Workflow

- Use [Conventional Commits](https://www.conventionalcommits.org/)
- Commit types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Example: `git commit -m "feat(payments): add support for YooKassa webhook"`

### Common Development Tasks

**View logs:**
```bash
# Docker
docker compose logs -f bot

# Local
tail -f logs/bot.log
```

**Database access:**
```bash
# Docker PostgreSQL
docker compose exec postgres psql -U remnawave_user -d remnawave_bot

# Local PostgreSQL
psql -U remnawave_user -d remnawave_bot
```

**Redis access:**
```bash
# Docker
docker compose exec redis redis-cli

# Local
redis-cli
```

**Run migrations:**
```bash
# Automatic on startup, or manually:
python -c "import asyncio; from app.database.universal_migration import run_universal_migration; asyncio.run(run_universal_migration())"
```

## Deployment Configuration

### Docker Compose Services

**Services:**
- `bot` - Main application container
- `postgres` - PostgreSQL 15 database
- `redis` - Redis 7 cache

**Networks:**
- `bot_network` - Internal Docker network

**Volumes:**
- `postgres_data` - Database persistence
- `redis_data` - Redis persistence
- `./logs` - Application logs
- `./data` - Application data (SQLite, backups)

### Health Checks

**Bot health check:**
- Endpoint: `http://localhost:8080/health`
- Command: `wget --no-verbose --tries=1 --spider http://localhost:8080/health`

**PostgreSQL health check:**
- Command: `pg_isready -U remnawave_user -d remnawave_bot`

**Redis health check:**
- Command: `redis-cli ping`

### Port Configuration

- **Web API/Webhooks:** Port 8080 (configurable via `WEB_API_PORT`)
- **PostgreSQL:** Port 5432 (internal, can be exposed)
- **Redis:** Port 6379 (internal)

## CI/CD Configuration

### GitHub Actions

Workflows are located in `.github/workflows/`:
- `docker-hub.yml` - Docker Hub image building
- `docker-registry.yml` - Docker registry publishing

### Deployment Scripts

- `install_bot.sh` - Installation script (if present)

## Common Development Commands

### Make Commands

```bash
make help           # Show all available commands
make up             # Start containers (detached)
make up-follow      # Start containers with logs
make down           # Stop containers
make reload         # Restart containers (detached)
make reload-follow  # Restart containers with logs
make test           # Run tests
```

### Docker Commands

```bash
# View logs
docker compose logs -f bot

# Execute command in container
docker compose exec bot python -c "..."

# Access database
docker compose exec postgres psql -U remnawave_user -d remnawave_bot

# Access Redis
docker compose exec redis redis-cli

# View container status
docker compose ps

# View resource usage
docker stats
```

## Troubleshooting

### Common Issues

**Bot not responding:**
- Check `BOT_TOKEN` in `.env`
- Verify internet connection
- Check logs: `docker compose logs bot`

**Database errors:**
- Verify PostgreSQL is running: `docker compose ps postgres`
- Check connection settings in `.env`
- Verify database exists

**Webhook not working:**
- Check `WEBHOOK_URL` is accessible via HTTPS
- Verify `WEBHOOK_SECRET_TOKEN` is set
- Check reverse proxy configuration

**API not accessible:**
- Verify `WEB_API_ENABLED=true`
- Check port 8080 is not blocked
- Verify CORS settings in `WEB_API_ALLOWED_ORIGINS`

**Cart not persisting:**
- Verify Redis is running: `docker compose ps redis`
- Check `REDIS_URL` in `.env`

## Development Best Practices

1. **Always use virtual environment** for local development
2. **Test changes locally** before committing
3. **Follow code style guidelines** from CONTRIBUTING.md
4. **Write tests** for new features
5. **Update documentation** when adding features
6. **Use type hints** for better IDE support
7. **Handle errors gracefully** with proper logging
8. **Use async/await** for all I/O operations
9. **Validate all user input** before processing
10. **Never commit secrets** - use `.env` file

## Additional Resources

- **README.md** - Complete project documentation
- **CONTRIBUTING.md** - Contribution guidelines
- **docs/web-admin-integration.md** - Web API integration guide
- **docs/miniapp-setup.md** - Mini app setup guide
