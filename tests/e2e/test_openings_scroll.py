"""E2E tests for the openings page infinite scroll and lazy board loading.

Uses Playwright to verify that:
- Only the first batch of cards is visible on initial page load
- Scrolling reveals additional batches
- Board SVGs are fetched lazily per batch
- Not all cards are rendered visible at once
"""

import threading

import pytest

from conftest import mock_db_modules

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skip(reason="Pending Vue SPA E2E rewrite"),
]

PAGE_SIZE = 10  # must match the JS PAGE_SIZE in openings.html
TOTAL_CARDS = 50  # enough to need multiple scroll batches


def _make_items(n):
    """Generate n fake deviation items for the template."""
    items = []
    for i in range(n):
        items.append({
            'eco_name': f'Opening {i}',
            'eco_code': f'B{i:02d}',
            'color': 'white',
            'eval_loss_display': '-0.5',
            'eval_loss_class': 'bad',
            'eval_display': '+0.3',
            'eval_class': 'good',
            'move_label': f'{i + 1}.',
            'played_san': 'e4',
            'best_san': 'd4',
            'book_moves': 'd4, c4',
            'fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
            'best_move_uci': 'd2d4',
            'played_move_uci': 'e2e4',
            'times_played': 3,
            'game_url': f'https://chess.com/game/{i}',
            'eval_loss_raw': 50 + i,
            'win_pct': 45,
            'loss_pct': 35,
            'time_class': 'blitz',
            'platform': 'chesscom',
            'opponent_name': f'opponent{i}',
            'game_date': 'January 1, 2026',
            'game_date_iso': '2026-01-01',
        })
    return items


def _make_template_data(n=TOTAL_CARDS):
    """Build the full template context for openings.html."""
    return {
        'username': 'testplayer',
        'chesscom_user': 'testplayer',
        'lichess_user': None,
        'items': _make_items(n),
        'groups': [{'eco_code': 'B00', 'eco_name': 'Test Opening',
                    'color': 'white', 'count': n}],
        'total_games_analyzed': n * 10,
        'avg_eval_loss': 0.5,
        'theory_knowledge_pct': 60,
        'accuracy_pct': 75,
        'new_games_analyzed': 0,
        'user_path': 'testplayer',
        'page': 'openings',
        'filter_eco': None,
        'filter_color': None,
        'endgame_count': 0,
    }


@pytest.fixture(scope='module')
def live_server():
    """Start the Flask app on a random port in a background thread."""
    _mock_db, cleanup = mock_db_modules()
    try:
        from web.app import create_app
        app = create_app()
        app.config['TESTING'] = True

        data = _make_template_data()

        # Patch routes to serve our mock data directly
        @app.route('/test/openings')
        def test_openings():
            from flask import render_template
            return render_template('openings.html', **data)

        # Fake board renderer that returns minimal SVGs quickly
        @app.route('/u/testplayer/api/render-boards', methods=['POST'])
        def fake_render_boards():
            from flask import request, jsonify
            specs = request.get_json()
            return jsonify(['<svg class="board-svg"></svg>'] * len(specs))

        server = None
        port = 5099

        def run():
            nonlocal server
            from werkzeug.serving import make_server
            server = make_server('127.0.0.1', port, app)
            server.serve_forever()

        t = threading.Thread(target=run, daemon=True)
        t.start()

        yield f'http://127.0.0.1:{port}'

        if server:
            server.shutdown()
    finally:
        cleanup()


