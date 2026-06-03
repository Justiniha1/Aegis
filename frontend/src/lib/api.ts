import type { Run, RunTriggerResponse, ProfileOut, Schedule, ScheduleCreate, ScheduleUpdate } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request(method: string, path: string, token?: string, body?: unknown) {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

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

/* ── Phase 2 — Run + Profile wrappers ────────────────────────────────── */
/* All wrappers thread the JWT via the existing apiGet/apiPost primitives.
   Consumers (TopBar dropdown, row triggers, polling hook) call these instead
   of the raw apiGet/apiPost with hardcoded paths — keeps the path strings
   in one place if the backend ever renames an endpoint. */

export async function triggerRun(
  profile: string,
  typeFilter: string[] | null,
  token: string,
): Promise<RunTriggerResponse> {
  return apiPost(
    "/api/v1/runs",
    { profile, type_filter: typeFilter },
    token,
  ) as Promise<RunTriggerResponse>;
}

export async function getRun(runId: number, token: string): Promise<Run> {
  return apiGet(`/api/v1/runs/${runId}`, token) as Promise<Run>;
}

export async function listRuns(limit: number, token: string): Promise<Run[]> {
  return apiGet(`/api/v1/runs?limit=${limit}`, token) as Promise<Run[]>;
}

export async function listProfiles(token: string): Promise<ProfileOut[]> {
  return apiGet("/api/v1/profiles", token) as Promise<ProfileOut[]>;
}

/* ── Phase 9 — Schedule wrappers ──────────────────────────────────────── */

export async function listSchedules(token: string): Promise<Schedule[]> {
  return apiGet("/api/v1/schedules", token) as Promise<Schedule[]>;
}

export async function createSchedule(body: ScheduleCreate, token: string): Promise<Schedule> {
  return apiPost("/api/v1/schedules", body, token) as Promise<Schedule>;
}

export async function updateSchedule(id: number, body: ScheduleUpdate, token: string): Promise<Schedule> {
  return request("PATCH", `/api/v1/schedules/${id}`, token, body) as Promise<Schedule>;
}

export async function deleteSchedule(id: number, token: string): Promise<void> {
  await apiDelete(`/api/v1/schedules/${id}`, token);
}
