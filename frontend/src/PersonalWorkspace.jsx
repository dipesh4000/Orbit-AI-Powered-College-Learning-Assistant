import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Code2,
  FolderGit2,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Plus,
  Pencil,
  Trash2,
  ArrowUpRight,
  Sparkles,
} from "lucide-react";
import Assistant from "./PersonalChat";
import PracticeWorkspace from "./PracticeWorkspace";
import { api, post } from "./api";
import "./personal.css";
import CodingWorkspace from "./CodingWorkspace";
import PaperWorkspace from "./PaperWorkspace";
import Suggestions from "./Suggestions";

const subjectFields = [
  ["name", "Subject name"],
  ["code", "Subject code"],
  ["semester", "Semester"],
];
const kinds = ["quiz", "midterm", "final", "assignment", "lab"];
const today = () => new Date().toISOString().slice(0, 10);
const csvTemplate =
  "subject_code,semester,title,score,max_score,assessed_on,kind,weak_topics\nCS301,3,SQL quiz,8,10,2026-01-10,quiz,joins;subqueries\n";
const emptyEvent = {
  name: "",
  event_date: today(),
  role: "",
  project: "",
  summary: "",
  technologies: "",
  repo_url: "",
  submission_url: "",
  result: "",
  reflection: "",
};

function Editor({ type, initial, subjects, onSave, onCancel, busy }) {
  const defaults =
    type === "subjects"
      ? { name: "", code: "", semester: "" }
      : type === "assessments"
        ? {
            subject_id: subjects[0]?.id || "",
            title: "",
            score: "",
            max_score: "",
            assessed_on: today(),
            kind: "quiz",
            weak_topics: "",
          }
        : emptyEvent;
  const allowed = Object.keys(defaults);
  const [draft, setDraft] = useState(
    Object.fromEntries(
      allowed.map((k) => [
        k,
        Array.isArray(initial?.[k])
          ? initial[k].join("; ")
          : (initial?.[k] ?? defaults[k]),
      ]),
    ),
  );
  const [preview, setPreview] = useState(null);
  const [repoBusy, setRepoBusy] = useState(false);
  const [repoError, setRepoError] = useState("");
  function field(name, label, options = {}) {
    return (
      <label key={name}>
        {label}
        <input
          name={name}
          value={draft[name]}
          onChange={(e) => {
            setDraft((d) => ({ ...d, [name]: e.target.value }));
            if (name === "repo_url") setPreview(null);
          }}
          required
          {...options}
        />
      </label>
    );
  }
  async function previewRepo() {
    setRepoBusy(true);
    setRepoError("");
    setPreview(null);
    try {
      setPreview(
        await post("/personal/github-preview", { url: draft.repo_url }),
      );
    } catch (e) {
      setRepoError(e.message);
    } finally {
      setRepoBusy(false);
    }
  }
  function submit(event) {
    event.preventDefault();
    const body = { ...draft };
    if (type === "assessments") {
      body.subject_id = Number(body.subject_id);
      body.score = Number(body.score);
      body.max_score = Number(body.max_score);
      body.weak_topics = body.weak_topics
        .split(";")
        .map((s) => s.trim())
        .filter(Boolean);
    }
    if (type === "hackathons")
      body.technologies = body.technologies
        .split(";")
        .map((s) => s.trim())
        .filter(Boolean);
    onSave(type, body, initial?.id);
  }
  return (
    <form
      className="record-form"
      onSubmit={submit}
      aria-label={`${initial ? "Edit" : "Add"} ${type}`}
    >
      <fieldset disabled={busy || repoBusy}>
        {type === "subjects" && (
          <div className="form-grid">
            {subjectFields.map(([name, label]) =>
              field(name, label, { maxLength: name === "name" ? 100 : 40 }),
            )}
          </div>
        )}
        {type === "assessments" && (
          <>
            <div className="form-grid">
              <label>
                Subject
                <select
                  value={draft.subject_id}
                  required
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, subject_id: e.target.value }))
                  }
                >
                  <option value="" disabled>
                    Select subject
                  </option>
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · {s.code} · {s.semester}
                    </option>
                  ))}
                </select>
              </label>
              {field("title", "Assessment title", { maxLength: 200 })}
              <label>
                Assessment type
                <select
                  value={draft.kind}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, kind: e.target.value }))
                  }
                >
                  {kinds.map((k) => (
                    <option key={k}>{k}</option>
                  ))}
                </select>
              </label>
              {field("score", "Score", {
                type: "number",
                min: 0,
                max: draft.max_score || 1000000,
                step: "any",
              })}
              {field("max_score", "Maximum score", {
                type: "number",
                min: 0.000001,
                max: 1000000,
                step: "any",
              })}
              {field("assessed_on", "Assessment date", {
                type: "date",
                max: today(),
              })}
            </div>
            {field(
              "weak_topics",
              "Weak topics (optional; separate with semicolons)",
              {
                required: false,
                maxLength: 3000,
                placeholder: "joins; subqueries",
              },
            )}
            <small>
              These are topics you report, not an inferred skill score.
            </small>
          </>
        )}
        {type === "hackathons" && (
          <>
            <div className="form-grid">
              {field("name", "Hackathon name", { maxLength: 200 })}
              {field("event_date", "Event date", { type: "date" })}
              {field("role", "Your role", { maxLength: 120 })}
            </div>
            <div className="repo-input">
              {field("repo_url", "GitHub repository (optional)", {
                type: "url",
                required: false,
                maxLength: 500,
                placeholder: "https://github.com/owner/repo",
              })}
              <button
                type="button"
                onClick={previewRepo}
                disabled={!draft.repo_url}
              >
                Preview GitHub details
              </button>
            </div>
            {repoError && (
              <p role="alert" className="error">
                {repoError}
              </p>
            )}
            {preview && (
              <div className="github-preview">
                <strong>{preview.project}</strong>
                <p>{preview.summary || "No repository description."}</p>
                <small>
                  {preview.technologies === null
                    ? "Languages unavailable"
                    : preview.technologies.join(", ") ||
                      "No languages reported"}
                </small>
                <p>
                  Applying replaces the project name, description, and available
                  languages below. Nothing is saved yet.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setDraft((d) => ({
                      ...d,
                      project: preview.project,
                      summary: preview.summary,
                      technologies:
                        preview.technologies?.join("; ") ?? d.technologies,
                    }));
                    setPreview(null);
                  }}
                >
                  Apply GitHub details
                </button>
              </div>
            )}
            <div className="form-grid">
              {field("project", "Project name", { maxLength: 200 })}
              {field(
                "technologies",
                "Technologies (separate with semicolons)",
                { required: false, maxLength: 3000 },
              )}
              {field("result", "Result (optional)", {
                required: false,
                maxLength: 200,
              })}
            </div>
            {field("submission_url", "Submission link (optional)", {
              type: "url",
              required: false,
              maxLength: 500,
            })}
            {[
              ["summary", "Project description"],
              ["reflection", "Reflection"],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <textarea
                  value={draft[key]}
                  maxLength={4000}
                  rows={3}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, [key]: e.target.value }))
                  }
                />
              </label>
            ))}
          </>
        )}
        <div className="form-actions">
          <button className="primary" type="submit">
            {busy
              ? "Saving…"
              : initial
                ? "Save changes"
                : type === "subjects"
                  ? "Add subject"
                  : type === "assessments"
                    ? "Save mark"
                    : "Save hackathon"}
          </button>
          {onCancel && (
            <button type="button" onClick={onCancel}>
              Cancel
            </button>
          )}
        </div>
      </fieldset>
    </form>
  );
}

