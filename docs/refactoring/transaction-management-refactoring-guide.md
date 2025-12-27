# راهنمای Refactoring Transaction Management

**تاریخ:** 2025-12-21  
**اولویت:** 🔴 HIGH

این فایل تغییرات دقیق برای refactoring transaction management را نشان می‌دهد.

---

## 📁 فایل‌های نیازمند تغییر

### 1. `app/database/crud/bot_feature_flag.py`

**تغییرات:**

```python
# BEFORE (خط 48-80)
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
        await db.commit()  # ❌ حذف شود
        await db.refresh(existing)
        return existing
    else:
        feature_flag = BotFeatureFlag(...)
        db.add(feature_flag)
        await db.commit()  # ❌ حذف شود
        await db.refresh(feature_flag)
        return feature_flag

# AFTER
async def set_feature_flag(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    enabled: bool,
    config: Optional[Dict[str, Any]] = None,
    commit: bool = True  # ✅ اضافه شود
) -> BotFeatureFlag:
    """
    Set or update a feature flag for a bot.
    
    Args:
        db: Database session
        bot_id: Bot ID
        feature_key: Feature key
        enabled: True/False
        config: Optional config dict
        commit: If True, commit the transaction. If False, caller must commit.
                Default True for backward compatibility.
    
    Returns:
        BotFeatureFlag instance
    """
    existing = await get_feature_flag(db, bot_id, feature_key)
    
    if existing:
        existing.enabled = enabled
        if config is not None:
            existing.config = config or {}
        if commit:  # ✅ شرطی شود
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
        if commit:  # ✅ شرطی شود
            await db.commit()
            await db.refresh(feature_flag)
        return feature_flag
```

**تغییرات در سایر functions:**

```python
# enable_feature (خط 114-121)
async def enable_feature(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    config: Optional[Dict[str, Any]] = None,
    commit: bool = True  # ✅ اضافه شود
) -> BotFeatureFlag:
    return await set_feature_flag(db, bot_id, feature_key, enabled=True, config=config, commit=commit)

# disable_feature (خط 124-130)
async def disable_feature(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    commit: bool = True  # ✅ اضافه شود
) -> BotFeatureFlag:
    return await set_feature_flag(db, bot_id, feature_key, enabled=False, commit=commit)

# toggle_feature (خط 133-149)
async def toggle_feature(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    commit: bool = True  # ✅ اضافه شود
) -> Optional[BotFeatureFlag]:
    feature_flag = await get_feature_flag(db, bot_id, feature_key)
    if not feature_flag:
        return None
    
    return await set_feature_flag(
        db,
        bot_id,
        feature_key,
        enabled=not feature_flag.enabled,
        config=feature_flag.config,
        commit=commit  # ✅ اضافه شود
    )
```

---

### 2. `app/database/crud/bot_configuration.py`

**تغییرات:**

```python
# BEFORE (خط 38-66)
async def set_configuration(
    db: AsyncSession,
    bot_id: int,
    config_key: str,
    config_value: Dict[str, Any]
) -> BotConfiguration:
    existing = await get_configuration(db, bot_id, config_key)
    
    if existing:
        existing.config_value = config_value
        await db.commit()  # ❌ حذف شود
        await db.refresh(existing)
        return existing
    else:
        configuration = BotConfiguration(...)
        db.add(configuration)
        await db.commit()  # ❌ حذف شود
        await db.refresh(configuration)
        return configuration

# AFTER
async def set_configuration(
    db: AsyncSession,
    bot_id: int,
    config_key: str,
    config_value: Dict[str, Any],
    commit: bool = True  # ✅ اضافه شود
) -> BotConfiguration:
    """
    Set or update a configuration for a bot.
    
    Args:
        db: Database session
        bot_id: Bot ID
        config_key: Config key
        config_value: Config value (JSONB)
        commit: If True, commit the transaction. If False, caller must commit.
                Default True for backward compatibility.
    
    Returns:
        BotConfiguration instance
    """
    existing = await get_configuration(db, bot_id, config_key)
    
    if existing:
        existing.config_value = config_value
        if commit:  # ✅ شرطی شود
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
        if commit:  # ✅ شرطی شود
            await db.commit()
            await db.refresh(configuration)
        return configuration
```

**تغییرات در سایر functions:**

```python
# update_configuration_partial (خط 126-148)
async def update_configuration_partial(
    db: AsyncSession,
    bot_id: int,
    config_key: str,
    partial_value: Dict[str, Any],
    commit: bool = True  # ✅ اضافه شود
) -> Optional[BotConfiguration]:
    existing = await get_configuration(db, bot_id, config_key)
    
    if existing:
        current_value = existing.config_value if isinstance(existing.config_value, dict) else {}
        merged_value = {**current_value, **partial_value}
        existing.config_value = merged_value
        if commit:  # ✅ شرطی شود
            await db.commit()
            await db.refresh(existing)
        return existing
    else:
        return await set_configuration(db, bot_id, config_key, partial_value, commit=commit)
```

