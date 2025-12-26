# Payment Flows - Detailed Implementation Guide

**Version:** 1.0  
**Date:** 2025-12-14  
**Status:** Ready for Implementation

---

## 🎯 هدف

این راهنما دستورالعمل‌های **step-by-step** برای پیاده‌سازی کامل payment flows (Card-to-Card و Zarinpal) را فراهم می‌کند.

---

## 💳 Card-to-Card Payment Flow

### Overview

**Flow:**
1. User selects card-to-card payment
2. System displays card info (with rotation)
3. User submits receipt (image/text)
4. System creates payment record
5. System sends notification to admin
6. Admin reviews and approves/rejects
7. On approval: Complete transaction and create subscription

### Increment 3.3: Card-to-Card Implementation

#### Step 1: Create Handler File

```bash
touch app/handlers/balance/card_to_card.py
```

#### Step 2: Add Imports and State

```python
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.bot import get_bot_by_id
from app.database.crud.tenant_payment_card import get_next_card_for_rotation
from app.database.crud.card_to_card_payment import (
    create_card_payment,
    get_payment_by_tracking,
    update_payment_status
)
from app.database.crud.transaction import create_transaction
from app.database.crud.subscription import create_subscription
from app.services.payment_card_service import PaymentCardService
import secrets

router = Router()


class CardToCardPaymentState(StatesGroup):
    waiting_for_receipt = State()
```

#### Step 3: Implement Card Selection Handler

```python
@router.callback_query(F.data == "payment_card_to_card")
async def handle_card_to_card_selection(
    callback: CallbackQuery,
    db: AsyncSession,
    bot_id: int,
    state: FSMContext
):
    """Display card information and request receipt."""
    # Get bot config
    bot = await get_bot_by_id(db, bot_id)
    if not bot or not bot.card_to_card_enabled:
        await callback.answer("پرداخت کارت به کارت غیرفعال است", show_alert=True)
        return
    
    # Get next card (with rotation)
    card = await PaymentCardService.get_next_card(db, bot_id)
    if not card:
        await callback.answer("کارت پرداختی یافت نشد", show_alert=True)
        return
    
    # Display card info
    card_info = f"""
💳 پرداخت کارت به کارت

شماره کارت: `{card.card_number}`
دارنده کارت: {card.card_holder_name}

لطفاً رسید پرداخت را ارسال کنید.
می‌توانید تصویر، متن، یا هر دو ارسال کنید.
"""
    
    await callback.message.answer(card_info, parse_mode="Markdown")
    await state.set_state(CardToCardPaymentState.waiting_for_receipt)
    await state.update_data(card_id=card.id)
    await callback.answer()
```

#### Step 4: Implement Receipt Handler

```python
@router.message(CardToCardPaymentState.waiting_for_receipt)
async def handle_receipt_received(
    message: Message,
    db: AsyncSession,
    bot_id: int,
    db_user: User,
    state: FSMContext
):
    """Process received receipt."""
    data = await state.get_data()
    card_id = data.get('card_id')
    
    # Get amount from context (should be set in purchase flow)
    amount_kopeks = data.get('amount_kopeks', 0)
    if not amount_kopeks:
        await message.answer("خطا: مبلغ مشخص نشده است")
        return
    
    # Extract receipt data
    receipt_type = None
    receipt_text = None
    receipt_image_file_id = None
    
    if message.photo:
        receipt_image_file_id = message.photo[-1].file_id
        receipt_type = 'image'
        if message.caption:
            receipt_text = message.caption
            receipt_type = 'both'
    elif message.text:
        receipt_text = message.text
        receipt_type = 'text'
    else:
        await message.answer("لطفاً تصویر یا متن رسید را ارسال کنید")
        return
    
    # Generate tracking number
    tracking_number = f"C2C{secrets.token_hex(8).upper()}"
    
    # Create payment record
    payment = await create_card_payment(
        db=db,
        bot_id=bot_id,
        user_id=db_user.id,
        card_id=card_id,
        amount_kopeks=amount_kopeks,
        tracking_number=tracking_number,
        receipt_type=receipt_type,
        receipt_text=receipt_text,
        receipt_image_file_id=receipt_image_file_id,
        status='pending'
    )
    
    # Send notification to admin
    await send_admin_notification(db, bot_id, payment)
    
    # Confirm to user
    await message.answer(
        f"✅ رسید شما دریافت شد.\n\n"
        f"شماره پیگیری: `{tracking_number}`\n\n"
        f"پس از بررسی، نتیجه به شما اطلاع داده خواهد شد.",
        parse_mode="Markdown"
    )
    
    await state.clear()
```

#### Step 5: Implement Admin Notification

