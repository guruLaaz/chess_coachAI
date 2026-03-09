"""End-to-end Playwright tests for lazy board loading and filter combinations.

These tests spin up the real Flask app and verify that SVG boards
actually render in the browser — catching race conditions, JS errors,
and fetch failures that unit tests cannot.
"""
import threading
import time

import chess
import pytest
from playwright.sync_api import sync_playwright

from repertoire_analyzer import OpeningEvaluation
from report_generator import CoachingReportGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_eval(eco_code="B90", eco_name="Sicilian", my_color="white",
               deviating_side="white", fen=None, best_move="d2d4",
               played_move="g1f3", eval_loss_cp=50, my_result="win",
               time_class="blitz", game_url="https://www.chess.com/game/live/12345",
               book_moves=None):
    if fen is None:
        fen = chess.Board().fen()
    if book_moves is None:
        book_moves = [best_move, played_move]
    return OpeningEvaluation(
        eco_code=eco_code,
        eco_name=eco_name,
        my_color=my_color,
        deviation_ply=6,
        deviating_side=deviating_side,
        eval_cp=-50,
        is_fully_booked=False,
        fen_at_deviation=fen,
        best_move_uci=best_move,
        played_move_uci=played_move,
        book_moves_uci=book_moves,
        eval_loss_cp=eval_loss_cp,
        game_moves_uci=[],
        my_result=my_result,
        time_class=time_class,
        game_url=game_url,
    )


