# Deployment Guide

## Overview

This guide covers production deployment of the RemnaWave Bedolaga Bot using Docker Compose. The application consists of three main services: the bot application, PostgreSQL database, and Redis cache.

## Prerequisites

### Server Requirements

**Minimum:**
- 1 vCPU
- 512 MB RAM
- 10 GB disk space
- Ubuntu 20.04+ or Debian 11+

**Recommended:**
- 2+ vCPU
- 2+ GB RAM
- 50+ GB SSD
- Stable internet connection

### Software Requirements

- Docker 20.10+
- Docker Compose 2.0+
- Make (optional, for convenience)

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot.git
cd remnawave-bedolaga-telegram-bot
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your configuration
```

**Critical settings:**
- `BOT_TOKEN` - Your Telegram bot token
- `ADMIN_IDS` - Your Telegram user ID(s)
- `REMNAWAVE_API_URL` - RemnaWave panel URL
- `REMNAWAVE_API_KEY` - RemnaWave API key
- Database credentials
- Redis URL

### 3. Create Required Directories

```bash
mkdir -p ./logs ./data ./data/backups ./data/referral_qr
chmod -R 755 ./logs ./data
sudo chown -R 1000:1000 ./logs ./data
```

### 4. Start Services

```bash
make up
# Or:
docker compose up -d --build
```

### 5. Verify Deployment

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f bot

# Health check
curl http://localhost:8080/health
```

## Production Configuration

### Environment Variables

**Bot Configuration:**
```env
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789,987654321
BOT_RUN_MODE=webhook  # Use webhook for production
```

**Database:**
```env
DATABASE_MODE=postgres
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=remnawave_bot
POSTGRES_USER=remnawave_user
POSTGRES_PASSWORD=strong_password_here
```

**Redis:**
```env
REDIS_URL=redis://redis:6379/0
```

**Web Server:**
```env
WEB_API_ENABLED=true
WEB_API_HOST=0.0.0.0
WEB_API_PORT=8080
WEB_API_DEFAULT_TOKEN=generate_strong_token_here
WEB_API_ALLOWED_ORIGINS=https://your-domain.com
```

**Webhook (Production):**
```env
BOT_RUN_MODE=webhook
WEBHOOK_URL=https://your-domain.com
WEBHOOK_PATH=/webhook
WEBHOOK_SECRET_TOKEN=generate_strong_token_here
WEBHOOK_DROP_PENDING_UPDATES=true
```

**RemnaWave:**
```env
REMNAWAVE_API_URL=https://your-panel.com
REMNAWAVE_API_KEY=your_api_key
REMNAWAVE_SECRET_KEY=secret_name:secret_value  # If panel is protected
```

### Generate Secure Tokens

```bash
# Webhook secret token
openssl rand -hex 32

# API default token
openssl rand -hex 32
```

## Reverse Proxy Setup

The bot runs on port 8080 internally. You need a reverse proxy (nginx, Caddy, etc.) for HTTPS.

### Nginx Configuration

```nginx
server {
    listen 80;
    listen 443 ssl http2;
    server_name api.your-domain.com;

    ssl_certificate /etc/ssl/certs/fullchain.pem;
    ssl_certificate_key /etc/ssl/private/privkey.pem;

    client_max_body_size 32m;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
        proxy_buffering off;
    }
}
```

### Caddy Configuration

```caddy
api.your-domain.com {
    reverse_proxy localhost:8080 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
    }
}
```

## Docker Compose Production Setup

### Recommended Production Configuration

```yaml
services:
  postgres:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 30s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s

  bot:
    build: .
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs:rw
      - ./data:/app/data:rw
      - ./locales:/app/locales:rw
    ports:
      - "127.0.0.1:8080:8080"  # Only bind to localhost, use reverse proxy
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1"]
      interval: 60s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
  redis_data:
```

## Webhook Configuration

### 1. Set Webhook URL

After reverse proxy is configured:

```bash
# The bot will automatically set webhook on startup if:
# - BOT_RUN_MODE=webhook
# - WEBHOOK_URL is set
# - Bot can reach the URL
```

### 2. Verify Webhook

```bash
curl https://your-domain.com/health/telegram-webhook
```

### 3. Manual Webhook Setup (if needed)

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/webhook" \
  -d "secret_token=<WEBHOOK_SECRET_TOKEN>"
