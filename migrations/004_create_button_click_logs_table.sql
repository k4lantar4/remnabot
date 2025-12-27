-- Create button_click_logs table
-- Migration: 004
-- Created: 2025-12-27
-- Description: Add table for tracking button click statistics

CREATE TABLE IF NOT EXISTS button_click_logs (
    id SERIAL PRIMARY KEY,
    button_id INTEGER NOT NULL,
    button_type VARCHAR(50),
    button_text VARCHAR(255),
    user_id INTEGER NOT NULL,
    clicked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS ix_button_click_logs_button_id ON button_click_logs (button_id);
CREATE INDEX IF NOT EXISTS ix_button_click_logs_user_id ON button_click_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_button_click_logs_clicked_at ON button_click_logs (clicked_at);
CREATE INDEX IF NOT EXISTS ix_button_click_logs_button_user ON button_click_logs (button_id, user_id);

-- Add comment
COMMENT ON TABLE button_click_logs IS 'Tracks button clicks for menu layout analytics and statistics';