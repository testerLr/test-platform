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

export interface MockCreate extends Omit<Mock, "id" | "request_match" | "response_headers"> {
  request_match?: Mock["request_match"];
  response_headers?: Record<string,string>;
}

export interface MockTestRequest {
  method: Mock["method"]; path: string;
  headers: Record<string,string>; query: Record<string,string>;
  body: string | null;
}
export interface MockTestResponse { status: number; headers: Record<string,string>; body: string }

export const mocksApi = {
  list: (projectId?: number) => http.get<Mock[]>("/mocks", { params: { project_id: projectId } }).then((r) => r.data),
  get: (id: number) => http.get<Mock>(`/mocks/${id}`).then((r) => r.data),
  create: (body: MockCreate) => http.post<Mock>("/mocks", body).then((r) => r.data),
  update: (id: number, body: Partial<MockCreate>) => http.patch<Mock>(`/mocks/${id}`, body).then((r) => r.data),
  remove: (id: number) => http.delete(`/mocks/${id}`),
  test: (id: number, body: MockTestRequest) => http.post<MockTestResponse>(`/mocks/${id}/test`, body).then((r) => r.data),
};
