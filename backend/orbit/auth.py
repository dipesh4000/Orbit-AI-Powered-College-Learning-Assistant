"""Personal authentication routes, separate from demo-only services."""

from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from . import accounts, coding, insights, papers, personal, sessions
from . import database as db
from .config import settings
from .github import RepoInput, preview_repo
from .llm import Model

personal_model = Model()

router = APIRouter(prefix="/api")


def engine():
    return db.get_engine()


def current_owner(request: Request, database=Depends(engine)):
    state = sessions.load(database, request.cookies.get("orbit_session"))
    if state.get("kind") != "personal" or not isinstance(state.get("owner_id"), int):
        raise HTTPException(403, "Sign in to a personal account.")
    with database.connect() as conn:
        owner = (
            conn.execute(
                select(db.owners.c.id, db.owners.c.email, db.owners.c.name).where(
                    db.owners.c.id == state["owner_id"]
                )
            )
            .mappings()
            .one_or_none()
        )
    if owner is None:
        raise HTTPException(401, "Sign in to continue.")
    return dict(owner)


@router.get("/papers")
def list_papers(owner=Depends(current_owner), database=Depends(engine)):
    return papers.listing(owner["id"], database)


@router.get("/personal/suggestions")
def list_suggestions(owner=Depends(current_owner), database=Depends(engine)):
    return insights.listing(owner["id"], database)


@router.post("/personal/suggestions/refresh")
def refresh_suggestions(owner=Depends(current_owner), database=Depends(engine)):
    return insights.refresh(owner["id"], database)


@router.put("/personal/suggestions/{key}")
def decide_suggestion(
    key: int,
    body: insights.Decision,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return insights.decide(owner["id"], database, key, body.state)


@router.get("/personal/evidence/{kind}/{key}")
def evidence_detail(
    kind: str, key: int, owner=Depends(current_owner), database=Depends(engine)
):
    return insights.evidence(owner["id"], database, kind, key)


@router.post("/papers", status_code=202)
async def upload_paper(
    tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    subject_id: int = Form(...),
    year: int = Form(...),
    topics: str = Form("", max_length=5000),
    owner=Depends(current_owner),
    database=Depends(engine),
):
    source = await file.read(papers.MAX_BYTES + 1)
    await file.close()
    key, lease = papers.create(
        owner["id"],
        database,
        file.filename or "paper",
        source,
        subject_id,
        year,
        topics,
    )
    tasks.add_task(papers.process, owner["id"], database, key, lease)
    return {"id": key}


@router.post("/papers/search")
def search_papers(
    body: papers.Search, owner=Depends(current_owner), database=Depends(engine)
):
    return papers.search(owner["id"], database, body)


@router.get("/papers/{paper_id}")
def paper_detail(paper_id: int, owner=Depends(current_owner), database=Depends(engine)):
    return papers.detail(owner["id"], database, paper_id)


@router.get("/papers/{paper_id}/source")
def paper_source(paper_id: int, owner=Depends(current_owner), database=Depends(engine)):
    with database.connect() as conn:
        row = personal._owned(owner["id"], conn, db.papers, paper_id)
    return Response(
        row["source"],
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(row["filename"], safe="")
        },
    )


@router.post("/papers/{paper_id}/retry", status_code=202)
def retry_paper(
    paper_id: int,
    tasks: BackgroundTasks,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    lease = papers.retry(owner["id"], database, paper_id)
    tasks.add_task(papers.process, owner["id"], database, paper_id, lease)
    return {"ok": True}


@router.post("/papers/{paper_id}/reindex")
def reindex_paper(
    paper_id: int, owner=Depends(current_owner), database=Depends(engine)
):
    return papers.reindex(owner["id"], database, paper_id)


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: int, owner=Depends(current_owner), database=Depends(engine)):
    return papers.remove(owner["id"], database, paper_id)


