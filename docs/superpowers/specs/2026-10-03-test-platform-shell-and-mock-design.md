# 测试平台 · 平台骨架与 Mock 功能 · 设计规格

**日期**: 2026-10-03
**状态**: 已设计,等待用户评审
**范围**: 第一份规格文档(共两份)。第二份规格文档为造数功能,后续单独设计。

---

## 1. 背景与目标

### 1.1 背景

企业内部研发团队需要一个测试平台,支持两类常用测试活动:
1. **Mock 接口**:在依赖服务未就绪或难以构造边界场景时,通过 Mock 接口模拟被测依赖的响应。
2. **造数**:在测试执行前批量构造测试数据(数据库、消息队列、HTTP 接口调用等)。

本规格文档聚焦于**平台骨架**和**Mock 功能**,造数功能在第二份规格文档中独立设计。

### 1.2 目标

- 提供一个企业内部多团队共用的测试平台,具备清晰的项目/用户权限隔离。
- Mock 功能以表单配置为主,支持动态响应(模板语法),不做脚本、不做录制、不做版本控制。
- 平台部署为 Docker 容器,易于运维和扩展。

### 1.3 非目标(本期不做)

- Mock 接口版本控制 / 历史回滚。
- Mock 录制 / OpenAPI/Postman 导入。
- Mock 响应脚本(JS/Python)。
- WebSocket / gRPC Mock。
- 团队级别的 Mock 运行时隔离。
- 审计日志(留待第二份规格文档——造数功能时一起做)。
- 造数功能本身(见第二份规格文档)。

---

## 2. 技术栈

| 维度 | 选型 | 理由 |
|---|---|---|
| 后端语言/框架 | Python 3.11+ / FastAPI | 异步性能好,OpenAPI 文档自动生成,适合同时承载管理 API 与 Mock 运行时 |
| 后端 ORM / 迁移 | SQLAlchemy 2.x(异步) + Alembic | 业界主流,异步友好 |
| 后端模板引擎 | Jinja2 | 成熟稳定,严格限制可用变量避免沙箱风险 |
| 后端认证 | JWT(HS256) + bcrypt | 无状态、可水平扩展 |
| 前端 | Vue 3 + Vite + Element Plus + Pinia + Vue Router + Axios | Vue3 生态主流后台组合 |
| 数据库 | MySQL 8.x | 企业内部已有 MySQL 运维体系 |
| 部署 | Docker Compose(FastAPI + Nginx + MySQL) | 运维简单,满足容器化要求 |
| 测试 | pytest + pytest-asyncio + httpx / Vitest + Vue Test Utils | 后端 + 前端核心模块覆盖 |

---

## 3. 总体架构

```
┌────────────────────────────────────────────────────────────┐
│                       浏览器 (Vue3 SPA)                      │
└────────────────────────┬───────────────────────────────────┘
                         │ HTTP
                         ▼
┌────────────────────────────────────────────────────────────┐
│              Nginx 反向代理 (Docker 容器)                    │
│   /              →  前端静态文件 (Vue3 build)                │
│   /api/*         →  后端 FastAPI 管理 API                    │
│   /m/*           →  后端 FastAPI Mock 响应入口                │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│           FastAPI 应用 (单进程,uvicorn workers)              │
│                                                             │
│   ┌─────────────────────┐    ┌─────────────────────────┐   │
│   │  管理 API (/api)    │    │  Mock 引擎 (/m)         │   │
│   │  - JWT 认证         │    │  - 内存路由表            │   │
│   │  - 项目 / Mock CRUD │    │  - 动态响应模板渲染       │   │
│   │  - 用户管理          │    │  - 延时模拟              │   │
│   └──────────┬──────────┘    └───────────┬─────────────┘   │
│              │                            │                  │
│              └────────┬───────────────────┘                 │
│                       │                                     │
└───────────────────────┼─────────────────────────────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │   MySQL 8.x (容器)   │
              │  - users             │
              │  - projects          │
              │  - project_members   │
              │  - mock_apis         │
              └─────────────────────┘
```

**关键决策**:

