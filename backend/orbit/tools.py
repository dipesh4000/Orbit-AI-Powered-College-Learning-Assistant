from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .cache import cache
from .practice import PracticeInput, generate


class Empty(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CourseFilter(Empty):
    course_id: str | None = Field(default=None, max_length=100)


class Course(Empty):
    course_id: str = Field(min_length=1, max_length=100)


class WeakTopics(CourseFilter):
    threshold: float = Field(default=0.6, ge=0, le=1)


class Assessment(Empty):
    assessment_id: str = Field(min_length=1, max_length=100)


class Search(CourseFilter):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=8)


SPECS = {
    "list_courses": (
        Empty,
        "List the current student’s enrolled course IDs and titles. Resolve course names before calling other tools.",
    ),
    "get_course_progress": (
        CourseFilter,
        "Recorded course activity and demo engagement progress; includes score assumptions.",
    ),
    "get_course_performance": (
        Empty,
        "Course MCQ performance with documented demo full marks; missing scores are null.",
    ),
    "get_hackathon_history": (
        Empty,
        "Student hackathon history grouped by assessment round and attempt, with scores.",
    ),
    "get_weak_topics": (
        WeakTopics,
        "Weighted hackathon topic scores below a threshold. No scored data is not failure.",
    ),
    "get_recommended_topics": (
        Course,
        "Weak topics associated with a course subject using the documented demo mapping.",
    ),
    "list_assessments": (
        CourseFilter,
        "List configured demo assessments. Use their assessment_id for eligibility.",
    ),
    "check_assessment_eligibility": (
        Assessment,
        "Get a fresh deterministic eligibility decision and reasons. Narrate exactly; never derive your own decision.",
    ),
    "search_course_content": (
        Search,
        "Retrieve demo learning passages with source IDs and cosine similarity. Empty results mean insufficient material.",
    ),
    "generate_practice": (
        PracticeInput,
        "Generate and save schema-validated course-grounded practice questions.",
    ),
}


def schemas():
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": schema.model_json_schema(),
            },
        }
        for name, (schema, description) in SPECS.items()
    ]


class ToolRegistry:
    def __init__(self, services, retriever, model):
        self.services, self.retriever, self.model = services, retriever, model

    async def execute(self, name, arguments, user_id):
        from time import perf_counter

        from . import telemetry

        started, failed, hit = perf_counter(), True, False
        try:
            result, hit = await self._execute(name, arguments, user_id)
            failed = isinstance(result, dict) and "error" in result
            return result, hit
        finally:
            telemetry.record(
                "tool",
                name if name in SPECS else "unknown",
                (perf_counter() - started) * 1000,
                error=failed,
                cache_hit=hit,
            )

    async def _execute(self, name, arguments, user_id):
        if name not in SPECS:
            raise ValueError("Unknown tool.")
        # This is the only dispatch boundary. LLM-supplied identities cannot reach services.
        arguments = {k: v for k, v in arguments.items() if k != "user_id"}
        params = SPECS[name][0].model_validate(arguments).model_dump()
        if name == "search_course_content":
            if params["course_id"] and params["course_id"] not in {
                c["course_id"]
                for c in await run_in_threadpool(self.services.list_courses, user_id)
            }:
                return {"error": "Select one of your enrolled courses."}, False
            return await run_in_threadpool(self.retriever.search, **params), False
        if name == "generate_practice":
            return await generate(
                PracticeInput(**params),
                user_id,
                self.services,
                self.retriever,
                self.model,
            ), False
        fn = getattr(self.services, name)
        if name == "check_assessment_eligibility":
            return await run_in_threadpool(fn, user_id, **params), False
        key = (user_id, name, tuple(sorted(params.items())))
        return await run_in_threadpool(
            cache.get_or_load, key, lambda: fn(user_id, **params)
        )
