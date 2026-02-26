# repertoire_analyzer.py

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional, Callable

import chess.engine

from pgn_parser import PGNParser
from opening_detector import OpeningDetector, DeviationResult
from stockfish_evaluator import StockfishEvaluator, EvalResult


@dataclass
class OpeningEvaluation:
    """Evaluation of a single game's opening phase."""
    eco_code: Optional[str]
    eco_name: str
    my_color: str
    deviation_ply: int
    deviating_side: str
    eval_cp: int        # centipawns from player's perspective
    is_fully_booked: bool
    # Coaching data (populated when available, empty for legacy cached entries)
    fen_at_deviation: str = ""
    best_move_uci: Optional[str] = None
    played_move_uci: Optional[str] = None
    book_moves_uci: List[str] = field(default_factory=list)
    eval_loss_cp: int = 0       # centipawn loss caused by played move (positive = bad)
    game_moves_uci: List[str] = field(default_factory=list)  # full game as UCI strings


@dataclass
class OpeningStats:
    """Aggregated statistics for one opening played as one color."""
    eco_code: Optional[str]
    eco_name: str
    color: str
    times_played: int = 0
    total_eval: int = 0
    min_eval: int = 0
    max_eval: int = 0
    total_deviation_ply: int = 0
    player_deviated_count: int = 0
    evaluations: List[int] = field(default_factory=list)

    @property
    def avg_eval(self):
        if self.times_played == 0:
            return 0.0
        return round(self.total_eval / self.times_played, 1)

    @property
    def avg_deviation_ply(self):
        if self.times_played == 0:
            return 0.0
        return round(self.total_deviation_ply / self.times_played, 1)


