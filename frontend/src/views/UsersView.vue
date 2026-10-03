<template>
  <el-page-header title="用户管理" />
  <el-button type="primary" @click="openCreate">新建用户</el-button>
  <el-table :data="users" style="margin-top:16px">
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="username" label="用户名" />
    <el-table-column label="管理员" width="100"><template #default="{ row }"><el-tag :type="row.is_admin ? 'success' : 'info'">{{ row.is_admin ? '是' : '否' }}</el-tag></template></el-table-column>
    <el-table-column label="启用" width="100"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '是' : '否' }}</el-tag></template></el-table-column>
    <el-table-column label="操作" width="200">
      <template #default="{ row }">
        <el-button link @click="toggleActive(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
        <el-button link @click="resetPwd(row)">重置密码</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="createOpen" title="新建用户" width="420">
    <el-form :model="createForm">
      <el-form-item label="用户名"><el-input v-model="createForm.username" /></el-form-item>
      <el-form-item label="密码"><el-input v-model="createForm.password" type="password" show-password /></el-form-item>
      <el-form-item label="管理员"><el-switch v-model="createForm.is_admin" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createOpen = false">取消</el-button>
      <el-button type="primary" @click="create">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="resetOpen" title="重置密码" width="420">
    <el-form :model="resetForm"><el-form-item label="新密码"><el-input v-model="resetForm.new_password" type="password" show-password /></el-form-item></el-form>
    <template #footer>
      <el-button @click="resetOpen = false">取消</el-button>
      <el-button type="primary" @click="doReset">提交</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { http } from "@/api/http";

interface User { id: number; username: string; is_admin: boolean; is_active: boolean }

const users = ref<User[]>([]);
const createOpen = ref(false);
const createForm = reactive({ username: "", password: "", is_admin: false });
const resetOpen = ref(false);
const resetForm = reactive({ id: 0, new_password: "" });

async function refresh() { users.value = (await http.get<User[]>("/users")).data; }
function openCreate() { Object.assign(createForm, { username: "", password: "", is_admin: false }); createOpen.value = true; }
async function create() {
  await http.post("/users", createForm);
  createOpen.value = false;
  await refresh();
  ElMessage.success("已创建");
}
async function toggleActive(u: User) {
  await http.patch(`/users/${u.id}`, { is_active: !u.is_active });
  await refresh();
}
function resetPwd(u: User) {
  resetForm.id = u.id; resetForm.new_password = ""; resetOpen.value = true;
}
async function doReset() {
  await http.post(`/users/${resetForm.id}/reset-password`, { new_password: resetForm.new_password });
  resetOpen.value = false;
  ElMessage.success("已重置");
}
onMounted(refresh);
</script>
