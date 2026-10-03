import { http } from "@/api/http";

export interface Project { id: number; name: string; description: string | null }
export interface Member { user_id: number; username: string; role: "owner" | "developer" | "viewer" }

export const projectsApi = {
  list: () => http.get<Project[]>("/projects").then((r) => r.data),
  get: (id: number) => http.get<Project>(`/projects/${id}`).then((r) => r.data),
  create: (body: { name: string; description?: string }) =>
    http.post<Project>("/projects", body).then((r) => r.data),
  update: (id: number, body: Partial<Project>) =>
    http.patch<Project>(`/projects/${id}`, body).then((r) => r.data),
  remove: (id: number) => http.delete(`/projects/${id}`),
  members: (id: number) => http.get<Member[]>(`/projects/${id}/members`).then((r) => r.data),
  addMember: (id: number, body: { user_id: number; role: Member["role"] }) =>
    http.post<Member>(`/projects/${id}/members`, body).then((r) => r.data),
  updateMember: (id: number, userId: number, body: { role: Member["role"] }) =>
    http.patch<Member>(`/projects/${id}/members/${userId}`, body).then((r) => r.data),
  removeMember: (id: number, userId: number) =>
    http.delete(`/projects/${id}/members/${userId}`),
};