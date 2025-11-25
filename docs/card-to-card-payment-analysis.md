# Card-to-Card Payment Analysis

**Author:** Architecture Team  
**Date:** 2025-11-21  
**Version:** 1.0

---

## Overview

This document analyzes the requirements and implementation approach for adding Card-to-Card (C2C) payment method with tenant-specific customization (card numbers and display texts).

---

## Current Payment System Architecture

### Existing Payment Providers

The system currently supports 9 payment providers:
1. **Telegram Stars** - Native Telegram payment
2. **YooKassa** - Bank cards + SBP
3. **Tribute** - Payment gateway
4. **CryptoBot** - Cryptocurrency
5. **Heleket** - Cryptocurrency
6. **MulenPay** - SBP
7. **Pal24/PayPalych** - SBP + cards
8. **Platega** - SBP + cards
9. **WATA** - Payment gateway

### Payment Architecture Pattern

**Mixin Pattern:**
- Each payment provider has a Mixin class in `app/services/payment/`
- Mixins are combined in `PaymentService` class
- Common functionality in `PaymentCommonMixin`

**Handler Pattern:**
- Payment handlers in `app/handlers/balance/`
- Each provider has its own handler file (e.g., `yookassa.py`, `cryptobot.py`)
- Handlers manage FSM states for payment flow

**Database Pattern:**
- Each provider has its own payment table (e.g., `yookassa_payments`, `cryptobot_payments`)
- All payments also create `Transaction` records
- Payment tables track provider-specific data

---

## Card-to-Card Payment Requirements

### Functional Requirements

1. **Display Card Number**
   - Show tenant-specific card number to user
   - Display payment instructions with customizable text
   - Show amount and payment reference

2. **Receive Receipt**
   - User uploads receipt (photo or document)
   - Store receipt in payment record
   - Validate receipt format (optional)

3. **Send to Channel/Group**
   - Forward receipt to configured Telegram channel/group
   - Include payment details (user, amount, reference)
   - Support topic/thread for organization

4. **Approve/Reject Receipt**
   - Admin reviews receipt in channel
   - Approve → Credit user balance
   - Reject → Notify user, allow resubmission
   - Buttons in channel message for quick action

5. **Tenant Customization**
   - Each tenant can configure:
     - Card number(s)
     - Display texts (instructions, messages)
     - Channel/group ID for receipts
     - Topic/thread ID (optional)

---

## Implementation Analysis

### ✅ Compatibility Assessment

**GOOD NEWS - Highly Compatible:**

1. **Payment Mixin Pattern**: ✅ Perfect fit
   - Can create `CardToCardPaymentMixin` following existing pattern
   - Integrates seamlessly with `PaymentService`

2. **FSM State Management**: ✅ Already exists
   - System uses FSM for multi-step flows
   - Can add states: `waiting_for_receipt`, `receipt_received`, etc.

3. **Channel/Group Messaging**: ✅ Infrastructure exists
   - `AdminNotificationService` sends messages to channels
   - Supports topics/threads
   - Can be extended for receipt forwarding

4. **Database Models**: ✅ Pattern established
   - Can create `card_to_card_payments` table
   - Follows same structure as other payment tables

5. **Transaction System**: ✅ Ready
   - `Transaction` model supports any payment method
   - Balance update logic already exists

6. **Tenant Settings**: ✅ JSONB ready
   - `tenant.settings` JSONB field can store card numbers and texts
   - No schema changes needed for customization

---

## Required Changes

### 1. Database Changes

#### New Table: `card_to_card_payments`

