import { useEffect, useRef, useState } from "react";
import { ArrowUp, Sparkles, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, post } from "./api";
import EvidenceList from "./Evidence";
import "./chat.css";

export default function PersonalChat({ demoMode, name }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pending, setPending] = useState("");
  const [retry, setRetry] = useState(0);
  const bottom = useRef(null),
    composer = useRef(null);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    api("/personal/chat", { signal: c.signal })
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
  }, [retry]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages, pending]);
  async function send(e) {
    e.preventDefault();
    const message = input.trim();
    if (!message || busy || loading) return;
    setPending(message);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const r = await post("/personal/chat", { message });
      setMessages((m) => [
        ...m,
        { role: "user", content: message },
        { role: "assistant", content: r.answer, sources: r.sources },
      ]);
    } catch (e) {
      setInput(message);
      setError(e.message);
    } finally {
      setBusy(false);
      setPending("");
    }
  }
  async function clear() {
    if (
      !window.confirm(
        "Clear this session's conversation? Your learning records will be kept.",
      )
    )
      return;
    setBusy(true);
    try {
      await api("/personal/chat", { method: "DELETE" });
      setMessages([]);
      setError("");
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
          <Sparkles size={18} /> Orbit <small>Your learning assistant</small>
        </span>
        <button
          onClick={clear}
          disabled={busy || loading || !messages.length}
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
              <span className="chat-orbit">◌</span>
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
            {error}{" "}
            <button
              disabled={busy || loading}
              onClick={() => setRetry((n) => n + 1)}
            >
              Reload conversation
            </button>
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
            placeholder="Message Orbit…"
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
