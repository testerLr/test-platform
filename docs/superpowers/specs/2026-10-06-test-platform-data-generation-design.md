# 测试平台 · 造数功能 · 设计规格

**日期**: 2026-10-06
**状态**: 已设计,等待用户评审
**范围**: 第二份规格文档(共两份)。第一份(平台骨架 + Mock)已发布并推送到 main。

---

## 1. 背景与目标

### 1.1 背景

第一份规格已交付企业内测试平台的骨架与 HTTP/HTTPS Mock 功能。本规格在此基础上扩展**造数功能**:在测试执行前批量构造测试数据,涉及 MySQL、Kafka、Redis、HTTP 接口,并支持将这些操作串联起来形成可复用的流水线。

### 1.2 目标

- 提供表单配置式的"原子节点"(Step):MySQL 插入、Kafka 发送、Redis 设置、HTTP 调用
- 提供线性流水线(Pipeline):按顺序串联多个节点,前面节点的输出可被后面节点通过 Jinja2 模板引用
- 每次运行产生完整历史(每步输入/输出/耗时/错误),保留最近 30 条
- 复用 v1 的项目/权限/认证模型与 Jinja2 SandboxedEnvironment renderer

### 1.3 非目标(本期不做)

- 定时调度(cron)
- DAG / 流水线内节点并发
- 流水线之间的复用(流水线 A 的输出喂给流水线 B)
- 数据回滚(成功后自动回滚)
- 审计日志(谁在什么时间改了哪个 config)
- Webhook 触发
- 节点的 "if/else" 条件分支
- 多步事务(跨节点 ACID)
- hset / lpush / sadd 等 Redis 操作(仅 set)
- HTTP 节点之外的协议(GRPC / WebSocket)

---

## 2. 技术栈新增依赖

| 维度 | 选型 |
|---|---|
| MySQL 客户端 | 复用 v1 `asyncmy`(无需新增) |
| Kafka 客户端 | `aiokafka>=0.10`(异步,与 FastAPI 一致) |
| Redis 客户端 | `redis>=5.0`(同步,通过 `asyncio.to_thread` 包装) |
| HTTP 客户端 | 复用 v1 已有的 `httpx`(异步) |
| 加密 | `cryptography>=42.0`(Fernet 对称加密) |
| 模板 | 复用 v1 `Jinja2 SandboxedEnvironment` |

---

## 3. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│                       浏览器 (Vue3 SPA)                       │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP
                         ▼
