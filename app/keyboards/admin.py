from typing import List, Optional, Tuple, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.localization.texts import get_texts


def _t(texts, key: str, default: str) -> str:
    """Helper for localized button labels with fallbacks."""
    return texts.t(key, default)


def get_admin_main_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_USERS_SUBSCRIPTIONS", "👥 Users / Subscriptions"),
                callback_data="admin_submenu_users",
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_SERVERS", "🌐 Servers"),
                callback_data="admin_servers",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_PRICING", "💰 Pricing"),
                callback_data="admin_pricing",
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_PROMO_STATS", "💰 Promo codes / Stats"),
                callback_data="admin_submenu_promo",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_SUPPORT", "🛟 Support"),
                callback_data="admin_submenu_support",
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_MESSAGES", "📨 Messages"),
                callback_data="admin_submenu_communications",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_SETTINGS", "⚙️ Settings"),
                callback_data="admin_submenu_settings",
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_SYSTEM", "🛠️ System"),
                callback_data="admin_submenu_system",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_TENANT_BOTS", "🤖 Tenant Bots"),
                callback_data="admin_tenant_bots_menu",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_TRIALS", "🧪 Trials"),
                callback_data="admin_trials",
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAIN_PAYMENTS", "💳 Top-ups"),
                callback_data="admin_payments",
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="back_to_menu")]
    ])


def get_admin_users_submenu_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.ADMIN_USERS, callback_data="admin_users"),
            InlineKeyboardButton(text=texts.ADMIN_REFERRALS, callback_data="admin_referrals")
        ],
        [
            InlineKeyboardButton(text=texts.ADMIN_SUBSCRIPTIONS, callback_data="admin_subscriptions")
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")
        ]
    ])


def get_admin_promo_submenu_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.ADMIN_PROMOCODES, callback_data="admin_promocodes"),
            InlineKeyboardButton(text=texts.ADMIN_STATISTICS, callback_data="admin_statistics")
        ],
        [
            InlineKeyboardButton(text=texts.ADMIN_CAMPAIGNS, callback_data="admin_campaigns")
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CONTESTS", "🏆 Конкурсы"),
                callback_data="admin_contests",
            )
        ],
        [
            InlineKeyboardButton(text=texts.ADMIN_PROMO_GROUPS, callback_data="admin_promo_groups")
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")
        ]
    ])


def get_admin_communications_submenu_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.ADMIN_MESSAGES, callback_data="admin_messages")
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_COMMUNICATIONS_POLLS", "🗳️ Polls"),
                callback_data="admin_polls",
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_COMMUNICATIONS_PROMO_OFFERS", "🎯 Promo offers"),
                callback_data="admin_promo_offers"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_COMMUNICATIONS_WELCOME_TEXT", "👋 Welcome message"),
                callback_data="welcome_text_panel"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_COMMUNICATIONS_MENU_MESSAGES", "📢 Menu messages"),
                callback_data="user_messages_panel"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")
        ]
    ])


def get_admin_support_submenu_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SUPPORT_TICKETS", "🎫 Support tickets"),
                callback_data="admin_tickets"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SUPPORT_AUDIT", "🧾 Moderator audit"),
                callback_data="admin_support_audit"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SUPPORT_SETTINGS", "🛟 Support settings"),
                callback_data="admin_support_settings"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")
        ]
    ])


def get_admin_settings_submenu_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.ADMIN_REMNAWAVE, callback_data="admin_remnawave"),
            InlineKeyboardButton(text=texts.ADMIN_MONITORING, callback_data="admin_monitoring")
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SETTINGS_BOT_CONFIG", "🧩 Bot configuration"),
                callback_data="admin_bot_config"
            ),
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_MONITORING_SETTINGS", "⚙️ Monitoring settings"),
                callback_data="admin_mon_settings"
            )
        ],
        [
            InlineKeyboardButton(text=texts.ADMIN_RULES, callback_data="admin_rules"),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SETTINGS_MAINTENANCE", "🔧 Maintenance"),
                callback_data="maintenance_panel"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SETTINGS_PRIVACY_POLICY", "🛡️ Privacy policy"),
                callback_data="admin_privacy_policy",
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SETTINGS_PUBLIC_OFFER", "📄 Public offer"),
                callback_data="admin_public_offer",
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SETTINGS_FAQ", "❓ FAQ"),
                callback_data="admin_faq",
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")
        ]
    ])


def get_admin_system_submenu_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYSTEM_UPDATES", "📄 Updates"),
                callback_data="admin_updates"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYSTEM_BACKUPS", "🗄️ Backups"),
                callback_data="backup_panel"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYSTEM_LOGS", "🧾 Logs"),
                callback_data="admin_system_logs"
            )
        ],
        [InlineKeyboardButton(text=texts.t("ADMIN_REPORTS", "📊 Reports"), callback_data="admin_reports")],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")
        ]
    ])


def get_admin_trials_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_TRIALS_RESET_BUTTON", "♻️ Reset all trials"),
                callback_data="admin_trials_reset",
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")],
    ])


def get_admin_reports_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_REPORTS_PREVIOUS_DAY", "📆 Yesterday"),
                callback_data="admin_reports_daily"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_REPORTS_LAST_WEEK", "🗓️ Last week"),
                callback_data="admin_reports_weekly"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_REPORTS_LAST_MONTH", "📅 Last month"),
                callback_data="admin_reports_monthly"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")]
    ])


def get_admin_report_result_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.t("REPORT_CLOSE", "❌ Close"), callback_data="admin_close_report")]
    ])


