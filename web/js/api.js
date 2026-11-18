// Tiny JSON API client. Relative paths only, so the app also works inside a Telegram Mini App later.
let demoRole = "patient";

export function setRole(role) { demoRole = role; }
export function getRole() { return demoRole; }

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function api(path, { method = "GET", body, role, form, signal } = {}) {
  const headers = { "X-Demo-Role": role || demoRole };
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  let res;
  try {
    res = await fetch(path, { method, headers, body: payload, signal });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError("Server bilan aloqa yo'q. Internet yoki serverni tekshiring.", 0);
  }
  let data = null;
  const text = await res.text();
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!res.ok) {
    const msg = (data && (typeof data.detail === "string" ? data.detail : null)) || `Xatolik (${res.status})`;
    throw new ApiError(msg, res.status);
  }
  return data;
}
