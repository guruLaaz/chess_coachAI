import chess
from unittest.mock import MagicMock, patch

from repertoire_analyzer import RepertoireAnalyzer, OpeningEvaluation, OpeningStats
from opening_detector import DeviationResult
from stockfish_evaluator import EvalResult
from helpers import make_chess_game


SAMPLE_PGN = """[Event "Live Chess"]
[ECO "B90"]

1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 1-0"""


def _make_game_with_pgn(my_color="white", pgn=SAMPLE_PGN, eco_code="B90",
                        eco_name="Sicilian Defense Najdorf Variation",
                        game_url=""):
    game = make_chess_game(my_color=my_color, game_url=game_url)
    game.pgn = pgn
    game.eco_code = eco_code
    game.eco_name = eco_name
    return game


def _mock_deviation(ply=6, side="black", fully_booked=False,
                    played_move=None, book_moves=None):
    return DeviationResult(
        deviation_ply=ply,
        deviating_side=side,
        board_at_deviation=chess.Board(),
        is_fully_booked=fully_booked,
        played_move=played_move,
        book_moves=book_moves or [],
    )


def _mock_eval(cp=25, best_move=None):
    return EvalResult(score_cp=cp, score_mate=None, depth=18, best_move=best_move)


class TestAnalyzeGame:
    def test_game_with_no_pgn_returns_none(self):
        game = make_chess_game()
        game.pgn = None

        mock_detector = MagicMock()
        mock_evaluator = MagicMock()

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        assert analyzer.analyze_game(game) is None

    def test_game_too_short_returns_none(self):
        short_pgn = '[Result "1-0"]\n\n1. e4 1-0'
        game = _make_game_with_pgn(pgn=short_pgn)

        mock_detector = MagicMock()
        mock_evaluator = MagicMock()

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        assert analyzer.analyze_game(game) is None

    def test_successful_analysis_as_white(self):
        game = _make_game_with_pgn(my_color="white")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(ply=6, side="black")

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=30)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result is not None
        assert result.eco_code == "B90"
        assert result.my_color == "white"
        assert result.deviation_ply == 6
        assert result.eval_cp == 30  # positive = good for white

    def test_successful_analysis_as_black(self):
        game = _make_game_with_pgn(my_color="black")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(ply=6, side="white")

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=30)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result is not None
        assert result.eval_cp == -30  # score flipped for black

    def test_no_deviation_returns_none(self):
        game = _make_game_with_pgn()

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = None

        mock_evaluator = MagicMock()

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        assert analyzer.analyze_game(game) is None

    def test_missing_eco_name_uses_unknown(self):
        game = _make_game_with_pgn(eco_name="")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=0)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)
        assert result.eco_name == "Unknown Opening"