def get_admin_users_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_ALL", "👥 All users"),
                callback_data="admin_users_list"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_SEARCH", "🔍 Search"),
                callback_data="admin_users_search"
            )
        ],
        [
            InlineKeyboardButton(text=texts.ADMIN_STATISTICS, callback_data="admin_users_stats"),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_INACTIVE", "🗑️ Inactive"),
                callback_data="admin_users_inactive"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_FILTERS", "⚙️ Filters"),
                callback_data="admin_users_filters"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_BLACKLIST", "🔐 Черный список"),
                callback_data="admin_blacklist_settings"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_BULK_BAN", "🛑 Массовый бан"),
                callback_data="admin_bulk_ban_start"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_users")
        ]
    ])


def get_admin_users_filters_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_FILTER_BALANCE", "💰 By balance"),
                callback_data="admin_users_balance_filter"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_FILTER_TRAFFIC", "📶 By traffic"),
                callback_data="admin_users_traffic_filter"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_FILTER_ACTIVITY", "🕒 By activity"),
                callback_data="admin_users_activity_filter"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_FILTER_SPENDING", "💳 By spending"),
                callback_data="admin_users_spending_filter"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_FILTER_PURCHASES", "🛒 By purchases"),
                callback_data="admin_users_purchases_filter"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_FILTER_RENEW_READY", "♻️ Ready to renew"),
                callback_data="admin_users_ready_to_renew_filter"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USERS_FILTER_CAMPAIGN", "📢 By campaign"),
                callback_data="admin_users_campaign_filter"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_users")
        ]
    ])


def get_admin_subscriptions_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SUBSCRIPTIONS_ALL", "📱 All subscriptions"),
                callback_data="admin_subs_list"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SUBSCRIPTIONS_EXPIRING", "⏰ Expiring"),
                callback_data="admin_subs_expiring"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SUBSCRIPTIONS_COUNTRIES", "🌍 Manage countries"),
                callback_data="admin_subs_countries"
            )
        ],
        [
            InlineKeyboardButton(text=texts.ADMIN_STATISTICS, callback_data="admin_subs_stats")
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_users")
        ]
    ])


def get_admin_promocodes_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODES_ALL", "🎫 All promo codes"),
                callback_data="admin_promo_list"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODES_CREATE", "➕ Create"),
                callback_data="admin_promo_create"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODES_GENERAL_STATS", "📊 Overall statistics"),
                callback_data="admin_promo_general_stats"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_promo")
        ]
    ])


def get_admin_campaigns_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CAMPAIGNS_LIST", "📋 Campaign list"),
                callback_data="admin_campaigns_list"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CAMPAIGNS_CREATE", "➕ Create"),
                callback_data="admin_campaigns_create"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CAMPAIGNS_GENERAL_STATS", "📊 Overall statistics"),
                callback_data="admin_campaigns_stats"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_promo")
        ]
    ])


def get_admin_contests_root_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CONTESTS_REFERRAL", "🤝 Реферальные конкурсы"),
                    callback_data="admin_contests_referral",
                )
            ],
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CONTESTS_DAILY", "📆 Ежедневные конкурсы"),
                    callback_data="admin_contests_daily",
                )
            ],
            [
                InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_promo"),
            ],
        ]
    )


def get_admin_contests_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CONTESTS_LIST", "📋 Текущие конкурсы"),
                    callback_data="admin_contests_list",
                ),
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CONTESTS_CREATE", "➕ Новый конкурс"),
                    callback_data="admin_contests_create",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=texts.BACK,
                    callback_data="admin_contests",
                )
            ],
        ]
    )


def get_contest_mode_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CONTEST_MODE_PAID", "💳 Реферал с покупкой"),
                    callback_data="admin_contest_mode_paid",
                )
            ],
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CONTEST_MODE_REGISTERED", "🧑‍🤝‍🧑 Просто реферал"),
                    callback_data="admin_contest_mode_registered",
                )
            ],
            [
                InlineKeyboardButton(text=texts.BACK, callback_data="admin_contests_referral")
            ],
        ]
    )


def get_daily_contest_manage_keyboard(
    template_id: int,
    is_enabled: bool,
    language: str = "ru",
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    toggle_text = _t(texts, "ADMIN_CONTEST_DISABLE", "⏸️ Остановить") if is_enabled else _t(texts, "ADMIN_CONTEST_ENABLE", "▶️ Запустить")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=toggle_text, callback_data=f"admin_daily_toggle_{template_id}"),
                InlineKeyboardButton(text=_t(texts, "ADMIN_CONTEST_START_NOW", "🚀 Запустить раунд"), callback_data=f"admin_daily_start_{template_id}"),
                InlineKeyboardButton(text=_t(texts, "ADMIN_CONTEST_START_MANUAL", "🧪 Ручной старт"), callback_data=f"admin_daily_manual_{template_id}"),
            ],
            [
                InlineKeyboardButton(text=_t(texts, "ADMIN_EDIT_PRIZE", "🏅 Приз (дни)"), callback_data=f"admin_daily_edit_{template_id}_prize_days"),
                InlineKeyboardButton(text=_t(texts, "ADMIN_EDIT_MAX_WINNERS", "👥 Победителей"), callback_data=f"admin_daily_edit_{template_id}_max_winners"),
            ],
            [
                InlineKeyboardButton(text=_t(texts, "ADMIN_EDIT_ATTEMPTS", "🔁 Попытки"), callback_data=f"admin_daily_edit_{template_id}_attempts_per_user"),
                InlineKeyboardButton(text=_t(texts, "ADMIN_EDIT_TIMES", "⏰ Раундов/день"), callback_data=f"admin_daily_edit_{template_id}_times_per_day"),
            ],
            [
                InlineKeyboardButton(text=_t(texts, "ADMIN_EDIT_SCHEDULE", "🕒 Расписание"), callback_data=f"admin_daily_edit_{template_id}_schedule_times"),
                InlineKeyboardButton(text=_t(texts, "ADMIN_EDIT_COOLDOWN", "⌛ Длительность"), callback_data=f"admin_daily_edit_{template_id}_cooldown_hours"),
            ],
            [
                InlineKeyboardButton(text=_t(texts, "ADMIN_EDIT_PAYLOAD", "🧩 Payload"), callback_data=f"admin_daily_payload_{template_id}"),
            ],
            [
                InlineKeyboardButton(text=_t(texts, "ADMIN_RESET_ATTEMPTS", "🔄 Сбросить попытки"), callback_data=f"admin_daily_reset_attempts_{template_id}"),
            ],
            [
                InlineKeyboardButton(text=_t(texts, "ADMIN_CLOSE_ROUND", "❌ Закрыть раунд"), callback_data=f"admin_daily_close_{template_id}"),
            ],
            [
                InlineKeyboardButton(text=texts.BACK, callback_data="admin_contests_daily"),
            ],
        ]
    )

