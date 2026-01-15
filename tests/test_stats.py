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
def seed_stats_data():
    messages = [
        {"message_id": "s1", "from": "+910000000001", "to": "+1000", "ts": "2025-01-01T10:00:00Z", "text": "A"},
        {"message_id": "s2", "from": "+910000000001", "to": "+1000", "ts": "2025-01-02T10:00:00Z", "text": "B"},
        {"message_id": "s3", "from": "+910000000002", "to": "+1000", "ts": "2025-01-03T10:00:00Z", "text": "C"},
    ]
    for msg in messages:
        body = json.dumps(msg).encode()
        sig = generate_signature(body, SECRET)
        client.post("/webhook", content=body, headers={"X-Signature": sig, "Content-Type": "application/json"})

def test_stats_structure(seed_stats_data):
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    expected_keys = {
        "total_messages", 
        "senders_count", 
        "messages_per_sender", 
        "first_message_ts", 
        "last_message_ts"
    }
    assert expected_keys.issubset(data.keys())
    
    assert isinstance(data["total_messages"], int)
    assert isinstance(data["senders_count"], int)
    assert isinstance(data["messages_per_sender"], list)
    
    # Check simple logic if base is clean or at least cumulative
    assert data["total_messages"] >= 3
    
    # Check top sender logic
    senders = data["messages_per_sender"]
    if senders:
        assert "from" in senders[0]
        assert "count" in senders[0]