class TestAnalyzeRepertoire:
    def test_multiple_games_same_opening(self):
        games = [
            _make_game_with_pgn(my_color="white"),
            _make_game_with_pgn(my_color="white"),
            _make_game_with_pgn(my_color="white"),
        ]

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(ply=6, side="black")

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.side_effect = [
            _mock_eval(cp=20),
            _mock_eval(cp=40),
            _mock_eval(cp=-10),
        ]

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        stats, new_evals = analyzer.analyze_repertoire(games)

        assert "B90_white" in stats
        entry = stats["B90_white"]
        assert entry.times_played == 3
        assert entry.avg_eval == round((20 + 40 + -10) / 3, 1)
        assert entry.min_eval == -10
        assert entry.max_eval == 40
        assert len(new_evals) == 3

    def test_different_openings_different_colors(self):
        game1 = _make_game_with_pgn(my_color="white", eco_code="B90")
        game2 = _make_game_with_pgn(my_color="black", eco_code="C50")
        game2.eco_name = "Italian Game"

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.side_effect = [
            _mock_eval(cp=15),
            _mock_eval(cp=10),
        ]

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        stats, new_evals = analyzer.analyze_repertoire([game1, game2])

        assert "B90_white" in stats
        assert "C50_black" in stats
        assert stats["B90_white"].times_played == 1
        assert stats["C50_black"].times_played == 1

    def test_skipped_games_not_counted(self):
        good_game = _make_game_with_pgn()
        bad_game = make_chess_game()
        bad_game.pgn = None

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=0)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        stats, new_evals = analyzer.analyze_repertoire([good_game, bad_game])

        assert len(stats) == 1

    def test_progress_callback_called(self):
        games = [_make_game_with_pgn(), _make_game_with_pgn()]

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=0)

        callback = MagicMock()
        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        analyzer.analyze_repertoire(games, progress_callback=callback)

        assert callback.call_count == 2
        callback.assert_any_call(1, 2)
        callback.assert_any_call(2, 2)

    def test_empty_games_returns_empty(self):
        analyzer = RepertoireAnalyzer("player", MagicMock(), MagicMock())
        stats, new_evals = analyzer.analyze_repertoire([])
        assert stats == {}
        assert new_evals == []

    def test_player_deviation_counted(self):
        game = _make_game_with_pgn(my_color="white")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(ply=4, side="white")

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=10)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        stats, _ = analyzer.analyze_repertoire([game])

        assert stats["B90_white"].player_deviated_count == 1

    def test_opponent_deviation_not_counted_as_player(self):
        game = _make_game_with_pgn(my_color="white")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(ply=5, side="black")

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=15)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        stats, _ = analyzer.analyze_repertoire([game])

        assert stats["B90_white"].player_deviated_count == 0

    def test_cached_evaluations_included_in_stats(self):
        """Cached evaluations should be aggregated without engine calls."""
        cached = [
            OpeningEvaluation(
                eco_code="B90", eco_name="Sicilian", my_color="white",
                deviation_ply=6, deviating_side="black",
                eval_cp=25, is_fully_booked=False,
            ),
            OpeningEvaluation(
                eco_code="B90", eco_name="Sicilian", my_color="white",
                deviation_ply=8, deviating_side="black",
                eval_cp=35, is_fully_booked=False,
            ),
        ]

        mock_evaluator = MagicMock()
        analyzer = RepertoireAnalyzer("player", MagicMock(), mock_evaluator)
        stats, new_evals = analyzer.analyze_repertoire(
            [], cached_evaluations=cached)

        assert "B90_white" in stats
        assert stats["B90_white"].times_played == 2
        assert stats["B90_white"].avg_eval == 30.0
        assert new_evals == []
        mock_evaluator.evaluate.assert_not_called()

    def test_cached_and_fresh_combined(self):
        """Cached + new games should both appear in final stats."""
        cached = [
            OpeningEvaluation(
                eco_code="B90", eco_name="Sicilian", my_color="white",
                deviation_ply=6, deviating_side="black",
                eval_cp=20, is_fully_booked=False,
            ),
        ]

        game = _make_game_with_pgn(my_color="white")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(ply=6, side="black")

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=40)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        stats, new_evals = analyzer.analyze_repertoire(
            [game], cached_evaluations=cached)

        assert stats["B90_white"].times_played == 2
        assert stats["B90_white"].avg_eval == 30.0
        assert len(new_evals) == 1

    def test_new_evals_contain_game_objects(self):
        """new_evals should be list of (game, OpeningEvaluation) tuples."""
        game = _make_game_with_pgn(my_color="white", game_url="https://game/1")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=10)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        _, new_evals = analyzer.analyze_repertoire([game])

        assert len(new_evals) == 1
        returned_game, returned_eval = new_evals[0]
        assert returned_game.game_url == "https://game/1"
        assert returned_eval.eval_cp == 10


