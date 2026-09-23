import { useEffect, useState } from "react";
import {
  MessageSquare,
  LayoutDashboard,
  Code2,
  FolderGit2,
  LogOut,
} from "lucide-react";
import { api } from "./api";
import PersonalChat from "./PersonalChat";
import AcademicDashboard from "./AcademicDashboard";
import CodingWorkspace from "./CodingWorkspace";
import GitHubConnection from "./GitHubConnection";
import RecordWorkspace from "./RecordWorkspace";
import ProjectWorkspace from "./ProjectWorkspace";
import "./personal.css";
import "./workspace.css";

const navigation = [
  ["Chat", MessageSquare],
  ["Dashboard", LayoutDashboard],
  ["Coding stats", Code2],
  ["Practice", FolderGit2],
];
export default function PersonalWorkspace({
  owner,
  onLogout,
  error: outerError,
  demoMode,
}) {
  const [tab, setTab] = useState("Chat"),
    [project, setProject] = useState(null);
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const refresh = () => setVersion((n) => n + 1);
  useEffect(() => {
    const c = new AbortController();
    api("/personal/workspace", { signal: c.signal })
      .then((r) => {
        setData(r);
        setError("");
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [owner.owner_id, version]);
  const subjects = data?.subjects || [];
  return (
    <div className={`personal-shell ${tab === "Chat" ? "chat-shell" : ""}`}>
      <aside className="personal-sidebar">
        <a className="brand" href="/chat">
          <span className="orbit-symbol">◌</span> orbit
        </a>
        <p className="eyebrow">YOUR WORKSPACE</p>
        <nav aria-label="Personal navigation">
          {navigation.map(([name, Icon]) => (
            <button
              key={name}
              className={tab === name ? "active" : ""}
              aria-current={tab === name ? "page" : undefined}
              onClick={() => setTab(name)}
            >
              <Icon size={19} />
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <strong>A little progress, every day.</strong>
          <p>Your subjects, projects and learning, together.</p>
        </div>
        <div className="owner-card">
          <span className="owner-avatar">
            {owner.name.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <strong>{owner.name}</strong>
            <small>Personal workspace</small>
          </div>
        </div>
        <button className="signout" onClick={onLogout}>
          <LogOut size={17} />
          Sign out
        </button>
      </aside>
      <main className="personal-workspace">
        {demoMode && (
          <div className="demo-banner">
            <strong>Demo workspace · resets when the server stops</strong>
            Reference marks and illustrative coding, hackathon and paper
            examples. New academic values and projects start empty.
          </div>
        )}
        <header className="workspace-topbar">
          <span>Workspace / {tab}</span>
          <span className="private-label">
            {demoMode ? "Local demo" : "Private account"}
          </span>
        </header>
        {(error || outerError) && (
          <p className="error" role="alert">
            {error || outerError}{" "}
            <button onClick={refresh}>Retry loading</button>
          </p>
        )}
        <div hidden={tab !== "Chat"} className="chat-view">
          <PersonalChat
            demoMode={demoMode}
            name={owner.name}
            project={project}
            onClearProject={() => setProject(null)}
          />
        </div>
        {tab === "Dashboard" && (
          <AcademicDashboard
            owner={owner}
            subjects={subjects}
            onChanged={refresh}
            demoMode={demoMode}
          />
        )}
        {tab === "Coding stats" && (
          <>
            <div className="workspace-intro">
              <div>
                <p className="eyebrow">BUILD YOUR MOMENTUM</p>
                <h1>Coding stats</h1>
                <p>DSA, development, and the things you build with others.</p>
              </div>
            </div>
            <CodingWorkspace
              hackathonCount={data?.hackathons?.length || null}
            />
            <GitHubConnection />
            <div id="hackathon-records">
              <RecordWorkspace
                owner={owner}
                section="Projects"
                onChanged={refresh}
              />
            </div>
          </>
        )}
        {tab === "Practice" && (
          <ProjectWorkspace
            owner={owner}
            subjects={subjects}
            demoMode={demoMode}
            onChat={(p) => {
              setProject(p);
              setTab("Chat");
            }}
          />
        )}
      </main>
    </div>
  );
}
