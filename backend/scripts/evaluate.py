"""Live smoke evaluation. Requires running Orbit + configured model; incurs API usage.

Checks tool/source contracts, not semantic correctness. Review the saved answers.
"""

import argparse
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--start", type=int, default=1, help="First scenario, one-based"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", default="live_evaluation.json")
    parser.add_argument(
        "--interval",
        type=float,
        default=0,
        help="Seconds between scenarios for provider rate limits",
    )
    args = parser.parse_args()
    if (
        args.start < 1
        or (args.limit is not None and args.limit < 1)
        or args.interval < 0
    ):
        parser.error("start and limit must be positive; interval must be nonnegative")
    scenarios = json.loads(
        (ROOT / "evaluation/scenarios.json").read_text(encoding="utf-8")
    )
    results = []
    with httpx.Client(base_url=args.url, timeout=180) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        if not health.json()["model_configured"]:
            raise SystemExit(
                "Configure LLM_API_KEY and LLM_MODEL before running live evaluation."
            )
        students = client.get("/api/students").json()
        if len(students) < 2:
            raise SystemExit("Import the dataset first.")
        client.post(
            "/api/session", json={"user_id": students[0]["user_id"]}
        ).raise_for_status()
        courses = client.get("/api/courses").json()
        selected = None
        for course in courses:
            response = client.get("/api/topics/" + course["course_id"])
            response.raise_for_status()
            topics = response.json()
            if topics:
                selected = course
                topic = topics[0]
                break
        if not selected:
            raise SystemExit(
                "Build a course index with material for the first student."
            )
        values = {
            "course": selected["title"],
            "course_id": selected["course_id"],
            "topic": topic,
            "other_user": students[1]["user_id"],
            **{
                level: f"demo-{selected['course_id']}-{level}"
                for level in ["foundation", "advanced", "closed"]
            },
        }
        selected_scenarios = scenarios[args.start - 1 :]
        if args.limit is not None:
            selected_scenarios = selected_scenarios[: args.limit]
        for number, scenario in enumerate(selected_scenarios, args.start):
            if results and args.interval:
                time.sleep(args.interval)
            if not scenario.get("follow_up"):
                client.delete("/api/conversation").raise_for_status()
            question = scenario["question"].format(**values)
            response = client.post("/api/chat", json={"message": question})
            actual = response.json()
            tools = set(actual.get("tools_called", []))
            passed = response.is_success
            if scenario.get("tools_any"):
                passed &= bool(tools.intersection(scenario["tools_any"]))
            if scenario.get("tools_all"):
                passed &= set(scenario["tools_all"]).issubset(tools)
            if scenario.get("sources"):
                passed &= bool(actual.get("sources"))
            if scenario.get("contains"):
                passed &= (
                    scenario["contains"].casefold()
                    in actual.get("answer", "").casefold()
                )
            results.append(
                {
                    "scenario": number,
                    "question": question,
                    "expected": scenario["expected"],
                    "actual": actual,
                    "contract_result": "PASS" if passed else "FAIL",
                    "semantic_review": "REQUIRED",
                    "http_status": response.status_code,
                }
            )
            print(
                f"{number:02}: {results[-1]['contract_result']} {question}", flush=True
            )
            # Preserve completed evidence even if a later provider/network request fails.
            (ROOT / "data").mkdir(exist_ok=True)
            (ROOT / "data" / Path(args.output).name).write_text(
                json.dumps(results, indent=2), encoding="utf-8"
            )
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / Path(args.output).name).write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(
        f"Saved data/{Path(args.output).name}. Tool-contract passes still require answer-quality review."
    )
    return 1 if any(row["contract_result"] == "FAIL" for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
