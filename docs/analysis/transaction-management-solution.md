# راه‌حل Transaction Management

**تاریخ:** 2025-12-21  
**اولویت:** 🔴 HIGH  
**هدف:** حل مشکل commit در CRUD functions برای پشتیبانی از transactions چندمرحله‌ای

---

## 📋 مشکل فعلی

CRUD functions داخل خودشان commit می‌کنند که باعث می‌شود نتوان چند عملیات را در یک transaction انجام داد.

**مثال مشکل:**
```python
# app/database/crud/bot_feature_flag.py
async def set_feature_flag(...):
    # ...
    await db.commit()  # ❌ مشکل: commit داخل CRUD
    return existing

# در handler نمی‌توان چند عملیات را در یک transaction انجام داد:
async def create_bot(...):
    await BotConfigService.set_feature_enabled(db, bot_id, 'card_to_card', True)
    # اگر این خط fail شود، خط قبلی commit شده است! ❌
    await BotConfigService.set_config(db, bot_id, 'DEFAULT_LANGUAGE', 'fa')
```

---

## ✅ راه‌حل پیشنهادی

### استراتژی: اضافه کردن Parameter `commit` به CRUD Functions

**مزایا:**
- ✅ Backward compatibility (default=True برای عملیات تک‌مرحله‌ای)
- ✅ کنترل transaction در handler level
- ✅ امکان استفاده از transaction context manager
- ✅ تغییرات minimal

---

## 🔧 پیاده‌سازی

### مرحله 1: Refactor CRUD Functions

#### 1.1. `app/database/crud/bot_feature_flag.py`

**قبل:**
```python
async def set_feature_flag(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    enabled: bool,
    config: Optional[Dict[str, Any]] = None
) -> BotFeatureFlag:
    existing = await get_feature_flag(db, bot_id, feature_key)
    
    if existing:
        existing.enabled = enabled
        if config is not None:
            existing.config = config or {}
        await db.commit()  # ❌ مشکل
        await db.refresh(existing)
        return existing
    else:
        feature_flag = BotFeatureFlag(...)
        db.add(feature_flag)
        await db.commit()  # ❌ مشکل
        await db.refresh(feature_flag)
        return feature_flag
```

**بعد:**
```python
async def set_feature_flag(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    enabled: bool,
    config: Optional[Dict[str, Any]] = None,
    commit: bool = True  # ✅ اضافه شده
) -> BotFeatureFlag:
    """
    Set or update a feature flag for a bot.
    
    Args:
        commit: If True, commit the transaction. If False, caller must commit.
                Default True for backward compatibility.
    """
    existing = await get_feature_flag(db, bot_id, feature_key)
    
    if existing:
        existing.enabled = enabled
        if config is not None:
            existing.config = config or {}
        if commit:
            await db.commit()
            await db.refresh(existing)
        return existing
    else:
        feature_flag = BotFeatureFlag(
            bot_id=bot_id,
            feature_key=feature_key,
            enabled=enabled,
            config=config or {}
        )
        db.add(feature_flag)
        if commit:
            await db.commit()
            await db.refresh(feature_flag)
        return feature_flag
```

#### 1.2. `app/database/crud/bot_configuration.py`

**قبل:**
```python
async def set_configuration(
    db: AsyncSession,
    bot_id: int,
    config_key: str,
    config_value: Dict[str, Any]
) -> BotConfiguration:
    existing = await get_configuration(db, bot_id, config_key)
    
    if existing:
        existing.config_value = config_value
        await db.commit()  # ❌ مشکل
        await db.refresh(existing)
        return existing
    else:
        configuration = BotConfiguration(...)
        db.add(configuration)
        await db.commit()  # ❌ مشکل
        await db.refresh(configuration)
        return configuration
```

**بعد:**
```python
async def set_configuration(
    db: AsyncSession,
    bot_id: int,
    config_key: str,
    config_value: Dict[str, Any],
    commit: bool = True  # ✅ اضافه شده
) -> BotConfiguration:
    """
    Set or update a configuration for a bot.
    
    Args:
        commit: If True, commit the transaction. If False, caller must commit.
                Default True for backward compatibility.
    """
    existing = await get_configuration(db, bot_id, config_key)
    
    if existing:
        existing.config_value = config_value
        if commit:
            await db.commit()
            await db.refresh(existing)
        return existing
    else:
        configuration = BotConfiguration(
            bot_id=bot_id,
            config_key=config_key,
            config_value=config_value
        )
        db.add(configuration)
        if commit:
            await db.commit()
            await db.refresh(configuration)
        return configuration
```

---

### مرحله 2: Update BotConfigService

#### 2.1. `app/services/bot_config_service.py`

**قبل:**
```python
@staticmethod
async def set_feature_enabled(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    enabled: bool,
    config: Optional[Dict[str, Any]] = None
) -> None:
    await set_feature_flag(db, bot_id, feature_key, enabled, config)

@staticmethod
async def set_config(
    db: AsyncSession,
    bot_id: int,
    config_key: str,
    value: Any
) -> None:
    # ...
    await set_configuration(db, bot_id, config_key, normalized_value)
```

