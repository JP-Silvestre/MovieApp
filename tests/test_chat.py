import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import mongomock
import pytest


@pytest.fixture
def client():
    """Flask test client backed by an in-memory MongoDB."""
    mock_db = mongomock.MongoClient()["movies_db"]
    mock_db.movies.insert_many([
        {"title": "The Dark Knight", "category": "thriller", "year": 2008,
         "description": "Batman faces the Joker."},
        {"title": "Superbad", "category": "comedy", "year": 2007,
         "description": "Two teens try to party."},
    ])
    with patch("app.db", mock_db):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as test_client:
            yield test_client


def ollama_response(payload):
    """Build a fake urlopen() result that works as a context manager."""
    return BytesIO(json.dumps(payload).encode("utf-8"))


def user_says(text):
    return {"messages": [{"role": "user", "content": text}]}


# ---------- /api/movies error path ----------

def test_movies_returns_500_when_db_fails(client):
    with patch("app.db") as broken_db:
        broken_db.movies.find.side_effect = RuntimeError("db down")
        res = client.get("/api/movies")
    assert res.status_code == 500
    assert res.get_json() == {"error": "db down"}


# ---------- /api/chat input validation ----------

@pytest.mark.parametrize("body, expected_error", [
    (None, "Send a messages array."),
    ({"messages": "hi"}, "Send a messages array."),
    ({"messages": ["hi"]}, "Messages must have a user or assistant role."),
    ({"messages": [{"role": "system", "content": "hi"}]},
     "Messages must have a user or assistant role."),
    ({"messages": [{"role": 1, "content": "hi"}]},
     "Messages must have a user or assistant role."),
    ({"messages": [{"role": "user", "content": "   "}]},
     "Each message must contain 1 to 2000 characters."),
    ({"messages": [{"role": "user", "content": 42}]},
     "Each message must contain 1 to 2000 characters."),
    ({"messages": [{"role": "user", "content": "x" * 2001}]},
     "Each message must contain 1 to 2000 characters."),
    ({"messages": []}, "The latest message must be from the user."),
    ({"messages": [{"role": "user", "content": "hi"},
                   {"role": "assistant", "content": "hello"}]},
     "The latest message must be from the user."),
])
def test_chat_rejects_invalid_input(client, body, expected_error):
    if body is None:
        res = client.post("/api/chat", data="not json", content_type="text/plain")
    else:
        res = client.post("/api/chat", json=body)
    assert res.status_code == 400
    assert res.get_json() == {"error": expected_error}


# ---------- /api/chat model calls ----------

def test_chat_returns_model_reply_and_sends_catalog(client):
    with patch("app.urlopen",
               return_value=ollama_response({"message": {"content": "  Watch Superbad!  "}})
               ) as fake_urlopen:
        res = client.post("/api/chat", json=user_says("  Recommend a comedy  "))

    assert res.status_code == 200
    assert res.get_json() == {"reply": "Watch Superbad!"}

    sent_request = fake_urlopen.call_args.args[0]
    sent = json.loads(sent_request.data)
    assert sent_request.full_url.endswith("/api/chat")
    assert sent["stream"] is False
    assert sent["messages"][0]["role"] == "system"
    assert "Superbad" in sent["messages"][0]["content"]
    assert sent["messages"][-1] == {"role": "user", "content": "Recommend a comedy"}


def test_chat_only_forwards_last_12_messages(client):
    history = []
    for i in range(10):
        history.append({"role": "user", "content": f"question {i}"})
        history.append({"role": "assistant", "content": f"answer {i}"})
    history.append({"role": "user", "content": "latest"})

    with patch("app.urlopen",
               return_value=ollama_response({"message": {"content": "ok"}})
               ) as fake_urlopen:
        res = client.post("/api/chat", json={"messages": history})

    assert res.status_code == 200
    sent = json.loads(fake_urlopen.call_args.args[0].data)
    assert len(sent["messages"]) == 1 + 12  # system prompt + last 12


@pytest.mark.parametrize("model_payload", [{"message": {"content": "   "}}, {}])
def test_chat_returns_502_on_empty_reply(client, model_payload):
    with patch("app.urlopen", return_value=ollama_response(model_payload)):
        res = client.post("/api/chat", json=user_says("hi"))
    assert res.status_code == 502
    assert res.get_json() == {"error": "The model returned an empty reply."}


@pytest.mark.parametrize("failure", [
    URLError("connection refused"),
    HTTPError("http://ollama", 500, "boom", None, None),
    TimeoutError("too slow"),
])
def test_chat_returns_502_when_model_unreachable(client, failure):
    with patch("app.urlopen", side_effect=failure):
        res = client.post("/api/chat", json=user_says("hi"))
    assert res.status_code == 502
    assert "unavailable" in res.get_json()["error"]


def test_chat_returns_502_on_invalid_model_json(client):
    with patch("app.urlopen", return_value=BytesIO(b"not json")):
        res = client.post("/api/chat", json=user_says("hi"))
    assert res.status_code == 502


def test_chat_returns_500_on_unexpected_error(client):
    with patch("app.db") as broken_db:
        broken_db.movies.find.side_effect = RuntimeError("db down")
        res = client.post("/api/chat", json=user_says("hi"))
    assert res.status_code == 500
    assert res.get_json() == {"error": "Unable to answer right now. Please try again."}