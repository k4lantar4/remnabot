# Feature Flags & Tenant Management Design Document

**Version:** 1.0  
**Date:** 2025-12-14  
**Status:** Design Phase  
**Author:** Development Team

---

## 📋 Executive Summary

این مستند راهکار جامع برای:
1. استخراج Feature Flags از `.env.example`
2. مدیریت Feature Flags بر اساس Subscription Plans
3. Registration Flow با Activation Fee
4. Tenant Admin Dashboard برای آمار و شخصی‌سازی
5. Master Admin Control Panel

---

## 🎯 Goals

1. **Feature Flag Extraction**: استخراج خودکار قابلیت‌های قابل شخصی‌سازی از `.env.example`
2. **Plan-Based Features**: فعال/غیرفعال کردن featureها بر اساس پلن اشتراک tenant
3. **Registration with Payment**: ثبت‌نام خودکار با پرداخت اولیه (activation fee)
4. **Tenant Admin Dashboard**: پنل مدیریت برای tenant admin با دسترسی محدود
5. **Master Admin Control**: کنترل کامل feature flags توسط master admin

---

## 🏗️ Architecture Overview

### 1. Feature Flag Extraction System

#### 1.1. Feature Flag Mapper

```python
# app/services/feature_flag_extractor.py

FEATURE_FLAG_PATTERNS = {
    # Payment Gateways
    'YOOKASSA_ENABLED': 'yookassa',
    'CRYPTOBOT_ENABLED': 'cryptobot',
    'PAL24_ENABLED': 'pal24',
    'MULENPAY_ENABLED': 'mulenpay',
    'PLATEGA_ENABLED': 'platega',
    'HELEKET_ENABLED': 'heleket',
    'TRIBUTE_ENABLED': 'tribute',
    'TELEGRAM_STARS_ENABLED': 'telegram_stars',
    
    # Payment Methods
    'CARD_TO_CARD_ENABLED': 'card_to_card',
    'ZARINPAL_ENABLED': 'zarinpal',
    
    # Features
    'TRIAL_PAYMENT_ENABLED': 'trial_subscription',
    'REFERRAL_PROGRAM_ENABLED': 'referral_program',
    'AUTOPAY_ENABLED': 'auto_renewal',
    'SIMPLE_SUBSCRIPTION_ENABLED': 'simple_purchase',
    'SUPPORT_SYSTEM_MODE': 'support_tickets',
    'MINIAPP_ENABLED': 'mini_app',
    'SERVER_STATUS_MODE': 'server_status',
    'MONITORING_ENABLED': 'monitoring',
    'CONTESTS_ENABLED': 'polls',
    'CAMPAIGNS_ENABLED': 'campaigns',
}

MASTER_ONLY_CONFIGS = [
    'REMNAWAVE_API_KEY',
    'REMNAWAVE_API_URL',
    'REMNAWAVE_SECRET_KEY',
    'REMNAWAVE_USERNAME',
    'REMNAWAVE_PASSWORD',
    'BOT_TOKEN',  # Each tenant has its own
]

def extract_feature_flags_from_env() -> Dict[str, Dict]:
    """Extract all feature flags from .env.example"""
    # Parse .env.example and return feature flags with default values
    pass

def get_feature_config_template(feature_key: str) -> Dict:
    """Get configuration template for a feature"""
    # Return default config structure for each feature
    pass
```

#### 1.2. Feature Flag Categories

```python
FEATURE_CATEGORIES = {
    'payment_gateways': [
        'yookassa', 'cryptobot', 'pal24', 'mulenpay', 
        'platega', 'heleket', 'tribute', 'telegram_stars'
    ],
    'payment_methods': ['card_to_card', 'zarinpal'],
    'subscription_features': [
        'trial_subscription', 'auto_renewal', 'simple_purchase'
    ],
    'marketing': ['referral_program', 'polls', 'campaigns'],
    'support': ['support_tickets', 'support_contact'],
    'integrations': ['mini_app', 'server_status', 'monitoring'],
}
```

---

### 2. Plan-Based Feature Grants

#### 2.1. Database Schema

