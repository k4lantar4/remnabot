# Telegram Bot Flows Overview

This document provides a high-level, **feature-centric** map of how the Telegram bot (aiogram) handles
user and admin interactions. It connects:

- Incoming updates (commands, text, buttons)
- aiogram middlewares and handlers
- Business services
- Database and external APIs
- Outgoing replies and keyboards

It serves as an entry point into the more detailed maps:

- `docs/telegram-keyboards-map.md` — button & keyboard centric view
- `docs/telegram-fsm-flows.md` — FSM/state centric view
- `docs/telegram-feature-flows.md` — end‑to‑end feature flows

---

## Layers & Global Request Flow

The bot uses a layered architecture (Handlers → Services → Database/External APIs).

### Complete Request Flow Diagram

```mermaid
flowchart TD
  telegramUpdate["Telegram Update<br/>(Message/CallbackQuery)"]
    --> middleware1["AuthMiddleware<br/>(Admin check)"]
  middleware1 --> middleware2["LoggingMiddleware<br/>(Request logging)"]
  middleware2 --> middleware3["ThrottlingMiddleware<br/>(Rate limiting)"]
  middleware3 --> middleware4["SubscriptionStatusMiddleware<br/>(Subscription check)"]
  middleware4 --> middleware5["MaintenanceMiddleware<br/>(Maintenance mode)"]
  middleware5 --> middleware6["ChannelCheckerMiddleware<br/>(Channel subscription)"]
  middleware6 --> middleware7["DisplayNameRestrictionMiddleware<br/>(Name validation)"]
  middleware7 --> middleware8["GlobalErrorMiddleware<br/>(Error handling)"]
  
  middleware8 --> handlerRouter["Handler Router<br/>(Command/Text/Callback filters)"]
  
  handlerRouter -->|Command| commandHandler["Command Handler<br/>(e.g., /start)"]
  handlerRouter -->|Text| textHandler["Text Handler<br/>(FSM state-based)"]
  handlerRouter -->|Callback| callbackHandler["Callback Handler<br/>(callback_data matching)"]
  
  commandHandler --> handlerLogic["Handler Logic<br/>(app/handlers/*.py)"]
  textHandler --> handlerLogic
  callbackHandler --> handlerLogic
  
  handlerLogic --> fsmState{FSM State?}
  fsmState -->|Yes| stateUpdate["Update FSM State<br/>(Redis/Memory)"]
  fsmState -->|No| serviceCall["Call Business Service"]
  stateUpdate --> serviceCall
  
  serviceCall --> service1["SubscriptionService"]
  serviceCall --> service2["PaymentService"]
  serviceCall --> service3["UserService"]
  serviceCall --> service4["RemnaWaveService"]
  serviceCall --> service5["Other Services..."]
  
  service1 --> crud1["CRUD Operations<br/>(app/database/crud/*)"]
  service2 --> crud2["CRUD Operations"]
  service3 --> crud3["CRUD Operations"]
  service4 --> external1["RemnaWave API<br/>(app/external/remnawave_api.py)"]
  service5 --> crud4["CRUD Operations"]
  
  crud1 --> models1["Database Models<br/>(app/database/models.py)"]
  crud2 --> models2["Database Models"]
  crud3 --> models3["Database Models"]
  crud4 --> models4["Database Models"]
  
  service2 --> external2["Payment Provider APIs<br/>(YooKassa, CryptoBot, etc.)"]
  external2 --> webhook["Webhook Handlers<br/>(app/webserver/payments.py)"]
  webhook --> service2
  
  models1 --> db["PostgreSQL/SQLite<br/>(via SQLAlchemy)"]
  models2 --> db
  models3 --> db
  models4 --> db
  
  service1 --> keyboardBuilder["Keyboard Builder<br/>(app/keyboards/*.py)"]
  service2 --> keyboardBuilder
  service3 --> keyboardBuilder
  
  keyboardBuilder --> replyMessage["Build Reply Message<br/>(Text + Keyboards)"]
  replyMessage --> telegramAPI["Telegram Bot API<br/>(Send message)"]
  telegramAPI --> user["User receives response"]
  
  style telegramUpdate fill:#e1f5ff
  style user fill:#c8e6c9
  style serviceCall fill:#fff9c4
  style db fill:#ffccbc
```

### Key Directories (Telegram-related)

- `app/bot.py` – bot & dispatcher setup, handler registration, middleware wiring.
- `app/states.py` – FSM state classes for registration, subscription, balance, admin flows, etc.
- `app/handlers/` – user, admin, subscription, balance, support, ticket and webhook handlers.
- `app/keyboards/` – reply, inline and admin keyboards.
- `app/services/` – business logic services (subscription, payments, users, referrals, etc.).
- `app/database/` – SQLAlchemy models and CRUD helpers.
- `app/external/` – payment providers and RemnaWave integration.

---

## Feature Buckets (Top-Level)

All bot capabilities can be grouped into the following **feature buckets**.
Each bucket will be detailed in `docs/telegram-feature-flows.md`.

- **Registration & Onboarding**
  - `/start` flow, language selection, first subscription state.
- **Main Menu & Navigation**
  - Main reply keyboard for users, navigation to other features.
- **Subscription Purchase & Management**
  - Subscription purchase wizard (countries, devices, traffic, period, autopay).
  - Subscription settings updates, trial activation, renewals.
- **Balance & Payments**
  - Balance top-up, multiple payment providers (YooKassa, CryptoBot, Heleket, MulenPay, Pal24, Stars, etc.).
- **Support & Tickets**
  - Contact support, create and manage tickets (user and admin sides).
- **Referral Program**
  - Referral link generation, referral stats and rewards.
- **Admin Panel**
  - All admin‑only flows (users, subscriptions, promo, campaigns, monitoring, servers, pricing, rules, reports, logs, etc.).

Each of these buckets will have:

- Trigger map (commands and buttons).
- FSM map (if applicable).
- Handler & service dependencies.
- External systems involved.

---

## FSM & State Usage – Overview

FSM state classes are defined in `app/states.py` and used throughout handlers
to model multi‑step flows (registration, subscription purchase, admin wizards, etc.).

Details per state class and per feature are documented in:

- `docs/telegram-fsm-flows.md` – state machine diagrams and handler mappings.

---

## How to Use These Docs

- Start here to locate **which feature bucket** a change belongs to.
- Jump to:
  - `docs/telegram-keyboards-map.md` to find which button triggers which handler/feature.
  - `docs/telegram-fsm-flows.md` to see which states and steps are involved.
  - `docs/telegram-feature-flows.md` to understand end‑to‑end data & service dependencies.

Keeping these documents in sync with code helps avoid **hidden couplings** and
reduces the risk of introducing technical debt when adding or modifying features.
