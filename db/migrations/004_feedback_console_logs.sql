-- 004_feedback_console_logs.sql — add console_logs column to feedback table

ALTER TABLE feedback ADD COLUMN IF NOT EXISTS console_logs TEXT DEFAULT '';