---

### 3. `app/services/bot_config_service.py`

**تغییرات:**

```python
# BEFORE (خط 52-70)
@staticmethod
async def set_feature_enabled(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    enabled: bool,
    config: Optional[Dict[str, Any]] = None
) -> None:
    await set_feature_flag(db, bot_id, feature_key, enabled, config)

# AFTER
@staticmethod
async def set_feature_enabled(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    enabled: bool,
    config: Optional[Dict[str, Any]] = None,
    commit: bool = True  # ✅ اضافه شود
) -> None:
    """
    Set or update a feature flag for a bot.
    
    Args:
        db: Database session
        bot_id: Bot ID
        feature_key: Feature key
        enabled: True/False
        config: Optional config dict
        commit: If True, commit the transaction. If False, caller must commit.
                Default True for backward compatibility.
    """
    await set_feature_flag(db, bot_id, feature_key, enabled, config, commit=commit)
```

```python
# BEFORE (خط 109-136)
@staticmethod
async def set_config(
    db: AsyncSession,
    bot_id: int,
    config_key: str,
    value: Any
) -> None:
    # Normalize value for JSONB storage
    if isinstance(value, (str, int, bool, float, type(None))):
        normalized_value = {'value': value}
    else:
        normalized_value = value
    
    await set_configuration(db, bot_id, config_key, normalized_value)

# AFTER
@staticmethod
async def set_config(
    db: AsyncSession,
    bot_id: int,
    config_key: str,
    value: Any,
    commit: bool = True  # ✅ اضافه شود
) -> None:
    """
    Set or update a configuration value for a bot.
    
    Args:
        db: Database session
        bot_id: Bot ID
        config_key: Config key
        value: Config value
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

### 4. `app/handlers/admin/tenant_bots.py`

**تغییرات در عملیات چندمرحله‌ای:**

#### 4.1. Create Bot Flow

```python
# BEFORE (اگر وجود دارد)
async def process_bot_token(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession,
    db_user: User
) -> None:
    data = await state.get_data()
    bot_token = message.text
    
    # Create bot
    bot = await create_bot(db, name=data['bot_name'], telegram_bot_token=bot_token)
    
    # Set configs (each commits separately) ❌
    await BotConfigService.set_config(db, bot.id, 'DEFAULT_LANGUAGE', 'fa')
    await BotConfigService.set_config(db, bot.id, 'SUPPORT_USERNAME', data.get('support', ''))
    await BotConfigService.set_feature_enabled(db, bot.id, 'card_to_card', True)

# AFTER
async def process_bot_token(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession,
    db_user: User
) -> None:
    data = await state.get_data()
    bot_token = message.text
    
    # Use transaction context manager for multi-step operation
    async with db.begin():  # ✅ Auto commit on success, rollback on error
        # Create bot (if create_bot also supports commit parameter)
        bot = await create_bot(
            db,
            name=data['bot_name'],
            telegram_bot_token=bot_token,
            commit=False  # ✅ Don't commit, let context manager handle it
        )
        
        # Set configs (all in same transaction)
        await BotConfigService.set_config(
            db, bot.id, 'DEFAULT_LANGUAGE', 'fa',
            commit=False  # ✅ Don't commit
        )
        await BotConfigService.set_config(
            db, bot.id, 'SUPPORT_USERNAME', data.get('support', ''),
            commit=False  # ✅ Don't commit
        )
        await BotConfigService.set_feature_enabled(
            db, bot.id, 'card_to_card', True,
            commit=False  # ✅ Don't commit
        )
        # If any operation fails, all will be rolled back automatically ✅
    
    # Transaction committed automatically on success
    await message.answer(f"✅ Bot created: {bot.name}")
    await state.clear()
```

#### 4.2. Edit Multiple Settings

```python
# اگر handler وجود دارد که چند config را همزمان تغییر می‌دهد:
async def process_edit_multiple_settings(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession,
    db_user: User,
    bot_id: int
) -> None:
    data = await state.get_data()
    
    try:
        async with db.begin():  # ✅ Transaction context manager
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
            # All operations in one transaction ✅
        
        await message.answer("✅ Settings updated successfully")
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        await message.answer("❌ Error updating settings. Please try again.")
        # Transaction automatically rolled back ✅
