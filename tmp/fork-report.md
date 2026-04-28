# Leaper Python Fork Report

**Fork 日期：** 2026-04-26  
**上游：** Hermes Agent v0.11.0 (NousResearch/hermes-agent, MIT)  
**输出：** Leaper Agent v0.7.0 (leaper-python/)

---

## 一、品牌变更（Brand Changes）

### 1.1 项目元数据（pyproject.toml）

| 字段 | Hermes 原值 | Leaper 新值 |
|------|-------------|-------------|
| `name` | `hermes-agent` | `leaper-agent` |
| `version` | `0.11.0` | `0.7.0` |
| `description` | "The self-improving AI agent…" | "自进化 AI 员工框架…" |
| `authors` | Nous Research | Deepleaper |
| `license` | MIT | Apache-2.0 |
| `requires-python` | `>=3.11` | `>=3.10` |
| `scripts.hermes` | `hermes_cli.main:main` | 保留（内部使用） |
| `scripts.leaper` | — | `leaper_cli:main`（新增） |
| extras `termux` | 自引用 `hermes-agent[...]` | 已移除（待适配）|

新增依赖：`inquirer>=3.1.0,<4`（`leaper init` 交互向导）

### 1.2 Home 目录与环境变量（hermes_constants.py）

| 项目 | Hermes | Leaper |
|------|--------|--------|
| 默认数据目录 | `~/.hermes` | `~/.leaper` |
| 主环境变量 | `HERMES_HOME` | `LEAPER_HOME`（优先），兼容 `HERMES_HOME` |
| 新增函数 | — | `get_leaper_home()` |
| `get_default_hermes_root()` | 检查 `~/.hermes` | 检查 `~/.leaper` |

> **兼容性说明：** 代码内部仍以 `get_hermes_home()` 为函数名，确保 agent/gateway/tools 所有现有调用零改动。

### 1.3 CLI 入口

| 命令 | Hermes | Leaper |
|------|--------|--------|
| 主 CLI | `hermes` | `leaper`（新） |
| 子命令 | `hermes chat/gateway/setup/…` | `leaper init/run/chat/status` |
| 底层实现 | `hermes_cli/main.py`（保留） | `leaper_cli.py`（新，简化版） |

---

## 二、新增文件（New Files）

### 2.1 agent/leaper_brain.py — SQLite 知识库

**类：** `LeaperBrain`

| 方法 | 说明 |
|------|------|
| `__init__(db_path)` | 初始化 SQLite，建表 `leaper_brain` |
| `learn(content, source, namespace)` | 存储知识条目，UUID 主键，返回 id |
| `recall(query, top_k, namespace)` | 关键词 LIKE 搜索 + 评分排序 |
| `forget(entry_id)` | 删除指定条目 |
| `get_stats()` | 返回总条数、命名空间统计 |
| `close()` | 关闭连接 |

**数据库结构：**
```sql
CREATE TABLE leaper_brain (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    keywords    TEXT NOT NULL,    -- JSON 数组
    source      TEXT,             -- 来源标记
    namespace   TEXT,             -- 命名空间
    layer       TEXT,             -- l0/l1/l2/seed
    created_at  TEXT,
    updated_at  TEXT
)
```

**召回逻辑（对应 TS recall.ts）：**
- 将 query 拆词后对 `content` 和 `keywords` 做 LIKE 搜索
- 结果按 `_score()` 函数排序（content_hits + kw_hits × 0.5）
- 支持 `namespace` 过滤

### 2.2 agent/leaper_evolution.py — 进化引擎

**类：** `EvolutionEngine`

| 层级 | 方法 | 状态 |
|------|------|------|
| L0 | `hybrid_recall(query, top_k, namespace)` | ✅ 完整实现 |
| L0 | `format_recall_for_prompt(query, top_k)` | ✅ 完整实现 |
| L1 | `experience_extract(user_msg, assistant_msg)` | ✅ 规则 + 可选 LLM |
| L2 | `skill_generate(experiences)` | ✅ 规则 + 可选 LLM |
| L3 | `skill_evolve(skills)` | 🔲 Placeholder |
| L4 | `user_model_update(conversation)` | 🔲 Placeholder |
| L5 | `validate(skill)` | 🔲 Placeholder |

**L1 提取字段（对应 TS L1Output）：**
```python
{
  "keywords": [...],
  "summary": "...",
  "task_success": bool,
  "user_satisfaction": "positive|neutral|negative|unknown",
  "reasoning_pattern": str | None,
  "complexity": "trivial|moderate|complex",
  "tools_used": [...]
}
```

**L2 生成字段（对应 TS GeneratedSkill）：**
```python
{
  "name": "snake_case_name",
  "description": "...",
  "triggers": [...],
  "procedure": "...",
  "confidence": 0.0-1.0,
  "source": "auto-generated",
  "version": 1,
  "status": "unverified"
}
```

### 2.3 agent/leaper_seed_loader.py — Workspace 文件加载器

**函数：** `load_workspace_files(workspace_dir, brain)`

**行为（对应 TS seed-loader.ts）：**

| 文件类型 | 处理方式 |
|----------|----------|
| `ALWAYS_LOAD` (EGO.md, SOUL.md, IDENTITY.md, USER.md, MEMORY.md) | 每次启动都注入 system prompt |
| `EXCLUDE` (README.md, CHANGELOG.md, LICENSE.md) | 跳过 |
| 其他 `.md` 文件 | 首次启动时种子化到 Brain（标记 `.leaper-seeded`） |

