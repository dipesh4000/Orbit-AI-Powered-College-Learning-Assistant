import { useEffect, useState } from "react";
import { Github } from "lucide-react";
import { api, post } from "./api";
export default function GitHubConnection() {
  const [profile, setProfile] = useState(null),
    [handle, setHandle] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    api("/github/profile", { signal: c.signal })
      .then((r) => {
        setProfile(r.profile);
        setHandle(r.profile?.handle || "");
        setError("");
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [retry]);
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
    <section className="workspace-card github-connection">
      <div className="section-heading">
        <h2>
          <Github size={19} /> GitHub profile
        </h2>
        {profile && (
          <small>
            Saved {new Date(profile.fetched_at * 1000).toLocaleString()}
          </small>
        )}
      </div>
      <p>
        {profile
          ? `${profile.snapshot.name || profile.handle} · ${profile.snapshot.public_repos ?? "—"} public repositories · ${profile.snapshot.followers ?? "—"} followers`
          : loading
            ? "Loading GitHub connection…"
            : "Connect your public GitHub username to add your development profile."}
      </p>
      <form
        className="inline-entry"
        onSubmit={(e) => {
          e.preventDefault();
          run(async () =>
            setProfile((await post("/github/profile", { handle })).profile),
          );
        }}
      >
        <label>
          GitHub username
          <input
            disabled={loading || busy}
            required
            pattern="[a-zA-Z0-9][a-zA-Z0-9-]{0,38}"
            maxLength={39}
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            placeholder="Your GitHub username"
          />
        </label>
        <button className="primary" disabled={busy || loading}>
          {busy
            ? "Connecting…"
            : profile
              ? "Refresh GitHub profile"
              : "Connect GitHub"}
        </button>
        {profile && (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (
                confirm(
                  "Disconnect this GitHub profile? Imported project material will remain in Practice.",
                )
              )
                run(async () => {
                  await api("/github/profile", { method: "DELETE" });
                  setProfile(null);
                  setHandle("");
                });
            }}
          >
            Disconnect GitHub
          </button>
        )}
      </form>
      {error && (
        <p role="alert" className="error">
          {error}{" "}
          <button onClick={() => setRetry((n) => n + 1)}>
            Retry connection status
          </button>
        </p>
      )}
      <p className="subtle">
        Public profile only. Detailed contribution activity is shown from your
        Codolio snapshot above. Add public repositories to projects in Practice
        to chat about their code.
      </p>
    </section>
  );
}
