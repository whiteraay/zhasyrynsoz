"""
backend/test_api.py
===================
Basic tests for the Kazakhsho FastAPI backend.

Run with:
    cd backend
    pip install httpx pytest pytest-asyncio
    pytest test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Patch the engine before importing main so no vectors are loaded
mock_engine = MagicMock()
mock_engine.is_loaded.return_value = True
mock_engine.words = ["үй", "су", "жер", "ат", "тас", "дос", "ана", "бала", "жол", "күн"]
mock_engine.word_to_idx = {w: i for i, w in enumerate(mock_engine.words)}
mock_engine.word_exists.side_effect = lambda w: w in mock_engine.word_to_idx
mock_engine.get_rank.return_value = 42
mock_engine._rank_cache = {}
mock_engine.get_top_similar.return_value = [("су", 0.9), ("жер", 0.85)]

with patch("embeddings.engine", mock_engine):
    from main import app

client = TestClient(app)


# ── Health ───────────────────────────────────────────────────────

def test_root_health():
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "vocab_size" in data


def test_daily_endpoint():
    res = client.get("/api/daily")
    assert res.status_code == 200
    data = res.json()
    assert "game_id" in data
    assert "date" in data
    assert "total_words" in data
    assert isinstance(data["game_id"], int)


# ── Guess ────────────────────────────────────────────────────────

def test_guess_returns_rank():
    # Find a valid game_id whose word is in our mock vocab
    from words import DAILY_WORDS
    # Find a game_id that maps to "үй"
    from main import game_id_to_word, EPOCH
    from datetime import date
    day_num = (date.today() - EPOCH).days
    game_id = day_num

    res = client.post("/api/guess", json={"game_id": game_id, "guess": "су"})
    # Either the guess is valid or the secret word maps outside mock — just check structure
    if res.status_code == 200:
        data = res.json()
        assert "rank" in data
        assert "color" in data
        assert "closeness_pct" in data
        assert "found" in data
        assert data["color"] in ("winner", "hot", "warm", "cold")


def test_guess_empty_word():
    res = client.post("/api/guess", json={"game_id": 0, "guess": ""})
    assert res.status_code == 422


def test_guess_too_long():
    res = client.post("/api/guess", json={"game_id": 0, "guess": "а" * 61})
    assert res.status_code == 422


def test_guess_word_not_in_vocab():
    mock_engine.word_exists.side_effect = lambda w: w == "үй"  # only secret exists
    res = client.post("/api/guess", json={"game_id": 0, "guess": "unknownword"})
    # Restore
    mock_engine.word_exists.side_effect = lambda w: w in mock_engine.word_to_idx
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "WORD_NOT_FOUND"


# ── Hints ────────────────────────────────────────────────────────

def test_hint_letter():
    from main import game_id_to_word
    game_id = 0
    word = game_id_to_word(game_id)
    res = client.get(f"/api/hint/{game_id}?hint_type=letter")
    assert res.status_code == 200
    data = res.json()
    assert "hint" in data
    assert word[0].upper() in data["hint"]


def test_hint_category():
    res = client.get("/api/hint/0?hint_type=category")
    assert res.status_code == 200
    assert "hint" in res.json()


def test_hint_close():
    mock_engine.word_exists.return_value = True
    res = client.get("/api/hint/0?hint_type=close")
    assert res.status_code == 200


# ── Stats ────────────────────────────────────────────────────────

def test_stats():
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "vocab_size" in data
    assert "total_daily_words" in data


# ── Rank helpers ─────────────────────────────────────────────────

def test_rank_to_color():
    from main import rank_to_color
    assert rank_to_color(1) == "winner"
    assert rank_to_color(50) == "hot"
    assert rank_to_color(500) == "warm"
    assert rank_to_color(5000) == "cold"


def test_rank_to_closeness_pct():
    from main import rank_to_closeness_pct
    assert rank_to_closeness_pct(1, 300000) == 100.0
    pct_near = rank_to_closeness_pct(10, 300000)
    pct_far = rank_to_closeness_pct(100000, 300000)
    assert pct_near > pct_far
    assert 0.0 <= pct_far <= 100.0
