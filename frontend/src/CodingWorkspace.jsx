import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Code2,
  Github,
  RefreshCw,
  Unplug,
} from "lucide-react";
import { api, post } from "./api";
import "./coding.css";

const metrics = [
  ["solved", "Problems solved"],
  ["active_days", "Problem-solving active days"],
  ["contributions", "GitHub contributions"],
  ["commits", "Commits"],
  ["stars", "Stars"],
  ["pull_requests", "Pull requests"],
  ["issues", "Issues"],
];
const number = (value) => (value == null ? "—" : value.toLocaleString());
const date = (value) =>
  value ? new Date(value * 1000).toLocaleString() : "Never";
const colors = [
  "#367957",
  "#669874",
  "#9cb88c",
  "#ccaa61",
  "#bf8067",
  "#7695a0",
];

function Heatmap({ snapshot }) {
  const activity = snapshot.normalized.activity || [];
  if (!activity.length)
    return (
      <p className="empty-state">
        Daily GitHub activity is unavailable in this snapshot.
      </p>
    );
  const end = new Date(snapshot.fetched_at * 1000);
  end.setUTCHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - 364);
  const values = new Map(activity.map((d) => [d.date, d.count]));
  const max = Math.max(1, ...activity.map((d) => d.count));
  const days = Array.from({ length: 365 }, (_, index) => {
    const day = new Date(start);
    day.setUTCDate(day.getUTCDate() + index);
    const key = day.toISOString().slice(0, 10);
    const value = values.get(key);
    return {
      key,
      value,
      level:
        value == null
          ? "unknown"
          : value === 0
            ? 0
            : Math.min(4, Math.ceil((value / max) * 4)),
    };
  });
  return (
    <>
      <p className="subtle">
        365 days ending {end.toISOString().slice(0, 10)} · UTC dates · GitHub
        activity via Codolio
      </p>
      <div
        className="coding-heatmap-scroll"
        tabIndex={0}
        role="region"
        aria-label="GitHub daily activity calendar, scroll horizontally"
      >
        <div
          className="coding-heatmap"
          role="list"
          aria-label="Daily contributions"
        >
          {days.map((d) => (
            <span
              role="listitem"
              key={d.key}
              className={`heat-day level-${d.level}`}
              title={`${d.key}: ${d.value == null ? "not reported" : `${d.value} contributions`}`}
              aria-label={`${d.key}: ${d.value == null ? "not reported" : `${d.value} contributions`}`}
            />
          ))}
        </div>
      </div>
      <div className="heat-legend">
        <span>Not reported</span>
        <i className="heat-day level-unknown" />
        <span>0</span>
        {[0, 1, 2, 3, 4].map((v) => (
          <i key={v} className={`heat-day level-${v}`} />
        ))}
        <span>More</span>
      </div>
    </>
  );
}

function ConfirmRemoval({ source, busy, onCancel, onConfirm }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="workspace-card delete-dialog"
      aria-labelledby="coding-remove-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onCancel();
      }}
    >
      <h2 id="coding-remove-title">
        {source === "codolio"
          ? "Disconnect Codolio?"
          : "Remove manual history?"}
      </h2>
      <p>
        {source === "codolio"
          ? "This removes your Codolio connection and all imported snapshots. Your manual entries remain."
          : "This removes all manually entered coding snapshots. Your Codolio data remains."}
      </p>
      <div className="form-actions">
        <button autoFocus disabled={busy} onClick={onCancel}>
          Cancel
        </button>
        <button className="danger-button" disabled={busy} onClick={onConfirm}>
          {busy ? "Removing…" : "Remove history"}
        </button>
      </div>
    </dialog>
  );
}

