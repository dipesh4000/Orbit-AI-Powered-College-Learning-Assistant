import secrets
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from . import conversations, sessions, telemetry
from . import database as db
from .config import ROOT, settings
from .embeddings import EmbeddingUnavailable
from .llm import Model, ModelUnavailable
from .orchestrator import chat
from .practice import PracticeInput, generate
from .rag import Retriever, index_ready
from .services import Services
from .tools import ToolRegistry

app = FastAPI(title="Orbit", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
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


@app.middleware("http")
async def observe_request(request, call_next):
    token = telemetry.request_id.set(secrets.token_hex(12))
    started, status = perf_counter(), 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = telemetry.request_id.get()
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        telemetry.record(
            "http",
            route,
            (perf_counter() - started) * 1000,
            error=status >= 400,
            status=status,
            method=request.method,
        )
        telemetry.request_id.reset(token)


@app.exception_handler(ModelUnavailable)
@app.exception_handler(EmbeddingUnavailable)
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


def session_engine(request: Request):
    # No database is needed to reject a missing cookie or log out anonymously.
    return db.get_engine() if request.cookies.get("orbit_session") else None


def current_session(request: Request, engine=Depends(session_engine)):
    return sessions.load(engine, request.cookies.get("orbit_session"))


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
        "model_configured": bool(
            (settings.llm_api_key and settings.llm_model)
            or (settings.nvidia_api_key and settings.nvidia_model)
        ),
        "embedding_configured": bool(settings.hf_token),
        "index_ready": index_ready(),
        "demo": True,
    }


@app.get("/api/students")
def list_students(service=Depends(services)):
    with service.engine.connect() as conn:
        return [dict(r) for r in conn.execute(select(db.students)).mappings()]


@app.post("/api/login")
@app.post("/api/session", include_in_schema=False)
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
    token = sessions.create(
        service.engine, student, request.cookies.get("orbit_session")
    )
    response.set_cookie(
        "orbit_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=sessions.MAX_AGE,
    )
    return dict(student)


@app.get("/api/session")
def session_info(session=Depends(current_session)):
    return {
        **{k: session[k] for k in ["user_id", "label", "rationale"]},
        "history": session.get("transcript", session["history"]),
        "conversation_id": session.get("conversation_id"),
    }


@app.delete("/api/session")
def logout(request: Request, response: Response, engine=Depends(session_engine)):
    sessions.revoke(engine, request.cookies.get("orbit_session"))
    response.delete_cookie(
        "orbit_session",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    return {"ok": True}


@app.delete("/api/conversation")
async def new_conversation(session=Depends(current_session)):
    async with session["lock"]:
        session["history"].clear()
        session.setdefault("transcript", []).clear()
        session.pop("conversation_id", None)
    return {"ok": True}


@app.get("/api/conversations")
def conversation_list(session=Depends(current_session), service=Depends(services)):
    return conversations.listing(service.engine, session["user_id"])


@app.post("/api/conversations/{conversation_id}/open")
async def open_conversation(
    conversation_id: str, session=Depends(current_session), service=Depends(services)
):
    if session["lock"].locked():
        raise HTTPException(429, "Wait for your current request to finish.")
    async with session["lock"]:
        saved = await run_in_threadpool(
            conversations.load, service.engine, session["user_id"], conversation_id
        )
        if not saved:
            raise HTTPException(404, "Conversation not found.")
        session["conversation_id"] = saved["id"]
        session["transcript"] = saved["messages"]
        session["history"] = [
            {"role": m["role"], "content": m["content"]}
            for m in saved["messages"][-20:]
        ]
        return {"conversation_id": saved["id"], "history": saved["messages"]}


@app.get("/api/metrics")
def metrics(session=Depends(current_session)):
    return telemetry.snapshot()


@app.get("/api/dashboard")
def dashboard(session=Depends(current_session), service=Depends(services)):
    return service.dashboard(session["user_id"])


@app.get("/api/courses")
def courses(session=Depends(current_session), service=Depends(services)):
    enrolled = service.list_courses(session["user_id"])
    for course in enrolled:
        try:
            course["practice_topics"] = retriever.topics(course["course_id"])
        except FileNotFoundError:
            course["practice_topics"] = []
    return enrolled


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
        result = await chat(
            body.message.strip(),
            session,
            ToolRegistry(service, retriever, model),
            model,
        )
        result["conversation_id"] = await run_in_threadpool(
            conversations.save, service.engine, session
        )
        return result


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
    @app.get("/login", include_in_schema=False)
    @app.get("/chat", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    @app.get("/practice", include_in_schema=False)
    def frontend():
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