class TestAnalyzeParallel:
    """Tests that specifically exercise the parallel (workers > 1) code path."""

    def test_parallel_returns_new_evals_not_stats(self):
        """Regression: _analyze_parallel must return new_evals list, not stats dict."""
        games = [
            _make_game_with_pgn(my_color="white", game_url="https://game/1"),
            _make_game_with_pgn(my_color="white", game_url="https://game/2"),
        ]

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(ply=6, side="black")

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=20)
        mock_evaluator.stockfish_path = "fake_path"
        mock_evaluator.depth = 18

        with patch("repertoire_analyzer.StockfishEvaluator") as MockSFClass:
            mock_engine = MagicMock()
            mock_engine.evaluate.return_value = _mock_eval(cp=20)
            MockSFClass.return_value = mock_engine

            analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
            stats, new_evals = analyzer.analyze_repertoire(games, workers=2)

        assert isinstance(new_evals, list)
        assert len(new_evals) == 2
        for game, evaluation in new_evals:
            assert hasattr(game, "game_url")
            assert isinstance(evaluation, OpeningEvaluation)

    def test_parallel_progress_called_per_game(self):
        """Progress callback should fire once per game, not once per batch."""
        games = [_make_game_with_pgn() for _ in range(4)]

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=0)
        mock_evaluator.stockfish_path = "fake_path"
        mock_evaluator.depth = 18

        with patch("repertoire_analyzer.StockfishEvaluator") as MockSFClass:
            mock_engine = MagicMock()
            mock_engine.evaluate.return_value = _mock_eval(cp=0)
            MockSFClass.return_value = mock_engine

            callback = MagicMock()
            analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
            analyzer.analyze_repertoire(games, progress_callback=callback, workers=2)

        # Should be called once per game (4 times), not once per worker (2 times)
        assert callback.call_count == 4

    def test_parallel_aggregates_stats_correctly(self):
        """Parallel path should produce the same aggregated stats as sequential."""
        games = [
            _make_game_with_pgn(my_color="white"),
            _make_game_with_pgn(my_color="white"),
        ]

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(ply=6, side="black")

        mock_evaluator = MagicMock()
        mock_evaluator.stockfish_path = "fake_path"
        mock_evaluator.depth = 18

        with patch("repertoire_analyzer.StockfishEvaluator") as MockSFClass:
            mock_engine = MagicMock()
            mock_engine.evaluate.side_effect = [_mock_eval(cp=10), _mock_eval(cp=30)]
            MockSFClass.return_value = mock_engine

            analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
            stats, _ = analyzer.analyze_repertoire(games, workers=2)

        assert "B90_white" in stats
        assert stats["B90_white"].times_played == 2


class TestPreprocessEdgeCases:
    """Test _preprocess_game edge cases and progress callback with 0 games."""

    def test_short_pgn_skipped_in_repertoire(self):
        """Games with fewer than MIN_MOVES_FOR_ANALYSIS are skipped."""
        short_pgn = '[Result "1-0"]\n\n1. e4 1-0'
        game = _make_game_with_pgn(pgn=short_pgn)

        mock_detector = MagicMock()
        mock_evaluator = MagicMock()

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        stats, new_evals = analyzer.analyze_repertoire([game])

        assert stats == {}
        assert new_evals == []
        mock_evaluator.evaluate.assert_not_called()

    def test_no_deviation_skipped_in_repertoire(self):
        """Games where find_deviation returns None are skipped."""
        game = _make_game_with_pgn()

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = None

        mock_evaluator = MagicMock()

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        stats, new_evals = analyzer.analyze_repertoire([game])

        assert stats == {}
        assert new_evals == []
        mock_evaluator.evaluate.assert_not_called()

    def test_progress_callback_with_all_games_filtered(self):
        """Progress callback fires (0, 0) when all games fail preprocessing."""
        game = make_chess_game()
        game.pgn = None  # will be skipped

        callback = MagicMock()
        analyzer = RepertoireAnalyzer("player", MagicMock(), MagicMock())
        stats, new_evals = analyzer.analyze_repertoire([game], progress_callback=callback)

        callback.assert_called_once_with(0, 0)
        assert new_evals == []

    def test_no_progress_callback_with_all_games_filtered(self):
        """No error when progress_callback is None and all games are filtered."""
        game = make_chess_game()
        game.pgn = None

        analyzer = RepertoireAnalyzer("player", MagicMock(), MagicMock())
        stats, new_evals = analyzer.analyze_repertoire([game])

        assert stats == {}
        assert new_evals == []


