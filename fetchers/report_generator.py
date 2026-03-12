# report_generator.py

import json
import threading
import webbrowser
import chess
import chess.svg
from flask import Flask, render_template_string, request, jsonify


class CoachingReportGenerator:
    """Flask web app that displays coaching recommendations with static SVG boards."""

    def __init__(self, evaluations, chesscom_user="", lichess_user="",
                 endgame_stats=None, new_games_analyzed=0):
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
        # Summary stats for the openings page
        self.total_games_analyzed = len(evaluations)
        self.avg_eval_loss_cp = (
            sum(ev.eval_loss_cp for ev in self.deviations) / len(self.deviations)
            if self.deviations else 0
        )
        # Theory Knowledge = % of games where the player never deviated
        # (either fully booked, or the opponent went out of book first)
        self.theory_knowledge_pct = (
            round(100 * sum(1 for ev in evaluations
                            if ev.is_fully_booked
                            or ev.deviating_side != ev.my_color)
                  / len(evaluations))
            if evaluations else 0
        )
        # Accuracy = % of deviations with eval loss < 50cp (minor inaccuracies)
        self.accuracy_pct = (
            round(100 * sum(1 for ev in self.deviations if ev.eval_loss_cp < 50)
                  / len(self.deviations))
            if self.deviations else 0
        )
        self.new_games_analyzed = new_games_analyzed
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
            "game_date_iso": ev.end_time.strftime("%Y-%m-%d") if ev.end_time else "",
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
                total_games_analyzed=self.total_games_analyzed,
                avg_eval_loss=round(self.avg_eval_loss_cp / 100, 2),
                theory_knowledge_pct=self.theory_knowledge_pct,
                accuracy_pct=self.accuracy_pct,
                new_games_analyzed=self.new_games_analyzed,
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
                total_games_analyzed=self.total_games_analyzed,
                avg_eval_loss=round(self.avg_eval_loss_cp / 100, 2),
                theory_knowledge_pct=self.theory_knowledge_pct,
                accuracy_pct=self.accuracy_pct,
                new_games_analyzed=self.new_games_analyzed,
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
                    entry["tc_breakdown_json"] = json.dumps(
                        s.get("tc_breakdown", {}))
                    # Compact per-game details for cross-filtering in JS
                    game_details = []
                    for g in s.get("all_games", []):
                        url = g.get("game_url", "")
                        plat = ("chesscom" if "chess.com" in url
                                else "lichess" if "lichess.org" in url
                                else "unknown")
                        et = g.get("end_time")
                        dt = (et.strftime("%Y-%m-%d")
                              if et and hasattr(et, "strftime") else "")
                        game_details.append({
                            "r": g.get("my_result", "draw"),
                            "tc": g.get("time_class", ""),
                            "p": plat,
                            "c": g.get("my_color", "white"),
                            "d": dt,
                        })
                    entry["game_details_json"] = json.dumps(game_details)
                    enriched.append(entry)
            # Summary stats for the default definition
            def_entries = [e for e in enriched
                           if e["definition"] == default_def]
            eg_total_games = sum(e["total"] for e in def_entries)
            eg_total_wins = sum(e["wins"] for e in def_entries)
            eg_total_losses = sum(e["losses"] for e in def_entries)
            eg_total_draws = sum(e["draws"] for e in def_entries)
            eg_win_pct = (round(100 * eg_total_wins / eg_total_games)
                          if eg_total_games else 0)
            eg_types_count = len(def_entries)
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
                eg_total_games=eg_total_games,
                eg_types_count=eg_types_count,
                eg_win_pct=eg_win_pct,
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
                    sidebar_filters=False,
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
                sidebar_filters=False,
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


_SIDEBAR_CSS = r"""
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            line-height: 1.6;
        }
        .layout { display: flex; min-height: 100vh; }
        .sidebar {
            width: 260px;
            background: #ffffff;
            border-right: 1px solid #e2e8f0;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }
        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 20px 20px 16px;
            border-bottom: 1px solid #e2e8f0;
            margin-bottom: 8px;
        }
        .sidebar-brand svg { width: 28px; height: 28px; flex-shrink: 0; }
        .sidebar-brand span {
            font-size: 1.2rem;
            font-weight: 700;
            color: #1e293b;
            letter-spacing: -0.3px;
        }
        .sidebar-nav {
            padding: 8px 0;
        }
        .sidebar-nav a {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 20px;
            color: #64748b;
            text-decoration: none;
            font-size: 0.9rem;
            font-weight: 500;
            border-left: 3px solid transparent;
            transition: all 0.15s;
        }
        .sidebar-nav a:hover { background: #f8fafc; color: #1e293b; }
        .sidebar-nav a.active {
            color: #f97316;
            border-left-color: #f97316;
            background: #fff7ed;
        }
        .sidebar-nav a svg { width: 18px; height: 18px; flex-shrink: 0; opacity: 0.7; }
        .sidebar-nav a.active svg { opacity: 1; }
        .sidebar-divider { height: 1px; background: #e2e8f0; margin: 8px 0; }
        .sidebar-section-label {
            font-size: 0.7rem;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 600;
            padding: 12px 20px 6px;
        }
        .sidebar-filter-group {
            padding: 6px 20px;
        }
        .sidebar-filter-label {
            font-size: 0.7rem;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 600;
            margin-bottom: 8px;
            display: block;
        }
        .sidebar-filter-group label:not(.sidebar-filter-label) {
            display: block;
            padding: 3px 0;
            font-size: 0.85rem;
            cursor: pointer;
            color: #334155;
        }
        .sidebar-filter-group input[type="checkbox"] { margin-right: 6px; }
        .sidebar-select {
            width: 100%;
            padding: 10px 12px;
            border-radius: 10px;
            border: 1px solid #e2e8f0;
            background: #f8fafc;
            color: #334155;
            font-size: 0.9rem;
            cursor: pointer;
        }
        .sidebar-select:focus { outline: none; border-color: #94a3b8; }
        .color-toggle, .tc-toggle { display: flex; border: 1px solid #d1d5db; border-radius: 6px; overflow: hidden; }
        .tc-toggle { flex-wrap: wrap; }
        .tc-btn {
            flex: 1 1 45%;
            padding: 7px 8px;
            border: none;
            border-right: 1px solid #d1d5db;
            border-bottom: 1px solid #d1d5db;
            background: #ffffff;
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }
        .tc-btn:nth-child(2n) { border-right: none; }
        .tc-btn:nth-child(n+3) { border-bottom: none; }
        .tc-btn:hover { background: #f8fafc; color: #1e293b; }
        .tc-btn.active { background: #e2e8f0; color: #1e293b; }
        .color-btn {
            flex: 1;
            padding: 7px 12px;
            border: none;
            border-right: 1px solid #d1d5db;
            background: #ffffff;
            color: #64748b;
            font-size: 0.82rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }
        .color-btn:last-child { border-right: none; }
        .color-btn:hover { background: #f8fafc; color: #1e293b; }
        .color-btn.active { background: #e2e8f0; color: #1e293b; }
        .sidebar-date {
            width: 100%;
            padding: 8px 10px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            background: #f8fafc;
            color: #334155;
            font-size: 0.85rem;
            font-family: inherit;
            cursor: pointer;
        }
        .sidebar-date:focus { outline: none; border-color: #94a3b8; }
        .date-presets {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
        }
        .date-preset {
            padding: 4px 10px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            background: #ffffff;
            color: #64748b;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.15s;
        }
        .date-preset:hover { border-color: #94a3b8; color: #1e293b; }
        .date-preset.active { background: #f1f5f9; color: #1e293b; border-color: #94a3b8; }
        .sidebar-range-wrap {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .sidebar-range {
            flex: 1;
            -webkit-appearance: none;
            height: 4px;
            border-radius: 2px;
            background: #e2e8f0;
            outline: none;
        }
        .sidebar-range::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 16px; height: 16px;
            border-radius: 50%;
            background: #f97316;
            cursor: pointer;
            border: 2px solid #fff;
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
        }
        .sidebar-range::-moz-range-thumb {
            width: 16px; height: 16px;
            border-radius: 50%;
            background: #f97316;
            cursor: pointer;
            border: 2px solid #fff;
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
        }
        .sidebar-range-value {
            font-size: 0.85rem;
            font-weight: 600;
            color: #1e293b;
            min-width: 20px;
            text-align: right;
        }
        .sidebar-bottom {
            margin-top: auto;
            padding: 16px 20px;
            border-top: 1px solid #e2e8f0;
        }
        .sync-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            width: 100%;
            padding: 10px 16px;
            background: #0d9488;
            color: #ffffff;
            border: none;
            border-radius: 10px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.15s;
        }
        .sync-btn:hover { background: #0f766e; }
        .sync-btn svg { width: 16px; height: 16px; }
"""

