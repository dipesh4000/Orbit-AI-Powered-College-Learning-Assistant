import { useState } from "react";
import Login from "./Login";
import { post } from "./api";
import "./personal.css";

export default function AccountLogin(props) {
  const [mode, setMode] = useState(
    new URLSearchParams(window.location.search).get("mode") === "register"
      ? "register"
      : "login",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      props.onAuthenticated(await post(`/auth/${mode}`, data));
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  if (mode === "demo")
    return (
      <>
        <button className="account-back" onClick={() => setMode("login")}>
          Back to personal login
        </button>
        <Login {...props} />
      </>
    );
  return (
    <main className="account-page">
      <section className="account-card">
        <a className="brand" href="/">
          <img src="/orbit-mark.svg" alt="" /> Orbit AI
        </a>
        <p className="eyebrow">YOUR PERSONAL LEARNING SPACE</p>
        <h1>{mode === "register" ? "Create your account" : "Welcome back"}</h1>
        <p>
          Keep your subjects, marks, and practice together in your own
          workspace.
        </p>
        {props.onDemo && <button className="primary" onClick={props.onDemo} disabled={props.busy}>Open preloaded demo</button>}
        {(error || props.error) && (
          <p className="error" role="alert">
            {error || props.error}
          </p>
        )}
        {props.loading && (
          <p role="status">
            {props.waking ? "Waking up your server…" : "Connecting to Orbit…"}
          </p>
        )}
        <form onSubmit={submit} aria-busy={busy}>
          {mode === "register" && (
            <label>
              Name
              <input name="name" autoComplete="name" required maxLength={100} />
            </label>
          )}
          <label>
            Email
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
              maxLength={254}
            />
          </label>
          <label>
            Password
            <input
              key={mode}
              name="password"
              type="password"
              autoComplete={
                mode === "register" ? "new-password" : "current-password"
              }
              required
              minLength={mode === "register" ? 12 : 1}
              maxLength={1024}
            />
          </label>
          {mode === "register" && <small>Use at least 12 characters.</small>}
          <button className="primary" disabled={busy || props.loading}>
            {busy
              ? "Opening workspace…"
              : mode === "register"
                ? "Create account"
                : "Sign in"}
          </button>
        </form>
        <button
          className="connection-retry"
          disabled={busy}
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
        >
          {mode === "login"
            ? "Create an account"
            : "Already have an account? Sign in"}
        </button>
        {props.health?.demo && (
          <button
            className="connection-retry"
            disabled={busy}
            onClick={() => setMode("demo")}
          >
            Explore demo profiles
          </button>
        )}
        {props.error && (
          <button onClick={props.onRetry}>Try connecting again</button>
        )}
      </section>
    </main>
  );
}
