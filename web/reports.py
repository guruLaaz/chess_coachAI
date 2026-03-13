"""Report rendering logic for the web app.

Helper functions and data-loading logic for the web routes to read
analysis results from PostgreSQL.
"""

import json
import logging

import chess
import chess.svg

import db.queries as dbq

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def group_deviations(candidates):
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


def render_board_svg(fen, move_uci, color, arrow_color):
    """Render an SVG chessboard with an arrow for a move."""
    board = chess.Board(fen)
    orientation = chess.WHITE if color == "white" else chess.BLACK
    arrows = []
    if move_uci:
        move = chess.Move.from_uci(move_uci)
        arrows = [chess.svg.Arrow(move.from_square, move.to_square, color=arrow_color)]
    return chess.svg.board(board, arrows=arrows, orientation=orientation, size=350)


def move_to_san(fen, move_uci):
    """Convert a UCI move to SAN notation given a FEN position."""
    if not move_uci:
        return "N/A"
    board = chess.Board(fen)
    try:
        move = chess.Move.from_uci(move_uci)
        return board.san(move)
    except (ValueError, chess.IllegalMoveError):
        return move_uci


def format_clock(seconds):
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


def ply_to_move_label(ply, color):
    """Convert a 0-based ply to a human-readable move number."""
    move_num = (ply // 2) + 1
    if color == "white" or ply % 2 == 0:
        return f"{move_num}."
    return f"{move_num}..."


def format_date(dt):
    """Format a datetime as 'Month D, YYYY' (e.g. 'September 5, 2025')."""
    if dt is None:
        return ""
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def prepare_deviation(ev, deviation_counts, deviation_results):
    """Prepare template data for a single deviation."""
    played_san = move_to_san(ev.fen_at_deviation, ev.played_move_uci)
    best_san = move_to_san(ev.fen_at_deviation, ev.best_move_uci)

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
    loss_display = (
        f"-{eval_loss_pawns:.1f}" if eval_loss_pawns > 0
        else f"+{abs(eval_loss_pawns):.1f}"
    )

    # Static eval display (secondary)
    eval_pawns = ev.eval_cp / 100.0
    sign = "+" if eval_pawns >= 0 else ""

    move_label = ply_to_move_label(ev.deviation_ply, ev.my_color)

    key = (ev.fen_at_deviation, ev.played_move_uci)
    count = deviation_counts.get(key, 1)

    # Win/loss/draw aggregation
    r = deviation_results.get(key, {"win": 0, "loss": 0, "draw": 0})
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
        "platform": (
            "lichess" if "lichess.org" in ev.game_url
            else "chesscom" if ev.game_url
            else "unknown"
        ),
        "opponent_name": ev.opponent_name or "",
        "game_date": format_date(ev.end_time),
        "game_date_iso": (
            ev.end_time.strftime("%Y-%m-%d") if ev.end_time else ""
        ),
    }


def get_opening_groups(deviations):
    """Group deviations by opening+color for sidebar navigation."""
    groups = {}
    for ev in deviations:
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


# ---------------------------------------------------------------------------
# Data loaders (read from PostgreSQL)
# ---------------------------------------------------------------------------

def load_openings_data(chesscom_user, lichess_user):
    """Load all opening evaluation data for a user from PostgreSQL."""
    username = chesscom_user or lichess_user
    logger.debug("Loading openings data for user=%s", username)
    evaluations = dbq.get_all_evaluations_for_user(username, depth=14)

    # Filter to player deviations that have coaching data
    candidates = [
        ev for ev in evaluations
        if ev.deviating_side == ev.my_color
        and ev.fen_at_deviation
        and ev.played_move_uci
        and not ev.is_fully_booked
    ]

    # Group by position + played move, keep worst instance per group
    deviations, deviation_counts, deviation_results = group_deviations(
        candidates
    )

    # Sort worst first (biggest eval loss = biggest mistake)
    deviations.sort(key=lambda ev: ev.eval_loss_cp, reverse=True)

    # Summary stats
    total_games_analyzed = len(evaluations)
    avg_eval_loss_cp = (
        sum(ev.eval_loss_cp for ev in deviations) / len(deviations)
        if deviations else 0
    )
    theory_knowledge_pct = (
        round(
            100
            * sum(
                1
                for ev in evaluations
                if ev.is_fully_booked or ev.deviating_side != ev.my_color
            )
            / len(evaluations)
        )
        if evaluations
        else 0
    )
    accuracy_pct = (
        round(
            100
            * sum(1 for ev in deviations if ev.eval_loss_cp < 50)
            / len(deviations)
        )
        if deviations
        else 0
    )

    # Pre-compute item dicts
    items = [
        prepare_deviation(ev, deviation_counts, deviation_results)
        for ev in deviations
    ]
    groups = get_opening_groups(deviations)

    logger.info("Openings loaded for %s: %d evaluations, %d deviations, %d groups",
                username, total_games_analyzed, len(deviations), len(groups))

    return {
        "username": username,
        "chesscom_user": chesscom_user,
        "lichess_user": lichess_user,
        "items": items,
        "groups": groups,
        "total_games_analyzed": total_games_analyzed,
        "avg_eval_loss": round(avg_eval_loss_cp / 100, 2),
        "theory_knowledge_pct": theory_knowledge_pct,
        "accuracy_pct": accuracy_pct,
        "new_games_analyzed": 0,
    }


