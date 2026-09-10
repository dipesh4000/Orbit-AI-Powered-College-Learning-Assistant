import os

import pytest
from orbit.config import ROOT, settings
from orbit.rag import Retriever


@pytest.fixture(scope="module")
def retriever():
    if os.getenv("ORBIT_LIVE_EMBEDDINGS") != "1" or not settings.hf_token:
        pytest.skip(
            "Set ORBIT_LIVE_EMBEDDINGS=1 and HF_TOKEN for paid live retrieval checks."
        )
    if not (ROOT / "data/rag/index.faiss").exists():
        pytest.skip("Build the Hugging Face course index to run live embedding checks.")
    return Retriever()


def test_normalization_retrieves_relevant_source(retriever):
    result = retriever.search("Explain database normalization")
    assert result[0]["id"] == "sql-normalization-0"


def test_python_retrieves_relevant_source(retriever):
    result = retriever.search("What is a Python tuple?")
    assert result[0]["id"] == "python-functions-0"


@pytest.mark.parametrize(
    "query",
    ["What is the secret campus parking policy?", "How do I bake a chocolate cake?"],
)
def test_unknown_topics_fail_groundedness_gate(retriever, query):
    assert retriever.search(query) == []


def test_course_filter_excludes_other_courses(retriever):
    assert (
        retriever.search(
            "Explain database normalization", course_id="course-not-in-catalog"
        )
        == []
    )
