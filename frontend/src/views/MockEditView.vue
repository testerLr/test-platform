<template>
  <el-page-header :title="isNew ? '新建 Mock' : '编辑 Mock'" @back="$router.back()" />
  <el-form :model="form" label-width="120px" style="max-width:760px">
    <el-form-item label="项目"><el-input-number v-model="form.project_id" :min="1" /></el-form-item>
    <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
    <el-form-item label="方法">
      <el-select v-model="form.method" style="width:140px">
        <el-option v-for="m in METHODS" :key="m" :value="m" :label="m" />
      </el-select>
    </el-form-item>
    <el-form-item label="路径"><el-input v-model="form.path" placeholder="如 /api/user/{id}" /></el-form-item>
    <el-form-item label="状态码"><el-input-number v-model="form.response_status" :min="100" :max="599" /></el-form-item>
    <el-form-item label="响应头 (JSON)"><el-input v-model="responseHeadersText" type="textarea" :rows="3" /></el-form-item>
    <el-form-item label="响应体"><el-input v-model="form.response_body" type="textarea" :rows="8" placeholder='{"id":"{{ request.path.id }}"}' /></el-form-item>
    <el-form-item label="延时(ms)"><el-input-number v-model="form.delay_ms" :min="0" :max="60000" /></el-form-item>
    <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
    <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
    <el-button type="primary" :loading="loading" @click="save">保存</el-button>
  </el-form>

  <el-divider />
  <h3>测试响应</h3>
  <el-form :model="testReq" label-width="100px" style="max-width:520px">
    <el-form-item label="Method">
      <el-select v-model="testReq.method" style="width:140px"><el-option v-for="m in METHODS" :key="m" :value="m" :label="m" /></el-select>
    </el-form-item>
    <el-form-item label="Path"><el-input v-model="testReq.path" placeholder="/api/user/1" /></el-form-item>
    <el-form-item label="Headers (JSON)"><el-input v-model="testHeadersText" type="textarea" :rows="2" /></el-form-item>
    <el-form-item label="Query (JSON)"><el-input v-model="testQueryText" type="textarea" :rows="2" /></el-form-item>
    <el-form-item label="Body"><el-input v-model="testReq.body" type="textarea" :rows="4" /></el-form-item>
    <el-button :disabled="!mockId" @click="runTest">运行测试</el-button>
  </el-form>
  <pre v-if="testRes" class="result">{{ testRes.status }} {{ testRes.headers }}\n{{ testRes.body }}</pre>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { mocksApi, Mock, MockTestResponse } from "@/api/mocks";

const route = useRoute();
const router = useRouter();
const METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"] as const;

const mockId = computed(() => (route.params.id ? Number(route.params.id) : null));
const isNew = computed(() => !mockId.value);

const form = reactive<Mock>({
  id: 0, project_id: Number(route.query.project_id) || 1, name: "", method: "GET", path: "/api/example",
  enabled: true, request_match: null, response_status: 200, response_headers: { "Content-Type": "application/json" },
  response_body: '{"ok":true}', delay_ms: 0, description: null
});
const responseHeadersText = ref(JSON.stringify(form.response_headers, null, 2));
const loading = ref(false);

const testReq = reactive({ method: "GET" as Mock["method"], path: "/api/example", headers: {} as Record<string,string>, query: {} as Record<string,string>, body: null as string | null });
const testHeadersText = ref("{}");
const testQueryText = ref("{}");
const testRes = ref<MockTestResponse | null>(null);

onMounted(async () => {
  if (mockId.value) {
    const m = await mocksApi.get(mockId.value);
    Object.assign(form, m);
    responseHeadersText.value = JSON.stringify(m.response_headers ?? {}, null, 2);
  }
});

async function save() {
  loading.value = true;
  try {
    let headers: Record<string,string> | undefined;
    try { headers = JSON.parse(responseHeadersText.value || "{}"); } catch { ElMessage.error("响应头 JSON 格式错误"); return; }
    const body = { ...form, response_headers: headers };
    delete (body as any).id;
    if (isNew.value) {
      const created = await mocksApi.create(body);
      router.replace(`/mocks/${created.id}`);
    } else {
      await mocksApi.update(mockId.value!, body);
      ElMessage.success("已保存");
    }
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || "保存失败"); }
  finally { loading.value = false; }
}

async function runTest() {
  try {
    testReq.headers = JSON.parse(testHeadersText.value || "{}");
    testReq.query = JSON.parse(testQueryText.value || "{}");
  } catch { return ElMessage.error("JSON 格式错误"); }
  testRes.value = await mocksApi.test(mockId.value!, testReq);
}
</script>

<style scoped>
.result { background:#f5f5f5; padding:12px; white-space: pre-wrap; }
</style>
