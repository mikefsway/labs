from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routers import labs, search

app = FastAPI(title="UKAS Lab Search", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(search.router)
app.include_router(labs.router)

templates = Jinja2Templates(directory="app/templates")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/lab/{lab_id}")
async def lab_detail(request: Request, lab_id: int):
    return templates.TemplateResponse(request, "lab.html", {"lab_id": lab_id})


@app.get("/health")
async def health():
    return {"status": "ok"}