@pytest.fixture(scope='module')
def browser_context(live_server):
    """Provide a Playwright browser context (module-scoped for speed)."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1280, 'height': 720})
    yield context
    context.close()
    browser.close()
    pw.stop()


@pytest.fixture
def page(browser_context):
    p = browser_context.new_page()
    yield p
    p.close()


class TestInitialPageLoad:
    """On first load, only PAGE_SIZE cards should be visible."""

    def test_only_first_batch_visible(self, page, live_server):
        page.goto(f'{live_server}/test/openings')
        # Wait for JS to run and first batch to appear
        page.wait_for_selector('.card[data-filtered="yes"]',
                               state='visible', timeout=5000)

        visible = page.eval_on_selector_all(
            '.card',
            'cards => cards.filter(c => c.style.display !== "none").length'
        )
        assert visible == PAGE_SIZE, (
            f'Expected {PAGE_SIZE} visible cards on initial load, got {visible}'
        )

    def test_total_cards_in_dom(self, page, live_server):
        page.goto(f'{live_server}/test/openings')
        page.wait_for_selector('.card', timeout=5000)

        total = page.eval_on_selector_all('.card', 'cards => cards.length')
        assert total == TOTAL_CARDS, (
            f'Expected {TOTAL_CARDS} total cards in DOM, got {total}'
        )

    def test_hidden_cards_not_displayed(self, page, live_server):
        page.goto(f'{live_server}/test/openings')
        page.wait_for_selector('.card[data-filtered="yes"]',
                               state='visible', timeout=5000)

        hidden = page.eval_on_selector_all(
            '.card',
            'cards => cards.filter(c => c.style.display === "none").length'
        )
        assert hidden == TOTAL_CARDS - PAGE_SIZE


class TestInfiniteScroll:
    """Scrolling should reveal additional batches of cards."""

    def test_scroll_loads_second_batch(self, page, live_server):
        page.goto(f'{live_server}/test/openings')
        page.wait_for_selector('.card[data-filtered="yes"]',
                               state='visible', timeout=5000)

        # Wait for board fetch to complete (fetchingBoards = false)
        page.wait_for_function('() => !window.fetchingBoards',
                               timeout=5000)

        # Scroll to bottom to trigger next batch
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        page.wait_for_timeout(500)

        visible = page.eval_on_selector_all(
            '.card',
            'cards => cards.filter(c => c.style.display !== "none").length'
        )
        assert visible == PAGE_SIZE * 2, (
            f'Expected {PAGE_SIZE * 2} visible cards after one scroll, '
            f'got {visible}'
        )

    def test_multiple_scrolls_load_more(self, page, live_server):
        page.goto(f'{live_server}/test/openings')
        page.wait_for_selector('.card[data-filtered="yes"]',
                               state='visible', timeout=5000)

        # Scroll multiple times
        for _ in range(4):
            page.wait_for_function('() => !window.fetchingBoards',
                                   timeout=5000)
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(500)

        visible = page.eval_on_selector_all(
            '.card',
            'cards => cards.filter(c => c.style.display !== "none").length'
        )
        assert visible == TOTAL_CARDS, (
            f'Expected all {TOTAL_CARDS} cards visible after scrolling '
            f'to end, got {visible}'
        )

    def test_no_extra_cards_after_all_loaded(self, page, live_server):
        page.goto(f'{live_server}/test/openings')
        page.wait_for_selector('.card[data-filtered="yes"]',
                               state='visible', timeout=5000)

        # Scroll enough times to load everything
        for _ in range(6):
            page.wait_for_function('() => !window.fetchingBoards',
                                   timeout=5000)
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(300)

        visible = page.eval_on_selector_all(
            '.card',
            'cards => cards.filter(c => c.style.display !== "none").length'
        )
        # Should never exceed TOTAL_CARDS
        assert visible == TOTAL_CARDS


class TestLazyBoardLoading:
    """Board SVGs should be fetched lazily, not all at once."""

    def test_boards_load_for_visible_cards(self, page, live_server):
        page.goto(f'{live_server}/test/openings')
        page.wait_for_selector('.card[data-filtered="yes"]',
                               state='visible', timeout=5000)
        # Wait for first batch boards to load
        page.wait_for_function(
            '() => !window.fetchingBoards',
            timeout=5000
        )

        # Visible cards should have SVG boards (no more spinners)
        spinners_in_visible = page.eval_on_selector_all(
            '.card',
            '''cards => cards
                .filter(c => c.style.display !== "none")
                .filter(c => c.querySelector(".board-spinner"))
                .length'''
        )
        assert spinners_in_visible == 0, (
            f'Visible cards should have loaded boards, '
            f'but {spinners_in_visible} still show spinners'
        )

    def test_hidden_cards_still_have_spinners(self, page, live_server):
        page.goto(f'{live_server}/test/openings')
        page.wait_for_selector('.card[data-filtered="yes"]',
                               state='visible', timeout=5000)
        page.wait_for_function('() => !window.fetchingBoards',
                               timeout=5000)

        # Hidden cards should still have spinner placeholders
        spinners_in_hidden = page.eval_on_selector_all(
            '.card',
            '''cards => cards
                .filter(c => c.style.display === "none")
                .filter(c => c.querySelector(".board-spinner"))
                .length'''
        )
        assert spinners_in_hidden == TOTAL_CARDS - PAGE_SIZE, (
            f'Expected {TOTAL_CARDS - PAGE_SIZE} hidden cards with spinners, '
            f'got {spinners_in_hidden}'
        )
