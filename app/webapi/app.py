from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.webapi.docs import add_redoc_endpoint

from .middleware import RequestLoggingMiddleware
from .routes import (
    broadcasts,
    backups,
    campaigns,
    config,
    health,
    main_menu_buttons,
    media,
    miniapp,
    partners,
    polls,
    promocodes,
    promo_groups,
    promo_offers,
    user_messages,
    welcome_texts,
    pages,
    remnawave,
    servers,
    subscription_events,
    stats,
    subscriptions,
    tickets,
    tokens,
    transactions,
    users,
    logs,
)


OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Monitoring of administrative API and related services status.",
    },
    {
        "name": "stats",
        "description": "Summary metrics for users, subscriptions and payments.",
    },
    {
        "name": "settings",
        "description": "Getting and changing bot configuration from administrative panel.",
    },
    {
        "name": "main-menu",
        "description": "Managing buttons and messages of Telegram bot main menu.",
    },
    {
        "name": "welcome-texts",
        "description": "Creating, editing and managing welcome texts.",
    },
    {
        "name": "users",
        "description": "Managing users, balance and subscription statuses.",
    },
    {
        "name": "subscriptions",
        "description": "Creating, extending and configuring bot subscriptions.",
    },
    {
        "name": "support",
        "description": "Working with support tickets, priorities and reply restrictions.",
    },
    {
        "name": "transactions",
        "description": "Financial operations and balance top-up history.",
    },
    {
        "name": "promo-groups",
        "description": "Creating and managing promo groups and their members.",
    },
    {
        "name": "servers",
        "description": (
            "Managing RemnaWave servers, their availability, promo groups and "
            "manual data synchronization."
        ),
    },
    {
        "name": "promo-offers",
        "description": "Managing promo offers, templates and event log.",
    },
    {
        "name": "logs",
        "description": (
            "Bot monitoring logs, support moderator actions and system log file."
        ),
    },
    {
        "name": "auth",
        "description": "Managing access tokens for administrative API.",
    },
    {
        "name": "remnawave",
        "description": (
            "RemnaWave integration: panel status, managing nodes, squads and data "
            "synchronization between bot and panel."
        ),
    },
    {
        "name": "media",
        "description": "Uploading files to Telegram and getting media links.",
    },
    {
        "name": "miniapp",
        "description": "Endpoint for Telegram Mini App with user subscription information.",
    },
    {
        "name": "partners",
        "description": "Viewing referral program participants, their earnings and referrals.",
    },
    {
        "name": "polls",
        "description": "Creating polls, deletion, statistics and user responses.",
    },
    {
        "name": "pages",
        "description": "Managing public page content: offer, policy, FAQ and rules.",
    },
    {
        "name": "notifications",
        "description": (
            "Getting and viewing notifications about purchases, activations and subscription extensions, "
            "balance top-ups, promocode activations, referral link clicks and "
            "user promo group changes for administrative panel."
        ),
    },
]


def create_web_api_app() -> FastAPI:
    docs_config = settings.get_web_api_docs_config()

    # Removed openapi_tags to prevent errors when generating openapi.json
    app = FastAPI(
        title=settings.WEB_API_TITLE,
        version=settings.WEB_API_VERSION,
        docs_url=docs_config.get("docs_url"),
        redoc_url=None,
        openapi_url=docs_config.get("openapi_url"),
        swagger_ui_parameters={"persistAuthorization": True},
    )

    add_redoc_endpoint(
        app,
        redoc_url=docs_config.get("redoc_url"),
        openapi_url=docs_config.get("openapi_url"),
        title=settings.WEB_API_TITLE,
    )

    allowed_origins = settings.get_web_api_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allowed_origins == ["*"] else allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.WEB_API_REQUEST_LOGGING:
        app.add_middleware(RequestLoggingMiddleware)

    app.include_router(health.router)
    app.include_router(stats.router, prefix="/stats", tags=["stats"])
    app.include_router(config.router, prefix="/settings", tags=["settings"])
    app.include_router(users.router, prefix="/users", tags=["users"])
    app.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
    app.include_router(tickets.router, prefix="/tickets", tags=["support"])
    app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
    app.include_router(promo_groups.router, prefix="/promo-groups", tags=["promo-groups"])
    app.include_router(promo_offers.router, prefix="/promo-offers", tags=["promo-offers"])
    app.include_router(servers.router, prefix="/servers", tags=["servers"])
    app.include_router(
        main_menu_buttons.router,
        prefix="/main-menu/buttons",
        tags=["main-menu"],
    )
    app.include_router(
        user_messages.router,
        prefix="/main-menu/messages",
        tags=["main-menu"],
    )
    app.include_router(
        welcome_texts.router,
        prefix="/welcome-texts",
        tags=["welcome-texts"],
    )
    app.include_router(pages.router, prefix="/pages", tags=["pages"])
    app.include_router(promocodes.router, prefix="/promo-codes", tags=["promo-codes"])
    app.include_router(broadcasts.router, prefix="/broadcasts", tags=["broadcasts"])
    app.include_router(backups.router, prefix="/backups", tags=["backups"])
    app.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
    app.include_router(tokens.router, prefix="/tokens", tags=["auth"])
    app.include_router(remnawave.router, prefix="/remnawave", tags=["remnawave"])
    app.include_router(media.router, tags=["media"])
    app.include_router(miniapp.router, prefix="/miniapp", tags=["miniapp"])
    app.include_router(partners.router, prefix="/partners", tags=["partners"])
    app.include_router(polls.router, prefix="/polls", tags=["polls"])
    app.include_router(logs.router, prefix="/logs", tags=["logs"])
    app.include_router(
        subscription_events.router,
        prefix="/notifications/subscriptions",
        tags=["notifications"],
    )

    return app