**返回值：**
```python
{
  "system_prompt_block": str,   # 注入 system prompt 的内容
  "seeded_count": int,          # 本次种子化的文件数
  "always_load_files": [str]    # 本次注入的 ALWAYS_LOAD 文件列表
}
```

### 2.4 plugins/memory/leaper/ — LeaperMemoryProvider 插件

**文件：**
- `__init__.py` — 插件注册 (`register(ctx)`)
- `provider.py` — `LeaperMemoryProvider(MemoryProvider)` 实现
- `plugin.yaml` — 插件元数据

**LeaperMemoryProvider 实现要点：**

| 方法 | 实现 |
|------|------|
| `name` | `"leaper"` |
| `is_available()` | 始终返回 True（本地 SQLite，无外部依赖） |
| `initialize(session_id, **kwargs)` | 初始化 Brain + SeedLoader，读 `hermes_home` kwarg |
| `system_prompt_block()` | 返回 Brain 使用说明 + workspace 内容 |
| `prefetch(query)` | 调用 `EvolutionEngine.format_recall_for_prompt()` |
| `sync_turn(user, asst)` | 后台线程：L1 提取 → 高质量条目存 Brain |
| `get_tool_schemas()` | `brain_recall`, `brain_learn` 两个工具 |
| `handle_tool_call()` | 分发到 `_handle_recall()` / `_handle_learn()` |
| `get_config_schema()` | 返回 `LEAPER_BRAIN_DB` 配置项 |
| `shutdown()` | 关闭 Brain SQLite 连接 |

### 2.5 leaper_config.py — YAML 配置读取器

**函数：**

| 函数 | 说明 |
|------|------|
| `load_leaper_config(config_path)` | 按优先级加载 leaper.yaml |
| `_apply_env_overrides(cfg)` | LEAPER_* 环境变量覆盖 |
| `config_to_hermes_env(cfg)` | 转换为 Hermes 所需的环境变量字典 |
| `write_hermes_config(cfg, leaper_home)` | 写入 ~/.leaper/config.yaml |

**搜索优先级：**
1. 显式传入路径
2. `./leaper.yaml`（当前目录）
3. `~/.leaper/leaper.yaml`（用户全局）

### 2.6 leaper_cli.py — 简化版 CLI

**命令：**

| 命令 | 实现 |
|------|------|
| `leaper init [workspace]` | Rich 交互向导，生成 leaper.yaml + .env |
| `leaper run [workspace]` | 加载配置 → 设置环境变量 → 启动 gateway 或 CLI |
| `leaper chat [workspace]` | 加载配置 → 委托 hermes_cli.main |
| `leaper status [workspace]` | 显示配置表 + Brain 统计 |

**依赖：** `fire`（CLI 框架）、`rich`（输出）、`inquirer`（init 向导）

### 2.7 leaper.yaml — 示例配置文件

详见文件注释，覆盖：provider / channel / brain / proxy 四个顶层块。

---

## 三、未改动内容（Unchanged）

| 目录/文件 | 状态 | 说明 |
|-----------|------|------|
| `gateway/` | ✅ 原封不动 | 所有平台适配器 |
| `agent/` (非 leaper_*.py) | ✅ 原封不动 | 核心推理、记忆管理、传输层 |
| `tools/` | ✅ 原封不动 | 40+ 工具实现 |
| `plugins/memory/honcho/` | ✅ 原封不动 | Honcho 记忆提供商 |
| `plugins/memory/holographic/` | ✅ 原封不动 | Holographic 记忆 |
| `hermes_cli/` | ✅ 原封不动 | Hermes 原生 CLI（leaper chat 委托给它）|
| `run_agent.py` | ✅ 原封不动 | 主 agent 执行器（12772 行）|
| `cli.py` | ✅ 原封不动 | 终端 TUI |
| `cron/` | ✅ 原封不动 | Cron 调度器 |
| `skills/` | ✅ 原封不动 | 内置 Skill |

---

## 四、运行验证路径

### leaper run（Telegram 模式）

```
leaper run
  → _bootstrap_env()        加载 .env
  → load_leaper_config()    读取 leaper.yaml
  → config_to_hermes_env()  转换为 Hermes env vars
  → write_hermes_config()   写入 ~/.leaper/config.yaml
  → _run_gateway("telegram") → gateway.run.main(platform="telegram")
  → LeaperMemoryProvider.initialize()  初始化 Brain + SeedLoader
  → 正常 Hermes 对话循环
```

### leaper chat（终端模式）

```
leaper chat
  → 同上环境准备
  → hermes_cli.main.main()  委托原生 Hermes CLI
```

---

## 五、已知限制与 TODO

| 项目 | 状态 |
|------|------|
| L3 Skill Evolution | 🔲 Placeholder，待实现 |
| L4 User Model | 🔲 Placeholder，待实现 |
| L5 Validation | 🔲 Placeholder，待实现 |
| Brain 向量搜索 | 🔲 目前仅关键词，可接入 Ollama nomic-embed |
| Brain 命名空间 ACL | 🔲 目前无权限控制 |
| `leaper init` 模板选择 | 🔲 当前仅交互式，无模板库 |
| Termux 支持 | 🔲 pyproject.toml 中已移除，待适配 |
| `leaper gateway` 子命令 | 🔲 计划直接对接 hermes gateway |
| 测试覆盖 | 🔲 新增文件均无单元测试 |

---

*生成时间：2026-04-26 by Leaper CTO Agent*