**بعد:**
```python
@staticmethod
async def set_feature_enabled(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    enabled: bool,
    config: Optional[Dict[str, Any]] = None,
    commit: bool = True  # ✅ اضافه شده
) -> None:
    """
    Set or update a feature flag for a bot.
    
    Args:
        commit: If True, commit the transaction. If False, caller must commit.
                Default True for backward compatibility.
    """
    await set_feature_flag(db, bot_id, feature_key, enabled, config, commit=commit)

@staticmethod
async def set_config(
    db: AsyncSession,
    bot_id: int,
    config_key: str,
    value: Any,
    commit: bool = True  # ✅ اضافه شده
) -> None:
    """
    Set or update a configuration value for a bot.
    
    Args:
        commit: If True, commit the transaction. If False, caller must commit.
                Default True for backward compatibility.
    """
    # Normalize value for JSONB storage
    if isinstance(value, (str, int, bool, float, type(None))):
        normalized_value = {'value': value}
    else:
        normalized_value = value
    
    await set_configuration(db, bot_id, config_key, normalized_value, commit=commit)
```

---

### مرحله 3: استفاده در Handlers

#### 3.1. عملیات تک‌مرحله‌ای (Backward Compatible)

**مثال: Toggle Feature Flag**
```python
# app/handlers/admin/tenant_bots.py
async def toggle_feature_flag(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    bot_id: int,
    feature_key: str
) -> None:
    """Toggle feature flag - single operation, commit=True (default)"""
    current = await BotConfigService.is_feature_enabled(db, bot_id, feature_key)
    await BotConfigService.set_feature_enabled(
        db, bot_id, feature_key, not current,
        commit=True  # یا بدون commit (default=True)
    )
    # Transaction committed automatically ✅
```

#### 3.2. عملیات چندمرحله‌ای (با Transaction Context Manager)

**مثال: Create Bot**
```python
# app/handlers/admin/tenant_bots.py
async def process_bot_token(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession,
    db_user: User
) -> None:
    """Create bot with multiple config operations in one transaction"""
    data = await state.get_data()
    bot_name = data.get('bot_name')
    bot_token = message.text
    
    # Validate token...
    
    # Use transaction context manager for multi-step operation
    async with db.begin():  # ✅ Auto commit on success, rollback on error
        # Create bot
        bot = await create_bot(
            db,
            name=bot_name,
            telegram_bot_token=bot_token,
            is_master=False,
            commit=False  # ✅ Don't commit, let context manager handle it
        )
        
        # Set initial configurations (all in same transaction)
        await BotConfigService.set_config(
            db, bot.id, 'DEFAULT_LANGUAGE', 'fa',
            commit=False  # ✅ Don't commit
        )
        await BotConfigService.set_config(
            db, bot.id, 'SUPPORT_USERNAME', data.get('support_username', ''),
            commit=False  # ✅ Don't commit
        )
        await BotConfigService.set_feature_enabled(
            db, bot.id, 'card_to_card', True,
            commit=False  # ✅ Don't commit
        )
        
        # If any operation fails, all will be rolled back automatically ✅
    
    # Transaction committed automatically on success
    await message.answer(f"✅ Bot created: {bot.name}")
```

#### 3.3. عملیات چندمرحله‌ای (با Manual Transaction Control)

**مثال: Edit Multiple Settings**
```python
# app/handlers/admin/tenant_bots.py
async def process_edit_bot_settings(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession,
    db_user: User,
    bot_id: int
) -> None:
    """Edit multiple bot settings in one transaction"""
    data = await state.get_data()
    
    try:
        # Start transaction
        # Note: db.begin() returns a transaction object
        async with db.begin():
            # Update multiple configs
            if 'language' in data:
                await BotConfigService.set_config(
                    db, bot_id, 'DEFAULT_LANGUAGE', data['language'],
                    commit=False
                )
            
            if 'support' in data:
                await BotConfigService.set_config(
                    db, bot_id, 'SUPPORT_USERNAME', data['support'],
                    commit=False
                )
            
            if 'notifications_chat_id' in data:
                await BotConfigService.set_config(
                    db, bot_id, 'ADMIN_NOTIFICATIONS_CHAT_ID', data['notifications_chat_id'],
                    commit=False
                )
            
            # All operations in one transaction
            # Auto commit on success, rollback on error ✅
        
        await message.answer("✅ Settings updated successfully")
        
    except Exception as e:
        logger.error(f"Error updating bot settings: {e}")
        await message.answer("❌ Error updating settings. Please try again.")
        # Transaction automatically rolled back ✅
```

---

## 📝 Migration Plan

### مرحله 1: Refactor CRUD Functions (Backward Compatible)

1. اضافه کردن parameter `commit: bool = True` به:
   - `app/database/crud/bot_feature_flag.py::set_feature_flag`
   - `app/database/crud/bot_configuration.py::set_configuration`
   - سایر CRUD functions که commit می‌کنند

2. تست کردن backward compatibility:
   - تمام handlers فعلی باید بدون تغییر کار کنند (commit=True default)

