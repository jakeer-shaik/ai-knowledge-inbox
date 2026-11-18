/**
 * HTTP client for the FastAPI backend.
 * All network access and error parsing lives here; components never call fetch directly.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  constructor(message, { status = 0, code = "UNKNOWN", details = null, requestId = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

async function request(path, { method = "GET", body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      signal,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError("Can't reach the server. Check that the backend is running on port 8000.", {
      code: "NETWORK_ERROR",
    });
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const error = data?.error;
    throw new ApiError(error?.message ?? `Request failed with HTTP ${response.status}.`, {
      status: response.status,
      code: error?.code ?? "HTTP_ERROR",
      details: error?.details ?? null,
      requestId: error?.request_id ?? null,
    });
  }
  return data;
}

export const httpApi = {
  health: () => request("/health"),
  listItems: () => request("/items").then((data) => data.items),
  /** payload: { type: "note", content } | { type: "url", url } */
  ingest: (payload) => request("/ingest", { method: "POST", body: payload }).then((data) => data.item),
  /**
   * payload: { question, conversation_id? } -> the new turn:
   * { id, conversation_id, question, search_query, answer, sources: [...], created_at }
   */
  query: (payload, { signal } = {}) => request("/query", { method: "POST", body: payload, signal }),
  listConversations: () => request("/conversations").then((data) => data.conversations),
  getConversation: (id, { signal } = {}) => request(`/conversations/${encodeURIComponent(id)}`, { signal }),
  deleteConversation: (id) => request(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
