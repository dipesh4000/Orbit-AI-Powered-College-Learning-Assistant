import { useEffect, useState } from "react";
import { api, post } from "./api";
import EvidenceList from "./Evidence";
import "./practice.css";

export default function PracticeWorkspace({ subjects, demoMode }) {
  const [sets, setSets] = useState([]),
    [active, setActive] = useState(null);
  const [answers, setAnswers] = useState({}),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [subject, setSubject] = useState(""),
    [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("foundation"),
    [count, setCount] = useState(3);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    setError("");
    api("/personal/practice", { signal: c.signal })
      .then(setSets)
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [retry]);
  function choose(row) {
    setActive(row);
    setAnswers(Object.fromEntries((row.answers || []).map((a, i) => [i, a])));
  }
  function update(row) {
    setSets((s) => [row, ...s.filter((x) => x.id !== row.id)]);
    choose(row);
  }
  async function generate(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      update(
        await post("/personal/practice", {
          subject_id: Number(subject),
          topic,
          difficulty,
          count: Number(count),
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      update(
        await post(`/personal/practice/${active.id}/answers`, {
          answers: active.questions.map((_, i) => answers[i]),
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(row) {
    if (!window.confirm("Delete this practice set and its saved attempt?"))
      return;
    setBusy(true);
    setError("");
    try {
      await api(`/personal/practice/${row.id}`, { method: "DELETE" });
      setSets((s) => s.filter((x) => x.id !== row.id));
      if (active?.id === row.id) setActive(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const completed = sets.filter((s) => s.answered_at !== null);
  return (
    <section className="workspace-card practice-workspace">
      <div className="section-heading">
        <div>
          <span className="eyebrow">LEARN, TRY, REFLECT</span>
          <h2>Your practice</h2>
        </div>
        <span className="subtle">{completed.length} completed attempts</span>
      </div>
      <p>
        Build a short quiz from your confirmed paper material. Feedback stays
        separate from formal marks.
      </p>
      {demoMode && (
        <p className="subtle">
          The local demo has no quiz model connection. Saved attempts remain
          available; generation requires a configured provider.
        </p>
      )}
      <form className="record-form" onSubmit={generate}>
        <fieldset disabled={busy || loading}>
          <div className="form-grid">
            <label>
              Practice subject
              <select
                required
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              >
                <option value="">Choose a subject</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} · {s.code}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Practice topic
              <input
                required
                minLength={2}
                maxLength={120}
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Use a confirmed topic, e.g. SQL"
              />
            </label>
            <label>
              Difficulty
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
              >
                {["foundation", "intermediate", "advanced"].map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </label>
            <label>
              Questions
              <input
                type="number"
                min={1}
                max={10}
                value={count}
                required
                onChange={(e) => setCount(e.target.value)}
              />
            </label>
          </div>
          <small>
            Generation needs source text that establishes the answers. Questions
            without answer evidence may not support a quiz.
          </small>
          <button className="primary" disabled={!subjects.length}>
            {busy ? "Working…" : "Generate practice"}
          </button>
        </fieldset>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}{" "}
          <button disabled={busy} onClick={() => setRetry((n) => n + 1)}>
            Reload saved practice
          </button>
        </p>
      )}
      {loading && <p role="status">Loading saved practice…</p>}
      {active && (
        <form className="practice-set" onSubmit={submit}>
          <h3>
            {active.topic} · {active.difficulty}
          </h3>
          {active.answered_at !== null && (
            <p className="success-message" role="status">
              Saved practice result: {active.correct}/{active.questions.length}.
              This is practice feedback, not a formal grade.
            </p>
          )}
          {active.questions.map((q, i) => (
            <fieldset
              key={`${active.id}-${i}`}
              disabled={busy || active.answered_at !== null}
            >
              <legend>
                {i + 1}. {q.question}
              </legend>
              {q.options.map((option) => (
                <label className="practice-option" key={option}>
                  <input
                    type="radio"
                    name={`question-${i}`}
                    required
                    checked={answers[i] === option}
                    onChange={() => setAnswers((a) => ({ ...a, [i]: option }))}
                  />
                  <span>{option}</span>
                </label>
              ))}
              {active.answered_at !== null && (
                <div className="practice-feedback">
                  <strong>
                    {answers[i] === q.correct_answer
                      ? "Correct"
                      : "Review this answer"}
                  </strong>
                  <p>Answer: {q.correct_answer}</p>
                  <p>{q.explanation}</p>
                  <small>
                    AI-generated feedback. Check the source material.
                  </small>
                </div>
              )}
            </fieldset>
          ))}
          <EvidenceList sources={active.sources} />
          {active.answered_at === null && (
            <button
              className="primary"
              disabled={busy || active.questions.some((_, i) => !answers[i])}
            >
              Check and save answers
            </button>
          )}
        </form>
      )}
      <h3>Saved sets & attempts</h3>
      {!loading && !sets.length && (
        <div className="empty-state">
          No practice yet. Confirm source material in Papers, then create your
          first set here.
        </div>
      )}
      <div className="practice-history">
        {sets.map((row) => (
          <article key={row.id}>
            <div>
              <strong>{row.topic}</strong>
              <small>
                {new Date(row.created_at * 1000).toLocaleString()} ·{" "}
                {row.difficulty} ·{" "}
                {row.answered_at === null
                  ? "Ready to continue"
                  : `${row.correct}/${row.questions.length} in practice`}
              </small>
            </div>
            <button disabled={busy} onClick={() => choose(row)}>
              {row.answered_at === null ? "Continue" : "Review"}
            </button>
            <button disabled={busy} onClick={() => remove(row)}>
              Delete
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
