import { useState } from "react";
import { api } from "./api";

function Evidence({ reference }) {
  const [data, setData] = useState(null),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const kind = reference.kind,
    key = reference.record_id ?? reference.id;
  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setData(null);
    setError("");
    try {
      setData((await api(`/personal/evidence/${kind}/${key}`)).data);
    } catch (e) {
      setError(e.message);
    }
  }
  return (
    <div className="evidence-row">
      <button type="button" onClick={toggle} aria-expanded={open}>
        <span>
          {kind}-{key}
        </span>{" "}
        {reference.source || reference.label}
      </button>
      {open && (
        <div className="evidence-detail">
          {error ? (
            <p role="alert">
              {error} The source may have been removed since this answer.
            </p>
          ) : !data ? (
            <p>Reading source…</p>
          ) : (
            <>
              {kind === "material" && (
                <>
                  <small>
                    {data.name} · {data.kind}
                  </small>
                  <p className="preserve-lines">{data.content}</p>
                </>
              )}
              {kind === "practice" && (
                <p>
                  {data.topic} ·{" "}
                  {data.answered_at == null
                    ? "Not submitted"
                    : `${data.correct}/${data.questions.length} in practice`}
                  <br />
                  Practice feedback is separate from formal marks.
                </p>
              )}
              {kind === "assessment" && (
                <p>
                  <strong>
                    {data.score}/{data.max_score}
                  </strong>{" "}
                  · {data.kind} · {data.assessed_on}
                  <br />
                  {data.title}
                  {data.weak_topics?.length > 0 && (
                    <>
                      <br />
                      Self-reported topics: {data.weak_topics.join(", ")}
                    </>
                  )}
                </p>
              )}
              {kind === "question" && (
                <>
                  <small>
                    {data.filename} · {data.year} · page {data.page} ·{" "}
                    {data.marks ?? "Unknown"} marks
                  </small>
                  <p>{data.content}</p>
                </>
              )}
              {kind === "subject" && (
                <p>
                  {data.name} · {data.code} · semester {data.semester}
                </p>
              )}
              {kind === "hackathon" && (
                <p>
                  {data.project} · {data.event_date}
                  <br />
                  {data.role}
                  <br />
                  {data.reflection || data.summary}
                </p>
              )}
              {kind === "coding" && (
                <p>
                  {data.source} · saved{" "}
                  {new Date(data.fetched_at * 1000).toLocaleString()}
                  <br />
                  Solved: {data.normalized.solved ?? "Unknown"} · contributions:{" "}
                  {data.normalized.contributions ?? "Unknown"}
                  <br />
                  {data.normalized.note}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function EvidenceList({ sources = [] }) {
  if (!sources.length) return null;
  return (
    <details className="evidence-list">
      <summary>{sources.length} supporting records</summary>
      <p>
        Open a record to check its current value. Earlier answers may reflect an
        older version.
      </p>
      {sources.map((r) => (
        <Evidence key={`${r.kind}-${r.record_id ?? r.id}`} reference={r} />
      ))}
    </details>
  );
}
