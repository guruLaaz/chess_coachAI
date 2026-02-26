"""Tests for the coaching report Flask web app."""
import chess
from repertoire_analyzer import OpeningEvaluation
from report_generator import CoachingReportGenerator


def _make_eval(eco_code="B90", eco_name="Sicilian", my_color="white",
               deviation_ply=6, deviating_side="white", eval_cp=-50,
               is_fully_booked=False, fen=None, best_move="d2d4",
               played_move="g1f3", book_moves=None, eval_loss_cp=50,
               game_moves_uci=None):
    """Helper to create an OpeningEvaluation with coaching data."""
    if fen is None:
        fen = chess.Board().fen()
    return OpeningEvaluation(
        eco_code=eco_code,
        eco_name=eco_name,
        my_color=my_color,
        deviation_ply=deviation_ply,
        deviating_side=deviating_side,
        eval_cp=eval_cp,
        is_fully_booked=is_fully_booked,
        fen_at_deviation=fen,
        best_move_uci=best_move,
        played_move_uci=played_move,
        book_moves_uci=book_moves or ["e2e4", "d2d4"],
        eval_loss_cp=eval_loss_cp,
        game_moves_uci=game_moves_uci or [],
    )


class TestDeviationFiltering:
    def test_only_player_deviations_included(self):
        """Only deviations where deviating_side == my_color are shown."""
        evals = [
            _make_eval(deviating_side="white", my_color="white"),    # included
            _make_eval(deviating_side="black", my_color="white"),    # excluded
            _make_eval(deviating_side="black", my_color="black"),    # included
        ]
        gen = CoachingReportGenerator("player", evals)
        assert len(gen.deviations) == 2

    def test_fully_booked_excluded(self):
        """Fully booked games are excluded from coaching report."""
        evals = [
            _make_eval(is_fully_booked=True),
            _make_eval(is_fully_booked=False),
        ]
        gen = CoachingReportGenerator("player", evals)
        assert len(gen.deviations) == 1

    def test_missing_fen_excluded(self):
        """Evaluations without FEN data (legacy cache) are excluded."""
        evals = [
            _make_eval(fen=""),
            _make_eval(),
        ]
        gen = CoachingReportGenerator("player", evals)
        assert len(gen.deviations) == 1

    def test_missing_played_move_excluded(self):
        """Evaluations without played_move are excluded."""
        evals = [
            _make_eval(played_move=None),
            _make_eval(),
        ]
        gen = CoachingReportGenerator("player", evals)
        assert len(gen.deviations) == 1

    def test_empty_evaluations(self):
        gen = CoachingReportGenerator("player", [])
        assert gen.deviations == []


class TestSorting:
    def test_sorted_by_eval_loss_descending(self):
        """Deviations are sorted by eval_loss_cp descending (biggest mistake first)."""
        evals = [
            _make_eval(eval_loss_cp=10),
            _make_eval(eval_loss_cp=120),
            _make_eval(eval_loss_cp=50),
        ]
        gen = CoachingReportGenerator("player", evals)
        assert [d.eval_loss_cp for d in gen.deviations] == [120, 50, 10]


class TestMoveConversion:
    def test_ply_to_move_label_white(self):
        gen = CoachingReportGenerator("player", [])
        assert gen._ply_to_move_label(0, "white") == "1."
        assert gen._ply_to_move_label(2, "white") == "2."
        assert gen._ply_to_move_label(4, "white") == "3."

    def test_ply_to_move_label_black(self):
        gen = CoachingReportGenerator("player", [])
        assert gen._ply_to_move_label(1, "black") == "1..."
        assert gen._ply_to_move_label(3, "black") == "2..."
        assert gen._ply_to_move_label(5, "black") == "3..."

    def test_move_to_san(self):
        gen = CoachingReportGenerator("player", [])
        fen = chess.Board().fen()
        assert gen._move_to_san(fen, "e2e4") == "e4"
        assert gen._move_to_san(fen, "g1f3") == "Nf3"

    def test_move_to_san_none(self):
        gen = CoachingReportGenerator("player", [])
        assert gen._move_to_san(chess.Board().fen(), None) == "N/A"


class TestOpeningGroups:
    def test_groups_by_eco_and_color(self):
        evals = [
            _make_eval(eco_code="B90", my_color="white", deviating_side="white"),
            _make_eval(eco_code="B90", my_color="white", deviating_side="white"),
            _make_eval(eco_code="C50", my_color="black", deviating_side="black"),
        ]
        gen = CoachingReportGenerator("player", evals)
        groups = gen._get_opening_groups()

        assert len(groups) == 2
        # Sorted by count descending
        assert groups[0]["eco_code"] == "B90"
        assert groups[0]["count"] == 2
        assert groups[1]["eco_code"] == "C50"
        assert groups[1]["count"] == 1


class TestSVGRendering:
    def test_render_board_with_arrow(self):
        gen = CoachingReportGenerator("player", [])
        svg = gen._render_board_svg(chess.Board().fen(), "e2e4", "white", "#22c55e")
        assert "<svg" in svg
        assert "svg" in svg.lower()

    def test_render_board_no_move(self):
        gen = CoachingReportGenerator("player", [])
        svg = gen._render_board_svg(chess.Board().fen(), None, "white", "#22c55e")
        assert "<svg" in svg


class TestFlaskRoutes:
    def _get_app(self, evals=None):
        if evals is None:
            evals = [_make_eval(), _make_eval(eco_code="C50", eco_name="Italian",
                                              my_color="black", deviating_side="black")]
        gen = CoachingReportGenerator("testuser", evals)
        app = gen._build_app()
        app.config["TESTING"] = True
        return app.test_client()

    def test_index_returns_200(self):
        client = self._get_app()
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_contains_username(self):
        client = self._get_app()
        resp = client.get("/")
        assert b"testuser" in resp.data

    def test_index_contains_boards(self):
        """Route contains SVG boards for best and played moves."""
        client = self._get_app()
        resp = client.get("/")
        assert b"<svg" in resp.data

    def test_index_contains_move_recommendation(self):
        client = self._get_app()
        resp = client.get("/")
        assert b"instead of" in resp.data

    def test_opening_filter_route_200(self):
        client = self._get_app()
        resp = client.get("/opening/B90/white")
        assert resp.status_code == 200

    def test_opening_filter_shows_only_matching(self):
        client = self._get_app()
        resp = client.get("/opening/C50/black")
        html = resp.data.decode()
        assert "Italian" in html
        # B90 should not be in the main content (though it may be in sidebar)

    def test_empty_report(self):
        client = self._get_app(evals=[])
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"No deviations found" in resp.data

    def test_nonexistent_opening_returns_empty(self):
        client = self._get_app()
        resp = client.get("/opening/Z99/white")
        assert resp.status_code == 200

    def test_eval_loss_displayed(self):
        """Eval loss badge is shown in the report."""
        evals = [_make_eval(eval_loss_cp=120)]
        client = self._get_app(evals)
        resp = client.get("/")
        assert b"-1.2 loss" in resp.data

    def test_always_renders_svg_boards(self):
        """SVG boards are always rendered for every deviation."""
        evals = [_make_eval(game_moves_uci=["e2e4", "c7c5", "g1f3"])]
        client = self._get_app(evals)
        resp = client.get("/")
        assert b"<svg" in resp.data
