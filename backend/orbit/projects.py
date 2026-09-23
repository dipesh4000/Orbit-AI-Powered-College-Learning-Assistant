"""Owned learning projects and bounded public GitHub context."""

import base64
import re
import time
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from . import database as db
from . import gemini, personal


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=4000)
    subject_ids: list[int] = Field(default_factory=list, max_length=50)


class MaterialInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=150000)


class Handle(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    handle: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,38}$")


def listing(owner_id, engine):
    with engine.connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                select(db.learning_projects)
                .where(db.learning_projects.c.owner_id == owner_id)
                .order_by(db.learning_projects.c.id.desc())
            ).mappings()
        ]


def detail(owner_id, engine, key):
    with engine.connect() as conn:
        row = personal._owned(owner_id, conn, db.learning_projects, key)
        row["materials"] = [
            dict(r)
            for r in conn.execute(
                select(db.project_materials)
                .where(
                    db.project_materials.c.owner_id == owner_id,
                    db.project_materials.c.project_id == key,
                )
                .order_by(db.project_materials.c.id)
            ).mappings()
        ]
        row["subjects"] = [
            dict(r)
            for r in conn.execute(
                select(db.subjects).where(
                    db.subjects.c.owner_id == owner_id,
                    db.subjects.c.id.in_(row["subject_ids"]),
                )
            ).mappings()
        ]
        row["syllabi"] = [
            dict(r)
            for r in conn.execute(
                select(db.subject_syllabi).where(
                    db.subject_syllabi.c.owner_id == owner_id,
                    db.subject_syllabi.c.subject_id.in_(row["subject_ids"]),
                )
            ).mappings()
        ]
        return row


def save(owner_id, engine, body, key=None):
    with engine.begin() as conn:
        for sid in body.subject_ids:
            personal._owned(owner_id, conn, db.subjects, sid)
        if key:
            personal._owned(owner_id, conn, db.learning_projects, key)
            conn.execute(
                db.learning_projects.update()
                .where(
                    db.learning_projects.c.owner_id == owner_id,
                    db.learning_projects.c.id == key,
                )
                .values(**body.model_dump())
            )
        else:
            key = conn.execute(
                db.learning_projects.insert().values(
                    owner_id=owner_id, created_at=time.time(), **body.model_dump()
                )
            ).inserted_primary_key[0]
    return detail(owner_id, engine, key)


def add_material(owner_id, engine, key, name, kind, content, url=None):
    if not content.strip() or len(content) > 150000:
        raise HTTPException(422, "Use material containing 1–150,000 characters.")
    with engine.begin() as conn:
        personal._owned(owner_id, conn, db.learning_projects, key, lock=True)
        existing = list(
            conn.execute(
                select(db.project_materials.c.id).where(
                    db.project_materials.c.owner_id == owner_id,
                    db.project_materials.c.project_id == key,
                )
            )
        )
        if len(existing) >= 30:
            raise HTTPException(422, "Use at most 30 materials in one project.")
        conn.execute(
            db.project_materials.insert().values(
                owner_id=owner_id,
                project_id=key,
                name=name[:200],
                kind=kind,
                content=content,
                source_url=url,
                created_at=time.time(),
            )
        )
    return detail(owner_id, engine, key)


async def upload(owner_id, engine, key, filename, data):
    with engine.connect() as conn:
        personal._owned(owner_id, conn, db.learning_projects, key)
    mime = gemini.media(filename, data)
    content = await gemini.document_text(data, mime)
    return add_material(
        owner_id,
        engine,
        key,
        filename.replace("\\", "/").split("/")[-1],
        "document",
        content,
    )


async def github_json(client, path, params=None):
    # All callers construct paths from validated handles or GitHub's hexadecimal SHAs.
    async with client.stream(
        "GET", "https://api.github.com" + path, params=params
    ) as response:
        response.raise_for_status()
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > 2_000_000:
                raise ValueError("GitHub response too large")
    import json

    return json.loads(data)


async def connect_github(owner_id, engine, handle):
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            row = await github_json(client, f"/users/{handle}")
        snapshot = {
            k: row.get(k)
            for k in ("login", "name", "bio", "public_repos", "followers", "following")
        }
        if not isinstance(snapshot["login"], str):
            raise TypeError("Missing profile")
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            503,
            "Could not fetch that public GitHub profile. Your saved connection is unchanged.",
        ) from exc
    from .academics import upsert

    with engine.begin() as conn:
        upsert(
            conn,
            db.github_profiles,
            {"owner_id": owner_id},
            {"handle": handle, "snapshot": snapshot, "fetched_at": time.time()},
        )
    return github_profile(owner_id, engine)


