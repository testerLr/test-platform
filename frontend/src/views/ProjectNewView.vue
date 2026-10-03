<template>
  <el-page-header title="新建项目" @back="$router.push('/projects')" />
  <el-form :model="form" label-width="80px" style="max-width:480px">
    <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
    <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
    <el-button type="primary" :loading="loading" @click="submit">创建</el-button>
  </el-form>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { projectsApi } from "@/api/projects";

const router = useRouter();
const form = reactive({ name: "", description: "" });
const loading = ref(false);

async function submit() {
  loading.value = true;
  try {
    const p = await projectsApi.create({ name: form.name, description: form.description || undefined });
    router.push(`/projects/${p.id}`);
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || "创建失败"); }
  finally { loading.value = false; }
}
</script>