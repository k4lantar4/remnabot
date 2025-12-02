from datetime import datetime, timedelta
from typing import Union, Optional


def format_datetime(dt: Union[datetime, str], format_str: str = "%d.%m.%Y %H:%M") -> str:
    if isinstance(dt, str):
        if dt == "now" or dt == "":
            dt = datetime.now()
        else:
            try:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                dt = datetime.now()
    
    return dt.strftime(format_str)


def format_date(dt: Union[datetime, str], format_str: str = "%d.%m.%Y") -> str:
    if isinstance(dt, str):
        if dt == "now" or dt == "":
            dt = datetime.now()
        else:
            try:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                dt = datetime.now()
    
    return dt.strftime(format_str)


def format_time_ago(dt: Union[datetime, str], language: str = "en") -> str:
    if isinstance(dt, str):
        if dt == "now" or dt == "":
            dt = datetime.now()
        else:
            try:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                dt = datetime.now()
    
    now = datetime.utcnow()
    diff = now - dt

    language_code = (language or "en").split("-")[0].lower()

    if diff.days > 0:
        if diff.days == 1:
            return "вчера" if language_code == "ru" else "yesterday"
        if diff.days < 7:
            value = diff.days
            if language_code == "ru":
                return f"{value} дн. назад"
            suffix = "day" if value == 1 else "days"
            return f"{value} {suffix} ago"
        if diff.days < 30:
            value = diff.days // 7
            if language_code == "ru":
                return f"{value} нед. назад"
            suffix = "week" if value == 1 else "weeks"
            return f"{value} {suffix} ago"
        if diff.days < 365:
            value = diff.days // 30
            if language_code == "ru":
                return f"{value} мес. назад"
            suffix = "month" if value == 1 else "months"
            return f"{value} {suffix} ago"
        value = diff.days // 365
        if language_code == "ru":
            return f"{value} г. назад"
        suffix = "year" if value == 1 else "years"
        return f"{value} {suffix} ago"

    if diff.seconds > 3600:
        value = diff.seconds // 3600
        if language_code == "ru":
            return f"{value} ч. назад"
        suffix = "hour" if value == 1 else "hours"
        return f"{value} {suffix} ago"

    if diff.seconds > 60:
        value = diff.seconds // 60
        if language_code == "ru":
            return f"{value} мин. назад"
        suffix = "minute" if value == 1 else "minutes"
        return f"{value} {suffix} ago"

    return "только что" if language_code == "ru" else "just now"

def format_days_declension(days: int, language: str = "en") -> str:
    if language == "ru":
        if days % 10 == 1 and days % 100 != 11:
            return f"{days} день"
        elif days % 10 in [2, 3, 4] and days % 100 not in [12, 13, 14]:
            return f"{days} дня"
        else:
            return f"{days} дней"
    
    return f"{days} day{'s' if days != 1 else ''}"


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} sec"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr"
    
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''}"


def format_bytes(bytes_value: int) -> str:
    if bytes_value == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(bytes_value)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if size == int(size):
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def format_percentage(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def format_number(number: Union[int, float], separator: str = " ") -> str:
    if isinstance(number, float):
        integer_part = int(number)
        decimal_part = number - integer_part
        
        formatted_integer = f"{integer_part:,}".replace(",", separator)
        
        if decimal_part > 0:
            return f"{formatted_integer}.{decimal_part:.2f}".split('.')[0] + f".{str(decimal_part).split('.')[1][:2]}"
        else:
            return formatted_integer
    else:
        return f"{number:,}".replace(",", separator)


def format_price_range(min_price: int, max_price: int) -> str:
    from app.config import settings
    
    min_formatted = settings.format_price(min_price)
    max_formatted = settings.format_price(max_price)
    
    if min_price == max_price:
        return min_formatted
    else:
        return f"{min_formatted} - {max_formatted}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_username(username: Optional[str], user_id: int, full_name: Optional[str] = None) -> str:
    if full_name:
        return full_name
    elif username:
        return f"@{username}"
    else:
        return f"ID{user_id}"


def format_subscription_status(
    is_active: bool,
    is_trial: bool,
    end_date: Union[datetime, str],
    language: str = None
) -> str:
    from app.localization.loader import DEFAULT_LANGUAGE
    from app.localization.texts import get_texts
    
    if language is None:
        language = DEFAULT_LANGUAGE
    texts = get_texts(language)
    
    if isinstance(end_date, str):
        try:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            end_date = datetime.now()
    
    if not is_active:
        return texts.t("SUBSCRIPTION_STATUS_INACTIVE", "❌ Inactive")
    
    if is_trial:
        status = texts.t("SUBSCRIPTION_STATUS_TRIAL", "🎁 Trial")
    else:
        status = texts.t("SUBSCRIPTION_STATUS_ACTIVE", "✅ Active")
    
    now = datetime.utcnow()
    if end_date > now:
        days_left = (end_date - now).days
        if days_left > 0:
            days_text = texts.t("DAYS_LEFT", "{days} days").format(days=days_left)
            status += f" ({days_text})"
        else:
            hours_left = (end_date - now).seconds // 3600
            hours_text = texts.t("HOURS_LEFT", "{hours} hrs").format(hours=hours_left)
            status += f" ({hours_text})"
    else:
        status = texts.t("SUBSCRIPTION_STATUS_EXPIRED", "⏰ Expired")
    
    return status


def format_traffic_usage(used_gb: float, limit_gb: int, language: str = None) -> str:
    from app.localization.loader import DEFAULT_LANGUAGE
    from app.localization.texts import get_texts
    
    if language is None:
        language = DEFAULT_LANGUAGE
    texts = get_texts(language)
    
    if limit_gb == 0: 
        return texts.t("TRAFFIC_USAGE_UNLIMITED", "{used} GB / ∞").format(used=f"{used_gb:.1f}")
    
    percentage = (used_gb / limit_gb) * 100 if limit_gb > 0 else 0
    return texts.t("TRAFFIC_USAGE_FORMAT", "{used} GB / {limit} GB ({percent}%)").format(
        used=f"{used_gb:.1f}",
        limit=limit_gb,
        percent=f"{percentage:.1f}"
    )


def format_boolean(value: bool, language: str = None) -> str:
    from app.localization.loader import DEFAULT_LANGUAGE
    from app.localization.texts import get_texts
    
    if language is None:
        language = DEFAULT_LANGUAGE
    texts = get_texts(language)
    
    if value:
        return texts.t("BOOLEAN_YES", "✅ Yes")
    else:
        return texts.t("BOOLEAN_NO", "❌ No")
