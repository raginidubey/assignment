# Webhook API Service

Production-grade FastAPI service for ingesting WhatsApp-like messages.

## Setup Used
VSCode + AI Assistant for refactoring

## Usage

### Prerequisites
- Docker & Docker Compose
- Make (optional, for shortcuts)

### Running
1. Start the service:
```bash
make up
# OR
docker-compose up -d --build
```
The API will be available at `http://localhost:8000`.

2. Stop the service:
```bash
make down
```

3. View logs:
```bash
make logs
```

4. Run tests:
```bash
make test
```

## Endpoints

- `POST /webhook`: Ingest message (Requires `X-Signature`).
- `GET /messages`: List messages (Supports `limit`, `offset`, `from`, `since`, `q`).
- `GET /stats`: View analytics.
- `GET /health/live`: Liveness probe.
- `GET /health/ready`: Readiness probe.
- `GET /metrics`: Prometheus metrics.

## Design Decisions

### HMAC Verification
Implemented as a FastAPI Dependency `verify_signature`. It:
1. Checks for `WEBHOOK_SECRET`.
2. Verifies `X-Signature` header exists.
3. Computes `HMAC-SHA256` of the raw request body.
4. Compares using `hmac.compare_digest` (constant time).

### Database & Idempotency
- **SQLite**: Stored at `/data/app.db` (mounted volume).
- **Idempotency**: Leveraging SQLite's `PRIMARY KEY` constraint on `message_id`.
    - If `INSERT` fails with `IntegrityError`, we return 200 OK (idempotent success).

### Pagination
- Standard `limit`/`offset` query parameters.
- Response wrapper: `{ "data": [...], "total": <count>, "limit": <N>, "offset": <N> }`.
- `total` reflects the count of items matching the filter.

### Configuration
- **12-Factor App**: All config via Environment Variables.