def get_referral_contest_manage_keyboard(
    contest_id: int,
    *,
    is_active: bool,
    can_delete: bool = False,
    language: str = "ru",
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    toggle_text = (
        _t(texts, "ADMIN_CONTEST_DISABLE", "⏸️ Остановить")
        if is_active
        else _t(texts, "ADMIN_CONTEST_ENABLE", "▶️ Запустить")
    )

    rows = [
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CONTEST_LEADERBOARD", "📊 Лидеры"),
                callback_data=f"admin_contest_leaderboard_{contest_id}",
            ),
            InlineKeyboardButton(
                text=toggle_text,
                callback_data=f"admin_contest_toggle_{contest_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CONTEST_EDIT_SUMMARY_TIMES", "🕒 Итоги в день"),
                callback_data=f"admin_contest_edit_times_{contest_id}",
            ),
        ],
    ]

    if can_delete:
        rows.append(
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CONTEST_DELETE", "🗑 Удалить"),
                    callback_data=f"admin_contest_delete_{contest_id}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BACK_TO_LIST", "⬅️ К списку"),
                callback_data="admin_contests_list",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_campaign_management_keyboard(
    campaign_id: int, is_active: bool, language: str = "ru"
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    status_text = (
        _t(texts, "ADMIN_CAMPAIGN_DISABLE", "🔴 Disable")
        if is_active
        else _t(texts, "ADMIN_CAMPAIGN_ENABLE", "🟢 Enable")
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CAMPAIGN_STATS", "📊 Statistics"),
                    callback_data=f"admin_campaign_stats_{campaign_id}",
                ),
                InlineKeyboardButton(
                    text=status_text,
                    callback_data=f"admin_campaign_toggle_{campaign_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CAMPAIGN_EDIT", "✏️ Edit"),
                    callback_data=f"admin_campaign_edit_{campaign_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CAMPAIGN_DELETE", "🗑️ Delete"),
                    callback_data=f"admin_campaign_delete_{campaign_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_BACK_TO_LIST", "⬅️ Back to list"),
                    callback_data="admin_campaigns_list"
                )
            ],
        ]
    )


def get_campaign_edit_keyboard(
    campaign_id: int,
    *,
    is_balance_bonus: bool,
    language: str = "ru",
) -> InlineKeyboardMarkup:
    texts = get_texts(language)

    keyboard: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CAMPAIGN_EDIT_NAME", "✏️ Name"),
                callback_data=f"admin_campaign_edit_name_{campaign_id}",
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CAMPAIGN_EDIT_START", "🔗 Parameter"),
                callback_data=f"admin_campaign_edit_start_{campaign_id}",
            ),
        ]
    ]

    if is_balance_bonus:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=_t(texts, "ADMIN_CAMPAIGN_BONUS_BALANCE", "💰 Balance bonus"),
                    callback_data=f"admin_campaign_edit_balance_{campaign_id}",
                )
            ]
        )
    else:
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        text=_t(texts, "ADMIN_CAMPAIGN_DURATION", "📅 Duration"),
                        callback_data=f"admin_campaign_edit_sub_days_{campaign_id}",
                    ),
                    InlineKeyboardButton(
                        text=_t(texts, "ADMIN_CAMPAIGN_TRAFFIC", "🌐 Traffic"),
                        callback_data=f"admin_campaign_edit_sub_traffic_{campaign_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=_t(texts, "ADMIN_CAMPAIGN_DEVICES", "📱 Devices"),
                        callback_data=f"admin_campaign_edit_sub_devices_{campaign_id}",
                    ),
                    InlineKeyboardButton(
                        text=_t(texts, "ADMIN_CAMPAIGN_SERVERS", "🌍 Servers"),
                        callback_data=f"admin_campaign_edit_sub_servers_{campaign_id}",
                    ),
                ],
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                text=texts.BACK, callback_data=f"admin_campaign_manage_{campaign_id}"
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_campaign_bonus_type_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CAMPAIGN_BONUS_BALANCE", "💰 Balance bonus"),
                callback_data="campaign_bonus_balance"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CAMPAIGN_BONUS_SUBSCRIPTION", "📱 Subscription"),
                callback_data="campaign_bonus_subscription"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_campaigns")
        ]
    ])


def get_promocode_management_keyboard(promo_id: int, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODE_EDIT", "✏️ Edit"),
                callback_data=f"promo_edit_{promo_id}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODE_TOGGLE", "🔄 Status"),
                callback_data=f"promo_toggle_{promo_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODE_STATS", "📊 Statistics"),
                callback_data=f"promo_stats_{promo_id}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODE_DELETE", "🗑️ Delete"),
                callback_data=f"promo_delete_{promo_id}"
            )
        ],
        [
            InlineKeyboardButton(text=_t(texts, "ADMIN_BACK_TO_LIST", "⬅️ Back to list"), callback_data="admin_promo_list")
        ]
    ])


