<template>
  <el-page-header :title="`运行 #${runId}`" @back="$router.back()" />
  <div v-if="run" style="margin: 8px 0">
    <el-tag :type="run.status === 'success' ? 'success' : (run.status === 'failed' ? 'danger' : '')">{{ run.status }}</el-tag>
    总计 {{ run.total_steps }} 步 | 成功 {{ run.success_count }} / 失败 {{ run.failure_count }} / 跳过 {{ run.skipped_count }}
    <span style="margin-left: 16px">{{ run.started_at }} → {{ run.finished_at }}</span>
  </div>

  <h3>每步详情</h3>
  <el-table :data="run?.steps || []">
    <el-table-column prop="order_index" label="#" width="60" />
    <el-table-column prop="status" label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="row.status === 'success' ? 'success' : (row.status === 'failed' ? 'danger' : (row.status === 'skipped' ? 'info' : ''))">{{ row.status }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="duration_ms" label="耗时(ms)" width="120" />
    <el-table-column label="输入(渲染后)">
      <template #default="{ row }">
        <el-popover v-if="row.input_rendered" placement="left" :width="500" trigger="click">
          <template #reference><el-button link>查看</el-button></template>
          <pre>{{ JSON.stringify(row.input_rendered, null, 2) }}</pre>
        </el-popover>
        <span v-else>—</span>
      </template>
    </el-table-column>
    <el-table-column label="输出">
      <template #default="{ row }">
        <el-popover v-if="row.output" placement="left" :width="500" trigger="click">
          <template #reference>
            <el-button link @click="copy(row.output)">查看/复制</el-button>
          </template>
          <pre>{{ JSON.stringify(row.output, null, 2) }}</pre>
        </el-popover>
        <span v-else>—</span>
      </template>
    </el-table-column>
    <el-table-column prop="error" label="错误" />
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { pipelinesApi, RunDetail } from "@/api/pipelines";

const route = useRoute();
const runId = Number(route.params.id);
const run = ref<RunDetail | null>(null);

async function refresh() {
  run.value = await pipelinesApi.getRun(runId);
}
async function copy(obj: any) {
  await navigator.clipboard.writeText(JSON.stringify(obj));
  ElMessage.success("已复制");
}
onMounted(refresh);
</script>