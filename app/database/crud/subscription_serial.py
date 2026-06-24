from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


async def allocate_subscription_public_serial(db: AsyncSession) -> str:
    result = await db.execute(text("SELECT nextval('subscription_public_serial_seq')::text"))
    value = result.scalar_one()
    serial = str(value).strip()
    if not serial.isdigit():
        raise RuntimeError(f'Invalid subscription public serial: {serial!r}')
    start = int(getattr(settings, 'SUBSCRIPTION_PUBLIC_SERIAL_START', 1000))
    if int(serial) < start:
        raise RuntimeError(f'Serial {serial} below configured start {start}')
    if len(serial) > 16:
        raise RuntimeError(f'Serial {serial} exceeds remnawave_short_id column limit')
    return serial
