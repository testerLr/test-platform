<template>
  <el-page-header :title="isNew ? '新建步骤' : '编辑步骤'" @back="$router.back()" />

  <el-form :model="form" label-width="140px" style="max-width:720px">
    <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
    <el-form-item label="类型">
      <el-select v-model="form.type" :disabled="!isNew" @change="onTypeChange">
        <el-option label="MySQL" value="mysql" />
        <el-option label="Kafka" value="kafka" />
        <el-option label="Redis" value="redis" />
        <el-option label="HTTP" value="http" />
      </el-select>
    </el-form-item>
    <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>

    <template v-if="form.type === 'mysql'">
      <el-divider content-position="left">连接</el-divider>
      <el-form-item label="host"><el-input v-model="form.config.connection.host" /></el-form-item>
      <el-form-item label="port"><el-input-number v-model="form.config.connection.port" :min="1" :max="65535" /></el-form-item>
      <el-form-item label="user"><el-input v-model="form.config.connection.user" /></el-form-item>
      <el-form-item label="password"><el-input v-model="form.config.connection.password" type="password" show-password /></el-form-item>
      <el-form-item label="database"><el-input v-model="form.config.connection.database" /></el-form-item>
      <el-divider content-position="left">SQL</el-divider>
      <el-form-item label="SQL"><el-input v-model="form.config.sql" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="params (JSON)"><el-input v-model="paramsText" type="textarea" :rows="4" /></el-form-item>
    </template>

    <template v-if="form.type === 'kafka'">
      <el-divider content-position="left">连接</el-divider>
      <el-form-item label="bootstrap_servers"><el-input v-model="form.config.connection.bootstrap_servers" /></el-form-item>
      <el-form-item label="security_protocol"><el-input v-model="form.config.connection.security_protocol" /></el-form-item>
      <el-form-item label="sasl_username"><el-input v-model="form.config.connection.sasl_username" /></el-form-item>
      <el-form-item label="sasl_password"><el-input v-model="form.config.connection.sasl_password" type="password" show-password /></el-form-item>
      <el-form-item label="topic"><el-input v-model="form.config.topic" /></el-form-item>
      <el-form-item label="key (模板)"><el-input v-model="form.config.key" /></el-form-item>
      <el-form-item label="value (模板)"><el-input v-model="form.config.value" type="textarea" :rows="4" /></el-form-item>
    </template>

    <template v-if="form.type === 'redis'">
      <el-divider content-position="left">连接</el-divider>
      <el-form-item label="host"><el-input v-model="form.config.connection.host" /></el-form-item>
      <el-form-item label="port"><el-input-number v-model="form.config.connection.port" :min="1" :max="65535" /></el-form-item>
      <el-form-item label="password"><el-input v-model="form.config.connection.password" type="password" show-password /></el-form-item>
      <el-form-item label="db"><el-input-number v-model="form.config.connection.db" :min="0" :max="15" /></el-form-item>
      <el-form-item label="key (模板)"><el-input v-model="form.config.key" /></el-form-item>
      <el-form-item label="value (模板)"><el-input v-model="form.config.value" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="ttl_seconds"><el-input-number v-model="form.config.ttl_seconds" :min="0" :max="2592000" /></el-form-item>
    </template>

    <template v-if="form.type === 'http'">
      <el-form-item label="method">
        <el-select v-model="form.config.method" style="width:160px">
          <el-option v-for="m in ['GET','POST','PUT','DELETE','PATCH']" :key="m" :value="m" :label="m" />
        </el-select>
      </el-form-item>
      <el-form-item label="URL (模板)"><el-input v-model="form.config.url" /></el-form-item>
      <el-form-item label="headers (JSON)"><el-input v-model="headersText" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="body (模板)"><el-input v-model="form.config.body" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="timeout_seconds"><el-input-number v-model="form.config.timeout_seconds" :min="1" :max="600" /></el-form-item>
    </template>

    <el-button type="primary" :loading="loading" @click="save">保存</el-button>
    <el-button :disabled="isNew" @click="runTest">测试此步骤</el-button>
  </el-form>

  <pre v-if="testResult" class="result">{{ JSON.stringify(testResult, null, 2) }}</pre>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { pipelinesApi, Step } from "@/api/pipelines";

const route = useRoute();
const router = useRouter();
const pipelineId = Number(route.params.id);
const stepId = computed(() => (route.params.stepId === "new" ? null : Number(route.params.stepId)));
const isNew = computed(() => stepId.value === null);

const form = reactive<{
  name: string; type: Step["type"]; enabled: boolean;
  config: any;
}>({
  name: "",
  type: "mysql",
  enabled: true,
  config: _defaultConfig("mysql"),
});

const paramsText = ref("{}");
const headersText = ref("{}");
const testResult = ref<any>(null);
const loading = ref(false);

function _defaultConfig(t: Step["type"]) {
  if (t === "mysql") return { connection: { host: "", port: 3306, user: "", password: "", database: "" }, sql: "", params: {} };
  if (t === "kafka") return { connection: { bootstrap_servers: "", security_protocol: "PLAINTEXT" }, topic: "", value: "" };
  if (t === "redis") return { connection: { host: "", port: 6379, db: 0 }, operation: "set", key: "", value: "", ttl_seconds: 0 };
  return { method: "GET", url: "", headers: {}, body: "", timeout_seconds: 30 };
}

function onTypeChange(t: Step["type"]) {
  form.config = _defaultConfig(t);
  paramsText.value = "{}";
  headersText.value = "{}";
}

onMounted(async () => {
  if (!isNew.value && stepId.value !== null) {
    const all = await pipelinesApi.steps(pipelineId);
    const s = all.find((x) => x.id === stepId.value);
    if (s) {
      form.name = s.name;
      form.type = s.type;
      form.enabled = s.enabled;
      form.config = s.config;
      paramsText.value = JSON.stringify(s.config.params ?? {}, null, 2);
      headersText.value = JSON.stringify(s.config.headers ?? {}, null, 2);
    }
  }
});

async function save() {
  loading.value = true;
  try {
    let config = JSON.parse(JSON.stringify(form.config));
    if (form.type === "mysql") {
      try { config.params = JSON.parse(paramsText.value || "{}"); } catch { ElMessage.error("params JSON 格式错误"); return; }
    }
    if (form.type === "http") {
      try { config.headers = JSON.parse(headersText.value || "{}"); } catch { ElMessage.error("headers JSON 格式错误"); return; }
    }
    if (isNew.value) {
      const created = await pipelinesApi.addStep(pipelineId, { type: form.type, name: form.name, enabled: form.enabled, config });
      router.replace(`/pipelines/${pipelineId}/steps/${created.id}`);
    } else {
      await pipelinesApi.updateStep(pipelineId, stepId.value!, { name: form.name, enabled: form.enabled, config });
      ElMessage.success("已保存");
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    loading.value = false;
  }
}

async function runTest() {
  try {
    const res = await pipelinesApi.testStep(pipelineId, stepId.value!, { context: {} });
    testResult.value = res;
  } catch (e: any) {
    testResult.value = { error: e.response?.data?.detail || e.message };
  }
}
</script>

<style scoped>
.result { background: #f5f5f5; padding: 12px; white-space: pre-wrap; margin-top: 16px; }
</style>
