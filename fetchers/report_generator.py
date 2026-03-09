# report_generator.py

import threading
import webbrowser
from typing import List

import chess
import chess.svg
from flask import Flask, render_template_string, request, jsonify

from repertoire_analyzer import OpeningEvaluation


class CoachingReportGenerator:
    """Flask web app that displays coaching recommendations with static SVG boards."""

    def __init__(self, evaluations, chesscom_user="", lichess_user="",
                 endgame_stats=None):
        self.chesscom_user = chesscom_user
        self.lichess_user = lichess_user
        self.username = chesscom_user or lichess_user
        # endgame_stats: dict[definition -> list[dict]] or legacy list[dict]
        if isinstance(endgame_stats, dict):
            self.endgame_stats_by_def = endgame_stats
        else:
            # Legacy: single list treated as minor-or-queen
            self.endgame_stats_by_def = {"minor-or-queen": endgame_stats or []}
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
            self._group_deviations(candidates))
        # Sort worst first (biggest eval loss = biggest mistake)
        self.deviations.sort(key=lambda ev: ev.eval_loss_cp, reverse=True)
        # Pre-compute item dicts (no SVGs — those are rendered lazily via API)
        self._cached_items = [self._prepare_deviation(ev) for ev in self.deviations]

    @staticmethod
    def _group_deviations(candidates):
        """Group deviations by (FEN, played_move).

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

    @staticmethod
    def _format_clock(seconds):
        """Format seconds as m:ss or h:mm:ss."""
        if seconds is None:
            return "?"
        seconds = int(seconds)
        if seconds >= 3600:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h}:{m:02d}:{s:02d}"
        m = seconds // 60
        s = seconds % 60
        return f"{m}:{s:02d}"

    def _ply_to_move_label(self, ply, color):
        """Convert a 0-based ply to a human-readable move number."""
        move_num = (ply // 2) + 1
        if color == "white" or ply % 2 == 0:
            return f"{move_num}."
        return f"{move_num}..."

    @staticmethod
    def _format_date(dt):
        """Format a datetime as 'Month D, YYYY' (e.g. 'September 5, 2025')."""
        if dt is None:
            return ""
        return f"{dt.strftime('%B')} {dt.day}, {dt.year}"

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
            "fen": ev.fen_at_deviation,
            "best_move_uci": ev.best_move_uci,
            "played_move_uci": ev.played_move_uci,
            "times_played": count,
            "game_url": ev.game_url,
            "eval_loss_raw": ev.eval_loss_cp,
            "win_pct": win_pct,
            "loss_pct": loss_pct,
            "time_class": ev.time_class or "unknown",
            "platform": "lichess" if "lichess.org" in ev.game_url else "chesscom" if ev.game_url else "unknown",
            "opponent_name": ev.opponent_name or "",
            "game_date": self._format_date(ev.end_time),
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

        default_def = "minor-or-queen"
        default_stats = self.endgame_stats_by_def.get(default_def, [])
        endgame_count = sum(s["total"] for s in default_stats)

        @app.route("/")
        def index():
            items = self._cached_items
            groups = self._get_opening_groups()
            return render_template_string(
                _MAIN_TEMPLATE,
                username=self.username,
                chesscom_user=self.chesscom_user,
                lichess_user=self.lichess_user,
                items=items,
                groups=groups,
                total=len(self.deviations),
                filter_eco=None,
                filter_color=None,
                page="openings",
                endgame_count=endgame_count,
            )

        @app.route("/opening/<eco_code>/<color>")
        def opening_filter(eco_code, color):
            items = [
                item for item in self._cached_items
                if item["eco_code"] == eco_code and item["color"] == color
            ]
            groups = self._get_opening_groups()
            return render_template_string(
                _MAIN_TEMPLATE,
                username=self.username,
                chesscom_user=self.chesscom_user,
                lichess_user=self.lichess_user,
                items=items,
                groups=groups,
                total=len(items),
                filter_eco=eco_code,
                filter_color=color,
                page="openings",
                endgame_count=endgame_count,
            )

        @app.route("/endgames")
        def endgames():
            groups = self._get_opening_groups()
            # Prepare endgame stats (SVGs rendered lazily via API)
            enriched = []
            for defn, stats_list in self.endgame_stats_by_def.items():
                for s in stats_list:
                    entry = dict(s)
                    entry["definition"] = defn
                    # Build deep-link URL that opens at the endgame move
                    game_url = s.get("example_game_url", "")
                    ply = s.get("example_endgame_ply", 0)
                    if game_url and ply:
                        if "lichess.org" in game_url:
                            entry["example_game_url"] = f"{game_url}#{ply + 1}"
                        elif "chess.com" in game_url:
                            analysis_url = game_url.replace(
                                "chess.com/game/",
                                "chess.com/analysis/game/")
                            entry["example_game_url"] = (
                                f"{analysis_url}?tab=analysis&move={ply}")
                    # Format example game date
                    entry["example_date"] = self._format_date(s.get("example_end_time"))
                    # Format average clock times for display
                    entry["avg_my_clock_fmt"] = self._format_clock(s.get("avg_my_clock"))
                    entry["avg_opp_clock_fmt"] = self._format_clock(s.get("avg_opp_clock"))
                    enriched.append(entry)
            return render_template_string(
                _ENDGAME_TEMPLATE,
                username=self.username,
                chesscom_user=self.chesscom_user,
                lichess_user=self.lichess_user,
                stats=enriched,
                endgame_count=endgame_count,
                groups=groups,
                total=len(self.deviations),
                page="endgames",
                definitions=list(self.endgame_stats_by_def.keys()),
                default_definition=default_def,
            )

        @app.route("/endgames/all")
        def endgames_all_games():
            defn = request.args.get("def", default_def)
            eg_type = request.args.get("type", "")
            balance = request.args.get("balance", "")
            groups = self._get_opening_groups()

            # Find the matching aggregate entry
            stats_list = self.endgame_stats_by_def.get(defn, [])
            match = None
            for s in stats_list:
                if s["type"] == eg_type and s["balance"] == balance:
                    match = s
                    break
            if match is None:
                return render_template_string(
                    _ENDGAME_ALL_GAMES_TEMPLATE,
                    username=self.username,
                chesscom_user=self.chesscom_user,
                lichess_user=self.lichess_user,
                    eg_type=eg_type,
                    balance=balance,
                    definition=defn,
                    games=[],
                    groups=groups,
                    endgame_count=endgame_count,
                    total=len(self.deviations),
                    page="endgames_all",
                )

            # Enrich each game with deep-link, formatted clocks (SVGs lazy)
            enriched_games = []
            for g in match.get("all_games", []):
                entry = dict(g)
                # Deep-link
                game_url = g.get("game_url", "")
                ply = g.get("endgame_ply", 0)
                entry["deep_link"] = ""
                if game_url and ply:
                    if "lichess.org" in game_url:
                        entry["deep_link"] = f"{game_url}#{ply + 1}"
                    elif "chess.com" in game_url:
                        analysis_url = game_url.replace(
                            "chess.com/game/",
                            "chess.com/analysis/game/")
                        entry["deep_link"] = (
                            f"{analysis_url}?tab=analysis&move={ply}")
                elif game_url:
                    entry["deep_link"] = game_url
                # Format clocks
                entry["my_clock_fmt"] = self._format_clock(g.get("my_clock"))
                entry["opp_clock_fmt"] = self._format_clock(g.get("opp_clock"))
                # Result badge class
                result = g.get("my_result", "draw")
                entry["result_class"] = (
                    "win" if result == "win"
                    else "loss" if result == "loss"
                    else "draw")
                enriched_games.append(entry)

            return render_template_string(
                _ENDGAME_ALL_GAMES_TEMPLATE,
                username=self.username,
                chesscom_user=self.chesscom_user,
                lichess_user=self.lichess_user,
                eg_type=eg_type,
                balance=balance,
                definition=defn,
                games=enriched_games,
                groups=groups,
                endgame_count=endgame_count,
                total=len(self.deviations),
                page="endgames_all",
            )

        @app.route("/api/render-boards", methods=["POST"])
        def render_boards():
            specs = request.get_json()
            results = []
            for s in specs:
                svg = self._render_board_svg(
                    s["fen"], s.get("move"), s["color"], s.get("arrow_color", ""))
                results.append(svg)
            return jsonify(results)

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
    <title>Chess Coach - {% if chesscom_user %}{{ chesscom_user }}{% endif %}{% if chesscom_user and lichess_user %} / {% endif %}{% if lichess_user %}{{ lichess_user }}{% endif %}</title>
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
            cursor: pointer;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .sidebar h2::after {
            content: "\25BE";
            font-size: 0.8rem;
            transition: transform 0.2s;
        }
        .sidebar h2.collapsed::after {
            transform: rotate(-90deg);
        }
        .section-links {
            overflow: hidden;
            transition: max-height 0.25s ease;
        }
        .section-links.collapsed {
            max-height: 0 !important;
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
        .user-badges { display: inline; }
        .user-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #334155;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 500;
            vertical-align: middle;
        }
        .user-badge + .user-badge { margin-left: 8px; }
        .user-badge svg { width: 18px; height: 18px; flex-shrink: 0; }
        a.user-badge { color: #e2e8f0; text-decoration: none; transition: background 0.15s; }
        a.user-badge:hover { background: #475569; }
        .subtitle { color: #94a3b8; margin-bottom: 32px; font-size: 0.95rem; }
        .board-spinner { text-align:center; padding:60px 0; color:#64748b; font-size:0.9rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .board-spinner::before { content:""; display:block; width:32px; height:32px; margin:0 auto 12px; border:3px solid #334155; border-top-color:#3b82f6; border-radius:50%; animation:spin .8s linear infinite; }
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
            <h2 id="hdr-openings">Openings</h2>
            <div class="section-links" id="openings-links">
                <a href="/" {% if page == 'openings' and not filter_eco %}class="active"{% endif %}>
                    All deviations <span class="count">{{ total }}</span>
                </a>
                {% for g in groups %}
                <a href="/opening/{{ g.eco_code }}/{{ g.color }}"
                   {% if filter_eco == g.eco_code and filter_color == g.color %}class="active"{% endif %}>
                    {{ g.eco_name }} ({{ g.color }})
                    <span class="count">{{ g.count }}</span>
                </a>
                {% endfor %}
            </div>
            <h2 id="hdr-analysis" style="margin-top: 24px;">Analysis</h2>
            <div class="section-links" id="analysis-links">
                <a href="/endgames" {% if page == 'endgames' %}class="active"{% endif %}>
                    Endgames <span class="count">{{ endgame_count }}</span>
                </a>
            </div>
        </nav>
        <main class="main">
            <h1>Chess Coach: <span class="user-badges">{% if chesscom_user %}<a class="user-badge" href="https://www.chess.com/member/{{ chesscom_user }}" target="_blank" rel="noopener"><svg viewBox="0 0 96.4 144"><path fill="#81b64c" d="M48.2 0C35.4-.1 25 10.3 24.9 23.1c0 7.5 3.6 14.6 9.7 18.9L17.9 53c0 3.5.9 6.9 2.6 9.9h14.8c-.3 6.6 2.4 22.6-21.8 41.1C5 110.4 0 121.3 0 134.6c0 .6 1.3 9.4 48.2 9.4s48.2-8.8 48.2-9.4c0-13.3-5-24.3-13.4-30.7-24.2-18.5-21.5-34.5-21.8-41.1H76c1.7-3 2.6-6.4 2.6-9.8L61.8 42c10.4-7.5 12.8-21.9 5.3-32.3C62.8 3.6 55.7 0 48.2 0z"/></svg>{{ chesscom_user }}</a>{% endif %}{% if lichess_user %}<a class="user-badge" href="https://lichess.org/@/{{ lichess_user }}" target="_blank" rel="noopener"><svg viewBox="0 0 50 50"><path fill="#fff" stroke="#fff" stroke-linejoin="round" d="M38.956.5c-3.53.418-6.452.902-9.286 2.984C5.534 1.786-.692 18.533.68 29.364 3.493 50.214 31.918 55.785 41.329 41.7c-7.444 7.696-19.276 8.752-28.323 3.084C3.959 39.116-.506 27.392 4.683 17.567 9.873 7.742 18.996 4.535 29.03 6.405c2.43-1.418 5.225-3.22 7.655-3.187l-1.694 4.86 12.752 21.37c-.439 5.654-5.459 6.112-5.459 6.112-.574-1.47-1.634-2.942-4.842-6.036-3.207-3.094-17.465-10.177-15.788-16.207-2.001 6.967 10.311 14.152 14.04 17.663 3.73 3.51 5.426 6.04 5.795 6.756 0 0 9.392-2.504 7.838-8.927L37.4 7.171z"/></svg>{{ lichess_user }}</a>{% endif %}</span></h1>
            {% if filter_eco %}
            <div class="subtitle">Showing {{ items|length }} deviations for {{ filter_eco }} as {{ filter_color }} &mdash; sorted by
                <select id="sort-select" class="sort-select">
                    <option value="eval-loss">Biggest mistake</option>
                    <option value="loss-pct">Loss %</option>
                </select>
                <span class="filter-wrapper">
                    <button class="filter-btn" id="filter-btn">Time controls &#9662;</button>
                    <div class="filter-panel" id="filter-panel">
                        <label><input type="checkbox" class="tc-filter" value="bullet" checked> Bullet</label>
                        <label><input type="checkbox" class="tc-filter" value="blitz" checked> Blitz</label>
                        <label><input type="checkbox" class="tc-filter" value="rapid" checked> Rapid</label>
                        <label><input type="checkbox" class="tc-filter" value="daily" checked> Daily</label>
                    </div>
                </span>
                <span class="filter-wrapper">
                    <button class="filter-btn" id="platform-btn">Platform &#9662;</button>
                    <div class="filter-panel" id="platform-panel">
                        <label><input type="checkbox" class="platform-filter" value="chesscom" checked> Chess.com</label>
                        <label><input type="checkbox" class="platform-filter" value="lichess" checked> Lichess</label>
                    </div>
                </span>
                <span class="filter-wrapper">
                    <button class="filter-btn" id="min-games-btn">Min games &#9662;</button>
                    <div class="filter-panel" id="min-games-panel">
                        <select id="min-games-select" class="sort-select" style="width:100%">
                            <option value="1">1+ (all)</option>
                            <option value="2">2+</option>
                            <option value="3" selected>3+</option>
                            <option value="5">5+</option>
                            <option value="10">10+</option>
                        </select>
                    </div>
                </span></div>
            {% else %}
            <div class="subtitle">{{ items|length }} positions where you deviated from book/engine &mdash; sorted by
                <select id="sort-select" class="sort-select">
                    <option value="eval-loss">Biggest mistake</option>
                    <option value="loss-pct">Loss %</option>
                </select>
                <span class="filter-wrapper">
                    <button class="filter-btn" id="filter-btn">Time controls &#9662;</button>
                    <div class="filter-panel" id="filter-panel">
                        <label><input type="checkbox" class="tc-filter" value="bullet" checked> Bullet</label>
                        <label><input type="checkbox" class="tc-filter" value="blitz" checked> Blitz</label>
                        <label><input type="checkbox" class="tc-filter" value="rapid" checked> Rapid</label>
                        <label><input type="checkbox" class="tc-filter" value="daily" checked> Daily</label>
                    </div>
                </span>
                <span class="filter-wrapper">
                    <button class="filter-btn" id="platform-btn">Platform &#9662;</button>
                    <div class="filter-panel" id="platform-panel">
                        <label><input type="checkbox" class="platform-filter" value="chesscom" checked> Chess.com</label>
                        <label><input type="checkbox" class="platform-filter" value="lichess" checked> Lichess</label>
                    </div>
                </span>
                <span class="filter-wrapper">
                    <button class="filter-btn" id="min-games-btn">Min games &#9662;</button>
                    <div class="filter-panel" id="min-games-panel">
                        <select id="min-games-select" class="sort-select" style="width:100%">
                            <option value="1">1+ (all)</option>
                            <option value="2">2+</option>
                            <option value="3" selected>3+</option>
                            <option value="5">5+</option>
                            <option value="10">10+</option>
                        </select>
                    </div>
                </span></div>
            {% endif %}

            {% if items %}
                {% for item in items %}
                <div class="card {{ 'positive' if item.eval_loss_class == 'good' else '' }}" style="display:none" data-eval-loss="{{ item.eval_loss_raw }}" data-loss-pct="{{ item.loss_pct }}" data-time-class="{{ item.time_class }}" data-platform="{{ item.platform }}" data-times="{{ item.times_played }}" data-fen="{{ item.fen }}" data-best-move="{{ item.best_move_uci }}" data-played-move="{{ item.played_move_uci }}" data-color="{{ item.color }}">
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
                            <div class="board-slot board-best"><div class="board-spinner">Loading board&hellip;</div></div>
                        </div>
                        <div class="board-panel">
                            <h4 class="played">You played: {{ item.played_san }}</h4>
                            <div class="board-slot board-played"><div class="board-spinner">Loading board&hellip;</div></div>
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
                        &mdash; <a class="game-link" href="{{ item.game_url }}" target="_blank" rel="noopener">view example game{% if item.opponent_name or item.time_class or item.game_date %} ({% if item.opponent_name %}vs {{ item.opponent_name }}{% endif %}{% if item.time_class and item.time_class != 'unknown' %}{% if item.opponent_name %}, {% endif %}{{ item.time_class }}{% endif %}{% if item.game_date %}{% if item.opponent_name or (item.time_class and item.time_class != 'unknown') %}, {% endif %}{{ item.game_date }}{% endif %}){% endif %} &rarr;</a>
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
        /* Sidebar accordion */
        (function() {
            var sections = [
                { hdr: document.getElementById('hdr-openings'), links: document.getElementById('openings-links') },
                { hdr: document.getElementById('hdr-analysis'), links: document.getElementById('analysis-links') }
            ];
            var activePage = '{{ page }}';
            var activeIdx = (activePage === 'endgames') ? 1 : 0;
            sections.forEach(function(s, i) {
                if (i === activeIdx) {
                    s.links.style.maxHeight = s.links.scrollHeight + 'px';
                } else {
                    s.links.classList.add('collapsed');
                    s.hdr.classList.add('collapsed');
                }
                s.hdr.addEventListener('click', function() {
                    sections.forEach(function(other) {
                        if (other === s) {
                            var isCollapsed = other.links.classList.contains('collapsed');
                            if (isCollapsed) {
                                other.links.classList.remove('collapsed');
                                other.hdr.classList.remove('collapsed');
                                other.links.style.maxHeight = other.links.scrollHeight + 'px';
                            } else {
                                other.links.classList.add('collapsed');
                                other.hdr.classList.add('collapsed');
                            }
                        } else {
                            other.links.classList.add('collapsed');
                            other.hdr.classList.add('collapsed');
                        }
                    });
                });
            });
        })();

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

        /* Shared filter logic: card visible only if it passes ALL active filters */
        var tcChecks = document.querySelectorAll('.tc-filter');
        var platChecks = document.querySelectorAll('.platform-filter');
        var minGamesSelect = document.getElementById('min-games-select');

        /* Infinite scroll state */
        var PAGE_SIZE = 10;
        var shownCount = 0;
        var fetchingBoards = false;

        function applyFilters() {
            var enabledTC = new Set();
            tcChecks.forEach(function(c) { if (c.checked) enabledTC.add(c.value); });
            var enabledPlat = new Set();
            platChecks.forEach(function(c) { if (c.checked) enabledPlat.add(c.value); });
            var minGames = minGamesSelect ? parseInt(minGamesSelect.value, 10) : 1;

            document.querySelectorAll('.card').forEach(function(card) {
                var tc = card.getAttribute('data-time-class');
                var pl = card.getAttribute('data-platform');
                var times = parseInt(card.getAttribute('data-times'), 10) || 0;
                var tcOk = !tc || enabledTC.has(tc);
                var plOk = !pl || enabledPlat.has(pl);
                var minOk = times >= minGames;
                card.setAttribute('data-filtered', (tcOk && plOk && minOk) ? 'yes' : 'no');
                card.style.display = 'none';
            });
            shownCount = 0;
            showNextBatch();
        }

        function showNextBatch() {
            if (fetchingBoards) return;
            var passing = Array.from(document.querySelectorAll('.card[data-filtered="yes"]'));
            var end = Math.min(shownCount + PAGE_SIZE, passing.length);
            var newCards = [];
            for (var i = shownCount; i < end; i++) {
                passing[i].style.display = '';
                newCards.push(passing[i]);
            }
            shownCount = end;
            loadBoards(newCards);
        }

        function loadBoards(cards) {
            var specs = [];
            var targets = [];
            cards.forEach(function(card) {
                var bestSlot = card.querySelector('.board-best');
                var playedSlot = card.querySelector('.board-played');
                if (bestSlot && bestSlot.querySelector('.board-spinner')) {
                    var fen = card.getAttribute('data-fen');
                    var color = card.getAttribute('data-color');
                    specs.push({fen: fen, move: card.getAttribute('data-best-move'), color: color, arrow_color: '#22c55e'});
                    specs.push({fen: fen, move: card.getAttribute('data-played-move'), color: color, arrow_color: '#ef4444'});
                    targets.push({best: bestSlot, played: playedSlot});
                }
            });
            if (!specs.length) return;
            fetchingBoards = true;
            fetch('/api/render-boards', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(specs)
            })
            .then(function(r) { return r.json(); })
            .then(function(svgs) {
                for (var i = 0; i < targets.length; i++) {
                    targets[i].best.innerHTML = svgs[i * 2];
                    targets[i].played.innerHTML = svgs[i * 2 + 1];
                }
                fetchingBoards = false;
                showNextBatch();
            })
            .catch(function() {
                targets.forEach(function(t) { t.best.innerHTML = ''; t.played.innerHTML = ''; });
                fetchingBoards = false;
                showNextBatch();
            });
        }

        tcChecks.forEach(function(cb) { cb.addEventListener('change', applyFilters); });
        platChecks.forEach(function(cb) { cb.addEventListener('change', applyFilters); });
        if (minGamesSelect) { minGamesSelect.addEventListener('change', applyFilters); }
        applyFilters();

        window.addEventListener('scroll', function() {
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 200) {
                showNextBatch();
            }
        });

        /* Re-apply scroll after sort */
        if (select) {
            select.addEventListener('change', function() { applyFilters(); });
        }

        /* Dropdown panel toggles */
        var panels = [
            {btn: document.getElementById('filter-btn'), panel: document.getElementById('filter-panel')},
            {btn: document.getElementById('platform-btn'), panel: document.getElementById('platform-panel')},
            {btn: document.getElementById('min-games-btn'), panel: document.getElementById('min-games-panel')}
        ];
        panels.forEach(function(p) {
            if (p.btn && p.panel) {
                p.btn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    p.panel.classList.toggle('open');
                });
            }
        });
        document.addEventListener('click', function(e) {
            panels.forEach(function(p) {
                if (p.panel && !p.panel.contains(e.target) && e.target !== p.btn) {
                    p.panel.classList.remove('open');
                }
            });
        });
    })();
    </script>
</body>
</html>"""


