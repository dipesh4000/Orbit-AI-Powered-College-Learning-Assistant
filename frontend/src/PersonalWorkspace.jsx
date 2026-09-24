import { useEffect, useState } from "react";
import {
  MessageSquare,
  LayoutDashboard,
  Code2,
  FolderGit2,
  LogOut,
  Settings,
  Plus,
  ChevronDown,
  ChevronRight,
  Trash2,
} from "lucide-react";
import { api, post } from "./api";
import PersonalChat from "./PersonalChat";
import AcademicDashboard from "./AcademicDashboard";
import CodingWorkspace from "./CodingWorkspace";
import RecordWorkspace from "./RecordWorkspace";
import ProjectWorkspace from "./ProjectWorkspace";
import SettingsModal from "./SettingsModal";
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
  const [showSettings, setShowSettings] = useState(false);
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  const [version, setVersion] = useState(0);

  // Chat sessions
  const [chats, setChats] = useState([]);
  const [chatId, setChatId] = useState(null);
  const [chatsOpen, setChatsOpen] = useState(true);
  const [chatBusy, setChatBusy] = useState(false);

  const refresh = () => setVersion((n) => n + 1);

  useEffect(() => {
    const c = new AbortController();
    api("/personal/workspace", { signal: c.signal })
      .then((r) => { setData(r); setError(""); })
      .catch((e) => { if (!c.signal.aborted) setError(e.message); });
    return () => c.abort();
  }, [owner.owner_id, version]);

  // Load chat list and auto-select most recent
  useEffect(() => {
    const c = new AbortController();
    api("/personal/chats", { signal: c.signal })
      .then((r) => {
        setChats(r);
        if (r.length > 0 && !chatId) setChatId(r[0].id);
      })
      .catch(() => {});
    return () => c.abort();
  }, [owner.owner_id]);

  async function newChat() {
    setChatBusy(true);
    try {
      const session = await post("/personal/chats", {});
      setChats((prev) => [session, ...prev]);
      setChatId(session.id);
      setTab("Chat");
    } catch (e) {
      setError(e.message);
    } finally {
      setChatBusy(false);
    }
  }

  async function deleteChat(id, e) {
    e.stopPropagation();
    if (!window.confirm("Delete this chat?")) return;
    try {
      await api(`/personal/chats/${id}`, { method: "DELETE" });
      setChats((prev) => prev.filter((c) => c.id !== id));
      if (chatId === id) {
        const remaining = chats.filter((c) => c.id !== id);
        setChatId(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (e) {
      setError(e.message);
    }
  }

  function refreshChatList(newChatId) {
    api("/personal/chats")
      .then((r) => {
        setChats(r);
        if (newChatId) setChatId(newChatId);
        else if (r.length > 0) setChatId((prev) => prev ?? r[0].id);
      })
      .catch(() => {});
  }

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

        {/* Chat history section */}
        <div className="chat-history-section">
          <div className="chat-history-header">
            <button
              className="chat-history-toggle"
              onClick={() => setChatsOpen((v) => !v)}
              aria-expanded={chatsOpen}
            >
              {chatsOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              <span>Recent chats</span>
            </button>
            <button
              className="chat-history-new"
              onClick={newChat}
              disabled={chatBusy}
              aria-label="New chat"
              title="New chat"
            >
              <Plus size={14} />
            </button>
          </div>
          {chatsOpen && (
            <ul className="chat-history-list">
              {chats.length === 0 && (
                <li className="chat-history-empty">No chats yet</li>
              )}
              {chats.map((c) => (
                <li key={c.id}>
                  <button
                    className={`chat-history-item ${chatId === c.id ? "active" : ""}`}
                    onClick={() => { setChatId(c.id); setTab("Chat"); }}
                    title={c.title}
                  >
                    <span className="chat-history-title">{c.title}</span>
                    <button
                      className="chat-history-delete"
                      onClick={(e) => deleteChat(c.id, e)}
                      aria-label="Delete chat"
                    >
                      <Trash2 size={12} />
                    </button>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

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
          <button
            className="owner-settings-btn"
            aria-label="Open settings"
            onClick={() => setShowSettings(true)}
          >
            <Settings size={15} />
          </button>
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
            chatId={chatId}
            onChatChanged={refreshChatList}
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
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </div>
  );
}