```python
async def send_admin_notification(db: AsyncSession, bot_id: int, payment: CardToCardPayment):
    """Send payment notification to admin for review."""
    from app.database.crud.bot import get_bot_by_id
    from app.database.crud.user import get_user_by_id
    from aiogram import Bot
    
    bot_config = await get_bot_by_id(db, bot_id)
    if not bot_config or not bot_config.admin_chat_id:
        return
    
    user = await get_user_by_id(db, payment.user_id, bot_id)
    
    # Build notification message
    message_text = f"""
🔔 درخواست پرداخت کارت به کارت

👤 کاربر: @{user.username or 'N/A'} ({user.telegram_id})
💰 مبلغ: {payment.amount_kopeks / 100} تومان
🔢 شماره پیگیری: {payment.tracking_number}
📅 تاریخ: {payment.created_at.strftime('%Y-%m-%d %H:%M')}
"""
    
    # Build inline keyboard
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ تایید",
                callback_data=f"approve_card_payment:{payment.id}"
            ),
            InlineKeyboardButton(
                text="❌ رد",
                callback_data=f"reject_card_payment:{payment.id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 جزئیات",
                callback_data=f"card_payment_details:{payment.id}"
            )
        ]
    ])
    
    # Send to admin topic
    bot = Bot(token=bot_config.telegram_bot_token)
    if bot_config.card_receipt_topic_id:
        await bot.send_message(
            chat_id=bot_config.admin_chat_id,
            message_thread_id=bot_config.card_receipt_topic_id,
            text=message_text,
            reply_markup=keyboard
        )
    else:
        await bot.send_message(
            chat_id=bot_config.admin_chat_id,
            text=message_text,
            reply_markup=keyboard
        )
    
    # Send receipt if image
    if payment.receipt_image_file_id:
        await bot.send_photo(
            chat_id=bot_config.admin_chat_id,
            photo=payment.receipt_image_file_id,
            message_thread_id=bot_config.card_receipt_topic_id if bot_config.card_receipt_topic_id else None
        )
```

#### Step 6: Implement Admin Approval Handler

```python
@router.callback_query(F.data.startswith("approve_card_payment:"))
async def handle_payment_approval(
    callback: CallbackQuery,
    db: AsyncSession,
    bot_id: int,
    db_user: User,  # Admin user
    state: FSMContext
):
    """Approve card-to-card payment."""
    payment_id = int(callback.data.split(":")[1])
    
    # Get payment
    payment = await get_payment_by_id(db, payment_id)
    if not payment or payment.bot_id != bot_id:
        await callback.answer("پرداخت یافت نشد", show_alert=True)
        return
    
    if payment.status != 'pending':
        await callback.answer("این پرداخت قبلاً بررسی شده است", show_alert=True)
        return
    
    # Update payment status
    await update_payment_status(
        db=db,
        payment_id=payment_id,
        status='approved',
        admin_reviewed_by=db_user.id,
        admin_reviewed_at=func.now()
    )
    
    # Create transaction
    transaction = await create_transaction(
        db=db,
        bot_id=bot_id,
        user_id=payment.user_id,
        amount_kopeks=payment.amount_kopeks,
        payment_method='card_to_card',
        status='completed'
    )
    
    # Update payment with transaction_id
    await update_payment_status(
        db=db,
        payment_id=payment_id,
        transaction_id=transaction.id
    )
    
    # Create subscription (get plan from context)
    # This should be done based on the original purchase flow
    
    # Notify user
    bot_config = await get_bot_by_id(db, bot_id)
    bot = Bot(token=bot_config.telegram_bot_token)
    await bot.send_message(
        chat_id=payment.user.telegram_id,
        text=f"✅ پرداخت شما تایید شد.\n\nشماره پیگیری: {payment.tracking_number}"
    )
    
    # Update admin message
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ تایید شد",
        reply_markup=None
    )
    await callback.answer("پرداخت تایید شد")
```

#### Step 7: Implement Admin Rejection Handler

```python
@router.callback_query(F.data.startswith("reject_card_payment:"))
async def handle_payment_rejection(
    callback: CallbackQuery,
    db: AsyncSession,
    bot_id: int,
    db_user: User,
    state: FSMContext
):
    """Reject card-to-card payment."""
    payment_id = int(callback.data.split(":")[1])
    
    # Get payment
    payment = await get_payment_by_id(db, payment_id)
    if not payment or payment.bot_id != bot_id:
        await callback.answer("پرداخت یافت نشد", show_alert=True)
        return
    
    if payment.status != 'pending':
        await callback.answer("این پرداخت قبلاً بررسی شده است", show_alert=True)
        return
    
    # Update payment status
    await update_payment_status(
        db=db,
        payment_id=payment_id,
        status='rejected',
        admin_reviewed_by=db_user.id,
        admin_reviewed_at=func.now()
    )
    
    # Notify user
    bot_config = await get_bot_by_id(db, bot_id)
    bot = Bot(token=bot_config.telegram_bot_token)
    await bot.send_message(
        chat_id=payment.user.telegram_id,
        text=f"❌ متأسفانه پرداخت شما رد شد.\n\nشماره پیگیری: {payment.tracking_number}\n\nلطفاً با پشتیبانی تماس بگیرید."
    )
    
    # Update admin message
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ رد شد",
        reply_markup=None
    )
    await callback.answer("پرداخت رد شد")
```