def get_admin_messages_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MESSAGES_ALL_USERS", "📨 All users"),
                callback_data="admin_msg_all"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MESSAGES_BY_SUBSCRIPTIONS", "🎯 By subscriptions"),
                callback_data="admin_msg_by_sub"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MESSAGES_BY_CRITERIA", "🔍 By criteria"),
                callback_data="admin_msg_custom"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MESSAGES_HISTORY", "📋 History"),
                callback_data="admin_msg_history"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_communications")
        ]
    ])


def get_admin_monitoring_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_START", "▶️ Start"),
                callback_data="admin_mon_start"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_STOP", "⏸️ Stop"),
                callback_data="admin_mon_stop"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_STATUS", "📊 Status"),
                callback_data="admin_mon_status"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_LOGS", "📋 Logs"),
                callback_data="admin_mon_logs"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_SETTINGS_BUTTON", "⚙️ Settings"),
                callback_data="admin_mon_settings"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_settings")
        ]
    ])


def get_admin_remnawave_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_REMNAWAVE_SYSTEM_STATS", "📊 System statistics"),
                callback_data="admin_rw_system"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_REMNAWAVE_MANAGE_NODES", "🖥️ Manage nodes"),
                callback_data="admin_rw_nodes"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_REMNAWAVE_SYNC", "🔄 Sync"),
                callback_data="admin_rw_sync"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_REMNAWAVE_MANAGE_SQUADS", "🌐 Manage squads"),
                callback_data="admin_rw_squads"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_REMNAWAVE_MIGRATION", "🚚 Migration"),
                callback_data="admin_rw_migration"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_REMNAWAVE_TRAFFIC", "📈 Traffic"),
                callback_data="admin_rw_traffic"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_settings")
        ]
    ])


def get_admin_statistics_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_STATS_USERS", "👥 Users"),
                callback_data="admin_stats_users"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_STATS_SUBSCRIPTIONS", "📱 Subscriptions"),
                callback_data="admin_stats_subs"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_STATS_REVENUE", "💰 Revenue"),
                callback_data="admin_stats_revenue"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_STATS_REFERRALS", "🤝 Referrals"),
                callback_data="admin_stats_referrals"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_STATS_SUMMARY", "📊 Summary"),
                callback_data="admin_stats_summary"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_promo")
        ]
    ])


def get_user_management_keyboard(user_id: int, user_status: str, language: str = "ru", back_callback: str = "admin_users_list") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    keyboard = [
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_BALANCE", "💰 Balance"),
                callback_data=f"admin_user_balance_{user_id}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_SUBSCRIPTION_SETTINGS", "📱 Subscription & settings"),
                callback_data=f"admin_user_subscription_{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.ADMIN_USER_PROMO_GROUP_BUTTON,
                callback_data=f"admin_user_promo_group_{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_REFERRALS_BUTTON", "🤝 Referrals"),
                callback_data=f"admin_user_referrals_{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_STATISTICS", "📊 Statistics"),
                callback_data=f"admin_user_statistics_{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_TRANSACTIONS", "📋 Transactions"),
                callback_data=f"admin_user_transactions_{user_id}"
            )
        ]
    ]

    keyboard.append([
        InlineKeyboardButton(
            text=_t(texts, "ADMIN_USER_SEND_MESSAGE", "✉️ Send message"),
            callback_data=f"admin_user_send_message_{user_id}"
        )
    ])

    if user_status == "active":
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_BLOCK", "🚫 Block"),
                callback_data=f"admin_user_block_{user_id}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_DELETE", "🗑️ Delete"),
                callback_data=f"admin_user_delete_{user_id}"
            )
        ])
    elif user_status == "blocked":
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_UNBLOCK", "✅ Unblock"),
                callback_data=f"admin_user_unblock_{user_id}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_DELETE", "🗑️ Delete"),
                callback_data=f"admin_user_delete_{user_id}"
            )
        ])
    elif user_status == "deleted":
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_USER_ALREADY_DELETED", "❌ User deleted"),
                callback_data="noop"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text=texts.BACK, callback_data=back_callback)
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_promo_group_keyboard(
    promo_groups: List[Tuple[Any, int]],
    user_id: int,
    current_group_ids,  # Can be Optional[int] or List[int]
    language: str = "ru"
) -> InlineKeyboardMarkup:
    texts = get_texts(language)

    # Ensure current_group_ids is a list
    if current_group_ids is None:
        current_group_ids = []
    elif isinstance(current_group_ids, int):
        current_group_ids = [current_group_ids]

    keyboard: List[List[InlineKeyboardButton]] = []

    for group, members_count in promo_groups:
        # Check if user has this group
        has_group = group.id in current_group_ids
        prefix = "✅" if has_group else "👥"
        count_text = f" ({members_count})" if members_count else ""
        keyboard.append([
            InlineKeyboardButton(
                text=f"{prefix} {group.name}{count_text}",
                callback_data=f"admin_user_promo_group_toggle_{user_id}_{group.id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text=texts.ADMIN_USER_PROMO_GROUP_BACK,
            callback_data=f"admin_user_manage_{user_id}"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(
    confirm_action: str,
    cancel_action: str = "admin_panel",
    language: str = "ru"
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.YES, callback_data=confirm_action),
            InlineKeyboardButton(text=texts.NO, callback_data=cancel_action)
        ]
    ])


def get_promocode_type_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODE_TYPE_BALANCE", "💰 Balance"),
                callback_data="promo_type_balance"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODE_TYPE_DAYS", "📅 Subscription days"),
                callback_data="promo_type_days"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODE_TYPE_TRIAL", "🎁 Trial"),
                callback_data="promo_type_trial"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODE_TYPE_PROMO_GROUP", "🏷️ Promo group"),
                callback_data="promo_type_group"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_promocodes")
        ]
    ])


