import { useEffect, useState } from "react";
import { ArrowUpRight, Code2, Github, RefreshCw } from "lucide-react";
import { api, post } from "./api";
import "./coding-dashboard.css";

const number = (value) =>
  value == null ? "—" : Number(value).toLocaleString();
const label = (value) =>
  String(value)
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
const when = (stamp) =>
  stamp ? new Date(stamp * 1000).toLocaleString() : "Never";
const metrics = [
  ["solved", "Questions solved"],
  ["active_days", "Active days"],
  ["contributions", "GitHub contributions"],
  ["github_active_days", "GitHub active days"],
  ["commits", "Commits"],
  ["pull_requests", "Pull requests"],
  ["stars", "Stars"],
  ["issues", "Issues"],
];

function Detail({ name, value, depth = 0 }) {
  if (value == null || value === "" || depth > 5) return null;
  if (Array.isArray(value))
    return value.length ? (
      value.length > 12 ? (
        <details className="cd-group cd-array">
          <summary>
            {label(name)} · {value.length}
          </summary>
          <div className="cd-detail-grid">
            {value.map((item, index) => (
              <Detail
                key={index}
                name={item?.name || item?.title || `${index + 1}`}
                value={item}
                depth={depth + 1}
              />
            ))}
          </div>
        </details>
      ) : (
        <div className="cd-group">
          <h4>{label(name)}</h4>
          <div className="cd-detail-grid">
            {value.map((item, index) => (
              <Detail
                key={index}
                name={item?.name || item?.title || `${index + 1}`}
                value={item}
                depth={depth + 1}
              />
            ))}
          </div>
        </div>
      )
    ) : null;
  if (typeof value === "object")
    return (
      <div className="cd-group">
        <h4>{label(name)}</h4>
        <div className="cd-detail-grid">
          {Object.entries(value).map(([key, item]) => (
            <Detail key={key} name={key} value={item} depth={depth + 1} />
          ))}
        </div>
      </div>
    );
  return (
    <div className="cd-detail">
      <span>{label(name)}</span>
      <strong>
        {typeof value === "number" ? number(value) : String(value)}
      </strong>
    </div>
  );
}

function ActivityCalendar({ snapshot, problem = false }) {
  const activity =
    (problem
      ? snapshot.normalized.problem_activity
      : snapshot.normalized.activity) || [];
  if (!activity.length)
    return (
      <p className="cd-muted">
        Daily activity data is unavailable in this snapshot.
      </p>
    );
  const end = new Date(snapshot.fetched_at * 1000);
  end.setUTCHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - 364);
  const values = new Map(activity.map(({ date, count }) => [date, count]));
  const max = Math.max(1, ...activity.map(({ count }) => count));
  return (
    <>
      <div
        className="cd-calendar-scroll"
        role="region"
        aria-label={
          problem
            ? "Daily problem solving activity"
            : "Daily GitHub contributions"
        }
        tabIndex={0}
      >
        <div className="cd-calendar">
          {Array.from({ length: 365 }, (_, index) => {
            const day = new Date(start);
            day.setUTCDate(start.getUTCDate() + index);
            const date = day.toISOString().slice(0, 10),
              value = values.get(date);
            const level =
              value == null
                ? "unknown"
                : value === 0
                  ? 0
                  : Math.min(4, Math.ceil((value / max) * 4));
            return (
              <span
                className={`cd-day cd-level-${level}`}
                key={date}
                title={`${date}: ${value == null ? "not reported" : `${value} ${problem ? "submissions" : "contributions"}`}`}
                aria-label={`${date}: ${value == null ? "not reported" : `${value} ${problem ? "submissions" : "contributions"}`}`}
              />
            );
          })}
        </div>
      </div>
      <p className="cd-muted">
        365 days ending {end.toISOString().slice(0, 10)} · UTC
      </p>
    </>
  );
}

function difficultyOf(value, depth = 0) {
  if (!value || typeof value !== "object" || depth > 5) return null;
  const entries = Object.entries(value);
  const group = ["easy", "medium", "hard"].map(
    (name) =>
      entries.find(
        ([key, item]) => key.toLowerCase() === name && typeof item === "number",
      )?.[1],
  );
  if (group.some((item) => item != null)) return group.map((item) => item || 0);
  for (const [, child] of entries) {
    const found = difficultyOf(child, depth + 1);
    if (found) return found;
  }
  return null;
}