```sql
-- Subscription Plan Tiers for Tenants
CREATE TABLE tenant_subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,  -- 'starter', 'growth', 'enterprise'
    display_name VARCHAR(255) NOT NULL,
    monthly_price_kopeks INTEGER NOT NULL,
    activation_fee_kopeks INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Feature Grants per Plan Tier
CREATE TABLE plan_feature_grants (
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT FALSE NOT NULL,
    config_override JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (plan_tier_id, feature_key)
);

CREATE INDEX idx_plan_feature_grants_plan ON plan_feature_grants(plan_tier_id);
CREATE INDEX idx_plan_feature_grants_enabled ON plan_feature_grants(plan_tier_id, enabled) WHERE enabled = TRUE;

-- Tenant Subscriptions (to platform)
CREATE TABLE tenant_subscriptions (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id),
    
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'expired', 'cancelled'
    start_date TIMESTAMP DEFAULT NOW(),
    end_date TIMESTAMP,
    auto_renewal BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(bot_id)  -- One active subscription per tenant
);

CREATE INDEX idx_tenant_subscriptions_bot ON tenant_subscriptions(bot_id);
CREATE INDEX idx_tenant_subscriptions_status ON tenant_subscriptions(status);
```

#### 2.2. Feature Grant Service

```python
# app/services/plan_feature_service.py

async def apply_plan_features_to_tenant(
    db: AsyncSession,
    bot_id: int,
    plan_tier_id: int
) -> None:
    """Apply all enabled features from plan to tenant bot"""
    # 1. Get all feature grants for plan
    # 2. Create/update bot_feature_flags
    # 3. Apply config overrides
    pass

async def sync_tenant_features_with_plan(
    db: AsyncSession,
    bot_id: int
) -> None:
    """Sync tenant features with current subscription plan"""
    # Get tenant's current plan
    # Apply features
    pass
```

---

### 3. Registration Flow with Activation Fee

#### 3.1. Registration States (FSM)

```python
# app/states.py

class TenantRegistrationState(StatesGroup):
    waiting_for_bot_name = State()
    waiting_for_bot_token = State()
    waiting_for_language = State()
    waiting_for_support_username = State()
    waiting_for_payment_method = State()
    waiting_for_payment_confirmation = State()
    completed = State()
```

#### 3.2. Registration Handler

```python
# app/handlers/tenant/registration.py

@router.message(Command("register_tenant"))
async def start_tenant_registration(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession,
    db_user: User
):
    """Start tenant registration flow"""
    # Check if user is admin of master bot
    # Show registration form
    # Set state to waiting_for_bot_name
    pass

async def process_bot_name(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession
):
    """Process bot name input"""
    # Validate bot name
    # Store in state
    # Ask for bot token
    pass

async def process_bot_token(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession
):
    """Process Telegram bot token"""
    # Validate token with BotFather API
    # Store in state
    # Ask for language
    pass

async def process_activation_payment(
    callback: types.CallbackQuery,
    state: FSMContext,
    db: AsyncSession,
    db_user: User
):
    """Process activation fee payment"""
    # Get selected plan tier
    # Calculate activation fee
    # Create payment transaction
    # Show payment methods
    pass

async def complete_registration(
    callback: types.CallbackQuery,
    state: FSMContext,
    db: AsyncSession,
    db_user: User
):
    """Complete tenant registration"""
    # 1. Create tenant bot
    # 2. Clone master configs (filtered)
    # 3. Apply plan features
    # 4. Generate API token
    # 5. Send confirmation with API token
    pass
```

#### 3.3. Config Cloning Service

```python
# app/services/config_cloner.py

async def clone_master_config_to_tenant(
    db: AsyncSession,
    tenant_bot_id: int,
    master_bot_id: int
) -> None:
    """Clone master bot configs to tenant (excluding sensitive data)"""
    # 1. Get master bot configurations
    # 2. Filter out MASTER_ONLY_CONFIGS
    # 3. Create bot_configurations for tenant
    # 4. Set default values for tenant-specific configs
    pass
```

---

### 4. Tenant Admin Dashboard

#### 4.1. Tenant Admin Permissions