function DeleteDialog({ item, busy, onCancel, onConfirm }) {
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    element.showModal();
    return () => element.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="delete-dialog"
      aria-labelledby="delete-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onCancel();
      }}
    >
      <h2 id="delete-title">Delete {item.label}?</h2>
      <p>
        This permanently removes this record. Subjects with saved marks must
        have those marks removed first.
      </p>
      <div className="form-actions">
        <button autoFocus onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button className="danger" onClick={onConfirm} disabled={busy}>
          {busy ? "Deleting…" : "Delete record"}
        </button>
      </div>
    </dialog>
  );
}

export default function PersonalWorkspace({
  owner,
  onLogout,
  error: outerError,
  demoMode,
}) {
  const [data, setData] = useState(null),
    [tab, setTab] = useState("Assistant"),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState(null),
    [deleting, setDeleting] = useState(null),
    [filter, setFilter] = useState("");
  const [subjectVersion, setSubjectVersion] = useState(0);
  const [semester, setSemester] = useState(demoMode ? "4" : "");
  const fileRef = useRef(null);
  const subjects = data?.subjects || [],
    marks = data?.assessments || [],
    events = data?.hackathons || [];
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    api("/personal/workspace", { signal: c.signal })
      .then(setData)
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [owner.owner_id, attempt]);
  function changeTab(name) {
    setTab(name);
    setEditing(null);
    setError("");
    setNotice("");
  }
  async function save(type, body, id) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/${type}${id ? `/${id}` : ""}`, {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(body),
      });
      setEditing(null);
      setSubjectVersion((v) => v + 1);
      setNotice("Record saved.");
      setAttempt((a) => a + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setBusy(true);
    setError("");
    try {
      await api(`/${deleting.type}/${deleting.id}`, { method: "DELETE" });
      if (deleting.type === "subjects" && filter === String(deleting.id))
        setFilter("");
      setDeleting(null);
      setNotice("Record deleted.");
      setAttempt((a) => a + 1);
    } catch (e) {
      setDeleting(null);
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function importCsv(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (file.size > 1000000)
        throw new Error("Choose a CSV smaller than 1 MB.");
      const result = await post("/assessments/import", {
        content: await file.text(),
      });
      setNotice(`${result.imported} marks imported.`);
      setAttempt((a) => a + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }
  function actions(type, record, label) {
    return (
      <div className="record-actions">
        <button
          title={`Edit ${label}`}
          aria-label={`Edit ${label}`}
          disabled={busy}
          onClick={() => setEditing({ type, record })}
        >
          <Pencil size={15} />
        </button>
        <button
          title={`Delete ${label}`}
          aria-label={`Delete ${label}`}
          disabled={busy}
          onClick={() => setDeleting({ type, id: record.id, label })}
        >
          <Trash2 size={15} />
        </button>
      </div>
    );
  }
  const tabs = [
    ["Assistant", MessageSquare],
    ["Academics", BookOpen],
    ["Projects", FolderGit2],
    ["Actions", Sparkles],
    ["Practice", BookOpen],
    ["Coding", Code2],
    ["Papers", BookOpen],
  ];
  const shownMarks = marks.filter(
    (m) =>
      (!filter || String(m.subject_id) === filter) &&
      (!semester ||
        subjects.find((s) => s.id === m.subject_id)?.semester === semester),
  );
  return (
    <div
      className={`personal-shell ${tab === "Assistant" ? "chat-shell" : ""}`}
    >
      <aside className="personal-sidebar">
        <a className="brand" href="/dashboard">
          <span className="orbit-symbol">◌</span> orbit
        </a>
        <p className="eyebrow">YOUR WORKSPACE</p>
        <nav aria-label="Personal navigation">
          {tabs.map(([name, Icon]) => (
            <button
              key={name}
              className={tab === name ? "active" : ""}
              aria-current={tab === name ? "page" : undefined}
              onClick={() => changeTab(name)}
            >
              <Icon size={19} />
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <Sparkles size={18} />
          <strong>Small steps. Real progress.</strong>
          <p>Your records are private to your account.</p>
        </div>
        <div className="owner-card">
          <span className="owner-avatar">
            {owner.name.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <strong>{owner.name}</strong>
            <small>Personal workspace</small>
          </div>
        </div>
        <button className="signout" onClick={onLogout}>
          <LogOut size={17} />
          Sign out
        </button>
      </aside>
      <main className="personal-workspace">
        {demoMode && (
          <div className="demo-banner">
            <strong>Demo workspace · resets when the server stops</strong>42
            reference results from the supplied PDF; dates are declaration
            dates. Quizzes, coding, projects, and papers are labeled
            illustrative examples. <a href="/">View landing page</a>
          </div>
        )}
        <header className="workspace-topbar">
          <span>
            <LayoutDashboard size={16} />
            Workspace / {tab}
          </span>
          <span className="private-label">Private account</span>
        </header>
        {tab !== "Assistant" && (
          <div className="workspace-intro">
            <div>
              <p className="eyebrow">YOUR LEARNING, IN ONE PLACE</p>
              <h1>Welcome, {owner.name}</h1>
              <p>A little clarity for your next step.</p>
            </div>
            <span className="intro-date">
              {new Date().toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
          </div>
        )}
        {(error || outerError) && (
          <div role="alert" className="error">
            <span>{error || outerError}</span>
            <button
              onClick={() => {
                setError("");
                setAttempt((a) => a + 1);
              }}
            >
              Retry loading
            </button>
          </div>
        )}
        {notice && (
          <p role="status" className="success-message">
            {notice}
          </p>
        )}
        {loading && <p role="status">Loading records…</p>}
        {tab !== "Assistant" && (
          <div className="summary-grid">
            {[
              ["subjects", "Subjects", "Academics", BookOpen],
              ["assessments", "Recorded marks", "Academics", LayoutDashboard],
              ["hackathons", "Hackathons", "Projects", FolderGit2],
            ].map(([key, label, target, Icon]) => (
              <button
                className="summary-card"
                key={key}
                onClick={() => {
                  changeTab(target);
                  if (key === "assessments")
                    setTimeout(
                      () =>
                        document
                          .getElementById("marks-panel")
                          ?.scrollIntoView({ behavior: "smooth" }),
                      0,
                    );
                }}
              >
                <div>
                  <span>{label}</span>
                  <Icon size={20} />
                </div>
                <strong>{data ? data.counts[key] : "—"}</strong>
                <small>
                  View your records <ArrowUpRight size={14} />
                </small>
              </button>
            ))}
          </div>
        )}
        {data && tab === "Academics" && (
          <>
            <label className="semester-control">
              View semester
              <select
                aria-label="View semester"
                value={semester}
                onChange={(e) => {
                  setSemester(e.target.value);
                  setFilter("");
                }}
              >
                <option value="">All semesters</option>
                {[...new Set(subjects.map((s) => s.semester))]
                  .sort()
                  .map((s) => (
                    <option key={s} value={s}>
                      Semester {s}
                    </option>
                  ))}
              </select>
            </label>
            <section className="workspace-card">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">BUILD YOUR FOUNDATION</span>
                  <h2>Your subjects</h2>
                </div>
                <span className="subtle">
                  {subjects.length}{" "}
                  {subjects.length === 1 ? "subject" : "subjects"}
                </span>
              </div>
              {subjects.length ? (
                <ul className="subject-list">
                  {subjects
                    .filter((s) => !semester || s.semester === semester)
                    .map((s) => (
                      <li key={s.id}>
                        <div className="subject-symbol">
                          <BookOpen size={20} />
                        </div>
                        <div className="subject-detail">
                          <strong>{s.name}</strong>
                          <small>
                            {s.code} · {s.semester}
                          </small>
                          <span className="subtle">
                            {s.latest
                              ? `${s.latest.title} · ${s.latest.assessed_on}`
                              : "No marks recorded yet"}
                          </span>
                        </div>
                        <div className="subject-score">
                          {s.latest ? (
                            <>
                              <button
                                className="score-link"
                                onClick={() => {
                                  setFilter(String(s.id));
                                  document
                                    .getElementById("marks-panel")
                                    ?.scrollIntoView({ behavior: "smooth" });
                                }}
                              >
                                {s.latest.score}
                                <span> / {s.latest.max_score}</span>
                              </button>
                              <small>
                                {s.change == null
                                  ? "No comparable earlier result"
                                  : `${s.change > 0 ? "+" : ""}${s.change} pp · same type and scale`}
                              </small>
                            </>
                          ) : (
                            <span className="subtle">Not available</span>
                          )}
                        </div>
                        {actions("subjects", s, `subject ${s.name}`)}
                      </li>
                    ))}
                </ul>
              ) : (
                <div className="empty-state">
                  No subjects yet. Add your first subject to begin.
                </div>
              )}
              <h3 className="form-title">
                {editing?.type === "subjects"
                  ? "Edit subject"
                  : "Add a subject"}
              </h3>
              <Editor
                key={
                  editing?.type === "subjects"
                    ? `subject-edit-${editing.record.id}`
                    : `subject-new-${subjectVersion}`
                }
                type="subjects"
                initial={editing?.type === "subjects" ? editing.record : null}
                subjects={subjects}
                onSave={save}
                onCancel={
                  editing?.type === "subjects" ? () => setEditing(null) : null
                }
                busy={busy || loading}
              />
            </section>
            <section className="workspace-card" id="marks-panel">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">FORMAL ASSESSMENTS</span>
                  <h2>Your marks</h2>
                </div>
                <button
                  className="primary"
                  disabled={!subjects.length || busy}
                  onClick={() =>
                    setEditing({ type: "assessments", record: null })
                  }
                >
                  <Plus size={16} />
                  Add mark
                </button>
              </div>
              <p className="subtle">
                Every mark keeps its date and grading scale. Practice results
                stay separate.
              </p>
              <div className="marks-toolbar">
                <label>
                  Filter by subject
                  <select
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  >
                    <option value="">All subjects</option>
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} · {s.semester}
                      </option>
                    ))}
                  </select>
                </label>
                <div>
                  <a
                    download="orbit-marks-template.csv"
                    href={`data:text/csv;charset=utf-8,${encodeURIComponent(csvTemplate)}`}
                  >
                    Download CSV template
                  </a>
                  <label className="file-label">
                    Import marks CSV
                    <input
                      ref={fileRef}
                      type="file"
                      accept=".csv,text/csv"
                      onChange={importCsv}
                      disabled={!subjects.length || busy}
                    />
                  </label>
                </div>
              </div>
              <small className="subtle">
                Imports are all-or-nothing, up to 1,000 rows. Re-importing adds
                new records.
              </small>
              {editing?.type === "assessments" && (
                <Editor
                  key={`mark-${editing.record?.id || "new"}`}
                  type="assessments"
                  initial={editing.record}
                  subjects={subjects}
                  onSave={save}
                  onCancel={() => setEditing(null)}
                  busy={busy || loading}
                />
              )}
              {shownMarks.length ? (
                <div className="record-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Assessment</th>
                        <th>Subject</th>
                        <th>Score / maximum</th>
                        <th>Date</th>
                        <th>Reported weak topics</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shownMarks.map((m) => (
                        <tr key={m.id}>
                          <td>
                            <strong>{m.title}</strong>
                            <small>
                              {m.kind} · Record #{m.id}
                            </small>
                          </td>
                          <td>
                            {subjects.find((s) => s.id === m.subject_id)?.name}
                          </td>
                          <td>
                            <strong>
                              {m.score} / {m.max_score}
                            </strong>
                            <small>{m.percent}%</small>
                          </td>
                          <td>{m.assessed_on}</td>
                          <td>{m.weak_topics.join(", ") || "Not reported"}</td>
                          <td>
                            {actions("assessments", m, `mark ${m.title}`)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  No marks recorded{filter ? " for this subject" : ""}. Add a
                  dated result or import a CSV.
                </div>
              )}
            </section>
          </>
        )}
        {data && tab === "Projects" && (
          <section className="workspace-card">
            <div className="section-heading">
              <div>
                <span className="eyebrow">BUILD. COLLABORATE. REFLECT.</span>
                <h2>Projects & hackathons</h2>
              </div>
              <button
                className="primary"
                onClick={() => setEditing({ type: "hackathons", record: null })}
                disabled={busy}
              >
                <Plus size={16} />
                Add hackathon
              </button>
            </div>
            <p className="subtle">
              Keep the story behind your work: your role, what you built, and
              what you learned.
            </p>
            {editing?.type === "hackathons" && (
              <Editor
                key={`event-${editing.record?.id || "new"}`}
                type="hackathons"
                initial={editing.record}
                subjects={subjects}
                onSave={save}
                onCancel={() => setEditing(null)}
                busy={busy || loading}
              />
            )}
            {events.length ? (
              <div className="project-grid">
                {events.map((e) => (
                  <article className="project-card" key={e.id}>
                    <div className="section-heading">
                      <FolderGit2 size={24} />
                      {actions("hackathons", e, `hackathon ${e.name}`)}
                    </div>
                    <small className="subtle">
                      {e.event_date} · {e.role}
                    </small>
                    <h3>{e.project}</h3>
                    <strong>{e.name}</strong>
                    <p>{e.summary || "No project description added."}</p>
                    <div className="tech-tags">
                      {e.technologies.map((t) => (
                        <span key={t}>{t}</span>
                      ))}
                    </div>
                    <p>
                      <strong>Result:</strong> {e.result || "Not recorded"}
                    </p>
                    {e.reflection && (
                      <details>
                        <summary>Reflection</summary>
                        <p>{e.reflection}</p>
                      </details>
                    )}
                    <div className="project-links">
                      {e.repo_url && (
                        <a href={e.repo_url} target="_blank" rel="noreferrer">
                          Repository <ArrowUpRight size={14} />
                        </a>
                      )}
                      {e.submission_url && (
                        <a
                          href={e.submission_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Submission <ArrowUpRight size={14} />
                        </a>
                      )}
                    </div>
                    <small className="subtle">
                      Self-recorded · Event #{e.id}
                    </small>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                No hackathons yet. Record your first project and the role you
                played.
              </div>
            )}
          </section>
        )}
        <div hidden={tab !== "Assistant"} className="chat-view">
          <Assistant demoMode={demoMode} name={owner.name} />
        </div>
        {tab === "Actions" && <Suggestions />}
        {tab === "Practice" && (
          <PracticeWorkspace subjects={subjects} demoMode={demoMode} />
        )}
        {tab === "Coding" && <CodingWorkspace />}
        {tab === "Papers" && <PaperWorkspace subjects={subjects} />}
        <footer className="workspace-footer">
          Your records. Your pace. Your next step.
        </footer>
      </main>
      {deleting && (
        <DeleteDialog
          item={deleting}
          busy={busy}
          onCancel={() => setDeleting(null)}
          onConfirm={remove}
        />
      )}
    </div>
  );
}
