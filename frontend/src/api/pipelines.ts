import { http } from "@/api/http";

export interface Pipeline {
  id: number; project_id: number; name: string;
  description: string | null; created_by: number;
  created_at: string; updated_at: string;
}

export interface Step {
  id: number; pipeline_id: number; order_index: number;
  type: "mysql" | "kafka" | "redis" | "http";
  name: string; enabled: boolean;
  config: Record<string, any>;
}

export interface Run {
  id: number; pipeline_id: number; triggered_by: number;
  status: "running" | "success" | "failed";
  started_at: string; finished_at: string | null;
  total_steps: number; success_count: number;
  failure_count: number; skipped_count: number;
}

export interface RunStep {
  id: number; run_id: number; step_id: number;
  order_index: number; status: string;
  started_at: string | null; finished_at: string | null;
  duration_ms: number | null;
  input_rendered: Record<string, any> | null;
  output: Record<string, any> | null;
  error: string | null;
}

export interface RunDetail extends Run {
  steps: RunStep[];
}

export const pipelinesApi = {
  list: (projectId: number) =>
    http.get<Pipeline[]>(`/pipelines`, { params: { project_id: projectId } }).then((r) => r.data),
  get: (id: number) =>
    http.get<Pipeline>(`/pipelines/${id}`).then((r) => r.data),
  create: (body: { project_id: number; name: string; description?: string }) =>
    http.post<Pipeline>(`/pipelines`, body).then((r) => r.data),
  update: (id: number, body: { name?: string; description?: string }) =>
    http.patch<Pipeline>(`/pipelines/${id}`, body).then((r) => r.data),
  remove: (id: number) => http.delete(`/pipelines/${id}`),
  steps: (pipelineId: number) =>
    http.get<Step[]>(`/pipelines/${pipelineId}/steps`).then((r) => r.data),
  addStep: (pipelineId: number, body: { type: Step["type"]; name: string; enabled?: boolean; config: Record<string, any> }) =>
    http.post<Step>(`/pipelines/${pipelineId}/steps`, body).then((r) => r.data),
  updateStep: (pipelineId: number, stepId: number, body: Partial<{ name: string; enabled: boolean; config: Record<string, any> }>) =>
    http.patch<Step>(`/pipelines/${pipelineId}/steps/${stepId}`, body).then((r) => r.data),
  removeStep: (pipelineId: number, stepId: number) =>
    http.delete(`/pipelines/${pipelineId}/steps/${stepId}`),
  reorder: (pipelineId: number, order: number[]) =>
    http.post<Step[]>(`/pipelines/${pipelineId}/steps/reorder`, { order }).then((r) => r.data),
  testStep: (pipelineId: number, stepId: number, body: { context: Record<string, any> }) =>
    http.post<{ ok: boolean; output?: any; error?: string; retryable?: boolean; rendered_config?: any }>(
      `/pipelines/${pipelineId}/steps/${stepId}/test`, body
    ).then((r) => r.data),
  run: (pipelineId: number) =>
    http.post<RunDetail>(`/pipelines/${pipelineId}/run`).then((r) => r.data),
  runs: (pipelineId: number) =>
    http.get<Run[]>(`/pipelines/${pipelineId}/runs`).then((r) => r.data),
  clearRuns: (pipelineId: number) => http.delete(`/pipelines/${pipelineId}/runs`),
  getRun: (runId: number) =>
    http.get<RunDetail>(`/runs/${runId}`).then((r) => r.data),
};
