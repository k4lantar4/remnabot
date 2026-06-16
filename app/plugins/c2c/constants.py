"""C2C plugin constants."""

from app.database.models import C2cReceiptStatus


C2C_CALLBACK_APPROVE_PREFIX = 'c2c:a:'
C2C_CALLBACK_REJECT_PREFIX = 'c2c:r:'
C2C_CARD_ROTATION_REDIS_KEY = 'c2c:card_rotation_index'

C2C_RECEIPT_STATUS_PENDING = C2cReceiptStatus.PENDING.value
C2C_RECEIPT_STATUS_APPROVED = C2cReceiptStatus.APPROVED.value
C2C_RECEIPT_STATUS_REJECTED = C2cReceiptStatus.REJECTED.value

C2C_RECEIPT_TYPE_PHOTO = 'photo'
C2C_RECEIPT_TYPE_DOCUMENT = 'document'
C2C_RECEIPT_TYPE_TEXT = 'text'
