<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <h3 class="logo">Test Platform</h3>
      <el-menu :default-active="route.path" router>
        <el-menu-item index="/projects">项目</el-menu-item>
        <el-menu-item index="/mocks">Mock 接口</el-menu-item>
        <el-menu-item v-if="auth.me?.is_admin" index="/users">用户管理</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="grow"></span>
        <span>{{ auth.me?.username }}</span>
        <el-button link @click="onLogout">退出</el-button>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

function onLogout() {
  auth.logout();
  router.push("/login");
}
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #001529; color: #fff; }
.logo { color: #fff; padding: 16px; }
.header { display: flex; align-items: center; border-bottom: 1px solid #eee; }
.grow { flex: 1; }
</style>