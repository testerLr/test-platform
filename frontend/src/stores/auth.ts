import { defineStore } from "pinia";
import { ref } from "vue";
import { http } from "@/api/http";

interface Me { id: number; username: string; is_admin: boolean }

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(localStorage.getItem("token"));
  const me = ref<Me | null>(null);

  async function login(username: string, password: string): Promise<void> {
    const r = await http.post("/auth/login", { username, password });
    const accessToken: string = r.data.access_token;
    token.value = accessToken;
    localStorage.setItem("token", accessToken);
    await fetchMe();
  }

  async function fetchMe(): Promise<void> {
    if (!token.value) { me.value = null; return; }
    const r = await http.get<Me>("/auth/me");
    me.value = r.data;
  }

  function logout(): void {
    token.value = null;
    me.value = null;
    localStorage.removeItem("token");
  }

  return { token, me, login, fetchMe, logout };
});