_ENDGAME_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chess Coach - {% if chesscom_user %}{{ chesscom_user }}{% endif %}{% if chesscom_user and lichess_user %} / {% endif %}{% if lichess_user %}{{ lichess_user }}{% endif %} - Endgames</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        .layout { display: flex; min-height: 100vh; }
        .sidebar {
            width: 280px;
            background: #1e293b;
            border-right: 1px solid #334155;
            padding: 20px 0;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
            flex-shrink: 0;
        }
        .sidebar h2 {
            padding: 0 16px;
            font-size: 0.85rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            cursor: pointer;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .sidebar h2::after {
            content: "\25BE";
            font-size: 0.8rem;
            transition: transform 0.2s;
        }
        .sidebar h2.collapsed::after {
            transform: rotate(-90deg);
        }
        .section-links {
            overflow: hidden;
            transition: max-height 0.25s ease;
        }
        .section-links.collapsed {
            max-height: 0 !important;
        }
        .sidebar a {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 16px;
            color: #94a3b8;
            text-decoration: none;
            font-size: 0.9rem;
            transition: all 0.15s;
        }
        .sidebar a:hover { background: #334155; color: #e2e8f0; }
        .sidebar a.active {
            background: #1e3a5f;
            color: #60a5fa;
            border-left: 3px solid #3b82f6;
        }
        .count {
            background: #334155;
            color: #94a3b8;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
        }
        .main {
            flex: 1;
            padding: 30px 40px;
            max-width: 960px;
        }
        h1 { font-size: 1.6rem; margin-bottom: 8px; color: #f8fafc; }
        .user-badges { display: inline; }
        .user-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #334155;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 500;
            vertical-align: middle;
        }
        .user-badge + .user-badge { margin-left: 8px; }
        .user-badge svg { width: 18px; height: 18px; flex-shrink: 0; }
        a.user-badge { color: #e2e8f0; text-decoration: none; transition: background 0.15s; }
        a.user-badge:hover { background: #475569; }
        .subtitle { color: #94a3b8; margin-bottom: 24px; font-size: 0.95rem; }
        .type-label {
            font-weight: 600;
            color: #e2e8f0;
        }
        .balance-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .balance-equal { background: #334155; color: #94a3b8; }
        .balance-up { background: #14532d; color: #4ade80; }
        .balance-down { background: #450a0a; color: #f87171; }
        .pct-good { color: #4ade80; }
        .pct-bad { color: #f87171; }
        .pct-neutral { color: #94a3b8; }
        .board-spinner { text-align:center; padding:60px 0; color:#64748b; font-size:0.9rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .board-spinner::before { content:""; display:block; width:32px; height:32px; margin:0 auto 12px; border:3px solid #334155; border-top-color:#3b82f6; border-radius:50%; animation:spin .8s linear infinite; }
        .eg-card {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
            border-left: 4px solid #334155;
        }
        .eg-card-header {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }
        .eg-games {
            color: #94a3b8;
            font-size: 0.9rem;
            margin-left: auto;
        }
        .eg-stat {
            font-weight: 600;
            font-size: 0.9rem;
        }
        .eg-clock {
            font-size: 0.85rem;
            margin-left: 4px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .eg-clock-icon {
            color: #94a3b8;
        }
        .clock-you {
            background: #16a34a22;
            color: #4ade80;
            padding: 1px 5px;
            border-radius: 4px;
            font-weight: 600;
        }
        .clock-opp {
            background: #64748b22;
            color: #94a3b8;
            padding: 1px 5px;
            border-radius: 4px;
        }
        .eg-card-body {
            margin-top: 16px;
            text-align: center;
        }
        .board-panel { display: inline-block; text-align: center; }
        .board-panel h4 {
            margin-bottom: 8px;
            font-size: 0.9rem;
            color: #94a3b8;
        }
        .board-panel svg { border-radius: 4px; }
        .game-link {
            display: inline-block;
            margin-top: 10px;
            font-size: 0.85rem;
            color: #60a5fa;
            text-decoration: none;
        }
        .game-link:hover { text-decoration: underline; color: #93bbfc; }
        .eval-badge {
            display: inline-block;
            margin-top: 6px;
            padding: 2px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .eval-positive { background: #166534; color: #4ade80; }
        .eval-negative { background: #7f1d1d; color: #f87171; }
        .eval-zero     { background: #334155; color: #94a3b8; }
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
        }
    </style>
</head>
<body>
    <div class="layout">
        <nav class="sidebar">
            <h2 id="hdr-openings">Openings</h2>
            <div class="section-links" id="openings-links">
                <a href="/" {% if page == 'openings' and not filter_eco %}class="active"{% endif %}>
                    All deviations <span class="count">{{ total }}</span>
                </a>
                {% for g in groups %}
                <a href="/opening/{{ g.eco_code }}/{{ g.color }}">
                    {{ g.eco_name }} ({{ g.color }})
                    <span class="count">{{ g.count }}</span>
                </a>
                {% endfor %}
            </div>
            <h2 id="hdr-analysis" style="margin-top: 24px;">Analysis</h2>
            <div class="section-links" id="analysis-links">
                <a href="/endgames" {% if page == 'endgames' %}class="active"{% endif %}>
                    Endgames <span class="count">{{ endgame_count }}</span>
                </a>
            </div>
        </nav>
        <main class="main">
            <h1>Chess Coach: <span class="user-badges">{% if chesscom_user %}<a class="user-badge" href="https://www.chess.com/member/{{ chesscom_user }}" target="_blank" rel="noopener"><svg viewBox="0 0 96.4 144"><path fill="#81b64c" d="M48.2 0C35.4-.1 25 10.3 24.9 23.1c0 7.5 3.6 14.6 9.7 18.9L17.9 53c0 3.5.9 6.9 2.6 9.9h14.8c-.3 6.6 2.4 22.6-21.8 41.1C5 110.4 0 121.3 0 134.6c0 .6 1.3 9.4 48.2 9.4s48.2-8.8 48.2-9.4c0-13.3-5-24.3-13.4-30.7-24.2-18.5-21.5-34.5-21.8-41.1H76c1.7-3 2.6-6.4 2.6-9.8L61.8 42c10.4-7.5 12.8-21.9 5.3-32.3C62.8 3.6 55.7 0 48.2 0z"/></svg>{{ chesscom_user }}</a>{% endif %}{% if lichess_user %}<a class="user-badge" href="https://lichess.org/@/{{ lichess_user }}" target="_blank" rel="noopener"><svg viewBox="0 0 50 50"><path fill="#fff" stroke="#fff" stroke-linejoin="round" d="M38.956.5c-3.53.418-6.452.902-9.286 2.984C5.534 1.786-.692 18.533.68 29.364 3.493 50.214 31.918 55.785 41.329 41.7c-7.444 7.696-19.276 8.752-28.323 3.084C3.959 39.116-.506 27.392 4.683 17.567 9.873 7.742 18.996 4.535 29.03 6.405c2.43-1.418 5.225-3.22 7.655-3.187l-1.694 4.86 12.752 21.37c-.439 5.654-5.459 6.112-5.459 6.112-.574-1.47-1.634-2.942-4.842-6.036-3.207-3.094-17.465-10.177-15.788-16.207-2.001 6.967 10.311 14.152 14.04 17.663 3.73 3.51 5.426 6.04 5.795 6.756 0 0 9.392-2.504 7.838-8.927L37.4 7.171z"/></svg>{{ lichess_user }}</a>{% endif %}</span></h1>
            <div class="subtitle">Endgame performance &mdash; sorted by
                <select id="eg-sort-select" class="sort-select">
                    <option value="data-total" selected>Games</option>
                    <option value="data-win-pct">Win %</option>
                    <option value="data-loss-pct">Loss %</option>
                    <option value="data-draw-pct">Draw %</option>
                </select>
                <span class="filter-wrapper">
                    <button class="filter-btn" id="eg-def-btn">Definition &#9662;</button>
                    <div class="filter-panel" id="eg-def-panel">
                        <select id="eg-def-select" class="sort-select" style="width:100%">
                            {% for d in definitions %}
                            <option value="{{ d }}" {{ 'selected' if d == default_definition else '' }}>{{ d }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </span>
                <span class="filter-wrapper">
                    <button class="filter-btn" id="eg-balance-btn">Balance &#9662;</button>
                    <div class="filter-panel" id="eg-balance-panel">
                        <label><input type="checkbox" class="balance-filter" value="up" checked> Up</label>
                        <label><input type="checkbox" class="balance-filter" value="equal" checked> Equal</label>
                        <label><input type="checkbox" class="balance-filter" value="down" checked> Down</label>
                    </div>
                </span>
                <span class="filter-wrapper">
                    <button class="filter-btn" id="eg-min-games-btn">Min games &#9662;</button>
                    <div class="filter-panel" id="eg-min-games-panel">
                        <select id="eg-min-games-select" class="sort-select" style="width:100%">
                            <option value="1">1+ (all)</option>
                            <option value="2">2+</option>
                            <option value="3" selected>3+</option>
                            <option value="5">5+</option>
                            <option value="10">10+</option>
                        </select>
                    </div>
                </span></div>

            {% if stats %}
                {% for s in stats %}
                <div class="eg-card" style="display:none" data-win-pct="{{ s.win_pct }}" data-loss-pct="{{ s.loss_pct }}" data-draw-pct="{{ s.draw_pct }}" data-total="{{ s.total }}" data-balance="{{ s.balance }}" data-definition="{{ s.definition }}" data-fen="{{ s.get('example_fen', '') }}" data-color="{{ s.get('example_color', 'white') }}">
                    <div class="eg-card-header">
                        <span class="type-label">{{ s.type }}</span>
                        <span class="balance-badge balance-{{ s.balance }}">{{ s.balance }}</span>
                        <span class="eg-games">{{ s.total }} games</span>
                        <span class="eg-stat {{ 'pct-good' if s.win_pct >= 50 else 'pct-bad' if s.win_pct < 30 else 'pct-neutral' }}">W {{ s.win_pct }}%</span>
                        <span class="eg-stat {{ 'pct-bad' if s.loss_pct >= 50 else 'pct-good' if s.loss_pct < 20 else 'pct-neutral' }}">L {{ s.loss_pct }}%</span>
                        <span class="eg-stat pct-neutral">D {{ s.draw_pct }}%</span>
                        {% if s.avg_my_clock is not none %}
                        <span class="eg-clock" title="Avg time remaining when entering endgame (you / opponent)"><span class="eg-clock-icon">&#9201;</span> <span class="clock-you">{{ s.avg_my_clock_fmt }}</span><span class="clock-opp">{{ s.avg_opp_clock_fmt }}</span></span>
                        {% endif %}
                    </div>
                    {% if s.get('example_fen') %}
                    <div class="eg-card-body">
                        <div class="board-panel">
                            <h4>{% if s.example_game_url %}<a class="game-link" href="{{ s.example_game_url }}" target="_blank" rel="noopener">Example game{% if s.example_opponent_name or s.example_time_class or s.example_date %} ({% if s.example_opponent_name %}vs {{ s.example_opponent_name }}{% endif %}{% if s.example_time_class %}{% if s.example_opponent_name %}, {% endif %}{{ s.example_time_class }}{% endif %}{% if s.example_date %}{% if s.example_opponent_name or s.example_time_class %}, {% endif %}{{ s.example_date }}{% endif %}){% endif %} &rarr;</a>{% else %}Example game{% endif %}</h4>
                            <div class="board-slot eg-board"><div class="board-spinner">Loading board&hellip;</div></div>
                            {% set diff = s.get("example_material_diff", 0) %}
                            <div class="eval-badge {{ 'eval-positive' if diff > 0 else 'eval-negative' if diff < 0 else 'eval-zero' }}">
                                material {{ "+%d"|format(diff) if diff > 0 else diff }}
                            </div>
                        </div>
                        <a class="game-link" href="/endgames/all?def={{ s.definition|urlencode }}&type={{ s.type|urlencode }}&balance={{ s.balance|urlencode }}" style="margin-left: 16px;">show all games &rarr;</a>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
            <div class="empty-state">
                <h2>No endgames detected</h2>
                <p>None of the analyzed games reached an endgame position.</p>
            </div>
            {% endif %}
        </main>
    </div>

    <script>
    (function() {
        /* Sidebar accordion */
        (function() {
            var sections = [
                { hdr: document.getElementById('hdr-openings'), links: document.getElementById('openings-links') },
                { hdr: document.getElementById('hdr-analysis'), links: document.getElementById('analysis-links') }
            ];
            var activePage = '{{ page }}';
            var activeIdx = (activePage === 'endgames' || activePage === 'endgames_all') ? 1 : 0;
            sections.forEach(function(s, i) {
                if (i === activeIdx) {
                    s.links.style.maxHeight = s.links.scrollHeight + 'px';
                } else {
                    s.links.classList.add('collapsed');
                    s.hdr.classList.add('collapsed');
                }
                s.hdr.addEventListener('click', function() {
                    sections.forEach(function(other) {
                        if (other === s) {
                            var isCollapsed = other.links.classList.contains('collapsed');
                            if (isCollapsed) {
                                other.links.classList.remove('collapsed');
                                other.hdr.classList.remove('collapsed');
                                other.links.style.maxHeight = other.links.scrollHeight + 'px';
                            } else {
                                other.links.classList.add('collapsed');
                                other.hdr.classList.add('collapsed');
                            }
                        } else {
                            other.links.classList.add('collapsed');
                            other.hdr.classList.add('collapsed');
                        }
                    });
                });
            });
        })();

        /* Sort dropdown for endgame cards */
        var sortSelect = document.getElementById('eg-sort-select');
        var container = document.querySelector('.main');
        if (sortSelect && container) {
            sortSelect.addEventListener('change', function() {
                var attr = sortSelect.value;
                var cards = Array.from(container.querySelectorAll('.eg-card'));
                cards.sort(function(a, b) {
                    return parseFloat(b.getAttribute(attr)) - parseFloat(a.getAttribute(attr));
                });
                cards.forEach(function(card) { container.appendChild(card); });
            });
        }

        /* Combined filter: definition + balance checkboxes + min games */
        var balanceChecks = document.querySelectorAll('.balance-filter');
        var minSelect = document.getElementById('eg-min-games-select');
        var defSelect = document.getElementById('eg-def-select');

        /* Infinite scroll state */
        var PAGE_SIZE = 10;
        var shownCount = 0;
        var fetchingBoards = false;

        function applyFilters() {
            var selectedDef = defSelect ? defSelect.value : '';
            var enabledBalance = new Set();
            balanceChecks.forEach(function(c) { if (c.checked) enabledBalance.add(c.value); });
            var min = minSelect ? parseInt(minSelect.value, 10) : 1;

            document.querySelectorAll('.eg-card').forEach(function(card) {
                var balance = card.getAttribute('data-balance');
                var total = parseInt(card.getAttribute('data-total'), 10) || 0;
                var defn = card.getAttribute('data-definition');
                var defOk = !selectedDef || defn === selectedDef;
                var balOk = !balance || enabledBalance.has(balance);
                var minOk = total >= min;
                card.setAttribute('data-filtered', (defOk && balOk && minOk) ? 'yes' : 'no');
                card.style.display = 'none';
            });
            shownCount = 0;
            showNextBatch();
        }

        function showNextBatch() {
            if (fetchingBoards) return;
            var passing = Array.from(document.querySelectorAll('.eg-card[data-filtered="yes"]'));
            var end = Math.min(shownCount + PAGE_SIZE, passing.length);
            var newCards = [];
            for (var i = shownCount; i < end; i++) {
                passing[i].style.display = '';
                newCards.push(passing[i]);
            }
            shownCount = end;
            loadBoards(newCards);
        }

        function loadBoards(cards) {
            var specs = [];
            var targets = [];
            cards.forEach(function(card) {
                var slot = card.querySelector('.eg-board');
                if (slot && slot.querySelector('.board-spinner')) {
                    var fen = card.getAttribute('data-fen');
                    if (fen) {
                        specs.push({fen: fen, color: card.getAttribute('data-color')});
                        targets.push(slot);
                    } else {
                        slot.innerHTML = '';
                    }
                }
            });
            if (!specs.length) return;
            fetchingBoards = true;
            fetch('/api/render-boards', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(specs)
            })
            .then(function(r) { return r.json(); })
            .then(function(svgs) {
                for (var i = 0; i < targets.length; i++) {
                    targets[i].innerHTML = svgs[i];
                }
                fetchingBoards = false;
                showNextBatch();
            })
            .catch(function() {
                targets.forEach(function(t) { t.innerHTML = ''; });
                fetchingBoards = false;
                showNextBatch();
            });
        }

        balanceChecks.forEach(function(cb) { cb.addEventListener('change', applyFilters); });
        if (minSelect) { minSelect.addEventListener('change', applyFilters); }
        if (defSelect) { defSelect.addEventListener('change', applyFilters); }
        applyFilters();

        window.addEventListener('scroll', function() {
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 200) {
                showNextBatch();
            }
        });

        /* Re-apply scroll after sort */
        if (sortSelect) {
            sortSelect.addEventListener('change', function() { applyFilters(); });
        }

        /* Dropdown panel toggles */
        var panels = [
            {btn: document.getElementById('eg-def-btn'), panel: document.getElementById('eg-def-panel')},
            {btn: document.getElementById('eg-balance-btn'), panel: document.getElementById('eg-balance-panel')},
            {btn: document.getElementById('eg-min-games-btn'), panel: document.getElementById('eg-min-games-panel')}
        ];
        panels.forEach(function(p) {
            if (p.btn && p.panel) {
                p.btn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    p.panel.classList.toggle('open');
                });
            }
        });
        document.addEventListener('click', function(e) {
            panels.forEach(function(p) {
                if (p.panel && !p.panel.contains(e.target) && e.target !== p.btn) {
                    p.panel.classList.remove('open');
                }
            });
        });
    })();
    </script>
</body>
</html>"""


_ENDGAME_ALL_GAMES_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chess Coach - {% if chesscom_user %}{{ chesscom_user }}{% endif %}{% if chesscom_user and lichess_user %} / {% endif %}{% if lichess_user %}{{ lichess_user }}{% endif %} - {{ eg_type }} ({{ balance }})</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        .layout { display: flex; min-height: 100vh; }
        .sidebar {
            width: 280px;
            background: #1e293b;
            border-right: 1px solid #334155;
            padding: 20px 0;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
            flex-shrink: 0;
        }
        .sidebar h2 {
            padding: 0 16px;
            font-size: 0.85rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            cursor: pointer;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .sidebar h2::after {
            content: "\25BE";
            font-size: 0.8rem;
            transition: transform 0.2s;
        }
        .sidebar h2.collapsed::after {
            transform: rotate(-90deg);
        }
        .section-links {
            overflow: hidden;
            transition: max-height 0.25s ease;
        }
        .section-links.collapsed {
            max-height: 0 !important;
        }
        .sidebar a {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 16px;
            color: #94a3b8;
            text-decoration: none;
            font-size: 0.9rem;
            transition: all 0.15s;
        }
        .sidebar a:hover { background: #334155; color: #e2e8f0; }
        .sidebar a.active {
            background: #1e3a5f;
            color: #60a5fa;
            border-left: 3px solid #3b82f6;
        }
        .count {
            background: #334155;
            color: #94a3b8;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
        }
        .main {
            flex: 1;
            padding: 30px 40px;
            max-width: 960px;
        }
        h1 { font-size: 1.6rem; margin-bottom: 8px; color: #f8fafc; }
        .user-badges { display: inline; }
        .user-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #334155;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 500;
            vertical-align: middle;
        }
        .user-badge + .user-badge { margin-left: 8px; }
        .user-badge svg { width: 18px; height: 18px; flex-shrink: 0; }
        a.user-badge { color: #e2e8f0; text-decoration: none; transition: background 0.15s; }
        a.user-badge:hover { background: #475569; }
        .subtitle { color: #94a3b8; margin-bottom: 24px; font-size: 0.95rem; }
        .back-link {
            display: inline-block;
            margin-bottom: 16px;
            color: #60a5fa;
            text-decoration: none;
            font-size: 0.9rem;
        }
        .back-link:hover { text-decoration: underline; }
        .balance-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .balance-equal { background: #334155; color: #94a3b8; }
        .balance-up { background: #14532d; color: #4ade80; }
        .balance-down { background: #450a0a; color: #f87171; }
        .game-row {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
            display: flex;
            align-items: flex-start;
            gap: 20px;
        }
        .board-spinner { text-align:center; padding:60px 0; color:#64748b; font-size:0.9rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .board-spinner::before { content:""; display:block; width:32px; height:32px; margin:0 auto 12px; border:3px solid #334155; border-top-color:#3b82f6; border-radius:50%; animation:spin .8s linear infinite; }
        .game-board { flex-shrink: 0; text-align: center; }
        .game-board svg { border-radius: 4px; }
        .game-info { flex: 1; display: flex; flex-direction: column; gap: 8px; }
        .game-badges { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .result-tag {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .result-win { background: #166534; color: #4ade80; }
        .result-loss { background: #7f1d1d; color: #f87171; }
        .result-draw { background: #334155; color: #94a3b8; }
        .eval-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .eval-positive { background: #166534; color: #4ade80; }
        .eval-negative { background: #7f1d1d; color: #f87171; }
        .eval-zero     { background: #334155; color: #94a3b8; }
        .clock-badge {
            font-size: 0.85rem;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .clock-icon { color: #94a3b8; }
        .clock-you {
            background: #16a34a22;
            color: #4ade80;
            padding: 1px 5px;
            border-radius: 4px;
            font-weight: 600;
        }
        .clock-opp {
            background: #64748b22;
            color: #94a3b8;
            padding: 1px 5px;
            border-radius: 4px;
        }
        .game-link {
            font-size: 0.85rem;
            color: #60a5fa;
            text-decoration: none;
        }
        .game-link:hover { text-decoration: underline; color: #93bbfc; }
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
            .game-row { flex-direction: column; align-items: center; }
        }
    </style>
</head>
<body>
    <div class="layout">
        <nav class="sidebar">
            <h2 id="hdr-openings">Openings</h2>
            <div class="section-links" id="openings-links">
                <a href="/">
                    All deviations <span class="count">{{ total }}</span>
                </a>
                {% for g in groups %}
                <a href="/opening/{{ g.eco_code }}/{{ g.color }}">
                    {{ g.eco_name }} ({{ g.color }})
                    <span class="count">{{ g.count }}</span>
                </a>
                {% endfor %}
            </div>
            <h2 id="hdr-analysis" style="margin-top: 24px;">Analysis</h2>
            <div class="section-links" id="analysis-links">
                <a href="/endgames" {% if page == 'endgames_all' %}class="active"{% endif %}>
                    Endgames <span class="count">{{ endgame_count }}</span>
                </a>
            </div>
        </nav>
        <main class="main">
            <a class="back-link" href="/endgames">&larr; Back to endgames</a>
            <h1>{{ eg_type }} <span class="balance-badge balance-{{ balance }}">{{ balance }}</span></h1>
            <div class="subtitle">{{ games|length }} games &mdash; definition: {{ definition }} &mdash; sorted by most recent</div>

            {% if games %}
                {% for g in games %}
                <div class="game-row" style="display:none" data-fen="{{ g.get('fen', '') }}" data-color="{{ g.get('my_color', 'white') }}">
                    {% if g.get('fen') %}
                    <div class="game-board">
                        <div class="board-slot allgames-board"><div class="board-spinner">Loading board&hellip;</div></div>
                    </div>
                    {% endif %}
                    <div class="game-info">
                        <div class="game-badges">
                            <span class="result-tag result-{{ g.result_class }}">{{ g.my_result|upper }}</span>
                            {% set diff = g.get("material_diff", 0) %}
                            <span class="eval-badge {{ 'eval-positive' if diff > 0 else 'eval-negative' if diff < 0 else 'eval-zero' }}">
                                material {{ "+%d"|format(diff) if diff > 0 else diff }}
                            </span>
                            {% if g.my_clock_fmt %}
                            <span class="clock-badge" title="Time remaining (you / opponent)">
                                <span class="clock-icon">&#9201;</span>
                                <span class="clock-you">{{ g.my_clock_fmt }}</span>
                                {% if g.opp_clock_fmt %}<span class="clock-opp">{{ g.opp_clock_fmt }}</span>{% endif %}
                            </span>
                            {% endif %}
                        </div>
                        {% if g.deep_link %}
                        <a class="game-link" href="{{ g.deep_link }}" target="_blank" rel="noopener">view game &rarr;</a>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <h2>No games found</h2>
                    <p>No games matched this endgame type and balance.</p>
                </div>
            {% endif %}
        </main>
    </div>

    <script>
    (function() {
        /* Sidebar accordion */
        (function() {
            var sections = [
                { hdr: document.getElementById('hdr-openings'), links: document.getElementById('openings-links') },
                { hdr: document.getElementById('hdr-analysis'), links: document.getElementById('analysis-links') }
            ];
            var activeIdx = 1;
            sections.forEach(function(s, i) {
                if (i === activeIdx) {
                    s.links.style.maxHeight = s.links.scrollHeight + 'px';
                } else {
                    s.links.classList.add('collapsed');
                    s.hdr.classList.add('collapsed');
                }
                s.hdr.addEventListener('click', function() {
                    sections.forEach(function(other) {
                        if (other === s) {
                            var isCollapsed = other.links.classList.contains('collapsed');
                            if (isCollapsed) {
                                other.links.classList.remove('collapsed');
                                other.hdr.classList.remove('collapsed');
                                other.links.style.maxHeight = other.links.scrollHeight + 'px';
                            } else {
                                other.links.classList.add('collapsed');
                                other.hdr.classList.add('collapsed');
                            }
                        } else {
                            other.links.classList.add('collapsed');
                            other.hdr.classList.add('collapsed');
                        }
                    });
                });
            });
        })();

        var PAGE_SIZE = 10;
        var shownCount = 0;
        var fetchingBoards = false;
        var rows = Array.from(document.querySelectorAll('.game-row'));

        function showNextBatch() {
            if (fetchingBoards) return;
            var end = Math.min(shownCount + PAGE_SIZE, rows.length);
            var newRows = [];
            for (var i = shownCount; i < end; i++) {
                rows[i].style.display = '';
                newRows.push(rows[i]);
            }
            shownCount = end;
            loadBoards(newRows);
        }

        function loadBoards(items) {
            var specs = [];
            var targets = [];
            items.forEach(function(row) {
                var slot = row.querySelector('.allgames-board');
                if (slot && slot.querySelector('.board-spinner')) {
                    var fen = row.getAttribute('data-fen');
                    if (fen) {
                        specs.push({fen: fen, color: row.getAttribute('data-color')});
                        targets.push(slot);
                    }
                }
            });
            if (!specs.length) return;
            fetchingBoards = true;
            fetch('/api/render-boards', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(specs)
            })
            .then(function(r) { return r.json(); })
            .then(function(svgs) {
                for (var i = 0; i < targets.length; i++) {
                    targets[i].innerHTML = svgs[i];
                }
                fetchingBoards = false;
                showNextBatch();
            })
            .catch(function() {
                targets.forEach(function(t) { t.innerHTML = ''; });
                fetchingBoards = false;
                showNextBatch();
            });
        }

        showNextBatch();

        window.addEventListener('scroll', function() {
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 200) {
                showNextBatch();
            }
        });
    })();
    </script>
</body>
</html>"""
