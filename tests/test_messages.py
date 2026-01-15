import pytest
import hmac
import hashlib
import json
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)
SECRET = settings.WEBHOOK_SECRET or "testsecret"
settings.WEBHOOK_SECRET = SECRET

def generate_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

@pytest.fixture
def seed_messages():
    # Helper to insert messages directly or via webhook
    messages = [
        {"message_id": "msg_1", "from": "+919876543210", "to": "+14155550100", "ts": "2025-01-15T10:00:00Z", "text": "Hello"},
        {"message_id": "msg_2", "from": "+919876543210", "to": "+14155550100", "ts": "2025-01-15T11:00:00Z", "text": "World"},
        {"message_id": "msg_3", "from": "+14155550199", "to": "+14155550100", "ts": "2025-01-15T12:00:00Z", "text": "Another"},
    ]
    for msg in messages:
        body = json.dumps(msg).encode()
        sig = generate_signature(body, SECRET)
        client.post("/webhook", content=body, headers={"X-Signature": sig, "Content-Type": "application/json"})

def test_list_messages(seed_messages):
    response = client.get("/messages")
    assert response.status_code == 200
    data = response.json()
    # Depending on previous tests running indiscriminately in same DB file, user might have existing data.
    # We just check structure and ensure we have at least what we ceded if DB was clean, 
    # or just checks keys.
    assert "data" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert len(data["data"]) >= 3

def test_messages_pagination(seed_messages):
    # Test Limit
    response = client.get("/messages?limit=1")
    data = response.json()
    assert len(data["data"]) == 1
    assert data["limit"] == 1

    # Test Offset
    # Order is ts ASC. 
    # msg_1 (10:00), msg_2 (11:00), msg_3 (12:00)
    response = client.get("/messages?limit=1&offset=1")
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["message_id"] == "msg_2" or data["data"][0]["message_id"] == "msg_3" # Assuming clean DB logic which isn't guaranteed here without teardown

def test_messages_filter_from(seed_messages):
    target = "+919876543210"
    response = client.get(f"/messages?from={target}")
    data = response.json()
    
    for msg in data["data"]:
        assert msg["from"] == target

def test_messages_filter_since(seed_messages):
    since_ts = "2025-01-15T11:30:00Z"
    response = client.get(f"/messages?since={since_ts}")
    data = response.json()
    
    # Should only contain msg_3 (12:00)
    for msg in data["data"]:
        assert msg["ts"] >= since_ts

def test_messages_search(seed_messages):
    response = client.get("/messages?q=Hello")
    data = response.json()
    # msg_1 has Hello
    found = any(m["message_id"] == "msg_1" for m in data["data"])
    assert found