def load_endgames_data(chesscom_user, lichess_user):
    """Load endgame data for a user from PostgreSQL.

    Returns template-ready endgame data for the templates.
    """
    username = chesscom_user or lichess_user
    logger.debug("Loading endgames data for user=%s", username)

    # Get all game URLs for this user (from evaluations table)
    evaluations = dbq.get_all_evaluations_for_user(username, depth=14)
    game_urls = list({ev.game_url for ev in evaluations if ev.game_url})

    if not game_urls:
        logger.info("No game URLs found for endgame data (user=%s)", username)
        return {
            "username": username,
            "chesscom_user": chesscom_user,
            "lichess_user": lichess_user,
            "stats": [],
            "endgame_count": 0,
            "definitions": [],
            "default_definition": "minor-or-queen",
            "eg_total_games": 0,
            "eg_types_count": 0,
            "eg_win_pct": 0,
        }

    # Load raw endgame rows: {game_url -> {definition -> EndgameInfo|None}}
    raw = dbq.get_all_endgames_for_user(game_urls)

    # Aggregate into the same format as EndgameClassifier.aggregate_all()
    endgame_stats_by_def = _aggregate_endgames(raw)

    default_def = "minor-or-queen"
    default_stats = endgame_stats_by_def.get(default_def, [])
    endgame_count = sum(s["total"] for s in default_stats)

    # Enrich entries for template rendering
    enriched = []
    for defn, stats_list in endgame_stats_by_def.items():
        for s in stats_list:
            entry = dict(s)
            entry["definition"] = defn

            # Build deep-link URL for example game
            game_url = s.get("example_game_url", "")
            ply = s.get("example_endgame_ply", 0)
            if game_url and ply:
                if "lichess.org" in game_url:
                    entry["example_game_url"] = f"{game_url}#{ply + 1}"
                elif "chess.com" in game_url:
                    analysis_url = game_url.replace(
                        "chess.com/game/", "chess.com/analysis/game/"
                    )
                    entry["example_game_url"] = (
                        f"{analysis_url}?tab=analysis&move={ply}"
                    )

            entry["example_date"] = format_date(s.get("example_end_time"))
            entry["avg_my_clock_fmt"] = format_clock(s.get("avg_my_clock"))
            entry["avg_opp_clock_fmt"] = format_clock(s.get("avg_opp_clock"))
            entry["tc_breakdown_json"] = json.dumps(
                s.get("tc_breakdown", {})
            )

            # Compact per-game details for cross-filtering in JS
            game_details = []
            for g in s.get("all_games", []):
                url = g.get("game_url", "")
                plat = (
                    "chesscom" if "chess.com" in url
                    else "lichess" if "lichess.org" in url
                    else "unknown"
                )
                et = g.get("end_time")
                dt = (
                    et.strftime("%Y-%m-%d")
                    if et and hasattr(et, "strftime")
                    else ""
                )
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
    def_entries = [e for e in enriched if e["definition"] == default_def]
    eg_total_games = sum(e["total"] for e in def_entries)
    eg_total_wins = sum(e["wins"] for e in def_entries)
    eg_types_count = len(def_entries)
    eg_win_pct = (
        round(100 * eg_total_wins / eg_total_games)
        if eg_total_games else 0
    )

    logger.info("Endgames loaded for %s: %d game_urls, %d endgame_count, %d types",
                username, len(game_urls), endgame_count, eg_types_count)

    return {
        "username": username,
        "chesscom_user": chesscom_user,
        "lichess_user": lichess_user,
        "stats": enriched,
        "endgame_count": endgame_count,
        "definitions": list(endgame_stats_by_def.keys()),
        "default_definition": default_def,
        "eg_total_games": eg_total_games,
        "eg_types_count": eg_types_count,
        "eg_win_pct": eg_win_pct,
    }


