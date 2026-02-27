#!/usr/bin/env python3
"""CLI to analyze a Chess.com player's opening repertoire via Stockfish evaluation."""

import argparse
import asyncio
import os
import re
import sys

# Add fetchers/ to import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fetchers"))

from chesscom_fetcher import ChessCom_Fetcher
from chessgame import ChessGame
from game_filter import filter_games_by_days, filter_games_by_time_class
from chessgameanalyzer import ChessGameAnalyzer
from opening_detector import OpeningDetector
from stockfish_evaluator import StockfishEvaluator
from repertoire_analyzer import RepertoireAnalyzer
from game_cache import GameCache

# Paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STOCKFISH = os.path.join(BASE_DIR, "engines", "stockfish-windows-x86-64-avx2.exe")
DEFAULT_BOOK = os.path.join(BASE_DIR, "data", "gm2001.bin")
DEFAULT_CACHE_DB = os.path.join(BASE_DIR, "data", "cache.db")


def _is_current_month(archive_url):
    """Check if an archive URL is for the current year/month."""
    from datetime import datetime, timezone
    match = re.search(r"/(\d{4})/(\d{2})$", archive_url)
    if not match:
        return True  # can't parse, treat as current (always refresh)
    year, month = int(match.group(1)), int(match.group(2))
    now = datetime.now(timezone.utc)
    return year == now.year and month == now.month


async def fetch_games(username, days, include_tc=None, exclude_tc=None,
                      cache=None, force_refresh=False):
    """Fetch and parse games from Chess.com, using cache when available."""
    fetcher = ChessCom_Fetcher(user_agent="chess_coachAI/1.0")

    print(f"Fetching archives for {username}...")
    try:
        archive_urls = await fetcher.get_archives(username)
    except Exception as e:
        print(f"Error: Could not connect to Chess.com API: {e}")
        sys.exit(1)

    raw_games = []
    cached_months = 0
    fetched_months = 0

    for url in archive_urls:
        # Use cache for completed months; always re-fetch current month
        cached_data = None
        if cache and not force_refresh:
            cached_data = cache.get_archive(url)
        if cached_data and not _is_current_month(url):
            raw_games.extend(cached_data.get("games", []))
            cached_months += 1
        else:
            try:
                month_data = await fetcher.fetch_games_by_month(url)
            except Exception as e:
                print(f"  Warning: Failed to fetch {url}: {e}")
                continue
            raw_games.extend(month_data.get("games", []))
            fetched_months += 1
            if cache:
                cache.save_archive(url, username, month_data)

    if cache:
        print(f"  Archives: {fetched_months} fetched from API, {cached_months} from cache")

    games = [g for g in (ChessGame.from_json(g, username) for g in raw_games) if g is not None]
    print(f"  Found {len(raw_games)} raw games, {len(games)} as {username}")

    if days > 0:
        games = filter_games_by_days(games, days)
        print(f"  Filtered to last {days} days: {len(games)} games")

    if include_tc or exclude_tc:
        before = len(games)
        games = filter_games_by_time_class(games, include=include_tc, exclude=exclude_tc)
        label = ", ".join(include_tc) if include_tc else f"excluding {', '.join(exclude_tc)}"
        print(f"  Time control filter ({label}): {before} -> {len(games)} games")

    return games


