import { useState } from "react";
import "./login.css";
import {
  ArrowRight,
  BookOpen,
  ChartNoAxesCombined,
  Check,
  LoaderCircle,
  Sparkles,
} from "lucide-react";

export default function Login({
  students,
  loading,
  waking,
  health,
  busy,
  error,
  onRetry,
  onSelect,
}) {
  const [selected, setSelected] = useState("");
  const student = students.find((item) => item.user_id === selected);
  return (
    <div className="login">
      <section className="login-story" aria-labelledby="story-title">
        <a className="brand" href="/login" aria-label="Orbit home">
          <span className="brand-icon">✳</span> orbit{" "}
          <span className="brand-tag">YOUR LEARNING SPACE</span>
        </a>
        <div className="story-copy">
          <div className="eyebrow">A LITTLE FOCUS. A LOT OF POSSIBILITY.</div>
          <h1 id="story-title">
            Find your focus.
            <br />
            <span>Build your momentum.</span>
          </h1>
          <p>
            A clearer picture of your progress. A little guidance when you need
            it. Your next step, all in one space.
          </p>
        </div>
        <div className="orbit-art" aria-hidden="true">
          <div className="orbit-ring ring-one">
            <i />
          </div>
          <div className="orbit-ring ring-two">
            <i />
          </div>
          <div className="orbit-ring ring-three">
            <i />
          </div>
          <div className="orbit-core">✳</div>
          <span className="orbit-label label-learn">
            <BookOpen size={16} /> Understand
          </span>
          <span className="orbit-label label-grow">
            <ChartNoAxesCombined size={16} /> Grow
          </span>
          <span className="orbit-label label-practice">
            <Sparkles size={16} /> Practice
          </span>
        </div>
        <p className="story-footer">
          <span className="small-dot" /> Small steps. Lasting progress.
        </p>
      </section>
      <main className="login-form-panel">
        <div className="login-card">
          <span className="login-badge">
            <Sparkles size={14} /> A SPACE TO MOVE FORWARD
          </span>
          <h2>Welcome to Orbit</h2>
          <p className="muted">
            Choose your demo profile to explore your learning workspace.
          </p>
          <div
            className={
              "server-status " +
              (error ? "unavailable" : health && !loading ? "ready" : "")
            }
            role="status"
            aria-live="polite"
          >
            {loading || busy ? (
              <LoaderCircle size={18} className="spin" />
            ) : health && !error ? (
              <Check size={18} />
            ) : (
              <span className="small-dot" />
            )}
            <div>
              <strong>
                {busy
                  ? "Opening your workspace…"
                  : loading
                    ? waking
                      ? "Waking up your server…"
                      : "Connecting to your workspace…"
                    : error
                      ? "Connection needs attention"
                      : "Your workspace is ready"}
              </strong>
              <small>
                {loading
                  ? waking
                    ? "Our free-tier server rests between visits. Waking up usually takes 60–90 seconds. You can leave this page open."
                    : "Getting everything ready for you."
                  : "Your courses, conversations, and practice in one place."}
              </small>
            </div>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (student && !busy && !loading) onSelect(selected);
            }}
            aria-busy={loading || busy}
          >
            <label htmlFor="student-profile">Student profile</label>
            <select
              id="student-profile"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
              disabled={loading || busy || !students.length}
              required
              aria-describedby="profile-description"
            >
              <option value="" disabled>
                {loading ? "Loading profiles…" : "Select your profile"}
              </option>
              {students.map((item) => (
                <option key={item.user_id} value={item.user_id}>
                  {item.label}
                </option>
              ))}
            </select>
            <p id="profile-description" className="profile-description">
              {student?.rationale ||
                "Explore a profile with its own course and assessment history."}
            </p>
            <button
              className="primary login-submit"
              type="submit"
              disabled={loading || busy || !student}
            >
              {busy ? (
                <LoaderCircle size={18} className="spin" />
              ) : (
                <>
                  Enter workspace <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>
          {!loading && (error || !students.length) && (
            <button
              className="connection-retry"
              onClick={onRetry}
              disabled={busy}
            >
              Try connecting again
            </button>
          )}
          <p className="login-disclosure">
            Demo workspace · No password required
          </p>
          <p className="fine">
            Profiles use supplied student records. Learning materials and
            assessment rules are labeled as demos.
          </p>
        </div>
        <p className="login-bottom">
          Made for curiosity. Designed for progress.
        </p>
      </main>
    </div>
  );
}
