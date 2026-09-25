import { useEffect, useRef, useState } from "react";
import { ArrowUp, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, post } from "./api";
import EvidenceList from "./Evidence";
import "./chat.css";

export default function PersonalChat({
  demoMode,
  name,
  project,
  onClearProject,
  chatId,
  onChatChanged,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState("");
  const bottom = useRef(null),
    composer = useRef(null);

  useEffect(() => {
    if (!chatId) {
      setMessages([]);
      setError("");
      return;
    }
    const c = new AbortController();
    setLoading(true);
    setMessages([]);
    api(`/personal/chats/${chatId}/messages`, { signal: c.signal })
      .then((r) => {
        setMessages(r.history);
        setError("");
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [chatId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages, pending]);

  async function send(e) {
    e.preventDefault();
    const message = input.trim();
    if (!message || busy || loading) return;
    // Auto-create a chat session if none exists
    let activeChatId = chatId;
    if (!activeChatId) {
      try {
        const session = await post("/personal/chats", {});
        activeChatId = session.id;
        onChatChanged?.(session.id);
      } catch (e) {
        setError(e.message);
        return;
      }
    }
    setPending(message);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const r = await post(`/personal/chats/${activeChatId}/messages`, {
        message,
        project_id: project?.id ?? null,
      });
      setMessages((m) => [
        ...m,
        { role: "user", content: message },
        {
          role: "assistant",
          content: r.answer,
          sources: r.sources,
          tools: r.tools_called,
          cache: r.cache_hits,
        },
      ]);
      onChatChanged?.();
    } catch (e) {
      setInput(message);
      setError(e.message);
    } finally {
      setBusy(false);
      setPending("");
    }
  }

  async function clear() {
    if (!chatId) return;
    if (
      !window.confirm(
        "Clear this conversation? Your learning records will be kept.",
      )
    )
      return;
    setBusy(true);
    try {
      await api(`/personal/chats/${chatId}/messages`, { method: "DELETE" });
      setMessages([]);
      setError("");
      onChatChanged?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const prompts = [
    "What should I focus on next?",
    "Compare my latest marks",
    "Help me plan a revision session",
    "Review my practice results",
  ];

  return (
    <section className="personal-chat" aria-label="Chat with Orbit">
      <div className="chat-heading">
        <span>
          <img src="/orbit-mark.svg" alt="" /> Orbit{" "}
          <small>Your learning assistant</small>
        </span>
        <button
          onClick={clear}
          disabled={busy || loading || !messages.length || !chatId}
          title="Clear conversation"
          aria-label="Clear conversation"
        >
          <Trash2 size={17} />
        </button>
      </div>
      {demoMode && (
        <p className="chat-demo-note">
          Local demo · rule-based replies · no live AI connection
        </p>
      )}
      {project && (
        <div className="project-context">
          <span>
            Chatting about <strong>{project.name}</strong>
          </span>
          <button type="button" onClick={onClearProject}>
            All workspace
          </button>
        </div>
      )}
      <div
        className="chat-scroll"
        role="log"
        aria-label="Conversation"
        aria-live="polite"
        aria-busy={busy || loading}
      >
        {loading ? (
          <p role="status">Loading conversation…</p>
        ) : (
          !messages.length &&
          !pending && (
            <div className="chat-welcome">
              <h1>What's on your mind, {name?.split(" ")[0]}?</h1>
              <p>
                Ask a question, make a study plan, or work through your next
                step.
              </p>
              <div className="chat-starters">
                {prompts.map((p) => (
                  <button
                    key={p}
                    onClick={() => {
                      setInput(p);
                      composer.current?.focus();
                    }}
                  >
                    {p}
                    <ArrowUp size={15} />
                  </button>
                ))}
              </div>
            </div>
          )
        )}
        <div className="chat-thread">
          {messages.map((m, i) => (
            <article key={i} className={`chat-message ${m.role}`}>
              <span className="sr-only">
                {m.role === "user" ? "You" : "Orbit"}
              </span>
              <div className="chat-message-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {m.content}
                </ReactMarkdown>
                <EvidenceList sources={m.sources} />
                {m.tools?.length > 0 && (
                  <small className="tool-summary">
                    Used {m.tools.length} tool calls
                    {m.cache > 0 ? ` · ${m.cache} cached` : ""}
                  </small>
                )}
              </div>
            </article>
          ))}
          {pending && (
            <>
              <article className="chat-message user">
                <div className="chat-message-body">{pending}</div>
              </article>
              <p className="chat-thinking" role="status">
                Orbit is reading your records…
              </p>
            </>
          )}
          <div ref={bottom} />
        </div>
      </div>
      <div className="chat-compose-area">
        {error && (
          <div role="alert" className="error">
            {error}
          </div>
        )}
        <form onSubmit={send} className="chat-composer">
          <label className="sr-only" htmlFor="orbit-message">
            Message
          </label>
          <textarea
            id="orbit-message"
            ref={composer}
            value={input}
            rows={2}
            maxLength={2000}
            disabled={busy || loading}
            onChange={(e) => setInput(e.target.value)}
            placeholder={chatId ? "Message Orbit…" : "Message Orbit…"}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                e.currentTarget.form.requestSubmit();
              }
            }}
          />
          <div className="chat-composer-bottom">
            <span>Your records give Orbit context</span>
            <button
              type="submit"
              className="primary"
              aria-label="Ask Orbit"
              disabled={busy || loading || !input.trim()}
            >
              <ArrowUp size={21} />
            </button>
          </div>
        </form>
        <p className="chat-disclaimer">
          Check the supporting records. Orbit can make mistakes.{" "}
          <span>Shift + Enter for a new line.</span>
        </p>
      </div>
    </section>
  );
}
