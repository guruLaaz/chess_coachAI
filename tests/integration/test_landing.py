"""Tests for the landing page (now served by Vue SPA)."""

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


def test_landing_serves_vue_spa(client):
    resp = client.get('/')
    html = resp.data.decode()
    assert '<div id="app"></div>' in html


def test_spa_catch_all_serves_index(client):
    """Non-API paths should return the SPA index.html."""
    resp = client.get('/u/someuser')
    assert resp.status_code == 200
    html = resp.data.decode()
    assert '<div id="app"></div>' in html


def test_catch_all_404_for_unknown_api(client):
    """API-prefixed paths with no matching route should 404."""
    resp = client.get('/api/nonexistent')
    assert resp.status_code == 404
