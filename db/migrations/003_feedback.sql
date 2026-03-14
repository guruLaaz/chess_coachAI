-- 003_feedback.sql — bug reports and contact submissions

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    email VARCHAR(255) NOT NULL,
    details TEXT NOT NULL,
    screenshot TEXT DEFAULT '',
    page_url TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
