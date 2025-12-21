-- Migration: Remove redundant columns from bots table
-- 
-- This migration removes feature flag and configuration columns from the bots table
-- after data has been migrated to bot_feature_flags and bot_configurations tables.
--
-- IMPORTANT: Run this migration ONLY after:
-- 1. Data migration script has been executed successfully
-- 2. Verification script confirms all data was migrated correctly
-- 3. All code has been updated to use BotConfigService
--
-- Rollback: If needed, columns can be re-added, but data will need to be re-migrated
-- from bot_feature_flags and bot_configurations tables.

BEGIN;

-- Remove feature flag columns
ALTER TABLE bots 
    DROP COLUMN IF EXISTS card_to_card_enabled,
    DROP COLUMN IF EXISTS zarinpal_enabled;

-- Remove configuration columns
ALTER TABLE bots 
    DROP COLUMN IF EXISTS default_language,
    DROP COLUMN IF EXISTS support_username,
    DROP COLUMN IF EXISTS admin_chat_id,
    DROP COLUMN IF EXISTS admin_topic_id,
    DROP COLUMN IF EXISTS notification_group_id,
    DROP COLUMN IF EXISTS notification_topic_id,
    DROP COLUMN IF EXISTS card_receipt_topic_id,
    DROP COLUMN IF EXISTS zarinpal_merchant_id,
    DROP COLUMN IF EXISTS zarinpal_sandbox;

COMMIT;

-- Verification query (run after migration to confirm):
-- SELECT column_name 
-- FROM information_schema.columns 
-- WHERE table_name = 'bots' 
-- AND column_name IN (
--     'card_to_card_enabled', 'zarinpal_enabled', 'default_language',
--     'support_username', 'admin_chat_id', 'admin_topic_id',
--     'notification_group_id', 'notification_topic_id',
--     'card_receipt_topic_id', 'zarinpal_merchant_id', 'zarinpal_sandbox'
-- );
-- Expected result: 0 rows

