import asyncio

import pytest
from orbit import demo
from test_personal import environment as environment  # noqa: F401


@pytest.mark.parametrize("prompt, heading", [
    ("Tell about my Study room finder project", "Your Study room finder project"),
    ("Show my development and DSA coding stats together", "Development"),
    ("What should I focus on next?", "Decide what deserves attention first"),
    ("Help me plan a revision session", "60-minute session template"),
])
def test_saved_prompt_has_detailed_topic_specific_answer(environment, prompt, heading):
    owner = demo.seed(environment)
    result = asyncio.run(demo.reply(prompt, owner["id"], environment))
    assert heading in result["answer"]
    assert len(result["answer"].split()) >= 300
    assert result["answer"].count("###") >= 3
    if "project" in prompt:
        assert result["sources"]
        assert "Backend developer" in result["answer"]