def get_promocode_list_keyboard(promocodes: list, page: int, total_pages: int, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []
    
    for promo in promocodes:
        status_emoji = "✅" if promo.is_active else "❌"
        type_emoji = {"balance": "💰", "subscription_days": "📅", "trial_subscription": "🎁"}.get(promo.type, "🎫")
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status_emoji} {type_emoji} {promo.code}",
                callback_data=f"promo_manage_{promo.id}"
            )
        ])
    
    if total_pages > 1:
        pagination_row = []
        
        if page > 1:
            pagination_row.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"admin_promo_list_page_{page - 1}")
            )
        
        pagination_row.append(
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="current_page")
        )
        
        if page < total_pages:
            pagination_row.append(
                InlineKeyboardButton(text="➡️", callback_data=f"admin_promo_list_page_{page + 1}")
            )
        
        keyboard.append(pagination_row)
    
    keyboard.extend([
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PROMOCODES_CREATE", "➕ Create"),
                callback_data="admin_promo_create"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_promocodes")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_target_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_TARGET_ALL", "👥 Everyone"),
                callback_data="broadcast_all"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_TARGET_ACTIVE", "📱 With subscription"),
                callback_data="broadcast_active"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_TARGET_TRIAL", "🎁 Trial"),
                callback_data="broadcast_trial"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_TARGET_NO_SUB", "❌ No subscription"),
                callback_data="broadcast_no_sub"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_TARGET_EXPIRING", "⏰ Expiring"),
                callback_data="broadcast_expiring"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_TARGET_EXPIRED", "🔚 Expired"),
                callback_data="broadcast_expired"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_TARGET_ACTIVE_ZERO", "🧊 Active 0 GB"),
                callback_data="broadcast_active_zero"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_TARGET_TRIAL_ZERO", "🥶 Trial 0 GB"),
                callback_data="broadcast_trial_zero"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_messages")]
    ])


def get_custom_criteria_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CRITERIA_TODAY", "📅 Today"),
                callback_data="criteria_today"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CRITERIA_WEEK", "📅 Last 7 days"),
                callback_data="criteria_week"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CRITERIA_MONTH", "📅 Last month"),
                callback_data="criteria_month"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CRITERIA_ACTIVE_TODAY", "⚡ Active today"),
                callback_data="criteria_active_today"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CRITERIA_INACTIVE_WEEK", "💤 Inactive 7+ days"),
                callback_data="criteria_inactive_week"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CRITERIA_INACTIVE_MONTH", "💤 Inactive 30+ days"),
                callback_data="criteria_inactive_month"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CRITERIA_REFERRALS", "🤝 Via referrals"),
                callback_data="criteria_referrals"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CRITERIA_PROMOCODES", "🎫 Used promo codes"),
                callback_data="criteria_promocodes"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CRITERIA_DIRECT", "🎯 Direct registration"),
                callback_data="criteria_direct"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_messages")]
    ])


def get_broadcast_history_keyboard(page: int, total_pages: int, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []
    
    if total_pages > 1:
        pagination_row = []
        
        if page > 1:
            pagination_row.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"admin_msg_history_page_{page - 1}")
            )
        
        pagination_row.append(
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="current_page")
        )
        
        if page < total_pages:
            pagination_row.append(
                InlineKeyboardButton(text="➡️", callback_data=f"admin_msg_history_page_{page + 1}")
            )
        
        keyboard.append(pagination_row)
    
    keyboard.extend([
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_HISTORY_REFRESH", "🔄 Refresh"),
                callback_data="admin_msg_history"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_messages")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_sync_options_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = [
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_FULL", "🔄 Full sync"),
                callback_data="sync_all_users"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_TO_PANEL", "⬆️ Sync to panel"),
                callback_data="sync_to_panel"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_ONLY_NEW", "🆕 New only"),
                callback_data="sync_new_users"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_UPDATE", "📈 Update data"),
                callback_data="sync_update_data"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_VALIDATE", "🔍 Validate"),
                callback_data="sync_validate"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_CLEANUP", "🧹 Cleanup"),
                callback_data="sync_cleanup"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_RECOMMENDATIONS", "💡 Recommendations"),
                callback_data="sync_recommendations"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_remnawave")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_sync_confirmation_keyboard(sync_type: str, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = [
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_CONFIRM", "✅ Confirm"),
                callback_data=f"confirm_{sync_type}"
            )
        ],
        [InlineKeyboardButton(text=_t(texts, "ADMIN_CANCEL", "❌ Cancel"), callback_data="admin_rw_sync")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_sync_result_keyboard(sync_type: str, has_errors: bool = False, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []

    if has_errors:
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_RETRY", "🔄 Retry"),
                callback_data=f"sync_{sync_type}"
            )
        ])

    if sync_type != "all_users":
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_FULL", "🔄 Full sync"),
                callback_data="sync_all_users"
            )
        ])

    keyboard.extend([
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_STATS_BUTTON", "📊 Statistics"),
                callback_data="admin_rw_system"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_VALIDATE", "🔍 Validate"),
                callback_data="sync_validate"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_BACK", "⬅️ Back to sync"),
                callback_data="admin_rw_sync"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"),
                callback_data="admin_remnawave"
            )
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)



def get_period_selection_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PERIOD_TODAY", "📅 Today"),
                callback_data="period_today"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PERIOD_YESTERDAY", "📅 Yesterday"),
                callback_data="period_yesterday"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PERIOD_WEEK", "📅 Week"),
                callback_data="period_week"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PERIOD_MONTH", "📅 Month"),
                callback_data="period_month"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_PERIOD_ALL", "📅 All time"),
                callback_data="period_all"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_statistics")]
    ])


def get_node_management_keyboard(node_uuid: str, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_NODE_ENABLE", "▶️ Enable"),
                callback_data=f"node_enable_{node_uuid}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_NODE_DISABLE", "⏸️ Disable"),
                callback_data=f"node_disable_{node_uuid}"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_NODE_RESTART", "🔄 Restart"),
                callback_data=f"node_restart_{node_uuid}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_NODE_STATS", "📊 Statistics"),
                callback_data=f"node_stats_{node_uuid}"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_rw_nodes")]
    ])

