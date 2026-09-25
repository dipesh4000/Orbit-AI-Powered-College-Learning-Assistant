"""Private paper ingestion. Only explicitly confirmed questions are searchable."""

import json
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Literal

import numpy as np
import pymupdf
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from ..ai.embeddings import Embeddings, EmbeddingUnavailable
from ..core import database as db
from ..core.config import settings
from .personal import _owned, get_subject

embedder = Embeddings()
MAX_BYTES = 10 * 1024 * 1024
LEASE_SECONDS = 600


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(min_length=5, max_length=10000)
    topic: str = Field(min_length=1, max_length=100)
    marks: int | None = Field(default=None, ge=0, le=1000)
    page: int = Field(ge=1, le=40)
    confirmed: bool = False
    revision: int = Field(ge=1)


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=500)
    subject_id: int | None = Field(default=None, gt=0)
    mode: Literal["keyword", "semantic"] = "keyword"


def signature():
    return json.dumps(embedder.signature, sort_keys=True)


def encode_questions(rows):
    # Bound provider batch size while retaining the source text for reindexing.
    batches = [
        embedder.encode([r["content"] for r in rows[i : i + 32]])
        for i in range(0, len(rows), 32)
    ]
    vectors = np.concatenate(batches)
    if vectors.shape != (len(rows), 384):
        raise EmbeddingUnavailable(
            "Personal papers require 384-dimensional embeddings."
        )
    return vectors


def listing(owner_id, engine):
    with engine.connect() as conn:
        rows = conn.execute(
            select(db.papers)
            .where(db.papers.c.owner_id == owner_id)
            .order_by(db.papers.c.id.desc())
        ).mappings()
        result = []
        for row in rows:
            item = {k: v for k, v in row.items() if k not in {"source", "lease"}}
            item["retryable"] = item["status"] == "failed" or (
                item["status"] == "processing"
                and time.time() - item["started_at"] > LEASE_SECONDS
            )
            item["total"] = conn.scalar(
                select(func.count())
                .select_from(db.paper_questions)
                .where(
                    db.paper_questions.c.owner_id == owner_id,
                    db.paper_questions.c.paper_id == item["id"],
                )
            )
            item["confirmed_count"] = conn.scalar(
                select(func.count())
                .select_from(db.paper_questions)
                .where(
                    db.paper_questions.c.owner_id == owner_id,
                    db.paper_questions.c.paper_id == item["id"],
                    db.paper_questions.c.confirmed.is_(True),
                )
            )
            result.append(item)
        return result


def detail(owner_id, engine, paper_id):
    with engine.connect() as conn:
        paper = _owned(owner_id, conn, db.papers, paper_id)
        rows = conn.execute(
            select(db.paper_questions)
            .where(
                db.paper_questions.c.owner_id == owner_id,
                db.paper_questions.c.paper_id == paper_id,
            )
            .order_by(db.paper_questions.c.id)
        ).mappings()
        paper["questions"] = [
            {
                **{k: v for k, v in r.items() if k not in {"embedding", "signature"}},
                "indexed": r["embedding"] is not None and r["signature"] == signature(),
            }
            for r in rows
        ]
    return {k: v for k, v in paper.items() if k not in {"source", "lease"}}


def create(owner_id, engine, filename, source, subject_id, year, topics):
    get_subject(owner_id, engine, subject_id)
    filename = filename.replace("\\", "/").split("/")[-1][:200]
    if not filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".txt")):
        raise HTTPException(422, "Choose a PDF, PNG, JPEG, or UTF-8 text paper.")
    if not source or len(source) > MAX_BYTES:
        raise HTTPException(413, "Choose a nonempty paper up to 10 MB.")
    if not 1900 <= year <= datetime.now(UTC).year:
        raise HTTPException(422, "Enter a valid paper year.")
    topics = list(dict.fromkeys(t.strip() for t in topics.split(",") if t.strip()))
    if len(topics) > 40 or any(len(t) > 100 for t in topics):
        raise HTTPException(422, "Use up to 40 topics of at most 100 characters.")
    lease = str(uuid.uuid4())
    with engine.begin() as conn:
        key = conn.execute(
            db.papers.insert().values(
                owner_id=owner_id,
                subject_id=subject_id,
                filename=filename,
                source=source,
                year=year,
                topics=topics,
                status="processing",
                started_at=time.time(),
                lease=lease,
            )
        ).inserted_primary_key[0]
    return key, lease


