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
  PanelLeftClose,
  PanelLeftOpen,
  MessageSquare,
  Plus,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import "./style.css";
import ReactMarkdown from "react-markdown";
import SubjectChart from "./SubjectChart";

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
    [open, setOpen] = useState(false),
    [collapsed, setCollapsed] = useState(
      () => localStorage.getItem("orbit-sidebar") === "collapsed",
    );
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [health, setHealth] = useState(null),
    [messages, setMessages] = useState([]),
    [conversations, setConversations] = useState([]),
    [conversationId, setConversationId] = useState(null);
  const [dashboard, setDashboard] = useState(null),
    [courses, setCourses] = useState([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false);
  const end = useRef(null),
    inputRef = useRef(null),
    mainRef = useRef(null);
  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 });
  }, [view]);
  function toggleSidebar() {
    setCollapsed((value) => {
      localStorage.setItem("orbit-sidebar", value ? "expanded" : "collapsed");
      return !value;
    });
  }
  useEffect(() => {
    const close = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
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
        setConversationId(s.conversation_id || null);
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
      Promise.all([api("/dashboard"), api("/courses"), api("/conversations")])
        .then(([d, c, saved]) => {
          if (active) {
            setDashboard(d);
            setCourses(c);
            setConversations(saved);
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
      setConversations([]);
      setMessages([]);
      setConversationId(null);
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
      setConversations([]);
      setMessages([]);
      setConversationId(null);
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
      setConversationId(null);
      setInput("");
      setView("Chat");
      setOpen(false);
    } catch (e) {
      setError(e.message);
    }
  }
  async function openConversation(id) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const saved = await post(
        `/conversations/${encodeURIComponent(id)}/open`,
        {},
      );
      setMessages(saved.history);
      setConversationId(saved.conversation_id);
      setInput("");
      setView("Chat");
      setOpen(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
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
      setConversationId(r.conversation_id);
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
      api("/conversations")
        .then(setConversations)
        .catch(() =>
          setError(
            "Your reply is saved, but the history list could not refresh. Reload to retry.",
          ),
        );
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
          <div className="demo-info">
            <span className="demo-label">
              Demo student selection · no authentication
            </span>
            <span className="info-tooltip">
              <button
                type="button"
                aria-label="About the demo students"
                aria-describedby="student-info"
              >
                <CircleHelp size={16} />
              </button>
              <span role="tooltip" id="student-info">
                These test users are fetched from the supplied dataset to mimic
                a few prominent cases: recorded course scores, combined course
                and hackathon history, and missing course enrollment.
              </span>
            </span>
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
    <div className={"app " + (collapsed ? "sidebar-collapsed" : "")}>
      <button
        className={"scrim " + (open ? "visible" : "")}
        aria-label="Close navigation"
        onClick={() => setOpen(false)}
      />
      <aside
        id="workspace-navigation"
        className={"sidebar " + (open ? "open" : "")}
      >
        <button
          className="collapse-toggle"
          onClick={toggleSidebar}
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
        >
          <PanelLeftClose size={18} />
        </button>
        <button
          className="mobile-close"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        >
          <X size={18} />
        </button>
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
                aria-current={view === name ? "page" : undefined}
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
        <div className="conversation-history">
          <div className="nav-label">RECENT CHATS</div>
          {conversations.length ? (
            conversations.map((c) => (
              <button
                key={c.id}
                disabled={busy}
                title={c.title}
                className={conversationId === c.id ? "active" : ""}
                onClick={() => openConversation(c.id)}
              >
                <MessageSquare size={14} />
                <span>{c.title}</span>
              </button>
            ))
          ) : (
            <p className="history-empty">
              Your conversations will appear here.
            </p>
          )}
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
      <main ref={mainRef}>
        <header>
          <div className="breadcrumb">
            {collapsed && (
              <button
                className="expand-toggle"
                onClick={toggleSidebar}
                aria-label="Expand sidebar"
                title="Expand sidebar"
              >
                <PanelLeftOpen size={19} />
              </button>
            )}
            <button
              className="mobile-menu"
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
              aria-expanded={open}
              aria-controls="workspace-navigation"
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
                  <div className="message-body">
                    {m.role === "assistant" ? (
                      <ReactMarkdown>{m.content}</ReactMarkdown>
                    ) : (
                      m.content
                    )}
                  </div>
                  {m.isError && (
                    <button
                      className="retry-message"
                      onClick={() => prompt(messages[i - 1]?.content || "")}
                    >
                      Edit and retry
                    </button>
                  )}
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
                  <button
                    key={title}
                    onClick={() =>
                      title === "Put it into practice"
                        ? setView("Practice")
                        : prompt(p)
                    }
                  >
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
        <div hidden={view !== "Practice"}>
          <Practice key={student.user_id} courses={courses} health={health} />
        </div>
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
  const scored = (data.subjects || []).filter(
    (s) => s.marks_out_of_100 != null,
  );
  return (
    <section className="content">
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR LEARNING, IN VIEW</div>
          <h1>Your learning overview</h1>
          <p className="muted">Track your courses and find your next focus.</p>
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
          [
            "Subjects with marks",
            scored.length,
            "Recorded scores on a 100-point scale",
          ],
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
      <SubjectChart subjects={data.subjects || []} />
      <div className="dashboard-grid">
        <article className="panel">
          <div className="panel-head">
            <h2>Course progress</h2>
            <span className="muted">Recorded activity</span>
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
                    <span>
                      {c.performance_percent == null
                        ? "Course marks not recorded"
                        : `Marks: ${c.performance_percent.toFixed(1)} / 100`}
                    </span>
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

function Practice({ courses, health }) {
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
    if (courses.length && !course)
      setCourse(
        (courses.find((c) => c.practice_topics?.length) || courses[0])
          .course_id,
      );
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
    if (busy || loadingTopics || !course || !topic) return;
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
          <h1>Create a quiz</h1>
          <p className="muted">
            Choose a topic. Let AI build your next practice session.
          </p>
        </div>
      </div>
      <div className="practice-banner">
        <Sparkles size={32} />
        <div>
          <h2>Made for what you’re learning.</h2>
          <p>
            AI creates original questions from the demo materials linked to your
            course. Every answer includes an explanation and source.
          </p>
        </div>
      </div>
      <form className="panel quiz-setup" onSubmit={generate}>
        <div className="panel-head">
          <h2>
            <Sparkles size={17} /> Create with AI
          </h2>
          <span className="pill">Personalized practice</span>
        </div>
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
                  {c.practice_topics?.length === 0 ? " (no materials)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Topic
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={busy || loadingTopics || !topics.length}
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
        {!loadingTopics && course && !topics.length && !error && (
          <div className="notice">
            No learning materials are available for this course yet. Choose
            another course to create a grounded quiz.
          </div>
        )}
        {health && !health.model_configured && (
          <div className="notice">
            AI is not connected yet. Configure the model and API key in
            backend/.env, then refresh this page.
          </div>
        )}
        <details className="generation-rules">
          <summary>How your quiz is created</summary>
          <p>
            Questions stay within the selected course materials and match your
            difficulty. Each question has four distinct choices, one correct
            answer, a source, and an explanation. We validate the format and
            source references before showing your quiz.
          </p>
        </details>
        <div className="setup-footer">
          <span className="fine">Demo course material · Answers included</span>
          <button
            className="primary"
            disabled={
              busy ||
              loadingTopics ||
              !topic ||
              !course ||
              health?.model_configured === false
            }
          >
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Sparkles size={17} />
            )}{" "}
            {busy ? "Creating your quiz…" : "Generate quiz"}
          </button>
        </div>
      </form>
      <ErrorBox message={error} />
      {busy && (
        <div className="notice" role="status">
          <Busy />
          Creating questions and checking their format and sources. This may
          take a minute.
        </div>
      )}
      {result?.questions?.length > 0 && (
        <div className="quiz-progress" role="status">
          <div>
            <strong>Your quiz is ready</strong>
            <small>
              {Object.keys(answers).length} of {result.questions.length}{" "}
              answered · {Object.keys(revealed).length} reviewed
            </small>
          </div>
          {Object.keys(revealed).length === result.questions.length && (
            <span className="pill">
              {
                result.questions.filter(
                  (q, i) => answers[i] === q.correct_answer,
                ).length
              }{" "}
              / {result.questions.length} correct
            </span>
          )}
        </div>
      )}
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
            <button
              disabled={!answers[i]}
              onClick={() => setRevealed((r) => ({ ...r, [i]: true }))}
            >
              Check answer
            </button>
          )}
        </article>
      ))}
      <Sources sources={result?.sources} />
    </section>
  );
}

createRoot(document.getElementById("root")).render(<App />);