export default function CodingDashboard({
  hackathonCount = null,
  demoMode = false,
}) {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [source, setSource] = useState("codolio"),
    [view, setView] = useState("Problem solving");
  const [handle, setHandle] = useState(""),
    [manual, setManual] = useState(null),
    [busy, setBusy] = useState(false),
    [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api("/coding", { signal: controller.signal })
      .then((result) => {
        setData(result);
        setError("");
        if (
          !result.latest.codolio &&
          !result.connection &&
          result.latest.manual
        )
          setSource("manual");
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [attempt]);
  const refreshing =
    data?.connection?.refreshing &&
    Date.now() / 1000 - data.connection.attempted_at < 60;
  useEffect(() => {
    if (!refreshing || busy) return;
    const timer = setTimeout(() => setAttempt((value) => value + 1), 2000);
    return () => clearTimeout(timer);
  }, [refreshing, busy, attempt]);
  async function run(task) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await task();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const snapshot = data?.latest[source],
    n = snapshot?.normalized || {};
  const featured =
    data?.latest.codolio?.normalized || data?.latest.manual?.normalized || {};
  const card = featured.problem_details?.codolioCardDetails || {};
  const contestCount = Object.entries(card).find(
    ([key, value]) =>
      /contest.*(attend|participat)/i.test(key) && typeof value === "number",
  )?.[1];
  const detailSections = Object.entries(n.problem_details || {});
  const difficulty = difficultyOf(n.problem_details);

  return (
    <div className="cd-page">
      {error && (
        <div className="cd-alert" role="alert">
          {error}
          <button onClick={() => setAttempt((value) => value + 1)}>
            Retry
          </button>
        </div>
      )}
      {notice && (
        <div className="cd-alert" role="status">
          {notice}
        </div>
      )}
      {data?.connection?.error && (
        <div className="cd-alert" role="alert">
          {data.connection.error}
        </div>
      )}
      {!data && !error && (
        <div className="cd-panel" role="status">
          Loading coding statistics…
        </div>
      )}
      {data && (
        <>
          <div className="cd-heading">
            <div>
              <h1>Coding statistics</h1>
              <p>
                {demoMode
                  ? "Illustrative statistics for exploring the full dashboard."
                  : "Your problem solving and development activity in one place."}
              </p>
            </div>
            <div className="cd-actions">
              <div
                className="cd-segments"
                role="group"
                aria-label="Snapshot source"
              >
                {["codolio", "manual"].map((item) => (
                  <button
                    key={item}
                    aria-pressed={source === item}
                    onClick={() => setSource(item)}
                  >
                    {item === "codolio" ? "Codolio" : "Manual"}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="cd-source">
            {snapshot && (
              <span>
                {demoMode && source === "codolio"
                  ? "Illustrative sample"
                  : source === "manual"
                    ? "Self reported"
                    : "Saved profile"}{" "}
                · {when(snapshot.fetched_at)}
              </span>
            )}
            <div className="cd-actions">
              {data.connection && (
                <button
                  disabled={busy || refreshing || demoMode}
                  onClick={() =>
                    run(async () => {
                      setData(await post("/coding/refresh", {}));
                      setNotice("Refreshing your public profile…");
                    })
                  }
                >
                  <RefreshCw size={15} />
                  {refreshing ? "Refreshing…" : "Refresh"}
                </button>
              )}
              <button
                onClick={() =>
                  setManual(
                    Object.fromEntries([
                      ...metrics
                        .filter(([key]) => key !== "github_active_days")
                        .map(([key]) => [
                          key,
                          data.latest.manual?.normalized[key] ?? "",
                        ]),
                      ["note", data.latest.manual?.normalized.note || ""],
                    ]),
                  )
                }
              >
                Add manual stats
              </button>
            </div>
          </div>
          {!data.connection && !demoMode && (
            <form
              className="cd-connect cd-panel"
              onSubmit={(event) => {
                event.preventDefault();
                run(async () => {
                  setData(
                    await post("/coding/connection", { handle: handle.trim() }),
                  );
                  setHandle("");
                  setNotice(
                    "Profile connected. Select Refresh to import statistics.",
                  );
                });
              }}
            >
              <div>
                <strong>Connect Codolio</strong>
                <p>
                  Import your public problem solving profile into a saved
                  snapshot.
                </p>
              </div>
              <label className="sr-only" htmlFor="cd-handle">
                Codolio username
              </label>
              <input
                id="cd-handle"
                required
                pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,59}"
                placeholder="Codolio username"
                value={handle}
                onChange={(event) => setHandle(event.target.value)}
              />
              <button type="submit" disabled={busy}>
                Connect
              </button>
            </form>
          )}
          {snapshot ? (
            <>
              <div className="cd-tabs" aria-label="Coding views">
                {["Problem solving", "Development"].map((item) => (
                  <button
                    key={item}
                    aria-pressed={view === item}
                    onClick={() => setView(item)}
                  >
                    {item === "Development" ? (
                      <Github size={16} />
                    ) : (
                      <Code2 size={16} />
                    )}
                    {item}
                  </button>
                ))}
              </div>
              <div className="cd-metrics">
                {(view === "Problem solving"
                  ? [
                      ...metrics.slice(0, 2),
                      ["contests", "Contests", contestCount],
                      ["hackathons", "Hackathons", hackathonCount],
                    ]
                  : metrics.slice(2)
                ).map(([key, title, suppliedValue]) => {
                  const value =
                    suppliedValue === undefined ? n[key] : suppliedValue;
                  return (
                    <article key={key}>
                      <span>{title}</span>
                      <strong>{number(value)}</strong>
                      <small>
                        {value == null
                          ? "Not reported"
                          : source === "manual"
                            ? "Self reported"
                            : demoMode
                              ? "Illustrative demo data"
                              : "Provider reported"}
                      </small>
                    </article>
                  );
                })}
                {view === "Problem solving" &&
                  Object.entries(n.problem_details?.codolioCardDetails || {})
                    .filter(
                      ([key, value]) =>
                        typeof value === "number" &&
                        !["totalQuestionsSolved", "totalActiveDays"].includes(
                          key,
                        ),
                    )
                    .map(([key, value]) => (
                      <article key={key}>
                        <span>{label(key.replace(/^total/, ""))}</span>
                        <strong>{number(value)}</strong>
                        <small>
                          {demoMode
                            ? "Illustrative demo data"
                            : "Provider reported"}
                        </small>
                      </article>
                    ))}
              </div>
              {view === "Problem solving" ? (
                <>
                  {n.problem_activity?.length > 0 && (
                    <section className="cd-panel">
                      <h3>Problem solving activity</h3>
                      <ActivityCalendar snapshot={snapshot} problem />
                    </section>
                  )}
                  {difficulty && (
                    <section className="cd-panel">
                      <h3>Questions by difficulty</h3>
                      <div className="cd-difficulty">
                        {["Easy", "Medium", "Hard"].map((name, index) => (
                          <div key={name}>
                            <span>{name}</span>
                            <div>
                              <i
                                style={{
                                  width: `${(difficulty[index] / Math.max(1, ...difficulty)) * 100}%`,
                                }}
                              />
                            </div>
                            <strong>{number(difficulty[index])}</strong>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}
                  <section className="cd-panel">
                    <div className="cd-panel-heading">
                      <div>
                        <h3>Problem solving details</h3>
                        <p>
                          Every available platform, difficulty, contest and
                          activity section in the saved response.
                        </p>
                      </div>
                      {!demoMode && data.connection?.handle && (
                        <a
                          href={`https://codolio.com/profile/${encodeURIComponent(data.connection.handle)}/problemSolving`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          View profile <ArrowUpRight size={15} />
                        </a>
                      )}
                    </div>
                    {detailSections.length ? (
                      <div className="cd-sections">
                        {detailSections.map(([key, value]) => (
                          <Detail
                            key={key}
                            name={
                              key === "codolioCardDetails" ? "Overview" : key
                            }
                            value={value}
                          />
                        ))}
                      </div>
                    ) : (
                      <p className="cd-muted">
                        This snapshot has only summary totals. Refresh the
                        connected profile to import the full provider response.
                      </p>
                    )}
                  </section>
                </>
              ) : (
                <>
                  <section className="cd-panel">
                    <h3>Contribution activity</h3>
                    <ActivityCalendar snapshot={snapshot} />
                  </section>
                  <section className="cd-panel">
                    <h3>Languages across repositories</h3>
                    <p className="cd-muted">
                      Share of reported code bytes, not proficiency.
                    </p>
                    {n.languages?.length ? (
                      <>
                        <div className="cd-language-bar">
                          {n.languages.map((item, index) => (
                            <span
                              key={item.name}
                              style={{
                                width: `${item.percent}%`,
                                background: `hsl(0 0% ${22 + index * 11}%)`,
                              }}
                            />
                          ))}
                        </div>
                        <div className="cd-languages">
                          {n.languages.map((item) => (
                            <div key={item.name}>
                              <span>{item.name}</span>
                              <strong>{item.percent}%</strong>
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <p className="cd-muted">No language data reported.</p>
                    )}
                  </section>
                </>
              )}
              {n.note && <p className="cd-note">{n.note}</p>}
              <details className="cd-panel cd-history">
                <summary>
                  Snapshot history · {data.history[source]?.length || 0}
                </summary>
                <div className="record-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Saved</th>
                        <th>Questions solved</th>
                        <th>Contributions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data.history[source] || []).map((row) => (
                        <tr key={row.id}>
                          <td>{when(row.fetched_at)}</td>
                          <td>{number(row.solved)}</td>
                          <td>{number(row.contributions)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
              {!demoMode && (source === "manual" || data.connection) && (
                <button
                  className="cd-remove"
                  onClick={() => {
                    const text =
                      source === "manual"
                        ? "Remove all manual coding snapshots?"
                        : "Disconnect Codolio and remove imported snapshots?";
                    if (window.confirm(text))
                      run(async () => {
                        setData(
                          await api(
                            source === "manual"
                              ? "/coding/manual"
                              : "/coding/connection",
                            { method: "DELETE" },
                          ),
                        );
                        setNotice("History removed.");
                      });
                  }}
                >
                  {source === "manual"
                    ? "Remove manual history"
                    : "Disconnect Codolio"}
                </button>
              )}
            </>
          ) : (
            <div className="cd-panel cd-empty">
              <Code2 size={22} />
              <h3>
                {source === "manual"
                  ? "Start with your own baseline"
                  : "Connect your coding profile"}
              </h3>
              <p>
                {source === "manual"
                  ? "Add totals from your profiles and track changes over time."
                  : "Connect a public Codolio username above, then refresh it to load your statistics."}
              </p>
              {source === "manual" && (
                <button
                  onClick={() =>
                    setManual(
                      Object.fromEntries([
                        ...metrics
                          .filter(([key]) => key !== "github_active_days")
                          .map(([key]) => [key, ""]),
                        ["note", ""],
                      ]),
                    )
                  }
                >
                  Add manual snapshot
                </button>
              )}
            </div>
          )}
        </>
      )}
      {manual && (
        <section className="cd-panel">
          <h3>Record coding totals</h3>
          <p className="cd-muted">
            Leave unknown values blank. Enter zero only when known.
          </p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              run(async () => {
                const body = Object.fromEntries(
                  metrics
                    .filter(([key]) => key !== "github_active_days")
                    .map(([key]) => [
                      key,
                      manual[key] === "" ? null : Number(manual[key]),
                    ]),
                );
                setData(
                  await post("/coding/manual", { ...body, note: manual.note }),
                );
                setSource("manual");
                setManual(null);
                setNotice("Manual snapshot saved.");
              });
            }}
          >
            <fieldset disabled={busy} className="cd-fields">
              <div>
                {metrics
                  .filter(([key]) => key !== "github_active_days")
                  .map(([key, title]) => (
                    <label key={key}>
                      {title}
                      <input
                        type="number"
                        min="0"
                        max="1000000000"
                        step="1"
                        value={manual[key]}
                        onChange={(event) =>
                          setManual({ ...manual, [key]: event.target.value })
                        }
                      />
                    </label>
                  ))}
              </div>
              <label>
                Snapshot note
                <textarea
                  maxLength={500}
                  value={manual.note}
                  onChange={(event) =>
                    setManual({ ...manual, note: event.target.value })
                  }
                />
              </label>
              <div className="cd-actions">
                <button type="button" onClick={() => setManual(null)}>
                  Cancel
                </button>
                <button type="submit">Save snapshot</button>
              </div>
            </fieldset>
          </form>
        </section>
      )}
    </div>
  );
}