- **单应用**:平台管理与 Mock 响应共用同一个 FastAPI 应用,通过路由前缀区分(`/api` vs `/m`)。共享 MySQL 连接池,部署简单。
- **Mock 路由缓存**:Mock 配置存 MySQL,在内存里维护一份已启用路由表。配置变更时通过 API handler 同步刷新(无需重启服务)。
- **JWT 认证**:管理 API 用 JWT;Mock 响应入口(`/m/*`)**不需认证**——被测系统直接调用。

---

## 4. 数据模型

```sql
-- 用户表
users
  id            BIGINT PK
  username      VARCHAR(64) UNIQUE NOT NULL
  password_hash VARCHAR(255) NOT NULL      -- bcrypt
  is_admin      BOOLEAN DEFAULT FALSE      -- 平台管理员
  is_active     BOOLEAN DEFAULT TRUE
  created_at    DATETIME
  updated_at    DATETIME

-- 项目表
projects
  id            BIGINT PK
  name          VARCHAR(128) NOT NULL
  description   TEXT
  created_by    BIGINT FK -> users.id
  created_at    DATETIME
  updated_at    DATETIME

-- 项目成员表(用户-项目多对多 + 角色)
project_members
  id            BIGINT PK
  project_id    BIGINT FK -> projects.id
  user_id       BIGINT FK -> users.id
  role          ENUM('owner','developer','viewer')
  created_at    DATETIME
  UNIQUE(project_id, user_id)

-- Mock 接口表
mock_apis
  id                BIGINT PK
  project_id        BIGINT FK -> projects.id    -- 归属项目
  name              VARCHAR(128)                -- 便于识别的名称
  method            ENUM('GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS')
  path              VARCHAR(255)                -- 支持 {id} 占位符
  enabled           BOOLEAN DEFAULT TRUE
  request_match     JSON                        -- 可选:请求匹配条件
  response_status   INT DEFAULT 200
  response_headers  JSON                        -- 自定义响应头
  response_body     LONGTEXT                    -- 支持模板语法的响应体
  delay_ms          INT DEFAULT 0               -- 延时模拟
  description       TEXT
  created_by        BIGINT FK -> users.id
  created_at        DATETIME
  updated_at        DATETIME
  INDEX(method, path, enabled)
```

### 4.1 权限模型

- **平台管理员**(`is_admin=TRUE`):可管理所有项目和用户。
- **项目 owner**:可管理项目成员、可删除项目。
- **项目 developer**:可创建/修改/启用停用本项目的 Mock 接口。
- **项目 viewer**:只能查看本项目的 Mock 接口列表。
- **运行时 Mock 入口**(`/m/*`):**不做任何权限校验**——被测系统调用时只需按 method+path 匹配到 enabled 的 Mock 接口即可。

---

## 5. Mock 引擎设计

Mock 引擎是平台的核心运行时,负责把用户在表单里配置的 Mock 接口变成真实的 HTTP 响应服务。

### 5.1 路由匹配

**基础匹配**:`method + path` 精确匹配。

- 例:配置 `method=GET, path=/api/user/1`,外部请求 `GET /m/api/user/1` 即匹配。
- **不匹配处理**:返回 404,响应体 `{"detail": "Mock not found"}`。

**路径参数**:

- 配置时支持 `{key}` 占位符,实际路径段匹配任意非空字符串。
- 例:配置 `path=/api/user/{id}`,可匹配 `GET /m/api/user/1`、`GET /m/api/user/42`。
- 路径参数可在响应模板中通过 `{{ request.path.id }}` 引用。

**请求匹配**(可选,基于 `request_match` JSON):

全部为 **AND 关系**,任一不匹配则返回 404。

`request_match` 字段 JSON schema:

```json
{
  "query": { "<key>": "<value>" },
  "headers": { "<key>": "<value>" },
  "body_contains": "<substring>",
  "body_jsonpath": "<jsonpath-expression-evaluating-to-bool>"
}
```

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `query` | object | 查询参数精确匹配 | `{"token": "abc"}` |
| `headers` | object | 请求头精确匹配(大小写不敏感) | `{"Authorization": "Bearer xxx"}` |
| `body_contains` | string | 请求体中必须包含的子串 | `"action=login"` |
| `body_jsonpath` | string | JSONPath 布尔表达式;请求体解析为 JSON 后求值,必须为 true 才匹配 | `$.action == "login"` |

匹配规则细节:
- `query` / `headers`:键值对**全部相等**才算匹配(缺省字段视为不匹配)。
- `body_contains`:仅对原始字节做子串匹配;请求体非文本(如二进制)则视为不匹配。
- `body_jsonpath`:请求体必须是合法 JSON,否则视为不匹配;JSONPath 求值结果非 true/false 时视为不匹配。
- 请求体为空时,`body_contains` 和 `body_jsonpath` 视为不匹配。

### 5.2 动态响应(模板渲染)

响应体中可使用 `{{ ... }}` 占位符,在返回时实时替换:

| 占位符 | 含义 | 示例 |
|---|---|---|
| `{{ request.path.<key> }}` | 路径参数 | `{{ request.path.id }}` → `"1"` |
| `{{ request.query.<key> }}` | 查询参数 | `{{ request.query.token }}` |
| `{{ request.header.<key> }}` | 请求头 | `{{ request.header.Authorization }}` |
| `{{ request.body.<key> }}` | 请求体字段(JSON) | `{{ request.body.username }}` |
| `{{ now() }}` | 当前时间(ISO 8601 字符串) | |
| `{{ uuid() }}` | 随机 UUID v4 字符串 | |
| `{{ randint(min, max) }}` | `[min, max]` 区间随机整数 | `{{ randint(1, 100) }}` |

**实现**:用 **Jinja2** 作为模板引擎,但严格限制可用变量(只暴露 `request`、`now()`、`uuid()`、`randint()`),避免沙箱安全问题。响应头、响应体独立渲染。

### 5.3 内存路由表与刷新机制

```python
# 伪代码
class MockEngine:
    def __init__(self):
        self._routes: list[MockAPI] = []
        self._lock = asyncio.Lock()

    async def load_all(self):
        """启动时全量加载所有 enabled 的 Mock 配置"""
        async with self._lock:
            self._routes = await db.query(MockAPI).filter_by(enabled=True).all()

    async def upsert(self, mock_api: MockAPI):
        """Mock 接口变更时,增量更新内存路由表"""
        async with self._lock:
            self._routes = [r for r in self._routes if r.id != mock_api.id]
            if mock_api.enabled:
                self._routes.append(mock_api)

    async def remove(self, mock_api_id: int):
        async with self._lock:
            self._routes = [r for r in self._routes if r.id != mock_api_id]

    def match(self, method, path) -> MockAPI | None:
        for r in self._routes:
            if r.method == method and self._path_match(r.path, path):
                if self._request_match(r.request_match, request):
                    return r
        return None
```

**触发时机**:

- 应用启动时:`load_all()`
- 创建 / 更新 / 启用 / 停用 / 删除 Mock 接口时:API handler 调用 `engine.upsert()` / `engine.remove()`

**并发安全**:`asyncio.Lock` 保证多 worker 进程下,每个 worker 进程内路由表的一致性(每个 worker 独立维护一份;内存占用 = Mock 数量 × 单条大小,可控)。

---

## 6. 管理 API 设计

所有管理 API 前缀为 `/api/v1`,使用 JWT 认证。

### 6.1 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/login` | 用户名密码登录,返回 `{access_token, token_type}` |
| GET | `/api/v1/auth/me` | 获取当前登录用户信息 |
| POST | `/api/v1/auth/change-password` | 修改自己的密码 |