```

## Payment Provider Webhooks

Configure webhook URLs in each payment provider's dashboard:

- **YooKassa**: `https://your-domain.com/yookassa-webhook`
- **CryptoBot**: `https://your-domain.com/cryptobot-webhook`
- **Tribute**: `https://your-domain.com/tribute-webhook`
- **Heleket**: `https://your-domain.com/heleket-webhook`
- **MulenPay**: `https://your-domain.com/mulenpay-webhook`
- **Pal24**: `https://your-domain.com/pal24-webhook`
- **Platega**: `https://your-domain.com/platega-webhook`
- **WATA**: `https://your-domain.com/wata-webhook`

## Database Backups

### Automatic Backups

Configure in `.env`:
```env
BACKUP_AUTO_ENABLED=true
BACKUP_INTERVAL_HOURS=24
BACKUP_TIME=03:00
BACKUP_NOTIFICATION_CHAT_ID=-1001234567890
```

### Manual Backup

```bash
# Via admin panel or API
# Or directly:
docker compose exec postgres pg_dump -U remnawave_user remnawave_bot > backup.sql
```

### Restore Backup

```bash
# Via admin panel or:
docker compose exec -T postgres psql -U remnawave_user remnawave_bot < backup.sql
```

## Monitoring

### Health Checks

**Unified health:**
```bash
curl https://your-domain.com/health/unified
```

**Database health:**
```bash
curl https://your-domain.com/health/database
```

**Telegram webhook:**
```bash
curl https://your-domain.com/health/telegram-webhook
```

### Log Monitoring

**View logs:**
```bash
docker compose logs -f bot
```

**Log rotation:**
Configure logrotate for `logs/bot.log`:
```bash
/path/to/logs/bot.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

### Resource Monitoring

```bash
# Container stats
docker stats

# Disk usage
docker system df
```

## Updates and Maintenance

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
make reload

# Or manually:
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Database Migrations

Migrations run automatically on startup. To run manually:

```bash
docker compose exec bot alembic upgrade head
```

### Maintenance Mode

Enable via admin panel or API:
```bash
curl -X PUT https://your-domain.com/settings \
  -H "Authorization: Bearer <token>" \
  -d '{"maintenance_mode": true}'
```

## Security Best Practices

### 1. Firewall Configuration

```bash
# Allow only necessary ports
ufw allow 22/tcp    # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
ufw enable
```

### 2. SSL/TLS Certificates

Use Let's Encrypt or commercial certificates:
```bash
# Let's Encrypt with certbot
certbot --nginx -d your-domain.com
```

### 3. Environment Variables

- Never commit `.env` file
- Use strong, unique passwords
- Rotate secrets regularly
- Restrict file permissions: `chmod 600 .env`

### 4. Database Security

- Use strong PostgreSQL passwords
- Restrict database access (bind to localhost only)
- Enable SSL for remote connections
- Regular backups

### 5. API Security

- Use strong API tokens
- Enable rate limiting
- Monitor API usage
- Rotate tokens periodically

## Scaling

### Horizontal Scaling

For high-traffic scenarios:

1. **Load Balancer**: Use nginx/HAProxy in front of multiple bot instances
2. **Database**: Use PostgreSQL read replicas
3. **Redis**: Use Redis Cluster for high availability

### Vertical Scaling

Increase container resources:
```yaml
services:
  bot:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

## Troubleshooting

### Bot Not Responding

1. Check container status: `docker compose ps`
2. View logs: `docker compose logs bot`
3. Verify BOT_TOKEN is correct
4. Check webhook status: `curl https://your-domain.com/health/telegram-webhook`

### Database Connection Issues

1. Verify PostgreSQL is running: `docker compose ps postgres`
2. Check connection string in `.env`
3. Test connection: `docker compose exec postgres psql -U remnawave_user -d remnawave_bot`

### Webhook Not Working

1. Verify URL is publicly accessible
2. Check SSL certificate is valid
3. Verify WEBHOOK_SECRET_TOKEN matches
4. Check firewall rules

### High Memory Usage

1. Check container stats: `docker stats`
2. Review log levels (set to INFO in production)
3. Monitor Redis memory: `docker compose exec redis redis-cli INFO memory`
4. Consider increasing container memory limits

## Backup and Disaster Recovery

### Backup Strategy

1. **Database**: Daily automated backups
2. **Configuration**: Version control `.env` (without secrets)
3. **Logs**: Rotate and archive
4. **Data**: Backup `data/` directory

### Recovery Procedure

1. Restore database from backup
2. Restore configuration files
3. Restart services: `docker compose up -d`
4. Verify health: `curl https://your-domain.com/health`

## Support

- **Documentation**: Check `docs/` directory
- **Issues**: [GitHub Issues](https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot/issues)
- **Community**: [Telegram Chat](https://t.me/+wTdMtSWq8YdmZmVi)