def extract(source, filename):
    if filename.lower().endswith(".txt"):
        text = source.decode("utf-8-sig")
        if len(text) > 200000:
            raise ValueError("Paper text exceeds 200,000 characters. Split the file.")
        return [(1, text)]
    with pymupdf.open(stream=source) as original:
        if original.needs_pass:
            raise ValueError("This PDF is password protected. Upload an unlocked copy.")
        if original.page_count > 40:
            raise ValueError("Upload at most 40 pages at a time.")
        converted = None
        document = original
        if not original.is_pdf:
            converted = pymupdf.open("pdf", original.convert_to_pdf())
            document = converted
        try:
            pages = []
            for number, page in enumerate(document, 1):
                text = page.get_text(sort=True)
                if sum(c.isalpha() for c in text) < 20:
                    try:
                        text = page.get_text(
                            textpage=page.get_textpage_ocr(dpi=150, full=True)
                        )
                    except Exception as exc:
                        raise ValueError(
                            "This paper needs OCR. Install Tesseract English language data on the server, or upload a text PDF / UTF-8 transcript."
                        ) from exc
                pages.append((number, text))
                if sum(len(t) for _, t in pages) > 200000:
                    raise ValueError(
                        "Paper text exceeds 200,000 characters. Split the file."
                    )
            return pages
        finally:
            if converted:
                converted.close()


def split_questions(pages, topics):
    result = []
    marker = re.compile(r"(?im)^\s*(?:Q(?:uestion)?\s*\.?\s*\d+[.):]?|\d+[.)])\s+")
    for page, text in pages:
        matches = list(marker.finditer(text))
        spans = [
            (m.start(), matches[i + 1].start() if i + 1 < len(matches) else len(text))
            for i, m in enumerate(matches)
        ] or [(0, len(text))]
        for start, end in spans:
            content = text[start:end].strip()
            if len(content) < 5:
                continue
            if len(content) > 10000:
                raise ValueError(
                    "A question exceeds 10,000 characters. Split the source into numbered questions."
                )
            marks = re.search(
                r"(?:\[|\()\s*(\d{1,3})\s*(?:marks?)?\s*[\])]|\b(\d{1,3})\s+marks?\b",
                content,
                re.IGNORECASE,
            )
            result.append(
                {
                    "page": page,
                    "content": content,
                    "topic": next(
                        (t for t in topics if t.casefold() in content.casefold()),
                        "Unclassified",
                    ),
                    "marks": int(next(g for g in marks.groups() if g))
                    if marks
                    else None,
                    "confirmed": False,
                    "revision": 1,
                }
            )
    if not result or len(result) > 200:
        raise ValueError(
            "Expected 1–200 readable questions. Check the source and upload again."
        )
    return result


def process(owner_id, engine, paper_id, lease):
    try:
        with engine.connect() as conn:
            paper = _owned(owner_id, conn, db.papers, paper_id)
        chunks = split_questions(
            extract(paper["source"], paper["filename"]), paper["topics"]
        )
        error = None
        try:
            vectors = encode_questions(chunks)
            if vectors.shape[1] != 384:
                raise EmbeddingUnavailable(
                    "Personal papers require 384-dimensional embeddings."
                )
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.update(embedding=vector.tolist(), signature=signature())
        except EmbeddingUnavailable:
            error = "Questions extracted. Semantic indexing is unavailable; keyword search works after confirmation. Configure embeddings, then reindex."
        with engine.begin() as conn:
            changed = conn.execute(
                db.papers.update()
                .where(
                    db.papers.c.id == paper_id,
                    db.papers.c.owner_id == owner_id,
                    db.papers.c.lease == lease,
                    db.papers.c.status == "processing",
                )
                .values(status="needs review", error=error)
            )
            if changed.rowcount:
                conn.execute(
                    db.paper_questions.insert(),
                    [dict(owner_id=owner_id, paper_id=paper_id, **c) for c in chunks],
                )
    except Exception as exc:  # noqa: BLE001 -- background jobs must persist a safe failure state
        message = (
            str(exc)
            if isinstance(exc, ValueError)
            else "Could not extract this paper. Check the file and retry, or upload a UTF-8 transcript."
        )
        with engine.begin() as conn:
            conn.execute(
                db.papers.update()
                .where(
                    db.papers.c.id == paper_id,
                    db.papers.c.owner_id == owner_id,
                    db.papers.c.lease == lease,
                )
                .values(status="failed", error=message)
            )


def retry(owner_id, engine, paper_id):
    with engine.begin() as conn:
        row = _owned(owner_id, conn, db.papers, paper_id, lock=True)
        if row["status"] != "failed" and not (
            row["status"] == "processing"
            and time.time() - row["started_at"] > LEASE_SECONDS
        ):
            raise HTTPException(
                409, "Processing is still running or this paper is already extracted."
            )
        lease = str(uuid.uuid4())
        conn.execute(
            db.papers.update()
            .where(db.papers.c.id == paper_id, db.papers.c.owner_id == owner_id)
            .values(
                status="processing", error=None, lease=lease, started_at=time.time()
            )
        )
    return lease


