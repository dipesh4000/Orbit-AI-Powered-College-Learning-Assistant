import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUp,
  ArrowRight,
  BookOpen,
  ChartNoAxesCombined,
  Check,
  ChevronRight,
  CircleHelp,
  GraduationCap,
  LoaderCircle,
  LogOut,
  Menu,
  MessageSquare,
  Plus,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import "./style.css";

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch("/api" + path, {
      credentials: "include",
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error(
      "Cannot reach Orbit. Check your connection and that the backend is running, then retry.",
    );
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "Orbit's backend is unavailable. Start the backend and retry.",
    );
  }
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Please check the entered values.",
    );
  return data;
}
const post = (path, data) =>
  api(path, { method: "POST", body: JSON.stringify(data) });
const pct = (value) =>
  value == null ? "Not available" : `${value.toFixed(1)}%`;
function Sources({ sources = [] }) {
  return (
    sources.length > 0 && (
      <details className="sources">
        <summary>
          {sources.length} demo course source{sources.length > 1 ? "s" : ""}
        </summary>
        {sources.map((s) => (
          <article key={s.id}>
            <strong>{s.source}</strong>
            <small>[{s.id}] · Authored demo material</small>
            <p>{s.text}</p>
          </article>
        ))}
      </details>
    )
  );
}
function ErrorBox({ message }) {
  return (
    message && (
      <div className="error" role="alert">
        <CircleHelp size={18} />
        <span>{message}</span>
      </div>
    )
  );
}
function Busy() {
  return (
    <span className="busy">
      <LoaderCircle size={16} className="spin" /> Working with your course data…
    </span>
  );
}

