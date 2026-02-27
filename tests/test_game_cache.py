import os
import tempfile
import pytest

from game_cache import GameCache
from repertoire_analyzer import OpeningEvaluation


@pytest.fixture
def cache(tmp_path):
    """Create a GameCache with a temp DB file."""
    db_path = str(tmp_path / "test_cache.db")
    c = GameCache(db_path)
    yield c
    c.close()


class TestArchiveCache:
    def test_save_and_get_archive(self, cache):
        url = "https://api.chess.com/pub/player/bob/games/2024/06"
        data = {"games": [{"url": "game1"}, {"url": "game2"}]}

        cache.save_archive(url, "bob", data)
        result = cache.get_archive(url)

        assert result is not None
        assert len(result["games"]) == 2
        assert result["games"][0]["url"] == "game1"

    def test_get_archive_miss_returns_none(self, cache):
        assert cache.get_archive("https://nonexistent") is None

    def test_save_archive_upsert(self, cache):
        url = "https://api.chess.com/pub/player/bob/games/2024/06"

        cache.save_archive(url, "bob", {"games": [{"id": 1}]})
        cache.save_archive(url, "bob", {"games": [{"id": 1}, {"id": 2}]})

        result = cache.get_archive(url)
        assert len(result["games"]) == 2

    def test_different_urls_stored_separately(self, cache):
        url1 = "https://api.chess.com/pub/player/bob/games/2024/05"
        url2 = "https://api.chess.com/pub/player/bob/games/2024/06"

        cache.save_archive(url1, "bob", {"games": [{"id": "may"}]})
        cache.save_archive(url2, "bob", {"games": [{"id": "june"}]})

        assert cache.get_archive(url1)["games"][0]["id"] == "may"
        assert cache.get_archive(url2)["games"][0]["id"] == "june"


class TestEvaluationCache:
    def _make_eval(self, eco_code="B90", eco_name="Sicilian", my_color="white",
                   deviation_ply=6, deviating_side="black", eval_cp=30,
                   is_fully_booked=False):
        return OpeningEvaluation(
            eco_code=eco_code, eco_name=eco_name, my_color=my_color,
            deviation_ply=deviation_ply, deviating_side=deviating_side,
            eval_cp=eval_cp, is_fully_booked=is_fully_booked,
        )

    def test_save_and_get_evaluation(self, cache):
        ev = self._make_eval(eval_cp=45)
        cache.save_evaluation("https://game/1", "bob", 18, ev)

        result = cache.get_evaluation("https://game/1", 18)
        assert result is not None
        assert result.eval_cp == 45
        assert result.eco_code == "B90"
        assert result.my_color == "white"
        assert result.is_fully_booked is False

    def test_get_evaluation_miss_returns_none(self, cache):
        assert cache.get_evaluation("https://game/999", 18) is None

    def test_different_depth_is_separate(self, cache):
        ev18 = self._make_eval(eval_cp=30)
        ev22 = self._make_eval(eval_cp=35)

        cache.save_evaluation("https://game/1", "bob", 18, ev18)
        cache.save_evaluation("https://game/1", "bob", 22, ev22)

        assert cache.get_evaluation("https://game/1", 18).eval_cp == 30
        assert cache.get_evaluation("https://game/1", 22).eval_cp == 35

    def test_upsert_evaluation(self, cache):
        ev1 = self._make_eval(eval_cp=30)
        ev2 = self._make_eval(eval_cp=50)

        cache.save_evaluation("https://game/1", "bob", 18, ev1)
        cache.save_evaluation("https://game/1", "bob", 18, ev2)

        result = cache.get_evaluation("https://game/1", 18)
        assert result.eval_cp == 50

    def test_batch_get_evaluations(self, cache):
        cache.save_evaluation("https://game/1", "bob", 18, self._make_eval(eval_cp=10))
        cache.save_evaluation("https://game/2", "bob", 18, self._make_eval(eval_cp=20))
        cache.save_evaluation("https://game/3", "bob", 18, self._make_eval(eval_cp=30))

        urls = ["https://game/1", "https://game/2", "https://game/4"]
        result = cache.get_cached_evaluations(urls, 18)

        assert len(result) == 2
        assert result["https://game/1"].eval_cp == 10
        assert result["https://game/2"].eval_cp == 20
        assert "https://game/4" not in result

    def test_batch_get_empty_urls(self, cache):
        assert cache.get_cached_evaluations([], 18) == {}

    def test_batch_save_evaluations(self, cache):
        evals = [
            ("https://game/1", self._make_eval(eval_cp=10)),
            ("https://game/2", self._make_eval(eval_cp=20)),
            ("https://game/3", self._make_eval(eval_cp=30)),
        ]

        cache.save_evaluations_batch("bob", 18, evals)

        assert cache.get_evaluation("https://game/1", 18).eval_cp == 10
        assert cache.get_evaluation("https://game/2", 18).eval_cp == 20
        assert cache.get_evaluation("https://game/3", 18).eval_cp == 30

    def test_batch_save_empty_list(self, cache):
        cache.save_evaluations_batch("bob", 18, [])
        # Should not raise

    def test_is_fully_booked_stored_as_bool(self, cache):
        ev = self._make_eval(is_fully_booked=True)
        cache.save_evaluation("https://game/1", "bob", 18, ev)

        result = cache.get_evaluation("https://game/1", 18)
        assert result.is_fully_booked is True

    def test_null_eco_code(self, cache):
        ev = self._make_eval(eco_code=None)
        cache.save_evaluation("https://game/1", "bob", 18, ev)

        result = cache.get_evaluation("https://game/1", 18)
        assert result.eco_code is None