def update_status(conn, owner_id, paper_id):
    rows = (
        conn.execute(
            select(db.paper_questions.c.confirmed).where(
                db.paper_questions.c.owner_id == owner_id,
                db.paper_questions.c.paper_id == paper_id,
            )
        )
        .scalars()
        .all()
    )
    conn.execute(
        db.papers.update()
        .where(db.papers.c.id == paper_id, db.papers.c.owner_id == owner_id)
        .values(status="ready" if rows and all(rows) else "needs review")
    )


def review(owner_id, engine, question_id, body):
    with engine.begin() as conn:
        row = _owned(owner_id, conn, db.paper_questions, question_id)
        paper = _owned(owner_id, conn, db.papers, row["paper_id"], lock=True)
        row = _owned(owner_id, conn, db.paper_questions, question_id, lock=True)
        if body.topic not in [*paper["topics"], "Unclassified"]:
            raise HTTPException(422, "Choose a topic from this paper's topic list.")
        if row["revision"] != body.revision:
            raise HTTPException(409, "This question changed. Reload it before saving.")
        values = body.model_dump()
        values["revision"] += 1
        if row["content"] != body.content:
            values.update(embedding=None, signature=None)
        conn.execute(
            db.paper_questions.update()
            .where(
                db.paper_questions.c.id == question_id,
                db.paper_questions.c.owner_id == owner_id,
            )
            .values(**values)
        )
        update_status(conn, owner_id, row["paper_id"])
    return {"ok": True}


def reindex(owner_id, engine, paper_id):
    with engine.connect() as conn:
        _owned(owner_id, conn, db.papers, paper_id)
        rows = [
            dict(r)
            for r in conn.execute(
                select(db.paper_questions).where(
                    db.paper_questions.c.paper_id == paper_id,
                    db.paper_questions.c.owner_id == owner_id,
                )
            ).mappings()
        ]
    if not rows:
        raise HTTPException(409, "Extract questions before indexing.")
    vectors = encode_questions(rows)
    if vectors.shape[1] != 384:
        raise EmbeddingUnavailable(
            "Personal papers require 384-dimensional embeddings."
        )
    with engine.begin() as conn:
        _owned(owner_id, conn, db.papers, paper_id, lock=True)
        for row, vector in zip(rows, vectors, strict=True):
            conn.execute(
                db.paper_questions.update()
                .where(
                    db.paper_questions.c.id == row["id"],
                    db.paper_questions.c.owner_id == owner_id,
                    db.paper_questions.c.revision == row["revision"],
                )
                .values(embedding=vector.tolist(), signature=signature())
            )
        conn.execute(
            db.papers.update()
            .where(db.papers.c.id == paper_id, db.papers.c.owner_id == owner_id)
            .values(error=None)
        )
    return {"ok": True}


def remove(owner_id, engine, paper_id):
    with engine.begin() as conn:
        _owned(owner_id, conn, db.papers, paper_id, lock=True)
        conn.execute(
            db.paper_questions.delete().where(
                db.paper_questions.c.owner_id == owner_id,
                db.paper_questions.c.paper_id == paper_id,
            )
        )
        conn.execute(
            db.papers.delete().where(
                db.papers.c.owner_id == owner_id, db.papers.c.id == paper_id
            )
        )
    return {"ok": True}


def search(owner_id, engine, body):
    q, p = db.paper_questions, db.papers
    query = (
        select(q, p.c.filename, p.c.year, p.c.subject_id)
        .join(p, (p.c.id == q.c.paper_id) & (p.c.owner_id == q.c.owner_id))
        .where(q.c.owner_id == owner_id, q.c.confirmed.is_(True))
    )
    if body.subject_id:
        get_subject(owner_id, engine, body.subject_id)
        query = query.where(p.c.subject_id == body.subject_id)
    if body.mode == "keyword":
        for word in body.query.split():
            query = query.where(
                (q.c.content.icontains(word, autoescape=True))
                | (q.c.topic.icontains(word, autoescape=True))
            )
        query = query.order_by(q.c.id.desc()).limit(30)
    else:
        vector = embedder.encode([body.query], query=True)[0]
        if len(vector) != 384:
            raise EmbeddingUnavailable(
                "Personal papers require 384-dimensional embeddings."
            )
        query = query.where(q.c.embedding.is_not(None), q.c.signature == signature())
        if engine.dialect.name == "postgresql":
            distance = q.c.embedding.cosine_distance(vector)
            query = (
                query.add_columns((1 - distance).label("similarity"))
                .where(distance <= 1 - settings.rag_threshold)
                .order_by(distance)
                .limit(30)
            )
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(query).mappings()]
    if body.mode == "semantic" and engine.dialect.name != "postgresql":
        for row in rows:
            row["similarity"] = float(np.dot(vector, row["embedding"]))
        rows = sorted(
            (r for r in rows if r["similarity"] >= settings.rag_threshold),
            key=lambda r: r["similarity"],
            reverse=True,
        )[:30]
    return [
        {k: v for k, v in r.items() if k not in {"embedding", "signature"}}
        for r in rows
    ]