class RepertoireAnalyzer:
    """Analyzes a player's opening repertoire using engine evaluation."""

    MIN_MOVES_FOR_ANALYSIS = 4  # skip very short games

    def __init__(self, username, opening_detector, stockfish_evaluator):
        self.username = username.lower()
        self.opening_detector = opening_detector
        self.stockfish_evaluator = stockfish_evaluator

    def _compute_eval_loss(self, deviation, eval_before_cp, evaluator, color):
        """Compute centipawn loss of the played move.

        Returns eval_before - eval_after (positive = player lost centipawns).
        Returns 0 for fully booked games or when played_move is None.
        """
        if deviation.is_fully_booked or deviation.played_move is None:
            return 0
        board_after = deviation.board_at_deviation.copy()
        board_after.push(deviation.played_move)
        eval_after = evaluator.evaluate(board_after)
        return eval_before_cp - eval_after.score_for_color(color)

    def analyze_game(self, game):
        """Analyze a single game's opening and return an OpeningEvaluation.

        Returns None if the game has no PGN or is too short.
        """
        if not game.pgn:
            return None

        moves = PGNParser.parse_moves(game.pgn)
        if not moves or len(moves) < self.MIN_MOVES_FOR_ANALYSIS:
            return None

        deviation = self.opening_detector.find_deviation(moves)
        if deviation is None:
            return None

        eval_result = self.stockfish_evaluator.evaluate(deviation.board_at_deviation)
        eval_cp = eval_result.score_for_color(game.my_color)
        eval_loss_cp = self._compute_eval_loss(
            deviation, eval_cp, self.stockfish_evaluator, game.my_color)

        eco_name = game.eco_name or "Unknown Opening"
        deviating_side = deviation.deviating_side

        return OpeningEvaluation(
            eco_code=game.eco_code,
            eco_name=eco_name,
            my_color=game.my_color,
            deviation_ply=deviation.deviation_ply,
            deviating_side=deviating_side,
            eval_cp=eval_cp,
            is_fully_booked=deviation.is_fully_booked,
            fen_at_deviation=deviation.board_at_deviation.fen(),
            best_move_uci=eval_result.best_move.uci() if eval_result.best_move else None,
            played_move_uci=deviation.played_move.uci() if deviation.played_move else None,
            book_moves_uci=[m.uci() for m in deviation.book_moves],
            eval_loss_cp=eval_loss_cp,
            game_moves_uci=[m.uci() for m in moves],
        )

    def _preprocess_game(self, game):
        """Parse PGN and find book deviation (fast, no engine needed).

        Returns (game, deviation, moves) or None if the game should be skipped.
        """
        if not game.pgn:
            return None

        moves = PGNParser.parse_moves(game.pgn)
        if not moves or len(moves) < self.MIN_MOVES_FOR_ANALYSIS:
            return None

        deviation = self.opening_detector.find_deviation(moves)
        if deviation is None:
            return None

        return (game, deviation, moves)

    @staticmethod
    def _aggregate(stats, evaluation):
        """Add a single evaluation into the stats dict."""
        key = f"{evaluation.eco_code or 'Unknown'}_{evaluation.my_color}"

        if key not in stats:
            stats[key] = OpeningStats(
                eco_code=evaluation.eco_code,
                eco_name=evaluation.eco_name,
                color=evaluation.my_color,
                times_played=0,
                total_eval=0,
                min_eval=evaluation.eval_cp,
                max_eval=evaluation.eval_cp,
                total_deviation_ply=0,
                player_deviated_count=0,
            )

        entry = stats[key]
        entry.times_played += 1
        entry.total_eval += evaluation.eval_cp
        entry.min_eval = min(entry.min_eval, evaluation.eval_cp)
        entry.max_eval = max(entry.max_eval, evaluation.eval_cp)
        entry.total_deviation_ply += evaluation.deviation_ply
        entry.evaluations.append(evaluation.eval_cp)

        if evaluation.deviating_side == evaluation.my_color:
            entry.player_deviated_count += 1

    def analyze_repertoire(self, games, progress_callback=None, workers=1,
                           cached_evaluations=None):
        """Analyze all games and return aggregated stats per opening+color.

        Args:
            games: List of ChessGame objects to analyze with engine.
            progress_callback: Optional callable(current, total) for progress.
            workers: Number of parallel Stockfish instances (default 1).
            cached_evaluations: Optional list of OpeningEvaluation objects
                (from cache) to include in aggregation without re-analyzing.

        Returns:
            Tuple of (stats_dict, new_evaluations_list):
              - stats_dict: Dict keyed by "{eco_code}_{color}" -> OpeningStats
              - new_evaluations_list: List of (game, OpeningEvaluation) for
                newly analyzed games (for caching). game objects have game_url.
        """
        stats = {}

        # Aggregate any cached evaluations first
        if cached_evaluations:
            for evaluation in cached_evaluations:
                self._aggregate(stats, evaluation)

        # Phase 1: pre-process (PGN parse + book lookup) — fast, sequential
        prepared = []
        for game in games:
            result = self._preprocess_game(game)
            if result is not None:
                prepared.append(result)

        total = len(prepared)
        if total == 0:
            if progress_callback:
                progress_callback(0, 0)
            return stats, []

        if workers <= 1:
            new_evals = self._analyze_sequential(prepared, total, progress_callback, stats)
        else:
            new_evals = self._analyze_parallel(prepared, total, progress_callback, workers, stats)

        return stats, new_evals

    def _analyze_sequential(self, prepared, total, progress_callback, stats):
        """Evaluate positions sequentially using the existing engine."""
        new_evals = []
        for i, (game, deviation, moves) in enumerate(prepared):
            if progress_callback:
                progress_callback(i + 1, total)

            eval_result = self.stockfish_evaluator.evaluate(deviation.board_at_deviation)
            eval_cp = eval_result.score_for_color(game.my_color)
            eval_loss_cp = self._compute_eval_loss(
                deviation, eval_cp, self.stockfish_evaluator, game.my_color)
            evaluation = self._make_evaluation(
                game, deviation, eval_result, eval_loss_cp, moves)
            self._aggregate(stats, evaluation)
            new_evals.append((game, evaluation))

        return new_evals

    def _analyze_parallel(self, prepared, total, progress_callback, workers, stats):
        """Evaluate positions in parallel using multiple Stockfish instances."""
        new_evals = []
        completed = [0]  # list so closure can mutate
        lock = Lock()

        def evaluate_batch(batch, engine):
            """Worker: evaluate a batch sequentially on one engine, report per-game."""
            batch_evals = []
            for game, deviation, moves in batch:
                eval_result = engine.evaluate(deviation.board_at_deviation)
                eval_cp = eval_result.score_for_color(game.my_color)
                eval_loss_cp = self._compute_eval_loss(
                    deviation, eval_cp, engine, game.my_color)
                evaluation = self._make_evaluation(
                    game, deviation, eval_result, eval_loss_cp, moves)
                with lock:
                    self._aggregate(stats, evaluation)
                    new_evals.append((game, evaluation))
                    completed[0] += 1
                    if progress_callback:
                        progress_callback(completed[0], total)
            return batch_evals

        # Split work into chunks, one per worker (round-robin)
        chunks = [[] for _ in range(workers)]
        for i, item in enumerate(prepared):
            chunks[i % workers].append(item)

        # Spawn one engine per worker thread
        engines = []
        try:
            for _ in range(workers):
                eng = StockfishEvaluator(
                    self.stockfish_evaluator.stockfish_path,
                    depth=self.stockfish_evaluator.depth,
                )
                eng.__enter__()
                engines.append(eng)

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [
                    pool.submit(evaluate_batch, chunk, engine)
                    for chunk, engine in zip(chunks, engines)
                    if chunk
                ]

                for future in as_completed(futures):
                    future.result()  # raise any exceptions

        finally:
            for eng in engines:
                eng.__exit__(None, None, None)

        return new_evals

    def _make_evaluation(self, game, deviation, eval_result,
                         eval_loss_cp=0, moves=None):
        """Build an OpeningEvaluation from pre-processed data + engine result."""
        eval_cp = eval_result.score_for_color(game.my_color)
        return OpeningEvaluation(
            eco_code=game.eco_code,
            eco_name=game.eco_name or "Unknown Opening",
            my_color=game.my_color,
            deviation_ply=deviation.deviation_ply,
            deviating_side=deviation.deviating_side,
            eval_cp=eval_cp,
            is_fully_booked=deviation.is_fully_booked,
            fen_at_deviation=deviation.board_at_deviation.fen(),
            best_move_uci=eval_result.best_move.uci() if eval_result.best_move else None,
            played_move_uci=deviation.played_move.uci() if deviation.played_move else None,
            book_moves_uci=[m.uci() for m in deviation.book_moves],
            eval_loss_cp=eval_loss_cp,
            game_moves_uci=[m.uci() for m in moves] if moves else [],
        )

    @staticmethod
    def format_summary(stats, min_games=2):
        """Format opening stats into human-readable summary lines.

        Args:
            stats: Dict from analyze_repertoire().
            min_games: Only include openings played at least this many times.

        Returns:
            List of formatted strings, sorted by avg eval descending.
        """
        lines = []

        filtered = {k: v for k, v in stats.items() if v.times_played >= min_games}
        sorted_openings = sorted(filtered.values(), key=lambda s: s.avg_eval, reverse=True)

        for s in sorted_openings:
            eval_pawns = s.avg_eval / 100.0
            sign = "+" if eval_pawns >= 0 else ""
            eco_label = f" ({s.eco_code})" if s.eco_code else ""

            line = (
                f"{s.eco_name}{eco_label} as {s.color}: "
                f"avg {sign}{eval_pawns:.1f} pawns, "
                f"played {s.times_played}x, "
                f"avg book depth {s.avg_deviation_ply} plies"
            )
            lines.append(line)

        return lines
