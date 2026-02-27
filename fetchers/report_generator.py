# report_generator.py

import threading
import webbrowser
from typing import List

import chess
import chess.svg
from flask import Flask, render_template_string

from repertoire_analyzer import OpeningEvaluation


class CoachingReportGenerator:
    """Flask web app that displays coaching recommendations with static SVG boards."""

    def __init__(self, username, evaluations, min_times=1):
        self.username = username
        self.min_times = min_times
        # Filter to player deviations that have coaching data
        candidates = [
            ev for ev in evaluations
            if ev.deviating_side == ev.my_color
            and ev.fen_at_deviation
            and ev.played_move_uci
            and not ev.is_fully_booked
        ]
        # Group by position + played move, keep worst instance per group
        self.deviations, self.deviation_counts, self.deviation_results = (
            self._group_deviations(candidates, min_times))
        # Sort worst first (biggest eval loss = biggest mistake)
        self.deviations.sort(key=lambda ev: ev.eval_loss_cp, reverse=True)

    @staticmethod
    def _group_deviations(candidates, min_times):
        """Group deviations by (FEN, played_move) and apply min_times filter.

        Returns (deviations, counts, results) where deviations is a list of
        the worst-case representative per group, counts maps
        (fen, played_move) -> occurrence count, and results maps
        (fen, played_move) -> {"win": N, "loss": N, "draw": N}.
        """
        groups = {}
        for ev in candidates:
            key = (ev.fen_at_deviation, ev.played_move_uci)
            if key not in groups:
                groups[key] = []
            groups[key].append(ev)

        deviations = []
        counts = {}
        results = {}
        for key, evs in groups.items():
            if len(evs) >= min_times:
                worst = max(evs, key=lambda e: e.eval_loss_cp)
                deviations.append(worst)
                counts[key] = len(evs)
                r = {"win": 0, "loss": 0, "draw": 0}
                for e in evs:
                    if e.my_result in r:
                        r[e.my_result] += 1
                results[key] = r

        return deviations, counts, results

    def _render_board_svg(self, fen, move_uci, color, arrow_color):
        """Render an SVG chessboard with an arrow for a move."""
        board = chess.Board(fen)
        orientation = chess.WHITE if color == "white" else chess.BLACK
        arrows = []
        if move_uci:
            move = chess.Move.from_uci(move_uci)
            arrows = [chess.svg.Arrow(move.from_square, move.to_square, color=arrow_color)]
        return chess.svg.board(board, arrows=arrows, orientation=orientation, size=350)

    def _move_to_san(self, fen, move_uci):
        """Convert a UCI move to SAN notation given a FEN position."""
        if not move_uci:
            return "N/A"
        board = chess.Board(fen)
        try:
            move = chess.Move.from_uci(move_uci)
            return board.san(move)
        except (ValueError, chess.IllegalMoveError):
            return move_uci

    def _ply_to_move_label(self, ply, color):
        """Convert a 0-based ply to a human-readable move number."""
        move_num = (ply // 2) + 1
        if color == "white" or ply % 2 == 0:
            return f"{move_num}."
        return f"{move_num}..."

    def _prepare_deviation(self, ev):
        """Prepare template data for a single deviation."""
        played_san = self._move_to_san(ev.fen_at_deviation, ev.played_move_uci)
        best_san = self._move_to_san(ev.fen_at_deviation, ev.best_move_uci)

        board = chess.Board(ev.fen_at_deviation)
        book_sans = []
        for uci in ev.book_moves_uci:
            try:
                m = chess.Move.from_uci(uci)
                book_sans.append(board.san(m))
            except (ValueError, chess.IllegalMoveError):
                book_sans.append(uci)

        # Eval loss display (primary)
        eval_loss_pawns = ev.eval_loss_cp / 100.0
        loss_display = f"-{eval_loss_pawns:.1f}" if eval_loss_pawns > 0 else f"+{abs(eval_loss_pawns):.1f}"

        # Static eval display (secondary)
        eval_pawns = ev.eval_cp / 100.0
        sign = "+" if eval_pawns >= 0 else ""

        move_label = self._ply_to_move_label(ev.deviation_ply, ev.my_color)

        svg_best = self._render_board_svg(
            ev.fen_at_deviation, ev.best_move_uci, ev.my_color, "#22c55e")
        svg_played = self._render_board_svg(
            ev.fen_at_deviation, ev.played_move_uci, ev.my_color, "#ef4444")

        key = (ev.fen_at_deviation, ev.played_move_uci)
        count = self.deviation_counts.get(key, 1)

        # Win/loss/draw aggregation
        r = self.deviation_results.get(key, {"win": 0, "loss": 0, "draw": 0})
        r_total = r["win"] + r["loss"] + r["draw"]
        win_pct = round(100 * r["win"] / r_total) if r_total else 0
        loss_pct = round(100 * r["loss"] / r_total) if r_total else 0

        return {
            "eco_name": ev.eco_name,
            "eco_code": ev.eco_code or "?",
            "color": ev.my_color,
            "eval_loss_display": loss_display,
            "eval_loss_class": "bad" if ev.eval_loss_cp > 0 else "good",
            "eval_display": f"{sign}{eval_pawns:.1f}",
            "eval_class": "good" if ev.eval_cp >= 0 else "bad",
            "move_label": move_label,
            "played_san": played_san,
            "best_san": best_san,
            "book_moves": ", ".join(book_sans) if book_sans else "None in book",
            "svg_best": svg_best,
            "svg_played": svg_played,
            "times_played": count,
            "game_url": ev.game_url,
            "eval_loss_raw": ev.eval_loss_cp,
            "win_pct": win_pct,
            "loss_pct": loss_pct,
            "time_class": ev.time_class or "unknown",
        }

    def _get_opening_groups(self):
        """Group deviations by opening+color for sidebar navigation."""
        groups = {}
        for ev in self.deviations:
            key = f"{ev.eco_code or 'Unknown'}_{ev.my_color}"
            if key not in groups:
                groups[key] = {
                    "eco_code": ev.eco_code or "Unknown",
                    "eco_name": ev.eco_name,
                    "color": ev.my_color,
                    "count": 0,
                }
            groups[key]["count"] += 1
        return sorted(groups.values(), key=lambda g: g["count"], reverse=True)

    def _build_app(self):
        """Create and configure the Flask app."""
        app = Flask(__name__)

        @app.route("/")
        def index():
            items = [self._prepare_deviation(ev) for ev in self.deviations]
            groups = self._get_opening_groups()
            return render_template_string(
                _MAIN_TEMPLATE,
                username=self.username,
                items=items,
                groups=groups,
                total=len(self.deviations),
                min_times=self.min_times,
                filter_eco=None,
                filter_color=None,
            )

        @app.route("/opening/<eco_code>/<color>")
        def opening_filter(eco_code, color):
            filtered = [
                ev for ev in self.deviations
                if (ev.eco_code or "Unknown") == eco_code and ev.my_color == color
            ]
            items = [self._prepare_deviation(ev) for ev in filtered]
            groups = self._get_opening_groups()
            return render_template_string(
                _MAIN_TEMPLATE,
                username=self.username,
                items=items,
                groups=groups,
                total=len(filtered),
                min_times=self.min_times,
                filter_eco=eco_code,
                filter_color=color,
            )

        return app

    def run(self, port=5050):
        """Start the Flask app and auto-open browser."""
        app = self._build_app()

        # Open browser after a short delay to let the server start
        url = f"http://127.0.0.1:{port}"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

        print(f"\n  Coaching report running at {url}")
        print("  Press Ctrl+C to stop.\n")
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


_MAIN_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chess Coach - {{ username }}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            line-height: 1.6;
        }
        .layout { display: flex; min-height: 100vh; }
        .sidebar {
            width: 280px;
            background: #1e293b;
            padding: 20px;
            border-right: 1px solid #334155;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
        }
        .sidebar h2 {
            color: #f8fafc;
            font-size: 1.1rem;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #334155;
        }
        .sidebar a {
            display: block;
            padding: 8px 12px;
            color: #94a3b8;
            text-decoration: none;
            border-radius: 6px;
            margin-bottom: 4px;
            font-size: 0.9rem;
        }
        .sidebar a:hover { background: #334155; color: #e2e8f0; }
        .sidebar a.active { background: #3b82f6; color: #fff; }
        .sidebar .count { float: right; color: #64748b; font-size: 0.8rem; }
        .sidebar a.active .count { color: #bfdbfe; }
        .main {
            flex: 1;
            padding: 32px;
            max-width: 960px;
        }
        h1 { font-size: 1.8rem; color: #f8fafc; margin-bottom: 8px; }
        .subtitle { color: #94a3b8; margin-bottom: 32px; font-size: 0.95rem; }
        .card {
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            border-left: 4px solid #ef4444;
        }
        .card.positive { border-left-color: #22c55e; }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            flex-wrap: wrap;
            gap: 8px;
        }
        .card-title { font-size: 1.15rem; font-weight: 600; color: #f8fafc; }
        .eco-badge {
            background: #334155;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            color: #94a3b8;
        }
        .eval-badges { display: flex; gap: 8px; align-items: center; }
        .eval-badge {
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.95rem;
        }
        .eval-badge.bad { background: #7f1d1d; color: #fca5a5; }
        .eval-badge.good { background: #166534; color: #4ade80; }
        .eval-badge-secondary {
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            background: #334155;
            color: #94a3b8;
        }
        .result-badge {
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .result-badge.win-high { background: #166534; color: #4ade80; }
        .result-badge.win-low { background: #7f1d1d; color: #fca5a5; }
        /* --- Static SVG fallback boards --- */
        .boards {
            display: flex;
            gap: 24px;
            justify-content: center;
            flex-wrap: wrap;
            margin: 16px 0;
        }
        .board-panel { text-align: center; }
        .board-panel h4 { margin-bottom: 8px; font-size: 0.95rem; color: #cbd5e1; }
        .board-panel h4.best { color: #4ade80; }
        .board-panel h4.played { color: #f87171; }
        .board-panel svg { border-radius: 4px; }
        .meta { margin-top: 12px; font-size: 0.9rem; color: #94a3b8; }
        .times-badge {
            background: #334155;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            color: #94a3b8;
        }
        .times-badge.recurring { background: #3730a3; color: #c7d2fe; }
        .recommendation {
            margin-top: 12px;
            padding: 10px 16px;
            background: #0f2a1a;
            border-radius: 8px;
            color: #4ade80;
            font-size: 1rem;
        }
        .recommendation strong { color: #86efac; }
        .game-link {
            display: inline-block;
            margin-top: 8px;
            font-size: 0.85rem;
            color: #60a5fa;
            text-decoration: none;
        }
        .game-link:hover { text-decoration: underline; color: #93bbfc; }
        .sort-controls { display: inline; }
        .sort-select {
            background: #334155;
            color: #e2e8f0;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 0.9rem;
            cursor: pointer;
        }
        .sort-select:hover { border-color: #60a5fa; }
        .filter-wrapper {
            display: inline-block;
            position: relative;
            margin-left: 12px;
        }
        .filter-btn {
            background: #334155;
            color: #e2e8f0;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.9rem;
            cursor: pointer;
        }
        .filter-btn:hover { border-color: #60a5fa; }
        .filter-panel {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            margin-top: 4px;
            background: #1e293b;
            border: 1px solid #475569;
            border-radius: 8px;
            padding: 8px 12px;
            z-index: 100;
            min-width: 140px;
        }
        .filter-panel.open { display: block; }
        .filter-panel label {
            display: block;
            padding: 4px 0;
            font-size: 0.85rem;
            color: #cbd5e1;
            cursor: pointer;
        }
        .filter-panel input[type="checkbox"] { margin-right: 6px; }
        .empty-state { text-align: center; padding: 80px 20px; color: #64748b; }
        .empty-state h2 { color: #94a3b8; margin-bottom: 12px; }
        @media (max-width: 768px) {
            .layout { flex-direction: column; }
            .sidebar {
                width: 100%;
                height: auto;
                position: static;
                border-right: none;
                border-bottom: 1px solid #334155;
            }
            .boards { flex-direction: column; align-items: center; }
        }
    </style>
</head>
<body>
    <div class="layout">
        <nav class="sidebar">
            <h2>Openings</h2>
            <a href="/" {% if not filter_eco %}class="active"{% endif %}>
                All deviations <span class="count">{{ total }}</span>
            </a>
            {% for g in groups %}
            <a href="/opening/{{ g.eco_code }}/{{ g.color }}"
               {% if filter_eco == g.eco_code and filter_color == g.color %}class="active"{% endif %}>
                {{ g.eco_name }} ({{ g.color }})
                <span class="count">{{ g.count }}</span>
            </a>
            {% endfor %}
        </nav>
        <main class="main">
            <h1>Chess Coach: {{ username }}</h1>
            {% if filter_eco %}
            <div class="subtitle">Showing {{ items|length }} deviations for {{ filter_eco }} as {{ filter_color }} &mdash; sorted by
                <select id="sort-select" class="sort-select">
                    <option value="eval-loss">Biggest mistake</option>
                    <option value="loss-pct">Loss %</option>
                </select>{% if min_times > 1 %} ({{ min_times }}+ occurrences){% endif %}
                <span class="filter-wrapper">
                    <button class="filter-btn" id="filter-btn">Time controls &#9662;</button>
                    <div class="filter-panel" id="filter-panel">
                        <label><input type="checkbox" class="tc-filter" value="bullet" checked> Bullet</label>
                        <label><input type="checkbox" class="tc-filter" value="blitz" checked> Blitz</label>
                        <label><input type="checkbox" class="tc-filter" value="rapid" checked> Rapid</label>
                        <label><input type="checkbox" class="tc-filter" value="daily" checked> Daily</label>
                    </div>
                </span></div>
            {% else %}
            <div class="subtitle">{{ items|length }} positions where you deviated from book/engine &mdash; sorted by
                <select id="sort-select" class="sort-select">
                    <option value="eval-loss">Biggest mistake</option>
                    <option value="loss-pct">Loss %</option>
                </select>{% if min_times > 1 %} ({{ min_times }}+ occurrences){% endif %}
                <span class="filter-wrapper">
                    <button class="filter-btn" id="filter-btn">Time controls &#9662;</button>
                    <div class="filter-panel" id="filter-panel">
                        <label><input type="checkbox" class="tc-filter" value="bullet" checked> Bullet</label>
                        <label><input type="checkbox" class="tc-filter" value="blitz" checked> Blitz</label>
                        <label><input type="checkbox" class="tc-filter" value="rapid" checked> Rapid</label>
                        <label><input type="checkbox" class="tc-filter" value="daily" checked> Daily</label>
                    </div>
                </span></div>
            {% endif %}

            {% if items %}
                {% for item in items %}
                <div class="card {{ 'positive' if item.eval_loss_class == 'good' else '' }}" data-eval-loss="{{ item.eval_loss_raw }}" data-loss-pct="{{ item.loss_pct }}" data-time-class="{{ item.time_class }}">
                    <div class="card-header">
                        <span class="card-title">
                            {{ item.eco_name }}
                            <span class="eco-badge">{{ item.eco_code }}</span>
                            as {{ item.color }}
                        </span>
                        <div class="eval-badges">
                            <span class="eval-badge {{ item.eval_loss_class }}">{{ item.eval_loss_display }} loss</span>
                            <span class="eval-badge-secondary">pos {{ item.eval_display }}</span>
                            <span class="result-badge {{ 'win-high' if item.win_pct >= 50 else 'win-low' }}">W {{ item.win_pct }}% / L {{ item.loss_pct }}%</span>
                        </div>
                    </div>

                    <div class="boards">
                        <div class="board-panel">
                            <h4 class="best">Best: {{ item.best_san }}</h4>
                            {{ item.svg_best | safe }}
                        </div>
                        <div class="board-panel">
                            <h4 class="played">You played: {{ item.played_san }}</h4>
                            {{ item.svg_played | safe }}
                        </div>
                    </div>

                    <p class="meta">
                        Move {{ item.move_label }} &bull;
                        Book moves: {{ item.book_moves }} &bull;
                        <span class="times-badge {{ 'recurring' if item.times_played > 1 else '' }}">{{ item.times_played }}&times; played</span>
                    </p>
                    <div class="recommendation">
                        Play <strong>{{ item.best_san }}</strong> instead of {{ item.played_san }}
                        {% if item.game_url %}
                        &mdash; <a class="game-link" href="{{ item.game_url }}" target="_blank" rel="noopener">view example game &rarr;</a>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <h2>No deviations found</h2>
                    <p>Either all your moves are in the book, or cached data lacks coaching info.</p>
                    <p>Try running with <code>--no-cache</code> to regenerate.</p>
                </div>
            {% endif %}
        </main>
    </div>

    <script>
    (function() {
        /* Sort dropdown */
        var select = document.getElementById('sort-select');
        if (select) {
            select.addEventListener('change', function() {
                var container = document.querySelector('.main');
                var cards = Array.from(container.querySelectorAll('.card'));
                if (!cards.length) return;
                var attr = 'data-' + select.value;
                cards.sort(function(a, b) {
                    return parseFloat(b.getAttribute(attr)) - parseFloat(a.getAttribute(attr));
                });
                cards.forEach(function(card) { container.appendChild(card); });
            });
        }

        /* Time control filter */
        var filterBtn = document.getElementById('filter-btn');
        var filterPanel = document.getElementById('filter-panel');
        if (filterBtn && filterPanel) {
            filterBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                filterPanel.classList.toggle('open');
            });
            document.addEventListener('click', function(e) {
                if (!filterPanel.contains(e.target)) {
                    filterPanel.classList.remove('open');
                }
            });
            var checkboxes = document.querySelectorAll('.tc-filter');
            checkboxes.forEach(function(cb) {
                cb.addEventListener('change', function() {
                    var enabled = new Set();
                    checkboxes.forEach(function(c) {
                        if (c.checked) enabled.add(c.value);
                    });
                    var cards = document.querySelectorAll('.card');
                    cards.forEach(function(card) {
                        var tc = card.getAttribute('data-time-class');
                        card.style.display = (!tc || enabled.has(tc)) ? '' : 'none';
                    });
                });
            });
        }
    })();
    </script>
</body>
</html>"""