function App() {
  const [student, setStudent] = useState(null),
    [students, setStudents] = useState([]),
    [view, setView] = useState("Chat"),
    [open, setOpen] = useState(false);
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [health, setHealth] = useState(null),
    [messages, setMessages] = useState([]);
  const [dashboard, setDashboard] = useState(null),
    [courses, setCourses] = useState([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false);
  const end = useRef(null),
    inputRef = useRef(null);
  async function initialize() {
    setError("");
    setLoading(true);
    try {
      setHealth(await api("/health"));
      setStudents(await api("/students"));
      try {
        const s = await api("/session");
        setStudent(s);
        setMessages(s.history || []);
      } catch {
        setStudent(null);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    initialize();
  }, []);
  useEffect(() => {
    let active = true;
    if (student) {
      Promise.all([api("/dashboard"), api("/courses")])
        .then(([d, c]) => {
          if (active) {
            setDashboard(d);
            setCourses(c);
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    }
    return () => {
      active = false;
    };
  }, [student?.user_id]);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);
  async function selectStudent(user_id) {
    setBusy(true);
    setError("");
    try {
      const s = await post("/session", { user_id });
      setStudent(s);
      setMessages([]);
      setDashboard(null);
      setCourses([]);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    if (busy) return;
    try {
      await api("/session", { method: "DELETE" });
      setStudent(null);
      setMessages([]);
      setDashboard(null);
      setCourses([]);
      setView("Chat");
    } catch (e) {
      setError(e.message);
    }
  }
  async function newChat() {
    if (busy) return;
    try {
      await api("/conversation", { method: "DELETE" });
      setMessages([]);
      setInput("");
      setView("Chat");
      setOpen(false);
    } catch (e) {
      setError(e.message);
    }
  }
  async function send(e) {
    e.preventDefault();
    if (busy || !input.trim()) return;
    const question = input.trim();
    setInput("");
    setError("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setBusy(true);
    try {
      const r = await post("/chat", { message: question });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: r.answer,
          sources: r.sources,
          tools: r.tools_called,
          cache: r.cache_hits,
        },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: e.message, isError: true },
      ]);
    } finally {
      setBusy(false);
    }
  }
  const prompt = (text) => {
    setView("Chat");
    setInput(text);
    setOpen(false);
    setTimeout(() => inputRef.current?.focus(), 50);
  };
  if (!student)
    return (
      <div className="login">
        <div className="login-card">
          <div className="brand">
            <span className="brand-icon">✳</span> orbit
            <span className="tiny">LEARNING SPACE</span>
          </div>
          <div className="eyebrow">A LITTLE FOCUS. A LOT OF POSSIBILITY.</div>
          <h1>
            Your next step
            <br />
            starts here.
          </h1>
          <p className="muted">
            Choose a student to explore their courses, find areas to focus on,
            and turn learning into practice.
          </p>
          <div className="demo-label">
            Demo student selection · no authentication
          </div>
          <ErrorBox message={error} />
          {loading ? (
            <Busy />
          ) : students.length ? (
            <div className="student-list">
              {students.map((s) => (
                <button
                  key={s.user_id}
                  disabled={busy}
                  onClick={() => selectStudent(s.user_id)}
                >
                  <span className="avatar">{s.label.split(" ")[1]}</span>
                  <span>
                    <strong>{s.label}</strong>
                    <small>{s.rationale}</small>
                    <code>{s.user_id}</code>
                  </span>
                  <ArrowRight size={18} />
                </button>
              ))}
            </div>
          ) : (
            <div className="setup-note">
              <strong>Connect your workspace</strong>
              <p>
                Configure <code>backend/.env</code>, then import the supplied
                CSVs. The student picker will populate from real records.
              </p>
              <button onClick={initialize}>Check connection</button>
            </div>
          )}
          <p className="fine">
            Demo marks, rules, and learning materials are labeled throughout.
            Student records come from the supplied dataset.
          </p>
        </div>
      </div>
    );
  return (
    <div className="app">
      <button
        className={"scrim " + (open ? "visible" : "")}
        aria-label="Close navigation"
        onClick={() => setOpen(false)}
      />
      <aside className={"sidebar " + (open ? "open" : "")}>
        <div className="brand">
          <span className="brand-icon">✳</span> orbit
          <span className="tiny">STUDENT</span>
        </div>
        <button className="new-chat" onClick={newChat} disabled={busy}>
          <Plus size={17} /> New conversation
        </button>
        <div>
          <div className="nav-label">YOUR WORKSPACE</div>
          <nav>
            {[
              [MessageSquare, "Chat"],
              [ChartNoAxesCombined, "Dashboard"],
              [BookOpen, "Practice"],
            ].map(([Icon, name]) => (
              <button
                key={name}
                className={view === name ? "active" : ""}
                onClick={() => {
                  setView(name);
                  setOpen(false);
                }}
              >
                <Icon size={18} />
                {name}
                {view === name && <span className="nav-dot" />}
              </button>
            ))}
          </nav>
        </div>
        <div className="examples">
          <div className="nav-label">TRY A CONVERSATION</div>
          {[
            "What topics should I focus on?",
            "How am I doing in my courses?",
            "Which assessments can I take?",
          ].map((p) => (
            <button key={p} onClick={() => prompt(p)}>
              {p}
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="learning-note">
            <Sparkles size={18} />
            <p>
              Small steps,
              <br />
              <strong>lasting progress.</strong>
            </p>
          </div>
          <div className="profile">
            <span className="avatar">{student.label.split(" ")[1]}</span>
            <div>
              <strong>{student.label}</strong>
              <small>Demo workspace</small>
            </div>
            <button
              aria-label="Switch student"
              title="Switch student"
              onClick={logout}
              disabled={busy}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <div className="breadcrumb">
            <button
              className="mobile-menu"
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <span>My workspace</span>
            <ChevronRight size={14} />
            <strong>{view}</strong>
          </div>
          <span className="status-dot">Personal learning space</span>
        </header>
        <ErrorBox message={error} />
        {view === "Chat" && (
          <section
            className={"chat " + (messages.length ? "has-messages" : "")}
          >
            <div className="welcome">
              <div className="spark-tile">
                <Sparkles size={28} />
              </div>
              <div className="eyebrow">MAKE ROOM FOR YOUR NEXT IDEA</div>
              <h1>What will you learn today?</h1>
              <p>
                Your courses, your progress, and a little guidance along the
                way.
              </p>
            </div>
            <div className="messages" aria-live="polite">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={"message " + m.role + (m.isError ? " failed" : "")}
                >
                  <small>{m.role === "user" ? "YOU" : "✳ ORBIT"}</small>
                  <div>{m.content}</div>
                  <Sources sources={m.sources} />
                  {m.tools?.length > 0 && (
                    <details className="trace">
                      <summary>
                        Used {m.tools.length} tools
                        {m.cache ? ` · ${m.cache} cached lookups` : ""}
                      </summary>
                      {m.tools.join(" → ")}
                    </details>
                  )}
                </div>
              ))}
              {busy && <Busy />}
              <div ref={end} />
            </div>
            <form className="composer" onSubmit={send}>
              <textarea
                ref={inputRef}
                aria-label="Ask Orbit"
                placeholder="Ask about a concept, your progress, or what to study next…"
                maxLength={2000}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    send(e);
                  }
                }}
              />
              <div className="composer-footer">
                <span>
                  <span className="small-dot" /> Your learning context
                </span>
                <button
                  className="send"
                  disabled={busy || !input.trim()}
                  aria-label="Send message"
                >
                  <ArrowUp size={22} />
                </button>
              </div>
            </form>
            {!messages.length && (
              <div className="suggestions">
                {[
                  [
                    BookOpen,
                    "Understand a concept",
                    "Make the complicated feel simple.",
                    "Explain a topic from one of my courses.",
                  ],
                  [
                    Target,
                    "Find my focus",
                    "See where a little practice can help.",
                    "What topics am I weak in?",
                  ],
                  [
                    Sparkles,
                    "Put it into practice",
                    "Build confidence, one question at a time.",
                    "Help me choose a course for practice.",
                  ],
                ].map(([Icon, title, sub, p]) => (
                  <button key={title} onClick={() => prompt(p)}>
                    <Icon size={20} />
                    <strong>{title}</strong>
                    <small>{sub}</small>
                  </button>
                ))}
              </div>
            )}
            <p className="fine centered">
              Grounded in your records and labeled demo course materials.
              Missing information stays missing.
            </p>
          </section>
        )}
        {view === "Dashboard" && (
          <Dashboard data={dashboard} onPractice={() => setView("Practice")} />
        )}{" "}
        {view === "Practice" && (
          <Practice courses={courses} studentId={student.user_id} />
        )}
      </main>
    </div>
  );
}

