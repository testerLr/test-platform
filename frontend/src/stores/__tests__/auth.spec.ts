import { setActivePinia, createPinia } from "pinia";
import { useAuthStore } from "@/stores/auth";

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("starts logged out", () => {
    const s = useAuthStore();
    expect(s.token).toBeNull();
    expect(s.me).toBeNull();
  });

  it("logout clears state", () => {
    const s = useAuthStore();
    s.token = "abc";
    s.me = { id: 1, username: "u", is_admin: false };
    s.logout();
    expect(s.token).toBeNull();
    expect(s.me).toBeNull();
  });
});