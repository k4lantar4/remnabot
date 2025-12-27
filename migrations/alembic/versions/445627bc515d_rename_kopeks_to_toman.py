from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "445627bc515d"
down_revision: Union[str, None] = "e3c1e0b5b4a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rename all *_kopeks columns to *_toman and convert data (multiply by 100).

    This migration converts from kopek-based storage (1 kopek = 1/100 ruble)
    to direct toman storage (1 toman = 1 toman).
    """

    # bots table
    op.execute("ALTER TABLE bots RENAME COLUMN wallet_balance_kopeks TO wallet_balance_toman")
    op.execute("UPDATE bots SET wallet_balance_toman = wallet_balance_toman * 100")

    # bot_plans table
    op.execute("ALTER TABLE bot_plans RENAME COLUMN price_kopeks TO price_toman")
    op.execute("UPDATE bot_plans SET price_toman = price_toman * 100")

    # card_to_card_payments table
    op.execute("ALTER TABLE card_to_card_payments RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE card_to_card_payments SET amount_toman = amount_toman * 100")

    # zarinpal_payments table
    op.execute("ALTER TABLE zarinpal_payments RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE zarinpal_payments SET amount_toman = amount_toman * 100")

    # yookassa_payments table
    op.execute("ALTER TABLE yookassa_payments RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE yookassa_payments SET amount_toman = amount_toman * 100")

    # mulenpay_payments table
    op.execute("ALTER TABLE mulenpay_payments RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE mulenpay_payments SET amount_toman = amount_toman * 100")

    # pal24_payments table
    op.execute("ALTER TABLE pal24_payments RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE pal24_payments SET amount_toman = amount_toman * 100")

    # wata_payments table
    op.execute("ALTER TABLE wata_payments RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE wata_payments SET amount_toman = amount_toman * 100")

    # platega_payments table
    op.execute("ALTER TABLE platega_payments RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE platega_payments SET amount_toman = amount_toman * 100")

    # promo_groups table
    op.execute("ALTER TABLE promo_groups RENAME COLUMN auto_assign_total_spent_kopeks TO auto_assign_total_spent_toman")
    op.execute(
        "UPDATE promo_groups SET auto_assign_total_spent_toman = auto_assign_total_spent_toman * 100 WHERE auto_assign_total_spent_toman IS NOT NULL"
    )

    # users table
    op.execute("ALTER TABLE users RENAME COLUMN balance_kopeks TO balance_toman")
    op.execute("UPDATE users SET balance_toman = balance_toman * 100")
    op.execute("ALTER TABLE users RENAME COLUMN auto_promo_group_threshold_kopeks TO auto_promo_group_threshold_toman")
    op.execute("UPDATE users SET auto_promo_group_threshold_toman = auto_promo_group_threshold_toman * 100")

    # transactions table
    op.execute("ALTER TABLE transactions RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE transactions SET amount_toman = amount_toman * 100")

    # subscription_conversions table
    op.execute(
        "ALTER TABLE subscription_conversions RENAME COLUMN first_payment_amount_kopeks TO first_payment_amount_toman"
    )
    op.execute(
        "UPDATE subscription_conversions SET first_payment_amount_toman = first_payment_amount_toman * 100 WHERE first_payment_amount_toman IS NOT NULL"
    )

    # promocodes table
    op.execute("ALTER TABLE promocodes RENAME COLUMN balance_bonus_kopeks TO balance_bonus_toman")
    op.execute("UPDATE promocodes SET balance_bonus_toman = balance_bonus_toman * 100")

    # referral_earnings table
    op.execute("ALTER TABLE referral_earnings RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE referral_earnings SET amount_toman = amount_toman * 100")

    # referral_contest_events table
    op.execute("ALTER TABLE referral_contest_events RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE referral_contest_events SET amount_toman = amount_toman * 100")

    # squads table
    op.execute("ALTER TABLE squads RENAME COLUMN price_kopeks TO price_toman")
    op.execute("UPDATE squads SET price_toman = price_toman * 100")

    # subscription_events table
    op.execute("ALTER TABLE subscription_events RENAME COLUMN amount_kopeks TO amount_toman")
    op.execute("UPDATE subscription_events SET amount_toman = amount_toman * 100 WHERE amount_toman IS NOT NULL")

    # discount_offers table
    op.execute("ALTER TABLE discount_offers RENAME COLUMN bonus_amount_kopeks TO bonus_amount_toman")
    op.execute("UPDATE discount_offers SET bonus_amount_toman = bonus_amount_toman * 100")

    # promo_offer_templates table
    op.execute("ALTER TABLE promo_offer_templates RENAME COLUMN bonus_amount_kopeks TO bonus_amount_toman")
    op.execute("UPDATE promo_offer_templates SET bonus_amount_toman = bonus_amount_toman * 100")

    # polls table
    op.execute("ALTER TABLE polls RENAME COLUMN reward_amount_kopeks TO reward_amount_toman")
    op.execute("UPDATE polls SET reward_amount_toman = reward_amount_toman * 100")

    # poll_responses table
    op.execute("ALTER TABLE poll_responses RENAME COLUMN reward_amount_kopeks TO reward_amount_toman")
    op.execute("UPDATE poll_responses SET reward_amount_toman = reward_amount_toman * 100")

    # server_squads table
    op.execute("ALTER TABLE server_squads RENAME COLUMN price_kopeks TO price_toman")
    op.execute("UPDATE server_squads SET price_toman = price_toman * 100")

    # subscription_servers table
    op.execute("ALTER TABLE subscription_servers RENAME COLUMN paid_price_kopeks TO paid_price_toman")
    op.execute("UPDATE subscription_servers SET paid_price_toman = paid_price_toman * 100")

    # advertising_campaigns table
    op.execute("ALTER TABLE advertising_campaigns RENAME COLUMN balance_bonus_kopeks TO balance_bonus_toman")
    op.execute("UPDATE advertising_campaigns SET balance_bonus_toman = balance_bonus_toman * 100")

    # advertising_campaign_registrations table
    op.execute(
        "ALTER TABLE advertising_campaign_registrations RENAME COLUMN balance_bonus_kopeks TO balance_bonus_toman"
    )
    op.execute("UPDATE advertising_campaign_registrations SET balance_bonus_toman = balance_bonus_toman * 100")


def downgrade() -> None:
    """
    Revert the migration: rename *_toman back to *_kopeks and divide by 100.
    """

    # advertising_campaign_registrations table
    op.execute(
        "ALTER TABLE advertising_campaign_registrations RENAME COLUMN balance_bonus_toman TO balance_bonus_kopeks"
    )
    op.execute("UPDATE advertising_campaign_registrations SET balance_bonus_kopeks = balance_bonus_kopeks / 100")

    # advertising_campaigns table
    op.execute("ALTER TABLE advertising_campaigns RENAME COLUMN balance_bonus_toman TO balance_bonus_kopeks")
    op.execute("UPDATE advertising_campaigns SET balance_bonus_kopeks = balance_bonus_kopeks / 100")

    # subscription_servers table
    op.execute("ALTER TABLE subscription_servers RENAME COLUMN paid_price_toman TO paid_price_kopeks")
    op.execute("UPDATE subscription_servers SET paid_price_kopeks = paid_price_kopeks / 100")

    # server_squads table
    op.execute("ALTER TABLE server_squads RENAME COLUMN price_toman TO price_kopeks")
    op.execute("UPDATE server_squads SET price_kopeks = price_kopeks / 100")

    # poll_responses table
    op.execute("ALTER TABLE poll_responses RENAME COLUMN reward_amount_toman TO reward_amount_kopeks")
    op.execute("UPDATE poll_responses SET reward_amount_kopeks = reward_amount_kopeks / 100")

    # polls table
    op.execute("ALTER TABLE polls RENAME COLUMN reward_amount_toman TO reward_amount_kopeks")
    op.execute("UPDATE polls SET reward_amount_kopeks = reward_amount_kopeks / 100")

    # promo_offer_templates table
    op.execute("ALTER TABLE promo_offer_templates RENAME COLUMN bonus_amount_toman TO bonus_amount_kopeks")
    op.execute("UPDATE promo_offer_templates SET bonus_amount_kopeks = bonus_amount_kopeks / 100")

    # discount_offers table
    op.execute("ALTER TABLE discount_offers RENAME COLUMN bonus_amount_toman TO bonus_amount_kopeks")
    op.execute("UPDATE discount_offers SET bonus_amount_kopeks = bonus_amount_kopeks / 100")

    # subscription_events table
    op.execute("ALTER TABLE subscription_events RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE subscription_events SET amount_kopeks = amount_kopeks / 100 WHERE amount_kopeks IS NOT NULL")

    # squads table
    op.execute("ALTER TABLE squads RENAME COLUMN price_toman TO price_kopeks")
    op.execute("UPDATE squads SET price_kopeks = price_kopeks / 100")

    # referral_contest_events table
    op.execute("ALTER TABLE referral_contest_events RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE referral_contest_events SET amount_kopeks = amount_kopeks / 100")

    # referral_earnings table
    op.execute("ALTER TABLE referral_earnings RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE referral_earnings SET amount_kopeks = amount_kopeks / 100")

    # promocodes table
    op.execute("ALTER TABLE promocodes RENAME COLUMN balance_bonus_toman TO balance_bonus_kopeks")
    op.execute("UPDATE promocodes SET balance_bonus_kopeks = balance_bonus_kopeks / 100")

    # subscription_conversions table
    op.execute(
        "ALTER TABLE subscription_conversions RENAME COLUMN first_payment_amount_toman TO first_payment_amount_kopeks"
    )
    op.execute(
        "UPDATE subscription_conversions SET first_payment_amount_kopeks = first_payment_amount_kopeks / 100 WHERE first_payment_amount_kopeks IS NOT NULL"
    )

    # transactions table
    op.execute("ALTER TABLE transactions RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE transactions SET amount_kopeks = amount_kopeks / 100")

    # users table
    op.execute("ALTER TABLE users RENAME COLUMN auto_promo_group_threshold_toman TO auto_promo_group_threshold_kopeks")
    op.execute("UPDATE users SET auto_promo_group_threshold_kopeks = auto_promo_group_threshold_kopeks / 100")
    op.execute("ALTER TABLE users RENAME COLUMN balance_toman TO balance_kopeks")
    op.execute("UPDATE users SET balance_kopeks = balance_kopeks / 100")

    # promo_groups table
    op.execute("ALTER TABLE promo_groups RENAME COLUMN auto_assign_total_spent_toman TO auto_assign_total_spent_kopeks")
    op.execute(
        "UPDATE promo_groups SET auto_assign_total_spent_kopeks = auto_assign_total_spent_kopeks / 100 WHERE auto_assign_total_spent_kopeks IS NOT NULL"
    )

    # platega_payments table
    op.execute("ALTER TABLE platega_payments RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE platega_payments SET amount_kopeks = amount_kopeks / 100")

    # wata_payments table
    op.execute("ALTER TABLE wata_payments RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE wata_payments SET amount_kopeks = amount_kopeks / 100")

    # pal24_payments table
    op.execute("ALTER TABLE pal24_payments RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE pal24_payments SET amount_kopeks = amount_kopeks / 100")

    # mulenpay_payments table
    op.execute("ALTER TABLE mulenpay_payments RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE mulenpay_payments SET amount_kopeks = amount_kopeks / 100")

    # yookassa_payments table
    op.execute("ALTER TABLE yookassa_payments RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE yookassa_payments SET amount_kopeks = amount_kopeks / 100")

    # zarinpal_payments table
    op.execute("ALTER TABLE zarinpal_payments RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE zarinpal_payments SET amount_kopeks = amount_kopeks / 100")

    # card_to_card_payments table
    op.execute("ALTER TABLE card_to_card_payments RENAME COLUMN amount_toman TO amount_kopeks")
    op.execute("UPDATE card_to_card_payments SET amount_kopeks = amount_kopeks / 100")

    # bot_plans table
    op.execute("ALTER TABLE bot_plans RENAME COLUMN price_toman TO price_kopeks")
    op.execute("UPDATE bot_plans SET price_kopeks = price_kopeks / 100")

    # bots table
    op.execute("ALTER TABLE bots RENAME COLUMN wallet_balance_toman TO wallet_balance_kopeks")
    op.execute("UPDATE bots SET wallet_balance_kopeks = wallet_balance_kopeks / 100")