class TestCoachingColumns:
    """Tests for the v2 coaching data columns."""

    def _make_coaching_eval(self):
        return OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="white", eval_cp=-25,
            is_fully_booked=False,
            fen_at_deviation="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            best_move_uci="d2d4",
            played_move_uci="g1f3",
            book_moves_uci=["e2e4", "d2d4", "c2c4"],
        )

    def test_coaching_fields_round_trip(self, cache):
        ev = self._make_coaching_eval()
        cache.save_evaluation("https://game/1", "bob", 18, ev)

        result = cache.get_evaluation("https://game/1", 18)
        assert result.fen_at_deviation == ev.fen_at_deviation
        assert result.best_move_uci == "d2d4"
        assert result.played_move_uci == "g1f3"
        assert result.book_moves_uci == ["e2e4", "d2d4", "c2c4"]

    def test_coaching_fields_batch_round_trip(self, cache):
        ev = self._make_coaching_eval()
        cache.save_evaluations_batch("bob", 18, [("https://game/1", ev)])

        results = cache.get_cached_evaluations(["https://game/1"], 18)
        result = results["https://game/1"]
        assert result.fen_at_deviation == ev.fen_at_deviation
        assert result.best_move_uci == "d2d4"
        assert result.played_move_uci == "g1f3"
        assert result.book_moves_uci == ["e2e4", "d2d4", "c2c4"]

    def test_legacy_rows_return_empty_defaults(self, cache):
        """Old cached rows without coaching data return empty defaults."""
        # Directly insert a row without coaching columns
        cache._conn.execute(
            """INSERT INTO opening_evaluations
               (game_url, username, depth, eco_code, eco_name, my_color,
                deviation_ply, deviating_side, eval_cp, is_fully_booked)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("https://game/old", "bob", 18, "B90", "Sicilian", "white",
             6, "black", 30, 0)
        )
        cache._conn.commit()

        result = cache.get_evaluation("https://game/old", 18)
        assert result is not None
        assert result.fen_at_deviation == ""
        assert result.best_move_uci is None
        assert result.played_move_uci is None
        assert result.book_moves_uci == []
        assert result.eval_loss_cp == 0
        assert result.game_moves_uci == []

    def test_migration_is_idempotent(self, cache):
        """Calling _migrate_coaching_columns twice should not error."""
        cache._migrate_coaching_columns()
        cache._migrate_coaching_columns()
        # Save and get to verify DB still works
        ev = self._make_coaching_eval()
        cache.save_evaluation("https://game/1", "bob", 18, ev)
        assert cache.get_evaluation("https://game/1", 18).best_move_uci == "d2d4"

    def test_null_best_move_round_trip(self, cache):
        """Evaluations with None best_move should round-trip correctly."""
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="white", eval_cp=10,
            is_fully_booked=False,
            fen_at_deviation="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            best_move_uci=None,
            played_move_uci="e2e4",
            book_moves_uci=[],
        )
        cache.save_evaluation("https://game/1", "bob", 18, ev)

        result = cache.get_evaluation("https://game/1", 18)
        assert result.best_move_uci is None
        assert result.book_moves_uci == []


class TestEvalLossAndGameMoves:
    """Tests for eval_loss_cp and game_moves_uci cache columns."""

    def test_eval_loss_round_trip(self, cache):
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="white", eval_cp=-25,
            is_fully_booked=False, eval_loss_cp=120,
            fen_at_deviation="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            best_move_uci="d2d4", played_move_uci="g1f3",
            book_moves_uci=["e2e4"],
        )
        cache.save_evaluation("https://game/1", "bob", 18, ev)
        result = cache.get_evaluation("https://game/1", 18)
        assert result.eval_loss_cp == 120

    def test_game_moves_uci_round_trip(self, cache):
        moves = ["e2e4", "c7c5", "g1f3", "d7d6"]
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="white", eval_cp=-25,
            is_fully_booked=False, game_moves_uci=moves,
            fen_at_deviation="start",
        )
        cache.save_evaluation("https://game/1", "bob", 18, ev)
        result = cache.get_evaluation("https://game/1", 18)
        assert result.game_moves_uci == moves

    def test_game_moves_batch_round_trip(self, cache):
        moves = ["e2e4", "e7e5", "g1f3"]
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=4, deviating_side="white", eval_cp=10,
            is_fully_booked=False, game_moves_uci=moves,
            eval_loss_cp=30, fen_at_deviation="start",
        )
        cache.save_evaluations_batch("bob", 18, [("https://game/1", ev)])
        results = cache.get_cached_evaluations(["https://game/1"], 18)
        result = results["https://game/1"]
        assert result.game_moves_uci == moves
        assert result.eval_loss_cp == 30

    def test_empty_game_moves_round_trip(self, cache):
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="white", eval_cp=0,
            is_fully_booked=False, game_moves_uci=[],
        )
        cache.save_evaluation("https://game/1", "bob", 18, ev)
        result = cache.get_evaluation("https://game/1", 18)
        assert result.game_moves_uci == []

    def test_game_url_round_trip(self, cache):
        """game_url is populated from the DB row on read-back."""
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="white", eval_cp=0,
            is_fully_booked=False,
        )
        cache.save_evaluation("https://www.chess.com/game/live/99", "bob", 18, ev)
        result = cache.get_evaluation("https://www.chess.com/game/live/99", 18)
        assert result.game_url == "https://www.chess.com/game/live/99"

    def test_game_url_batch_round_trip(self, cache):
        """game_url is populated in batch lookups."""
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="white", eval_cp=0,
            is_fully_booked=False,
        )
        cache.save_evaluation("https://game/42", "bob", 18, ev)
        results = cache.get_cached_evaluations(["https://game/42"], 18)
        assert results["https://game/42"].game_url == "https://game/42"


class TestMyResultCache:
    """Tests for the my_result column."""

    def test_my_result_round_trip(self, cache):
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="black", eval_cp=30,
            is_fully_booked=False, my_result="win",
        )
        cache.save_evaluation("https://game/1", "bob", 18, ev)
        result = cache.get_evaluation("https://game/1", 18)
        assert result.my_result == "win"

    def test_my_result_loss_round_trip(self, cache):
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="black",
            deviation_ply=6, deviating_side="white", eval_cp=-20,
            is_fully_booked=False, my_result="loss",
        )
        cache.save_evaluation("https://game/1", "bob", 18, ev)
        result = cache.get_evaluation("https://game/1", 18)
        assert result.my_result == "loss"

    def test_my_result_batch_round_trip(self, cache):
        evals = [
            ("https://game/1", OpeningEvaluation(
                eco_code="B90", eco_name="Sicilian", my_color="white",
                deviation_ply=6, deviating_side="black", eval_cp=30,
                is_fully_booked=False, my_result="win",
            )),
            ("https://game/2", OpeningEvaluation(
                eco_code="B90", eco_name="Sicilian", my_color="white",
                deviation_ply=6, deviating_side="black", eval_cp=-10,
                is_fully_booked=False, my_result="draw",
            )),
        ]
        cache.save_evaluations_batch("bob", 18, evals)
        results = cache.get_cached_evaluations(["https://game/1", "https://game/2"], 18)
        assert results["https://game/1"].my_result == "win"
        assert results["https://game/2"].my_result == "draw"

    def test_my_result_empty_default(self, cache):
        """Evaluations without my_result get empty string."""
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="black", eval_cp=30,
            is_fully_booked=False,
        )
        cache.save_evaluation("https://game/1", "bob", 18, ev)
        result = cache.get_evaluation("https://game/1", 18)
        assert result.my_result == ""


class TestTimeClassCache:
    """Tests for the time_class column."""

    def test_time_class_round_trip(self, cache):
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="black", eval_cp=30,
            is_fully_booked=False, time_class="blitz",
        )
        cache.save_evaluation("https://game/1", "bob", 18, ev)
        result = cache.get_evaluation("https://game/1", 18)
        assert result.time_class == "blitz"

    def test_time_class_batch_round_trip(self, cache):
        evals = [
            ("https://game/1", OpeningEvaluation(
                eco_code="B90", eco_name="Sicilian", my_color="white",
                deviation_ply=6, deviating_side="black", eval_cp=30,
                is_fully_booked=False, time_class="rapid",
            )),
            ("https://game/2", OpeningEvaluation(
                eco_code="B90", eco_name="Sicilian", my_color="white",
                deviation_ply=6, deviating_side="black", eval_cp=-10,
                is_fully_booked=False, time_class="bullet",
            )),
        ]
        cache.save_evaluations_batch("bob", 18, evals)
        results = cache.get_cached_evaluations(["https://game/1", "https://game/2"], 18)
        assert results["https://game/1"].time_class == "rapid"
        assert results["https://game/2"].time_class == "bullet"

    def test_time_class_empty_default(self, cache):
        ev = OpeningEvaluation(
            eco_code="B90", eco_name="Sicilian", my_color="white",
            deviation_ply=6, deviating_side="black", eval_cp=30,
            is_fully_booked=False,
        )
        cache.save_evaluation("https://game/1", "bob", 18, ev)
        result = cache.get_evaluation("https://game/1", 18)
        assert result.time_class == ""


class TestCacheLifecycle:
    def test_close_and_reopen(self, tmp_path):
        db_path = str(tmp_path / "lifecycle.db")

        cache = GameCache(db_path)
        cache.save_archive("https://url", "bob", {"games": []})
        cache.close()

        cache2 = GameCache(db_path)
        assert cache2.get_archive("https://url") is not None
        cache2.close()

    def test_db_file_created(self, tmp_path):
        db_path = str(tmp_path / "new.db")
        assert not os.path.exists(db_path)

        cache = GameCache(db_path)
        assert os.path.exists(db_path)
        cache.close()