def load_endgames_all_data(chesscom_user, lichess_user, defn, eg_type,
                           balance):
    """Load data for the endgames/all drilldown page."""
    eg_data = load_endgames_data(chesscom_user, lichess_user)

    # Find matching aggregate entry
    match = None
    for s in eg_data["stats"]:
        if (s.get("definition") == defn
                and s["type"] == eg_type
                and s["balance"] == balance):
            match = s
            break

    games = []
    if match:
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
                        "chess.com/game/", "chess.com/analysis/game/"
                    )
                    entry["deep_link"] = (
                        f"{analysis_url}?tab=analysis&move={ply}"
                    )
            elif game_url:
                entry["deep_link"] = game_url

            entry["my_clock_fmt"] = format_clock(g.get("my_clock"))
            entry["opp_clock_fmt"] = format_clock(g.get("opp_clock"))
            result = g.get("my_result", "draw")
            entry["result_class"] = (
                "win" if result == "win"
                else "loss" if result == "loss"
                else "draw"
            )
            games.append(entry)

    return {
        "username": eg_data["username"],
        "chesscom_user": chesscom_user,
        "lichess_user": lichess_user,
        "eg_type": eg_type,
        "balance": balance,
        "definition": defn,
        "games": games,
        "groups": [],
        "endgame_count": eg_data["endgame_count"],
        "total": 0,
        "page": "endgames_all",
        "sidebar_filters": False,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _aggregate_endgames(raw):
    """Aggregate raw endgame rows into the same structure as
    EndgameClassifier.aggregate_all().

    raw: dict of game_url -> {definition -> EndgameInfo or None}
    Returns: dict of definition -> list of aggregate stat dicts
    """
    # Group by (definition, endgame_type, balance)
    buckets = {}  # (defn, type, balance) -> list of info dicts
    for game_url, defs in raw.items():
        for defn, info in defs.items():
            if info is None:
                continue
            balance = _material_balance_label(info.material_diff)
            key = (defn, info.endgame_type, balance)
            if key not in buckets:
                buckets[key] = []
            buckets[key].append({
                "game_url": info.game_url or game_url,
                "fen": info.fen_at_endgame,
                "endgame_ply": info.endgame_ply,
                "my_result": info.my_result,
                "material_diff": info.material_diff or 0,
                "my_clock": info.my_clock,
                "opp_clock": info.opp_clock,
                "my_color": "white",
                "time_class": "",
                "end_time": None,
            })

    # Build per-definition result
    by_def = {}
    for (defn, etype, balance), games in buckets.items():
        total = len(games)
        wins = sum(1 for g in games if g["my_result"] == "win")
        losses = sum(1 for g in games if g["my_result"] == "loss")
        draws = total - wins - losses
        win_pct = round(100 * wins / total) if total else 0
        loss_pct = round(100 * losses / total) if total else 0
        draw_pct = 100 - win_pct - loss_pct

        # Pick example game (first one)
        example = games[0] if games else {}

        # Clock averages
        my_clocks = [g["my_clock"] for g in games if g["my_clock"] is not None]
        opp_clocks = [g["opp_clock"] for g in games
                      if g["opp_clock"] is not None]

        entry = {
            "type": etype,
            "balance": balance,
            "total": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_pct": win_pct,
            "loss_pct": loss_pct,
            "draw_pct": draw_pct,
            "example_fen": example.get("fen", ""),
            "example_game_url": example.get("game_url", ""),
            "example_color": example.get("my_color", "white"),
            "example_material_diff": example.get("material_diff", 0),
            "example_endgame_ply": example.get("endgame_ply", 0),
            "example_opponent_name": "",
            "example_time_class": example.get("time_class", ""),
            "example_end_time": example.get("end_time"),
            "avg_my_clock": (
                sum(my_clocks) / len(my_clocks) if my_clocks else None
            ),
            "avg_opp_clock": (
                sum(opp_clocks) / len(opp_clocks) if opp_clocks else None
            ),
            "all_games": games,
            "tc_breakdown": {},
        }

        if defn not in by_def:
            by_def[defn] = []
        by_def[defn].append(entry)

    # Sort each definition's list by total games descending
    for defn in by_def:
        by_def[defn].sort(key=lambda e: e["total"], reverse=True)

    return by_def


def _material_balance_label(diff):
    """Convert a numeric material diff to a balance label."""
    if diff is None or diff == 0:
        return "equal"
    return "up" if diff > 0 else "down"
