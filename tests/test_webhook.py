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

def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_webhook_success():
    payload = {
        "message_id": "test_m1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello World"
    }
    body = json.dumps(payload).encode()
    sig = generate_signature(body, SECRET)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": sig, "Content-Type": "application/json"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_webhook_duplicate():
    payload = {
        "message_id": "test_m2",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "First"
    }
    body = json.dumps(payload).encode()
    sig = generate_signature(body, SECRET)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": sig, "Content-Type": "application/json"}
    )
    assert response.status_code == 200

    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": sig, "Content-Type": "application/json"}
    )
    assert response.status_code == 200

def test_webhook_invalid_signature():
    payload = {"message_id": "bad_sig"}
    body = json.dumps(payload).encode()
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": "wrong", "Content-Type": "application/json"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid signature"

def test_webhook_missing_signature():
    payload = {"message_id": "no_sig"}
    body = json.dumps(payload).encode()
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 401

def test_webhook_validation_error():
    payload = {
        "message_id": "inv_phone",
        "from": "123",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z"
    }
    body = json.dumps(payload).encode()
    sig = generate_signature(body, SECRET)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Signature": sig, "Content-Type": "application/json"}
    )
    assert response.status_code == 422