export default function CodingWorkspace() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [handle, setHandle] = useState("");
  const [source, setSource] = useState("codolio");
  const [view, setView] = useState("Problem solving");
  const [manual, setManual] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const initialized = useRef(false);
  const refreshing =
    data?.connection?.refreshing &&
    Date.now() / 1000 - data.connection.attempted_at < 60;
  useEffect(() => {
    const controller = new AbortController();
    api("/coding", { signal: controller.signal })
      .then((result) => {
        setData(result);
        if (!initialized.current)
          setSource(
            result.latest.codolio || result.connection
              ? "codolio"
              : result.latest.manual
                ? "manual"
                : "codolio",
          );
        initialized.current = true;
        if (attempt > 0 && !result.connection?.refreshing) {
          setNotice(
            result.connection?.error
              ? ""
              : "Saved coding data is up to date with your last refresh.",
          );
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [attempt]);
  // A reload during refresh resumes watching the saved backend state, never refetches Codolio.
  useEffect(() => {
    if (!refreshing || busy) return;
    const timer = setTimeout(() => setAttempt((v) => v + 1), 2000);
    return () => clearTimeout(timer);
  }, [data, busy, attempt, refreshing]);

  async function run(work) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    const result = await post("/coding/refresh", {});
    setData(result);
    if (!result.connection?.error)
      setNotice(
        "Refresh started. Your saved snapshot stays available while Codolio responds.",
      );
  }
  function openManual() {
    const latest = data.latest.manual?.normalized || {};
    setManual(
      Object.fromEntries([
        ...metrics.map(([key]) => [key, latest[key] ?? ""]),
        ["note", latest.note || ""],
      ]),
    );
  }
  const snapshot = data?.latest[source];
  const n = snapshot?.normalized;
  const stale = snapshot && Date.now() / 1000 - snapshot.fetched_at > 86400;
  const working = busy || refreshing;

  return (
    <div className="coding-workspace">
      <section className="workspace-card coding-connect">
        <div className="section-heading">
          <div>
            <span className="eyebrow">YOUR CODING JOURNEY</span>
            <h2>Small steps. Visible progress.</h2>
            <p className="subtle">
              Bring your problem solving and development activity into one
              place.
            </p>
          </div>
          <Code2 size={30} />
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="coding-notice" role="status">
            {notice}
          </p>
        )}
        {!data ? (
          <div className="empty-state">
            {error ? (
              <button
                onClick={() => {
                  setError("");
                  setAttempt((v) => v + 1);
                }}
              >
                Retry loading coding data
              </button>
            ) : (
              "Loading saved coding data…"
            )}
          </div>
        ) : (
          <>
            {data.connection ? (
              <div className="coding-source-row">
                <div>
                  <strong>Codolio / {data.connection.handle}</strong>
                  <p className="subtle">
                    Last attempt: {date(data.connection.attempted_at)}
                  </p>
                </div>
                <div className="coding-actions">
                  <a
                    href={`https://codolio.com/profile/${encodeURIComponent(data.connection.handle)}/${view === "Development" ? "devStats" : "problemSolving"}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View profile <ArrowUpRight size={14} />
                  </a>
                  <button disabled={working} onClick={() => run(refresh)}>
                    <RefreshCw size={15} />
                    {working ? "Refreshing…" : "Refresh Codolio"}
                  </button>
                  <button
                    aria-label="Disconnect Codolio"
                    disabled={busy}
                    onClick={() => setRemoving("codolio")}
                  >
                    <Unplug size={15} />
                  </button>
                </div>
              </div>
            ) : (
              <form
                className="coding-connection-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  run(async () => {
                    setData(
                      await post("/coding/connection", {
                        handle: handle.trim(),
                      }),
                    );
                    setSource("codolio");
                    await refresh();
                  });
                }}
              >
                <label htmlFor="codolio-handle">
                  <strong>No coding source connected</strong>
                  <span className="subtle">
                    Enter your public Codolio handle to import a snapshot.
                  </span>
                </label>
                <div className="coding-actions">
                  <input
                    id="codolio-handle"
                    placeholder="Your Codolio handle"
                    value={handle}
                    maxLength={60}
                    required
                    pattern="[A-Za-z0-9][A-Za-z0-9_.\-]{0,59}"
                    onChange={(e) => setHandle(e.target.value)}
                    disabled={busy}
                  />
                  <button className="primary-button" disabled={busy}>
                    {busy ? "Connecting…" : "Connect Codolio"}
                  </button>
                </div>
              </form>
            )}
            {data.connection?.error && (
              <p className="coding-warning" role="status">
                {data.connection.error}
              </p>
            )}
            <p className="subtle coding-save-hint">
              Saved in your Orbit account. Refresh only when you choose. No
              Codolio account?{" "}
              <button
                className="text-button"
                disabled={busy}
                onClick={openManual}
              >
                Enter totals manually
              </button>
            </p>
          </>
        )}
      </section>

      {manual && (
        <section className="workspace-card">
          <h2>Record your coding totals</h2>
          <p className="subtle">
            A dated, self-reported snapshot. Leave unknown values blank; enter 0
            only for a known zero.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                const body = Object.fromEntries(
                  metrics.map(([key]) => [
                    key,
                    manual[key] === "" ? null : Number(manual[key]),
                  ]),
                );
                setData(
                  await post("/coding/manual", { ...body, note: manual.note }),
                );
                setManual(null);
                setSource("manual");
                setNotice("Manual snapshot saved.");
              });
            }}
          >
            <fieldset disabled={busy} className="coding-fieldset">
              <div className="form-grid">
                {metrics.map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <input
                      type="number"
                      min="0"
                      max="1000000000"
                      step="1"
                      value={manual[key]}
                      onChange={(e) =>
                        setManual({ ...manual, [key]: e.target.value })
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
                  onChange={(e) =>
                    setManual({ ...manual, note: e.target.value })
                  }
                  placeholder="For example: totals checked on my profiles today"
                />
              </label>
              <div className="form-actions">
                <button type="button" onClick={() => setManual(null)}>
                  Cancel
                </button>
                <button className="primary-button">Save manual snapshot</button>
              </div>
            </fieldset>
          </form>
        </section>
      )}

      {data && (
        <section className="workspace-card coding-dashboard">
          <div className="section-heading">
            <h2>Coding overview</h2>
            <div className="coding-segments" aria-label="Snapshot source">
              {["codolio", "manual"].map((s) => (
                <button
                  key={s}
                  aria-pressed={source === s}
                  onClick={() => setSource(s)}
                >
                  {s === "codolio" ? "Codolio" : "Manual"}
                </button>
              ))}
            </div>
          </div>
          {snapshot ? (
            <>
              <div className="coding-provenance">
                <span className={`coding-badge ${stale ? "stale" : ""}`}>
                  {source === "manual" ? "Self-reported" : "Saved snapshot"}
                  {stale ? " · Over 24h old" : ""}
                </span>
                <span>
                  Saved {date(snapshot.fetched_at)} · Snapshot #{snapshot.id}
                </span>
                {source === "manual" && (
                  <button
                    className="text-button"
                    onClick={openManual}
                    disabled={busy}
                  >
                    Update totals
                  </button>
                )}
              </div>
              <div className="coding-view-tabs" aria-label="Coding views">
                {["Problem solving", "Development"].map((v) => (
                  <button
                    key={v}
                    aria-pressed={view === v}
                    onClick={() => setView(v)}
                  >
                    {v === "Development" ? (
                      <Github size={17} />
                    ) : (
                      <Code2 size={17} />
                    )}
                    {v}
                  </button>
                ))}
              </div>
              <div className="coding-metrics">
                {metrics
                  .filter(([key]) =>
                    view === "Problem solving"
                      ? ["solved", "active_days"].includes(key)
                      : !["solved", "active_days"].includes(key),
                  )
                  .map(([key, label]) => (
                    <article className="coding-metric" key={key}>
                      <span>{label}</span>
                      <strong>{number(n[key])}</strong>
                      <small>
                        {n[key] == null
                          ? "Not reported"
                          : source === "manual"
                            ? "Self-reported total"
                            : "Provider-reported total"}
                      </small>
                    </article>
                  ))}
              </div>
              {view === "Problem solving" ? (
                <div className="coding-insight">
                  <Activity size={23} />
                  <div>
                    <h3>Consistency starts with a baseline</h3>
                    <p>
                      Save snapshots over time to track your totals. Difficulty,
                      topic breakdowns, and problem-solving heatmaps are not
                      supplied by this connection.
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div className="coding-chart">
                    <h3>Contribution activity</h3>
                    <Heatmap snapshot={snapshot} />
                  </div>
                  <div className="coding-chart">
                    <h3>Languages across repositories</h3>
                    <p className="subtle">
                      Share of reported code bytes, not proficiency or time
                      spent.
                    </p>
                    {n.languages?.length ? (
                      <>
                        <div className="language-bar" aria-hidden="true">
                          {n.languages.map((l, i) => (
                            <span
                              key={l.name}
                              style={{
                                width: `${l.percent}%`,
                                background: colors[i % colors.length],
                              }}
                            />
                          ))}
                        </div>
                        <ul className="language-list">
                          {n.languages.map((l, i) => (
                            <li key={l.name}>
                              <i
                                style={{
                                  background: colors[i % colors.length],
                                }}
                              />
                              <span>{l.name}</span>
                              <strong>{l.percent}%</strong>
                            </li>
                          ))}
                        </ul>
                      </>
                    ) : (
                      <p className="empty-state">
                        Language distribution is unavailable in this snapshot.
                      </p>
                    )}
                  </div>
                  {n.provider_updated_at && (
                    <p className="subtle">
                      Provider-reported GitHub update: {n.provider_updated_at}{" "}
                      (timezone not supplied). Lifetime totals and the calendar
                      window may differ.
                    </p>
                  )}
                </>
              )}
              {n.note && <p className="coding-note">{n.note}</p>}
              <details className="coding-history">
                <summary>
                  Snapshot history · latest {data.history[source].length}
                </summary>
                <div className="record-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Saved</th>
                        <th>Problems solved</th>
                        <th>GitHub contributions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.history[source].map((r) => (
                        <tr key={r.id}>
                          <td>{date(r.fetched_at)}</td>
                          <td>{number(r.solved)}</td>
                          <td>{number(r.contributions)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
              {source === "manual" && (
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => setRemoving("manual")}
                >
                  Remove manual history
                </button>
              )}
            </>
          ) : (
            <div className="empty-state">
              <Code2 size={28} />
              <h3>
                {source === "manual"
                  ? "Your own starting point"
                  : "Your first snapshot belongs here"}
              </h3>
              <p>
                {source === "manual"
                  ? "Record totals from your profiles whenever you want. Manual entries stay separate from Codolio."
                  : "Connect and refresh your public profile above. Your saved data will be available without another provider request."}
              </p>
              {source === "manual" && (
                <button
                  className="primary-button"
                  disabled={busy}
                  onClick={openManual}
                >
                  Add manual snapshot
                </button>
              )}
            </div>
          )}
        </section>
      )}
      {removing && (
        <ConfirmRemoval
          source={removing}
          busy={busy}
          onCancel={() => setRemoving(null)}
          onConfirm={() =>
            run(async () => {
              setData(
                await api(
                  removing === "codolio"
                    ? "/coding/connection"
                    : "/coding/manual",
                  { method: "DELETE" },
                ),
              );
              setRemoving(null);
              setNotice("History removed.");
            })
          }
        />
      )}
    </div>
  );
}
