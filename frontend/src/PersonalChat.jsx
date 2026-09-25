import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";
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
  initialDraft,
  onInitialDraftUsed,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState("");
  const [streaming, setStreaming] = useState(false);
  const generation = useRef(0);
  const createdChat = useRef(null);
  const streamTimer = useRef(null);
  const scrollArea = useRef(null);
  const followBottom = useRef(true);
  const bottom = useRef(null),
    composer = useRef(null);

  useEffect(() => {
    if (createdChat.current === chatId && chatId) {
      createdChat.current = null;
      return;
    }
    generation.current += 1;
    clearInterval(streamTimer.current);
    setStreaming(false);
    setBusy(false);
    setPending("");
    setLoading(false);
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

  useEffect(
    () => () => {
      generation.current += 1;
      clearInterval(streamTimer.current);
    },
    [],
  );

  useEffect(() => {
    if (followBottom.current && scrollArea.current) {
      scrollArea.current.scrollTop = scrollArea.current.scrollHeight;
    }
  }, [messages, pending]);

  useEffect(() => {
    if (!initialDraft) return;
    setInput(initialDraft);
    composer.current?.focus();
    onInitialDraftUsed?.();
  }, [initialDraft, onInitialDraftUsed]);

  async function send(e) {
    e.preventDefault();
    const message = input.trim();
    if (!message || busy || loading) return;
    const request = ++generation.current;
    setBusy(true);
    followBottom.current = true;
    // Auto-create a chat session if none exists
    let activeChatId = chatId;
    if (!activeChatId) {
      try {
        const session = await post("/personal/chats", {});
        if (request !== generation.current) return;
        activeChatId = session.id;
        createdChat.current = session.id;
        onChatChanged?.(session.id);
      } catch (e) {
        if (request !== generation.current) return;
        setError(e.message);
        setBusy(false);
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
      if (request !== generation.current) return;
      const animate =
        demoMode &&
        !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      setPending("");
      setMessages((m) => [
        ...m,
        { role: "user", content: message },
        {
          role: "assistant",
          content: animate ? "" : r.answer,
          sources: r.sources,
          tools: r.tools_called,
          cache: r.cache_hits,
        },
      ]);
      onChatChanged?.();
      if (animate) {
        setStreaming(true);
        const words = r.answer.match(/\S+\s*|\s+/g) || [];
        let index = 0;
        let text = "";
        streamTimer.current = setInterval(() => {
          if (request !== generation.current) {
            clearInterval(streamTimer.current);
            return;
          }
          text += words[index++] || "";
          setMessages((m) =>
            m.map((item, i) =>
              i === m.length - 1 ? { ...item, content: text } : item,
            ),
          );
          if (index >= words.length) {
            clearInterval(streamTimer.current);
            setStreaming(false);
            setBusy(false);
          }
        }, 30);
      } else setBusy(false);
    } catch (e) {
      if (request !== generation.current) return;
      setInput(message);
      setError(e.message);
      setBusy(false);
      setPending("");
    }
  }

  const prompts = [
    "Tell about my Study room finder project",
    "Show my development and DSA coding stats together",
    ...(project
      ? [
          `Quiz me on the architecture of ${project.name}`,
          `Ask me five questions about files in ${project.name}`,
        ]
      : []),
    "What should I focus on next?",
    "Help me plan a revision session",
  ];

  return (
    <section className="personal-chat" aria-label="Chat with Orbit">
      <div className="chat-heading">
        <span>
          <img src="/orbit-mark.svg" alt="" /> Orbit{" "}
          <small>Your learning assistant</small>
        </span>
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
        ref={scrollArea}
        onScroll={(e) => {
          const el = e.currentTarget;
          followBottom.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
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
                {!(streaming && i === messages.length - 1) && (
                  <EvidenceList sources={m.sources} />
                )}
                {!(streaming && i === messages.length - 1) &&
                  m.tools?.length > 0 && (
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