```python
# app/utils/permissions.py

TENANT_ADMIN_PERMISSIONS = {
    # View-only
    'view_statistics': True,
    'view_users': True,
    'view_subscriptions': True,
    'view_transactions': True,
    'view_traffic': True,
    
    # Management
    'manage_plans': True,  # Create/edit bot_plans
    'manage_pricing': True,  # Edit prices in bot_plans
    'manage_payment_cards': True,  # Manage tenant_payment_cards
    'manage_payment_gateways': True,  # Configure gateway settings (not enable/disable)
    
    # Restricted
    'manage_feature_flags': False,  # Only master admin
    'manage_remnawave': False,  # Only master admin
    'view_master_stats': False,  # Only master admin
}
```

#### 4.2. Tenant Admin Handlers

```python
# app/handlers/tenant/admin.py

@tenant_admin_required
async def show_tenant_dashboard(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Show tenant admin dashboard"""
    # Get bot_id from user
    # Show statistics, quick actions
    pass

@tenant_admin_required
async def show_tenant_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Show tenant-specific statistics"""
    # Users, subscriptions, revenue, traffic
    # Filtered by bot_id
    pass

@tenant_admin_required
async def show_tenant_plans(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Show and manage tenant's subscription plans"""
    # List bot_plans for this tenant
    # Allow create/edit/delete
    pass

@tenant_admin_required
async def show_tenant_traffic(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Show real-time traffic consumption"""
    # traffic_consumed_bytes, traffic_sold_bytes
    # Charts, trends
    pass

@tenant_admin_required
async def show_tenant_revenue(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Show revenue and profit statistics"""
    # Total revenue, profit, commission
    # Payment method breakdown
    pass
```

---

### 5. Master Admin Control Panel

#### 5.1. Feature Flag Management

```python
# app/handlers/master/feature_flags.py

@master_admin_required
async def show_feature_flags_menu(
    callback: types.CallbackQuery,
    db: AsyncSession
):
    """Show feature flags management menu"""
    # List all available features
    # Show which tenants have which features
    pass

@master_admin_required
async def manage_tenant_features(
    callback: types.CallbackQuery,
    db: AsyncSession,
    bot_id: int
):
    """Manage feature flags for a specific tenant"""
    # Show current features
    # Allow enable/disable based on plan
    # Override plan defaults if needed
    pass

@master_admin_required
async def manage_plan_features(
    callback: types.CallbackQuery,
    db: AsyncSession,
    plan_tier_id: int
):
    """Manage feature grants for a plan tier"""
    # Show all features
    # Enable/disable for this plan
    # Set config overrides
    pass
```

#### 5.2. Tenant Management

```python
# app/handlers/master/tenants.py

@master_admin_required
async def show_tenants_list(
    callback: types.CallbackQuery,
    db: AsyncSession
):
    """List all tenant bots"""
    # Show tenants with status, plan, stats
    pass

@master_admin_required
async def manage_tenant_subscription(
    callback: types.CallbackQuery,
    db: AsyncSession,
    bot_id: int
):
    """Manage tenant's subscription plan"""
    # Change plan tier
    # Update features automatically
    pass
```

---

## 📊 Database Models

### New Models

```python
# app/database/models.py

class TenantSubscriptionPlan(Base):
    __tablename__ = "tenant_subscription_plans"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    monthly_price_kopeks = Column(Integer, nullable=False)
    activation_fee_kopeks = Column(Integer, default=0, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    feature_grants = relationship("PlanFeatureGrant", back_populates="plan")
    tenant_subscriptions = relationship("TenantSubscription", back_populates="plan")


class PlanFeatureGrant(Base):
    __tablename__ = "plan_feature_grants"
    
    plan_tier_id = Column(Integer, ForeignKey("tenant_subscription_plans.id", ondelete="CASCADE"), primary_key=True)
    feature_key = Column(String(100), primary_key=True)
    enabled = Column(Boolean, default=False, nullable=False)
    config_override = Column(JSONB, default={})
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    plan = relationship("TenantSubscriptionPlan", back_populates="feature_grants")


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"
    
    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_tier_id = Column(Integer, ForeignKey("tenant_subscription_plans.id"), nullable=False)
    
    status = Column(String(20), default='active')
    start_date = Column(DateTime, default=func.now())
    end_date = Column(DateTime)
    auto_renewal = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    bot = relationship("Bot", backref="tenant_subscription")
    plan = relationship("TenantSubscriptionPlan", back_populates="tenant_subscriptions")
```

