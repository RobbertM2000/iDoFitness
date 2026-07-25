/**
 * Thin fetch wrapper (White Paper §11 / §10.2).
 * - Always sends credentials so the session cookie is included.
 * - Parses the backend's single error envelope:
 *     {"error": {"code": "...", "message": "...", "fields": {...}}}
 * - Throws an ApiError so callers can branch on `.fields` for inline
 *   form errors vs `.message` for a generic toast.
 */

export class ApiError extends Error {
  constructor(message, { code, fields, status } = {}) {
    super(message);
    this.code = code;
    this.fields = fields || {};
    this.status = status;
  }
}

async function request(path, { method = "GET", body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const err = data?.error;
    throw new ApiError(err?.message || "Er ging iets mis", {
      code: err?.code,
      fields: err?.fields,
      status: res.status,
    });
  }

  return data;
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  delete: (path) => request(path, { method: "DELETE" }),
};
