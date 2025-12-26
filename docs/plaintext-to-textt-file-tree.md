# File Tree with Line Counts

This file contains the complete tree structure of all Python files in the `app/` directory with their line counts.

Status markers: ⏳ Not Started | 🔄 In Progress | ✅ Completed

For large files (>500 lines), process in chunks and update the "Last processed line" marker.

---

```
app/
  bot.py (508 lines) - Status: ✅ Completed
  config.py (1741 lines) - Status: ✅ Completed
  states.py (202 lines) - Status: ✅ Completed
  database/
    __init__.py (23 lines) - Status: ✅ Completed
    database.py (397 lines) - Status: ✅ Completed
    models.py (1868 lines) - Status: ✅ Completed
    universal_migration.py (4397 lines) - Status: ✅ Completed
    crud/
      bot.py (149 lines) - Status: ✅ Completed

      bot_configuration.py (148 lines) - Status: ✅ Completed
      bot_feature_flag.py (149 lines) - Status: ✅ Completed
      bot_plan.py (172 lines) - Status: ✅ Completed
      campaign.py (491 lines) - Status: ✅ Completed
      card_to_card_payment.py (178 lines) - Status: ✅ Completed
      cryptobot.py (156 lines) - Status: ✅ Completed
      discount_offer.py (275 lines) - Status: ✅ Completed
      faq.py (150 lines) - Status: ✅ Completed
      heleket.py (176 lines) - Status: ✅ Completed
      init_master_bot.py (56 lines) - Status: ✅ Completed
      main_menu_button.py (145 lines) - Status: ✅ Completed
      mulenpay.py (137 lines) - Status: ✅ Completed
      notification.py (66 lines) - Status: ✅ Completed
      pal24.py (167 lines) - Status: ✅ Completed
      platega.py (156 lines) - Status: ✅ Completed
      poll.py (297 lines) - Status: ✅ Completed
      privacy_policy.py (79 lines) - Status: ✅ Completed
      promo_group.py (306 lines) - Status: ✅ Completed
      promo_offer_log.py (96 lines) - Status: ✅ Completed
      promo_offer_template.py (226 lines) - Status: ✅ Completed
      promocode.py (296 lines) - Status: ✅ Completed
      public_offer.py (79 lines) - Status: ✅ Completed
      referral.py (305 lines) - Status: ✅ Completed
      rules.py (218 lines) - Status: ✅ Completed
      server_squad.py (721 lines) - Status: ✅ Completed
      squad.py (61 lines) - Status: ✅ Completed
      subscription.py (1633 lines) - Status: ✅ Completed
      subscription_conversion.py (118 lines) - Status: ✅ Completed
      subscription_event.py (72 lines) - Status: ✅ Completed
      system_setting.py (40 lines) - Status: ✅ Completed
      tenant_payment_card.py (266 lines) - Status: ✅ Completed
      ticket.py (472 lines) - Status: ✅ Completed
      transaction.py (409 lines) - Status: ✅ Completed
      user.py (1040 lines) - Status: ✅ Completed
      user_message.py (179 lines) - Status: ✅ Completed
      user_promo_group.py (311 lines) - Status: ✅ Completed
      wata.py (168 lines) - Status: ✅ Completed
      web_api_token.py (106 lines) - Status: ✅ Completed
      welcome_text.py (286 lines) - Status: ✅ Completed
      yookassa.py (276 lines) - Status: ✅ Completed
  services/
    __init__.py (3 lines) - Status: ✅ Completed
    admin_notification_service.py (1916 lines) - Status: ✅ Completed
    backup_service.py (1556 lines) - Status: ✅ Completed
    broadcast_service.py (474 lines) - Status: ✅ Completed
    campaign_service.py (193 lines) - Status: ✅ Completed
    external_admin_service.py (160 lines) - Status: ✅ Completed
    faq_service.py (273 lines) - Status: ✅ Completed
    main_menu_button_service.py (137 lines) - Status: ✅ Completed
    maintenance_service.py (542 lines) - Status: ✅ Completed
    monitoring_service.py (1964 lines) - Status: ✅ Completed
    notification_settings_service.py (257 lines) - Status: ✅ Completed
    pal24_service.py (125 lines) - Status: ✅ Completed
    payment_service.py (148 lines) - Status: ✅ Completed
    payment_verification_service.py (559 lines) - Status: ✅ Completed
    poll_service.py (246 lines) - Status: ✅ Completed
    privacy_policy_service.py (178 lines) - Status: ✅ Completed
    promo_group_assignment.py (193 lines) - Status: ✅ Completed
    promo_offer_service.py (228 lines) - Status: ✅ Completed
    promocode_service.py (253 lines) - Status: ✅ Completed
    public_offer_service.py (359 lines) - Status: ✅ Completed
    referral_service.py (375 lines) - Status: ✅ Completed
    remnawave_service.py (2611 lines) - Status: ✅ Completed
    remnawave_sync_service.py (282 lines) - Status: ✅ Completed
    reporting_service.py (599 lines) - Status: ✅ Completed
    server_status_service.py (157 lines) - Status: ✅ Completed
    subscription_auto_purchase_service.py (621 lines) - Status: ✅ Completed
    subscription_checkout_service.py (78 lines) - Status: ✅ Completed
    subscription_purchase_service.py (1232 lines) - Status: ✅ Completed
    subscription_renewal_service.py (571 lines) - Status: ✅ Completed
    subscription_service.py (1147 lines) - Status: ✅ Completed
    support_settings_service.py (221 lines) - Status: ✅ Completed
    system_settings_service.py (1462 lines) - Status: ✅ Completed
    tenant_feature_service.py (258 lines) - Status: ✅ Completed
    trial_activation_service.py (214 lines) - Status: ✅ Completed
    user_cart_service.py (112 lines) - Status: ✅ Completed
    user_service.py (1099 lines) - Status: ✅ Completed
    version_service.py (271 lines) - Status: ✅ Completed
    web_api_token_service.py (100 lines) - Status: ✅ Completed
    payment/
      __init__.py (15 lines) - Status: ✅ Completed
      common.py (265 lines) - Status: ✅ Completed
      cryptobot.py (782 lines) - Status: ✅ Completed
      pal24.py (1036 lines) - Status: ✅ Completed
      stars.py (595 lines) - Status: ✅ Completed
  webserver/
    __init__.py (11 lines) - Status: ✅ Completed
    payments.py (667 lines) - Status: ✅ Completed
    telegram.py (359 lines) - Status: ✅ Completed
    unified_app.py (233 lines) - Status: ✅ Completed
  keyboards/
    admin.py (2036 lines) - Status: ✅ Completed
    inline.py (2545 lines) - Status: ✅ Completed
    reply.py (128 lines) - Status: ✅ Completed
  external/
    cryptobot.py (187 lines) - Status: ✅ Completed
    heleket.py (174 lines) - Status: ✅ Completed
    heleket_webhook.py (111 lines) - Status: ✅ Completed
    pal24_client.py (216 lines) - Status: ✅ Completed
    pal24_webhook.py (162 lines) - Status: ✅ Completed
    remnawave_api.py (917 lines) - Status: ✅ Completed
    telegram_stars.py (116 lines) - Status: ✅ Completed
    tribute.py (161 lines) - Status: ✅ Completed
    wata_webhook.py (262 lines) - Status: ✅ Completed
    webhook_server.py (433 lines) - Status: ✅ Completed
    yookassa_webhook.py (393 lines) - Status: ✅ Completed
  webapi/
    __init__.py (5 lines) - Status: ✅ Completed
    app.py (219 lines) - Status: ✅ Completed
    dependencies.py (59 lines) - Status: ✅ Completed
    docs.py (33 lines) - Status: ✅ Completed
    middleware.py (31 lines) - Status: ✅ Completed
    server.py (81 lines) - Status: ✅ Completed
    routes/
      __init__.py (51 lines) - Status: ✅ Completed
      backups.py (159 lines) - Status: ✅ Completed
      bots.py (283 lines) - Status: ✅ Completed
      broadcasts.py (149 lines) - Status: ✅ Completed
      campaigns.py (169 lines) - Status: ✅ Completed
      config.py (185 lines) - Status: ✅ Completed
      health.py (41 lines) - Status: ✅ Completed
      logs.py (267 lines) - Status: ✅ Completed
      main_menu_buttons.py (113 lines) - Status: ✅ Completed
      media.py (158 lines) - Status: ✅ Completed
      miniapp.py (5535 lines) - Status: ✅ Completed
      pages.py (512 lines) - Status: ✅ Completed
      partners.py (199 lines) - Status: ✅ Completed
      payment_cards.py (252 lines) - Status: ✅ Completed
      polls.py (367 lines) - Status: ✅ Completed
      promo_groups.py (180 lines) - Status: ✅ Completed
      promo_offers.py (464 lines) - Status: ✅ Completed
      promocodes.py (302 lines) - Status: ✅ Completed
      remnawave.py (561 lines) - Status: ✅ Completed
      servers.py (418 lines) - Status: ✅ Completed
      stats.py (326 lines) - Status: ✅ Completed
      subscription_events.py (139 lines) - Status: ✅ Completed
      subscriptions.py (280 lines) - Status: ✅ Completed
      tickets.py (290 lines) - Status: ✅ Completed
      tokens.py (107 lines) - Status: ✅ Completed
      transactions.py (79 lines) - Status: ✅ Completed
      user_messages.py (130 lines) - Status: ✅ Completed
      users.py (323 lines) - Status: ✅ Completed
      welcome_texts.py (124 lines) - Status: ✅ Completed
    schemas/
      __init__.py (4 lines) - Status: ✅ Completed
      backups.py (55 lines) - Status: ✅ Completed
      bots.py (110 lines) - Status: ✅ Completed
      broadcasts.py (110 lines) - Status: ✅ Completed
      campaigns.py (97 lines) - Status: ✅ Completed
      config.py (59 lines) - Status: ✅ Completed
      health.py (25 lines) - Status: ✅ Completed
      logs.py (101 lines) - Status: ✅ Completed
      main_menu_buttons.py (79 lines) - Status: ✅ Completed
      media.py (16 lines) - Status: ✅ Completed
      miniapp.py (814 lines) - Status: ✅ Completed
      pages.py (153 lines) - Status: ✅ Completed
      partners.py (75 lines) - Status: ✅ Completed
      payment_cards.py (67 lines) - Status: ✅ Completed
      polls.py (191 lines) - Status: ✅ Completed
      promo_groups.py (81 lines) - Status: ✅ Completed
      promo_offers.py (187 lines) - Status: ✅ Completed
      promocodes.py (73 lines) - Status: ✅ Completed
      remnawave.py (215 lines) - Status: ✅ Completed
      servers.py (160 lines) - Status: ✅ Completed
      subscription_events.py (58 lines) - Status: ✅ Completed
      subscriptions.py (53 lines) - Status: ✅ Completed
      tickets.py (70 lines) - Status: ✅ Completed
      tokens.py (30 lines) - Status: ✅ Completed
      transactions.py (27 lines) - Status: ✅ Completed
      user_messages.py (50 lines) - Status: ✅ Completed
      users.py (88 lines) - Status: ✅ Completed
      welcome_texts.py (50 lines) - Status: ✅ Completed
    background/
      __init__.py (1 lines) - Status: ✅ Completed
      backup_tasks.py (73 lines) - Status: ✅ Completed
  middlewares/
    __init__.py (0 lines) - Status: ✅ Completed
    auth.py (231 lines) - Status: ✅ Completed
    bot_context.py (63 lines) - Status: ✅ Completed
    channel_checker.py (366 lines) - Status: ✅ Completed
    display_name_restriction.py (165 lines) - Status: ✅ Completed
    global_error.py (148 lines) - Status: ✅ Completed
    logging.py (42 lines) - Status: ✅ Completed
    maintenance.py (45 lines) - Status: ✅ Completed
    subscription_checker.py (53 lines) - Status: ✅ Completed
    throttling.py (93 lines) - Status: ✅ Completed
  utils/
    __init__.py (13 lines) - Status: ✅ Completed
    cache.py (284 lines) - Status: ✅ Completed
    check_reg_process.py (38 lines) - Status: ✅ Completed
    currency_converter.py (121 lines) - Status: ✅ Completed
    decorators.py (170 lines) - Status: ✅ Completed
    formatters.py (233 lines) - Status: ✅ Completed
    message_patch.py (165 lines) - Status: ✅ Completed
    miniapp_buttons.py (35 lines) - Status: ✅ Completed
    pagination.py (82 lines) - Status: ✅ Completed
    payment_utils.py (244 lines) - Status: ✅ Completed
    photo_message.py (137 lines) - Status: ✅ Completed
    price_display.py (194 lines) - Status: ✅ Completed
    pricing_utils.py (326 lines) - Status: ✅ Completed
    promo_offer.py (256 lines) - Status: ✅ Completed
    security.py (28 lines) - Status: ✅ Completed
    startup_timeline.py (184 lines) - Status: ✅ Completed
    subscription_utils.py (231 lines) - Status: ✅ Completed
    telegram_webapp.py (91 lines) - Status: ✅ Completed
    timezone.py (82 lines) - Status: ✅ Completed
    user_utils.py (356 lines) - Status: ✅ Completed
    validators.py (316 lines) - Status: ✅ Completed
  localization/
    loader.py (336 lines) - Status: ✅ Completed
    texts.py (245 lines) - Status: ✅ Completed
  handlers/
    __init__.py (3 lines) - Status: ✅ Completed
    common.py (131 lines) - Status: ✅ Completed
    menu.py (1171 lines) - Status: ✅ Completed
    polls.py (255 lines) - Status: ✅ Completed
    promocode.py (131 lines) - Status: ✅ Completed
    referral.py (387 lines) - Status: ✅ Completed
    server_status.py (212 lines) - Status: ✅ Completed
    simple_subscription.py (2692 lines) - Status: ✅ Completed
    stars_payments.py (221 lines) - Status: ✅ Completed
    start.py (1903 lines) - Status: ✅ Completed
    support.py (36 lines) - Status: ✅ Completed
    tickets.py (1061 lines) - Status: ✅ Completed
    webhooks.py (93 lines) - Status: ✅ Completed
    balance/
      __init__.py (3 lines) - Status: ✅ Completed
      card_to_card.py (572 lines) - Status: ✅ Completed
      cryptobot.py (292 lines) - Status: ✅ Completed
      heleket.py (404 lines) - Status: ✅ Completed
      main.py (1031 lines) - Status: ✅ Completed
      mulenpay.py (377 lines) - Status: ✅ Completed
      pal24.py (716 lines) - Status: ✅ Completed
      platega.py (448 lines) - Status: ✅ Completed
      stars.py (136 lines) - Status: ✅ Completed
      tribute.py (30 lines) - Status: ✅ Completed
      wata.py (316 lines) - Status: ✅ Completed
      yookassa.py (628 lines) - Status: ✅ Completed
    subscription/
      __init__.py (211 lines) - Status: ✅ Completed
      autopay.py (286 lines) - Status: ✅ Completed
      common.py (500 lines) - Status: ✅ Completed
      countries.py (1023 lines) - Status: ✅ Completed
      devices.py (1384 lines) - Status: ✅ Completed
      happ.py (158 lines) - Status: ✅ Completed
      links.py (354 lines) - Status: ✅ Completed
      notifications.py (131 lines) - Status: ✅ Completed
      pricing.py (544 lines) - Status: ✅ Completed
      promo.py (459 lines) - Status: ✅ Completed
      purchase.py (3454 lines) - Status: ✅ Completed
      summary.py (62 lines) - Status: ✅ Completed
      traffic.py (860 lines) - Status: ✅ Completed
    admin/
      __init__.py (1 lines) - Status: ✅ Completed
      backup.py (722 lines) - Status: ✅ Completed
      bot_configuration.py (2852 lines) - Status: ✅ Completed
      campaigns.py (1799 lines) - Status: ✅ Completed
      faq.py (1065 lines) - Status: ✅ Completed
      main.py (468 lines) - Status: ✅ Completed
      maintenance.py (468 lines) - Status: ✅ Completed
      messages.py (1403 lines) - Status: ✅ Completed
      monitoring.py (1213 lines) - Status: ✅ Completed
      payments.py (613 lines) - Status: ✅ Completed
      polls.py (1254 lines) - Status: ✅ Completed
      pricing.py (1443 lines) - Status: ✅ Completed
      privacy_policy.py (512 lines) - Status: ✅ Completed
      promo_groups.py (1474 lines) - Status: ✅ Completed
      promo_offers.py (2412 lines) - Status: ✅ Completed
      promocodes.py (1237 lines) - Status: ✅ Completed
      public_offer.py (530 lines) - Status: ✅ Completed
      referrals.py (202 lines) - Status: ✅ Completed
      remnawave.py (3917 lines) - Status: ✅ Completed
      reports.py (120 lines) - Status: ✅ Completed
      rules.py (384 lines) - Status: ✅ Completed
      servers.py (1382 lines) - Status: ✅ Completed
      statistics.py (368 lines) - Status: ✅ Completed
      subscriptions.py (442 lines) - Status: ✅ Completed
      support_settings.py (468 lines) - Status: ✅ Completed
      system_logs.py (169 lines) - Status: ✅ Completed
      tenant_bots.py (1247 lines) - Status: ✅ Completed
      tickets.py (1132 lines) - Status: ✅ Completed
      trials.py (86 lines) - Status: ✅ Completed
      updates.py (303 lines) - Status: ✅ Completed
      user_messages.py (661 lines) - Status: ✅ Completed
      users.py (5141 lines) - Status: ✅ Completed
      welcome_text.py (534 lines) - Status: ✅ Completed
```
