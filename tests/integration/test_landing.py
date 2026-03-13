"""Tests for the landing page."""

import pytest
from web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_landing_returns_200(client):
    resp = client.get('/')
    assert resp.status_code == 200


def test_landing_contains_brand(client):
    resp = client.get('/')
    html = resp.data.decode()
    assert 'Chess Coach' in html
    assert 'AI' in html


def test_landing_contains_form(client):
    resp = client.get('/')
    html = resp.data.decode()
    assert 'action="/analyze"' in html
    assert 'method="POST"' in html
    assert 'chesscom_username' in html
    assert 'lichess_username' in html


def test_landing_contains_headline(client):
    resp = client.get('/')
    html = resp.data.decode()
    assert 'Find your opening weaknesses.' in html
    assert 'Fix your endgame habits.' in html
