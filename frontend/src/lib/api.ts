const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request(method: string, path: string, token?: string, body?: unknown) {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }

  if (res.status === 204) return;
  return res.json();
}

export const apiGet = (path: string, token?: string) => request("GET", path, token);
export const apiPost = (path: string, body: unknown, token?: string) => request("POST", path, token, body);
export const apiPut = (path: string, body: unknown, token?: string) => request("PUT", path, token, body);
export const apiDelete = (path: string, token?: string) => request("DELETE", path, token);

/** Fetch a plain-text response (e.g. the YAML editor endpoint). */
export async function apiGetText(path: string, token?: string): Promise<string> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.text();
}
