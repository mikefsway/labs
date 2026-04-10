import base64
import secrets
import time
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
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
    # Allow health check and agent discovery files without auth — these are
    # intentionally public so AI agents can fetch them to learn what this
    # site is and how to use its MCP server.
    if request.url.path in (
        "/health",
        "/llms.txt",
        "/skill.md",
        "/robots.txt",
        "/sitemap.xml",
        "/.well-known/mcp.json",
    ):
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


@app.get("/llms.txt", include_in_schema=False)
async def llms_txt(request: Request):
    content = templates.get_template("llms.txt").render(request=request)
    return PlainTextResponse(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/skill.md", include_in_schema=False)
async def skill_md(request: Request):
    content = templates.get_template("skill.md").render(request=request)
    return PlainTextResponse(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /llms.txt\n"
        "Allow: /skill.md\n"
        "Allow: /robots.txt\n"
        "Allow: /sitemap.xml\n"
        "Allow: /.well-known/mcp.json\n"
        "Disallow: /\n"
        "\n"
        "# Site is currently Basic Auth protected during testing phase.\n"
        "# Agent discovery files above are intentionally exempt from auth.\n"
        "\n"
        "User-agent: GPTBot\nAllow: /llms.txt\nAllow: /skill.md\nDisallow: /\n\n"
        "User-agent: ClaudeBot\nAllow: /llms.txt\nAllow: /skill.md\nDisallow: /\n\n"
        "User-agent: PerplexityBot\nAllow: /llms.txt\nAllow: /skill.md\nDisallow: /\n\n"
        "User-agent: CCBot\nAllow: /llms.txt\nAllow: /skill.md\nDisallow: /\n\n"
        "User-agent: Google-Extended\nAllow: /llms.txt\nAllow: /skill.md\nDisallow: /\n\n"
        "Sitemap: https://labcurate.com/sitemap.xml\n"
    )
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    body = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://labcurate.com/llms.txt</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>https://labcurate.com/skill.md</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>https://labcurate.com/.well-known/mcp.json</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>
</urlset>
"""
    return Response(body, media_type="application/xml; charset=utf-8")


@app.get("/.well-known/mcp.json", include_in_schema=False)
async def well_known_mcp():
    return JSONResponse({
        "mcp_url": "https://labcurate.com/mcp/",
        "transport": "streamable-http",
        "auth": {
            "type": "bearer",
            "token_source": "contact site operator",
            "scope": "shared",
        },
        "skill_url": "https://labcurate.com/skill.md",
        "llms_txt_url": "https://labcurate.com/llms.txt",
        "tools_count": 4,
        "ecosystem": {
            "spec": "https://fraglet.org/llms.txt",
            "registry": "https://fraglet.org/services.json",
        },
        "description": "UK testing laboratory capability advisor. 1,524 UKAS-accredited labs, ~14,300 capabilities, ~45,000 ISO/ASTM standards. Single-test search, multi-test project matching, and standards cross-referencing.",
        "status": "testing-phase — web UI is Basic Auth protected; MCP is separately gated by Bearer API key.",
    })
