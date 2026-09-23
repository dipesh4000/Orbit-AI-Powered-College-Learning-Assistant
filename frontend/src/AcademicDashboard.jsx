import { useEffect, useState } from "react";
import { BookOpen, Plus, Upload } from "lucide-react";
import { api, post } from "./api";
import RecordWorkspace from "./RecordWorkspace";
import AcademicImport from "./AcademicImport";
import Suggestions from "./Suggestions";

const defaults = {
  program: "",
  current_semester: "",
  total_credits: null,
  target_sgpa: null,
  sgpa_scale: 10,
};
export function ProfileFields({ value, onChange }) {
  return (
    <div className="form-grid">
      {[
        ["program", "Program", "text"],
        ["current_semester", "Current semester", "text"],
        ["total_credits", "Total credits obtained", "number"],
        ["target_sgpa", "Target SGPA", "number"],
        ["sgpa_scale", "SGPA scale", "number"],
      ].map(([key, label, type]) => (
        <label key={key}>
          {label}
          <input
            type={type}
            min={type === "number" ? 0 : undefined}
            step="any"
            value={value[key] ?? ""}
            onChange={(e) =>
              onChange({
                ...value,
                [key]:
                  type === "number"
                    ? e.target.value === ""
                      ? null
                      : Number(e.target.value)
                    : e.target.value,
              })
            }
          />
        </label>
      ))}
    </div>
  );
}

function SgpaChart({ rows, scale }) {
  if (!rows.length)
    return (
      <div className="academic-chart-empty">
        <span className="chart-ghost">↗</span>
        <p>Your semester story starts here.</p>
        <small>Add a reported SGPA to see your progress.</small>
      </div>
    );
  const x = (i) => 42 + (i * 420) / Math.max(rows.length - 1, 1),
    y = (n) => 190 - (n / scale) * 150;
  return (
    <>
      <svg
        className="sgpa-chart"
        viewBox="0 0 510 232"
        role="img"
        aria-label="Reported SGPA by semester"
      >
        {[0, scale / 2, scale].map((n) => (
          <g key={n}>
            <line x1="40" x2="485" y1={y(n)} y2={y(n)} stroke="#e3e8df" />
            <text x="30" y={y(n) + 4} textAnchor="end">
              {n}
            </text>
          </g>
        ))}
        <polyline
          points={rows.map((r, i) => `${x(i)},${y(r.sgpa)}`).join(" ")}
          fill="none"
          stroke="#557c4d"
          strokeWidth="3"
        />
        {rows.map((r, i) => (
          <g key={r.id}>
            <circle cx={x(i)} cy={y(r.sgpa)} r="5" fill="#557c4d">
              <title>
                Semester {r.semester}: {r.sgpa}/{scale}
              </title>
            </circle>
            <text x={x(i)} y={y(r.sgpa) - 12} textAnchor="middle">
              {r.sgpa}
            </text>
            <text x={x(i)} y="216" textAnchor="middle">
              Sem {r.semester}
            </text>
          </g>
        ))}
      </svg>
      <p className="subtle">
        Reported values · scale {scale} · missing semesters are not zero.
      </p>
    </>
  );
}