### مرحله 2: Update BotConfigService

1. اضافه کردن parameter `commit: bool = True` به:
   - `BotConfigService.set_feature_enabled`
   - `BotConfigService.set_config`

2. Pass کردن commit parameter به CRUD functions

### مرحله 3: Update Handlers برای عملیات چندمرحله‌ای

1. شناسایی handlers با عملیات چندمرحله‌ای:
   - `start_create_bot` / `process_bot_token`
   - `process_edit_bot_settings` (اگر چند config را همزمان تغییر می‌دهد)

2. استفاده از transaction context manager:
   ```python
   async with db.begin():
       # Multiple operations with commit=False
   ```

### مرحله 4: Testing

1. Unit tests برای CRUD functions با `commit=False`
2. Integration tests برای عملیات چندمرحله‌ای
3. Test rollback scenarios

---

## 🧪 Testing Strategy

### Test 1: Backward Compatibility

```python
# tests/test_crud_backward_compatibility.py
async def test_set_feature_flag_default_commit():
    """Test that default commit=True still works"""
    db = get_test_db()
    flag = await set_feature_flag(db, bot_id=1, feature_key='test', enabled=True)
    # Should commit automatically
    assert flag.enabled == True
    
    # Verify it's persisted
    db2 = get_test_db()
    flag2 = await get_feature_flag(db2, bot_id=1, feature_key='test')
    assert flag2 is not None
    assert flag2.enabled == True
```

### Test 2: Multi-Step Transaction

```python
# tests/test_multi_step_transaction.py
async def test_create_bot_with_configs_transaction():
    """Test that create bot with configs uses transaction"""
    db = get_test_db()
    
    async with db.begin():
        bot = await create_bot(db, name="Test", token="test", commit=False)
        await BotConfigService.set_config(db, bot.id, 'DEFAULT_LANGUAGE', 'fa', commit=False)
        await BotConfigService.set_feature_enabled(db, bot.id, 'card_to_card', True, commit=False)
    
    # Verify all persisted
    db2 = get_test_db()
    bot2 = await get_bot_by_id(db2, bot.id)
    assert bot2 is not None
    
    lang = await BotConfigService.get_config(db2, bot.id, 'DEFAULT_LANGUAGE')
    assert lang == 'fa'
    
    enabled = await BotConfigService.is_feature_enabled(db2, bot.id, 'card_to_card')
    assert enabled == True
```

### Test 3: Rollback on Error

```python
# tests/test_transaction_rollback.py
async def test_rollback_on_error():
    """Test that transaction rolls back on error"""
    db = get_test_db()
    
    try:
        async with db.begin():
            bot = await create_bot(db, name="Test", token="test", commit=False)
            await BotConfigService.set_config(db, bot.id, 'DEFAULT_LANGUAGE', 'fa', commit=False)
            # Simulate error
            raise ValueError("Test error")
    except ValueError:
        pass
    
    # Verify nothing persisted
    db2 = get_test_db()
    bot2 = await get_bot_by_id(db2, bot.id)
    assert bot2 is None  # Should be rolled back
```

---

## 📋 Checklist پیاده‌سازی

### Phase 1: CRUD Refactoring
- [ ] اضافه کردن `commit: bool = True` به `set_feature_flag`
- [ ] اضافه کردن `commit: bool = True` به `set_configuration`
- [ ] تست backward compatibility
- [ ] Update docstrings

### Phase 2: Service Layer Update
- [ ] اضافه کردن `commit: bool = True` به `BotConfigService.set_feature_enabled`
- [ ] اضافه کردن `commit: bool = True` به `BotConfigService.set_config`
- [ ] Pass کردن commit parameter به CRUD functions
- [ ] تست backward compatibility

### Phase 3: Handler Updates
- [ ] شناسایی handlers با عملیات چندمرحله‌ای
- [ ] Update `start_create_bot` / `process_bot_token` برای استفاده از transaction
- [ ] Update سایر handlers که نیاز به transaction دارند
- [ ] تست عملیات چندمرحله‌ای

### Phase 4: Testing
- [ ] Unit tests برای CRUD با `commit=False`
- [ ] Integration tests برای transactions
- [ ] Test rollback scenarios
- [ ] Performance testing

---

## ⚠️ نکات مهم

1. **Backward Compatibility**: همیشه `commit=True` را به عنوان default بگذارید
2. **Documentation**: تمام functions باید document شوند که commit parameter چیست
3. **Error Handling**: Transaction context manager به صورت خودکار rollback می‌کند
4. **Performance**: استفاده از transaction برای عملیات چندمرحله‌ای بهتر است

---

## 🎯 نتیجه

با این راه‌حل:
- ✅ Backward compatibility حفظ می‌شود
- ✅ عملیات چندمرحله‌ای در یک transaction انجام می‌شوند
- ✅ Rollback خودکار در صورت خطا
- ✅ تغییرات minimal و safe

**اولویت پیاده‌سازی:** 🔴 HIGH - باید قبل از ادامه STORY-002 و STORY-003 انجام شود