---

## 🔄 Workflow Diagrams

### Registration Flow

```
User → /register_tenant
  ↓
Enter Bot Name
  ↓
Enter Telegram Bot Token
  ↓
Select Language
  ↓
Enter Support Username (optional)
  ↓
Select Subscription Plan
  ↓
Pay Activation Fee
  ↓
Bot Created → API Token Generated
  ↓
Send Confirmation with API Token
```

### Feature Flag Application

```
Tenant Subscribes to Plan
  ↓
Get Plan Feature Grants
  ↓
Apply Features to bot_feature_flags
  ↓
Apply Config Overrides
  ↓
Tenant Bot Ready
```

### Tenant Admin Dashboard

```
Tenant Admin → /tenant_dashboard
  ↓
View Statistics (filtered by bot_id)
  ↓
Manage Plans (bot_plans)
  ↓
View Traffic & Revenue
  ↓
Configure Payment Methods
  ↓
(No access to feature flags)
```

---

## 🛠️ Implementation Tasks

### Phase 1: Feature Flag Extraction
- [ ] Create `feature_flag_extractor.py`
- [ ] Parse `.env.example` and extract flags
- [ ] Create feature flag mapping
- [ ] Generate default configs

### Phase 2: Plan-Based Features
- [ ] Create database tables
- [ ] Create models
- [ ] Create CRUD operations
- [ ] Create feature grant service
- [ ] Seed default plans

### Phase 3: Registration Flow
- [ ] Create FSM states
- [ ] Create registration handlers
- [ ] Integrate payment processing
- [ ] Create config cloner
- [ ] Generate API tokens

### Phase 4: Tenant Admin Dashboard
- [ ] Create permission system
- [ ] Create tenant admin handlers
- [ ] Create statistics queries (filtered)
- [ ] Create plan management UI
- [ ] Create traffic/revenue views

### Phase 5: Master Admin Panel
- [ ] Create feature flag management
- [ ] Create tenant management
- [ ] Create plan management
- [ ] Create override system

---

## 📝 Configuration Examples

### Default Plan Tiers

```python
DEFAULT_PLANS = [
    {
        'name': 'starter',
        'display_name': 'Starter Plan',
        'monthly_price_kopeks': 500000,  # 5000 RUB
        'activation_fee_kopeks': 100000,  # 1000 RUB
        'features': {
            'card_to_card': True,
            'zarinpal': True,
            'trial_subscription': True,
            'referral_program': False,
            'auto_renewal': True,
        }
    },
    {
        'name': 'growth',
        'display_name': 'Growth Plan',
        'monthly_price_kopeks': 1000000,  # 10000 RUB
        'activation_fee_kopeks': 200000,  # 2000 RUB
        'features': {
            'card_to_card': True,
            'zarinpal': True,
            'yookassa': True,
            'cryptobot': True,
            'trial_subscription': True,
            'referral_program': True,
            'auto_renewal': True,
            'simple_purchase': True,
        }
    },
    {
        'name': 'enterprise',
        'display_name': 'Enterprise Plan',
        'monthly_price_kopeks': 2000000,  # 20000 RUB
        'activation_fee_kopeks': 500000,  # 5000 RUB
        'features': {
            # All features enabled
        }
    },
]
```

---

## 🔐 Security Considerations

1. **API Token Security**: Hash tokens, show only once
2. **Permission Checks**: Strict tenant_admin_required decorator
3. **Data Isolation**: All queries filtered by bot_id
4. **Config Cloning**: Never clone sensitive master configs
5. **Feature Overrides**: Master admin only

---

## 📈 Future Enhancements

1. **Usage-Based Billing**: Track feature usage, bill accordingly
2. **Feature Analytics**: Track which features are most used
3. **A/B Testing**: Test features on subset of tenants
4. **Feature Rollout**: Gradual feature rollout
5. **Settlement System**: Automated revenue sharing

---

## ✅ Success Criteria

1. ✅ All features from `.env.example` extractable
2. ✅ Plans can grant/revoke features automatically
3. ✅ Registration flow works with payment
4. ✅ Tenant admins can manage their bots
5. ✅ Master admins have full control
6. ✅ Data isolation maintained

---

**End of Document**













