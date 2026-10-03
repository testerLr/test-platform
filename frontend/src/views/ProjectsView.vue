<template>
  <div>
    <el-page-header title="项目" />
    <el-button type="primary" @click="$router.push('/projects/new')">新建项目</el-button>
    <el-table :data="projects" style="width:100%;margin-top:16px">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="description" label="描述" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link @click="$router.push(`/projects/${row.id}`)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { projectsApi, Project } from "@/api/projects";

const projects = ref<Project[]>([]);
onMounted(async () => { projects.value = await projectsApi.list(); });
</script>