@router.put("/paper-questions/{question_id}")
def review_question(
    question_id: int,
    body: papers.Review,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return papers.review(owner["id"], database, question_id, body)


@router.post("/papers/{paper_id}/questions", status_code=201)
def add_question(paper_id: int, owner=Depends(current_owner), database=Depends(engine)):
    with database.begin() as conn:
        row = personal._owned(owner["id"], conn, db.papers, paper_id, lock=True)
        if row["status"] in {"processing", "failed"}:
            raise HTTPException(409, "Extract the paper before adding questions.")
        conn.execute(
            db.paper_questions.insert().values(
                owner_id=owner["id"],
                paper_id=paper_id,
                page=1,
                content="Enter the missing question here.",
                topic="Unclassified",
                confirmed=False,
                revision=1,
            )
        )
        papers.update_status(conn, owner["id"], paper_id)
    return {"ok": True}


@router.delete("/paper-questions/{question_id}")
def delete_question(
    question_id: int, owner=Depends(current_owner), database=Depends(engine)
):
    with database.begin() as conn:
        row = personal._owned(owner["id"], conn, db.paper_questions, question_id)
        personal._owned(owner["id"], conn, db.papers, row["paper_id"], lock=True)
        personal._owned(owner["id"], conn, db.paper_questions, question_id, lock=True)
        conn.execute(
            db.paper_questions.delete().where(
                db.paper_questions.c.id == question_id,
                db.paper_questions.c.owner_id == owner["id"],
            )
        )
        papers.update_status(conn, owner["id"], row["paper_id"])
    return {"ok": True}


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024, repr=False)


def signed_in(database, owner, request, response):
    state = {"kind": "personal", "owner_id": owner["id"]}
    token = sessions.create(database, state, request.cookies.get("orbit_session"))
    response.set_cookie(
        "orbit_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=sessions.MAX_AGE,
        path="/",
    )
    return {**state, "name": owner["name"], "email": owner["email"], "demo_account": getattr(request.app.state, "demo_owner_id", None) == owner["id"]}


@router.post("/auth/demo")
def enter_demo(request: Request, response: Response, database=Depends(engine)):
    key = getattr(request.app.state, "demo_owner_id", None)
    if key is None or database.dialect.name != "sqlite":
        raise HTTPException(404, "Run start.bat --demo to open the local demo.")
    with database.connect() as conn:
        owner = (
            conn.execute(
                select(db.owners.c.id, db.owners.c.name, db.owners.c.email).where(
                    db.owners.c.id == key
                )
            )
            .mappings()
            .one()
        )
    return signed_in(database, owner, request, response)


@router.post("/auth/register", status_code=201)
def register(
    body: accounts.Registration,
    request: Request,
    response: Response,
    database=Depends(engine),
):
    try:
        owner = accounts.register(database, body)
    except accounts.AccountExists as exc:
        raise HTTPException(409, str(exc)) from exc
    return signed_in(database, owner, request, response)


@router.post("/auth/login")
def login(
    body: Credentials, request: Request, response: Response, database=Depends(engine)
):
    owner = accounts.authenticate(database, body.email, body.password)
    if owner is None:
        raise HTTPException(401, "Email or password is incorrect.")
    return signed_in(database, owner, request, response)


@router.get("/subjects")
def subjects(owner=Depends(current_owner), database=Depends(engine)):
    return personal.list_subjects(owner["id"], database)


@router.post("/subjects", status_code=201)
def add_subject(
    body: personal.SubjectInput, owner=Depends(current_owner), database=Depends(engine)
):
    return personal.create_subject(owner["id"], database, body)


@router.get("/subjects/{subject_id}")
def subject(subject_id: int, owner=Depends(current_owner), database=Depends(engine)):
    return personal.get_subject(owner["id"], database, subject_id)


