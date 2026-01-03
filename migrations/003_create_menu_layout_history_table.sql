-- Create menu_layout_history table
-- Migration: 003
-- Created: 2025-12-27
-- Description: Add table for tracking menu layout configuration changes

-- Create table (only if it doesn't exist)
DO $$ BEGIN
    CREATE TABLE IF NOT EXISTS menu_layout_history (
        id SERIAL PRIMARY KEY,
        config_json TEXT NOT NULL,
        action VARCHAR(100) NOT NULL,
        changes_summary TEXT NOT NULL,
        user_info VARCHAR(255),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
EXCEPTION
    WHEN duplicate_table THEN
        -- Table already exists, do nothing
        NULL;
END $$;

-- Create index for efficient ordering by creation time
CREATE INDEX IF NOT EXISTS ix_menu_layout_history_created_at ON menu_layout_history (created_at DESC);

-- Add comment
COMMENT ON TABLE menu_layout_history IS 'Tracks changes to menu layout configurations for audit and rollback purposes';