def get_squad_management_keyboard(squad_uuid: str, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SQUAD_ADD_ALL", "👥 Add all users"),
                callback_data=f"squad_add_users_{squad_uuid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SQUAD_REMOVE_ALL", "❌ Remove all users"),
                callback_data=f"squad_remove_users_{squad_uuid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SQUAD_EDIT", "✏️ Edit"),
                callback_data=f"squad_edit_{squad_uuid}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SQUAD_DELETE", "🗑️ Delete squad"),
                callback_data=f"squad_delete_{squad_uuid}"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_rw_squads")]
    ])

def get_squad_edit_keyboard(squad_uuid: str, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SQUAD_EDIT_INBOUNDS", "🔧 Edit inbounds"),
                callback_data=f"squad_edit_inbounds_{squad_uuid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SQUAD_RENAME", "✏️ Rename"),
                callback_data=f"squad_rename_{squad_uuid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BACK_TO_SQUADS", "⬅️ Back to squads"),
                callback_data=f"admin_squad_manage_{squad_uuid}"
            )
        ]
    ])

def get_monitoring_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_START", "▶️ Start"),
                callback_data="admin_mon_start"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_STOP_HARD", "⏹️ Stop"),
                callback_data="admin_mon_stop"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_FORCE_CHECK", "🔄 Force check"),
                callback_data="admin_mon_force_check"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_LOGS", "📋 Logs"),
                callback_data="admin_mon_logs"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_TEST_NOTIFICATIONS", "🧪 Test notifications"),
                callback_data="admin_mon_test_notifications"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_STATISTICS", "📊 Statistics"),
                callback_data="admin_mon_statistics"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BACK_TO_ADMIN", "⬅️ Back to admin"),
                callback_data="admin_panel"
            )
        ]
    ])

def get_monitoring_logs_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_HISTORY_REFRESH", "🔄 Refresh"),
                callback_data="admin_mon_logs"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_CLEAR_OLD", "🗑️ Clear old"),
                callback_data="admin_mon_clear_logs"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_monitoring")]
    ])

def get_monitoring_logs_navigation_keyboard(
    current_page: int,
    total_pages: int,
    has_logs: bool = True,
    language: str = "ru"
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []
    
    if total_pages > 1:
        nav_row = []
        
        if current_page > 1:
            nav_row.append(InlineKeyboardButton(
                text="⬅️", 
                callback_data=f"admin_mon_logs_page_{current_page - 1}"
            ))
        
        nav_row.append(InlineKeyboardButton(
            text=f"{current_page}/{total_pages}", 
            callback_data="current_page_info"
        ))
        
        if current_page < total_pages:
            nav_row.append(InlineKeyboardButton(
                text="➡️", 
                callback_data=f"admin_mon_logs_page_{current_page + 1}"
            ))
        
        keyboard.append(nav_row)
    
    management_row = []
    
    refresh_button = InlineKeyboardButton(
        text=_t(texts, "ADMIN_HISTORY_REFRESH", "🔄 Refresh"),
        callback_data="admin_mon_logs"
    )

    if has_logs:
        management_row.extend([
            refresh_button,
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_CLEAR", "🗑️ Clear"),
                callback_data="admin_mon_clear_logs"
            )
        ])
    else:
        management_row.append(refresh_button)
    
    keyboard.append(management_row)
    
    keyboard.append([
        InlineKeyboardButton(
            text=_t(texts, "ADMIN_BACK_TO_MONITORING", "⬅️ Back to monitoring"),
            callback_data="admin_monitoring"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_log_detail_keyboard(log_id: int, current_page: int = 1, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_DELETE_LOG", "🗑️ Delete this log"),
                callback_data=f"admin_mon_delete_log_{log_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_BACK_TO_LOGS", "⬅️ Back to log list"),
                callback_data=f"admin_mon_logs_page_{current_page}"
            )
        ]
    ])


def get_monitoring_clear_confirm_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_CONFIRM_CLEAR", "✅ Yes, clear"),
                callback_data="admin_mon_clear_logs_confirm"
            ),
            InlineKeyboardButton(text=_t(texts, "ADMIN_CANCEL", "❌ Cancel"), callback_data="admin_mon_logs")
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_CLEAR_ALL", "🗑️ Clear ALL logs"),
                callback_data="admin_mon_clear_all_logs"
            )
        ]
    ])

def get_monitoring_status_keyboard(
    is_running: bool,
    last_check_ago_minutes: int = 0,
    language: str = "ru"
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []

    control_row = []
    if is_running:
        control_row.extend([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_STOP_HARD", "⏹️ Stop"),
                callback_data="admin_mon_stop"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_RESTART", "🔄 Restart"),
                callback_data="admin_mon_restart"
            )
        ])
    else:
        control_row.append(
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_START", "▶️ Start"),
                callback_data="admin_mon_start"
            )
        )

    keyboard.append(control_row)

    monitoring_row = []

    if not is_running or last_check_ago_minutes > 10:
        monitoring_row.append(
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_FORCE_CHECK", "⚡ Urgent check"),
                callback_data="admin_mon_force_check"
            )
        )
    else:
        monitoring_row.append(
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_CHECK_NOW", "🔄 Check now"),
                callback_data="admin_mon_force_check"
            )
        )

    keyboard.append(monitoring_row)

    info_row = [
        InlineKeyboardButton(text=_t(texts, "ADMIN_MONITORING_LOGS", "📋 Logs"), callback_data="admin_mon_logs"),
        InlineKeyboardButton(
            text=_t(texts, "ADMIN_MONITORING_STATISTICS", "📊 Statistics"),
            callback_data="admin_mon_statistics"
        )
    ]
    keyboard.append(info_row)

    test_row = [
        InlineKeyboardButton(
            text=_t(texts, "ADMIN_MONITORING_TEST_NOTIFICATIONS", "🧪 Test notifications"),
            callback_data="admin_mon_test_notifications"
        )
    ]
    keyboard.append(test_row)

    keyboard.append([
        InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_settings")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_monitoring_settings_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_SET_INTERVAL", "⏱️ Check interval"),
                callback_data="admin_mon_set_interval"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_NOTIFICATIONS", "🔔 Notifications"),
                callback_data="admin_mon_toggle_notifications"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_AUTOPAY_SETTINGS", "💳 Auto-pay settings"),
                callback_data="admin_mon_autopay_settings"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_AUTO_CLEANUP", "🧹 Auto-clean logs"),
                callback_data="admin_mon_auto_cleanup"
            )
        ],
        [InlineKeyboardButton(text=_t(texts, "ADMIN_BACK_TO_MONITORING", "⬅️ Back to monitoring"), callback_data="admin_monitoring")]
    ])


