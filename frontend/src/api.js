const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(
  /\/$/,
  "",
);

export async function api(path, options = {}) {
  const { timeout = 120000, signal, ...request } = options;
  const controller = new AbortController();
  const abort = () => controller.abort(signal.reason);
  if (signal?.aborted) abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(API_BASE + path, {
      credentials: "include",
      ...request,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...request.headers },
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error(
        typeof data?.detail === "string"
          ? data.detail
          : "Orbit is temporarily unavailable. Please try again.",
      );
      error.status = response.status;
      if (response.status === 401 && path !== "/session")
        window.dispatchEvent(new Event("orbit:session-expired"));
      throw error;
    }
    if (data === null)
      throw new Error(
        "Orbit returned an unexpected response. Please try again.",
      );
    return data;
  } catch (error) {
    if (signal?.aborted) throw error;
    if (controller.signal.aborted)
      throw new Error("This request took too long. Please try again.");
    if (error instanceof TypeError)
      throw new Error(
        "Cannot reach Orbit. Check your internet connection and try again.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

export const post = (path, data) =>
  api(path, { method: "POST", body: JSON.stringify(data) });

export async function wakeServer(signal) {
  const deadline = Date.now() + 120000;
  while (!signal.aborted && Date.now() < deadline) {
    try {
      const health = await api("/health", {
        signal,
        timeout: Math.min(12000, deadline - Date.now()),
      });
      if (health.status === "ok") return health;
    } catch (error) {
      if (signal.aborted) throw error;
      if (error.status && error.status < 500 && error.status !== 429)
        throw error;
    }
    await new Promise((resolve) => {
      const done = () => {
        clearTimeout(timer);
        signal.removeEventListener("abort", done);
        resolve();
      };
      const timer = setTimeout(
        done,
        Math.min(2000, Math.max(0, deadline - Date.now())),
      );
      signal.addEventListener("abort", done, { once: true });
    });
  }
  if (signal.aborted) throw new DOMException("Cancelled", "AbortError");
  throw new Error(
    "The server is taking longer than expected. Please try connecting again in a moment.",
  );
}