def run_analysis(games, username, stockfish_path, book_path, depth,
                 workers=1, cache=None, report=False, force_refresh=False):
    """Run opening repertoire analysis on the fetched games.

    Returns list of all OpeningEvaluation objects when report=True.
    """
    # General stats
    analyzer = ChessGameAnalyzer(username, games)
    stats = analyzer.summarize()

    if stats:
        print(f"\n--- General Stats ({stats['total_games']} games) ---")
        print(f"  Wins:   {stats['wins']} ({stats['win_percent']}%)")
        print(f"  Losses: {stats['losses']}")
        print(f"  Draws:  {stats['draws']}")
        print(f"  Win as white: {stats['win_white_percent']}% (of {stats['games_white']} games)")
        print(f"  Win as black: {stats['win_black_percent']}% (of {stats['games_black']} games)")

    # Opening repertoire analysis
    worker_label = f", {workers} workers" if workers > 1 else ""
    print(f"\n--- Opening Repertoire Analysis (depth {depth}{worker_label}) ---")
    print("  Loading opening book...")
    detector = OpeningDetector(book_path)

    # Check cache for existing evaluations
    cached_evals = []
    uncached_games = games
    if cache and not force_refresh:
        game_urls = [g.game_url for g in games if g.game_url]
        cached_map = cache.get_cached_evaluations(game_urls, depth)

        if cached_map:
            cached_evals = list(cached_map.values())
            cached_urls = set(cached_map.keys())
            uncached_games = [g for g in games if g.game_url not in cached_urls]
            print(f"  Cache: {len(cached_evals)} evaluations cached, "
                  f"{len(uncached_games)} new games to analyze")

    if not uncached_games and cached_evals:
        # Everything is cached, just aggregate
        opening_stats = {}
        for ev in cached_evals:
            RepertoireAnalyzer._aggregate(opening_stats, ev)
        new_evals = []
        print("  All games already cached, skipping engine analysis.")
    else:
        with StockfishEvaluator(stockfish_path, depth=depth) as evaluator:
            rep_analyzer = RepertoireAnalyzer(username, detector, evaluator)

            def progress(current, total):
                if current % 10 == 0 or current == total:
                    print(f"  Analyzing game {current}/{total}...", end="\r")

            opening_stats, new_evals = rep_analyzer.analyze_repertoire(
                uncached_games, progress_callback=progress, workers=workers,
                cached_evaluations=cached_evals)
            print()  # clear the \r line

    # Cache newly computed evaluations
    if cache and new_evals:
        batch = [(game.game_url, ev) for game, ev in new_evals if game.game_url]
        if batch:
            cache.save_evaluations_batch(username, depth, batch)
            print(f"  Cached {len(batch)} new evaluations.")

    if not opening_stats:
        print("  No openings detected (games may be too short or missing PGN data).")
        return [] if report else None

    # Summary with min 2 games
    lines = RepertoireAnalyzer.format_summary(opening_stats, min_games=2)
    if lines:
        print(f"\n  Openings played 2+ times (sorted best to worst):\n")
        for line in lines:
            print(f"    {line}")
    else:
        print("  No opening played more than once.")

    # Also show one-offs
    one_offs = {k: v for k, v in opening_stats.items() if v.times_played == 1}
    if one_offs:
        print(f"\n  Played once ({len(one_offs)} openings):")
        for key, s in sorted(one_offs.items(), key=lambda x: x[1].avg_eval, reverse=True):
            eval_pawns = s.avg_eval / 100.0
            sign = "+" if eval_pawns >= 0 else ""
            eco_label = f" ({s.eco_code})" if s.eco_code else ""
            print(f"    {s.eco_name}{eco_label} as {s.color}: {sign}{eval_pawns:.1f} pawns")

    # Return all evaluations for report generation
    if report:
        all_evals = list(cached_evals) + [ev for _, ev in new_evals]
        stale = sum(1 for ev in all_evals if not ev.fen_at_deviation)
        if stale:
            print(f"\n  Note: {stale} cached evaluations lack coaching data. "
                  "Run with --no-cache to re-analyze and update cache.")
        return all_evals


def main():
    parser = argparse.ArgumentParser(description="Analyze Chess.com opening repertoire with Stockfish")
    parser.add_argument("username", help="Chess.com username")
    parser.add_argument("days", nargs="?", type=int, default=0,
                        help="Only analyze games from the last N days (0 = all)")
    parser.add_argument("--depth", type=int, default=18,
                        help="Stockfish analysis depth (default: 18)")
    parser.add_argument("--stockfish", default=DEFAULT_STOCKFISH,
                        help="Path to Stockfish executable")
    parser.add_argument("--book", default=DEFAULT_BOOK,
                        help="Path to polyglot opening book (.bin)")

    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel Stockfish instances (default: 1)")

    parser.add_argument("--no-cache", action="store_true",
                        help="Force fresh fetch and analysis (repopulates cache)")
    parser.add_argument("--report", action="store_true",
                        help="Launch coaching report web app after analysis")
    parser.add_argument("--min-times", type=int, default=1,
                        help="Only show deviations that occurred N+ times (default: 1)")

    tc_group = parser.add_mutually_exclusive_group()
    tc_group.add_argument("--include", nargs="+", metavar="TYPE",
                          choices=["bullet", "blitz", "rapid", "daily"],
                          help="Only include these time controls (bullet, blitz, rapid, daily)")
    tc_group.add_argument("--exclude", nargs="+", metavar="TYPE",
                          choices=["bullet", "blitz", "rapid", "daily"],
                          help="Exclude these time controls (bullet, blitz, rapid, daily)")
    args = parser.parse_args()

    # Validate paths
    if not os.path.isfile(args.stockfish):
        print(f"Error: Stockfish not found at {args.stockfish}")
        sys.exit(1)
    if not os.path.isfile(args.book):
        print(f"Error: Opening book not found at {args.book}")
        sys.exit(1)

    # Set up cache (always created; --no-cache skips reads but still writes)
    os.makedirs(os.path.dirname(DEFAULT_CACHE_DB), exist_ok=True)
    cache = GameCache(DEFAULT_CACHE_DB)
    force_refresh = args.no_cache

    if force_refresh:
        print("Cache: force refresh enabled (will re-fetch and re-analyze, then save to cache)")

    try:
        include_tc = set(args.include) if args.include else None
        exclude_tc = set(args.exclude) if args.exclude else None
        games = asyncio.run(fetch_games(args.username, args.days,
                                        include_tc, exclude_tc, cache=cache,
                                        force_refresh=force_refresh))

        if not games:
            print("No games found.")
            sys.exit(0)

        all_evals = run_analysis(games, args.username, args.stockfish, args.book,
                                 args.depth, args.workers, cache=cache,
                                 report=args.report,
                                 force_refresh=force_refresh)

        if args.report and all_evals:
            from report_generator import CoachingReportGenerator
            generator = CoachingReportGenerator(args.username, all_evals,
                                                   min_times=args.min_times)
            generator.run()
    finally:
        cache.close()


if __name__ == "__main__":
    main()