def get_log_type_filter_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_FILTER_SUCCESS", "✅ Success"),
                callback_data="admin_mon_logs_filter_success"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_FILTER_ERRORS", "❌ Errors"),
                callback_data="admin_mon_logs_filter_error"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_FILTER_CYCLES", "🔄 Monitoring cycles"),
                callback_data="admin_mon_logs_filter_cycle"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MONITORING_FILTER_AUTOPAY", "💳 Auto-payments"),
                callback_data="admin_mon_logs_filter_autopay"
            )
        ],
        [
            InlineKeyboardButton(text=_t(texts, "ADMIN_MONITORING_ALL_LOGS", "📋 All logs"), callback_data="admin_mon_logs"),
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_monitoring")
        ]
    ])

def get_admin_servers_keyboard(language: str = "ru") -> InlineKeyboardMarkup:

    texts = get_texts(language)

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVERS_LIST", "📋 Server list"),
                callback_data="admin_servers_list"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVERS_SYNC", "🔄 Sync"),
                callback_data="admin_servers_sync"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVERS_ADD", "➕ Add server"),
                callback_data="admin_servers_add"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVERS_STATS", "📊 Statistics"),
                callback_data="admin_servers_stats"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_subscriptions")]
    ])


def get_server_edit_keyboard(server_id: int, is_available: bool, language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)

    toggle_text = _t(texts, "ADMIN_SERVER_DISABLE", "❌ Disable") if is_available else _t(texts, "ADMIN_SERVER_ENABLE", "✅ Enable")

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVER_EDIT_NAME", "✏️ Name"),
                callback_data=f"admin_server_edit_name_{server_id}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVER_EDIT_PRICE", "💰 Price"),
                callback_data=f"admin_server_edit_price_{server_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVER_EDIT_COUNTRY", "🌍 Country"),
                callback_data=f"admin_server_edit_country_{server_id}"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVER_EDIT_LIMIT", "👥 Limit"),
                callback_data=f"admin_server_edit_limit_{server_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVER_EDIT_DESCRIPTION", "📝 Description"),
                callback_data=f"admin_server_edit_desc_{server_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=toggle_text,
                callback_data=f"admin_server_toggle_{server_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SERVER_DELETE", "🗑️ Delete"),
                callback_data=f"admin_server_delete_{server_id}"
            ),
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_servers_list")
        ]
    ])