#### Step 8: Register Handlers

In `app/handlers/balance/__init__.py`:

```python
from .card_to_card import router as card_to_card_router

def register_card_to_card_handlers(dp):
    dp.include_router(card_to_card_router)
```

In `app/bot.py`:

```python
from app.handlers.balance import register_card_to_card_handlers
register_card_to_card_handlers(dp)
```

#### Acceptance Criteria

- ✅ Card selection displays card info
- ✅ Receipt submission works (image/text/both)
- ✅ Tracking number generated
- ✅ Payment record created
- ✅ Admin notification sent
- ✅ Admin approval works
- ✅ Admin rejection works
- ✅ Transaction created on approval
- ✅ User notified of result
- ✅ All tests pass

---

## 💰 Zarinpal Payment Flow

### Overview

**Flow:**
1. User selects Zarinpal payment
2. System creates payment request via Zarinpal API
3. User redirected to Zarinpal payment page
4. User completes payment
5. Zarinpal redirects to callback URL
6. System verifies payment
7. On success: Complete transaction and create subscription

### Increment 3.4: Zarinpal Implementation

#### Step 1: Create Zarinpal Client

```bash
touch app/external/zarinpal.py
```

#### Step 2: Implement Zarinpal Client

```python
import aiohttp
from typing import Dict, Optional
from app.config import settings


class ZarinpalClient:
    def __init__(self, merchant_id: str, sandbox: bool = False):
        self.merchant_id = merchant_id
        self.sandbox = sandbox
        self.base_url = "https://sandbox.zarinpal.com" if sandbox else "https://api.zarinpal.com"
    
    async def create_payment_request(
        self,
        amount: int,  # in Toman (not kopeks)
        callback_url: str,
        description: str,
        mobile: Optional[str] = None,
        email: Optional[str] = None
    ) -> Dict:
        """Create payment request and get authority."""
        url = f"{self.base_url}/pg/v4/payment/request.json"
        
        data = {
            "merchant_id": self.merchant_id,
            "amount": amount,
            "callback_url": callback_url,
            "description": description
        }
        
        if mobile:
            data["mobile"] = mobile
        if email:
            data["email"] = email
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                result = await response.json()
                
                if result.get("data", {}).get("code") == 100:
                    return {
                        "success": True,
                        "authority": result["data"]["authority"],
                        "payment_url": f"{self.base_url}/pg/StartPay/{result['data']['authority']}"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("errors", {}).get("message", "Unknown error")
                    }
    
    async def verify_payment(
        self,
        authority: str,
        amount: int  # in Toman
    ) -> Dict:
        """Verify payment after callback."""
        url = f"{self.base_url}/pg/v4/payment/verify.json"
        
        data = {
            "merchant_id": self.merchant_id,
            "authority": authority,
            "amount": amount
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                result = await response.json()
                
                if result.get("data", {}).get("code") == 100:
                    return {
                        "success": True,
                        "ref_id": result["data"]["ref_id"]
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("errors", {}).get("message", "Payment failed")
                    }
```

#### Step 3: Create Handler File

```bash
touch app/handlers/balance/zarinpal.py
```

#### Step 4: Implement Payment Request Handler

