import time
import uuid
from collections import defaultdict, deque
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

app = FastAPI()

EMAIL = "24f1002692@ds.study.iitm.ac.in"
ASSIGNED_ORIGIN = "https://app-lothjb.example.com"

# Add the exam page's own origin here once you find it (see instructions below)
EXTRA_ALLOWED_ORIGINS = {
    "https://exam.sanand.workers.dev",  # placeholder - replace after checking real exam origin
}

ALLOWED_ORIGINS = {ASSIGNED_ORIGIN} | EXTRA_ALLOWED_ORIGINS

RATE_LIMIT = 14
WINDOW_SECONDS = 10

rate_buckets = defaultdict(deque)


def is_rate_limited(client_id: str) -> bool:
    now = time.time()
    bucket = rate_buckets[client_id]
    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT:
        return True
    bucket.append(now)
    return False


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class CORSAndRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")

        # Handle preflight directly
        if request.method == "OPTIONS":
            resp = JSONResponse(content={})
            if origin in ALLOWED_ORIGINS:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                resp.headers["Access-Control-Allow-Headers"] = "*"
                resp.headers["Vary"] = "Origin"
            return resp

        client_id = request.headers.get("X-Client-Id", "anonymous")
        if is_rate_limited(client_id):
            resp = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            if origin in ALLOWED_ORIGINS:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Vary"] = "Origin"
            return resp

        response = await call_next(request)
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response


app.add_middleware(CORSAndRateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)


@app.get("/ping")
async def ping(request: Request):
    return {"email": EMAIL, "request_id": request.state.request_id}