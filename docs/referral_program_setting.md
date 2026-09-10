# Enabling and disabling the referral program

## Description

The referral (partner) program can be enabled and disabled through an environment variable.

## Configuration

In `.env`, set:

- `REFERRAL_PROGRAM_ENABLED=true` — referral program enabled
- `REFERRAL_PROGRAM_ENABLED=false` — referral program disabled

## Behavior

- When the program is disabled, **Partners**, **Referrals**, and other related items are hidden from the bot’s main menu
- Ordinary (non-referral) buttons continue to display regardless of this setting
- Referral admin functions remain available in the admin panel for management
- The setting is also respected by the API and other services that use referral-program information

## Examples of hidden items

- **🤝 Partners** button in the main menu
- **👥 My referrals** button
- **🤝 Referral program** (English locale)
- Other items containing the words “partner”, “referr”, “партнер”, or “реферал”

## Technical details

- The new `REFERRAL_PROGRAM_ENABLED` variable was added in `app/config.py`
- `is_referral_program_enabled()` checks the setting
- `get_main_menu_keyboard` in `app/keyboards/inline.py` hides the **Partners** button when the program is disabled
- `MainMenuButtonService` in `app/services/main_menu_button_service.py` hides extra buttons related to referrals
- `.env.example` was updated with the new setting