```sql
CREATE TABLE card_to_card_payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    amount_kopeks INTEGER NOT NULL,
    reference_code VARCHAR(50) UNIQUE NOT NULL, -- Payment reference
    card_number VARCHAR(50), -- Tenant's card number used
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, receipt_received, approved, rejected, expired
    receipt_file_id VARCHAR(255), -- Telegram file_id of receipt
    receipt_message_id INTEGER, -- Message ID in channel/group
    receipt_chat_id BIGINT, -- Channel/group ID where receipt was sent
    admin_reviewer_id INTEGER REFERENCES users(id), -- Admin who approved/rejected
    rejection_reason TEXT, -- If rejected
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL, -- Payment expires if not completed
    approved_at TIMESTAMP,
    rejected_at TIMESTAMP
);

CREATE INDEX idx_card_to_card_payments_user_id ON card_to_card_payments(user_id);
CREATE INDEX idx_card_to_card_payments_tenant_id ON card_to_card_payments(tenant_id);
CREATE INDEX idx_card_to_card_payments_status ON card_to_card_payments(status);
CREATE INDEX idx_card_to_card_payments_reference ON card_to_card_payments(reference_code);
CREATE INDEX idx_card_to_card_payments_receipt_message ON card_to_card_payments(receipt_chat_id, receipt_message_id);
```

**Migration**: Add `tenant_id` column (already planned for multi-tenancy)

---

### 2. Tenant Settings Schema Extension

Add to `tenant.settings` JSONB:

```json
{
  "card_to_card": {
    "enabled": true,
    "card_numbers": [
      {
        "number": "1234 5678 9012 3456",
        "bank_name": "Bank Name",
        "cardholder": "Cardholder Name"
      }
    ],
    "display_texts": {
      "instructions": "لطفاً مبلغ {amount} را به شماره کارت {card_number} واریز کنید",
      "reference_label": "کد پیگیری",
      "receipt_prompt": "لطفاً تصویر رسید پرداخت را ارسال کنید",
      "pending_message": "در انتظار تایید رسید...",
      "approved_message": "پرداخت شما تایید شد! موجودی شما افزایش یافت.",
      "rejected_message": "رسید شما رد شد. لطفاً دوباره تلاش کنید."
    },
    "channel": {
      "chat_id": -1001234567890,
      "topic_id": 123,  // Optional, for forum groups
      "notification_text": "رسید جدید دریافت شد:\nکاربر: {user_name}\nمبلغ: {amount}\nکد پیگیری: {reference}"
    },
    "settings": {
      "expiration_hours": 24,
      "auto_approve_enabled": false,
      "min_amount_kopeks": 10000,
      "max_amount_kopeks": 10000000
    }
  }
}
```

---

### 3. Code Changes

#### 3.1 Payment Mixin

**File**: `app/services/payment/card_to_card.py`

```python
class CardToCardPaymentMixin:
    """Mixin for Card-to-Card payment processing."""
    
    async def create_card_to_card_payment(
        self,
        db: AsyncSession,
        user_id: int,
        amount_kopeks: int,
        tenant_id: int,
        description: str,
    ) -> Dict[str, Any]:
        """Create a new card-to-card payment request."""
        # Generate unique reference code
        # Get tenant card number and settings
        # Create payment record
        # Return payment details
        pass
    
    async def process_receipt_upload(
        self,
        db: AsyncSession,
        payment_id: int,
        file_id: str,
        user_id: int,
    ) -> bool:
        """Process uploaded receipt."""
        # Save receipt to payment record
        # Forward to channel/group
        # Update status to receipt_received
        pass
    
    async def approve_payment(
        self,
        db: AsyncSession,
        payment_id: int,
        admin_id: int,
    ) -> bool:
        """Approve payment and credit user balance."""
        # Update payment status
        # Credit user balance
        # Create transaction record
        # Notify user
        pass
    
    async def reject_payment(
        self,
        db: AsyncSession,
        payment_id: int,
        admin_id: int,
        reason: str,
    ) -> bool:
        """Reject payment and notify user."""
        # Update payment status
        # Notify user with reason
        # Allow resubmission
        pass
```

**Estimated LOC**: ~300-400 lines

---

#### 3.2 Payment Handlers

