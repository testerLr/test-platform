<template>
  <el-page-header :title="project?.name || '项目'" @back="$router.push('/projects')" />
  <el-tabs v-model="tab">
    <el-tab-pane label="Mock 列表" name="mocks">
      <el-button type="primary" @click="$router.push(`/mocks/new?project_id=${projectId}`)">新建 Mock</el-button>
      <el-table :data="mocks">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="method" label="方法" width="100" />
        <el-table-column prop="path" label="路径" />
        <el-table-column label="启用" width="100">
          <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/mocks/${row.id}`)">编辑</el-button>
            <el-popconfirm title="确认删除?" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
    <el-tab-pane label="成员管理" name="members">
      <el-select v-model="newUserId" placeholder="选择用户" filterable>
        <el-option v-for="u in allUsers" :key="u.id" :label="u.username" :value="u.id" />
      </el-select>
      <el-select v-model="newRole" placeholder="角色" style="width:120px;margin-left:8px">
        <el-option label="developer" value="developer" />
        <el-option label="viewer" value="viewer" />
      </el-select>
      <el-button @click="addMember">添加</el-button>
      <el-table :data="members" style="margin-top:16px">
        <el-table-column prop="user_id" label="用户ID" width="100" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="role" label="角色" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link @click="removeMember(row.user_id)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { projectsApi, Member } from "@/api/projects";
import { mocksApi, Mock } from "@/api/mocks";
import { http } from "@/api/http";

const route = useRoute();
const projectId = Number(route.params.id);
const project = ref<{ id: number; name: string } | null>(null);
const tab = ref("mocks");
const mocks = ref<Mock[]>([]);
const members = ref<Member[]>([]);
const allUsers = ref<{ id: number; username: string }[]>([]);
const newUserId = ref<number | null>(null);
const newRole = ref<Member["role"]>("developer");

async function refresh() {
  project.value = await projectsApi.get(projectId);
  mocks.value = await mocksApi.list(projectId);
  members.value = await projectsApi.members(projectId);
}

async function loadUsers() {
  try {
    allUsers.value = (await http.get("/users")).data;
  } catch { /* non-admin */ }
}

async function addMember() {
  if (!newUserId.value) return;
  await projectsApi.addMember(projectId, { user_id: newUserId.value, role: newRole.value });
  await refresh();
  ElMessage.success("已添加");
}

async function removeMember(uid: number) {
  await projectsApi.removeMember(projectId, uid);
  await refresh();
}

async function remove(id: number) {
  await mocksApi.remove(id);
  await refresh();
}

onMounted(async () => { await refresh(); await loadUsers(); });
</script>