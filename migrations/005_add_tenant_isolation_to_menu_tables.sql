-- Add tenant isolation to menu layout tables
-- Migration: 005
-- Created: 2025-12-27
-- Description: Add bot_id columns for tenant isolation in menu_layout_history and button_click_logs

-- Add bot_id to menu_layout_history table
ALTER TABLE menu_layout_history ADD COLUMN IF NOT EXISTS bot_id INTEGER;

-- Add bot_id to button_click_logs table
ALTER TABLE button_click_logs ADD COLUMN IF NOT EXISTS bot_id INTEGER;

-- Create indexes for tenant isolation
CREATE INDEX IF NOT EXISTS ix_menu_layout_history_bot_id ON menu_layout_history (bot_id);
CREATE INDEX IF NOT EXISTS ix_button_click_logs_bot_id ON button_click_logs (bot_id);

-- Note: Existing data will need to be migrated to include bot_id values
-- This should be done by application logic when records are accessed
