# Warehouse Agent

独立的 AI 数仓研发平台。V2 不依赖 `bigdata-platform`，并按你的实际环境采用 **DolphinScheduler MySQL → 本地现有代码 → Agent 本地工作区 → SQL 执行 → 数据校验 → 人工验收 → 发布包**。

## 架构

```text
DolphinScheduler MySQL
        ↓ 只读
DS Importer
        ↓
data/source/dolphinscheduler/     # 现有 SQL，只读
        ↓
Code Index / SQL AST / Lineage
        ↓
Warehouse Agent
        ↓
data/workspaces/<task_no>/        # Agent 新代码，可写
        ↓
Agent Dev MySQL / StarRocks
        ↓
自动数据校验
        ↓
人工验收
        ↓
data/releases/<task_no>/          # RELEASE_READY
```

当前版本**不会自动写回 DolphinScheduler**。人工验收通过后只生成发布包，后续再增加独立的 DS 发布审批步骤。

## 本地目录

```text
data/
├── source/
│   └── dolphinscheduler/
│       └── <project>__<code>/<workflow>__<code>/<task>__<code>/
│           ├── task.sql
│           └── task.json
├── workspaces/
│   └── DW-xxxx/
│       ├── requirement.md
│       ├── context/
│       ├── design/model.json
│       ├── sql/ddl/
│       ├── sql/etl/
│       ├── validation/
│       └── result/
└── releases/
    └── DW-xxxx/
        ├── design/
        ├── sql/
        ├── validation/
        ├── manifest.json
        └── release-note.md
```

`source/` 是现有生产代码快照，Agent 只读；所有新代码只写 `workspaces/`。

## DolphinScheduler 读取

V2 只读 DS MySQL 的核心表：

- `t_ds_project`
- `t_ds_process_definition`
- `t_ds_task_definition`
- `t_ds_process_task_relation`

SQL 从 `task_params` JSON 中提取，同时把项目、工作流、任务、数据源引用、上下游 task code 写入 `task.json`。由于 DS 不同版本字段会变化，导入器在运行时读取现有表结构并保留兼容逻辑。

## 启动

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

默认 `APP_MOCK_EXTERNAL=true`，不连接真实 DS / StarRocks 也能跑完整链路。接真实环境后改成 `false`。

## 核心 API

### DS → 本地 source

- `GET /api/dolphinscheduler/config`
- `PUT /api/dolphinscheduler/config`
- `POST /api/dolphinscheduler/test`
- `POST /api/dolphinscheduler/import`
- `GET /api/source/files`
- `GET /api/source/files/{id}`
- `POST /api/source/index/rebuild`
- `GET /api/source/lineage`
- `GET /api/source/task-dependencies`

### 数据源与元数据

- `GET/POST /api/datasources`
- `POST /api/datasources/{id}/test`
- `POST /api/datasources/{id}/metadata/scan`
- `GET /api/metadata/tables`
- `GET /api/metadata/tables/{id}`

### Agent 工作区

- `POST /api/tasks`
- `GET /api/tasks/{id}`
- `GET /api/tasks/{id}/workspace/files`
- `PUT /api/tasks/{id}/code`
- `POST /api/tasks/{id}/sql/validate`
- `POST /api/tasks/{id}/sql/execute`
- `POST /api/tasks/{id}/validations/run`
- `POST /api/tasks/{id}/review/approve`
- `POST /api/tasks/{id}/review/reject`
- `GET /api/releases`

## 安全边界

- DS 元数据库仅需 `SELECT` 权限。
- `source/` 只读。
- 新代码只写 `workspaces/`。
- 生产数据源建议只读。
- 写 SQL 仅允许 Agent Dev 环境。
- 默认拦截 `DROP / DELETE / UPDATE / ALTER / TRUNCATE / GRANT / REVOKE`。
- 人工验收前不生成发布包。
- 当前版本不自动修改 DS 任务。

## 测试

```bash
pytest -q
```

当前回归测试覆盖 DS Mock 导入、本地代码落盘、表级血缘、DS task dependency、任务 workspace、SQL 执行、自动校验、驳回和人工验收 release。
