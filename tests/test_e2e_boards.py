"""End-to-end Playwright tests for lazy board loading.

These tests spin up the real Flask app and verify that SVG boards
actually render in the browser — catching race conditions, JS errors,
and fetch failures that unit tests cannot.
"""
import threading
import time

import chess
import pytest
from playwright.sync_api import sync_playwright, expect

from repertoire_analyzer import OpeningEvaluation
from report_generator import CoachingReportGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_eval(eco_code="B90", eco_name="Sicilian", my_color="white",
               deviating_side="white", fen=None, best_move="d2d4",
               played_move="g1f3", eval_loss_cp=50, my_result="win",
               time_class="blitz"):
    if fen is None:
        fen = chess.Board().fen()
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
        book_moves_uci=["e2e4", "d2d4"],
        eval_loss_cp=eval_loss_cp,
        game_moves_uci=[],
        my_result=my_result,
        time_class=time_class,
        game_url="https://www.chess.com/game/live/12345",
    )


def _make_endgame_entry(eg_type, balance="equal", total=5, fen=None,
                        color="white"):
    """Build one endgame stats dict matching what EndgameDetector produces."""
    if fen is None:
        fen = "4k3/8/8/8/8/8/4K3/4R3 w - - 0 1"  # K+R vs K
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
                // Walk up to check if any ancestor is hidden
                let node = el;
                while (node) {
                    if (node.style && node.style.display === 'none') return false;
                    node = node.parentElement;
                }
                return true;
            }).length;
    }""")


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
    """Spin up a Flask server with both endgame definitions and openings."""
    evals = [_make_eval() for _ in range(3)]

    endgame_stats = {
        "minor-or-queen": [
            _make_endgame_entry("R vs R"),
            _make_endgame_entry("Q vs Q"),
        ],
        "material": [
            _make_endgame_entry("RB vs RN"),
            _make_endgame_entry("RR vs RR"),
            _make_endgame_entry("QR vs QR"),
        ],
    }

    gen = CoachingReportGenerator(
        evals, chesscom_user="testplayer", endgame_stats=endgame_stats,
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
# Endgame board tests
# ---------------------------------------------------------------------------

class TestEndgameBoardLoading:
    """Verify that SVG boards load on the endgames page."""

    def test_boards_load_on_default_definition(self, playwright_ctx,
                                                server_url):
        """Boards for the default definition render as SVGs."""
        page = playwright_ctx.new_page()
        page.goto(f"{server_url}/endgames")
        page.wait_for_selector(".eg-board svg", timeout=10000)

        assert _visible_spinners(page) == 0, "Some boards still show spinner"
        page.close()

    def test_boards_load_after_switching_definition(self, playwright_ctx,
                                                     server_url):
        """Switching the definition dropdown loads boards for the new set."""
        page = playwright_ctx.new_page()
        page.goto(f"{server_url}/endgames")
        page.wait_for_selector(".eg-board svg", timeout=10000)

        # Open the definition panel then switch value
        page.select_option("#eg-def-select", "material", force=True)

        # Wait for a material card's board to load
        page.wait_for_selector(
            ".eg-card[data-definition='material'] .eg-board svg",
            timeout=10000,
        )

        assert _visible_spinners(page) == 0, (
            "Spinners remain after switching to material definition")
        page.close()

    def test_boards_load_after_switching_back(self, playwright_ctx,
                                               server_url):
        """Switching definition back and forth still loads boards."""
        page = playwright_ctx.new_page()
        page.goto(f"{server_url}/endgames")
        page.wait_for_selector(".eg-board svg", timeout=10000)

        page.select_option("#eg-def-select", "material", force=True)
        page.wait_for_selector(
            ".eg-card[data-definition='material'] .eg-board svg",
            timeout=10000,
        )

        page.select_option("#eg-def-select", "minor-or-queen", force=True)
        page.wait_for_selector(
            ".eg-card[data-definition='minor-or-queen'] .eg-board svg",
            timeout=10000,
        )

        assert _visible_spinners(page) == 0
        page.close()

    def test_no_js_errors_on_definition_switch(self, playwright_ctx,
                                                server_url):
        """No JS console errors when switching definitions."""
        page = playwright_ctx.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto(f"{server_url}/endgames")
        page.wait_for_selector(".eg-board svg", timeout=10000)

        page.select_option("#eg-def-select", "material", force=True)
        page.wait_for_selector(
            ".eg-card[data-definition='material'] .eg-board svg",
            timeout=10000,
        )

        assert errors == [], f"JS errors on page: {errors}"
        page.close()


# ---------------------------------------------------------------------------
# Openings board tests
# ---------------------------------------------------------------------------

class TestOpeningsBoardLoading:
    """Verify that SVG boards load on the openings page."""

    def test_boards_load_on_index(self, playwright_ctx, server_url):
        """Opening deviation boards render as SVGs."""
        page = playwright_ctx.new_page()
        page.goto(server_url)
        page.wait_for_selector(".board-best svg", timeout=10000)
        page.wait_for_selector(".board-played svg", timeout=10000)

        assert _visible_spinners(page) == 0
        page.close()

    def test_no_js_errors_on_openings(self, playwright_ctx, server_url):
        page = playwright_ctx.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto(server_url)
        page.wait_for_selector(".board-best svg", timeout=10000)

        assert errors == [], f"JS errors on page: {errors}"
        page.close()
