import { useEffect, useRef, useState } from "react";
import {
  X,
  Github,
  Code2,
  RefreshCw,
  Unplug,
  ArrowUpRight,
} from "lucide-react";
import { api, post } from "./api";

function CodolioConnection() {
  const [data, setData] = useState(null);
  const [handle, setHandle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [removing, setRemoving] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const refreshing =
    data?.connection?.refreshing &&
    Date.now() / 1000 - data.connection.attempted_at < 60;

  useEffect(() => {
    const c = new AbortController();
    api("/coding", { signal: c.signal })
      .then((r) => setData(r))
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [attempt]);

  useEffect(() => {
    if (!refreshing || busy) return;
    const t = setTimeout(() => setAttempt((v) => v + 1), 2000);
    return () => clearTimeout(t);
  }, [data, busy, refreshing]);

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

  async function doRefresh() {
    const result = await post("/coding/refresh", {});
    setData(result);
    if (!result.connection?.error) setNotice("Refresh started.");
  }

  const working = busy || refreshing;

  return (
    <div className="settings-connection-block">
      <div className="settings-connection-header">
        <Code2 size={18} />
        <div>
          <strong>Codolio</strong>
          <p>Import your problem-solving and development stats.</p>
        </div>
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
        <p className="subtle">Loading…</p>
      ) : data.connection ? (
        <div className="settings-connected-row">
          <div>
            <span className="settings-connected-badge">Connected</span>
            <span className="subtle"> · {data.connection.handle}</span>
          </div>
          <div className="coding-actions">
            <a
              href={`https://codolio.com/profile/${encodeURIComponent(data.connection.handle)}`}
              target="_blank"
              rel="noreferrer"
            >
              View profile <ArrowUpRight size={13} />
            </a>
            <button disabled={working} onClick={() => run(doRefresh)}>
              <RefreshCw size={14} /> {working ? "Refreshing…" : "Refresh"}
            </button>
            {removing ? (
              <span className="settings-confirm-row">
                <span className="subtle">
                  Disconnect and remove all snapshots?
                </span>
                <button
                  className="danger-button"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      setData(
                        await api("/coding/connection", { method: "DELETE" }),
                      );
                      setRemoving(false);
                      setNotice("Codolio disconnected.");
                    })
                  }
                >
                  Confirm
                </button>
                <button onClick={() => setRemoving(false)}>Cancel</button>
              </span>
            ) : (
              <button disabled={busy} onClick={() => setRemoving(true)}>
                <Unplug size={14} /> Disconnect
              </button>
            )}
          </div>
          {data.connection.error && (
            <p className="coding-warning" role="status">
              {data.connection.error}
            </p>
          )}
        </div>
      ) : (
        <form
          className="settings-connect-form"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              const r = await post("/coding/connection", {
                handle: handle.trim(),
              });
              setData(r);
              await post("/coding/refresh", {});
              setAttempt((v) => v + 1);
              setNotice("Codolio connected. Refresh started.");
            });
          }}
        >
          <div className="settings-input-row">
            <span className="settings-prefix">codolio.com/profile/</span>
            <input
              placeholder="your-handle"
              value={handle}
              maxLength={60}
              required
              pattern="[A-Za-z0-9][A-Za-z0-9_.\-]{0,59}"
              onChange={(e) => setHandle(e.target.value)}
              disabled={busy}
            />
            <button className="primary-button" disabled={busy}>
              {busy ? "Connecting…" : "Connect"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function GitHubConnectionPanel() {
  const [profile, setProfile] = useState(null);
  const [handle, setHandle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    const c = new AbortController();
    api("/github/profile", { signal: c.signal })
      .then((r) => {
        setProfile(r.profile);
        setHandle(r.profile?.handle || "");
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, []);

  async function run(work) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings-connection-block">
      <div className="settings-connection-header">
        <Github size={18} />
        <div>
          <strong>GitHub</strong>
          <p>Connect your public profile to enrich projects in Practice.</p>
        </div>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p className="subtle">Loading…</p>
      ) : profile ? (
        <div className="settings-connected-row">
          <div>
            <span className="settings-connected-badge">Connected</span>
            <span className="subtle"> · {profile.handle}</span>
            <span className="subtle">
              {" "}
              · {profile.snapshot.public_repos ?? "—"} repos ·{" "}
              {profile.snapshot.followers ?? "—"} followers
            </span>
          </div>
          <div className="coding-actions">
            <a
              href={`https://github.com/${encodeURIComponent(profile.handle)}`}
              target="_blank"
              rel="noreferrer"
            >
              View profile <ArrowUpRight size={13} />
            </a>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                run(async () =>
                  setProfile(
                    (await post("/github/profile", { handle })).profile,
                  ),
                );
              }}
            >
              <button className="primary-button" disabled={busy}>
                {busy ? "Refreshing…" : "Refresh"}
              </button>
            </form>
            {removing ? (
              <span className="settings-confirm-row">
                <span className="subtle">Disconnect GitHub profile?</span>
                <button
                  className="danger-button"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      await api("/github/profile", { method: "DELETE" });
                      setProfile(null);
                      setHandle("");
                      setRemoving(false);
                    })
                  }
                >
                  Confirm
                </button>
                <button onClick={() => setRemoving(false)}>Cancel</button>
              </span>
            ) : (
              <button disabled={busy} onClick={() => setRemoving(true)}>
                <Unplug size={14} /> Disconnect
              </button>
            )}
          </div>
        </div>
      ) : (
        <form
          className="settings-connect-form"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () =>
              setProfile((await post("/github/profile", { handle })).profile),
            );
          }}
        >
          <div className="settings-input-row">
            <span className="settings-prefix">github.com/</span>
            <input
              placeholder="your-username"
              value={handle}
              required
              pattern="[a-zA-Z0-9][a-zA-Z0-9-]{0,38}"
              maxLength={39}
              onChange={(e) => setHandle(e.target.value)}
              disabled={busy}
            />
            <button className="primary-button" disabled={busy}>
              {busy ? "Connecting…" : "Connect"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default function SettingsModal({ onClose, theme, onThemeChange }) {
  const backdropRef = useRef(null);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="settings-backdrop"
      ref={backdropRef}
      onClick={(e) => {
        if (e.target === backdropRef.current) onClose();
      }}
    >
      <div
        className="settings-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
      >
        <aside className="settings-sidebar">
          <p className="settings-section-label">PREFERENCES</p>
          <span className="settings-nav-item active">
            Appearance & accounts
          </span>
        </aside>
        <div className="settings-content">
          <div className="settings-content-header">
            <h2>Settings</h2>
            <button
              className="settings-close"
              onClick={onClose}
              aria-label="Close settings"
            >
              <X size={20} />
            </button>
          </div>
          <div className="settings-appearance">
            <div>
              <strong>Dark mode</strong>
              <p>Use a darker workspace. Saved on this device.</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={theme === "dark"}
              aria-label="Dark mode"
              onClick={() => onThemeChange(theme === "dark" ? "light" : "dark")}
            >
              {theme === "dark" ? "On" : "Off"}
            </button>
          </div>
          <p className="subtle" style={{ marginBottom: 24 }}>
            Connect your public profiles to import coding stats and enrich your
            workspace.
          </p>
          <CodolioConnection />
          <GitHubConnectionPanel />
        </div>
      </div>
    </div>
  );
}
