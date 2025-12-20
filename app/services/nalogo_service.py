import logging
from typing import Optional, Dict, Any
from decimal import Decimal

from nalogo import Client
from nalogo.dto.income import IncomeClient, IncomeType

from app.config import settings

logger = logging.getLogger(__name__)


class NaloGoService:
    """Сервис для работы с API NaloGO (налоговая служба самозанятых)."""

    def __init__(self,
                 inn: Optional[str] = None,
                 password: Optional[str] = None,
                 device_id: Optional[str] = None,
                 storage_path: Optional[str] = None):

        inn = inn or getattr(settings, 'NALOGO_INN', None)
        password = password or getattr(settings, 'NALOGO_PASSWORD', None)
        device_id = device_id or getattr(settings, 'NALOGO_DEVICE_ID', None)
        storage_path = storage_path or getattr(settings, 'NALOGO_STORAGE_PATH', './nalogo_tokens.json')

        self.configured = False

        if not inn or not password:
            logger.warning(
                "NaloGO INN or PASSWORD not configured in settings. "
                "Receipt functionality will be DISABLED.")
        else:
            try:
                self.client = Client(
                    base_url="https://lknpd.nalog.ru/api",
                    storage_path=storage_path,
                    device_id=device_id or "bot-device-123"
                )
                self.inn = inn
                self.password = password
                self.configured = True
                logger.info(f"NaloGO client initialized for INN: {inn[:5]}...")
            except Exception as error:
                logger.error(
                    "Error initializing NaloGO client: %s",
                    error,
                    exc_info=True,
                )
                self.configured = False

    async def authenticate(self) -> bool:
        """Аутентификация в сервисе NaloGO."""
        if not self.configured:
            return False

        try:
            token = await self.client.create_new_access_token(self.inn, self.password)
            await self.client.authenticate(token)
            logger.info("Успешная аутентификация в NaloGO")
            return True
        except Exception as error:
            logger.error("Ошибка аутентификации в NaloGO: %s", error, exc_info=True)
            return False

    async def create_receipt(self, name: str, amount: float, quantity: int = 1, client_info: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Create income receipt.

        Args:
            name: Service name
            amount: Amount in Toman
            quantity: Quantity
            client_info: Client information (optional)

        Returns:
            Receipt UUID or None on error
        """
        if not self.configured:
            logger.warning("NaloGO not configured, receipt not created")
            return None

        try:
            # Authenticate if needed
            if not hasattr(self.client, '_access_token') or not self.client._access_token:
                auth_success = await self.authenticate()
                if not auth_success:
                    return None

            income_api = self.client.income()

            # Create client if information provided
            income_client = None
            if client_info:
                income_client = IncomeClient(
                    contact_phone=client_info.get("phone"),
                    display_name=client_info.get("name"),
                    income_type=client_info.get("income_type", IncomeType.FROM_INDIVIDUAL),
                    inn=client_info.get("inn")
                )

            result = await income_api.create(
                name=name,
                amount=Decimal(str(amount)),
                quantity=quantity,
                client=income_client
            )

            receipt_uuid = result.get("approvedReceiptUuid")
            if receipt_uuid:
                logger.info(f"Receipt created successfully: {receipt_uuid} for amount {amount} Toman")
                return receipt_uuid
            else:
                logger.error(f"Error creating receipt: {result}")
                return None

        except Exception as error:
            logger.error("Error creating receipt in NaloGO: %s", error, exc_info=True)
            return None
