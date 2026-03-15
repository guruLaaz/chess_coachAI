"""Tests for web/reports.py — helper functions and DB-backed report routes."""

import sys
from collections import namedtuple
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

# Mock the db module before importing anything that touches it.
_mock_db = MagicMock()
sys.modules.setdefault('db', _mock_db)
sys.modules.setdefault('db.queries', _mock_db.queries)
sys.modules.setdefault('db.connection', _mock_db.connection)
sys.modules.setdefault('db.models', _mock_db.models)

from web.reports import (  # noqa: E402
    group_deviations,
    render_board_svg,
    move_to_san,
    format_clock,
    ply_to_move_label,
    format_date,
    prepare_deviation,
    get_opening_groups,
    load_openings_data,
    load_endgames_data,
    _aggregate_endgames,
)
from web.app import create_app  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — lightweight stand-in for OpeningEvaluation
# ---------------------------------------------------------------------------

OpeningEvaluation = namedtuple('OpeningEvaluation', [
    'eco_code', 'eco_name', 'my_color', 'deviation_ply', 'deviating_side',
    'eval_cp', 'is_fully_booked', 'fen_at_deviation', 'best_move_uci',
    'played_move_uci', 'book_moves_uci', 'eval_loss_cp', 'game_moves_uci',
    'game_url', 'my_result', 'time_class', 'opponent_name', 'end_time',
])


