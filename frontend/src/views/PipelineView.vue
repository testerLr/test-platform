<template>
  <el-page-header :title="pipeline?.name || '流水线'" @back="$router.push(`/projects/${pipeline?.project_id}`)" />
  <div style="margin: 8px 0">
    <el-button type="primary" @click="runIt" :loading="running">运行</el-button>
    <el-button @click="$router.push(`/pipelines/${pipelineId}/edit`)">编辑</el-button>
    <el-popconfirm title="确认删除?" @confirm="removePipeline">
      <template #reference><el-button type="danger" link>删除</el-button></template>
    </el-popconfirm>
  </div>
  <div style="margin: 8px 0">
    描述: {{ pipeline?.description || "—" }}
  </div>

  <h3>步骤</h3>
  <el-table :data="steps">
    <el-table-column prop="order_index" label="#" width="60" />
    <el-table-column prop="type" label="类型" width="100" />
    <el-table-column prop="name" label="名称" />
    <el-table-column label="启用" width="80">
      <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "是" : "否" }}</el-tag></template>
    </el-table-column>
    <el-table-column label="操作" width="200">
      <template #default="{ row }">
        <el-button link @click="$router.push(`/pipelines/${pipelineId}/steps/${row.id}`)">编辑</el-button>
        <el-popconfirm title="删除步骤?" @confirm="removeStep(row.id)">
          <template #reference><el-button link type="danger">删除</el-button></template>
        </el-popconfirm>
      </template>
    </el-table-column>
  </el-table>
  <el-button @click="$router.push(`/pipelines/${pipelineId}/steps/new`)">+ 添加步骤</el-button>

  <h3 style="margin-top:24px">运行历史(最近 30 条)</h3>
  <el-table :data="runs">
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column label="状态" width="100">
      <template #default="{ row }"><el-tag :type="row.status === 'success' ? 'success' : (row.status === 'failed' ? 'danger' : '')">{{ row.status }}</el-tag></template>
    </el-table-column>
    <el-table-column prop="started_at" label="开始时间" />
    <el-table-column label="成功/失败/跳过">
      <template #default="{ row }">{{ row.success_count }} / {{ row.failure_count }} / {{ row.skipped_count }}</template>
    </el-table-column>
    <el-table-column label="操作" width="100">
      <template #default="{ row }"><el-button link @click="$router.push(`/runs/${row.id}`)">查看</el-button></template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { pipelinesApi, Pipeline, Step, Run } from "@/api/pipelines";

const route = useRoute();
const router = useRouter();
const pipelineId = Number(route.params.id);
const pipeline = ref<Pipeline | null>(null);
const steps = ref<Step[]>([]);
const runs = ref<Run[]>([]);
const running = ref(false);

async function refresh() {
  pipeline.value = await pipelinesApi.get(pipelineId);
  steps.value = await pipelinesApi.steps(pipelineId);
  runs.value = await pipelinesApi.runs(pipelineId);
}

async function runIt() {
  running.value = true;
  try {
    const run = await pipelinesApi.run(pipelineId);
    await refresh();
    ElMessage.success(`运行 ${run.status}`);
    router.push(`/runs/${run.id}`);
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "运行失败");
  } finally {
    running.value = false;
  }
}

async function removePipeline() {
  await pipelinesApi.remove(pipelineId);
  ElMessage.success("已删除");
  router.push(`/projects/${pipeline.value?.project_id}`);
}

async function removeStep(id: number) {
  await pipelinesApi.removeStep(pipelineId, id);
  await refresh();
}

onMounted(refresh);
</script>