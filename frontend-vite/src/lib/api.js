const API_BASE = localStorage.getItem("envy.apiBase") || "http://127.0.0.1:8765";

export function apiBase() {
  return API_BASE;
}

export async function apiJson(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = localStorage.getItem("envy.dashboardToken") || "";
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.hint || body.error || `HTTP ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

export function postJson(path, body) {
  return apiJson(path, { method: "POST", body: JSON.stringify(body || {}) });
}

export function putJson(path, body) {
  return apiJson(path, { method: "PUT", body: JSON.stringify(body || {}) });
}

export function deleteJson(path) {
  return apiJson(path, { method: "DELETE" });
}
