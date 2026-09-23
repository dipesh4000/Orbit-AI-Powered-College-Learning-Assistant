"""Four-section workspace API. Every lookup binds the authenticated owner."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from . import academics, gemini, personal, projects
from . import database as db
from .auth import current_owner, engine
from .github import RepoInput

router = APIRouter(prefix="/api")


@router.get("/academics")
def academic_packet(owner=Depends(current_owner), database=Depends(engine)):
    return academics.packet(owner["id"], database)


@router.put("/academics/profile")
def profile(
    body: academics.Profile, owner=Depends(current_owner), database=Depends(engine)
):
    return academics.save_profile(owner["id"], database, body)


@router.post("/academics/semesters")
def semester(
    body: academics.Semester, owner=Depends(current_owner), database=Depends(engine)
):
    return academics.save_semester(owner["id"], database, body)


@router.delete("/academics/semesters/{key}")
def delete_semester(key: int, owner=Depends(current_owner), database=Depends(engine)):
    return remove_owned(database, owner["id"], db.semester_results, key)


@router.put("/academics/syllabus/{key}")
def syllabus(
    key: int,
    body: academics.Syllabus,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return academics.save_syllabus(owner["id"], database, key, body)


@router.get("/academics/imports")
def imports(owner=Depends(current_owner), database=Depends(engine)):
    return academics.imports(owner["id"], database)


@router.post("/academics/imports", status_code=202)
async def import_academics(
    tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    owner=Depends(current_owner),
    database=Depends(engine),
):
    data = await file.read(gemini.MAX_BYTES + 1)
    await file.close()
    key, lease = academics.create_import(
        owner["id"], database, file.filename or "document", data
    )
    tasks.add_task(academics.extract, owner["id"], database, key, lease)
    return {"id": key}


@router.post("/academics/imports/{key}/retry", status_code=202)
async def retry_import(
    key: int,
    tasks: BackgroundTasks,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    lease = academics.retry_import(owner["id"], database, key)
    tasks.add_task(academics.extract, owner["id"], database, key, lease)
    return {"ok": True}


@router.put("/academics/imports/{key}/confirm")
def confirm_import(
    key: int,
    body: academics.Draft,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return academics.confirm(owner["id"], database, key, body)


@router.delete("/academics/imports/{key}")
def delete_import(key: int, owner=Depends(current_owner), database=Depends(engine)):
    return remove_owned(database, owner["id"], db.academic_imports, key)


@router.get("/projects")
def list_projects(owner=Depends(current_owner), database=Depends(engine)):
    return projects.listing(owner["id"], database)


@router.post("/projects", status_code=201)
def add_project(
    body: projects.ProjectInput, owner=Depends(current_owner), database=Depends(engine)
):
    return projects.save(owner["id"], database, body)


@router.get("/projects/{key}")
def get_project(key: int, owner=Depends(current_owner), database=Depends(engine)):
    return projects.detail(owner["id"], database, key)


@router.put("/projects/{key}")
def edit_project(
    key: int,
    body: projects.ProjectInput,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    return projects.save(owner["id"], database, body, key)


@router.delete("/projects/{key}")
def delete_project(key: int, owner=Depends(current_owner), database=Depends(engine)):
    with database.begin() as conn:
        personal._owned(owner["id"], conn, db.learning_projects, key, lock=True)
        conn.execute(
            db.project_materials.delete().where(
                db.project_materials.c.owner_id == owner["id"],
                db.project_materials.c.project_id == key,
            )
        )
        conn.execute(
            db.learning_projects.delete().where(
                db.learning_projects.c.owner_id == owner["id"],
                db.learning_projects.c.id == key,
            )
        )
    return {"ok": True}


@router.post("/projects/{key}/documents", status_code=201)
async def add_document(
    key: int,
    file: Annotated[UploadFile, File()],
    owner=Depends(current_owner),
    database=Depends(engine),
):
    data = await file.read(gemini.MAX_BYTES + 1)
    await file.close()
    return await projects.upload(
        owner["id"], database, key, file.filename or "document", data
    )


@router.post("/projects/{key}/repository", status_code=201)
async def add_repository(
    key: int, body: RepoInput, owner=Depends(current_owner), database=Depends(engine)
):
    try:
        return await asyncio.wait_for(
            projects.import_repo(owner["id"], database, key, body.url), timeout=75
        )
    except TimeoutError as exc:
        raise HTTPException(
            503, "Repository import timed out. Try a smaller public repository."
        ) from exc


@router.put("/project-materials/{key}")
def edit_material(
    key: int,
    body: projects.MaterialInput,
    owner=Depends(current_owner),
    database=Depends(engine),
):
    with database.begin() as conn:
        personal._owned(owner["id"], conn, db.project_materials, key)
        conn.execute(
            db.project_materials.update()
            .where(
                db.project_materials.c.owner_id == owner["id"],
                db.project_materials.c.id == key,
            )
            .values(content=body.content)
        )
    return {"ok": True}


@router.delete("/project-materials/{key}")
def delete_material(key: int, owner=Depends(current_owner), database=Depends(engine)):
    return remove_owned(database, owner["id"], db.project_materials, key)


@router.get("/github/profile")
def github_profile(owner=Depends(current_owner), database=Depends(engine)):
    return {"profile": projects.github_profile(owner["id"], database)}


@router.post("/github/profile")
async def connect_github(
    body: projects.Handle, owner=Depends(current_owner), database=Depends(engine)
):
    return {
        "profile": await projects.connect_github(owner["id"], database, body.handle)
    }


@router.delete("/github/profile")
def disconnect_github(owner=Depends(current_owner), database=Depends(engine)):
    with database.begin() as conn:
        conn.execute(
            db.github_profiles.delete().where(
                db.github_profiles.c.owner_id == owner["id"]
            )
        )
    return {"ok": True}


def remove_owned(database, owner_id, table, key):
    with database.begin() as conn:
        personal._owned(owner_id, conn, table, key)
        conn.execute(
            table.delete().where(table.c.owner_id == owner_id, table.c.id == key)
        )
    return {"ok": True}
