"""Saved coding evidence. External reads happen only on an explicit refresh."""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from ..core.database import coding_connections as connections
from ..core.database import coding_snapshots as snapshots

FETCH_TIMEOUT = 20


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    handle: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$")


class ManualInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)
    solved: int | None = Field(default=None, ge=0, le=1000000000)
    active_days: int | None = Field(default=None, ge=0, le=1000000000)
    contributions: int | None = Field(default=None, ge=0, le=1000000000)
    stars: int | None = Field(default=None, ge=0, le=1000000000)
    commits: int | None = Field(default=None, ge=0, le=1000000000)
    pull_requests: int | None = Field(default=None, ge=0, le=1000000000)
    issues: int | None = Field(default=None, ge=0, le=1000000000)
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def has_metric(self):
        if all(v is None for k, v in self.model_dump().items() if k != "note"):
            raise ValueError("Enter at least one metric; blank fields stay unknown.")
        return self


def count(value):
    return value if type(value) is int and 0 <= value <= 10**12 else None


def public_problem_details(data):
    """Keep bounded, displayable problem-solving data; never expose account fields."""
    private = (
        "email",
        "phone",
        "token",
        "secret",
        "password",
        "address",
        "birth",
        "userid",
        "user_id",
    )
    relevant = (
        "card",
        "problem",
        "question",
        "contest",
        "rating",
        "submission",
        "streak",
        "dsa",
        "topic",
        "difficulty",
        "platform",
        "award",
        "achievement",
        "badge",
        "rank",
        "fundamental",
        "heatmap",
        "distribution",
        "skill",
        "tag",
        "stats",
        "analysis",
        "calendar",
        "leetcode",
        "geeksforgeeks",
        "gfg",
        "codechef",
        "codeforces",
        "atcoder",
        "hackerrank",
        "codestudio",
        "codingninjas",
    )
    budget = [0]

    def clean(value, depth=0):
        if depth > 7 or budget[0] >= 10000:
            return None
        budget[0] += 1
        if isinstance(value, dict):
            return {
                str(key)[:80]: item
                for key, raw in list(value.items())[:1000]
                if not any(word in str(key).lower() for word in private)
                if (item := clean(raw, depth + 1)) is not None
            }
        if isinstance(value, list):
            return [
                item
                for raw in value[:1000]
                if (item := clean(raw, depth + 1)) is not None
            ]
        if type(value) is bool:
            return value
        if type(value) in (int, float) and 0 <= value <= 10**12:
            return value
        if (
            isinstance(value, str)
            and len(value) <= 160
            and not value.startswith(("http://", "https://"))
        ):
            return value
        return None

    return {
        key: clean(value)
        for key, value in data.items()
        if key not in ("githubProfileDetails", "userDetails")
        and "development" not in key.lower()
        and any(word in key.lower() for word in relevant)
        and (isinstance(value, (dict, list)) or type(value) in (int, float, bool))
    }


def normalize(raw, now):
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict) or raw.get("status", {}).get("success") is not True:
        raise ValueError("Unavailable profile")
    card = data.get("codolioCardDetails") or {}
    github = data.get("githubProfileDetails") or {}
    if not isinstance(card, dict) or not isinstance(github, dict):
        raise TypeError("Invalid provider response")
    result = {
        "solved": count(card.get("totalQuestionsSolved")),
        "active_days": count(card.get("totalActiveDays")),
        "contributions": count(github.get("totalContributions")),
        "stars": count(github.get("stars")),
        "commits": count(github.get("commitCounts")),
        "pull_requests": count(github.get("pushRequestsCount")),
        "issues": count(github.get("issues")),
        "github_active_days": count(github.get("totalActiveDays")),
    }
    if all(value is None for value in result.values()):
        raise ValueError("No supported coding metrics in this profile")
    # Provider timestamps have no timezone; preserve them as reported, not as UTC.
    updated = github.get("updatedAt")
    result["provider_updated_at"] = updated[:50] if isinstance(updated, str) else None
    activity = github.get("developmentActivity")
    days = {}
    end = datetime.fromtimestamp(now, UTC).date()
    start = end - timedelta(days=364)
    if isinstance(activity, dict):
        for stamp, value in activity.items():
            try:
                day = datetime.fromtimestamp(int(stamp), UTC).date()
            except (ValueError, TypeError, OverflowError, OSError):
                continue
            if start <= day <= end and count(value) is not None:
                days[day.isoformat()] = value
    result["activity"] = [
        {"date": day, "count": value} for day, value in sorted(days.items())
    ]
    languages = github.get("languageDistributions")
    values = (
        [
            (str(k)[:80], v)
            for k, v in languages.items()
            if count(v) and len(str(k)) <= 80
        ]
        if isinstance(languages, dict)
        else []
    )
    total = sum(v for _, v in values)
    result["languages"] = [
        {"name": name, "bytes": value, "percent": round(value / total * 100, 2)}
        for name, value in sorted(values, key=lambda item: -item[1])
    ]
    problem_activity = {}
    for key, value in data.items():
        if not isinstance(value, dict) or not any(
            word in key.lower()
            for word in (
                "problemactivity",
                "problemsolvingactivity",
                "problem_solving_activity",
                "submissioncalendar",
                "submission_calendar",
            )
        ):
            continue
        for stamp, amount in value.items():
            try:
                day = (
                    datetime.fromtimestamp(int(stamp), UTC).date()
                    if str(stamp).isdigit()
                    else datetime.fromisoformat(str(stamp)).date()
                )
            except (ValueError, TypeError, OverflowError, OSError):
                continue
            if start <= day <= end and count(amount) is not None:
                problem_activity[day.isoformat()] = amount
    result["problem_activity"] = [
        {"date": day, "count": value} for day, value in sorted(problem_activity.items())
    ]
    result["problem_details"] = public_problem_details(
        {
            key: value
            for key, value in data.items()
            if not (
                problem_activity
                and key.lower()
                in (
                    "problemsolvingactivity",
                    "problem_solving_activity",
                    "submissioncalendar",
                    "submission_calendar",
                )
            )
        }
    )
    return result


