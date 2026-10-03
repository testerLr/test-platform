import { http } from "@/api/http";

export interface Mock {
  id: number; project_id: number; name: string;
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH" | "HEAD" | "OPTIONS";
  path: string; enabled: boolean;
  request_match: { query?: Record<string,string>; headers?: Record<string,string>; body_contains?: string; body_jsonpath?: string } | null;
  response_status: number;
  response_headers: Record<string,string> | null;
  response_body: string;
  delay_ms: number; description: string | null;
}

export const mocksApi = {
  list: (projectId?: number) => http.get<Mock[]>("/mocks", { params: { project_id: projectId } }).then((r) => r.data),
  remove: (id: number) => http.delete(`/mocks/${id}`),
};