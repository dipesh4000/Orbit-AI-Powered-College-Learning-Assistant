"""Personal authentication routes, separate from demo-only services."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from . import accounts, personal, sessions
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
    return {**state, "name": owner["name"], "email": owner["email"]}


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
        return await chat(
            body.message, state, PersonalRegistry(database), personal_model
        )