export default function AcademicDashboard({ owner, subjects, onChanged }) {
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  const [version, setVersion] = useState(0),
    [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState(false),
    [profile, setProfile] = useState(defaults);
  const [semester, setSemester] = useState(""),
    [sgpa, setSgpa] = useState("");
  const [mode, setMode] = useState("overview"),
    [subject, setSubject] = useState(null),
    [syllabus, setSyllabus] = useState("");
  const refresh = () => {
    setVersion((v) => v + 1);
    onChanged();
  };
  useEffect(() => {
    const c = new AbortController();
    api("/academics", { signal: c.signal })
      .then((r) => {
        setData(r);
        setError("");
        setProfile(
          r.profile
            ? Object.fromEntries(
                Object.keys(defaults).map((k) => [k, r.profile[k]]),
              )
            : defaults,
        );
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [version]);
  async function run(work) {
    setBusy(true);
    setError("");
    try {
      await work();
      refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const current = data?.profile?.current_semester || "";
  const currentSubjects = subjects.filter(
    (s) => !current || s.semester === current,
  );
  return (
    <>
      <div className="workspace-intro">
        <div>
          <p className="eyebrow">YOUR ACADEMIC PICTURE</p>
          <h1>{data?.profile?.program || "Dashboard"}</h1>
          <p>
            {current
              ? `Semester ${current} · your subjects, syllabus and marks`
              : "Add your semester and academic records to get started."}
          </p>
        </div>
        <button
          className="primary"
          onClick={() => setMode(mode === "import" ? "overview" : "import")}
        >
          <Upload size={16} />
          Import image or PDF
        </button>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}{" "}
          <button onClick={() => setVersion((v) => v + 1)}>
            Retry dashboard
          </button>
        </p>
      )}
      {mode === "import" && <AcademicImport onSaved={refresh} />}
      <div className="academic-hero">
        <section className="workspace-card academic-summary">
          <span className="eyebrow">THIS SEMESTER, YOUR WAY</span>
          <div className="academic-numbers">
            <div>
              <span>Total credits obtained</span>
              <strong>{data?.profile?.total_credits ?? "—"}</strong>
              <small>
                {data?.profile?.total_credits == null
                  ? "Add your reported credits"
                  : "Reported total credits"}
              </small>
            </div>
            <div>
              <span>Target SGPA</span>
              <strong>{data?.profile?.target_sgpa ?? "—"}</strong>
              <small>
                {data?.profile?.target_sgpa == null
                  ? "Set a goal for the semester"
                  : `Out of ${data.profile.sgpa_scale}`}
              </small>
            </div>
          </div>
          <button onClick={() => setEdit(!edit)}>
            <Plus size={15} />
            {data?.profile ? "Edit academic details" : "Add academic details"}
          </button>
        </section>
        <section className="workspace-card">
          <div className="section-heading">
            <h2>SGPA over semesters</h2>
            <button onClick={() => setEdit(true)}>Add SGPA</button>
          </div>
          <SgpaChart
            rows={data?.semesters || []}
            scale={data?.profile?.sgpa_scale || 10}
          />
        </section>
      </div>
      {edit && (
        <section className="workspace-card">
          <h2>Academic details</h2>
          <p className="subtle">
            Enter values from your result sheet. SGPA is not calculated from
            marks.
          </p>
          <form
            className="record-form"
            onSubmit={(e) => {
              e.preventDefault();
              run(() =>
                api("/academics/profile", {
                  method: "PUT",
                  body: JSON.stringify(profile),
                }),
              );
            }}
          >
            <fieldset disabled={busy}>
              <ProfileFields value={profile} onChange={setProfile} />
              <button className="primary">Save academic details</button>
            </fieldset>
          </form>
          <form
            className="record-form"
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await post("/academics/semesters", {
                  semester,
                  sgpa: Number(sgpa),
                });
                setSemester("");
                setSgpa("");
              });
            }}
          >
            <fieldset disabled={busy}>
              <div className="form-grid">
                <label>
                  Result semester
                  <input
                    required
                    maxLength={40}
                    value={semester}
                    onChange={(e) => setSemester(e.target.value)}
                  />
                </label>
                <label>
                  Reported SGPA
                  <input
                    required
                    type="number"
                    step="any"
                    min="0"
                    max={data?.profile?.sgpa_scale || 10}
                    value={sgpa}
                    onChange={(e) => setSgpa(e.target.value)}
                  />
                </label>
              </div>
              <button className="primary">Save semester result</button>
            </fieldset>
          </form>
          <div className="semester-results">
            {data?.semesters.map((r) => (
              <div key={r.id}>
                <span>
                  Semester {r.semester}: <strong>{r.sgpa}</strong>
                </span>
                <button
                  disabled={busy}
                  onClick={() => {
                    setSemester(r.semester);
                    setSgpa(r.sgpa);
                  }}
                >
                  Edit
                </button>
                <button
                  disabled={busy}
                  onClick={() => {
                    if (confirm(`Remove semester ${r.semester} SGPA?`))
                      run(() =>
                        api(`/academics/semesters/${r.id}`, {
                          method: "DELETE",
                        }),
                      );
                  }}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
      <section className="workspace-card">
        <div className="section-heading">
          <div>
            <span className="eyebrow">YOUR CURRENT SUBJECTS</span>
            <h2>{current ? `Semester ${current}` : "Subjects & syllabus"}</h2>
          </div>
          <button onClick={() => setMode("records")}>
            <Plus size={15} />
            Add subjects or marks
          </button>
        </div>
        {currentSubjects.length ? (
          <div className="subject-tiles">
            {currentSubjects.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  setSubject(s);
                  setSyllabus(
                    data?.syllabi.find((r) => r.subject_id === s.id)?.content ||
                      "",
                  );
                }}
              >
                <BookOpen size={20} />
                <strong>{s.name}</strong>
                <small>
                  {s.code} · semester {s.semester}
                </small>
                <span>View syllabus & marks →</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            No subjects for this semester yet. Add subjects manually or import
            your syllabus.
          </div>
        )}
        {subject && (
          <div className="syllabus-editor">
            <h3>{subject.name}</h3>
            <p>
              {subject.latest
                ? `${subject.latest.title}: ${subject.latest.score}/${subject.latest.max_score} · ${subject.latest.assessed_on}`
                : "No marks saved yet."}
            </p>
            <label>
              Subject syllabus
              <textarea
                rows={7}
                value={syllabus}
                maxLength={100000}
                placeholder="Topics, modules and learning goals…"
                onChange={(e) => setSyllabus(e.target.value)}
              />
            </label>
            <div className="form-actions">
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  run(() =>
                    api(`/academics/syllabus/${subject.id}`, {
                      method: "PUT",
                      body: JSON.stringify({ content: syllabus }),
                    }),
                  )
                }
              >
                Save syllabus
              </button>
              <button onClick={() => setMode("records")}>Manage marks</button>
              <button onClick={() => setSubject(null)}>Close</button>
            </div>
          </div>
        )}
      </section>
      <div className="workspace-subtabs">
        <button
          aria-pressed={mode === "records"}
          onClick={() => setMode(mode === "records" ? "overview" : "records")}
        >
          Manage subjects & marks
        </button>
        <button
          aria-pressed={mode === "syllabus"}
          onClick={() => setMode(mode === "syllabus" ? "overview" : "syllabus")}
        >
          Overall syllabus
        </button>
        <button
          aria-pressed={mode === "actions"}
          onClick={() => setMode(mode === "actions" ? "overview" : "actions")}
        >
          Suggested actions
        </button>
      </div>
      {mode === "records" && (
        <RecordWorkspace
          key={version}
          owner={owner}
          initialSemester={current}
          onChanged={refresh}
        />
      )}
      {mode === "syllabus" && (
        <section className="workspace-card">
          <h2>Overall syllabus</h2>
          {data?.syllabi.length ? (
            data.syllabi.map((r) => (
              <details key={r.id}>
                <summary>
                  {subjects.find((s) => s.id === r.subject_id)?.name ||
                    "Subject"}
                </summary>
                <p className="preserve-lines">{r.content}</p>
              </details>
            ))
          ) : (
            <p className="empty-state">
              No syllabus yet. Open a subject to add its topics, or import your
              syllabus document.
            </p>
          )}
        </section>
      )}
      {mode === "actions" && <Suggestions />}
    </>
  );
}
