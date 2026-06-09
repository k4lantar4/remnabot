from app.config import settings


def effective_autopay_enabled(subscription) -> bool:
    if not settings.ENABLE_AUTOPAY:
        return False
    return bool(getattr(subscription, 'autopay_enabled', False))