┌──────────────────────────────────────────────────────────────┐
│              Nginx 反向代理 (复用 v1)                          │
│   /              →  前端静态文件                                 │
│   /api/*         →  后端 FastAPI 管理 API                      │
│   /m/*           →  后端 FastAPI Mock 运行时(已有)              │
│   /d/*           →  后端 FastAPI 造数执行入口(新增)             │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│         FastAPI 应用 (在 v1 进程内扩展)                          │
│                                                                │
│   ┌──────────────────────┐    ┌─────────────────────────┐    │
│   │  管理 API (/api/v1)   │    │  造数执行器 (/d)        │    │
│   │  (v1 + Pipeline CRUD) │    │  - PipelineExecutor     │    │
│   └──────────┬───────────┘    │  - NodeExecutorFactory  │    │
│              │                │    - MySQLExecutor      │    │
│              └────────┬───────┴    - KafkaExecutor      │    │
│                       │            - RedisExecutor      │    │
│                       │            - HttpExecutor       │    │
│                       │        └────────┬────────────────┘    │
└───────────────────────┼─────────────────┼───────────────────────┘
                        │                 │
                        ▼                 ▼
              ┌─────────────────────┐  ┌──────────────────────────┐
              │   MySQL(v1)         │  │  外部数据源                 │
              │  + pipelines         │  │  - 用户配置的 MySQL       │
              │  + pipeline_steps    │  │  - 用户配置的 Kafka       │
              │  + pipeline_runs     │  │  - 用户配置的 Redis       │
              │  + pipeline_run_     │  │  - 用户配置的 HTTP 端点   │
              │    steps             │  └──────────────────────────┘
              └─────────────────────┘
```

**关键决策**:
- 流水线执行**在请求线程内同步执行**;阻塞 HTTP 调用,返回完整运行结果
- 节点按顺序执行,任一失败抛出 `NodeExecutionError`,后续标记 skipped
- 运行历史在执行完成后写库(失败也要写)
- 同一 FastAPI 进程,通过路由前缀区分;复用 v1 的进程、连接池、模型、JWT 认证

---

## 4. 应用日志(补充)

FastAPI 应用日志写到仓库根目录 `logs/app.log`:

- 使用 Python `logging.config.dictConfig` 配置
- 同时输出 stdout(Docker logs 收集)+ 文件
- 格式:`%(asctime)s %(levelname)s %(name)s %(message)s`
- 轮转:`RotatingFileHandler`,`maxBytes=10MB`,`backupCount=5`
- `logs/` 加入 `.gitignore`(运行时产物)
- v1 + v2 共用此日志配置;uvicorn / uvicorn.error / uvicorn.access / app 四个 logger 都路由到 stdout+file

---

## 5. 数据模型

```sql
-- 流水线
pipelines
  id            BIGINT PK
  project_id    BIGINT FK -> projects.id  -- 归属项目
  name          VARCHAR(128)
  description   TEXT
  created_by    BIGINT FK -> users.id
  created_at    DATETIME
  updated_at    DATETIME

-- 流水线节点
pipeline_steps
  id            BIGINT PK
  pipeline_id   BIGINT FK -> pipelines.id  -- ON DELETE CASCADE
  order_index   INT              -- 0-based,执行顺序
  type          ENUM('mysql','kafka','redis','http')
  name          VARCHAR(128)
  enabled       BOOLEAN DEFAULT TRUE  -- 关闭的节点跳过但不中断
  config        JSON             -- 类型专属配置(见 §6)
  created_at    DATETIME
  updated_at    DATETIME
  INDEX(pipeline_id, order_index)

-- 流水线运行记录
pipeline_runs
  id            BIGINT PK
  pipeline_id   BIGINT FK -> pipelines.id
  triggered_by  BIGINT FK -> users.id
  status        ENUM('running','success','failed')
  started_at    DATETIME
  finished_at   DATETIME
  total_steps   INT
  success_count INT DEFAULT 0
  failure_count INT DEFAULT 0
  skipped_count INT DEFAULT 0

-- 每步执行明细
pipeline_run_steps
  id            BIGINT PK
  run_id        BIGINT FK -> pipeline_runs.id  -- ON DELETE CASCADE
  step_id       BIGINT FK -> pipeline_steps.id  -- 引用,即使 step 被删也能查
  order_index   INT              -- 冗余存储,便于排序
  status        ENUM('pending','success','failed','skipped')
  started_at    DATETIME
  finished_at   DATETIME
  duration_ms   INT
  input_rendered  JSON            -- 模板渲染后的输入快照
  output        JSON             -- 节点输出
  error         TEXT             -- 失败时的错误信息
```

### 5.1 权限

- 平台管理员(`is_admin=TRUE`):所有项目所有流水线可见可改
- 项目 owner:可删流水线、清空运行历史
- 项目 developer:可创建/修改流水线、运行、查看历史
- 项目 viewer:只读流水线列表与运行历史

---

## 6. 节点 config schema

### 6.1 MySQL

```jsonc
{
  "connection": {
    "host": "string", "port": 5432, "user": "string",
    "password": "string (明文,API 入参)",
    "database": "string"
  },
  "sql": "INSERT INTO users (name, age) VALUES (%s, %s)",
  "params": { "name": "{{ steps.0.output.name }}", "age": 25 }
}
```

API handler 写入数据库前把 `password` 用 `encrypt()` 转成 `password_enc` 并丢弃明文;DB 内只存密文。运行时 executor 调 `decrypt()` 解出明文,**不写日志**。

**output**:`{"affected_rows": int, "inserted_id": int | null}`

### 6.2 Kafka

```jsonc
{
  "connection": {
    "bootstrap_servers": "host:9092",
    "security_protocol": "PLAINTEXT",
    "sasl_username": "string (可选)",
    "sasl_password": "string (明文,API 入参,可选)"
  },
  "topic": "string",
  "key": "string (template, 可选)",
  "value": "string (template)"
}
```

**output**:`{"topic": str, "partition": int, "offset": int}`

### 6.3 Redis

```jsonc
{
  "connection": {
    "host": "string", "port": 6379,
    "password": "string (明文,可选)",
    "db": 0
  },
  "operation": "set",        // v1 仅 set
  "key": "string (template)",
  "value": "string (template)",
  "ttl_seconds": 0           // 0 = 永久
}
```

**output**:`{"key": str, "operation": "set"}`

### 6.4 HTTP

```jsonc
{
  "method": "POST",
  "url": "string (template)",
  "headers": { "Content-Type": "application/json" },
  "body": "string (template, 可选)",
  "timeout_seconds": 30       // 可选,默认 30
}
```

**output**:`{"status": int, "headers": {...}, "body": <parsed-json-or-string>}`

---

## 7. 执行器架构

### 7.1 PipelineExecutor

```python
class PipelineExecutor:
    def __init__(self, db, run, pipeline):
        self.db = db
        self.run = run
        self.steps = sorted(pipeline.steps, key=lambda s: s.order_index)
        self.context = {"steps": []}

    async def execute(self) -> PipelineRunResult:
        for step in self.steps:
            if not step.enabled:
                await self._mark_skipped(step)
                continue
            executor = self._resolve_executor(step.type)
            rendered = render_step_config(step.config, self.context)
            try:
                output = await executor.run(rendered)
                self.context["steps"].append({"output": output})
                await self._mark_success(step, rendered, output)
            except NodeExecutionError as e:
                self.context["steps"].append({"output": {}, "error": str(e)})
                await self._mark_failed(step, rendered, str(e))
                await self._mark_remaining_skipped()
                break
        return self._build_result()
```

### 7.2 节点执行器接口

```python
class NodeExecutor(Protocol):
    type: StepType
    async def run(self, rendered_config: dict, ctx: ExecutionContext) -> dict: ...
```

### 7.3 模板渲染

复用 v1 `app.mock_engine.renderer.render`(SandboxedEnvironment):

```python
def render_step_template(text: str, context: dict) -> str:
    return _ENV.from_string(text).render(
        steps=context["steps"],   # 让 {{ steps.0.output.user_id }} 工作
        now=_now, uuid=_uuid, randint=_randint,
    )
```

模板可用:
- `{{ steps.N.output.field }}` — 引用第 N 步的输出
- `{{ now() }}` / `{{ uuid() }}` / `{{ randint(min, max) }}` — 内置函数

### 7.4 错误处理

```python
class NodeExecutionError(Exception):
    def __init__(self, message: str, *, retryable: bool = False, details: dict | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.details = details or {}
```

| 场景 | retryable |
|---|---|
| MySQL 连接失败 | true |
| MySQL SQL 错误(语法错) | false |
| Kafka 连接失败 / 发送失败 | true |
| Redis 连接失败 / SET 失败 | true / false |
| HTTP 5xx / 连接超时 | true |
| HTTP 4xx | false |

**v1 不做自动 retry**;仅在 error 里标记 `retryable`,留给未来扩展。

### 7.5 凭据加密

```python
# app/security/crypto.py
from cryptography.fernet import Fernet
from app.config import settings

_fernet = Fernet(settings.encryption_key.encode())

def encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()

def decrypt(cipher: str) -> str:
    return _fernet.decrypt(cipher.encode()).decode()
```

- 配置:`ENCRYPTION_KEY` 环境变量,Fernet 密钥(base64 编码的 32 字节)
- API 入参是明文(`password` / `sasl_password`);API handler 写入数据库前调 `encrypt()` 转成 `password_enc` / `sasl_password_enc` 并丢弃明文字段
- 数据库只存密文;executor 运行时调 `decrypt()` 解出明文使用,**不写日志**
- Pydantic schema 暴露明文字段名(`password` / `sasl_password`),便于 API 直传;DB 列名带 `_enc` 后缀

---

## 8. 节点执行器实现

### 8.1 MySQL Executor

- 短连接:每节点独立 asyncmy 连接,执行完关闭
- 参数化:即使 SQL 模板是用户输入,params 仍走参数化绑定防注入
- 异常映射:连接失败 → retryable;SQL 错误 → not retryable,带 sqlstate

### 8.2 Kafka Executor

- aiokafka.AIOKafkaProducer,单消息发送等 ack
- 安全协议:`PLAINTEXT` / `SASL_PLAINTEXT` / `SASL_SSL`
- value 模板渲染后必须是字符串

### 8.3 Redis Executor

- redis.Redis 同步客户端,通过 `asyncio.to_thread` 包装
- v1 仅 `operation="set"`(hset/lpush/sadd 留待 v2)

### 8.4 HTTP Executor

- httpx.AsyncClient 短连接
- 响应:尝试 JSON 解析,失败则保留原文
- 超时:默认 30s,可被 config 覆盖

### 8.5 Pydantic 校验

每种类型 config 用 discriminated union:

```python
class MySQLConfig(BaseModel): ...
class KafkaConfig(BaseModel): ...
class RedisConfig(BaseModel): ...
class HttpConfig(BaseModel): ...

NodeConfig = Annotated[
    Union[MySQLConfig, KafkaConfig, RedisConfig, HttpConfig],
    Field(discriminator="type")
]
```

API 根据 `type` 字段选对应 schema 校验 config;UI 表单按 type 字段切表单。

---

## 9. 管理 API 设计

所有 API 前缀 `/api/v1`,沿用 v1 JWT 认证。

### 9.1 流水线 CRUD

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/pipelines?project_id=N` | 列出某项目下的流水线 | 项目成员 |
| POST | `/api/v1/pipelines` | 创建流水线 | 项目 developer |
| GET | `/api/v1/pipelines/{id}` | 流水线详情(含 steps) | 项目成员 |
| PATCH | `/api/v1/pipelines/{id}` | 修改 name/description | 项目 developer |
| DELETE | `/api/v1/pipelines/{id}` | 删除流水线(cascade) | 项目 owner |

### 9.2 步骤管理

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/pipelines/{id}/steps` | 列出步骤 | 项目成员 |
| POST | `/api/v1/pipelines/{id}/steps` | 创建步骤 | 项目 developer |
| GET | `/api/v1/pipelines/{id}/steps/{step_id}` | 步骤详情 | 项目成员 |
| PATCH | `/api/v1/pipelines/{id}/steps/{step_id}` | 修改步骤 | 项目 developer |
| DELETE | `/api/v1/pipelines/{id}/steps/{step_id}` | 删除步骤 | 项目 developer |
| POST | `/api/v1/pipelines/{id}/steps/reorder` | body:`{"order": [step_id_1, ...]}` 重排 | 项目 developer |

### 9.3 运行与历史

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/api/v1/pipelines/{id}/run` | 同步执行流水线 | 项目 developer+ |
| GET | `/api/v1/pipelines/{id}/runs` | 运行历史列表(最近 30 条) | 项目成员 |
| GET | `/api/v1/runs/{run_id}` | 单次运行详情 | 项目成员 |
| DELETE | `/api/v1/pipelines/{id}/runs` | 清空该流水线历史 | 项目 developer |

### 9.4 单步 dry-run 测试

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/api/v1/pipelines/{id}/steps/{step_id}/test` | 测试单步;body:`{"context": {...}}`;响应:`{output, rendered_config}` 或 `{error}` | 项目 developer |

### 9.5 错误响应

```json
{ "detail": "错误描述" }
```

| 状态码 | 含义 |
|---|---|
| 400 | 参数错误 |
| 401 | 未登录 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 422 | Pydantic 校验失败(type/config 不匹配) |
| 500 | 服务器内部错误(含外部数据源不可达) |

### 9.6 运行响应结构

```json
{
  "run_id": 123,
  "pipeline_id": 1,
  "status": "success",
  "started_at": "2026-10-06T10:00:00Z",
  "finished_at": "2026-10-06T10:00:02.500Z",
  "duration_ms": 2500,
  "total_steps": 3,
  "success_count": 3,
  "failure_count": 0,
  "skipped_count": 0,
  "steps": [
    {
      "step_id": 11,
      "order_index": 0,
      "name": "插入用户",
      "type": "mysql",
      "status": "success",
      "duration_ms": 50,
      "input_rendered": {"sql": "INSERT ...", "params": {"name": "alice"}},
      "output": {"affected_rows": 1, "inserted_id": 42}
    }
  ]
}
```

---

## 10. 前端页面

### 10.1 路由

```
/projects/:id                       项目详情(已有)
  ├── Tab: Mock 列表
  ├── Tab: 成员管理
  └── Tab: 数据流水线 ⭐

/pipelines                         (可选 v1 简化:从项目详情进入)
/pipelines/:id                     流水线详情(步骤列表 + 操作)
/pipelines/new?project_id=N        新建流水线
/pipelines/:id/steps/:step_id      步骤编辑

/runs/:run_id                       运行详情(只读)
```

### 10.2 项目详情页 — 新增 Tab

复用 v1 的 `<el-tabs>`,加第三个 pane:

- 顶部"新建流水线"按钮
- 表格:流水线名、步骤数、最近运行状态、上次运行时间、操作(运行/查看/编辑/删除)
- 折叠"运行历史"区:该项目的最近 30 条(跨流水线)

### 10.3 流水线详情页 `/pipelines/:id`

- 顶部:返回 / 名称 / 运行 / 编辑 / 删除
- 中部:描述 + 步骤数 + 上次运行
- 主体:步骤列表(可拖拽排序或上下按钮)+ 添加步骤按钮

### 10.4 步骤编辑页

- 顶部 `el-radio-group` 选 MySQL/Kafka/Redis/HTTP;切换清空 config
- 类型专属表单(对应 Pydantic schema)
- 底部"测试此步骤"按钮:调用 `/test`,展示渲染后 config + output

### 10.5 运行详情页 `/runs/:run_id`

- 只读:整体状态 + 每步的
  - 状态徽章(成功 ✓ / 失败 ✗ / 跳过 ⊘)
  - duration_ms
  - 渲染后 input(可折叠 JSON)
  - output(可折叠 JSON)
  - error(失败时高亮)
- "复制上下文"按钮:复制该步 output 文本,便于下游 `{{ steps.N.output.X }}` 调试

### 10.6 权限

- 路由级:必须登录,后端二次校验项目成员
- 按钮级:viewer 看不到新建/运行/删除/编辑按钮
- 平台管理员:看得到所有项目下的流水线

---

## 11. 部署集成

### 11.1 新增环境变量

```env
ENCRYPTION_KEY=base64-encoded-32-byte-fernet-key
LOG_LEVEL=INFO
```

`.env.example` 和 docker-compose 同步更新。

生成密钥:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 11.2 数据迁移

新建 Alembic 迁移:`alembic revision --autogenerate -m "data generation tables"`。

应用时机:由 `backend-init` 容器自动跑 `alembic upgrade head`。

### 11.3 Docker 集成

复用现有 compose;后端镜像重建以包含新依赖。前端无需重建。

可选挂载(生产环境收集日志):
```yaml
  backend:
    volumes:
      - ./logs:/app/logs
```

---

## 12. 后续

- 本规格落地后,转入 `superpowers:writing-plans` 制定实施计划
- v1 部署在 https://github.com/testerLr/test-platform;v2 在同一仓库的 main 分支继续
- 后续可选扩展:DAG 并行、定时调度、审计日志、流水线复用、Redis hset/lpush/sadd 等
