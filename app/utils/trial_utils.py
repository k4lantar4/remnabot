from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


async def is_trial_globally_available(db: AsyncSession) -> bool:
    if settings.TRIAL_DURATION_DAYS <= 0:
        return False

    if not settings.is_tariffs_mode():
        return True

    from app.database.crud.tariff import get_tariff_by_id, get_trial_tariff

    trial_tariff = await get_trial_tariff(db)
    if trial_tariff:
        return True

    trial_tariff_id = settings.get_trial_tariff_id()
    if trial_tariff_id > 0:
        tariff = await get_tariff_by_id(db, trial_tariff_id)
        return tariff is not None

    return False
