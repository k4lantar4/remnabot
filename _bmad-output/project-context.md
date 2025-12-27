---
project_name: 'dev5-from-upstream'
user_name: 'K4lantar4'
date: '2025-12-25'
sections_completed: ['technology_stack', 'implementation_rules', 'anti_patterns', 'error_handling']
existing_patterns_found: 18
---

# Project Context for AI Agents

_Critical rules and patterns for implementing code in remnabot multi-tenant transformation. Focus on unobvious details that agents might miss._

---

## Technology Stack & Versions

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.13+ | Language |
| aiogram | 3.22.0 | Telegram Bot |
| FastAPI | 0.115.6 | REST API |
| SQLAlchemy | 2.0.43 | ORM |
| PostgreSQL | 15+ | Database (with RLS) |
| asyncpg | 0.30.0 | Async PostgreSQL |
| Redis | 5.0.1 | Cache |
| Pydantic | 2.11.9 | Validation |
| Alembic | 1.16.5 | Migrations |
| structlog | 23.2.0 | Logging |

---

## Critical Implementation Rules

### Multi-Tenancy Rules (CRITICAL)

- ✅ **ALWAYS** use `get_current_tenant()` to access tenant context
- ✅ **ALWAYS** include `bot_id` in database queries
- ✅ **ALWAYS** use `get_tenant_session()` for database operations
- ✅ **NEVER** query database without tenant context set
- ✅ **ALWAYS** prefix Redis keys with `tenant:{id}:`

```python
# ✅ CORRECT
bot_id = get_current_tenant()
async with get_tenant_session(bot_id) as session:
    users = await session.execute(select(User))

# ❌ WRONG - No tenant context
users = await session.execute(select(User))
```

### Database & ORM Rules

- Use `snake_case` for all table and column names
- Tables are plural: `users`, `subscriptions`, `payments`
- Foreign keys format: `{table}_id` (e.g., `bot_id`, `user_id`)
- Index naming: `idx_{table}_{columns}`
- All tenant tables MUST have RLS policies enabled
- Tenant identifier type: Integer (auto-increment)

### API Rules

- Endpoints use `snake_case` and plural: `/api/v1/users`
- All responses use wrapper format:
  ```json
  {"success": true, "data": {...}}
  {"success": false, "error": {"code": "...", "message": "..."}}
  ```
- Webhook routing: `/webhook/{bot_token}`
- JWT tokens MUST include `bot_id` claim

### Python Code Style

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `user_service.py` |
| Classes | PascalCase | `UserService` |
| Functions | snake_case | `get_user_by_id()` |
| Variables | snake_case | `user_id` |
| Constants | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| Private | _prefix | `_validate_input()` |

### Localization Rules

- **NEVER** hardcode user-facing text
- **ALWAYS** use `Texts.get("key")` for user messages
- Persian is primary language, English is fallback
- Localization keys in `snake_case`

### Logging Rules

- Use `structlog` for all logging
- **ALWAYS** include `bot_id` in log context
- Log format: structured JSON

```python
logger.info(
    "payment_processed",
    bot_id=get_current_tenant(),
    user_id=user.id,
    amount=amount,
    payment_method="zarinpal"
)
```

### Testing Rules

- Test files mirror source structure: `tests/services/test_*.py`
- Use `pytest-asyncio` for async tests
- Create tenant fixtures for isolation testing
- Verify tenant isolation in all tests

---

## Anti-Patterns to Avoid

| ❌ Don't | ✅ Do |
|---------|------|
| `userId`, `getUserData` | `user_id`, `get_user_data` |
| `/api/v1/User` | `/api/v1/users` |
| Direct DB queries | Use `get_tenant_session()` |
| Hardcoded messages | Use `Texts.get("key")` |
| `print()` | Use `logger.info()` |
| Russian comments | English comments only |
| kopeks currency | Tomans only |
| MiniApp for payments | Inline Keyboard only |

---

## Payment Integration Rules

| Gateway | Status | Usage |
|---------|--------|-------|
| ZarinPal | ✅ Use | Automated Iranian payments |
| Card-to-Card | ✅ Use | Manual approval via Telegram channel |
| CryptoBot | ✅ Use | International payments |
| YooKassa | ❌ Remove | Russian gateway |
| Heleket | ❌ Remove | Russian gateway |
| Tribute | ❌ Remove | Russian gateway |
| MulenPay | ❌ Remove | Russian gateway |
| Pal24 | ❌ Remove | Russian gateway |
| Platega | ❌ Remove | Russian gateway |
| WATA | ❌ Remove | Russian gateway |

---

## Error Handling Pattern

```python
# User-facing errors (localized)
class UserError(Exception):
    def __init__(self, code: str, message_key: str, details: dict = None):
        self.code = code
        self.message_key = message_key  # Localization key
        self.details = details or {}

# Internal errors (English, logged)
class InternalError(Exception):
    def __init__(self, message: str, context: dict = None):
        self.message = message
        self.context = context or {}
```

---

## Tenant Context Pattern

```python
from contextvars import ContextVar
from typing import Optional

current_tenant: ContextVar[Optional[int]] = ContextVar('current_tenant', default=None)

def get_current_tenant() -> int:
    """Get tenant from context - raises if not set"""
    bot_id = current_tenant.get()
    if bot_id is None:
        raise RuntimeError("No tenant in context")
    return bot_id

async def get_tenant_session(bot_id: int) -> AsyncSession:
    """Create session with RLS context"""
    session = async_session_maker()
    await session.execute(
        text("SET app.current_tenant = :bot_id"),
        {"bot_id": bot_id}
    )
    return session
```

---

## File Organization

```
app/
├── core/           # Tenant context (base layer, no dependencies)
├── database/       # Models, CRUD (depends on core/)
├── services/       # Business logic (depends on database/, core/)
├── handlers/       # Bot handlers (depends on services/)
├── webapi/         # REST API (depends on services/)
└── external/       # Third-party integrations
```

**Dependency Flow:** `core/ → database/ → services/ → handlers/webapi/`

---

## UX Rules (Telegram Bot)

- **NO MiniApp** for payment flows (trust issues in Iran)
- Inline Keyboard only for critical actions
- Maximum 3 clicks for any operation
- Persian UI with English fallback
- Reply Keyboard for navigation, Inline for actions

---

## Architecture Reference

Full architectural decisions documented in: `_bmad-output/architecture.md`

---

_Generated 2025-12-25 by BMAD Generate Project Context Workflow_

