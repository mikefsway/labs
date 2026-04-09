import secrets

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.routers import auth, labs, search

app = FastAPI(title="LabCurate", version="0.1.0")


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    settings = get_settings()
    if not settings.site_password:
        return await call_next(request)
    # Allow health check without auth
    if request.url.path == "/health":
        return await call_next(request)
    auth = request.headers.get("authorization", "")
    if auth.startswith("Basic "):
        import base64
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            _, password = decoded.split(":", 1)
            if secrets.compare_digest(password, settings.site_password):
                return await call_next(request)
        except Exception:
            pass
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