function Dashboard({ data, onPractice }) {
  const [allCourses, setAllCourses] = useState(false);
  const [allTopics, setAllTopics] = useState(false);
  const [decision, setDecision] = useState(null),
    [error, setError] = useState(""),
    [checking, setChecking] = useState(false);
  async function check(id) {
    setChecking(true);
    setError("");
    try {
      setDecision(await api("/eligibility/" + encodeURIComponent(id)));
    } catch (e) {
      setError(e.message);
    } finally {
      setChecking(false);
    }
  }
  if (!data)
    return (
      <div className="content">
        <Busy />
      </div>
    );
  const scored = data.courses.filter((c) => c.performance_percent != null);
  return (
    <section className="content">
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR LEARNING, IN VIEW</div>
          <h1>A little perspective.</h1>
          <p className="muted">See where you are. Decide where to go next.</p>
        </div>
        <span className="pill">
          {data.cache_hit ? "Cached · up to 60s" : "Fresh data"}
        </span>
      </div>
      <div className="notice">{data.demo_notice}</div>
      <div className="stats">
        {[
          [
            "Enrolled courses",
            new Set(data.courses.map((c) => c.course_id)).size,
            "From your course records",
          ],
          ["Courses with scores", scored.length, "Missing scores are not zero"],
          ["Focus topics", data.weak_topics.length, "Below 60% of full marks"],
          ["Recent attempts", data.history.length, "Up to 30 recorded rounds"],
        ].map(([label, value, note]) => (
          <div className="stat" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{note}</small>
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        <article className="panel">
          <div className="panel-head">
            <h2>Course performance</h2>
            <span className="muted">MCQ scores</span>
          </div>
          {data.courses.length ? (
            data.courses.slice(0, allCourses ? undefined : 8).map((c) => (
              <div className="course" key={c.id}>
                <span className="course-icon">
                  <BookOpen size={17} />
                </span>
                <div>
                  <strong>{c.title}</strong>
                  <small>{c.subject}</small>
                  <div className="course-metrics">
                    <span>Score: {pct(c.performance_percent)}</span>
                    <span>Progress: {pct(c.progress_percent)}</span>
                  </div>
                  {c.progress_percent != null && (
                    <progress
                      max="100"
                      value={c.progress_percent}
                      aria-label={`${c.title} demo engagement progress`}
                    />
                  )}
                  <details>
                    <summary>How this is calculated</summary>
                    <p>
                      {c.score_basis}. {c.progress_basis}.
                    </p>
                    {c.multiple_source_rows && (
                      <p>
                        Multiple source rows exist; eligibility requires
                        reconciliation.
                      </p>
                    )}
                  </details>
                </div>
              </div>
            ))
          ) : (
            <p className="muted">No enrolled courses in the supplied data.</p>
          )}
          {data.courses.length > 8 && (
            <button className="full" onClick={() => setAllCourses(!allCourses)}>
              {allCourses
                ? "Show fewer courses"
                : `View all ${data.courses.length} course records`}
            </button>
          )}
        </article>
        <article className="panel focus-panel">
          <div className="panel-head">
            <h2>Your next focus</h2>
            <Target size={19} />
          </div>
          <p className="muted">
            Topics where practice could make a difference.
          </p>
          {data.weak_topics.length ? (
            data.weak_topics.slice(0, allTopics ? undefined : 8).map((t) => (
              <div className="weak" key={t.skill + t.topic}>
                <strong>{t.topic}</strong>
                <small>
                  {t.skill} · {t.question_count} question records
                </small>
                <span>{pct(t.score_percent)}</span>
              </div>
            ))
          ) : (
            <p className="empty">
              No weak topics identified in available scored history.
            </p>
          )}
          {data.weak_topics.length > 8 && (
            <button className="full" onClick={() => setAllTopics(!allTopics)}>
              {allTopics ? "Show fewer topics" : "View all focus topics"}
            </button>
          )}
          <button className="primary full" onClick={onPractice}>
            Make time for practice <ArrowRight size={16} />
          </button>
        </article>
      </div>
      <article className="panel">
        <div className="panel-head">
          <h2>Assessment history</h2>
          <span className="pill">Supplied hackathon records</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Hackathon / round</th>
                <th>Attempt</th>
                <th>Score</th>
                <th>Pending review</th>
                <th>Last submission</th>
              </tr>
            </thead>
            <tbody>
              {data.history.map((h, i) => (
                <tr key={i}>
                  <td>
                    {h.hackathon_id} / {h.round_id}
                  </td>
                  <td>{h.attempt_id || "Unknown"}</td>
                  <td>
                    {pct(h.score_percent)}
                    <small>
                      {h.obtained} / {h.maximum}
                    </small>
                  </td>
                  <td>{h.pending_questions}</td>
                  <td>{h.submitted_at?.slice(0, 10) || "Unavailable"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data.history.length && (
            <p className="empty">No assessment history available.</p>
          )}
        </div>
      </article>
      <article className="panel eligibility">
        <h2>Ready for an assessment?</h2>
        <p className="muted">
          New demo assessments use configured rules. Supplied hackathon attempts
          are not counted against unrelated demo assessments.
        </p>
        <label htmlFor="assessment">Choose a demo assessment</label>
        <select
          id="assessment"
          defaultValue=""
          disabled={checking}
          onChange={(e) => e.target.value && check(e.target.value)}
        >
          <option value="" disabled>
            Select assessment…
          </option>
          {data.assessments.map((a) => (
            <option key={a.assessment_id} value={a.assessment_id}>
              {a.title}
            </option>
          ))}
        </select>
        {checking && <Busy />}
        <ErrorBox message={error} />
        {decision && (
          <div className="decision" role="status">
            <strong>{decision.status.toUpperCase()}</strong>
            <p>{decision.reason}</p>
          </div>
        )}
      </article>
    </section>
  );
}

function Practice({ courses, studentId }) {
  const [course, setCourse] = useState(""),
    [topics, setTopics] = useState([]),
    [topic, setTopic] = useState(""),
    [difficulty, setDifficulty] = useState("foundation"),
    [count, setCount] = useState(5);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState(null),
    [revealed, setRevealed] = useState({}),
    [answers, setAnswers] = useState({}),
    [loadingTopics, setLoadingTopics] = useState(false);
  useEffect(() => {
    if (courses.length && !course) setCourse(courses[0].course_id);
  }, [courses]);
  useEffect(() => {
    let active = true;
    setTopic("");
    setTopics([]);
    setResult(null);
    setError("");
    if (course) {
      setLoadingTopics(true);
      api("/topics/" + encodeURIComponent(course))
        .then((t) => {
          if (active) {
            setTopics(t);
            setTopic(t[0] || "");
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        })
        .finally(() => {
          if (active) setLoadingTopics(false);
        });
    }
    return () => {
      active = false;
    };
  }, [course]);
  async function generate(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    setRevealed({});
    setAnswers({});
    try {
      const r = await post("/practice", {
        course_id: course,
        topic,
        difficulty,
        count: Number(count),
      });
      setResult(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="content practice">
      <div className="page-heading">
        <div>
          <div className="eyebrow">KNOWLEDGE INTO CONFIDENCE</div>
          <h1>Make it stick.</h1>
          <p className="muted">
            A focused practice session, built around what you're learning.
          </p>
        </div>
      </div>
      <div className="practice-banner">
        <Sparkles size={32} />
        <div>
          <h2>A little practice goes a long way.</h2>
          <p>
            Questions use authored demo materials linked to your course subject.
            Every answer includes an explanation and source.
          </p>
        </div>
      </div>
      <form className="panel" onSubmit={generate}>
        <div className="practice-fields">
          <label>
            Course
            <select
              value={course}
              onChange={(e) => setCourse(e.target.value)}
              disabled={busy}
            >
              <option value="">Choose a course</option>
              {courses.map((c) => (
                <option key={c.course_id} value={c.course_id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Topic
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={busy || loadingTopics}
            >
              <option value="">
                {loadingTopics
                  ? "Loading topics…"
                  : "No demo material for this course"}
              </option>
              {topics.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>
            Difficulty
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              disabled={busy}
            >
              {["foundation", "intermediate", "advanced"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>
            Questions
            <select
              value={count}
              onChange={(e) => setCount(e.target.value)}
              disabled={busy}
            >
              {[1, 3, 5, 10].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="setup-footer">
          <span className="fine">
            Demo material · Four options · Source-checked output
          </span>
          <button className="primary" disabled={busy || !topic || !course}>
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Sparkles size={17} />
            )}{" "}
            Generate practice
          </button>
        </div>
      </form>
      <ErrorBox message={error} />
      {busy && <Busy />}
      {result?.message && <div className="notice">{result.message}</div>}
      {result?.questions.map((q, i) => (
        <article className="panel question" key={i}>
          <div className="eyebrow">
            QUESTION {i + 1} OF {result.questions.length}
          </div>
          <h2>{q.question}</h2>
          <div className="options">
            {q.options.map((o, j) => (
              <button
                disabled={revealed[i]}
                aria-pressed={answers[i] === o}
                className={
                  (answers[i] === o ? "selected " : "") +
                  (revealed[i] && q.correct_answer === o ? "correct" : "")
                }
                key={o}
                onClick={() => setAnswers((a) => ({ ...a, [i]: o }))}
              >
                <span>{String.fromCharCode(65 + j)}</span>
                {o}
                {revealed[i] && q.correct_answer === o && <Check size={18} />}
              </button>
            ))}
          </div>
          {revealed[i] ? (
            <div className="explanation">
              <strong>
                {answers[i] === q.correct_answer ? "Correct." : "Keep going."}{" "}
                Answer: {q.correct_answer}
              </strong>
              <p>{q.explanation}</p>
              <small>Source: [{q.source_reference}] · Demo material</small>
            </div>
          ) : (
            <button onClick={() => setRevealed((r) => ({ ...r, [i]: true }))}>
              Reveal answer & explanation
            </button>
          )}
        </article>
      ))}
      <Sources sources={result?.sources} />
    </section>
  );
}

createRoot(document.getElementById("root")).render(<App />);