_SIDEBAR_HTML = r"""
        <nav class="sidebar">
            <div class="sidebar-brand">
                <svg viewBox="0 0 96.4 144"><path fill="#f97316" d="M48.2 0C35.4-.1 25 10.3 24.9 23.1c0 7.5 3.6 14.6 9.7 18.9L17.9 53c0 3.5.9 6.9 2.6 9.9h14.8c-.3 6.6 2.4 22.6-21.8 41.1C5 110.4 0 121.3 0 134.6c0 .6 1.3 9.4 48.2 9.4s48.2-8.8 48.2-9.4c0-13.3-5-24.3-13.4-30.7-24.2-18.5-21.5-34.5-21.8-41.1H76c1.7-3 2.6-6.4 2.6-9.8L61.8 42c10.4-7.5 12.8-21.9 5.3-32.3C62.8 3.6 55.7 0 48.2 0z"/></svg>
                <span>Chessalyzer</span>
            </div>
            <div class="sidebar-nav">
                <a href="/" {% if page == 'openings' %}class="active"{% endif %}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                    Openings
                </a>
                <a href="/endgames" {% if page in ('endgames', 'endgames_all') %}class="active"{% endif %}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                    Endgames
                </a>
            </div>
            <div class="sidebar-divider"></div>
            {% if sidebar_filters != false %}
            <div class="sidebar-section-label">Filters</div>
            <div class="sidebar-filter-group">
                <label class="sidebar-filter-label">Platform</label>
                <select id="platform-select" class="sidebar-select">
                    <option value="all">All Platforms</option>
                    <option value="chesscom">Chess.com</option>
                    <option value="lichess">Lichess</option>
                </select>
            </div>
            <div class="sidebar-filter-group">
                <label class="sidebar-filter-label">Time Control</label>
                <div class="tc-toggle">
                    <button class="tc-btn" data-tc-filter="bullet">Bullet</button>
                    <button class="tc-btn active" data-tc-filter="blitz">Blitz</button>
                    <button class="tc-btn active" data-tc-filter="rapid">Rapid</button>
                    <button class="tc-btn" data-tc-filter="daily">Daily</button>
                </div>
            </div>
            <div class="sidebar-filter-group">
                <label class="sidebar-filter-label">Playing As</label>
                <div class="color-toggle">
                    <button class="color-btn active" data-color-filter="white">White</button>
                    <button class="color-btn" data-color-filter="black">Black</button>
                </div>
            </div>
            <div class="sidebar-filter-group">
                <label class="sidebar-filter-label">Min. Games: <span id="min-games-value">3</span></label>
                <div class="sidebar-range-wrap">
                    <input type="range" id="min-games-range" class="sidebar-range" min="1" max="20" value="3">
                </div>
            </div>
            <div class="sidebar-filter-group">
                <label class="sidebar-filter-label">From</label>
                <input type="date" id="date-from" class="sidebar-date">
                <div class="date-presets">
                    <button class="date-preset active" data-days="">All-time</button>
                    <button class="date-preset" data-days="7">Last week</button>
                    <button class="date-preset" data-days="180">6 months</button>
                    <button class="date-preset" data-days="365">Last year</button>
                </div>
            </div>
            {% endif %}
            <div class="sidebar-bottom">
                <button class="sync-btn" onclick="window.location.reload()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                    Sync Games
                </button>
            </div>
        </nav>
        <script>
        /* Persist sidebar filter state across page navigation */
        function saveFilterState() {
            var state = {};
            var plat = document.getElementById('platform-select');
            if (plat) state.platform = plat.value;
            var tc = [];
            document.querySelectorAll('.tc-btn').forEach(function(b) {
                if (b.classList.contains('active')) tc.push(b.getAttribute('data-tc-filter'));
            });
            state.tc = tc;
            var colors = [];
            document.querySelectorAll('.color-btn').forEach(function(b) {
                if (b.classList.contains('active')) colors.push(b.getAttribute('data-color-filter'));
            });
            state.colors = colors;
            var range = document.getElementById('min-games-range');
            if (range) state.minGames = range.value;
            var dateFrom = document.getElementById('date-from');
            if (dateFrom) state.dateFrom = dateFrom.value;
            var activePreset = document.querySelector('.date-preset.active');
            state.dateDays = activePreset ? (activePreset.getAttribute('data-days') || '') : '';
            try { sessionStorage.setItem('_filters', JSON.stringify(state)); } catch(e) {}
        }
        function restoreFilterState() {
            var raw;
            try { raw = sessionStorage.getItem('_filters'); } catch(e) {}
            if (!raw) return false;
            var state;
            try { state = JSON.parse(raw); } catch(e) { return false; }
            var plat = document.getElementById('platform-select');
            if (plat && state.platform) plat.value = state.platform;
            if (state.tc) {
                var tcSet = new Set(state.tc);
                document.querySelectorAll('.tc-btn').forEach(function(b) {
                    var v = b.getAttribute('data-tc-filter');
                    if (tcSet.has(v)) b.classList.add('active');
                    else b.classList.remove('active');
                });
            }
            if (state.colors) {
                var cSet = new Set(state.colors);
                document.querySelectorAll('.color-btn').forEach(function(b) {
                    var v = b.getAttribute('data-color-filter');
                    if (cSet.has(v)) b.classList.add('active');
                    else b.classList.remove('active');
                });
            }
            var range = document.getElementById('min-games-range');
            var rangeLabel = document.getElementById('min-games-value');
            if (range && state.minGames) { range.value = state.minGames; if (rangeLabel) rangeLabel.textContent = state.minGames; }
            var dateFrom = document.getElementById('date-from');
            if (dateFrom && state.dateFrom !== undefined) dateFrom.value = state.dateFrom;
            if (state.dateDays !== undefined) {
                document.querySelectorAll('.date-preset').forEach(function(b) {
                    var d = b.getAttribute('data-days') || '';
                    if (d === state.dateDays) b.classList.add('active');
                    else b.classList.remove('active');
                });
            }
            return true;
        }
        </script>
"""