def get_admin_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
    back_callback: str = "admin_panel",
    language: str = "ru"
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []
    
    if total_pages > 1:
        row = []
        
        if current_page > 1:
            row.append(InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{callback_prefix}_page_{current_page - 1}"
            ))
        
        row.append(InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="current_page"
        ))
        
        if current_page < total_pages:
            row.append(InlineKeyboardButton(
                text="➡️",
                callback_data=f"{callback_prefix}_page_{current_page + 1}"
            ))
        
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton(text=texts.BACK, callback_data=back_callback)
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_maintenance_keyboard(
    language: str,
    is_maintenance_active: bool,
    is_monitoring_active: bool,
    panel_has_issues: bool = False
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []

    if is_maintenance_active:
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAINTENANCE_DISABLE", "🟢 Disable maintenance"),
                callback_data="maintenance_toggle"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAINTENANCE_ENABLE", "🔧 Enable maintenance"),
                callback_data="maintenance_toggle"
            )
        ])

    if is_monitoring_active:
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAINTENANCE_STOP_MONITORING", "⏹️ Stop monitoring"),
                callback_data="maintenance_monitoring"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_MAINTENANCE_START_MONITORING", "▶️ Start monitoring"),
                callback_data="maintenance_monitoring"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text=_t(texts, "ADMIN_MAINTENANCE_CHECK_API", "🔍 Check API"),
            callback_data="maintenance_check_api"
        ),
        InlineKeyboardButton(
            text=_t(texts, "ADMIN_MAINTENANCE_PANEL_STATUS", "🌐 Panel status") + ("⚠️" if panel_has_issues else ""),
            callback_data="maintenance_check_panel"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            text=_t(texts, "ADMIN_MAINTENANCE_SEND_NOTIFICATION", "📢 Send notification"),
            callback_data="maintenance_manual_notify"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            text=_t(texts, "ADMIN_REFRESH", "🔄 Refresh"),
            callback_data="maintenance_panel"
        ),
        InlineKeyboardButton(
            text=texts.BACK,
            callback_data="admin_submenu_settings"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_sync_simplified_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = [
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_SYNC_FULL", "🔄 Full sync"),
                callback_data="sync_all_users"
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data="admin_remnawave")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_welcome_text_keyboard(language: str = "ru", is_enabled: bool = True) -> InlineKeyboardMarkup:

    texts = get_texts(language)
    toggle_text = _t(texts, "ADMIN_WELCOME_DISABLE", "🔴 Disable") if is_enabled else _t(texts, "ADMIN_WELCOME_ENABLE", "🟢 Enable")
    toggle_callback = "toggle_welcome_text"

    keyboard = [
        [
            InlineKeyboardButton(text=toggle_text, callback_data=toggle_callback)
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_WELCOME_EDIT", "📝 Edit text"),
                callback_data="edit_welcome_text"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_WELCOME_SHOW", "👁️ Show current"),
                callback_data="show_welcome_text"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_WELCOME_PREVIEW", "👁️ Preview"),
                callback_data="preview_welcome_text"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_WELCOME_RESET", "🔄 Reset"),
                callback_data="reset_welcome_text"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_WELCOME_HTML", "🏷️ HTML formatting"),
                callback_data="show_formatting_help"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_WELCOME_PLACEHOLDERS", "💡 Placeholders"),
                callback_data="show_placeholders_help"
            )
        ],
        [
            InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_communications")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

DEFAULT_BROADCAST_BUTTONS = ("home",)

BROADCAST_BUTTONS = {
    "balance": {
        "default_text": "💰 Top up balance",
        "text_key": "ADMIN_BROADCAST_BUTTON_BALANCE",
        "callback": "balance_topup",
    },
    "referrals": {
        "default_text": "🤝 Referrals",
        "text_key": "ADMIN_BROADCAST_BUTTON_REFERRALS",
        "callback": "menu_referrals",
    },
    "promocode": {
        "default_text": "🎫 Promo code",
        "text_key": "ADMIN_BROADCAST_BUTTON_PROMOCODE",
        "callback": "menu_promocode",
    },
    "connect": {
        "default_text": "🔗 Connect",
        "text_key": "ADMIN_BROADCAST_BUTTON_CONNECT",
        "callback": "subscription_connect",
    },
    "subscription": {
        "default_text": "📱 Subscription",
        "text_key": "ADMIN_BROADCAST_BUTTON_SUBSCRIPTION",
        "callback": "menu_subscription",
    },
    "support": {
        "default_text": "🛠️ Support",
        "text_key": "ADMIN_BROADCAST_BUTTON_SUPPORT",
        "callback": "menu_support",
    },
    "home": {
        "default_text": "🏠 Main menu",
        "text_key": "ADMIN_BROADCAST_BUTTON_HOME",
        "callback": "back_to_menu",
    },
}

BROADCAST_BUTTON_ROWS: tuple[tuple[str, ...], ...] = (
    ("balance", "referrals"),
    ("promocode", "connect"),
    ("subscription", "support"),
    ("home",),
)


def get_broadcast_button_config(language: str) -> dict[str, dict[str, str]]:
    texts = get_texts(language)
    return {
        key: {
            "text": texts.t(config["text_key"], config["default_text"]),
            "callback": config["callback"],
        }
        for key, config in BROADCAST_BUTTONS.items()
    }


def get_broadcast_button_labels(language: str) -> dict[str, str]:
    return {key: value["text"] for key, value in get_broadcast_button_config(language).items()}


def get_message_buttons_selector_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    return get_updated_message_buttons_selector_keyboard_with_media(list(DEFAULT_BROADCAST_BUTTONS), False, language)

def get_broadcast_media_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_ADD_PHOTO", "📷 Add photo"),
                callback_data="add_media_photo"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_ADD_VIDEO", "🎥 Add video"),
                callback_data="add_media_video"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_ADD_DOCUMENT", "📄 Add document"),
                callback_data="add_media_document"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_SKIP_MEDIA", "⏭️ Skip media"),
                callback_data="skip_media"
            )
        ],
        [InlineKeyboardButton(text=_t(texts, "ADMIN_CANCEL", "❌ Cancel"), callback_data="admin_messages")]
    ])

def get_media_confirm_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_USE_MEDIA", "✅ Use this media"),
                callback_data="confirm_media"
            ),
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_REPLACE_MEDIA", "🔄 Replace media"),
                callback_data="replace_media"
            )
        ],
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_NO_MEDIA", "⏭️ No media"),
                callback_data="skip_media"
            ),
            InlineKeyboardButton(text=_t(texts, "ADMIN_CANCEL", "❌ Cancel"), callback_data="admin_messages")
        ]
    ])

def get_updated_message_buttons_selector_keyboard_with_media(selected_buttons: list, has_media: bool = False, language: str = "ru") -> InlineKeyboardMarkup:
    selected_buttons = selected_buttons or []

    texts = get_texts(language)
    button_config_map = get_broadcast_button_config(language)
    keyboard: list[list[InlineKeyboardButton]] = []

    for row in BROADCAST_BUTTON_ROWS:
        row_buttons: list[InlineKeyboardButton] = []
        for button_key in row:
            button_config = button_config_map[button_key]
            base_text = button_config["text"]
            if button_key in selected_buttons:
                if " " in base_text:
                    toggle_text = f"✅ {base_text.split(' ', 1)[1]}"
                else:
                    toggle_text = f"✅ {base_text}"
            else:
                toggle_text = base_text
            row_buttons.append(
                InlineKeyboardButton(text=toggle_text, callback_data=f"btn_{button_key}")
            )
        if row_buttons:
            keyboard.append(row_buttons)

    if has_media:
        keyboard.append([
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_BROADCAST_CHANGE_MEDIA", "🖼️ Change media"),
                callback_data="change_media"
            )
        ])

    keyboard.extend([
        [
            InlineKeyboardButton(
                text=_t(texts, "ADMIN_CONTINUE", "✅ Continue"),
                callback_data="buttons_confirm"
            )
        ],
        [
            InlineKeyboardButton(text=_t(texts, "ADMIN_CANCEL", "❌ Cancel"), callback_data="admin_messages")
        ]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
