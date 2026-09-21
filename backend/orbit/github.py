"""Optional GitHub enrichment. User content is never used as a fetch hostname."""

import asyncio
import re
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class RepoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=500)


async def preview_repo(url):
    try:
        parsed = urlsplit(url.strip())
    except ValueError as exc:
        raise HTTPException(422, "Invalid repository URL.") from exc
    match = re.fullmatch(r"/([\w.-]+)/([\w.-]+)/?", parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != "github.com"
        or not match
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(
            422, "Paste a repository URL such as https://github.com/owner/repo."
        )
    owner, repo = match.groups()
    repo = repo.removesuffix(".git")
    if owner in {".", ".."} or repo in {"", ".", ".."}:
        raise HTTPException(422, "Invalid repository URL.")
    base = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=False,
            headers={"Accept": "application/vnd.github+json"},
        ) as client:
            metadata, languages = await asyncio.gather(
                client.get(base),
                client.get(base + "/languages"),
                return_exceptions=True,
            )
        if isinstance(metadata, Exception):
            raise metadata
        if metadata.status_code == 404:
            raise HTTPException(
                404,
                "Public repository not found. You can still enter details manually.",
            )
        metadata.raise_for_status()
        body = metadata.json()
        if not isinstance(body, dict) or not isinstance(body.get("name"), str):
            raise TypeError("Invalid GitHub response")
        techs = None
        if isinstance(languages, httpx.Response) and languages.status_code == 200:
            language_data = languages.json()
            if isinstance(language_data, dict):
                techs = list(language_data)[:30]
        return {
            "project": body["name"][:200],
            "summary": (body.get("description") or "")[:4000],
            "technologies": techs,
            "source": "GitHub",
            "repo_url": f"https://github.com/{owner}/{repo}",
        }
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            503,
            "GitHub is unavailable or rate limited. Your form is unchanged; enter details manually.",
        ) from exc