def _make_endgame_entry(eg_type, balance="equal", total=5, fen=None,
                        color="white", tc_breakdown=None):
    """Build one endgame stats dict matching what EndgameDetector produces."""
    if fen is None:
        fen = "4k3/8/8/8/8/8/4K3/4R3 w - - 0 1"
    if tc_breakdown is None:
        tc_breakdown = {"blitz": {
            "wins": total // 2 + 1,
            "losses": total // 4,
            "draws": total - (total // 2 + 1) - total // 4,
        }}
    return {
        "type": eg_type,
        "balance": balance,
        "total": total,
        "wins": total // 2 + 1,
        "losses": total // 4,
        "draws": total - (total // 2 + 1) - total // 4,
        "win_pct": 60,
        "loss_pct": 20,
        "draw_pct": 20,
        "example_fen": fen,
        "example_game_url": "https://www.chess.com/game/12345",
        "example_color": color,
        "example_material_diff": 5,
        "example_endgame_ply": 40,
        "example_opponent_name": "opponent42",
        "example_time_class": "blitz",
        "example_end_time": None,
        "avg_my_clock": 120.0,
        "avg_opp_clock": 95.0,
        "all_games": [],
        "tc_breakdown": tc_breakdown,
    }


def _start_server(generator, port):
    """Start the Flask app in a daemon thread."""
    app = generator._build_app()
    t = threading.Thread(
        target=lambda: app.run(port=port, use_reloader=False),
        daemon=True,
    )
    t.start()
    return t


def _visible_spinners(page):
    """Count board-spinner elements that are actually visible to the user."""
    return page.evaluate("""() => {
        return Array.from(document.querySelectorAll('.board-spinner'))
            .filter(el => {
                let node = el;
                while (node) {
                    if (node.style && node.style.display === 'none') return false;
                    node = node.parentElement;
                }
                return true;
            }).length;
    }""")


def _filtered_count(page, card_class):
    """Count cards with data-filtered='yes'."""
    return page.evaluate(
        f'() => document.querySelectorAll(\'{card_class}[data-filtered="yes"]\').length'
    )


def _set_checkboxes(page, selector, values_to_check):
    """Uncheck all checkboxes matching selector, then check only those in values_to_check."""
    page.evaluate("""(args) => {
        var selector = args[0], vals = new Set(args[1]);
        document.querySelectorAll(selector).forEach(function(cb) {
            cb.checked = vals.has(cb.value);
        });
        var first = document.querySelector(selector);
        if (first) first.dispatchEvent(new Event('change'));
    }""", [selector, list(values_to_check)])
    page.wait_for_timeout(200)


def _select_option(page, select_id, value):
    """Set a <select> value and dispatch change, even if hidden."""
    page.evaluate("""(args) => {
        var el = document.getElementById(args[0]);
        if (el) { el.value = args[1]; el.dispatchEvent(new Event('change')); }
    }""", [select_id, value])
    page.wait_for_timeout(200)


def _no_results_visible(page, elem_id):
    """Check if the no-results empty-state element is visible."""
    return page.evaluate(f"""() => {{
        var el = document.getElementById('{elem_id}');
        return el && el.style.display !== 'none';
    }}""")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def playwright_ctx():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def server_url():
    """Spin up a Flask server with diverse data for filter testing.

    Openings data (4 distinct deviations):
      - Sicilian (B90), white, blitz, chess.com, played 3x
      - French (C00), black, rapid, lichess, played 1x
      - Italian (C50), white, bullet, chess.com, played 1x
      - Caro-Kann (B10), black, daily, lichess, played 1x

    Endgame data (2 definitions, mixed balances & time classes):
      minor-or-queen:
        - R vs R, equal, blitz-only (5 games)
        - Q vs Q, equal, rapid-only (5 games)
        - R vs B, up, blitz+rapid (10 games)
        - N vs N, down, bullet-only (3 games)
      material:
        - RB vs RN, equal, blitz (5 games)
        - RR vs RR, equal, daily (5 games)
        - QR vs QR, up, blitz+bullet (8 games)
    """
    # --- Openings evals ---
    # Use different FENs (all white-to-move) so they become distinct deviations.
    # White deviations: white-to-move FENs with white moves.
    # Black deviations: black-to-move FENs with black moves.
    fen_start = chess.Board().fen()  # white to move

    board2 = chess.Board()
    board2.push_san("e4")
    fen2 = board2.fen()  # black to move (after 1.e4)

    board3 = chess.Board()
    board3.push_san("e4")
    board3.push_san("e5")
    fen3 = board3.fen()  # white to move (after 1.e4 e5)

    board4 = chess.Board()
    board4.push_san("d4")
    fen4 = board4.fen()  # black to move (after 1.d4)

    evals = [
        # Sicilian, white, blitz, chess.com — 3 copies = times_played 3
        _make_eval(eco_code="B90", eco_name="Sicilian", my_color="white",
                   time_class="blitz", fen=fen_start, played_move="g1f3",
                   best_move="d2d4",
                   game_url="https://www.chess.com/game/live/1"),
        _make_eval(eco_code="B90", eco_name="Sicilian", my_color="white",
                   time_class="blitz", fen=fen_start, played_move="g1f3",
                   best_move="d2d4",
                   game_url="https://www.chess.com/game/live/2"),
        _make_eval(eco_code="B90", eco_name="Sicilian", my_color="white",
                   time_class="blitz", fen=fen_start, played_move="g1f3",
                   best_move="d2d4",
                   game_url="https://www.chess.com/game/live/3"),
        # French, black, rapid, lichess — 1 copy (black to move after 1.e4)
        _make_eval(eco_code="C00", eco_name="French", my_color="black",
                   deviating_side="black", time_class="rapid", fen=fen2,
                   played_move="d7d6", best_move="d7d5",
                   game_url="https://lichess.org/abc123"),
        # Italian, white, bullet, chess.com — 1 copy (white to move after 1.e4 e5)
        _make_eval(eco_code="C50", eco_name="Italian", my_color="white",
                   time_class="bullet", fen=fen3, played_move="b1c3",
                   best_move="g1f3",
                   game_url="https://www.chess.com/game/live/4"),
        # Caro-Kann, black, daily, lichess — 1 copy (black to move after 1.d4)
        _make_eval(eco_code="B10", eco_name="Caro-Kann", my_color="black",
                   deviating_side="black", time_class="daily", fen=fen4,
                   played_move="d7d6", best_move="d7d5",
                   game_url="https://lichess.org/xyz789"),
    ]

    # --- Endgame stats ---
    endgame_stats = {
        "minor-or-queen": [
            _make_endgame_entry("R vs R", balance="equal", total=5,
                                tc_breakdown={"blitz": {"wins": 3, "losses": 1, "draws": 1}}),
            _make_endgame_entry("Q vs Q", balance="equal", total=5,
                                tc_breakdown={"rapid": {"wins": 2, "losses": 2, "draws": 1}}),
            _make_endgame_entry("R vs B", balance="up", total=10,
                                tc_breakdown={
                                    "blitz": {"wins": 4, "losses": 1, "draws": 0},
                                    "rapid": {"wins": 3, "losses": 1, "draws": 1},
                                }),
            _make_endgame_entry("N vs N", balance="down", total=3,
                                tc_breakdown={"bullet": {"wins": 0, "losses": 2, "draws": 1}}),
        ],
        "material": [
            _make_endgame_entry("RB vs RN", balance="equal", total=5,
                                tc_breakdown={"blitz": {"wins": 3, "losses": 1, "draws": 1}}),
            _make_endgame_entry("RR vs RR", balance="equal", total=5,
                                tc_breakdown={"daily": {"wins": 2, "losses": 1, "draws": 2}}),
            _make_endgame_entry("QR vs QR", balance="up", total=8,
                                tc_breakdown={
                                    "blitz": {"wins": 3, "losses": 1, "draws": 0},
                                    "bullet": {"wins": 2, "losses": 1, "draws": 1},
                                }),
        ],
    }

    gen = CoachingReportGenerator(
        evals, chesscom_user="testplayer", lichess_user="testplayer_li",
        endgame_stats=endgame_stats,
    )
    port = 5987
    _start_server(gen, port)
    base = f"http://127.0.0.1:{port}"

    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{base}/", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        pytest.fail("Flask server did not start in time")

    return base


# ---------------------------------------------------------------------------
# Board loading tests
# ---------------------------------------------------------------------------

class TestBoardLoading:
    """Verify that SVG boards render correctly."""

    def test_openings_boards_load(self, playwright_ctx, server_url):
        page = playwright_ctx.new_page()
        page.goto(server_url)
        page.wait_for_selector(".board-best svg", timeout=10000)
        page.wait_for_selector(".board-played svg", timeout=10000)
        assert _visible_spinners(page) == 0
        page.close()

    def test_endgames_boards_load(self, playwright_ctx, server_url):
        page = playwright_ctx.new_page()
        page.goto(f"{server_url}/endgames")
        page.wait_for_selector(".eg-board svg", timeout=10000)
        assert _visible_spinners(page) == 0
        page.close()

    def test_endgames_boards_load_after_definition_switch(self, playwright_ctx,
                                                           server_url):
        page = playwright_ctx.new_page()
        page.goto(f"{server_url}/endgames")
        page.wait_for_selector(".eg-board svg", timeout=10000)

        _select_option(page, "eg-def-select", "material")
        page.wait_for_selector(
            ".eg-card[data-definition='material'] .eg-board svg", timeout=10000)
        assert _visible_spinners(page) == 0

        _select_option(page, "eg-def-select", "minor-or-queen")
        page.wait_for_selector(
            ".eg-card[data-definition='minor-or-queen'] .eg-board svg", timeout=10000)
        assert _visible_spinners(page) == 0
        page.close()

    def test_no_js_errors_openings(self, playwright_ctx, server_url):
        page = playwright_ctx.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(server_url)
        page.wait_for_selector(".board-best svg", timeout=10000)
        assert errors == [], f"JS errors: {errors}"
        page.close()

    def test_no_js_errors_endgames(self, playwright_ctx, server_url):
        page = playwright_ctx.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(f"{server_url}/endgames")
        page.wait_for_selector(".eg-board svg", timeout=10000)
        _select_option(page, "eg-def-select", "material")
        page.wait_for_selector(
            ".eg-card[data-definition='material'] .eg-board svg", timeout=10000)
        assert errors == [], f"JS errors: {errors}"
        page.close()


# ---------------------------------------------------------------------------
# Openings filter combination tests
# ---------------------------------------------------------------------------

class TestOpeningsFilters:
    """Test all filter combinations on the openings page.

    Fixture data (4 deviations):
      Sicilian  | white | blitz  | chesscom | 3x played
      French    | black | rapid  | lichess  | 1x played
      Italian   | white | bullet | chesscom | 1x played
      Caro-Kann | black | daily  | lichess  | 1x played
    """

    def _goto_openings(self, playwright_ctx, server_url):
        page = playwright_ctx.new_page()
        page.goto(server_url)
        page.wait_for_selector(".board-best svg", timeout=10000)
        # Set min-games to 1 so all test cards are visible
        _select_option(page, "min-games-select", "1")
        return page

    # -- Time class filter --

    def test_all_tc_checked_shows_all(self, playwright_ctx, server_url):
        page = self._goto_openings(playwright_ctx, server_url)
        assert _filtered_count(page, ".card") == 4
        page.close()

    def test_tc_blitz_only(self, playwright_ctx, server_url):
        """Only the Sicilian (blitz) card should show."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["blitz"])
        assert _filtered_count(page, ".card") == 1
        page.close()

    def test_tc_rapid_only(self, playwright_ctx, server_url):
        """Only the French (rapid) card."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["rapid"])
        assert _filtered_count(page, ".card") == 1
        page.close()

    def test_tc_bullet_only(self, playwright_ctx, server_url):
        """Only the Italian (bullet) card."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["bullet"])
        assert _filtered_count(page, ".card") == 1
        page.close()

    def test_tc_daily_only(self, playwright_ctx, server_url):
        """Only the Caro-Kann (daily) card."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["daily"])
        assert _filtered_count(page, ".card") == 1
        page.close()

    def test_tc_blitz_and_rapid(self, playwright_ctx, server_url):
        """Sicilian + French."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["blitz", "rapid"])
        assert _filtered_count(page, ".card") == 2
        page.close()

    def test_tc_none_shows_empty(self, playwright_ctx, server_url):
        """Unchecking all TCs shows empty state."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", [])
        assert _filtered_count(page, ".card") == 0
        assert _no_results_visible(page, "no-results")
        page.close()

    # -- Platform filter --

    def test_platform_chesscom_only(self, playwright_ctx, server_url):
        """Sicilian + Italian (chess.com)."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".platform-filter", ["chesscom"])
        assert _filtered_count(page, ".card") == 2
        page.close()

    def test_platform_lichess_only(self, playwright_ctx, server_url):
        """French + Caro-Kann (lichess)."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".platform-filter", ["lichess"])
        assert _filtered_count(page, ".card") == 2
        page.close()

    def test_platform_none_shows_empty(self, playwright_ctx, server_url):
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".platform-filter", [])
        assert _filtered_count(page, ".card") == 0
        assert _no_results_visible(page, "no-results")
        page.close()

    # -- Min games filter --

    def test_min_games_1(self, playwright_ctx, server_url):
        """All 4 cards pass min=1."""
        page = self._goto_openings(playwright_ctx, server_url)
        _select_option(page, "min-games-select", "1")
        assert _filtered_count(page, ".card") == 4
        page.close()

    def test_min_games_2(self, playwright_ctx, server_url):
        """Only Sicilian (3x played) passes min=2."""
        page = self._goto_openings(playwright_ctx, server_url)
        _select_option(page, "min-games-select", "2")
        assert _filtered_count(page, ".card") == 1
        page.close()

    def test_min_games_5(self, playwright_ctx, server_url):
        """No card has 5+ plays."""
        page = self._goto_openings(playwright_ctx, server_url)
        _select_option(page, "min-games-select", "5")
        assert _filtered_count(page, ".card") == 0
        assert _no_results_visible(page, "no-results")
        page.close()

    # -- Combined filters --

    def test_tc_blitz_platform_chesscom(self, playwright_ctx, server_url):
        """blitz + chess.com = Sicilian only."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["blitz"])
        _set_checkboxes(page, ".platform-filter", ["chesscom"])
        assert _filtered_count(page, ".card") == 1
        page.close()

    def test_tc_rapid_platform_chesscom(self, playwright_ctx, server_url):
        """rapid + chess.com = no match (French is lichess)."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["rapid"])
        _set_checkboxes(page, ".platform-filter", ["chesscom"])
        assert _filtered_count(page, ".card") == 0
        assert _no_results_visible(page, "no-results")
        page.close()

    def test_tc_bullet_platform_lichess(self, playwright_ctx, server_url):
        """bullet + lichess = no match (Italian is chess.com)."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["bullet"])
        _set_checkboxes(page, ".platform-filter", ["lichess"])
        assert _filtered_count(page, ".card") == 0
        page.close()

    def test_tc_daily_platform_lichess(self, playwright_ctx, server_url):
        """daily + lichess = Caro-Kann."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["daily"])
        _set_checkboxes(page, ".platform-filter", ["lichess"])
        assert _filtered_count(page, ".card") == 1
        page.close()

    def test_tc_blitz_min_games_2(self, playwright_ctx, server_url):
        """blitz + min 2 = Sicilian (3x blitz)."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["blitz"])
        _select_option(page, "min-games-select", "2")
        assert _filtered_count(page, ".card") == 1
        page.close()

    def test_tc_rapid_min_games_2(self, playwright_ctx, server_url):
        """rapid + min 2 = nothing (French is 1x)."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["rapid"])
        _select_option(page, "min-games-select", "2")
        assert _filtered_count(page, ".card") == 0
        page.close()

    def test_all_three_filters_combined(self, playwright_ctx, server_url):
        """blitz + chess.com + min 2 = Sicilian."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["blitz"])
        _set_checkboxes(page, ".platform-filter", ["chesscom"])
        _select_option(page, "min-games-select", "2")
        assert _filtered_count(page, ".card") == 1
        page.close()

    def test_all_three_filters_no_match(self, playwright_ctx, server_url):
        """bullet + lichess + min 2 = nothing."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["bullet"])
        _set_checkboxes(page, ".platform-filter", ["lichess"])
        _select_option(page, "min-games-select", "2")
        assert _filtered_count(page, ".card") == 0
        assert _no_results_visible(page, "no-results")
        page.close()

    def test_filter_then_reset(self, playwright_ctx, server_url):
        """Filtering down then re-checking all restores full list."""
        page = self._goto_openings(playwright_ctx, server_url)
        _set_checkboxes(page, ".tc-filter", ["blitz"])
        assert _filtered_count(page, ".card") == 1
        _set_checkboxes(page, ".tc-filter", ["bullet", "blitz", "rapid", "daily"])
        assert _filtered_count(page, ".card") == 4
        page.close()


