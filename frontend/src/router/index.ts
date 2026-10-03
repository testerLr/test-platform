import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/views/LoginView.vue") },
    { path: "/", component: () => import("@/views/HomeView.vue") }
  ]
});

export default router;