```

---

## ✅ Checklist پیاده‌سازی

### Step 1: CRUD Functions
- [ ] Update `app/database/crud/bot_feature_flag.py::set_feature_flag`
  - [ ] اضافه کردن parameter `commit: bool = True`
  - [ ] شرطی کردن `await db.commit()`
  - [ ] Update docstring
- [ ] Update `app/database/crud/bot_feature_flag.py::enable_feature`
- [ ] Update `app/database/crud/bot_feature_flag.py::disable_feature`
- [ ] Update `app/database/crud/bot_feature_flag.py::toggle_feature`
- [ ] Update `app/database/crud/bot_configuration.py::set_configuration`
  - [ ] اضافه کردن parameter `commit: bool = True`
  - [ ] شرطی کردن `await db.commit()`
  - [ ] Update docstring
- [ ] Update `app/database/crud/bot_configuration.py::update_configuration_partial`

### Step 2: Service Layer
- [ ] Update `app/services/bot_config_service.py::set_feature_enabled`
  - [ ] اضافه کردن parameter `commit: bool = True`
  - [ ] Pass کردن commit به CRUD function
  - [ ] Update docstring
- [ ] Update `app/services/bot_config_service.py::set_config`
  - [ ] اضافه کردن parameter `commit: bool = True`
  - [ ] Pass کردن commit به CRUD function
  - [ ] Update docstring

### Step 3: Handlers (Multi-Step Operations)
- [ ] شناسایی handlers با عملیات چندمرحله‌ای
- [ ] Update `app/handlers/admin/tenant_bots.py::process_bot_token` (اگر وجود دارد)
- [ ] Update سایر handlers که نیاز به transaction دارند
- [ ] استفاده از `async with db.begin():` برای عملیات چندمرحله‌ای

### Step 4: Testing
- [ ] Unit tests برای CRUD با `commit=False`
- [ ] Integration tests برای transactions
- [ ] Test rollback scenarios
- [ ] Test backward compatibility (commit=True default)

---

## 🧪 مثال Test Cases

### Test 1: Backward Compatibility

```python
# tests/test_crud_backward_compatibility.py
import pytest
from app.database.crud.bot_feature_flag import set_feature_flag, get_feature_flag

@pytest.mark.asyncio
async def test_set_feature_flag_default_commit(db_session):
    """Test that default commit=True still works (backward compatibility)"""
    bot_id = 1
    feature_key = 'test_feature'
    
    # Set feature flag with default commit=True
    flag = await set_feature_flag(
        db_session, bot_id, feature_key, enabled=True
    )
    assert flag.enabled == True
    
    # Verify it's persisted (new session)
    new_session = get_new_db_session()
    flag2 = await get_feature_flag(new_session, bot_id, feature_key)
    assert flag2 is not None
    assert flag2.enabled == True
```

### Test 2: Multi-Step Transaction

```python
# tests/test_multi_step_transaction.py
import pytest
from app.services.bot_config_service import BotConfigService

@pytest.mark.asyncio
async def test_create_bot_with_configs_transaction(db_session):
    """Test that create bot with configs uses transaction"""
    bot_id = 999
    
    async with db_session.begin():
        await BotConfigService.set_config(
            db_session, bot_id, 'DEFAULT_LANGUAGE', 'fa',
            commit=False
        )
        await BotConfigService.set_config(
            db_session, bot_id, 'SUPPORT_USERNAME', '@support',
            commit=False
        )
        await BotConfigService.set_feature_enabled(
            db_session, bot_id, 'card_to_card', True,
            commit=False
        )
    
    # Verify all persisted
    new_session = get_new_db_session()
    lang = await BotConfigService.get_config(new_session, bot_id, 'DEFAULT_LANGUAGE')
    assert lang == 'fa'
    
    support = await BotConfigService.get_config(new_session, bot_id, 'SUPPORT_USERNAME')
    assert support == '@support'
    
    enabled = await BotConfigService.is_feature_enabled(new_session, bot_id, 'card_to_card')
    assert enabled == True
```

### Test 3: Rollback on Error

```python
# tests/test_transaction_rollback.py
import pytest
from app.services.bot_config_service import BotConfigService

@pytest.mark.asyncio
async def test_rollback_on_error(db_session):
    """Test that transaction rolls back on error"""
    bot_id = 999
    
    try:
        async with db_session.begin():
            await BotConfigService.set_config(
                db_session, bot_id, 'DEFAULT_LANGUAGE', 'fa',
                commit=False
            )
            # Simulate error
            raise ValueError("Test error")
    except ValueError:
        pass
    
    # Verify nothing persisted
    new_session = get_new_db_session()
    lang = await BotConfigService.get_config(new_session, bot_id, 'DEFAULT_LANGUAGE')
    assert lang is None  # Should be rolled back
```

---

## 📝 Notes

1. **Backward Compatibility**: همه تغییرات backward compatible هستند (default `commit=True`)
2. **Gradual Migration**: می‌توان به تدریج handlers را update کرد
3. **Testing**: حتماً قبل از deploy تست کنید
4. **Documentation**: تمام functions باید document شوند

---

**اولویت:** 🔴 HIGH  
**زمان تخمینی:** 2-3 ساعت برای refactoring + 2-3 ساعت برای testing