def _make_eval(**overrides):
    defaults = dict(
        eco_code='B90', eco_name='Sicilian Najdorf',
        my_color='white', deviation_ply=10, deviating_side='white',
        eval_cp=-30, is_fully_booked=False,
        fen_at_deviation='rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',
        best_move_uci='e7e5', played_move_uci='d7d5',
        book_moves_uci=['e7e5', 'c7c5'], eval_loss_cp=120,
        game_moves_uci=['e2e4', 'd7d5'], game_url='https://chess.com/game/123',
        my_result='loss', time_class='blitz', opponent_name='opponent1',
        end_time=datetime(2025, 6, 15, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return OpeningEvaluation(**defaults)


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------


class TestGroupDeviations:
    def test_empty_input(self):
        devs, counts, results = group_deviations([])
        assert devs == []
        assert counts == {}
        assert results == {}

    def test_single_deviation(self):
        ev = _make_eval()
        devs, counts, results = group_deviations([ev])
        assert len(devs) == 1
        key = (ev.fen_at_deviation, ev.played_move_uci)
        assert counts[key] == 1
        assert results[key]['loss'] == 1

    def test_groups_by_fen_and_move(self):
        ev1 = _make_eval(eval_loss_cp=100, my_result='loss')
        ev2 = _make_eval(eval_loss_cp=200, my_result='win')
        devs, counts, results = group_deviations([ev1, ev2])
        # Same fen+move → single group, keeps worst (200cp)
        assert len(devs) == 1
        assert devs[0].eval_loss_cp == 200
        key = (ev1.fen_at_deviation, ev1.played_move_uci)
        assert counts[key] == 2
        assert results[key] == {'win': 1, 'loss': 1, 'draw': 0}

    def test_different_moves_separate_groups(self):
        ev1 = _make_eval(played_move_uci='d7d5')
        ev2 = _make_eval(played_move_uci='e7e6')
        devs, counts, _ = group_deviations([ev1, ev2])
        assert len(devs) == 2


class TestMoveToSan:
    def test_valid_move(self):
        fen = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'
        assert move_to_san(fen, 'e7e5') == 'e5'

    def test_empty_move(self):
        assert move_to_san('startpos', '') == 'N/A'

    def test_invalid_move_returns_uci(self):
        fen = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'
        assert move_to_san(fen, 'z9z9') == 'z9z9'


class TestFormatClock:
    def test_none(self):
        assert format_clock(None) == '?'

    def test_under_hour(self):
        assert format_clock(90) == '1:30'

    def test_over_hour(self):
        assert format_clock(3661) == '1:01:01'

    def test_zero(self):
        assert format_clock(0) == '0:00'


class TestPlyToMoveLabel:
    def test_white_first_move(self):
        assert ply_to_move_label(0, 'white') == '1.'

    def test_black_first_move(self):
        assert ply_to_move_label(1, 'black') == '1...'

    def test_white_move_ten(self):
        assert ply_to_move_label(18, 'white') == '10.'


class TestFormatDate:
    def test_none(self):
        assert format_date(None) == ''

    def test_formats_correctly(self):
        dt = datetime(2025, 9, 5, tzinfo=timezone.utc)
        assert format_date(dt) == 'September 5, 2025'


class TestPrepareDeviation:
    def test_returns_expected_keys(self):
        ev = _make_eval()
        counts = {(ev.fen_at_deviation, ev.played_move_uci): 3}
        results = {(ev.fen_at_deviation, ev.played_move_uci): {
            'win': 1, 'loss': 1, 'draw': 1
        }}
        item = prepare_deviation(ev, counts, results)
        assert item['eco_code'] == 'B90'
        assert item['times_played'] == 3
        assert item['win_pct'] == 33
        assert item['loss_pct'] == 33
        assert item['platform'] == 'chesscom'
        assert 'fen' in item
        assert 'best_san' in item
        assert 'played_san' in item


class TestGetOpeningGroups:
    def test_groups_by_eco_and_color(self):
        ev1 = _make_eval(eco_code='B90', my_color='white')
        ev2 = _make_eval(eco_code='B90', my_color='white')
        ev3 = _make_eval(eco_code='C50', my_color='black')
        groups = get_opening_groups([ev1, ev2, ev3])
        assert len(groups) == 2
        # Sorted by count desc — B90 white has 2
        assert groups[0]['eco_code'] == 'B90'
        assert groups[0]['count'] == 2


class TestRenderBoardSvg:
    def test_returns_svg_string(self):
        fen = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'
        svg = render_board_svg(fen, 'e7e5', 'white', '#22c55e')
        assert '<svg' in svg
        assert 'viewBox' in svg

    def test_no_move(self):
        fen = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'
        svg = render_board_svg(fen, '', 'black', '')
        assert '<svg' in svg


# ---------------------------------------------------------------------------
# Data loader tests (mock DB)
# ---------------------------------------------------------------------------


class TestLoadOpeningsData:
    @patch('web.reports.dbq')
    def test_empty_evaluations(self, mock_dbq):
        mock_dbq.get_all_evaluations_for_user.return_value = []
        data = load_openings_data('testuser', None)
        assert data['total_games_analyzed'] == 0
        assert data['items'] == []
        assert data['accuracy_pct'] == 0

    @patch('web.reports.dbq')
    def test_with_evaluations(self, mock_dbq):
        evs = [
            _make_eval(eval_loss_cp=120, deviating_side='white'),
            _make_eval(eval_loss_cp=50, deviating_side='white',
                       played_move_uci='e7e6'),
            _make_eval(is_fully_booked=True, deviating_side='black'),
        ]
        mock_dbq.get_all_evaluations_for_user.return_value = evs
        data = load_openings_data('testuser', None)
        assert data['total_games_analyzed'] == 3
        assert len(data['items']) == 2  # 2 deviations (3rd is fully booked)
        assert data['theory_knowledge_pct'] == 33  # 1 of 3 fully booked/opp
        assert data['username'] == 'testuser'


class TestLoadEndgamesData:
    @patch('web.reports.dbq')
    def test_no_evaluations(self, mock_dbq):
        mock_dbq.get_all_evaluations_for_user.return_value = []
        data = load_endgames_data('testuser', None)
        assert data['eg_total_games'] == 0
        assert data['stats'] == []

    @patch('web.reports.dbq')
    def test_no_endgames(self, mock_dbq):
        mock_dbq.get_all_evaluations_for_user.return_value = [
            _make_eval(game_url='https://chess.com/game/1'),
        ]
        mock_dbq.get_all_endgames_for_user.return_value = {}
        data = load_endgames_data('testuser', None)
        assert data['eg_total_games'] == 0


class TestAggregateEndgamesGameMeta:
    """Verify that _aggregate_endgames propagates game metadata."""

    def _make_endgame_info(self, **overrides):
        from fetchers.endgame_detector import EndgameInfo
        defaults = dict(
            endgame_type='R vs R', endgame_ply=40,
            material_balance='equal', my_result='win',
            fen_at_endgame='8/8/8/8/8/8/8/8 w - - 0 1',
            game_url='https://chess.com/game/1',
            material_diff=0, my_clock=300.0, opp_clock=250.0,
        )
        defaults.update(overrides)
        return EndgameInfo(**defaults)

    def test_game_meta_propagated(self):
        """Game color, time_class, end_time should come from game_meta."""
        raw = {
            'https://chess.com/game/1': {
                'minor-or-queen': self._make_endgame_info(),
            },
        }
        game_meta = {
            'https://chess.com/game/1': {
                'my_color': 'black',
                'time_class': 'rapid',
                'end_time': datetime(2025, 9, 1, tzinfo=timezone.utc),
                'opponent_name': 'Magnus',
            },
        }
        result = _aggregate_endgames(raw, game_meta)
        entry = result['minor-or-queen'][0]
        games = entry['all_games']
        assert len(games) == 1
        assert games[0]['my_color'] == 'black'
        assert games[0]['time_class'] == 'rapid'
        assert games[0]['end_time'] == datetime(2025, 9, 1, tzinfo=timezone.utc)
        assert games[0]['opponent_name'] == 'Magnus'
        # example_opponent_name should come from the example game
        assert entry['example_opponent_name'] == 'Magnus'
        # tc_breakdown should be computed from games
        assert entry['tc_breakdown'] == {'rapid': {'wins': 1, 'losses': 0, 'draws': 0}}

    def test_skipped_without_meta(self):
        """Without game_meta, games should be skipped."""
        raw = {
            'https://chess.com/game/1': {
                'minor-or-queen': self._make_endgame_info(),
            },
        }
        result = _aggregate_endgames(raw)
        assert result == {}


# ---------------------------------------------------------------------------
# Route integration tests (mock DB, real template rendering)
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


class TestOpeningsRoute:
    """Tests for /api/report/openings JSON endpoint."""

    @patch('web.routes.load_endgames_data')
    @patch('web.routes.load_openings_data')
    @patch('web.routes.queries')
    def test_returns_json_with_items(self, mock_q, mock_openings,
                                     mock_endgames, client):
        mock_q.get_latest_job.return_value = {'id': 1, 'status': 'complete', 'total_games': 10}
        mock_openings.return_value = {
            'username': 'hikaru',
            'chesscom_user': 'hikaru',
            'lichess_user': None,
            'items': [{
                'eco_name': 'Sicilian Najdorf',
                'eco_code': 'B90',
                'color': 'white',
                'eval_loss_display': '-1.2',
                'eval_loss_class': 'bad',
                'eval_display': '-0.3',
                'eval_class': 'bad',
                'move_label': '6.',
                'played_san': 'd5',
                'best_san': 'e5',
                'book_moves': 'e5, c5',
                'fen': 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',
                'best_move_uci': 'e7e5',
                'played_move_uci': 'd7d5',
                'times_played': 3,
                'game_url': 'https://chess.com/game/123',
                'eval_loss_raw': 120,
                'win_pct': 33,
                'loss_pct': 33,
                'time_class': 'blitz',
                'platform': 'chesscom',
                'opponent_name': 'opponent1',
                'game_date': 'June 15, 2025',
                'game_date_iso': '2025-06-15',
            }],
            'groups': [{'eco_code': 'B90', 'eco_name': 'Sicilian Najdorf',
                        'color': 'white', 'count': 1}],
            'total_games_analyzed': 10,
            'avg_eval_loss': 1.2,
            'theory_knowledge_pct': 60,
            'accuracy_pct': 40,
            'new_games_analyzed': 2,
        }
        mock_endgames.return_value = {'endgame_count': 5}

        resp = client.get('/api/report/openings/hikaru')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['username'] == 'hikaru'
        assert len(data['items']) == 1
        assert data['items'][0]['eco_code'] == 'B90'
        assert data['endgame_count'] == 5

    @patch('web.routes.queries')
    def test_no_job_returns_redirect(self, mock_q, client):
        mock_q.get_latest_job.return_value = None
        resp = client.get('/api/report/openings/hikaru')
        data = resp.get_json()
        assert data['redirect'] == '/'


class TestOpeningDetailRoute:
    """Tests for /api/report/openings/{path}/{eco}/{color} JSON filtering."""

    @patch('web.routes.load_endgames_data')
    @patch('web.routes.load_openings_data')
    @patch('web.routes.queries')
    def test_filters_by_eco_and_color(self, mock_q, mock_openings,
                                      mock_endgames, client):
        mock_q.get_latest_job.return_value = {'status': 'complete', 'total_games': 5}
        mock_openings.return_value = {
            'username': 'hikaru',
            'chesscom_user': 'hikaru',
            'lichess_user': None,
            'items': [
                {'eco_code': 'B90', 'color': 'white', 'eco_name': 'Najdorf'},
                {'eco_code': 'C50', 'color': 'black', 'eco_name': 'Italian'},
            ],
            'groups': [],
            'total_games_analyzed': 5,
            'avg_eval_loss': 0.75,
            'theory_knowledge_pct': 50,
            'accuracy_pct': 50,
            'new_games_analyzed': 0,
        }
        mock_endgames.return_value = {'endgame_count': 0}

        resp = client.get('/api/report/openings/hikaru/B90/white')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['filter_eco'] == 'B90'
        assert data['filter_color'] == 'white'
        assert len(data['items']) == 1
        assert data['items'][0]['eco_code'] == 'B90'


class TestEndgameRoutes:
    """Tests for /api/report/endgames and /api/report/endgames-all JSON."""

    @patch('web.routes.load_openings_data')
    @patch('web.routes.load_endgames_data')
    @patch('web.routes.queries')
    def test_endgames_json(self, mock_q, mock_endgames, mock_openings, client):
        mock_q.get_latest_job.return_value = {'status': 'complete', 'total_games': 10}
        mock_endgames.return_value = {
            'username': 'hikaru',
            'chesscom_user': 'hikaru',
            'lichess_user': None,
            'stats': [],
            'endgame_count': 5,
            'definitions': ['minor-or-queen'],
            'default_definition': 'minor-or-queen',
            'eg_total_games': 5,
            'eg_types_count': 2,
            'eg_win_pct': 60,
        }
        mock_openings.return_value = {
            'items': [{'eco_code': 'B20'}],
            'groups': [{'eco_code': 'B20', 'count': 1}],
        }

        resp = client.get('/api/report/endgames/hikaru')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['endgame_count'] == 5
        assert data['total'] == 1
        assert len(data['groups']) == 1

    @patch('web.routes.load_endgames_all_data')
    @patch('web.routes.queries')
    def test_endgames_all_json(self, mock_q, mock_all, client):
        mock_q.get_latest_job.return_value = {'status': 'complete', 'total_games': 10}
        mock_all.return_value = {
            'username': 'hikaru',
            'chesscom_user': 'hikaru',
            'lichess_user': None,
            'eg_type': 'R vs R',
            'balance': 'equal',
            'definition': 'minor-or-queen',
            'games': [],
            'groups': [],
            'endgame_count': 0,
            'total': 0,
            'page': 'endgames_all',
            'sidebar_filters': False,
        }

        resp = client.get('/api/report/endgames-all/hikaru?def=minor-or-queen'
                          '&type=R+vs+R&balance=equal')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['eg_type'] == 'R vs R'
        assert data['balance'] == 'equal'


class TestRenderBoardsAPI:
    def test_render_boards_returns_svgs(self, client):
        resp = client.post('/u/hikaru/api/render-boards',
                           json=[{
                               'fen': 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',
                               'move': 'e7e5',
                               'color': 'white',
                               'arrow_color': '#22c55e',
                           }])
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert '<svg' in data[0]

    def test_render_boards_no_move(self, client):
        resp = client.post('/u/hikaru/api/render-boards',
                           json=[{
                               'fen': 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',
                               'color': 'black',
                           }])
        assert resp.status_code == 200
        data = resp.get_json()
        assert '<svg' in data[0]


