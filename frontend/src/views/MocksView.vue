<template>
  <el-page-header title="Mock 接口" />
  <el-button type="primary" @click="$router.push('/mocks/new')">新建 Mock</el-button>
  <el-table :data="mocks" style="margin-top:16px">
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="project_id" label="项目" width="80" />
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
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { mocksApi, Mock } from "@/api/mocks";

const mocks = ref<Mock[]>([]);
async function refresh() { mocks.value = await mocksApi.list(); }
async function remove(id: number) { await mocksApi.remove(id); await refresh(); ElMessage.success("已删除"); }
onMounted(refresh);
</script>