**File**: `app/handlers/balance/card_to_card.py`

**Handlers Needed:**
1. `start_card_to_card_payment` - Initiate payment, show card number
2. `handle_card_to_card_amount` - Process amount input
3. `handle_receipt_upload` - Receive receipt photo/document
4. `handle_receipt_confirmation` - Confirm receipt before sending
5. `handle_payment_cancel` - Cancel payment flow

**FSM States:**
- `CardToCardStates.waiting_for_amount`
- `CardToCardStates.waiting_for_receipt`
- `CardToCardStates.receipt_confirmed`

**Estimated LOC**: ~400-500 lines

---

#### 3.3 Channel Receipt Handler

**File**: `app/handlers/admin/card_to_card_receipts.py`

**Handlers Needed:**
1. `handle_receipt_approve` - Approve from channel button
2. `handle_receipt_reject` - Reject from channel button
3. `handle_receipt_view` - View payment details
4. `handle_receipt_forward` - Manual forward (if needed)

**Estimated LOC**: ~200-300 lines

---

#### 3.4 Service Integration

**File**: `app/services/card_to_card_service.py`

**Service Methods:**
- `get_tenant_card_config(tenant_id)` - Get tenant card settings
- `generate_reference_code()` - Generate unique reference
- `forward_receipt_to_channel()` - Send receipt to channel
- `validate_receipt()` - Basic validation (optional)
- `expire_old_payments()` - Background task

**Estimated LOC**: ~200-300 lines

---

#### 3.5 CRUD Operations

**File**: `app/database/crud/card_to_card.py`

**Functions:**
- `create_card_to_card_payment()`
- `get_card_to_card_payment_by_id()`
- `get_card_to_card_payment_by_reference()`
- `get_pending_payments_by_tenant()`
- `update_payment_status()`
- `get_user_payments()`

**Estimated LOC**: ~150-200 lines

---

#### 3.6 Model Updates

**File**: `app/database/models.py`

Add `CardToCardPayment` model class.

**Estimated LOC**: ~50-80 lines

---

#### 3.7 Configuration Updates

**File**: `app/config.py`

Add settings:
- `CARD_TO_CARD_ENABLED: bool = False`
- `CARD_TO_CARD_DEFAULT_EXPIRATION_HOURS: int = 24`
- `CARD_TO_CARD_MIN_AMOUNT_KOPEKS: int = 10000`
- `CARD_TO_CARD_MAX_AMOUNT_KOPEKS: int = 10000000`

**Estimated LOC**: ~20-30 lines

---

#### 3.8 Integration Points

**Update Existing Files:**

1. **`app/services/payment_service.py`**:
   - Add `CardToCardPaymentMixin` to PaymentService
   - Add `create_card_to_card_payment()` method

2. **`app/handlers/balance/main.py`**:
   - Add "card_to_card" to payment method selection
   - Add handler routing

3. **`app/keyboards/inline.py`**:
   - Add card-to-card payment keyboard
   - Add receipt upload keyboard

4. **`app/localization/locales/fa.json`**:
   - Add all card-to-card related text keys

**Estimated LOC**: ~100-150 lines (modifications)

---

### 4. Multi-Tenancy Integration

**Tenant Context:**
- Payment automatically uses tenant's card number from `tenant.settings.card_to_card.card_numbers`
- Display texts come from `tenant.settings.card_to_card.display_texts`
- Receipts sent to `tenant.settings.card_to_card.channel.chat_id`

**Isolation:**
- All payments filtered by `tenant_id`
- Each tenant has separate card numbers and channels
- Admins see only their tenant's receipts (unless system admin)

---

## Change Summary

