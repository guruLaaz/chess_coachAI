-- 001_initial.sql — full schema for Chess CoachAI

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id SERIAL PRIMARY KEY,
    chesscom_user TEXT,
    lichess_user TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    progress_pct INTEGER NOT NULL DEFAULT 0,
    total_games INTEGER,
    message TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS archive_months (
    id SERIAL PRIMARY KEY,
    archive_url TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    raw_json JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS opening_evaluations (
    id SERIAL PRIMARY KEY,
    game_url TEXT NOT NULL,
    username TEXT NOT NULL,
    depth INTEGER NOT NULL,
    eco_code TEXT,
    eco_name TEXT NOT NULL,
    my_color TEXT NOT NULL,
    deviation_ply INTEGER NOT NULL,
    deviating_side TEXT NOT NULL,
    eval_cp INTEGER NOT NULL,
    is_fully_booked BOOLEAN NOT NULL DEFAULT FALSE,
    fen_at_deviation TEXT DEFAULT '',
    best_move_uci TEXT,
    played_move_uci TEXT,
    book_moves_uci TEXT DEFAULT '',
    eval_loss_cp INTEGER DEFAULT 0,
    game_moves_uci TEXT DEFAULT '',
    my_result TEXT DEFAULT '',
    time_class TEXT DEFAULT '',
    opponent_name TEXT DEFAULT '',
    end_time TIMESTAMPTZ,
    UNIQUE (game_url, depth)
);

CREATE TABLE IF NOT EXISTS endgame_analyses (
    id SERIAL PRIMARY KEY,
    game_url TEXT NOT NULL,
    definition TEXT NOT NULL,
    endgame_type TEXT,
    endgame_ply INTEGER,
    material_balance TEXT,
    my_result TEXT,
    fen_at_endgame TEXT,
    material_diff INTEGER,
    game_url_link TEXT DEFAULT '',
    my_clock REAL,
    opp_clock REAL,
    UNIQUE (game_url, definition)
);
