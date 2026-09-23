import { useEffect, useState } from "react";
import { api, post } from "./api";
import { ProfileFields } from "./AcademicDashboard";

const fields = {
  subjects: [
    ["name", "Subject name"],
    ["code", "Subject code"],
    ["semester", "Semester"],
    ["syllabus", "Syllabus", "textarea"],
  ],
  semesters: [
    ["semester", "Semester"],
    ["sgpa", "Reported SGPA", "number"],
  ],
  marks: [
    ["subject_code", "Subject code"],
    ["semester", "Semester"],
    ["title", "Assessment title"],
    ["score", "Score", "number"],
    ["max_score", "Maximum score", "number"],
    ["assessed_on", "Assessment date", "date"],
    ["kind", "Assessment type", "select"],
  ],
};
export default function AcademicImport({ onSaved }) {
  const [rows, setRows] = useState([]),
    [selected, setSelected] = useState(null),
    [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const c = new AbortController();
    let timer;
    async function load() {
      try {
        const r = await api("/academics/imports", { signal: c.signal });
        setRows(r);
        if (r.some((x) => x.status === "processing"))
          timer = setTimeout(load, 2000);
      } catch (e) {
        if (!c.signal.aborted) setError(e.message);
      }
    }
    load();
    return () => {
      c.abort();
      clearTimeout(timer);
    };
  }, [version]);
  async function run(work) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function cell(group, index, key, value) {
    setDraft((d) => ({
      ...d,
      [group]: d[group].map((r, i) =>
        i === index ? { ...r, [key]: value } : r,
      ),
    }));
  }
  return (
    <section className="workspace-card academic-import">
      <h2>Import academic records</h2>
      <p>
        Upload your result sheet or syllabus. Gemini reads the image or PDF; you
        review and correct everything before saving. Missing values stay blank.
      </p>
      <label className="file-drop">
        Choose image, PDF or text (up to 10 MB)
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
              await api("/academics/imports", { method: "POST", body });
              setNotice(
                "Uploaded. Recognition is running; you can keep using the workspace.",
              );
            });
          }}
        />
      </label>
      <small>Your selected file is sent to Gemini for recognition.</small>
      {error && (
        <p className="error" role="alert">
          {error}{" "}
          <button onClick={() => setVersion((v) => v + 1)}>
            Reload imports
          </button>
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <div className="import-list">
        {rows.map((r) => (
          <article key={r.id}>
            <div>
              <strong>{r.filename}</strong>
              <small>
                {r.status === "review"
                  ? "Ready to review"
                  : r.status === "saved"
                    ? "Saved to dashboard"
                    : r.status === "processing"
                      ? "Recognizing…"
                      : "Recognition failed"}
              </small>
              {r.error && <p>{r.error}</p>}
            </div>
            {r.status === "review" && (
              <button
                disabled={busy}
                onClick={() => {
                  setSelected(r.id);
                  setDraft(structuredClone(r.draft));
                }}
              >
                Review extracted data
              </button>
            )}
            {r.retryable && (
              <button
                disabled={busy}
                onClick={() =>
                  run(() => post(`/academics/imports/${r.id}/retry`, {}))
                }
              >
                Retry recognition
              </button>
            )}
            <button
              disabled={busy}
              onClick={() => {
                if (
                  confirm(
                    "Remove this uploaded file and its extraction? Saved academic records remain.",
                  )
                )
                  run(async () => {
                    await api(`/academics/imports/${r.id}`, {
                      method: "DELETE",
                    });
                    if (selected === r.id) {
                      setSelected(null);
                      setDraft(null);
                    }
                  });
              }}
            >
              Remove upload
            </button>
          </article>
        ))}
      </div>
      {draft && (
        <form
          className="import-review"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await api(`/academics/imports/${selected}/confirm`, {
                method: "PUT",
                body: JSON.stringify(draft),
              });
              setDraft(null);
              setSelected(null);
              setNotice("Reviewed records saved to your dashboard.");
              onSaved();
            });
          }}
        >
          <fieldset disabled={busy}>
            <h3>Check the extracted records</h3>
            <p>
              Fill missing subject codes, semesters and assessment dates, or
              remove incomplete rows. Matching subjects and semester results are
              updated; marks are added once for this upload.
            </p>
            {draft.profile && (
              <>
                <h3>Academic details</h3>
                <ProfileFields
                  value={draft.profile}
                  onChange={(p) => setDraft((d) => ({ ...d, profile: p }))}
                />
                <button
                  type="button"
                  onClick={() => setDraft((d) => ({ ...d, profile: null }))}
                >
                  Exclude academic details
                </button>
              </>
            )}
            {Object.entries(fields).map(([group, columns]) => (
              <section key={group}>
                <h3>
                  {group === "semesters"
                    ? "Semester results"
                    : group === "subjects"
                      ? "Subjects & syllabus"
                      : "Marks"}{" "}
                  ({draft[group]?.length || 0})
                </h3>
                {draft[group]?.map((row, i) => (
                  <div className="import-review-row" key={i}>
                    <div className="form-grid">
                      {columns.map(([key, label, type = "text"]) => (
                        <label key={key}>
                          {label}
                          {type === "textarea" ? (
                            <textarea
                              value={row[key] ?? ""}
                              rows={3}
                              onChange={(e) =>
                                cell(group, i, key, e.target.value)
                              }
                            />
                          ) : type === "select" ? (
                            <select
                              value={row[key]}
                              onChange={(e) =>
                                cell(group, i, key, e.target.value)
                              }
                            >
                              {[
                                "quiz",
                                "midterm",
                                "final",
                                "assignment",
                                "lab",
                              ].map((v) => (
                                <option key={v}>{v}</option>
                              ))}
                            </select>
                          ) : (
                            <input
                              type={type}
                              step="any"
                              value={row[key] ?? ""}
                              onChange={(e) =>
                                cell(
                                  group,
                                  i,
                                  key,
                                  type === "number"
                                    ? e.target.value === ""
                                      ? null
                                      : Number(e.target.value)
                                    : type === "date"
                                      ? e.target.value || null
                                      : e.target.value,
                                )
                              }
                            />
                          )}
                        </label>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setDraft((d) => ({
                          ...d,
                          [group]: d[group].filter((_, j) => i !== j),
                        }))
                      }
                    >
                      Remove row
                    </button>
                  </div>
                ))}
              </section>
            ))}
            <div className="form-actions">
              <button className="primary">Confirm and save records</button>
              <button type="button" onClick={() => setDraft(null)}>
                Close review
              </button>
            </div>
          </fieldset>
        </form>
      )}
    </section>
  );
}
