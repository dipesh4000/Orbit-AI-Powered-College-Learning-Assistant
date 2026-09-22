import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  FileText,
  Plus,
  Search,
  Upload,
  X,
} from "lucide-react";
import { api, post, apiUrl } from "./api";
import "./papers.css";

function Question({ question, topics, save, remove, busy }) {
  const [draft, setDraft] = useState(question);
  const dirty =
    draft.content !== question.content ||
    draft.topic !== question.topic ||
    String(draft.marks ?? "") !== String(question.marks ?? "") ||
    Number(draft.page) !== question.page;
  function submit(event) {
    event.preventDefault();
    const confirmed = event.nativeEvent.submitter?.value === "confirm";
    save(question.id, {
      content: draft.content,
      topic: draft.topic,
      marks:
        draft.marks === "" || draft.marks == null ? null : Number(draft.marks),
      page: Number(draft.page),
      confirmed,
      revision: question.revision,
    });
  }
  return (
    <form className="question-card" onSubmit={submit}>
      <div className="question-top">
        <span className={`paper-status ${question.confirmed ? "ready" : ""}`}>
          {question.confirmed ? (
            <>
              <Check size={13} /> Confirmed
            </>
          ) : (
            "Needs your review"
          )}
        </span>
        <span>
          Page {question.page} ·{" "}
          {question.indexed ? "Indexed" : "Keyword search only"}
        </span>
      </div>
      <fieldset disabled={busy}>
        <label>
          Question text
          <textarea
            required
            minLength={5}
            maxLength={10000}
            value={draft.content}
            onChange={(e) => setDraft({ ...draft, content: e.target.value })}
          />
        </label>
        <div className="question-fields">
          <label>
            Topic
            <select
              value={draft.topic}
              onChange={(e) => setDraft({ ...draft, topic: e.target.value })}
            >
              {[...new Set([...topics, "Unclassified"])].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>
            Marks
            <input
              type="number"
              min="0"
              max="1000"
              value={draft.marks ?? ""}
              onChange={(e) => setDraft({ ...draft, marks: e.target.value })}
            />
          </label>
          <label>
            Source page
            <input
              type="number"
              min="1"
              max="40"
              required
              value={draft.page}
              onChange={(e) => setDraft({ ...draft, page: e.target.value })}
            />
          </label>
        </div>
        <div className="question-actions">
          <button type="submit" value="draft">
            Save as draft
          </button>
          <button className="primary" type="submit" value="confirm">
            <Check size={15} />
            {question.confirmed && !dirty
              ? "Keep confirmed"
              : "Confirm question"}
          </button>
          <button
            type="button"
            className="paper-remove"
            onClick={() => remove(question.id)}
          >
            Remove
          </button>
        </div>
      </fieldset>
    </form>
  );
}

export default function PaperWorkspace({ subjects }) {
  const [papers, setPapers] = useState([]),
    [selected, setSelected] = useState(null),
    [detail, setDetail] = useState(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false),
    [searchOpen, setSearchOpen] = useState(false),
    [results, setResults] = useState(null),
    [searchBusy, setSearchBusy] = useState(false);
  const [deletion, setDeletion] = useState(null);
  const dialog = useRef(null);
  useEffect(() => {
    if (deletion) dialog.current?.showModal();
  }, [deletion]);
  async function refresh(id = selected) {
    const list = await api("/papers");
    setPapers(list);
    if (id) setDetail(await api(`/papers/${id}`));
  }
  useEffect(() => {
    const c = new AbortController();
    api("/papers", { signal: c.signal })
      .then(setPapers)
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, []);
  useEffect(() => {
    if (!papers.some((p) => p.status === "processing")) return;
    const timer = setTimeout(
      () => refresh().catch((e) => setError(e.message)),
      2000,
    );
    return () => clearTimeout(timer);
  }, [papers, selected]);
  async function run(action, message) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh();
      setResults(null);
      if (message) setNotice(message);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function openPaper(id) {
    setError("");
    setBusy(true);
    try {
      setDetail(await api(`/papers/${id}`));
      setSelected(id);
      setUploadOpen(false);
      setSearchOpen(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = new FormData(form);
    if (body.get("file").size > 10 * 1024 * 1024) {
      setError("Choose a paper up to 10 MB.");
      return;
    }
    await run(async () => {
      await api("/papers", { method: "POST", body });
      setUploadOpen(false);
    }, "Paper uploaded. Extraction continues in the background.");
  }
  async function find(event) {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(event.currentTarget));
    body.subject_id = body.subject_id ? Number(body.subject_id) : null;
    setError("");
    setSearchBusy(true);
    try {
      setResults(await post("/papers/search", body));
    } catch (e) {
      setError(e.message);
      setResults(null);
    } finally {
      setSearchBusy(false);
    }
  }
  return (
    <div className="paper-workspace">
      <section className="paper-hero">
        <div>
          <p className="eyebrow">YOUR PERSONAL QUESTION LIBRARY</p>
          <h2>Past papers. Fresh perspective.</h2>
          <p>
            Turn the papers you’ve collected into questions you can come back
            to.
          </p>
        </div>
        <div className="paper-hero-icon">
          <FileText size={39} />
          <span>✳</span>
        </div>
      </section>
      <div className="paper-toolbar">
        <div className="paper-counts">
          <strong>{papers.length}</strong> papers <span>·</span>{" "}
          <strong>{papers.reduce((n, p) => n + p.confirmed_count, 0)}</strong>{" "}
          confirmed questions
        </div>
        <div>
          <button
            onClick={() => {
              setSearchOpen(!searchOpen);
              setSelected(null);
            }}
            disabled={busy}
          >
            <Search size={16} /> Search questions
          </button>
          <button
            className="primary"
            onClick={() => {
              setUploadOpen(!uploadOpen);
              setSelected(null);
            }}
            disabled={busy}
          >
            <Plus size={16} /> Upload paper
          </button>
        </div>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="paper-notice" role="status">
          {notice}
        </p>
      )}
      {uploadOpen && (
        <form className="workspace-card paper-upload" onSubmit={upload}>
          <h3>Bring a paper into your workspace</h3>
          <p>
            PDF, PNG, JPEG, or UTF-8 text · up to 10 MB and 40 pages. Scans need
            server OCR. You’ll review every question before it enters search.
          </p>
          <fieldset disabled={busy}>
            <div className="paper-upload-grid">
              <label>
                Subject
                <select name="subject_id" aria-label="Subject" required defaultValue="">
                  <option value="" disabled>
                    Select a subject
                  </option>
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · {s.code}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Paper year
                <input
                  name="year"
                  type="number"
                  min="1900"
                  max={new Date().getFullYear()}
                  defaultValue={new Date().getFullYear()}
                  required
                />
              </label>
            </div>
            {!subjects.length && (
              <p className="paper-notice">
                Add a subject in Academics first, then return to upload your
                paper.
              </p>
            )}
            <label>
              Topics for this paper
              <input
                name="topics"
                placeholder="SQL, Joins, Normalization"
                maxLength={5000}
              />
              <small>
                Comma-separated. These become your review choices; unmatched
                questions start as Unclassified.
              </small>
            </label>
            <label className="paper-drop">
              <Upload size={25} />
              <strong>Choose your past paper</strong>
              <input
                name="file"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.txt"
                required
              />
            </label>
            <div className="form-actions">
              <button type="button" onClick={() => setUploadOpen(false)}>
                Cancel
              </button>
              <button className="primary" disabled={!subjects.length}>
                {busy ? "Uploading…" : "Upload and extract"}
              </button>
            </div>
          </fieldset>
        </form>
      )}
      {searchOpen && (
        <section className="workspace-card paper-search">
          <h3>Find a question to revisit</h3>
          <p>
            Only questions you’ve confirmed appear here. Keyword search works
            without an AI connection.
          </p>
          <form onSubmit={find}>
            <label>
              Search query
              <input
                name="query"
                required
                maxLength={500}
                placeholder="Try SQL or normalization"
              />
            </label>
            <div className="paper-upload-grid">
              <label>
                Subject
                <select name="subject_id" aria-label="Subject">
                  <option value="">All subjects</option>
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Search mode
                <select name="mode">
                  <option value="keyword">Keyword and topic</option>
                  <option value="semantic">Semantic similarity</option>
                </select>
              </label>
            </div>
            <button className="primary" disabled={searchBusy}>
              {searchBusy ? "Searching…" : "Search confirmed questions"}
            </button>
          </form>
          {results !== null && (
            <div aria-live="polite">
              <p>
                {results.length} matching questions
                {results.length === 30 ? " (showing first 30)" : ""}
              </p>
              {results.map((r) => (
                <article className="paper-result" key={r.id}>
                  <small>
                    {r.topic} · {r.filename} · {r.year} · page {r.page}
                  </small>
                  <p>{r.content}</p>
                  <button onClick={() => openPaper(r.paper_id)}>
                    Open source paper
                  </button>
                </article>
              ))}
              {!results.length && (
                <p>
                  Try another topic, or confirm questions from a paper first.
                  Semantic search also requires current embeddings; use Reindex
                  questions after editing.
                </p>
              )}
            </div>
          )}
        </section>
      )}
      {selected && detail ? (
        <section className="paper-review">
          <button
            onClick={() => {
              setSelected(null);
              setDetail(null);
            }}
          >
            <ArrowLeft size={16} /> All papers
          </button>
          <div className="paper-review-heading">
            <div>
              <h3>{detail.filename}</h3>
              <p>
                {detail.year} ·{" "}
                {detail.questions.filter((q) => q.confirmed).length}/
                {detail.questions.length} confirmed · {detail.status}
              </p>
            </div>
            <button
              disabled={busy || !detail.questions.length}
              onClick={() =>
                run(
                  () => post(`/papers/${selected}/reindex`, {}),
                  "Search index updated.",
                )
              }
            >
              Reindex questions
            </button>
          </div>
          <p className="paper-review-help">
            Check the wording, source page, topic, and marks. Fix split
            questions with Add missing question and Remove. Confirmed text
            changes need reindexing for semantic search.
          </p>
          <a className="paper-source-link" href={apiUrl(`/papers/${selected}/source`)} download={detail.filename}>Download original paper ↗</a>
          {detail.error && <p className="paper-notice">{detail.error}</p>}
          {detail.status === "processing" && (
            <p role="status">
              Extracting questions… You can leave this page and come back.
            </p>
          )}
          {detail.questions.map((q) => (
            <Question
              key={`${q.id}-${q.revision}`}
              question={q}
              topics={detail.topics}
              busy={busy}
              save={(id, body) =>
                run(
                  () =>
                    api(`/paper-questions/${id}`, {
                      method: "PUT",
                      body: JSON.stringify(body),
                    }),
                  body.confirmed
                    ? "Question confirmed."
                    : "Draft saved. This question is excluded from search.",
                )
              }
              remove={(id) => setDeletion({ kind: "question", id })}
            />
          ))}
          {!["processing", "failed"].includes(detail.status) && (
            <button
              disabled={busy}
              onClick={() =>
                run(() => post(`/papers/${selected}/questions`, {}))
              }
            >
              <Plus size={16} /> Add missing question
            </button>
          )}
        </section>
      ) : (
        <div className="paper-list">
          {loading ? (
            <p role="status">Loading your papers…</p>
          ) : papers.length ? (
            papers.map((p) => (
              <article className="paper-list-card" key={p.id}>
                <div className="paper-file-icon">
                  <FileText size={24} />
                </div>
                <div className="paper-file-info">
                  <h3>{p.filename}</h3>
                  <p>
                    {subjects.find((s) => s.id === p.subject_id)?.name} ·{" "}
                    {p.year}
                  </p>
                  <span
                    className={`paper-status ${p.status === "ready" ? "ready" : ""}`}
                  >
                    {p.status}
                  </span>
                  <small>
                    {p.confirmed_count}/{p.total} questions confirmed
                  </small>
                  {p.error && <p className="paper-inline-error">{p.error}</p>}
                </div>
                <div className="paper-list-actions">
                  <button disabled={busy} onClick={() => openPaper(p.id)}>
                    Review questions
                  </button>
                  {p.retryable && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        run(() => post(`/papers/${p.id}/retry`, {}))
                      }
                    >
                      Retry extraction
                    </button>
                  )}
                  <button
                    className="paper-remove"
                    disabled={busy}
                    onClick={() => setDeletion({ kind: "paper", id: p.id })}
                  >
                    Delete paper
                  </button>
                </div>
              </article>
            ))
          ) : (
            <section className="paper-empty">
              <div className="paper-empty-icon">
                <FileText size={35} />
              </div>
              <h3>Your next revision starts here.</h3>
              <p>
                That folder of past papers? Give it a new purpose.
                <br />
                Upload one, check the questions, and make it yours.
              </p>
              <button className="primary" onClick={() => setUploadOpen(true)}>
                <Upload size={16} /> Upload your first paper
              </button>
              <div className="paper-steps">
                <span>
                  01 <b>Upload</b>
                </span>
                <span>
                  02 <b>Review</b>
                </span>
                <span>
                  03 <b>Rediscover</b>
                </span>
              </div>
            </section>
          )}
        </div>
      )}
      {deletion && (
        <dialog
          ref={dialog}
          className="delete-dialog"
          onCancel={(e) => {
            e.preventDefault();
            if (!busy) setDeletion(null);
          }}
        >
          <h2>Delete this {deletion.kind}?</h2>
          <p>
            {deletion.kind === "paper"
              ? "This removes the original upload and all its questions from your workspace and search."
              : "This removes this extracted question from review and search."}
          </p>
          <div className="form-actions">
            <button autoFocus disabled={busy} onClick={() => setDeletion(null)}>
              <X size={14} /> Cancel
            </button>
            <button
              className="danger"
              disabled={busy}
              onClick={async () => {
                const item = deletion;
                setDeletion(null);
                if (item.kind === "paper") {
                  setSelected(null);
                  setDetail(null);
                }
                setBusy(true);
                setError("");
                try {
                  await api(
                    item.kind === "paper"
                      ? `/papers/${item.id}`
                      : `/paper-questions/${item.id}`,
                    { method: "DELETE" },
                  );
                  await refresh(item.kind === "paper" ? null : selected);
                  setResults(null);
                } catch (e) {
                  setError(e.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Delete {deletion.kind}
            </button>
          </div>
        </dialog>
      )}
    </div>
  );
}
