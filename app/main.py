from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth import ClerkAuthError, verify_clerk_token
from app.config import get_settings
from app.ratelimit import limiter
from app.routers import labs, search

app = FastAPI(title="LabCurate", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Paths that do not require Clerk authentication. Discovery files are
# intentionally public so AI agents can fetch them unauthenticated.
_PUBLIC_PATHS = frozenset({
    "/health",
    "/llms.txt",
    "/skill.md",
    "/robots.txt",
    "/sitemap.xml",
    "/.well-known/mcp.json",
    "/login",
})


@app.middleware("http")
async def clerk_auth_middleware(request: Request, call_next):
    settings = get_settings()
    # If Clerk isn't configured (e.g. local bootstrap), fail closed for
    # protected routes and open for discovery routes.
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith("/static/"):
        return await call_next(request)

    if not settings.clerk_jwt_issuer_url:
        return JSONResponse({"error": "auth not configured"}, status_code=503)

    token = request.cookies.get("__session", "")
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if token:
        try:
            verify_clerk_token(token)
            return await call_next(request)
        except ClerkAuthError:
            pass

    if path.startswith("/api/"):
        return JSONResponse({"error": "authentication required"}, status_code=401)
    return RedirectResponse("/login", status_code=302)


app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(search.router)
app.include_router(labs.router)

templates = Jinja2Templates(directory="app/templates")


def _clerk_ctx():
    settings = get_settings()
    return {
        "clerk_publishable_key": settings.clerk_publishable_key,
        "clerk_frontend_api": settings.clerk_frontend_api,
    }


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", _clerk_ctx())


@app.get("/lab/{lab_id}")
async def lab_detail(request: Request, lab_id: int):
    return templates.TemplateResponse(
        request, "lab.html", {"lab_id": lab_id, **_clerk_ctx()}
    )


@app.get("/login")
async def login(request: Request):
    return templates.TemplateResponse(request, "login.html", _clerk_ctx())


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
        "# Web UI requires sign-in (Clerk) during the testing phase.\n"
        "# Agent discovery files above are intentionally exempt.\n"
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
        "status": "testing-phase — web UI gated by Clerk sign-in; MCP is separately gated by Bearer API key.",
    })
