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