### New Files (7 files)
1. `app/services/payment/card_to_card.py` - Payment mixin
2. `app/handlers/balance/card_to_card.py` - User payment handlers
3. `app/handlers/admin/card_to_card_receipts.py` - Admin receipt handlers
4. `app/services/card_to_card_service.py` - Business logic service
5. `app/database/crud/card_to_card.py` - CRUD operations
6. `migrations/xxx_add_card_to_card_payments.py` - Database migration
7. `tests/test_card_to_card_payment.py` - Unit tests

### Modified Files (6 files)
1. `app/database/models.py` - Add CardToCardPayment model
2. `app/services/payment_service.py` - Integrate mixin
3. `app/handlers/balance/main.py` - Add payment method
4. `app/keyboards/inline.py` - Add keyboards
5. `app/config.py` - Add settings
6. `app/localization/locales/fa.json` - Add translations

### Database Changes
- 1 new table: `card_to_card_payments`
- 6 indexes
- Migration script

---

## Effort Estimation

### Development Time

| Task | Estimated Hours |
|------|----------------|
| Database schema & migration | 2-3 |
| Payment Mixin implementation | 4-6 |
| User handlers (payment flow) | 6-8 |
| Admin handlers (approval flow) | 3-4 |
| Service layer | 3-4 |
| CRUD operations | 2-3 |
| Model & integration | 2-3 |
| Localization (Persian) | 2-3 |
| Testing | 6-8 |
| **Total** | **30-42 hours** |

### Complexity: **Medium**

- Well-defined patterns to follow
- Existing infrastructure supports it
- No major architectural changes needed
- Clear separation of concerns

---

## Risks & Considerations

### Low Risk ✅
- Payment pattern is well-established
- Channel messaging already works
- FSM system handles multi-step flows
- Database pattern is consistent

### Medium Risk ⚠️
- **Receipt validation**: Manual review required (no automatic OCR)
- **Channel permissions**: Bot must have send permissions in tenant channels
- **Expiration handling**: Need background task to expire old payments
- **Concurrent payments**: User might create multiple payments (need limits)

### Mitigation
- Start with manual review (no auto-approval)
- Add payment limits per user (e.g., max 3 pending)
- Background task for expiration (use existing task system)
- Clear error messages for channel permission issues

---

## Testing Requirements

### Unit Tests
- Payment creation
- Receipt upload
- Approval/rejection flow
- Tenant settings loading
- Reference code generation

### Integration Tests
- Full payment flow (user → receipt → approval)
- Channel forwarding
- Balance update
- Transaction creation
- Multi-tenant isolation

### Manual Tests
- Receipt upload (photo/document)
- Channel button interactions
- Tenant-specific card numbers
- Custom display texts
- Error scenarios

---

## Compatibility with Multi-Tenancy

### ✅ Full Compatibility

1. **Tenant Isolation**: Payments filtered by `tenant_id`
2. **Customization**: Card numbers and texts per tenant
3. **Channel Routing**: Each tenant has own channel
4. **Admin Access**: Tenant admins see only their receipts
5. **Settings**: Stored in `tenant.settings` JSONB

### Integration Points

- Uses `tenant_id` from context (same as other payments)
- Settings loaded from `tenant.settings.card_to_card`
- Channel ID from tenant settings
- All queries include tenant filtering

---

## Conclusion

**✅ Highly Compatible**: The existing codebase architecture is well-suited for card-to-card payments. The Mixin pattern, FSM system, channel messaging, and multi-tenancy support all align perfectly with this feature.

**Estimated Effort**: 30-42 hours of development time

**Complexity**: Medium (follows established patterns)

**Risk Level**: Low-Medium (mostly implementation, no architectural changes)

**Recommendation**: ✅ **Proceed with implementation** - The system is ready and compatible.

---

**Next Steps:**
1. Create database migration
2. Implement payment mixin
3. Add user handlers
4. Add admin handlers
5. Integrate with existing payment flow
6. Add localization
7. Test thoroughly

---

**Document Status**: Ready for Implementation  
**Review Required**: Yes - Architecture Team  
**Approval Required**: Yes - Technical Lead

