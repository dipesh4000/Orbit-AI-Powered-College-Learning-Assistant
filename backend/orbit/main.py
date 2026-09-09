if __name__ == "__main__":
    import runpy
    from pathlib import Path

    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "run.py"), run_name="__main__"
    )
import asyncio
import secrets
from collections import OrderedDict
from time import monotonic

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from . import database as db
from .config import ROOT, settings
from .llm import Model, ModelUnavailable
from .orchestrator import chat
from .practice import PracticeInput, generate
from .rag import Retriever
from .services import Services
from .tools import ToolRegistry

app = FastAPI(title="Orbit", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
sessions = OrderedDict()
retriever, model = Retriever(), Model()


@app.middleware("http")
async def origin_guard(request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method in ("POST", "DELETE")
        and origin
        and origin not in {*settings.allowed_origins, str(request.base_url).rstrip("/")}
    ):
        return JSONResponse({"detail": "Untrusted request origin."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ModelUnavailable)
async def model_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=503)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(
        {"detail": "Database unavailable. Check DATABASE_URL and run the importer."},
        status_code=503,
    )


@app.exception_handler(RuntimeError)
async def configuration_error(request, exc):
    return JSONResponse(
        {
            "detail": "Service is not configured. Check backend/.env and setup instructions."
        },
        status_code=503,
    )


@app.exception_handler(FileNotFoundError)
async def index_error(request, exc):
    return JSONResponse(
        {"detail": "Course index is missing. Run python -m orbit.rag from backend/."},
        status_code=503,
    )


def services():
    return Services(db.get_engine())


def current_session(request: Request):
    token = request.cookies.get("orbit_session")
    session = sessions.get(token)
    if not session or session["expires"] < monotonic():
        sessions.pop(token, None)
        raise HTTPException(401, "Choose a student to begin.")
    sessions.move_to_end(token)
    return session


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(max_length=100)


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "database_configured": bool(settings.database_url),
        "model_configured": bool(settings.llm_api_key and settings.llm_model),
        "index_ready": (ROOT / "data/rag/index.faiss").exists(),
        "demo": True,
    }


@app.get("/api/students")
def list_students(service=Depends(services)):
    with service.engine.connect() as conn:
        return [dict(r) for r in conn.execute(select(db.students)).mappings()]


@app.post("/api/session")
def login(body: Login, request: Request, response: Response, service=Depends(services)):
    with service.engine.connect() as conn:
        student = (
            conn.execute(
                select(db.students).where(db.students.c.user_id == body.user_id)
            )
            .mappings()
            .first()
        )
    if not student:
        raise HTTPException(400, "Select an available demo student.")
    sessions.pop(request.cookies.get("orbit_session"), None)
    token = secrets.token_urlsafe(32)
    sessions[token] = {
        **dict(student),
        "expires": monotonic() + 8 * 3600,
        "history": [],
        "lock": asyncio.Lock(),
    }
    while len(sessions) > 100:
        sessions.popitem(last=False)
    response.set_cookie(
        "orbit_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=8 * 3600,
    )
    return dict(student)


@app.get("/api/session")
def session_info(session=Depends(current_session)):
    return {
        **{k: session[k] for k in ["user_id", "label", "rationale"]},
        "history": session.get("transcript", session["history"]),
    }


@app.delete("/api/session")
def logout(request: Request, response: Response):
    sessions.pop(request.cookies.get("orbit_session"), None)
    response.delete_cookie("orbit_session")
    return {"ok": True}


@app.delete("/api/conversation")
async def new_conversation(session=Depends(current_session)):
    async with session["lock"]:
        session["history"].clear()
        session.setdefault("transcript", []).clear()
    return {"ok": True}


@app.get("/api/dashboard")
def dashboard(session=Depends(current_session), service=Depends(services)):
    return service.dashboard(session["user_id"])


@app.get("/api/courses")
def courses(session=Depends(current_session), service=Depends(services)):
    return service.list_courses(session["user_id"])


@app.get("/api/topics/{course_id}")
def topics(course_id: str, session=Depends(current_session), service=Depends(services)):
    if course_id not in {
        c["course_id"] for c in service.list_courses(session["user_id"])
    }:
        raise HTTPException(404, "Enrolled course not found.")
    return retriever.topics(course_id)


@app.get("/api/eligibility/{assessment_id}")
def check_eligibility(
    assessment_id: str, session=Depends(current_session), service=Depends(services)
):
    return service.check_assessment_eligibility(session["user_id"], assessment_id)


@app.post("/api/chat")
async def send_message(
    body: Message, session=Depends(current_session), service=Depends(services)
):
    if not body.message.strip():
        raise HTTPException(422, "Enter a question.")
    if session["lock"].locked():
        raise HTTPException(429, "Wait for your current request to finish.")
    async with session["lock"]:
        return await chat(
            body.message.strip(),
            session,
            ToolRegistry(service, retriever, model),
            model,
        )


@app.post("/api/practice")
async def practice(
    body: PracticeInput, session=Depends(current_session), service=Depends(services)
):
    if session["lock"].locked():
        raise HTTPException(429, "Wait for your current request to finish.")
    async with session["lock"]:
        try:
            return await generate(body, session["user_id"], service, retriever, model)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


DIST = ROOT.parent / "frontend/dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def frontend():
        return FileResponse(DIST / "index.html")
