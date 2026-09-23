"""Synthetic browser fixtures; installed only by the disposable test server."""

import base64
import json
import re

from fastapi import HTTPException
from orbit import auth, gemini, projects


def install():
    original = auth.personal_model

    class WorkspaceModel:
        async def complete(self, messages, tools=None):
            selected = re.search(r"selected project ID (\d+)", messages[0]["content"])
            if tools is not None and selected:
                if messages[-1]["role"] == "tool":
                    return {
                        "role": "assistant",
                        "content": "The project notes say SELECT reads rows. This answer uses your selected project.",
                    }
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "project-fixture",
                            "type": "function",
                            "function": {
                                "name": "get_project_context",
                                "arguments": json.dumps(
                                    {
                                        "project_id": int(selected.group(1)),
                                        "query": "SELECT",
                                    }
                                ),
                            },
                        }
                    ],
                }
            return await original.complete(messages, tools)

    auth.personal_model = WorkspaceModel()
    gemini.recognize = recognize
    projects.github_json = github_json


async def recognize(data, mime, schema, instruction):
    if b"FAIL" in data:
        raise HTTPException(503, "Fixture failure")
    if "subjects" in schema.get("properties", {}):
        return {
            "profile": None,
            "semesters": [{"semester": "2", "sgpa": 8.4}],
            "subjects": [
                {
                    "name": "Database Systems",
                    "code": "DB",
                    "semester": "3",
                    "syllabus": "SQL SELECT reads rows. Joins and transactions.",
                }
            ],
            "marks": [
                {
                    "subject_code": "DB",
                    "semester": "3",
                    "title": "Imported quiz",
                    "score": 8,
                    "max_score": 10,
                    "assessed_on": "2026-06-01",
                    "kind": "quiz",
                }
            ],
        }
    return {"content": "SQL SELECT reads rows. Extracted fixture text."}


async def github_json(client, path, params=None):
    if path.startswith("/users/"):
        return {
            "login": path.split("/")[-1],
            "name": "Fixture developer",
            "public_repos": 6,
            "followers": 4,
            "following": 2,
        }
    if path.endswith("/commits"):
        return [{"sha": "a" * 40, "commit": {"tree": {"sha": "b" * 40}}}]
    if "/git/trees/" in path:
        return {
            "tree": [
                {
                    "path": "README.md",
                    "type": "blob",
                    "mode": "100644",
                    "size": 50,
                    "sha": "c" * 40,
                }
            ]
        }
    if "/git/blobs/" in path:
        return {
            "content": base64.b64encode(
                b"SQL SELECT reads rows. Public repo fixture."
            ).decode()
        }
    return {"default_branch": "main", "description": "Fixture project"}
