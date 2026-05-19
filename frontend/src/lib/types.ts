export interface TestResult {
  id: number;
  test_id: string;
  test_name: string;
  test_type: string;
  status: string;
  severity: string;
  metrics: Record<string, unknown>;
  message: string;
  run_at: string;
  table: string | null;
  column: string | null;
}

export interface TestDefinition {
  id: number;
  name: string;
  description: string | null;
  type: string;
  severity: string;
  enabled: boolean;
  tags: string[];
  config: Record<string, unknown>;
  profile: string;
  created_at: string;
  updated_at: string;
}

export interface RunSummary {
  run_at: string;
  total: number;
  passed: number;
  failed: number;
  errors: number;
}

/* ── Phase 2 — Run lifecycle types ──────────────────────────────────── */

export type RunStatus = "QUEUED" | "RUNNING" | "COMPLETE" | "FAILED";
export type ResultStatus = "PASSED" | "FAILED" | "ERROR" | "SKIPPED" | "PENDING";

export interface RunErrorDetail {
  reason: string;
  at_test?: number | null;
}

export interface Run {
  id: number;
  client_id: number;
  profile: string;
  type_filter: string[] | null;
  status: RunStatus;
  total_tests: number;
  completed_tests: number;
  started_at: string;       // ISO timestamp
  completed_at: string | null;
  error: RunErrorDetail | null;
}

export interface RunTriggerResponse {
  run_id: number;
  total_tests: number;
  status: RunStatus;
}

export interface ProfileOut {
  name: string;
  is_default: boolean;
}
