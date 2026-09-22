"""Synthetic provider for browser tests only; never loaded by orbit.main."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx

calls = {}


async def fetch(handle):
    await asyncio.sleep(0.2)
    calls[handle] = calls.get(handle, 0) + 1
    if calls[handle] > 1:
        raise httpx.ReadTimeout("Synthetic provider outage")
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "status": {"success": True},
        "data": {
            "codolioCardDetails": {"totalQuestionsSolved": 128, "totalActiveDays": 47},
            "githubProfileDetails": {
                "totalContributions": 256,
                "stars": 12,
                "commitCounts": 204,
                "pushRequestsCount": 7,
                "issues": 3,
                "developmentActivity": {
                    str(int((now - timedelta(days=i)).timestamp())): (i * 7) % 13
                    for i in range(365)
                },
                "languageDistributions": {
                    "Python": 400,
                    "TypeScript": 320,
                    "JavaScript": 180,
                    "CSS": 100,
                },
                "updatedAt": "2026-09-20T10:00:00",
            },
        },
    }
