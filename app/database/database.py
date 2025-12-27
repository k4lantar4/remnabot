import asyncio
import logging
from functools import wraps
from typing import AsyncGenerator, Callable, Optional, TypeVar
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, AsyncEngine
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy import event, text, bindparam, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, InterfaceError
import time
from app.config import settings
from app.database.models import Base

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ============================================================================
# PRODUCTION-GRADE CONNECTION POOLING
# ============================================================================


def _is_sqlite_url(url: str) -> bool:
    """Проверка на SQLite URL (поддерживает sqlite:// и sqlite+aiosqlite://)"""
    return url.startswith("sqlite") or ":memory:" in url


DATABASE_URL = settings.get_database_url()
IS_SQLITE = _is_sqlite_url(DATABASE_URL)

if IS_SQLITE:
    poolclass = NullPool
    pool_kwargs = {}
else:
    poolclass = AsyncAdaptedQueuePool
    pool_kwargs = {
        "pool_size": 20,
        "max_overflow": 30,
        "pool_timeout": 30,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        # Aggressive cleanup of dead connections
        "pool_reset_on_return": "rollback",
    }

# ============================================================================
# ENGINE WITH ADVANCED OPTIMIZATIONS
# ============================================================================

# PostgreSQL-специфичные connect_args
_pg_connect_args = {
    "server_settings": {
        "application_name": "remnawave_bot",
        "jit": "on",
        "statement_timeout": "60000",  # 60 секунд
        "idle_in_transaction_session_timeout": "300000",  # 5 минут
    },
    "command_timeout": 60,
    "timeout": 10,
}

engine = create_async_engine(
    DATABASE_URL,
    poolclass=poolclass,
    echo=settings.DEBUG,
    future=True,
    # Query cache for compiled queries (proper placement)
    query_cache_size=500,
    connect_args=_pg_connect_args if not IS_SQLITE else {},
    execution_options={
        "isolation_level": "READ COMMITTED",
    },
    **pool_kwargs,
)

# ============================================================================
# SESSION FACTORY WITH OPTIMIZATIONS
# ============================================================================

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # Critical for performance
    autocommit=False,
)

# ============================================================================
# RETRY LOGIC FOR DATABASE OPERATIONS
# ============================================================================

RETRYABLE_EXCEPTIONS = (OperationalError, InterfaceError, ConnectionRefusedError, OSError)
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 0.5  # секунды