@router.put("/subjects/{subject_id}")
def edit_subject(
    subject_id: int,
    body: personal.SubjectInput,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return personal.update_subject(owner["id"], database, subject_id, body)


@router.delete("/subjects/{subject_id}")
def remove_subject(
    subject_id: int, owner=Depends(current_owner), database=Depends(engine)
):
    return personal.delete_subject(owner["id"], database, subject_id)


@router.get("/personal/workspace")
def workspace(owner=Depends(current_owner), database=Depends(engine)):
    return personal.workspace(owner["id"], database)


@router.post("/assessments/import")
def import_marks(
    body: personal.CsvInput, owner=Depends(current_owner), database=Depends(engine)
):
    return personal.import_marks(owner["id"], database, body.content)


@router.get("/assessments")
def list_assessments(
    subject_id: int | None = None,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return personal.list_records(owner["id"], database, "assessments", subject_id)


@router.post("/assessments", status_code=201)
def add_assessments(
    body: personal.AssessmentInput,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return personal.save_record(owner["id"], database, "assessments", body)


@router.get("/assessments/{key}")
def get_assessments(key: int, owner=Depends(current_owner), database=Depends(engine)):
    return personal.get_record(owner["id"], database, "assessments", key)


@router.put("/assessments/{key}")
def edit_assessments(
    key: int,
    body: personal.AssessmentInput,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return personal.save_record(owner["id"], database, "assessments", body, key)


@router.delete("/assessments/{key}")
def remove_assessments(
    key: int, owner=Depends(current_owner), database=Depends(engine)
):
    return personal.delete_record(owner["id"], database, "assessments", key)


@router.get("/hackathons")
def list_hackathons(
    subject_id: int | None = None,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return personal.list_records(owner["id"], database, "hackathons", subject_id)


@router.post("/hackathons", status_code=201)
def add_hackathons(
    body: personal.HackathonInput,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return personal.save_record(owner["id"], database, "hackathons", body)


@router.get("/hackathons/{key}")
def get_hackathons(key: int, owner=Depends(current_owner), database=Depends(engine)):
    return personal.get_record(owner["id"], database, "hackathons", key)


@router.put("/hackathons/{key}")
def edit_hackathons(
    key: int,
    body: personal.HackathonInput,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return personal.save_record(owner["id"], database, "hackathons", body, key)


@router.delete("/hackathons/{key}")
def remove_hackathons(key: int, owner=Depends(current_owner), database=Depends(engine)):
    return personal.delete_record(owner["id"], database, "hackathons", key)


@router.post("/personal/github-preview")
async def github_preview(body: RepoInput, owner=Depends(current_owner)):
    return await preview_repo(body.url)


class PersonalMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000)


@router.get("/personal/chat")
def personal_history(
    request: Request, owner=Depends(current_owner), database=Depends(engine)
):
    state = sessions.load(database, request.cookies.get("orbit_session"))
    return {"history": state.get("transcript", [])}


@router.post("/personal/chat")
async def personal_chat(
    body: PersonalMessage,
    request: Request,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    from starlette.concurrency import run_in_threadpool

    from .orchestrator import chat
    from .personal_tools import PersonalRegistry

    state = await run_in_threadpool(
        sessions.load, database, request.cookies.get("orbit_session")
    )
    async with state["lock"]:
        if (
            getattr(request.app.state, "demo_owner_id", None) == owner["id"]
            and database.dialect.name == "sqlite"
        ):
            from .demo import reply

            result = await reply(body.message, owner["id"], database)
            state.setdefault("transcript", []).extend(
                [
                    {"role": "user", "content": body.message},
                    {
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result["sources"],
                        "demo": True,
                    },
                ]
            )
            del state["transcript"][:-200]
            return result
        return await chat(
            body.message, state, PersonalRegistry(database), personal_model
        )


@router.get("/coding")
def coding_snapshot(owner=Depends(current_owner), database=Depends(engine)):
    return coding.packet(owner["id"], database)


@router.post("/coding/connection", status_code=201)
def connect_coding(
    body: coding.ConnectionInput, owner=Depends(current_owner), database=Depends(engine)
):
    return coding.connect(owner["id"], database, body)


@router.post("/coding/refresh", status_code=202)
async def refresh_coding(
    background: BackgroundTasks, owner=Depends(current_owner), database=Depends(engine)
):
    from starlette.concurrency import run_in_threadpool

    ticket = await run_in_threadpool(coding.claim, owner["id"], database)
    background.add_task(coding.refresh, owner["id"], database, ticket)
    return await run_in_threadpool(coding.packet, owner["id"], database)


@router.delete("/coding/connection")
def disconnect_coding(owner=Depends(current_owner), database=Depends(engine)):
    return coding.remove(owner["id"], database, "codolio")


@router.post("/coding/manual", status_code=201)
def manual_coding(
    body: coding.ManualInput, owner=Depends(current_owner), database=Depends(engine)
):
    return coding.save_manual(owner["id"], database, body)


@router.delete("/coding/manual")
def remove_manual_coding(owner=Depends(current_owner), database=Depends(engine)):
    return coding.remove(owner["id"], database, "manual")
