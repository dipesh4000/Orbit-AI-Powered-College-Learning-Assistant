import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
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
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  X,
} from "lucide-react";
import { api, post } from "./api";
import PersonalChat from "./PersonalChat";
import AcademicDashboard from "./AcademicDashboard";
import CodingDashboard from "./CodingDashboard";
import RecordWorkspace from "./RecordWorkspace";
import ProjectWorkspace from "./ProjectWorkspace";
import SettingsModal from "./SettingsModal";
import "./personal.css";
import "./workspace.css";
import "./product.css";
import "./theme.css";

const navigation = [
  ["Chat", MessageSquare],
  ["Dashboard", LayoutDashboard],
  ["Coding stats", Code2],
  ["Practice", FolderGit2],
];
const tabPaths = {
  Chat: "/chat",
  Dashboard: "/dashboard",
  "Coding stats": "/coding",
  Practice: "/practice",
};
const tabFromPath = (path) =>
  Object.keys(tabPaths).find((name) => tabPaths[name] === path);

export default function PersonalWorkspace({
  owner,
  onLogout,
  error: outerError,
  demoMode,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [tab, setTab] = useState(
      () => tabFromPath(location.pathname) || "Chat",
    ),
    [project, setProject] = useState(null),
    [projectPrompt, setProjectPrompt] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("orbit-theme") === "dark" ? "dark" : "light";
    } catch {
      return "light";
    }
  });
  function changeTheme(next) {
    setTheme(next);
    try {
      localStorage.setItem("orbit-theme", next);
    } catch {
      /* Preference still applies for this session. */
    }
  }
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  const [version, setVersion] = useState(0);

  // Chat sessions
  const [chats, setChats] = useState([]);
  const [chatId, setChatId] = useState(null);
  const [chatsOpen, setChatsOpen] = useState(true);
  const [chatBusy, setChatBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("orbit-personal-sidebar") === "collapsed",
  );

  const refresh = () => setVersion((n) => n + 1);
  useEffect(() => {
    document.title = `${tab} · Orbit AI`;
  }, [tab]);
  useEffect(() => {
    const next = tabFromPath(location.pathname);
    if (next) setTab(next);
  }, [location.pathname]);
  useEffect(() => {
    if (!sidebarOpen) return;
    const close = (event) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [sidebarOpen]);
  const openTab = (name) => {
    setTab(name);
    navigate(tabPaths[name]);
    setSidebarOpen(false);
  };

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
      openTab("Chat");
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
    <div
      className={`personal-shell ${tab === "Chat" ? "chat-shell" : ""} ${collapsed ? "personal-collapsed" : ""} ${sidebarOpen ? "sidebar-open" : ""}`}
      data-theme={theme}
    >
      <button
        className="personal-scrim"
        aria-label="Close navigation"
        onClick={() => setSidebarOpen(false)}
      />
      <aside className="personal-sidebar" aria-label="Workspace sidebar">
        <div className="personal-sidebar-head">
          <a className="brand" href="/chat">
            <img className="orbit-mark" src="/orbit-mark.svg" alt="" />{" "}
            <span>Orbit AI</span>
          </a>
          <button
            className="personal-collapse"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => {
              setCollapsed(!collapsed);
              localStorage.setItem(
                "orbit-personal-sidebar",
                collapsed ? "expanded" : "collapsed",
              );
            }}
          >
            {collapsed ? (
              <PanelLeftOpen size={18} />
            ) : (
              <PanelLeftClose size={18} />
            )}
          </button>
          <button
            className="personal-mobile-close"
            aria-label="Close navigation"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>
        <button
          className="personal-new-chat"
          aria-label="New chat"
          onClick={() => {
            newChat();
            setSidebarOpen(false);
          }}
          disabled={chatBusy}
        >
          <Plus size={17} />
          <span>New chat</span>
        </button>
        <p className="eyebrow">WORKSPACE</p>
        <nav aria-label="Personal navigation">
          {navigation.map(([name, Icon]) => (
            <button
              key={name}
              className={tab === name ? "active" : ""}
              aria-current={tab === name ? "page" : undefined}
              onClick={() => openTab(name)}
              aria-label={name}
              title={name}
            >
              <Icon size={19} />
              <span>{name}</span>
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
              {chatsOpen ? (
                <ChevronDown size={13} />
              ) : (
                <ChevronRight size={13} />
              )}
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
                  <div
                    className={`chat-history-item ${chatId === c.id ? "active" : ""}`}
                    title={c.title}
                  >
                    <button
                      className="chat-history-select"
                      onClick={() => {
                        setChatId(c.id);
                        openTab("Chat");
                      }}
                    >
                      <span className="chat-history-title">{c.title}</span>
                    </button>
                    <button
                      className="chat-history-delete"
                      onClick={(e) => deleteChat(c.id, e)}
                      aria-label="Delete chat"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
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
        <header className="workspace-topbar">
          <span>
            <button
              className="personal-mobile-menu"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={19} />
            </button>
            {tab !== "Coding stats" && (
              <strong>{tab === "Chat" ? "Orbit" : tab}</strong>
            )}
          </span>
          <span className="private-label">
            {demoMode ? "Demo workspace" : "Private workspace"}
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
            initialDraft={projectPrompt}
            onInitialDraftUsed={() => setProjectPrompt("")}
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
            <CodingDashboard
              hackathonCount={data?.hackathons?.length || null}
              demoMode={demoMode}
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
            onChat={(p, prompt = "") => {
              setProject(p);
              setProjectPrompt(prompt);
              openTab("Chat");
            }}
          />
        )}
      </main>
      {showSettings && (
        <SettingsModal
          theme={theme}
          onThemeChange={changeTheme}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  );
}
