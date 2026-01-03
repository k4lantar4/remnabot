"""High level integration with WATA API."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)


class WataAPIError(Exception):
    """Base error for WATA API operations."""


class WataService:
    """Wrapper around WATA API providing domain helpers."""

    def __init__(
        self,
        *,
        access_token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.access_token = access_token or settings.WATA_ACCESS_TOKEN
        self.base_url = (base_url or settings.WATA_BASE_URL or "").rstrip("/")
        self.timeout = timeout or settings.WATA_REQUEST_TIMEOUT

        if not self.access_token:
            logger.warning("WataService initialized without access token")

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token) and bool(self.base_url) and settings.is_wata_enabled()

    async def create_payment_link(
        self,
        *,
        amount_toman: int,
        order_id: str,
        description: Optional[str] = None,
        success_redirect_url: Optional[str] = None,
        fail_redirect_url: Optional[str] = None,
        expiration_datetime: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Creates a payment link in WATA."""
        if not self.is_configured:
            logger.error("WataService is not configured")
            return None

        amount_rubles = amount_toman / 100.0

        payload: Dict[str, Any] = {
            "amount": amount_rubles,
            "orderId": order_id,
            "terminalPublicId": settings.WATA_TERMINAL_PUBLIC_ID,
            "type": settings.WATA_PAYMENT_TYPE,
        }

        if description:
            payload["description"] = description
        elif settings.WATA_PAYMENT_DESCRIPTION:
            payload["description"] = settings.WATA_PAYMENT_DESCRIPTION

        if success_redirect_url:
            payload["successRedirectUrl"] = success_redirect_url
        elif settings.WATA_SUCCESS_REDIRECT_URL:
            payload["successRedirectUrl"] = settings.WATA_SUCCESS_REDIRECT_URL

        if fail_redirect_url:
            payload["failRedirectUrl"] = fail_redirect_url
        elif settings.WATA_FAIL_REDIRECT_URL:
            payload["failRedirectUrl"] = settings.WATA_FAIL_REDIRECT_URL

        if expiration_datetime:
            payload["expirationDateTime"] = self._format_datetime(expiration_datetime)
        elif settings.WATA_LINK_TTL_MINUTES:
            expiration = datetime.utcnow() + timedelta(minutes=settings.WATA_LINK_TTL_MINUTES)
            payload["expirationDateTime"] = self._format_datetime(expiration)

        url = f"{self.base_url}/payment-links"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    status = response.status
                    try:
                        result = await response.json()
                    except aiohttp.ContentTypeError:
                        text_body = await response.text()
                        logger.error(
                            "WATA API returned non-JSON response for %s: %s",
                            url,
                            text_body[:500],
                        )
                        return None

                    if status >= 400:
                        logger.error(
                            "WATA API error at %s: status=%s, response=%s",
                            url,
                            status,
                            result,
                        )
                        return None

                    logger.info("WATA payment link created: %s", result.get("id"))
                    return result

        except aiohttp.ClientError as error:
            logger.error("WATA API request failed: %s", error)
            return None
        except Exception as error:
            logger.error("Unexpected error calling WATA API: %s", error, exc_info=True)
            return None

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        """Formats datetime as ISO 8601 string in UTC (Z suffix)."""
        if value.tzinfo is not None:
            # Convert to UTC
            from datetime import timezone

            utc_dt = value.astimezone(timezone.utc)
            # Make naive (remove timezone info)
            value = utc_dt.replace(tzinfo=None)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        """Parses ISO 8601 datetime string and returns naive UTC datetime."""
        try:
            if value.endswith("Z"):
                dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            elif "+" in value:
                # Handle timezone offset like +03:00
                dt_str, offset_str = value.rsplit("+", 1)
                if ":" in offset_str:
                    hours, minutes = offset_str.split(":")
                    offset_seconds = int(hours) * 3600 + int(minutes) * 60
                    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
                    dt = dt - timedelta(seconds=offset_seconds)
                else:
                    dt = datetime.strptime(value.split("+")[0], "%Y-%m-%dT%H:%M:%S")
            elif "-" in value and len(value.split("-")) > 3:
                # Handle negative timezone offset like -05:00
                parts = value.rsplit("-", 1)
                if len(parts) == 2 and ":" in parts[1]:
                    dt_str = parts[0]
                    offset_str = parts[1]
                    hours, minutes = offset_str.split(":")
                    offset_seconds = int(hours) * 3600 + int(minutes) * 60
                    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
                    dt = dt + timedelta(seconds=offset_seconds)
                else:
                    dt = datetime.strptime(value.split("+")[0] if "+" in value else value, "%Y-%m-%dT%H:%M:%S")
            else:
                dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            return dt
        except Exception as error:
            logger.error("Failed to parse WATA datetime %s: %s", value, error)
            raise ValueError(f"Invalid datetime format: {value}") from error