def with_db_retry(
    attempts: int = DEFAULT_RETRY_ATTEMPTS,
    delay: float = DEFAULT_RETRY_DELAY,
    backoff: float = 2.0,
) -> Callable:
    """
    Декоратор для автоматического retry при сбоях подключения к БД.

    Args:
        attempts: Количество попыток
        delay: Начальная задержка между попытками (секунды)
        backoff: Множитель задержки для каждой следующей попытки
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    if attempt < attempts:
                        logger.warning(
                            "Ошибка БД (попытка %d/%d): %s. Повтор через %.1f сек...",
                            attempt,
                            attempts,
                            str(e)[:100],
                            current_delay,
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error("Ошибка БД: все %d попыток исчерпаны. Последняя ошибка: %s", attempts, str(e))

            raise last_exception

        return wrapper

    return decorator


async def execute_with_retry(
    session: AsyncSession,
    statement,
    attempts: int = DEFAULT_RETRY_ATTEMPTS,
):
    """Выполнение SQL с retry логикой."""
    last_exception = None
    delay = DEFAULT_RETRY_DELAY

    for attempt in range(1, attempts + 1):
        try:
            return await session.execute(statement)
        except RETRYABLE_EXCEPTIONS as e:
            last_exception = e
            if attempt < attempts:
                logger.warning("SQL retry (попытка %d/%d): %s", attempt, attempts, str(e)[:100])
                await asyncio.sleep(delay)
                delay *= 2

    raise last_exception


# ============================================================================
# QUERY PERFORMANCE MONITORING
# ============================================================================

if settings.DEBUG:

    @event.listens_for(Engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.time())
        logger.debug(f"🔍 Executing query: {statement[:100]}...")

    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.time() - conn.info["query_start_time"].pop(-1)
        if total > 0.1:  # Log slow queries > 100ms
            logger.warning(f"🐌 Slow query ({total:.3f}s): {statement[:100]}...")
        else:
            logger.debug(f"⚡ Query executed in {total:.3f}s")

# ============================================================================
# ADVANCED SESSION MANAGER WITH READ REPLICAS
# ============================================================================

HEALTH_CHECK_TIMEOUT = 5.0  # секунды


def _validate_database_url(url: Optional[str]) -> Optional[str]:
    """Валидация URL базы данных."""
    if not url:
        return None
    url = url.strip()
    if not url or url.isspace():
        return None
    # Простая проверка на валидный формат
    if not ("://" in url or url.startswith("sqlite")):
        logger.warning("Невалидный DATABASE_URL: %s", url[:20])
        return None
    return url


class DatabaseManager:
    """Advanced DB manager with replica and caching support"""

    def __init__(self):
        self.engine = engine
        self.read_replica_engine: Optional[AsyncEngine] = None
        self._read_replica_session_factory: Optional[async_sessionmaker] = None

        # Validation and creation of read replica engine
        replica_url = _validate_database_url(getattr(settings, "DATABASE_READ_REPLICA_URL", None))
        if replica_url:
            try:
                self.read_replica_engine = create_async_engine(
                    replica_url,
                    poolclass=poolclass,
                    pool_size=30,  # More for read operations
                    max_overflow=50,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False,
                )
                # Create sessionmaker once (not on every call)
                self._read_replica_session_factory = async_sessionmaker(
                    bind=self.read_replica_engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=False,
                )
                logger.info("Read replica configured: %s", replica_url[:30] + "...")
            except Exception as e:
                logger.error("Failed to configure read replica: %s", e)
                self.read_replica_engine = None

    @asynccontextmanager
    async def session(self, read_only: bool = False):
        """Контекстный менеджер для работы с сессией БД."""
        # Используем предсозданный sessionmaker вместо создания нового
        if read_only and self._read_replica_session_factory:
            session_factory = self._read_replica_session_factory
        else:
            session_factory = AsyncSessionLocal

        async with session_factory() as session:
            try:
                yield session
                if not read_only:
                    await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def health_check(self, timeout: float = HEALTH_CHECK_TIMEOUT) -> dict:
        """
        Проверка здоровья БД с таймаутом.

        Args:
            timeout: Максимальное время ожидания (секунды)
        """
        pool = self.engine.pool
        status = "unhealthy"
        latency = None

        try:
            async with asyncio.timeout(timeout):
                async with AsyncSessionLocal() as session:
                    start = time.time()
                    await session.execute(text("SELECT 1"))
                    latency = (time.time() - start) * 1000
            status = "healthy"
        except asyncio.TimeoutError:
            logger.error("Health check таймаут (%s сек)", timeout)
            status = "timeout"
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            status = "unhealthy"

        return {
            "status": status,
            "latency_ms": round(latency, 2) if latency else None,
            "pool": _collect_health_pool_metrics(pool),
        }

    async def health_check_replica(self, timeout: float = HEALTH_CHECK_TIMEOUT) -> Optional[dict]:
        """Проверка здоровья read replica."""
        if not self.read_replica_engine:
            return None

        pool = self.read_replica_engine.pool
        status = "unhealthy"
        latency = None

        try:
            async with asyncio.timeout(timeout):
                async with self._read_replica_session_factory() as session:
                    start = time.time()
                    await session.execute(text("SELECT 1"))
                    latency = (time.time() - start) * 1000
            status = "healthy"
        except asyncio.TimeoutError:
            status = "timeout"
        except Exception as e:
            logger.error("Read replica health check failed: %s", e)

        return {
            "status": status,
            "latency_ms": round(latency, 2) if latency else None,
            "pool": _collect_health_pool_metrics(pool),
        }


db_manager = DatabaseManager()

# ============================================================================
# SESSION DEPENDENCY FOR FASTAPI/AIOGRAM
# ============================================================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Standard dependency for FastAPI"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_read_only() -> AsyncGenerator[AsyncSession, None]:
    """Read-only dependency for heavy SELECT queries"""
    async with db_manager.session(read_only=True) as session:
        yield session


# ============================================================================
# BATCH OPERATIONS FOR PERFORMANCE
# ============================================================================


class BatchOperations:
    """Utilities for bulk operations"""

    @staticmethod
    async def bulk_insert(session: AsyncSession, model, data: list[dict], chunk_size: int = 1000):
        """Bulk insert with chunks"""
        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            session.add_all([model(**item) for item in chunk])
            await session.flush()
        await session.commit()

    @staticmethod
    async def bulk_update(session: AsyncSession, model, data: list[dict], chunk_size: int = 1000):
        """Bulk update with chunks"""
        if not data:
            return

        primary_keys = [column.name for column in model.__table__.primary_key.columns]
        if not primary_keys:
            raise ValueError("Model must have a primary key for bulk_update")

        updatable_columns = [column.name for column in model.__table__.columns if column.name not in primary_keys]

        if not updatable_columns:
            raise ValueError("No columns available for update in bulk_update")

        stmt = (
            model.__table__.update()
            .where(*[getattr(model.__table__.c, pk) == bindparam(pk) for pk in primary_keys])
            .values(**{column: bindparam(column, required=False) for column in updatable_columns})
        )

        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            filtered_chunk = []
            for item in chunk:
                missing_keys = [pk for pk in primary_keys if pk not in item]
                if missing_keys:
                    raise ValueError(f"Missing primary key values {missing_keys} for bulk_update")

                filtered_item = {
                    key: value for key, value in item.items() if key in primary_keys or key in updatable_columns
                }
                filtered_chunk.append(filtered_item)

            await session.execute(stmt, filtered_chunk)
        await session.commit()


batch_ops = BatchOperations()

# ============================================================================
# INITIALIZATION AND CLEANUP
# ============================================================================


async def init_db():
    """DB initialization with optimizations"""
    logger.info("🚀 Creating database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if not IS_SQLITE:
        logger.info("📊 Creating indexes for optimization...")

        async with engine.begin() as conn:
            indexes = [
                ("users", "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)"),
                (
                    "subscriptions",
                    "CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)",
                ),
                (
                    "subscriptions",
                    "CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status) WHERE status = 'active'",
                ),
                (
                    "payments",
                    "CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at DESC)",
                ),
            ]

            for table_name, index_sql in indexes:
                table_exists = await conn.run_sync(lambda sync_conn: inspect(sync_conn).has_table(table_name))

                if not table_exists:
                    logger.debug(
                        "Skipping index creation %s: table %s does not exist",
                        index_sql,
                        table_name,
                    )
                    continue

                try:
                    await conn.execute(text(index_sql))
                except Exception as e:
                    logger.debug("Index creation skipped for %s: %s", table_name, e)

    logger.info("✅ Database successfully initialized")

    health = await db_manager.health_check()
    logger.info("Database health: %s", health)


async def close_db():
    """Proper closure of all connections"""
    logger.info("🔄 Closing database connections...")

    await engine.dispose()

    if db_manager.read_replica_engine:
        await db_manager.read_replica_engine.dispose()

    logger.info("✅ All database connections closed")


# ============================================================================
# CONNECTION POOL METRICS (for monitoring)
# ============================================================================


def _pool_counters(pool):
    """Return basic pool counters or ``None`` when unsupported."""

    required_methods = ("size", "checkedin", "checkedout", "overflow")

    for method_name in required_methods:
        method = getattr(pool, method_name, None)
        if method is None or not callable(method):
            return None

    size = pool.size()
    checked_in = pool.checkedin()
    checked_out = pool.checkedout()
    overflow = pool.overflow()

    total_connections = size + overflow

    return {
        "size": size,
        "checked_in": checked_in,
        "checked_out": checked_out,
        "overflow": overflow,
        "total_connections": total_connections,
        "utilization_percent": (checked_out / total_connections * 100) if total_connections else 0.0,
    }


def _collect_health_pool_metrics(pool) -> dict:
    counters = _pool_counters(pool)

    if counters is None:
        return {
            "metrics_available": False,
            "size": 0,
            "checked_in": 0,
            "checked_out": 0,
            "overflow": 0,
            "total_connections": 0,
            "utilization": "0.0%",
        }

    return {
        "metrics_available": True,
        "size": counters["size"],
        "checked_in": counters["checked_in"],
        "checked_out": counters["checked_out"],
        "overflow": counters["overflow"],
        "total_connections": counters["total_connections"],
        "utilization": f"{counters['utilization_percent']:.1f}%",
    }


async def get_pool_metrics() -> dict:
    """Detailed pool metrics for Prometheus/Grafana"""
    pool = engine.pool

    counters = _pool_counters(pool)

    if counters is None:
        return {
            "metrics_available": False,
            "pool_size": 0,
            "checked_in_connections": 0,
            "checked_out_connections": 0,
            "overflow_connections": 0,
            "total_connections": 0,
            "max_possible_connections": 0,
            "pool_utilization_percent": 0.0,
        }

    return {
        "metrics_available": True,
        "pool_size": counters["size"],
        "checked_in_connections": counters["checked_in"],
        "checked_out_connections": counters["checked_out"],
        "overflow_connections": counters["overflow"],
        "total_connections": counters["total_connections"],
        "max_possible_connections": counters["total_connections"] + (getattr(pool, "_max_overflow", 0) or 0),
        "pool_utilization_percent": round(counters["utilization_percent"], 2),
    }