```python
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.bot import get_bot_by_id
from app.database.crud.zarinpal_payment import create_zarinpal_payment
from app.external.zarinpal import ZarinpalClient
from app.config import settings

router = Router()


@router.callback_query(F.data == "payment_zarinpal")
async def handle_zarinpal_selection(
    callback: CallbackQuery,
    db: AsyncSession,
    bot_id: int,
    db_user: User,
    state: FSMContext
):
    """Create Zarinpal payment request."""
    # Get bot config
    bot = await get_bot_by_id(db, bot_id)
    if not bot or not bot.zarinpal_enabled or not bot.zarinpal_merchant_id:
        await callback.answer("پرداخت زرین‌پال غیرفعال است", show_alert=True)
        return
    
    # Get amount from context
    data = await state.get_data()
    amount_kopeks = data.get('amount_kopeks', 0)
    if not amount_kopeks:
        await callback.answer("خطا: مبلغ مشخص نشده است")
        return
    
    amount_toman = amount_kopeks // 10  # Convert kopeks to Toman
    
    # Create Zarinpal client
    client = ZarinpalClient(
        merchant_id=bot.zarinpal_merchant_id,
        sandbox=bot.zarinpal_sandbox
    )
    
    # Build callback URL
    callback_url = f"{settings.WEB_API_URL}/api/v1/payments/zarinpal/callback"
    
    # Create payment request
    result = await client.create_payment_request(
        amount=amount_toman,
        callback_url=callback_url,
        description=f"خرید اشتراک - Bot {bot.name}",
        mobile=str(db_user.telegram_id) if db_user.telegram_id else None
    )
    
    if not result["success"]:
        await callback.answer(f"خطا: {result.get('error', 'Unknown error')}", show_alert=True)
        return
    
    # Create payment record
    payment = await create_zarinpal_payment(
        db=db,
        bot_id=bot_id,
        user_id=db_user.id,
        amount_kopeks=amount_kopeks,
        zarinpal_authority=result["authority"],
        status='pending',
        callback_url=callback_url
    )
    
    # Send payment URL to user
    await callback.message.answer(
        f"🔗 برای پرداخت، روی لینک زیر کلیک کنید:\n\n{result['payment_url']}\n\n"
        f"پس از پرداخت، به صورت خودکار به ربات بازمی‌گردید."
    )
    
    await callback.answer()
```

#### Step 5: Implement Callback Handler (Web API)

Create `app/webapi/routes/zarinpal_callback.py`:

```python
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.database.crud.zarinpal_payment import (
    get_payment_by_authority,
    update_zarinpal_payment
)
from app.database.crud.transaction import create_transaction
from app.external.zarinpal import ZarinpalClient
from app.database.crud.bot import get_bot_by_id

router = APIRouter()


@router.get("/api/v1/payments/zarinpal/callback")
async def zarinpal_callback(
    request: Request,
    Status: str,
    Authority: str,
    db: AsyncSession = Depends(get_db)
):
    """Handle Zarinpal payment callback."""
    # Get payment by authority
    payment = await get_payment_by_authority(db, Authority)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status != 'pending':
        return {"status": "already_processed", "payment_id": payment.id}
    
    # Get bot config
    bot = await get_bot_by_id(db, payment.bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    # Verify payment
    client = ZarinpalClient(
        merchant_id=bot.zarinpal_merchant_id,
        sandbox=bot.zarinpal_sandbox
    )
    
    amount_toman = payment.amount_kopeks // 10
    result = await client.verify_payment(Authority, amount_toman)
    
    if result["success"]:
        # Update payment
        await update_zarinpal_payment(
            db=db,
            payment_id=payment.id,
            status='paid',
            zarinpal_ref_id=result["ref_id"]
        )
        
        # Create transaction
        transaction = await create_transaction(
            db=db,
            bot_id=payment.bot_id,
            user_id=payment.user_id,
            amount_kopeks=payment.amount_kopeks,
            payment_method='zarinpal',
            status='completed'
        )
        
        # Update payment with transaction_id
        await update_zarinpal_payment(
            db=db,
            payment_id=payment.id,
            transaction_id=transaction.id
        )
        
        # Create subscription (based on original purchase flow)
        # ...
        
        # Notify user via Telegram
        from aiogram import Bot
        bot_instance = Bot(token=bot.telegram_bot_token)
        await bot_instance.send_message(
            chat_id=payment.user.telegram_id,
            text=f"✅ پرداخت شما با موفقیت انجام شد.\n\nکد پیگیری: {result['ref_id']}"
        )
        
        return {"status": "success", "ref_id": result["ref_id"]}
    else:
        # Update payment status
        await update_zarinpal_payment(
            db=db,
            payment_id=payment.id,
            status='failed'
        )
        
        return {"status": "failed", "error": result.get("error")}
```

#### Step 6: Register Routes

In `app/webapi/routes/__init__.py`:

```python
from .zarinpal_callback import router as zarinpal_callback_router

def register_routes(app):
    app.include_router(zarinpal_callback_router)
```

#### Acceptance Criteria

- ✅ Payment request created successfully
- ✅ User redirected to Zarinpal
- ✅ Callback received and processed
- ✅ Payment verification works
- ✅ Transaction created on success
- ✅ User notified of result
- ✅ All tests pass

---

## 📝 Notes

- **Error Handling:** Always handle errors gracefully
- **Logging:** Log all payment operations
- **Security:** Never expose API tokens or sensitive data
- **Testing:** Test with sandbox mode first
- **Monitoring:** Monitor payment success rates

---

**Related Documents:**
- [Workflow Guide](./07-workflow-guide.md)
- [Code Changes](./02-code-changes.md)
- [Database Schema](./01-database-schema.md)