### 6.2 用户管理(仅平台管理员)

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/users` | 列出所有用户 |
| POST | `/api/v1/users` | 创建用户(用户名、初始密码、是否管理员) |
| PATCH | `/api/v1/users/{id}` | 启用/停用、修改管理员标识 |
| POST | `/api/v1/users/{id}/reset-password` | 重置密码 |

### 6.3 项目管理

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/projects` | 列出我能看到的项目 | 登录即可 |
| POST | `/api/v1/projects` | 创建项目(创建者自动成为 owner) | 登录即可 |
| GET | `/api/v1/projects/{id}` | 项目详情 | 项目成员 |
| PATCH | `/api/v1/projects/{id}` | 修改项目信息 | 项目 owner |
| DELETE | `/api/v1/projects/{id}` | 删除项目 | 项目 owner |
| GET | `/api/v1/projects/{id}/members` | 项目成员列表 | 项目成员 |
| POST | `/api/v1/projects/{id}/members` | 添加成员(指定 role) | 项目 owner |
| PATCH | `/api/v1/projects/{id}/members/{user_id}` | 修改成员角色 | 项目 owner |
| DELETE | `/api/v1/projects/{id}/members/{user_id}` | 移除成员 | 项目 owner |

### 6.4 Mock 接口管理

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/mocks` | 列出 Mock 接口(可按 `project_id` 过滤) | 项目成员 |
| POST | `/api/v1/mocks` | 创建 Mock 接口 | 项目 developer |
| GET | `/api/v1/mocks/{id}` | Mock 详情 | 项目成员 |
| PATCH | `/api/v1/mocks/{id}` | 修改 Mock 配置(包括 enabled 切换) | 项目 developer |
| DELETE | `/api/v1/mocks/{id}` | 删除 Mock 接口 | 项目 developer |
| POST | `/api/v1/mocks/{id}/test` | 用示例请求测试 Mock(传入模拟请求,返回渲染结果) | 项目 developer |

### 6.5 Mock 响应入口(运行时)

| 方法 | 路径 | 说明 |
|---|---|---|
| ANY | `/m/{full_path:path}` | Mock 响应入口,根据 method+path 匹配 |

### 6.6 错误处理

统一错误响应格式:

```json
{
  "detail": "错误描述信息"
}
```

| 状态码 | 含义 |
|---|---|
| 400 | 请求参数错误 |
| 401 | 未登录或 token 无效 |
| 403 | 无权限 |
| 404 | 资源不存在 / Mock 未匹配 |
| 422 | 参数校验失败(Pydantic) |
| 500 | 服务器内部错误 |

---

## 7. 前端页面结构

### 7.1 技术栈

- **Vue 3** + Composition API
- **Vite** 构建
- **Vue Router** 路由
- **Pinia** 状态管理(token、当前用户信息)
- **Element Plus** UI 组件库
- **Axios** HTTP 客户端(自动注入 JWT)
- **vueuse** 工具集

### 7.2 路由结构

```
/login                          登录页(未登录可访问)