async def fetch_profile(handle):
    # Never follow a supplied URL or a provider redirect to another host.
    async with (
        httpx.AsyncClient(timeout=15, follow_redirects=False) as client,
        client.stream(
            "GET", "https://api.codolio.com/user/details", params={"userKey": handle}
        ) as response,
    ):
        response.raise_for_status()
        content = bytearray()
        async for chunk in response.aiter_bytes():
            content.extend(chunk)
            if len(content) > 2_000_000:
                raise ValueError("Provider response too large")
        import json

        return json.loads(content)


def packet(owner_id, engine):
    with engine.connect() as conn:
        connection = (
            conn.execute(select(connections).where(connections.c.owner_id == owner_id))
            .mappings()
            .first()
        )
        latest = {}
        history = {}
        for source in ("codolio", "manual"):
            rows = (
                conn.execute(
                    select(
                        snapshots.c.id,
                        snapshots.c.source,
                        snapshots.c.handle,
                        snapshots.c.fetched_at,
                        snapshots.c.normalized,
                    )
                    .where(
                        snapshots.c.owner_id == owner_id, snapshots.c.source == source
                    )
                    .order_by(snapshots.c.id.desc())
                    .limit(20)
                )
                .mappings()
                .all()
            )
            latest[source] = dict(rows[0]) if rows else None
            history[source] = [
                {
                    "id": r["id"],
                    "fetched_at": r["fetched_at"],
                    "solved": r["normalized"].get("solved"),
                    "contributions": r["normalized"].get("contributions"),
                }
                for r in rows
            ]
        return {
            "connection": {
                "handle": connection["handle"],
                "attempted_at": connection["attempted_at"],
                "error": connection["error"],
                "refreshing": bool(
                    connection["lease"]
                    and (connection["attempted_at"] or 0) > time.time() - 60
                ),
            }
            if connection
            else None,
            "latest": latest,
            "history": history,
        }


def connect(owner_id, engine, body):
    try:
        with engine.begin() as conn:
            conn.execute(
                connections.insert().values(owner_id=owner_id, handle=body.handle)
            )
    except IntegrityError:
        raise HTTPException(
            409,
            "A Codolio profile is already connected. Disconnect it before changing profiles.",
        ) from None
    return packet(owner_id, engine)


def claim(owner_id, engine):
    now, lease = time.time(), str(uuid4())
    with engine.begin() as conn:
        row = (
            conn.execute(
                select(connections)
                .where(connections.c.owner_id == owner_id)
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Connect a Codolio profile first.")
        if row["lease"] and row["attempted_at"] > now - 60:
            raise HTTPException(409, "A refresh is already running. Try again shortly.")
        conn.execute(
            connections.update()
            .where(connections.c.owner_id == owner_id)
            .values(lease=lease, attempted_at=now, error=None)
        )
        return row["handle"], lease


def finish(owner_id, engine, handle, lease, raw, normalized, error):
    with engine.begin() as conn:
        # Locks serialize finalization with disconnect. A cancelled lease cannot restore data.
        updated = conn.execute(
            connections.update()
            .where(connections.c.owner_id == owner_id, connections.c.lease == lease)
            .values(lease=None, error=error)
        )
        if updated.rowcount and normalized is not None:
            conn.execute(
                snapshots.insert().values(
                    owner_id=owner_id,
                    source="codolio",
                    handle=handle,
                    fetched_at=time.time(),
                    raw=raw,
                    normalized=normalized,
                )
            )


async def refresh(owner_id, engine, ticket=None):
    handle, lease = ticket or await run_in_threadpool(claim, owner_id, engine)
    raw = normalized = error = None
    try:
        async with asyncio.timeout(FETCH_TIMEOUT):
            raw = await fetch_profile(handle)
        normalized = normalize(raw, time.time())
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, TimeoutError):
        error = "Codolio could not be refreshed. Check the public handle or try later. Your last saved snapshot is unchanged."
    await run_in_threadpool(
        finish, owner_id, engine, handle, lease, raw, normalized, error
    )
    return await run_in_threadpool(packet, owner_id, engine)


def save_manual(owner_id, engine, body):
    values = body.model_dump()
    with engine.begin() as conn:
        conn.execute(
            snapshots.insert().values(
                owner_id=owner_id,
                source="manual",
                fetched_at=time.time(),
                raw=values,
                normalized={
                    **values,
                    "activity": [],
                    "languages": [],
                    "provider_updated_at": None,
                },
            )
        )
    return packet(owner_id, engine)


def remove(owner_id, engine, source):
    with engine.begin() as conn:
        if source == "codolio":
            conn.execute(connections.delete().where(connections.c.owner_id == owner_id))
        conn.execute(
            snapshots.delete().where(
                snapshots.c.owner_id == owner_id, snapshots.c.source == source
            )
        )
    return packet(owner_id, engine)