def github_profile(owner_id, engine):
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(db.github_profiles).where(
                    db.github_profiles.c.owner_id == owner_id
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None


async def import_repo(owner_id, engine, key, url):
    with engine.connect() as conn:
        personal._owned(owner_id, conn, db.learning_projects, key)
    parsed = urlsplit(url)
    match = re.fullmatch(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?", parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or not match
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(
            422, "Use a public repository URL: https://github.com/owner/repository"
        )
    owner, repo = match.groups()
    repo = repo.removesuffix(".git")
    if owner in {".", ".."} or repo in {"", ".", ".."}:
        raise HTTPException(422, "Invalid repository URL.")
    base = f"/repos/{owner}/{repo}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            metadata = await github_json(client, base)
            branch = metadata.get("default_branch")
            if not isinstance(branch, str):
                raise TypeError("Missing branch")
            commits = await github_json(
                client, base + "/commits", {"sha": branch, "per_page": 1}
            )
            commit = commits[0]["sha"]
            tree_sha = commits[0]["commit"]["tree"]["sha"]
            if not all(re.fullmatch(r"[a-f0-9]{40,64}", v) for v in (commit, tree_sha)):
                raise ValueError("Invalid revision")
            tree = await github_json(
                client, base + f"/git/trees/{tree_sha}", {"recursive": "1"}
            )
            files = []
            for r in tree.get("tree", []):
                path = r.get("path", "")
                if (
                    r.get("type") != "blob"
                    or r.get("mode") == "120000"
                    or not isinstance(path, str)
                ):
                    continue
                if any(
                    part.startswith(".")
                    or part in {"node_modules", "vendor", "dist", "build"}
                    for part in path.split("/")
                ):
                    continue
                if (
                    path.endswith(
                        (
                            ".md",
                            ".py",
                            ".js",
                            ".jsx",
                            ".ts",
                            ".tsx",
                            ".java",
                            ".c",
                            ".cpp",
                            ".go",
                            ".rs",
                            ".html",
                            ".css",
                        )
                    )
                    and isinstance(r.get("size"), int)
                    and r["size"] <= 30000
                ):
                    files.append(r)
            files.sort(
                key=lambda r: (
                    not r["path"].lower().startswith("readme"),
                    len(r["path"].split("/")),
                    r["path"],
                )
            )
            chunks = [
                f"Repository: {owner}/{repo}\nCommit: {commit}\nDescription: {metadata.get('description') or ''}\n"
            ]
            for file in files[:12]:
                sha = file.get("sha", "")
                if not re.fullmatch(r"[a-f0-9]{40,64}", sha):
                    continue
                blob = await github_json(client, base + f"/git/blobs/{sha}")
                content = base64.b64decode(blob["content"]).decode("utf-8")
                chunk = f"\n--- {file['path']} ---\n{content}"
                if sum(map(len, chunks)) + len(chunk) > 145000:
                    break
                chunks.append(chunk)
            if len(chunks) == 1:
                raise ValueError("No readable source files")
            chunks.append(
                f"\nImported {len(chunks) - 1} selected files; this is a bounded repository snapshot, not the entire repository."
            )
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        AttributeError,
    ) as exc:
        raise HTTPException(
            503,
            "Could not import repository source. Check that it is public and has readable code or Markdown, then retry.",
        ) from exc
    return add_material(
        owner_id,
        engine,
        key,
        f"{owner}/{repo} @ {commit[:8]}",
        "repository",
        "\n".join(chunks),
        f"https://github.com/{owner}/{repo}",
    )


def context(owner_id, engine, key, query=""):
    project = detail(owner_id, engine, key)
    terms = re.findall(r"\w+", query.lower())
    passages = []
    for item in project["materials"]:
        text = item["content"]
        chunks = [text[i : i + 2000] for i in range(0, len(text), 1800)]
        ranked = sorted(
            enumerate(chunks), key=lambda p: -sum(p[1].lower().count(t) for t in terms)
        )[:3]
        passages.append(
            {
                "evidence_id": f"material-{item['id']}",
                "name": item["name"],
                "kind": item["kind"],
                "excerpts": [{"offset": i * 1800, "text": t} for i, t in ranked],
            }
        )
    project["available_materials"] = [
        {"id": r["id"], "name": r["name"], "kind": r["kind"]}
        for r in project["materials"]
    ]
    passages.sort(
        key=lambda r: (
            -sum(e["text"].lower().count(t) for e in r["excerpts"] for t in terms)
        )
    )
    project["materials"] = passages[:10]
    project["retrieval_note"] = (
        "Up to 10 materials, 3 excerpts per material and 10 syllabi are included. Excerpts may omit relevant content; never claim the entire project was inspected."
    )
    project["syllabi"] = [
        {**r, "content": r["content"][:12000]} for r in project["syllabi"][:10]
    ]
    return project
