import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/views/LoginView.vue"), meta: { public: true } },
    {
      path: "/",
      component: () => import("@/layouts/AppLayout.vue"),
      children: [
        { path: "", redirect: "/projects" },
        { path: "projects", component: () => import("@/views/ProjectsView.vue") },
        { path: "projects/new", component: () => import("@/views/ProjectNewView.vue") },
        { path: "projects/:id", component: () => import("@/views/ProjectDetailView.vue") },
        { path: "mocks", component: () => import("@/views/MocksView.vue") },
        { path: "mocks/new", component: () => import("@/views/MockEditView.vue") },
        { path: "mocks/:id", component: () => import("@/views/MockEditView.vue") },
        { path: "pipelines/:id", component: () => import("@/views/PipelineView.vue") },
        { path: "users", component: () => import("@/views/UsersView.vue"), meta: { adminOnly: true } }
      ]
    }
  ]
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.meta.public) return true;
  if (!auth.token) return { path: "/login", query: { redirect: to.fullPath } };
  if (!auth.me) await auth.fetchMe();
  if (to.meta.adminOnly && !auth.me?.is_admin) return { path: "/projects" };
  return true;
});

export default router;