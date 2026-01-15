import hmac
import hashlib
import time
import timeit
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends, Header, Response, status, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.models import WebhookPayload, MessageResponse
from app import storage
from app.logging_utils import logger
from app import metrics

app = FastAPI(title="Webhook API")

@app.on_event("startup")
def startup_event():
    try:
        if not settings.WEBHOOK_SECRET:
            logger.error("WEBHOOK_SECRET is not set.")
        storage.init_db()
        logger.info({"event": "startup", "status": "success"})
    except Exception as e:
        logger.error({"event": "startup", "status": "failed", "error": str(e)})

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(time.time()))
    start_time = timeit.default_timer()
    
    response = await call_next(request)
    
    latency_ms = (timeit.default_timer() - start_time) * 1000
    
    metrics.HTTP_REQUESTS_TOTAL.labels(
        path=request.url.path, 
        status=response.status_code
    ).inc()
    metrics.REQUEST_LATENCY_MS.observe(latency_ms)

    log_data = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "latency_ms": round(latency_ms, 2)
    }
    logger.info(log_data, extra=log_data)
    
    return response

async def verify_signature(request: Request, x_signature: str = Header(None)):
    if not settings.WEBHOOK_SECRET:
        metrics.WEBHOOK_REQUESTS_TOTAL.labels(result="invalid_signature").inc()
        raise HTTPException(status_code=503, detail="Server misconfiguration")

    if not x_signature:
        logger.warning({"event": "auth_failure", "reason": "missing_signature"})
        metrics.WEBHOOK_REQUESTS_TOTAL.labels(result="invalid_signature").inc()
        raise HTTPException(status_code=401, detail="invalid signature")

    body_bytes = await request.body()
    
    computed_sig = hmac.new(
        key=settings.WEBHOOK_SECRET.encode(),
        msg=body_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_sig, x_signature):
        logger.warning({"event": "auth_failure", "reason": "signature_mismatch"})
        metrics.WEBHOOK_REQUESTS_TOTAL.labels(result="invalid_signature").inc()
        raise HTTPException(status_code=401, detail="invalid signature")

    return True

@app.post("/webhook", status_code=200)
async def webhook_endpoint(
    payload: WebhookPayload, 
    request: Request,
    verified: bool = Depends(verify_signature)
):
    inserted, error_msg = storage.store_message(payload)
    
    request_id = request.headers.get("X-Request-ID", "unknown")
    extra_log = {
        "request_id": request_id,
        "message_id": payload.message_id,
        "dup": not inserted,
    }

    if inserted:
        metrics.WEBHOOK_REQUESTS_TOTAL.labels(result="created").inc()
        extra_log["result"] = "created"
        logger.info("Webhook processed", extra=extra_log)
    else:
        if error_msg:
             metrics.WEBHOOK_REQUESTS_TOTAL.labels(result="error").inc()
             logger.error(f"Storage error: {error_msg}", extra=extra_log)
        else:
             metrics.WEBHOOK_REQUESTS_TOTAL.labels(result="duplicate").inc()
             extra_log["result"] = "duplicate"
             logger.info("Webhook duplicate", extra=extra_log)
    
    return {"status": "ok"}

@app.get("/messages")
def list_messages(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_msisdn: Optional[str] = Query(None, alias="from"), 
    since: Optional[str] = None,
    q: Optional[str] = None
):
    """
    List messages with pagination and filtering.
    """
    raw_data, total = storage.get_messages(limit, offset, from_msisdn, since, q)
    
    data = [
        MessageResponse.model_validate(dict(row)).model_dump(by_alias=True) 
        for row in raw_data
    ]

    return {
        "data": data,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.get("/stats")
def get_stats():
    return storage.get_stats()

@app.get("/health/live")
def health_live():
    return {"status": "ok"}

@app.get("/health/ready")
def health_ready(response: Response):
    db_ready = storage.check_db_ready()
    secret_ready = bool(settings.WEBHOOK_SECRET)
    
    if db_ready and secret_ready:
        return {"status": "ready"}
    
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not_ready", "db": db_ready, "secret": secret_ready}

@app.get("/metrics")
def metrics_endpoint():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    metrics.WEBHOOK_REQUESTS_TOTAL.labels(result="validation_error").inc()
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": str(exc)},
    )
