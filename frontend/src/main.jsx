import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import { BrowserRouter, useLocation, useNavigate } from "react-router-dom";
import Login from "./AccountLogin";
import PersonalWorkspace from "./PersonalWorkspace";
import Landing from "./Landing";
import StartupIntro from "./StartupIntro";
import { api, post, wakeServer } from "./api";

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const appRoutes = ["/chat", "/dashboard", "/coding", "/practice"];
  const [student, setStudent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [waking, setWaking] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const returnPath = useRef(
    appRoutes.includes(location.pathname) ? location.pathname : "/chat",
  );

  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;
    setLoading(true);
    setWaking(false);
    setError("");
    setHealth(null);
    const timer = setTimeout(() => setWaking(true), 3000);
    (async () => {
      try {
        const status = await wakeServer(signal);
        let session = null;
        try {
          session = await api("/session", { signal, timeout: 15000 });
        } catch (e) {
          if (e.status !== 401) throw e;
        }
        if (signal.aborted) return;
        setHealth(status);
        setStudent(session);
      } catch (e) {
        if (!signal.aborted) setError(e.message);
      } finally {
        clearTimeout(timer);
        if (!signal.aborted) setLoading(false);
      }
    })();
    return () => { clearTimeout(timer); controller.abort(); };
  }, [attempt]);

  useEffect(() => {
    if (loading) return;
    if (!student && appRoutes.includes(location.pathname)) {
      returnPath.current = location.pathname;
      navigate("/login", { replace: true });
    } else if (student && location.pathname === "/login") {
      navigate(returnPath.current, { replace: true });
    }
  }, [student, loading, location.pathname]);

  useEffect(() => {
    const expire = () => {
      returnPath.current = window.location.pathname;
      setStudent(null);
      setError("Your session has ended. Sign in to continue.");
      navigate("/login", { replace: true });
    };
    window.addEventListener("orbit:session-expired", expire);
    return () => window.removeEventListener("orbit:session-expired", expire);
  }, [navigate]);

  function logout() {
    api("/session", { method: "DELETE" }).catch(() => {});
    setStudent(null);
    returnPath.current = "/chat";
    navigate("/login", { replace: true });
  }

  if (location.pathname === "/") return <Landing signedIn={!!student} />;

  if (!student)
    return (
      <Login
        loading={loading}
        waking={waking}
        health={health}
        error={error}
        onRetry={() => setAttempt((v) => v + 1)}
        onAuthenticated={(owner) => {
          setStudent(owner);
          setError("");
          navigate(returnPath.current, { replace: true });
        }}
      />
    );

  return (
    <PersonalWorkspace
      key={student.owner_id}
      owner={student}
      onLogout={logout}
      error={error}
    />
  );
}

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <StartupIntro />
    <App />
  </BrowserRouter>,
);