class TestOpeningStats:
    def test_avg_eval_zero_times_played(self):
        """avg_eval returns 0.0 when times_played is 0."""
        stats = OpeningStats(eco_code="B90", eco_name="Sicilian", color="white")
        assert stats.avg_eval == 0.0

    def test_avg_deviation_ply_zero_times_played(self):
        """avg_deviation_ply returns 0.0 when times_played is 0."""
        stats = OpeningStats(eco_code="B90", eco_name="Sicilian", color="white")
        assert stats.avg_deviation_ply == 0.0

    def test_avg_eval_with_data(self):
        stats = OpeningStats(
            eco_code="B90", eco_name="Sicilian", color="white",
            times_played=3, total_eval=90,
        )
        assert stats.avg_eval == 30.0

    def test_avg_deviation_ply_with_data(self):
        stats = OpeningStats(
            eco_code="B90", eco_name="Sicilian", color="white",
            times_played=4, total_deviation_ply=20,
        )
        assert stats.avg_deviation_ply == 5.0


class TestFormatSummary:
    def test_basic_formatting(self):
        stats = {
            "B90_white": OpeningStats(
                eco_code="B90",
                eco_name="Sicilian Najdorf",
                color="white",
                times_played=5,
                total_eval=150,
                min_eval=10,
                max_eval=50,
                total_deviation_ply=40,
                player_deviated_count=2,
            ),
        }

        lines = RepertoireAnalyzer.format_summary(stats, min_games=2)
        assert len(lines) == 1
        assert "Sicilian Najdorf (B90)" in lines[0]
        assert "as white" in lines[0]
        assert "+0.3 pawns" in lines[0]
        assert "played 5x" in lines[0]

    def test_min_games_filter(self):
        stats = {
            "B90_white": OpeningStats(
                eco_code="B90", eco_name="Sicilian", color="white",
                times_played=1, total_eval=50,
            ),
        }

        lines = RepertoireAnalyzer.format_summary(stats, min_games=2)
        assert len(lines) == 0

    def test_sorted_by_avg_eval_descending(self):
        stats = {
            "B90_white": OpeningStats(
                eco_code="B90", eco_name="Sicilian", color="white",
                times_played=3, total_eval=-90,
            ),
            "C50_white": OpeningStats(
                eco_code="C50", eco_name="Italian", color="white",
                times_played=3, total_eval=150,
            ),
        }

        lines = RepertoireAnalyzer.format_summary(stats, min_games=2)
        assert "Italian" in lines[0]
        assert "Sicilian" in lines[1]

    def test_negative_eval_formatting(self):
        stats = {
            "D00_black": OpeningStats(
                eco_code="D00", eco_name="Queens Pawn", color="black",
                times_played=4, total_eval=-200,
                min_eval=-80, max_eval=-20,
                total_deviation_ply=24,
            ),
        }

        lines = RepertoireAnalyzer.format_summary(stats, min_games=2)
        assert len(lines) == 1
        assert "-0.5 pawns" in lines[0]
        assert "as black" in lines[0]

    def test_no_eco_code(self):
        stats = {
            "Unknown_white": OpeningStats(
                eco_code=None, eco_name="Unknown Opening", color="white",
                times_played=3, total_eval=0,
            ),
        }

        lines = RepertoireAnalyzer.format_summary(stats, min_games=2)
        assert len(lines) == 1
        assert "(Unknown" not in lines[0]  # no eco code label when None