# ---------------------------------------------------------------------------
# Endgames filter combination tests
# ---------------------------------------------------------------------------

class TestEndgamesFilters:
    """Test all filter combinations on the endgames page.

    minor-or-queen (4 entries):
      R vs R | equal | blitz-only         | 5 games
      Q vs Q | equal | rapid-only         | 5 games
      R vs B | up    | blitz+rapid        | 10 games
      N vs N | down  | bullet-only        | 3 games

    material (3 entries):
      RB vs RN | equal | blitz-only       | 5 games
      RR vs RR | equal | daily-only       | 5 games
      QR vs QR | up    | blitz+bullet     | 8 games
    """

    def _goto_endgames(self, playwright_ctx, server_url):
        page = playwright_ctx.new_page()
        page.goto(f"{server_url}/endgames")
        page.wait_for_selector(".eg-board svg", timeout=10000)
        return page

    # -- Definition filter --

    def test_default_definition(self, playwright_ctx, server_url):
        """Default is minor-or-queen, min games 3+, so cards with >=3 games show."""
        page = self._goto_endgames(playwright_ctx, server_url)
        # With default min=3: R vs R (5), Q vs Q (5), R vs B (10), N vs N (3) = 4
        count = _filtered_count(page, ".eg-card")
        assert count == 4
        page.close()

    def test_switch_to_material(self, playwright_ctx, server_url):
        """Switching to material shows its 3 entries (all >=3 games)."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        page.wait_for_timeout(300)
        count = _filtered_count(page, ".eg-card")
        assert count == 3
        page.close()

    def test_switch_back_to_minor_or_queen(self, playwright_ctx, server_url):
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        page.wait_for_timeout(300)
        _select_option(page, "eg-def-select", "minor-or-queen")
        page.wait_for_timeout(300)
        assert _filtered_count(page, ".eg-card") == 4
        page.close()

    # -- Balance filter --

    def test_balance_equal_only(self, playwright_ctx, server_url):
        """minor-or-queen equal: R vs R (5) + Q vs Q (5) = 2 cards."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".balance-filter", ["equal"])
        assert _filtered_count(page, ".eg-card") == 2
        page.close()

    def test_balance_up_only(self, playwright_ctx, server_url):
        """minor-or-queen up: R vs B (10) = 1 card."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".balance-filter", ["up"])
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_balance_down_only(self, playwright_ctx, server_url):
        """minor-or-queen down: N vs N (3) = 1 card."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".balance-filter", ["down"])
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_balance_none_shows_empty(self, playwright_ctx, server_url):
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".balance-filter", [])
        assert _filtered_count(page, ".eg-card") == 0
        assert _no_results_visible(page, "eg-no-results")
        page.close()

    # -- Time class filter --

    def test_tc_blitz_only(self, playwright_ctx, server_url):
        """minor-or-queen, blitz: R vs R (5 blitz) + R vs B (5 blitz) = 2."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        assert _filtered_count(page, ".eg-card") == 2
        page.close()

    def test_tc_rapid_only(self, playwright_ctx, server_url):
        """minor-or-queen, rapid: Q vs Q (5 rapid) + R vs B (5 rapid) = 2."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".eg-tc-filter", ["rapid"])
        assert _filtered_count(page, ".eg-card") == 2
        page.close()

    def test_tc_bullet_only(self, playwright_ctx, server_url):
        """minor-or-queen, bullet: N vs N (3 bullet) = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".eg-tc-filter", ["bullet"])
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_tc_daily_only(self, playwright_ctx, server_url):
        """minor-or-queen has no daily games = 0."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".eg-tc-filter", ["daily"])
        assert _filtered_count(page, ".eg-card") == 0
        assert _no_results_visible(page, "eg-no-results")
        page.close()

    def test_tc_none_shows_empty(self, playwright_ctx, server_url):
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".eg-tc-filter", [])
        assert _filtered_count(page, ".eg-card") == 0
        assert _no_results_visible(page, "eg-no-results")
        page.close()

    # -- Min games filter --

    def test_min_games_1(self, playwright_ctx, server_url):
        """All 4 minor-or-queen entries have >=1 game."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-min-games-select", "1")
        assert _filtered_count(page, ".eg-card") == 4
        page.close()

    def test_min_games_5(self, playwright_ctx, server_url):
        """min 5: R vs R (5), Q vs Q (5), R vs B (10) = 3. N vs N (3) excluded."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-min-games-select", "5")
        assert _filtered_count(page, ".eg-card") == 3
        page.close()

    def test_min_games_10(self, playwright_ctx, server_url):
        """min 10: only R vs B (10) passes."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-min-games-select", "10")
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    # -- Stats recalculation on TC filter --

    def test_tc_filter_recalculates_stats(self, playwright_ctx, server_url):
        """R vs B has 10 total (5 blitz + 5 rapid). Filtering to blitz shows 5."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        # R vs B card should show 5 games (blitz portion)
        games_text = page.evaluate("""() => {
            var cards = document.querySelectorAll('.eg-card[data-filtered="yes"]');
            var texts = [];
            cards.forEach(c => {
                var el = c.querySelector('.eg-games');
                if (el) texts.push(el.textContent.trim());
            });
            return texts;
        }""")
        # R vs R has 5, R vs B has 5 blitz games
        assert "5 games" in games_text
        page.close()

    # -- Combined: definition + balance --

    def test_material_equal(self, playwright_ctx, server_url):
        """material + equal: RB vs RN (5) + RR vs RR (5) = 2."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".balance-filter", ["equal"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 2
        page.close()

    def test_material_up(self, playwright_ctx, server_url):
        """material + up: QR vs QR (8) = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".balance-filter", ["up"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_material_down(self, playwright_ctx, server_url):
        """material has no 'down' entries = 0."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".balance-filter", ["down"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 0
        assert _no_results_visible(page, "eg-no-results")
        page.close()

    # -- Combined: definition + TC --

    def test_material_blitz(self, playwright_ctx, server_url):
        """material + blitz: RB vs RN (5 blitz) + QR vs QR (4 blitz) = 2."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 2
        page.close()

    def test_material_daily(self, playwright_ctx, server_url):
        """material + daily: RR vs RR (5 daily) = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".eg-tc-filter", ["daily"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_material_rapid(self, playwright_ctx, server_url):
        """material has no rapid games = 0."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".eg-tc-filter", ["rapid"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 0
        assert _no_results_visible(page, "eg-no-results")
        page.close()

    # -- Combined: balance + TC --

    def test_equal_blitz(self, playwright_ctx, server_url):
        """minor-or-queen, equal + blitz: R vs R (5 blitz) = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".balance-filter", ["equal"])
        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_equal_rapid(self, playwright_ctx, server_url):
        """minor-or-queen, equal + rapid: Q vs Q (5 rapid) = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".balance-filter", ["equal"])
        _set_checkboxes(page, ".eg-tc-filter", ["rapid"])
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_up_bullet(self, playwright_ctx, server_url):
        """minor-or-queen, up + bullet: R vs B has no bullet = 0."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".balance-filter", ["up"])
        _set_checkboxes(page, ".eg-tc-filter", ["bullet"])
        assert _filtered_count(page, ".eg-card") == 0
        page.close()

    def test_down_bullet(self, playwright_ctx, server_url):
        """minor-or-queen, down + bullet: N vs N (3 bullet) = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".balance-filter", ["down"])
        _set_checkboxes(page, ".eg-tc-filter", ["bullet"])
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    # -- Combined: TC + min games --

    def test_blitz_min_5(self, playwright_ctx, server_url):
        """minor-or-queen, blitz + min 5: R vs R (5 blitz), R vs B (5 blitz) = 2."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        _select_option(page, "eg-min-games-select", "5")
        assert _filtered_count(page, ".eg-card") == 2
        page.close()

    def test_blitz_min_10(self, playwright_ctx, server_url):
        """minor-or-queen, blitz + min 10: no entry has 10 blitz games = 0."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        _select_option(page, "eg-min-games-select", "10")
        assert _filtered_count(page, ".eg-card") == 0
        assert _no_results_visible(page, "eg-no-results")
        page.close()

    # -- Triple combo: definition + balance + TC --

    def test_material_equal_blitz(self, playwright_ctx, server_url):
        """material + equal + blitz: RB vs RN (5 blitz) = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".balance-filter", ["equal"])
        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_material_equal_daily(self, playwright_ctx, server_url):
        """material + equal + daily: RR vs RR (5 daily) = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".balance-filter", ["equal"])
        _set_checkboxes(page, ".eg-tc-filter", ["daily"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_material_up_bullet(self, playwright_ctx, server_url):
        """material + up + bullet: QR vs QR has 4 bullet games = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".balance-filter", ["up"])
        _set_checkboxes(page, ".eg-tc-filter", ["bullet"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_material_equal_bullet(self, playwright_ctx, server_url):
        """material + equal + bullet: no equal entry has bullet = 0."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".balance-filter", ["equal"])
        _set_checkboxes(page, ".eg-tc-filter", ["bullet"])
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 0
        assert _no_results_visible(page, "eg-no-results")
        page.close()

    # -- Quad combo: definition + balance + TC + min games --

    def test_material_up_blitz_min_3(self, playwright_ctx, server_url):
        """material + up + blitz + min 3: QR vs QR has 4 blitz = 1."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".balance-filter", ["up"])
        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        _select_option(page, "eg-min-games-select", "3")
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 1
        page.close()

    def test_material_up_blitz_min_5(self, playwright_ctx, server_url):
        """material + up + blitz + min 5: QR vs QR has only 4 blitz = 0."""
        page = self._goto_endgames(playwright_ctx, server_url)
        _select_option(page, "eg-def-select", "material")
        _set_checkboxes(page, ".balance-filter", ["up"])
        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        _select_option(page, "eg-min-games-select", "5")
        page.wait_for_timeout(200)
        assert _filtered_count(page, ".eg-card") == 0
        assert _no_results_visible(page, "eg-no-results")
        page.close()

    # -- Filter reset --

    def test_filter_reset_restores_all(self, playwright_ctx, server_url):
        """Narrowing filters then resetting restores original count."""
        page = self._goto_endgames(playwright_ctx, server_url)
        original = _filtered_count(page, ".eg-card")
        assert original == 4

        # Narrow down
        _set_checkboxes(page, ".eg-tc-filter", ["bullet"])
        assert _filtered_count(page, ".eg-card") == 1

        # Reset all
        _set_checkboxes(page, ".eg-tc-filter",
                        ["bullet", "blitz", "rapid", "daily"])
        assert _filtered_count(page, ".eg-card") == original
        page.close()

    # -- Empty state hides when filters restore matches --

    def test_empty_state_hides_on_restore(self, playwright_ctx, server_url):
        page = self._goto_endgames(playwright_ctx, server_url)
        _set_checkboxes(page, ".eg-tc-filter", [])
        assert _no_results_visible(page, "eg-no-results")

        _set_checkboxes(page, ".eg-tc-filter", ["blitz"])
        assert not _no_results_visible(page, "eg-no-results")
        assert _filtered_count(page, ".eg-card") > 0
        page.close()
