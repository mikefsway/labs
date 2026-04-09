import base64
import secrets
import time
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.ratelimit import limiter
from app.routers import auth, labs, search

app = FastAPI(title="LabCurate", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Brute-force protection ---
_auth_failures: dict[str, list[float]] = defaultdict(list)
_AUTH_MAX_FAILURES = 10
_AUTH_WINDOW_SECONDS = 300


def _is_ip_blocked(ip: str) -> bool:
    now = time.monotonic()
    attempts = _auth_failures[ip]
    # Prune old entries
    _auth_failures[ip] = [t for t in attempts if now - t < _AUTH_WINDOW_SECONDS]
    return len(_auth_failures[ip]) >= _AUTH_MAX_FAILURES


def _record_failure(ip: str):
    _auth_failures[ip].append(time.monotonic())


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    settings = get_settings()
    if not settings.site_password:
        return await call_next(request)
    # Allow health check without auth
    if request.url.path == "/health":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    if _is_ip_blocked(client_ip):
        return Response(content="Too many failed attempts", status_code=429)

    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            _, password = decoded.split(":", 1)
            if secrets.compare_digest(password, settings.site_password):
                _auth_failures.pop(client_ip, None)
                return await call_next(request)
        except Exception:
            pass
    _record_failure(client_ip)
    return Response(
        content="Authentication required",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="LabCurate"'},
    )


app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(labs.router)

templates = Jinja2Templates(directory="app/templates")


def _supabase_ctx():
    settings = get_settings()
    return {
        "supabase_url": settings.supabase_url,
        "supabase_anon_key": settings.supabase_anon_key,
        "turnstile_site_key": settings.turnstile_site_key,
    }


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", _supabase_ctx())


@app.get("/lab/{lab_id}")
async def lab_detail(request: Request, lab_id: int):
    return templates.TemplateResponse(request, "lab.html", {"lab_id": lab_id, **_supabase_ctx()})


@app.get("/health")
async def health():
    return {"status": "ok"}
