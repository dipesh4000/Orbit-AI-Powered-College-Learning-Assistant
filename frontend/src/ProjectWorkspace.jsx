import { useEffect, useState } from "react";
import { FolderGit2, MessageSquare, Plus } from "lucide-react";
import { api, post } from "./api";
import PracticeWorkspace from "./PracticeWorkspace";
import PaperWorkspace from "./PaperWorkspace";

const blank = { name: "", description: "", subject_ids: [] };
export default function ProjectWorkspace({ subjects, demoMode, onChat }) {
  const [rows, setRows] = useState([]),
    [project, setProject] = useState(null);
  const [draft, setDraft] = useState(null),
    [editing, setEditing] = useState(null),
    [repo, setRepo] = useState("");
  const [mode, setMode] = useState("Projects"),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true);
  const [error, setError] = useState(""),
    [version, setVersion] = useState(0);
  const [material, setMaterial] = useState(null),
    [text, setText] = useState("");
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    api("/projects", { signal: c.signal })
      .then(setRows)
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [version]);
  async function run(work) {
    setBusy(true);
    setError("");
    try {
      await work();
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function open(row) {
    await run(async () => {
      setProject(await api(`/projects/${row.id}`));
      setMaterial(null);
      setRepo("");
    });
  }
  return (
    <>
      <div className="workspace-intro">
        <div>
          <p className="eyebrow">MAKE SPACE TO LEARN</p>
          <h1>Practice</h1>
          <p>
            Bring a repository, a question paper, or a subject. Build a project
            and talk it through with Orbit.
          </p>
        </div>
        <button
          className="primary"
          onClick={() => {
            setMode("Projects");
            setEditing(null);
            setDraft(blank);
          }}
        >
          <Plus size={16} />
          Add project
        </button>
      </div>
      <div className="workspace-subtabs">
        {["Projects", "Question papers", "Quizzes"].map((v) => (
          <button key={v} aria-pressed={mode === v} onClick={() => setMode(v)}>
            {v}
          </button>
        ))}
      </div>
      {error && (
        <p className="error" role="alert">
          {error}{" "}
          <button
            disabled={busy}
            onClick={() => {
              setError("");
              setVersion((v) => v + 1);
            }}
          >
            Reload projects
          </button>
        </p>
      )}
      {mode === "Quizzes" && (
        <PracticeWorkspace subjects={subjects} demoMode={demoMode} />
      )}
      {mode === "Question papers" && <PaperWorkspace subjects={subjects} />}
      {mode === "Projects" && (
        <>
          {draft && (
            <form
              className="workspace-card record-form"
              onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  const r = await api(
                    `/projects${editing ? `/${editing}` : ""}`,
                    {
                      method: editing ? "PUT" : "POST",
                      body: JSON.stringify(draft),
                    },
                  );
                  setProject(r);
                  setDraft(null);
                  setMaterial(null);
                });
              }}
            >
              <fieldset disabled={busy}>
                <h2>{editing ? "Edit project" : "Add a project"}</h2>
                <div className="form-grid">
                  <label>
                    Project name
                    <input
                      required
                      maxLength={150}
                      value={draft.name}
                      onChange={(e) =>
                        setDraft((d) => ({ ...d, name: e.target.value }))
                      }
                      placeholder="e.g. Database revision or My portfolio"
                    />
                  </label>
                  <label>
                    Learning goal
                    <textarea
                      maxLength={4000}
                      rows={3}
                      value={draft.description}
                      onChange={(e) =>
                        setDraft((d) => ({ ...d, description: e.target.value }))
                      }
                    />
                  </label>
                </div>
                <div className="subject-options">
                  <span>Practise subjects (optional)</span>
                  {subjects.length ? (
                    subjects.map((s) => (
                      <label key={s.id}>
                        <input
                          type="checkbox"
                          checked={draft.subject_ids.includes(s.id)}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              subject_ids: e.target.checked
                                ? [...d.subject_ids, s.id]
                                : d.subject_ids.filter((id) => id !== s.id),
                            }))
                          }
                        />
                        {s.name} · {s.semester}
                      </label>
                    ))
                  ) : (
                    <p>
                      Add subjects in Dashboard to link their syllabus here.
                    </p>
                  )}
                </div>
                <div className="form-actions">
                  <button className="primary">
                    {editing ? "Save project" : "Create project"}
                  </button>
                  <button type="button" onClick={() => setDraft(null)}>
                    Cancel
                  </button>
                </div>
              </fieldset>
            </form>
          )}
          {loading && <p role="status">Loading projects…</p>}
          {!loading && !rows.length && !draft && (
            <section className="workspace-card project-empty">
              <FolderGit2 size={42} />
              <h2>What would you like to work on?</h2>
              <p>
                Create a project, add a public GitHub repository or documents,
                or select subjects to practise. Your project becomes context for
                the main chat.
              </p>
              <button className="primary" onClick={() => setDraft(blank)}>
                Create your first project
              </button>
            </section>
          )}
          <div className="learning-project-grid">
            {rows.map((r) => (
              <article
                className={`workspace-card learning-project ${project?.id === r.id ? "selected" : ""}`}
                key={r.id}
              >
                <FolderGit2 size={24} />
                <h2>{r.name}</h2>
                <p>
                  {r.description || "Add material and start a conversation."}
                </p>
                <small>{r.subject_ids.length} linked subjects</small>
                <div className="form-actions">
                  <button disabled={busy} onClick={() => open(r)}>
                    Open project
                  </button>
                  <button className="primary" onClick={() => onChat(r)}>
                    <MessageSquare size={15} />
                    Chat about this
                  </button>
                </div>
              </article>
            ))}
          </div>
          {project && (
            <section className="workspace-card project-detail">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">PROJECT MATERIALS</span>
                  <h2>{project.name}</h2>
                </div>
                <button className="primary" onClick={() => onChat(project)}>
                  <MessageSquare size={16} />
                  Chat about {project.name}
                </button>
              </div>
              <p>{project.description}</p>
              <p className="subtle">
                Linked subjects:{" "}
                {project.subjects.map((s) => s.name).join(", ") || "None yet"}
              </p>
              <div className="form-actions">
                <button
                  disabled={busy}
                  onClick={() => {
                    setEditing(project.id);
                    setDraft({
                      name: project.name,
                      description: project.description,
                      subject_ids: project.subject_ids,
                    });
                  }}
                >
                  Edit project or subjects
                </button>
                <button
                  disabled={busy}
                  onClick={() => {
                    if (
                      confirm(
                        `Delete ${project.name} and its materials? Earlier chat messages remain in your history.`,
                      )
                    )
                      run(async () => {
                        await api(`/projects/${project.id}`, {
                          method: "DELETE",
                        });
                        setProject(null);
                        setMaterial(null);
                      });
                  }}
                >
                  Delete project
                </button>
              </div>
              <div className="project-add-grid">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    run(async () => {
                      setProject(
                        await post(`/projects/${project.id}/repository`, {
                          url: repo,
                        }),
                      );
                      setRepo("");
                    });
                  }}
                >
                  <label>
                    Public GitHub repository
                    <input
                      type="url"
                      required
                      value={repo}
                      onChange={(e) => setRepo(e.target.value)}
                      placeholder="https://github.com/owner/repository"
                    />
                  </label>
                  <button className="primary" disabled={busy}>
                    {busy ? "Working…" : "Add repository"}
                  </button>
                  <small>
                    Imports a snapshot of up to 12 readable source files and
                    README content. Nothing is executed.
                  </small>
                </form>
                <div>
                  <label className="file-drop">
                    Add documents or question papers
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.md"
                      disabled={busy}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        e.target.value = "";
                        if (file.size > 10 * 1024 * 1024) {
                          setError("Choose a file up to 10 MB.");
                          return;
                        }
                        run(async () => {
                          const body = new FormData();
                          body.append("file", file);
                          setProject(
                            await api(`/projects/${project.id}/documents`, {
                              method: "POST",
                              body,
                            }),
                          );
                        });
                      }}
                    />
                  </label>
                  <small>
                    Text is read directly; PDF/images are sent to Gemini. Review
                    recognized text below before relying on it.
                  </small>
                </div>
              </div>
              {project.materials.length ? (
                project.materials.map((m) => (
                  <article className="material-row" key={m.id}>
                    <div>
                      <strong>{m.name}</strong>
                      <small>
                        {m.kind} · {m.content.length.toLocaleString()}{" "}
                        characters · saved{" "}
                        {new Date(m.created_at * 1000).toLocaleDateString()}
                      </small>
                    </div>
                    <button
                      disabled={busy}
                      onClick={() => {
                        setMaterial(m);
                        setText(m.content);
                      }}
                    >
                      Review material
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => {
                        if (confirm(`Remove ${m.name} from this project?`))
                          run(async () => {
                            await api(`/project-materials/${m.id}`, {
                              method: "DELETE",
                            });
                            setProject(await api(`/projects/${project.id}`));
                            if (material?.id === m.id) setMaterial(null);
                          });
                      }}
                    >
                      Remove material
                    </button>
                  </article>
                ))
              ) : (
                <p className="empty-state">
                  Add a repository or document, or link a subject to give Orbit
                  project context.
                </p>
              )}
              {material && (
                <form
                  className="material-review"
                  onSubmit={(e) => {
                    e.preventDefault();
                    run(async () => {
                      await api(`/project-materials/${material.id}`, {
                        method: "PUT",
                        body: JSON.stringify({ content: text }),
                      });
                      setProject(await api(`/projects/${project.id}`));
                      setMaterial(null);
                    });
                  }}
                >
                  <label>
                    Review {material.name}
                    <textarea
                      rows={14}
                      required
                      maxLength={150000}
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                    />
                  </label>
                  <div className="form-actions">
                    <button className="primary" disabled={busy}>
                      Save reviewed material
                    </button>
                    <button type="button" onClick={() => setMaterial(null)}>
                      Close
                    </button>
                  </div>
                </form>
              )}
            </section>
          )}
        </>
      )}
    </>
  );
}