class TestEvalLoss:
    """Tests for eval loss computation (eval before - eval after played move)."""

    def test_eval_loss_computed_for_player_move(self):
        """eval_loss_cp = eval_before - eval_after for player's move."""
        game = _make_game_with_pgn(my_color="white")
        played = chess.Move.from_uci("g1f3")  # legal from starting position

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(
            ply=2, side="white", played_move=played)

        mock_evaluator = MagicMock()
        # First call: eval at deviation (before move) = +50 from white's POV
        # Second call: eval after played move = +10 from white's POV
        mock_evaluator.evaluate.side_effect = [
            _mock_eval(cp=50),   # before
            _mock_eval(cp=10),   # after played move
        ]

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result.eval_loss_cp == 40  # 50 - 10 = 40 centipawns lost

    def test_eval_loss_zero_for_fully_booked(self):
        """Fully booked games should have eval_loss_cp = 0."""
        game = _make_game_with_pgn(my_color="white")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(
            fully_booked=True)

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=0)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result.eval_loss_cp == 0
        # Only one evaluate call (no second eval for loss)
        assert mock_evaluator.evaluate.call_count == 1

    def test_eval_loss_zero_when_no_played_move(self):
        """When played_move is None, eval_loss_cp = 0."""
        game = _make_game_with_pgn(my_color="white")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(
            played_move=None)

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=25)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result.eval_loss_cp == 0
        assert mock_evaluator.evaluate.call_count == 1

    def test_eval_loss_negative_when_move_improves(self):
        """If the played move is better than position eval, loss is negative."""
        game = _make_game_with_pgn(my_color="white")
        played = chess.Move.from_uci("e2e4")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(
            played_move=played)

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.side_effect = [
            _mock_eval(cp=20),   # before
            _mock_eval(cp=50),   # after (improved!)
        ]

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result.eval_loss_cp == -30  # 20 - 50 = -30

    def test_eval_loss_for_black_perspective(self):
        """Eval loss should work correctly from black's perspective."""
        game = _make_game_with_pgn(my_color="black")
        played = chess.Move.from_uci("e2e4")  # using starting pos

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(
            side="black", played_move=played)

        mock_evaluator = MagicMock()
        # score_cp is from white's POV; score_for_color("black") negates it
        mock_evaluator.evaluate.side_effect = [
            _mock_eval(cp=30),   # before: -30 from black's POV
            _mock_eval(cp=80),   # after: -80 from black's POV
        ]

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        # From black's POV: eval_before=-30, eval_after=-80
        # Loss = -30 - (-80) = 50 (black lost 50cp)
        assert result.eval_loss_cp == 50


class TestMyResult:
    """Tests for my_result being populated from game outcome."""

    def test_my_result_win_as_white(self):
        game = _make_game_with_pgn(my_color="white")
        # Default helper: white_result="win"

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=30)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result.my_result == "win"

    def test_my_result_loss_as_white(self):
        game = _make_game_with_pgn(my_color="white")
        game.white_result = "resigned"

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=-50)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result.my_result == "loss"

    def test_my_result_draw(self):
        game = _make_game_with_pgn(my_color="white")
        game.white_result = "stalemate"

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=0)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result.my_result == "draw"

    def test_my_result_loss_as_black(self):
        game = _make_game_with_pgn(my_color="black")
        game.black_result = "checkmated"

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation(side="white")

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=50)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        assert result.my_result == "loss"

    def test_my_result_populated_in_repertoire(self):
        """my_result should appear in new_evals from analyze_repertoire."""
        game = _make_game_with_pgn(my_color="white", game_url="https://game/1")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=10)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        _, new_evals = analyzer.analyze_repertoire([game])

        assert len(new_evals) == 1
        _, ev = new_evals[0]
        assert ev.my_result == "win"

    def test_all_loss_variants_detected(self):
        """All Chess.com loss result strings should map to 'loss'."""
        for loss_result in ["checkmated", "timeout", "resigned", "abandoned", "lose"]:
            game = _make_game_with_pgn(my_color="white")
            game.white_result = loss_result

            mock_detector = MagicMock()
            mock_detector.find_deviation.return_value = _mock_deviation()

            mock_evaluator = MagicMock()
            mock_evaluator.evaluate.return_value = _mock_eval(cp=0)

            analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
            result = analyzer.analyze_game(game)

            assert result.my_result == "loss", f"Expected 'loss' for '{loss_result}'"


class TestGameMovesUci:
    """Tests for game_moves_uci being populated in evaluations."""

    def test_game_moves_populated_in_analyze_game(self):
        game = _make_game_with_pgn(my_color="white")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=0)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        result = analyzer.analyze_game(game)

        # SAMPLE_PGN has 10 half-moves
        assert len(result.game_moves_uci) == 10
        assert all(isinstance(m, str) for m in result.game_moves_uci)
        assert result.game_moves_uci[0] == "e2e4"  # 1. e4

    def test_game_moves_populated_in_repertoire(self):
        game = _make_game_with_pgn(my_color="white", game_url="https://game/1")

        mock_detector = MagicMock()
        mock_detector.find_deviation.return_value = _mock_deviation()

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = _mock_eval(cp=10)

        analyzer = RepertoireAnalyzer("player", mock_detector, mock_evaluator)
        _, new_evals = analyzer.analyze_repertoire([game])

        assert len(new_evals) == 1
        _, ev = new_evals[0]
        assert len(ev.game_moves_uci) == 10