_MAIN_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chess Coach - {% if chesscom_user %}{{ chesscom_user }}{% endif %}{% if chesscom_user and lichess_user %} / {% endif %}{% if lichess_user %}{{ lichess_user }}{% endif %}</title>
    <style>
""" + _SIDEBAR_CSS + r"""
        .main {
            flex: 1;
            padding: 32px;
            max-width: 960px;
        }
        h1 { font-size: 1.8rem; color: #1e293b; margin-bottom: 8px; }
        .user-badges { display: inline; }
        .user-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #f1f5f9;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 500;
            vertical-align: middle;
        }
        .user-badge + .user-badge { margin-left: 8px; }
        .user-badge svg { width: 18px; height: 18px; flex-shrink: 0; }
        a.user-badge { color: #1e293b; text-decoration: none; transition: background 0.15s; }
        a.user-badge:hover { background: #e2e8f0; }
        .subtitle { color: #64748b; margin-bottom: 32px; font-size: 0.95rem; }
        .board-spinner { text-align:center; padding:60px 0; color:#94a3b8; font-size:0.9rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .board-spinner::before { content:""; display:block; width:32px; height:32px; margin:0 auto 12px; border:3px solid #e2e8f0; border-top-color:#3b82f6; border-radius:50%; animation:spin .8s linear infinite; }
        .card {
            background: #ffffff;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            border-left: 4px solid #f97316;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
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
        .card-title { font-size: 1.15rem; font-weight: 600; color: #1e293b; }
        .eco-badge {
            background: #f1f5f9;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            color: #64748b;
        }
        .eval-badges { display: flex; gap: 8px; align-items: center; }
        .eval-badge {
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.95rem;
        }
        .eval-badge.bad { background: #fef2f2; color: #dc2626; }
        .eval-badge.good { background: #f0fdf4; color: #16a34a; }
        .eval-badge-secondary {
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            background: #f1f5f9;
            color: #64748b;
        }
        .result-badge {
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .result-badge.win-high { background: #f0fdf4; color: #16a34a; }
        .result-badge.win-low { background: #fef2f2; color: #dc2626; }
        /* --- Static SVG fallback boards --- */
        .boards {
            display: flex;
            gap: 24px;
            justify-content: center;
            flex-wrap: wrap;
            margin: 16px 0;
        }
        .board-panel { text-align: center; }
        .board-panel h4 { margin-bottom: 8px; font-size: 0.95rem; color: #64748b; }
        .board-panel h4.best { color: #16a34a; }
        .board-panel h4.played { color: #dc2626; }
        .board-panel svg { border-radius: 4px; }
        .meta { margin-top: 12px; font-size: 0.9rem; color: #64748b; }
        .times-badge {
            background: #f1f5f9;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            color: #64748b;
        }
        .times-badge.recurring { background: #e0e7ff; color: #4338ca; }
        .recommendation {
            margin-top: 12px;
            padding: 10px 16px;
            background: #f0fdf4;
            border-radius: 8px;
            color: #15803d;
            font-size: 1rem;
        }
        .recommendation strong { color: #16a34a; }
        .game-link {
            display: inline-block;
            margin-top: 8px;
            font-size: 0.85rem;
            color: #2563eb;
            text-decoration: none;
        }
        .game-link:hover { text-decoration: underline; color: #1d4ed8; }
        .sort-controls { display: inline; }
        .sort-select {
            background: #ffffff;
            color: #334155;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 0.9rem;
            cursor: pointer;
        }
        .sort-select:hover { border-color: #3b82f6; }
        .filter-wrapper {
            display: inline-block;
            position: relative;
            margin-left: 12px;
        }
        .filter-btn {
            background: #ffffff;
            color: #334155;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.9rem;
            cursor: pointer;
        }
        .filter-btn:hover { border-color: #3b82f6; }
        .filter-panel {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            margin-top: 4px;
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 8px 12px;
            z-index: 100;
            min-width: 140px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .filter-panel.open { display: block; }
        .filter-panel label {
            display: block;
            padding: 4px 0;
            font-size: 0.85rem;
            color: #334155;
            cursor: pointer;
        }
        .filter-panel input[type="checkbox"] { margin-right: 6px; }
        .stats-bar { display: flex; gap: 16px; margin-bottom: 28px; }
        .stat-card {
            flex: 1;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 16px 20px;
            text-align: center;
        }
        .stat-card.stat-card-games {
            text-align: left;
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
        }
        .stat-card-games .stat-icon {
            width: 40px; height: 40px;
            background: #eff6ff;
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0;
            margin-right: -4px;
        }
        .stat-card-games .stat-icon svg { width: 22px; height: 22px; }
        .stat-card-games .stat-delta {
            display: flex; align-items: center; gap: 4px;
            font-size: 0.75rem; margin-top: 4px;
        }
        .stat-card-games .stat-delta.positive { color: #16a34a; }
        .stat-card-games .stat-delta.neutral { color: #94a3b8; }
        .stat-value { font-size: 1.8rem; font-weight: 700; color: #1e293b; }
        .stat-label { font-size: 0.8rem; color: #64748b; margin-top: 4px; }
        .donut-card { display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .donut-chart { display: block; }
        .empty-state { text-align: center; padding: 80px 20px; color: #94a3b8; }
        .empty-state h2 { color: #64748b; margin-bottom: 12px; }
        @media (max-width: 768px) {
            .layout { flex-direction: column; }
            .sidebar {
                width: 100%;
                height: auto;
                position: static;
                border-right: none;
                border-bottom: 1px solid #e2e8f0;
            }
            .boards { flex-direction: column; align-items: center; }
            .stats-bar { flex-direction: column; }
        }
    </style>
</head>
<body>
    <div class="layout">
""" + _SIDEBAR_HTML + r"""
        <main class="main">
            <h1>Chess Coach: <span class="user-badges">{% if chesscom_user %}<a class="user-badge" href="https://www.chess.com/member/{{ chesscom_user }}" target="_blank" rel="noopener"><svg viewBox="0 0 96.4 144"><path fill="#81b64c" d="M48.2 0C35.4-.1 25 10.3 24.9 23.1c0 7.5 3.6 14.6 9.7 18.9L17.9 53c0 3.5.9 6.9 2.6 9.9h14.8c-.3 6.6 2.4 22.6-21.8 41.1C5 110.4 0 121.3 0 134.6c0 .6 1.3 9.4 48.2 9.4s48.2-8.8 48.2-9.4c0-13.3-5-24.3-13.4-30.7-24.2-18.5-21.5-34.5-21.8-41.1H76c1.7-3 2.6-6.4 2.6-9.8L61.8 42c10.4-7.5 12.8-21.9 5.3-32.3C62.8 3.6 55.7 0 48.2 0z"/></svg>{{ chesscom_user }}</a>{% endif %}{% if lichess_user %}<a class="user-badge" href="https://lichess.org/@/{{ lichess_user }}" target="_blank" rel="noopener"><svg viewBox="0 0 50 50"><path fill="#000" stroke="#000" stroke-linejoin="round" d="M38.956.5c-3.53.418-6.452.902-9.286 2.984C5.534 1.786-.692 18.533.68 29.364 3.493 50.214 31.918 55.785 41.329 41.7c-7.444 7.696-19.276 8.752-28.323 3.084C3.959 39.116-.506 27.392 4.683 17.567 9.873 7.742 18.996 4.535 29.03 6.405c2.43-1.418 5.225-3.22 7.655-3.187l-1.694 4.86 12.752 21.37c-.439 5.654-5.459 6.112-5.459 6.112-.574-1.47-1.634-2.942-4.842-6.036-3.207-3.094-17.465-10.177-15.788-16.207-2.001 6.967 10.311 14.152 14.04 17.663 3.73 3.51 5.426 6.04 5.795 6.756 0 0 9.392-2.504 7.838-8.927L37.4 7.171z"/></svg>{{ lichess_user }}</a>{% endif %}</span></h1>
            {% if filter_eco %}
            <div class="subtitle">Showing {{ items|length }} deviations for {{ filter_eco }} as {{ filter_color }} &mdash; sorted by
                <select id="sort-select" class="sort-select">
                    <option value="eval-loss">Biggest mistake</option>
                    <option value="loss-pct">Loss %</option>
                </select></div>
            {% else %}
            <div class="subtitle">{{ items|length }} positions where you deviated from book/engine &mdash; sorted by
                <select id="sort-select" class="sort-select">
                    <option value="eval-loss">Biggest mistake</option>
                    <option value="loss-pct">Loss %</option>
                </select></div>
            {% endif %}

            <div class="stats-bar">
                <div class="stat-card stat-card-games">
                    <div>
                        <div class="stat-label">Total Games Analyzed</div>
                        <div class="stat-value">{{ "{:,}".format(total_games_analyzed) }}</div>
                        {% if new_games_analyzed > 0 %}
                        <div class="stat-delta positive">
                            <svg viewBox="0 0 12 12" width="12" height="12"><path d="M6 2 L10 7 H7 V10 H5 V7 H2 Z" fill="currentColor"/></svg>
                            {{ new_games_analyzed }} new {{ "game" if new_games_analyzed == 1 else "games" }} analyzed
                        </div>
                        {% else %}
                        <div class="stat-delta neutral">No new games to analyze</div>
                        {% endif %}
                    </div>
                    <div class="stat-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <ellipse cx="12" cy="5" rx="9" ry="3"/>
                            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                        </svg>
                    </div>
                </div>
                <div class="stat-card" title="Average centipawn loss across all your opening deviations. Lower is better.">
                    <div class="stat-value">{{ avg_eval_loss }}</div>
                    <div class="stat-label">Avg. Eval Loss</div>
                </div>
                <div class="stat-card" title="Percentage of games where you never deviated from book — either the game stayed fully in theory, or your opponent left book first.">
                    <div class="stat-value">{{ theory_knowledge_pct }}%</div>
                    <div class="stat-label">Theory Knowledge</div>
                </div>
                <div class="stat-card donut-card" title="Percentage of your deviations that lost less than 0.5 pawns (50 centipawns). Higher means your opening choices are more accurate.">
                    <svg viewBox="0 0 120 120" class="donut-chart" width="100" height="100">
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" stroke-width="12"/>
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#3b82f6" stroke-width="12"
                                stroke-dasharray="{{ (accuracy_pct / 100 * 314.16)|round(1) }} 314.16"
                                transform="rotate(-90 60 60)" stroke-linecap="round"/>
                        <text x="60" y="60" text-anchor="middle" dominant-baseline="central" font-size="20" font-weight="700"
                              fill="#1e293b">{{ accuracy_pct }}%</text>
                    </svg>
                    <div class="stat-label">Accuracy Rate</div>
                </div>
            </div>

            {% if items %}
                {% for item in items %}
                <div class="card {{ 'positive' if item.eval_loss_class == 'good' else '' }}" style="display:none" data-eval-loss="{{ item.eval_loss_raw }}" data-loss-pct="{{ item.loss_pct }}" data-time-class="{{ item.time_class }}" data-platform="{{ item.platform }}" data-times="{{ item.times_played }}" data-fen="{{ item.fen }}" data-best-move="{{ item.best_move_uci }}" data-played-move="{{ item.played_move_uci }}" data-color="{{ item.color }}" data-date="{{ item.game_date_iso }}">
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
            <div id="no-results" class="empty-state" style="display:none">
                <p>No openings match the selected filters.</p>
            </div>
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
        /* ECO search — filters sidebar opening links */
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

        /* Playing As color filter (toggle: both active = show all) */
        var colorBtns = document.querySelectorAll('.color-btn');
        colorBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                var otherActive = Array.from(colorBtns).some(function(b) {
                    return b !== btn && b.classList.contains('active');
                });
                if (btn.classList.contains('active') && !otherActive) return;
                btn.classList.toggle('active');
                applyFilters();
            });
        });

        /* Time control multi-select toggle */
        var tcBtns = document.querySelectorAll('.tc-btn');
        tcBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                btn.classList.toggle('active');
                applyFilters();
            });
        });

        /* Platform dropdown */
        var platformSelect = document.getElementById('platform-select');

        /* Min games range slider */
        var minGamesRange = document.getElementById('min-games-range');
        var minGamesValue = document.getElementById('min-games-value');
        if (minGamesRange && minGamesValue) {
            minGamesRange.addEventListener('input', function() {
                minGamesValue.textContent = minGamesRange.value;
                applyFilters();
            });
        }

        /* Date filter */
        var dateFrom = document.getElementById('date-from');
        var datePresets = document.querySelectorAll('.date-preset');
        datePresets.forEach(function(btn) {
            btn.addEventListener('click', function() {
                datePresets.forEach(function(b) { b.classList.remove('active'); });
                btn.classList.add('active');
                var days = btn.getAttribute('data-days');
                if (days) {
                    var d = new Date();
                    d.setDate(d.getDate() - parseInt(days, 10));
                    var mm = String(d.getMonth() + 1).padStart(2, '0');
                    var dd = String(d.getDate()).padStart(2, '0');
                    dateFrom.value = d.getFullYear() + '-' + mm + '-' + dd;
                } else {
                    dateFrom.value = '';
                }
                applyFilters();
            });
        });
        if (dateFrom) {
            dateFrom.addEventListener('change', function() {
                datePresets.forEach(function(b) { b.classList.remove('active'); });
                if (!dateFrom.value) {
                    datePresets[0].classList.add('active');
                }
                applyFilters();
            });
        }

        /* Infinite scroll state */
        var PAGE_SIZE = 10;
        var shownCount = 0;
        var fetchingBoards = false;

        function applyFilters() {
            var selectedPlat = platformSelect ? platformSelect.value : 'all';
            var minGames = minGamesRange ? parseInt(minGamesRange.value, 10) : 1;
            var activeColors = new Set();
            colorBtns.forEach(function(b) { if (b.classList.contains('active')) activeColors.add(b.getAttribute('data-color-filter')); });
            var enabledTC = new Set();
            tcBtns.forEach(function(b) { if (b.classList.contains('active')) enabledTC.add(b.getAttribute('data-tc-filter')); });
            var fromDate = dateFrom ? dateFrom.value : '';

            document.querySelectorAll('.card').forEach(function(card) {
                var pl = card.getAttribute('data-platform');
                var times = parseInt(card.getAttribute('data-times'), 10) || 0;
                var color = card.getAttribute('data-color');
                var tc = card.getAttribute('data-time-class');
                var cardDate = card.getAttribute('data-date') || '';
                var plOk = selectedPlat === 'all' || !pl || pl === selectedPlat;
                var minOk = times >= minGames;
                var colorOk = activeColors.size === 0 || activeColors.has(color);
                var tcOk = tcBtns.length === 0 || enabledTC.has(tc);
                var dateOk = !fromDate || !cardDate || cardDate >= fromDate;
                card.setAttribute('data-filtered', (plOk && minOk && colorOk && tcOk && dateOk) ? 'yes' : 'no');
                card.style.display = 'none';
            });
            shownCount = 0;
            showNextBatch();
            var noResults = document.getElementById('no-results');
            if (noResults) {
                var anyVisible = document.querySelector('.card[data-filtered="yes"]');
                noResults.style.display = anyVisible ? 'none' : '';
            }
            saveFilterState();
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

        if (platformSelect) { platformSelect.addEventListener('change', applyFilters); }

        /* Restore saved filter state or auto-escalate TC on first visit */
        var restored = restoreFilterState();
        function hasResults() { return !!document.querySelector('.card[data-filtered="yes"]'); }
        applyFilters();
        if (!restored && !hasResults() && tcBtns.length > 0) {
            var bullet = document.querySelector('.tc-btn[data-tc-filter="bullet"]');
            if (bullet && !bullet.classList.contains('active')) {
                bullet.classList.add('active');
                applyFilters();
            }
            if (!hasResults()) {
                var daily = document.querySelector('.tc-btn[data-tc-filter="daily"]');
                if (daily && !daily.classList.contains('active')) {
                    daily.classList.add('active');
                    applyFilters();
                }
            }
        }

        window.addEventListener('scroll', function() {
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 200) {
                showNextBatch();
            }
        });

        /* Re-apply after sort */
        if (select) {
            select.addEventListener('change', function() { applyFilters(); });
        }
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
""" + _SIDEBAR_CSS + r"""
        .stats-bar { display: flex; gap: 16px; margin-bottom: 28px; }
        .stat-card {
            flex: 1;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 18px 20px;
            text-align: center;
        }
        .stat-value { font-size: 1.8rem; font-weight: 700; color: #1e293b; }
        .stat-label { font-size: 0.8rem; color: #64748b; margin-top: 4px; }
        .donut-card { display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .donut-chart { display: block; }
        .count {
            background: #f1f5f9;
            color: #64748b;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
        }
        .main {
            flex: 1;
            padding: 30px 40px;
            max-width: 960px;
        }
        h1 { font-size: 1.6rem; margin-bottom: 8px; color: #1e293b; }
        .user-badges { display: inline; }
        .user-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #f1f5f9;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 500;
            vertical-align: middle;
        }
        .user-badge + .user-badge { margin-left: 8px; }
        .user-badge svg { width: 18px; height: 18px; flex-shrink: 0; }
        a.user-badge { color: #1e293b; text-decoration: none; transition: background 0.15s; }
        a.user-badge:hover { background: #e2e8f0; }
        .subtitle { color: #64748b; margin-bottom: 24px; font-size: 0.95rem; }
        .type-label {
            font-weight: 600;
            color: #1e293b;
        }
        .balance-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .balance-equal { background: #f1f5f9; color: #64748b; }
        .balance-up { background: #f0fdf4; color: #16a34a; }
        .balance-down { background: #fef2f2; color: #dc2626; }
        .pct-good { color: #16a34a; }
        .pct-bad { color: #dc2626; }
        .pct-neutral { color: #64748b; }
        .board-spinner { text-align:center; padding:60px 0; color:#94a3b8; font-size:0.9rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .board-spinner::before { content:""; display:block; width:32px; height:32px; margin:0 auto 12px; border:3px solid #e2e8f0; border-top-color:#3b82f6; border-radius:50%; animation:spin .8s linear infinite; }
        .eg-card {
            background: #ffffff;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
            border-left: 4px solid #e2e8f0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        .eg-card-header {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }
        .eg-games {
            color: #64748b;
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
            color: #64748b;
        }
        .clock-you {
            background: #dcfce7;
            color: #16a34a;
            padding: 1px 5px;
            border-radius: 4px;
            font-weight: 600;
        }
        .clock-opp {
            background: #f1f5f9;
            color: #64748b;
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
            color: #64748b;
        }
        .board-panel svg { border-radius: 4px; }
        .game-link {
            display: inline-block;
            margin-top: 10px;
            font-size: 0.85rem;
            color: #2563eb;
            text-decoration: none;
        }
        .game-link:hover { text-decoration: underline; color: #1d4ed8; }
        .eval-badge {
            display: inline-block;
            margin-top: 6px;
            padding: 2px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .eval-positive { background: #f0fdf4; color: #16a34a; }
        .eval-negative { background: #fef2f2; color: #dc2626; }
        .eval-zero     { background: #f1f5f9; color: #64748b; }
        .sort-select {
            background: #ffffff;
            color: #334155;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 0.9rem;
            cursor: pointer;
        }
        .sort-select:hover { border-color: #3b82f6; }
        .empty-state { text-align: center; padding: 80px 20px; color: #94a3b8; }
        .empty-state h2 { color: #64748b; margin-bottom: 12px; }
        @media (max-width: 768px) {
            .layout { flex-direction: column; }
            .sidebar {
                width: 100%;
                height: auto;
                position: static;
                border-right: none;
                border-bottom: 1px solid #e2e8f0;
            }
            .stats-bar { flex-direction: column; }
        }
    </style>
</head>
<body>
    <div class="layout">
""" + _SIDEBAR_HTML + r"""
        <main class="main">
            <h1>Chess Coach: <span class="user-badges">{% if chesscom_user %}<a class="user-badge" href="https://www.chess.com/member/{{ chesscom_user }}" target="_blank" rel="noopener"><svg viewBox="0 0 96.4 144"><path fill="#81b64c" d="M48.2 0C35.4-.1 25 10.3 24.9 23.1c0 7.5 3.6 14.6 9.7 18.9L17.9 53c0 3.5.9 6.9 2.6 9.9h14.8c-.3 6.6 2.4 22.6-21.8 41.1C5 110.4 0 121.3 0 134.6c0 .6 1.3 9.4 48.2 9.4s48.2-8.8 48.2-9.4c0-13.3-5-24.3-13.4-30.7-24.2-18.5-21.5-34.5-21.8-41.1H76c1.7-3 2.6-6.4 2.6-9.8L61.8 42c10.4-7.5 12.8-21.9 5.3-32.3C62.8 3.6 55.7 0 48.2 0z"/></svg>{{ chesscom_user }}</a>{% endif %}{% if lichess_user %}<a class="user-badge" href="https://lichess.org/@/{{ lichess_user }}" target="_blank" rel="noopener"><svg viewBox="0 0 50 50"><path fill="#000" stroke="#000" stroke-linejoin="round" d="M38.956.5c-3.53.418-6.452.902-9.286 2.984C5.534 1.786-.692 18.533.68 29.364 3.493 50.214 31.918 55.785 41.329 41.7c-7.444 7.696-19.276 8.752-28.323 3.084C3.959 39.116-.506 27.392 4.683 17.567 9.873 7.742 18.996 4.535 29.03 6.405c2.43-1.418 5.225-3.22 7.655-3.187l-1.694 4.86 12.752 21.37c-.439 5.654-5.459 6.112-5.459 6.112-.574-1.47-1.634-2.942-4.842-6.036-3.207-3.094-17.465-10.177-15.788-16.207-2.001 6.967 10.311 14.152 14.04 17.663 3.73 3.51 5.426 6.04 5.795 6.756 0 0 9.392-2.504 7.838-8.927L37.4 7.171z"/></svg>{{ lichess_user }}</a>{% endif %}</span></h1>
            <div class="subtitle">Endgame performance &mdash; sorted by
                <select id="eg-sort-select" class="sort-select">
                    <option value="data-total" selected>Games</option>
                    <option value="data-win-pct">Win %</option>
                    <option value="data-loss-pct">Loss %</option>
                    <option value="data-draw-pct">Draw %</option>
                </select></div>

            <div class="stats-bar">
                <div class="stat-card" title="Total endgame games across all types in the default definition.">
                    <div class="stat-value">{{ "{:,}".format(eg_total_games) }}</div>
                    <div class="stat-label">Endgame Games</div>
                </div>
                <div class="stat-card" title="Number of distinct endgame types detected (e.g. R vs R, Q vs Q).">
                    <div class="stat-value">{{ eg_types_count }}</div>
                    <div class="stat-label">Endgame Types</div>
                </div>
                <div class="stat-card donut-card" title="Overall win percentage across all endgame types.">
                    <svg viewBox="0 0 120 120" class="donut-chart" width="100" height="100">
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" stroke-width="12"/>
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#22c55e" stroke-width="12"
                                stroke-dasharray="{{ (eg_win_pct / 100 * 314.16)|round(1) }} 314.16"
                                transform="rotate(-90 60 60)" stroke-linecap="round"/>
                        <text x="60" y="60" text-anchor="middle" dominant-baseline="central" font-size="20" font-weight="700"
                              fill="#1e293b">{{ eg_win_pct }}%</text>
                    </svg>
                    <div class="stat-label">Win Rate</div>
                </div>
            </div>

            {% if stats %}
                {% for s in stats %}
                <div class="eg-card" style="display:none" data-win-pct="{{ s.win_pct }}" data-loss-pct="{{ s.loss_pct }}" data-draw-pct="{{ s.draw_pct }}" data-total="{{ s.total }}" data-balance="{{ s.balance }}" data-definition="{{ s.definition }}" data-fen="{{ s.get('example_fen', '') }}" data-color="{{ s.get('example_color', 'white') }}" data-tc-breakdown='{{ s.tc_breakdown_json|safe }}' data-game-details='{{ s.game_details_json|safe }}'>
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
                    <div class="eg-card-body" data-example-tc="{{ s.get('example_time_class', '') }}">
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
            <div id="eg-no-results" class="empty-state" style="display:none">
                <p>No endgames match the selected filters.</p>
            </div>
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

        /* Platform dropdown */
        var platformSelect = document.getElementById('platform-select');
        if (platformSelect) { platformSelect.addEventListener('change', applyFilters); }

        /* Time control multi-select toggle */
        var tcBtns = document.querySelectorAll('.tc-btn');
        tcBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                btn.classList.toggle('active');
                applyFilters();
            });
        });

        /* Playing As color filter */
        var colorBtns = document.querySelectorAll('.color-btn');
        colorBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                var otherActive = Array.from(colorBtns).some(function(b) {
                    return b !== btn && b.classList.contains('active');
                });
                if (btn.classList.contains('active') && !otherActive) return;
                btn.classList.toggle('active');
                applyFilters();
            });
        });

        /* Date filter */
        var dateFrom = document.getElementById('date-from');
        var datePresets = document.querySelectorAll('.date-preset');
        datePresets.forEach(function(btn) {
            btn.addEventListener('click', function() {
                datePresets.forEach(function(b) { b.classList.remove('active'); });
                btn.classList.add('active');
                var days = btn.getAttribute('data-days');
                if (days) {
                    var d = new Date();
                    d.setDate(d.getDate() - parseInt(days, 10));
                    var mm = String(d.getMonth() + 1).padStart(2, '0');
                    var dd = String(d.getDate()).padStart(2, '0');
                    dateFrom.value = d.getFullYear() + '-' + mm + '-' + dd;
                } else {
                    dateFrom.value = '';
                }
                applyFilters();
            });
        });
        if (dateFrom) {
            dateFrom.addEventListener('change', function() {
                datePresets.forEach(function(b) { b.classList.remove('active'); });
                if (!dateFrom.value) {
                    datePresets[0].classList.add('active');
                }
                applyFilters();
            });
        }

        /* Combined filter: definition + balance + tc + min games + platform + color + date */
        var minGamesRange = document.getElementById('min-games-range');
        var minGamesValue = document.getElementById('min-games-value');
        if (minGamesRange && minGamesValue) {
            minGamesRange.addEventListener('input', function() {
                minGamesValue.textContent = minGamesRange.value;
                applyFilters();
            });
        }
        var defSelect = document.getElementById('eg-def-select');
        var defaultDef = '{{ default_definition }}';

        /* Infinite scroll state */
        var PAGE_SIZE = 10;
        var shownCount = 0;
        var fetchingBoards = false;

        function applyFilters() {
            var selectedDef = defSelect ? defSelect.value : defaultDef;
            var enabledBalance = new Set();
            var enabledTC = new Set();
            tcBtns.forEach(function(b) { if (b.classList.contains('active')) enabledTC.add(b.getAttribute('data-tc-filter')); });
            var min = minGamesRange ? parseInt(minGamesRange.value, 10) : 1;
            var selectedPlat = platformSelect ? platformSelect.value : 'all';
            var activeColors = new Set();
            colorBtns.forEach(function(b) { if (b.classList.contains('active')) activeColors.add(b.getAttribute('data-color-filter')); });
            var fromDate = dateFrom ? dateFrom.value : '';

            document.querySelectorAll('.eg-card').forEach(function(card) {
                var balance = card.getAttribute('data-balance');
                var defn = card.getAttribute('data-definition');
                var defOk = !selectedDef || defn === selectedDef;
                var balOk = enabledBalance.size === 0 || !balance || enabledBalance.has(balance);

                /* Cross-filter from per-game details */
                var details = [];
                try { details = JSON.parse(card.getAttribute('data-game-details') || '[]'); } catch(e) {}
                var fWins = 0, fLosses = 0, fDraws = 0;
                for (var i = 0; i < details.length; i++) {
                    var g = details[i];
                    if (tcBtns.length > 0 && g.tc && !enabledTC.has(g.tc)) continue;
                    if (selectedPlat !== 'all' && g.p !== selectedPlat) continue;
                    if (activeColors.size > 0 && !activeColors.has(g.c)) continue;
                    if (fromDate && g.d && g.d < fromDate) continue;
                    if (g.r === 'win') fWins++;
                    else if (g.r === 'loss') fLosses++;
                    else fDraws++;
                }
                var fTotal = fWins + fLosses + fDraws;
                /* If no per-game details exist, fall back to card totals */
                if (details.length === 0) {
                    fTotal = parseInt(card.getAttribute('data-total'), 10) || 0;
                }
                var gamesOk = fTotal > 0;
                var minOk = fTotal >= min;

                card.setAttribute('data-filtered', (defOk && balOk && gamesOk && minOk) ? 'yes' : 'no');
                card.style.display = 'none';

                /* Hide example game if its time class is filtered out */
                var exBody = card.querySelector('.eg-card-body');
                if (exBody) {
                    var exTc = exBody.getAttribute('data-example-tc');
                    exBody.style.display = (tcBtns.length > 0 && exTc && !enabledTC.has(exTc)) ? 'none' : '';
                }

                /* Update displayed stats to reflect filtered counts */
                if (defOk && balOk && gamesOk && minOk) {
                    var winPct = fTotal ? Math.round(100 * fWins / fTotal) : 0;
                    var lossPct = fTotal ? Math.round(100 * fLosses / fTotal) : 0;
                    var drawPct = 100 - winPct - lossPct;
                    card.setAttribute('data-total', fTotal);
                    card.setAttribute('data-win-pct', winPct);
                    card.setAttribute('data-loss-pct', lossPct);
                    card.setAttribute('data-draw-pct', drawPct);
                    var gamesEl = card.querySelector('.eg-games');
                    if (gamesEl) gamesEl.textContent = fTotal + ' games';
                    var stats = card.querySelectorAll('.eg-stat');
                    if (stats.length >= 3) {
                        stats[0].textContent = 'W ' + winPct + '%';
                        stats[0].className = 'eg-stat ' + (winPct >= 50 ? 'pct-good' : winPct < 30 ? 'pct-bad' : 'pct-neutral');
                        stats[1].textContent = 'L ' + lossPct + '%';
                        stats[1].className = 'eg-stat ' + (lossPct >= 50 ? 'pct-bad' : lossPct < 20 ? 'pct-good' : 'pct-neutral');
                        stats[2].textContent = 'D ' + drawPct + '%';
                        stats[2].className = 'eg-stat pct-neutral';
                    }
                }
            });
            shownCount = 0;
            showNextBatch();
            var noResults = document.getElementById('eg-no-results');
            if (noResults) {
                var anyVisible = document.querySelector('.eg-card[data-filtered="yes"]');
                noResults.style.display = anyVisible ? 'none' : '';
            }
            saveFilterState();
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

        if (defSelect) { defSelect.addEventListener('change', applyFilters); }

        /* Restore saved filter state or auto-escalate TC on first visit */
        var restored = restoreFilterState();
        function hasResults() { return !!document.querySelector('.eg-card[data-filtered="yes"]'); }
        applyFilters();
        if (!restored && !hasResults() && tcBtns.length > 0) {
            var bullet = document.querySelector('.tc-btn[data-tc-filter="bullet"]');
            if (bullet && !bullet.classList.contains('active')) {
                bullet.classList.add('active');
                applyFilters();
            }
            if (!hasResults()) {
                var daily = document.querySelector('.tc-btn[data-tc-filter="daily"]');
                if (daily && !daily.classList.contains('active')) {
                    daily.classList.add('active');
                    applyFilters();
                }
            }
        }

        window.addEventListener('scroll', function() {
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 200) {
                showNextBatch();
            }
        });

        /* Re-apply after sort */
        if (sortSelect) {
            sortSelect.addEventListener('change', function() { applyFilters(); });
        }
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
""" + _SIDEBAR_CSS + r"""
        .main {
            flex: 1;
            padding: 30px 40px;
            max-width: 960px;
        }
        h1 { font-size: 1.6rem; margin-bottom: 8px; color: #1e293b; }
        .user-badges { display: inline; }
        .user-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #f1f5f9;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 500;
            vertical-align: middle;
        }
        .user-badge + .user-badge { margin-left: 8px; }
        .user-badge svg { width: 18px; height: 18px; flex-shrink: 0; }
        a.user-badge { color: #1e293b; text-decoration: none; transition: background 0.15s; }
        a.user-badge:hover { background: #e2e8f0; }
        .subtitle { color: #64748b; margin-bottom: 24px; font-size: 0.95rem; }
        .back-link {
            display: inline-block;
            margin-bottom: 16px;
            color: #2563eb;
            text-decoration: none;
            font-size: 0.9rem;
        }
        .back-link:hover { text-decoration: underline; }
        .filter-wrapper { display: inline-block; position: relative; }
        .filter-btn {
            background: #ffffff; color: #334155; border: 1px solid #d1d5db;
            border-radius: 8px; padding: 6px 14px; font-size: 0.85rem; cursor: pointer;
        }
        .filter-btn:hover { border-color: #3b82f6; }
        .filter-panel {
            display: none; position: absolute; top: 100%; left: 0; margin-top: 4px;
            background: #ffffff; border: 1px solid #d1d5db; border-radius: 8px;
            padding: 8px 12px; z-index: 100; min-width: 140px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .filter-panel.open { display: block; }
        .filter-panel label { display: block; padding: 4px 0; font-size: 0.85rem; cursor: pointer; white-space: nowrap; color: #334155; }
        .filter-panel input[type="checkbox"] { margin-right: 6px; }
        .balance-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .balance-equal { background: #f1f5f9; color: #64748b; }
        .balance-up { background: #f0fdf4; color: #16a34a; }
        .balance-down { background: #fef2f2; color: #dc2626; }
        .game-row {
            background: #ffffff;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
            display: flex;
            align-items: flex-start;
            gap: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        .board-spinner { text-align:center; padding:60px 0; color:#94a3b8; font-size:0.9rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .board-spinner::before { content:""; display:block; width:32px; height:32px; margin:0 auto 12px; border:3px solid #e2e8f0; border-top-color:#3b82f6; border-radius:50%; animation:spin .8s linear infinite; }
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
        .result-win { background: #f0fdf4; color: #16a34a; }
        .result-loss { background: #fef2f2; color: #dc2626; }
        .result-draw { background: #f1f5f9; color: #64748b; }
        .eval-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .eval-positive { background: #f0fdf4; color: #16a34a; }
        .eval-negative { background: #fef2f2; color: #dc2626; }
        .eval-zero     { background: #f1f5f9; color: #64748b; }
        .clock-badge {
            font-size: 0.85rem;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .clock-icon { color: #64748b; }
        .clock-you {
            background: #dcfce7;
            color: #16a34a;
            padding: 1px 5px;
            border-radius: 4px;
            font-weight: 600;
        }
        .clock-opp {
            background: #f1f5f9;
            color: #64748b;
            padding: 1px 5px;
            border-radius: 4px;
        }
        .game-link {
            font-size: 0.85rem;
            color: #2563eb;
            text-decoration: none;
        }
        .game-link:hover { text-decoration: underline; color: #1d4ed8; }
        .empty-state { text-align: center; padding: 80px 20px; color: #94a3b8; }
        .empty-state h2 { color: #64748b; margin-bottom: 12px; }
        @media (max-width: 768px) {
            .layout { flex-direction: column; }
            .sidebar {
                width: 100%;
                height: auto;
                position: static;
                border-right: none;
                border-bottom: 1px solid #e2e8f0;
            }
            .game-row { flex-direction: column; align-items: center; }
        }
    </style>
</head>
<body>
    <div class="layout">
""" + _SIDEBAR_HTML + r"""
        <main class="main">
            <a class="back-link" href="/endgames">&larr; Back to endgames</a>
            <h1>{{ eg_type }} <span class="balance-badge balance-{{ balance }}">{{ balance }}</span></h1>
            <div class="subtitle"><span id="ag-game-count">{{ games|length }}</span> games &mdash; definition: {{ definition }} &mdash; sorted by most recent</div>
            <div style="margin-bottom:16px">
                <span class="filter-wrapper">
                    <button class="filter-btn" id="ag-tc-btn">Time class &#9662;</button>
                    <div class="filter-panel" id="ag-tc-panel">
                        <label><input type="checkbox" class="ag-tc-filter" value="bullet" checked> Bullet</label>
                        <label><input type="checkbox" class="ag-tc-filter" value="blitz" checked> Blitz</label>
                        <label><input type="checkbox" class="ag-tc-filter" value="rapid" checked> Rapid</label>
                        <label><input type="checkbox" class="ag-tc-filter" value="daily" checked> Daily</label>
                    </div>
                </span>
            </div>

            {% if games %}
                {% for g in games %}
                <div class="game-row" style="display:none" data-fen="{{ g.get('fen', '') }}" data-color="{{ g.get('my_color', 'white') }}" data-time-class="{{ g.get('time_class', '') }}">
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
            <div id="ag-no-results" class="empty-state" style="display:none">
                <p>No games match the selected filters.</p>
            </div>
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
        var PAGE_SIZE = 10;
        var shownCount = 0;
        var fetchingBoards = false;
        var allRows = Array.from(document.querySelectorAll('.game-row'));
        var agTcChecks = document.querySelectorAll('.ag-tc-filter');
        var gameCountEl = document.getElementById('ag-game-count');

        function applyFilters() {
            var enabledTC = new Set();
            agTcChecks.forEach(function(c) { if (c.checked) enabledTC.add(c.value); });
            var visibleCount = 0;
            allRows.forEach(function(row) {
                var tc = row.getAttribute('data-time-class');
                var ok = !tc || enabledTC.has(tc);
                row.setAttribute('data-filtered', ok ? 'yes' : 'no');
                row.style.display = 'none';
                if (ok) visibleCount++;
            });
            if (gameCountEl) gameCountEl.textContent = visibleCount;
            shownCount = 0;
            showNextBatch();
            var noResults = document.getElementById('ag-no-results');
            if (noResults) noResults.style.display = visibleCount > 0 ? 'none' : '';
        }

        agTcChecks.forEach(function(cb) { cb.addEventListener('change', applyFilters); });

        function showNextBatch() {
            if (fetchingBoards) return;
            var passing = allRows.filter(function(r) { return r.getAttribute('data-filtered') === 'yes'; });
            var end = Math.min(shownCount + PAGE_SIZE, passing.length);
            var newRows = [];
            for (var i = shownCount; i < end; i++) {
                passing[i].style.display = '';
                newRows.push(passing[i]);
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

        applyFilters();

        window.addEventListener('scroll', function() {
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 200) {
                showNextBatch();
            }
        });

        /* Dropdown panel toggle */
        var agTcBtn = document.getElementById('ag-tc-btn');
        var agTcPanel = document.getElementById('ag-tc-panel');
        if (agTcBtn && agTcPanel) {
            agTcBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                agTcPanel.classList.toggle('open');
            });
            document.addEventListener('click', function() { agTcPanel.classList.remove('open'); });
        }
    })();
    </script>
</body>
</html>"""