/                               主页(登录后默认)
├── /projects                   项目列表
│   ├── /projects/new           新建项目
│   └── /projects/:id           项目详情
│       ├── 成员管理 tab
│       └── Mock 列表 tab
│
├── /mocks                      Mock 接口列表(全平台可见,按项目过滤)
│   ├── /mocks/new              新建 Mock
│   └── /mocks/:id              Mock 编辑页(含"测试响应"面板)
│
└── /users                      用户管理(仅平台管理员可见)
```

### 7.3 关键页面要点

**登录页** `/login`
- 居中卡片,用户名 + 密码 + 登录按钮。
- 登录成功存 token 到 Pinia + localStorage,跳转主页。

**项目列表** `/projects`
- 表格列出当前用户能看到的项目(名称、描述、我的角色、Mock 数量、创建时间)。
- 仅显示"我作为成员"的项目(平台管理员可见全部)。
- 顶部"新建项目"按钮。

**项目详情** `/projects/:id`
- 顶部:项目信息 + 我的角色。
- Tab 切换:**Mock 列表** / **成员管理**。
- Mock 列表:表格,支持按 method/path 搜索,新建/编辑/启用停用/删除。
- 成员管理:列出成员,可添加/移除/调整角色(owner 才能改)。

**Mock 编辑页** `/mocks/:id`
- 表单分块:
  - 基础信息:名称、归属项目、method/path(支持 `{id}` 占位符)。
  - 请求匹配:是否启用请求匹配规则(JSON 编辑器)。
  - 响应配置:状态码、响应头(JSON 编辑)、响应体(支持模板的 textarea 或 Monaco Editor)。
  - 高级:延时(毫秒)、启用开关、描述。
- 右侧/底部"**测试响应**"面板:可填模拟请求(method/path/headers/query/body),点"测试"调用 `/api/v1/mocks/{id}/test`,实时预览渲染后的响应。

**用户管理** `/users`(仅平台管理员)
- 表格列出所有用户,管理员可新建/启用停用/重置密码。

### 7.4 权限拦截

- **路由级**:进入 `/users` 检查 `is_admin`;进入项目详情检查是否成员。
- **按钮级**:非 developer 看不到"新建/编辑/删除 Mock"按钮;非 owner 看不到"删除项目/管理成员"。
- **API 级**:即使前端隐藏按钮,后端也会二次校验权限(返回 403 时前端弹出提示并刷新列表)。

---

## 8. Docker 部署

### 8.1 项目结构

```
test-platform/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 配置(从环境变量读)
│   │   ├── deps.py                  # 依赖注入(DB、当前用户)
│   │   ├── db/
│   │   │   ├── base.py              # SQLAlchemy base
│   │   │   └── session.py           # 会话工厂
│   │   ├── models/                  # ORM 模型
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   └── mock_api.py
│   │   ├── schemas/                 # Pydantic schemas
│   │   ├── auth/                    # JWT、密码哈希
│   │   ├── api/v1/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── projects.py
│   │   │   └── mocks.py
│   │   └── mock_engine/
│   │       ├── engine.py            # 内存路由表
│   │       ├── matcher.py           # method+path 匹配
│   │       ├── renderer.py          # Jinja2 模板渲染
│   │       └── routes.py            # /m/* 入口路由
│   ├── alembic/                     # 数据库迁移
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.ts
│   │   ├── router/
│   │   ├── stores/                  # Pinia
│   │   ├── api/                     # Axios 封装
│   │   ├── views/
│   │   ├── components/
│   │   └── layouts/
│   ├── package.json
│   └── Dockerfile                   # 多阶段构建(Vite build → nginx)
│
├── nginx/
│   ├── nginx.conf                   # 反向代理 + 静态文件服务
│   └── Dockerfile
│
├── docker-compose.yml               # 一键起 backend + frontend + mysql
├── .env.example                     # 环境变量示例
└── README.md
```

### 8.2 Docker Compose 服务

```yaml
services:
  mysql:
    image: mysql:8
    volumes:
      - mysql_data:/var/lib/mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: test_platform

  backend:
    build: ./backend
    depends_on: [mysql]
    environment:
      DATABASE_URL: mysql+asyncmy://...
      JWT_SECRET: ${JWT_SECRET}
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

  frontend:
    build: ./frontend
    depends_on: [backend]
    ports:
      - "80:80"

volumes:
  mysql_data:
```

### 8.3 部署后访问入口

- 平台 UI:`http://平台域名/`
- 被测系统访问 Mock:`http://平台域名/m/<path>`,**无需 token**

---

## 9. 测试策略

| 层 | 工具 | 覆盖目标 |
|---|---|---|
| 后端单元测试 | pytest + pytest-asyncio | 模板渲染、路径匹配、权限校验、JWT 签发/校验 |
| 后端集成测试 | pytest + httpx + 测试 MySQL | API 端到端(create/read/update/delete)、Mock 引擎全流程 |
| 前端单元测试 | Vitest + Vue Test Utils | 关键组件(权限按钮显隐) |

**覆盖率目标**:后端核心模块(Mock 引擎、auth、权限)≥ 80%;整体 ≥ 60%。

---

## 10. 后续

- 本规格文档落地后,转入 `superpowers:writing-plans` 制定实施计划。
- 第二份规格文档(造数功能)单独进行 brainstorming → spec → plan → implementation 循环。
- 审计日志、Mock 版本控制等高级特性视第二份规格文档与实际使用反馈再决定。
