# Leaper Agent

**会自己进化的 AI 员工框架** — 越用越聪明，不是口号，是工程实现。

大多数 AI Agent 是无状态的：每次对话从零开始，聊过的事情不记得，犯过的错再犯一遍。Leaper 不一样：它从每次对话中提取结构化经验，聚类成可复用技能，构建你的心理模型，还会自我验证知识的一致性。六层进化，持续运行。

---

## 一句话安装

```bash
pip install leaper-agent
leaper init
leaper run
```

不需要 C++ 编译器。不需要 GPU。纯 Python，零原生依赖。

---

## 为什么选 Leaper？

| 特性 | 说明 |
|------|------|
| **真正的记忆，不是记事本** | 每段对话从四个维度（任务/策略/结果/洞察）提取经验，经过 4 道质量门控，cosine > 0.85 去重，存入本地 SQLite。BM25 + 向量混合召回，RRF 融合排序 — 不是把所有东西塞进 context。 |
| **越用越聪明** | L1 提取经验 → L2 聚类成技能 → L3 合并/废弃/晋升 → L4 构建用户画像 → L5 一致性验证 + 回归测试 + 记忆衰减。每层都有质量门控和可量化指标。 |
| **本地优先的 LLM 策略** | 高频操作（embedding、提取、验证）跑本地 Ollama 模型。只有低频推理（技能合成、用户建模）才调云端。确定性操作用规则，不用 LLM。 |
| **产品级安装体验** | 交互式向导，不需要手动编辑配置文件。Windows / macOS / Linux 都行。 |
| **15+ 平台即插即用** | Telegram · Discord · Slack · WhatsApp · Signal · 飞书 · 钉钉 · Matrix · 邮件 · Home Assistant · API · 终端 — 一个进程连接所有平台。 |
| **搜索零配置** | DuckDuckGo 兜底，不需要任何 API Key。加 Firecrawl / Tavily 可以深度搜索。 |
| **模板系统** | `leaper init --template ceo-coach` 一条命令创建一个专业 AI 员工。10 个 CXO 角色 + 20 个行业适配。 |

---

## DeepBrain：六层自进化记忆引擎

这是 Leaper 和所有其他 Agent 框架的根本区别。

### 为什么不用 RAG？

现有 Agent 的"记忆"无非两种模式：

1. **全量注入** — 把所有东西写进 MEMORY.md，每轮全部塞进 system prompt。问题：context 线性增长，50 次对话后成本不可控。
2. **RAG 向量检索** — 把记忆 embed 后每轮 Top-K 召回。问题：纯向量搜索对精确术语匹配很差（"MST 状态机"检索不到"Mission State Transition"），也处理不了知识衰减和冲突。

DeepBrain 的方案：**BM25 精确匹配 + 向量语义搜索，RRF 融合排序，六层进化闭环。** 不是 RAG — 是认知进化系统。

### 数据流

```
用户消息 → 核心引擎处理 → Agent 回复
                                ↓
                          sync_turn() 触发
                                ↓
                  ┌───────────────────────────┐
                  │  L1 经验提取               │
                  │  四维分析 → 4Gate → 存储   │
                  └─────────────┬─────────────┘
                                ↓（积累 5+ 条）
                  ┌───────────────────────────┐
                  │  L2 技能生成               │
                  │  聚类 → 合成 → 回测       │
                  └─────────────┬─────────────┘
                                ↓（周期性）
                  ┌───────────────────────────┐
                  │  L3 跨技能进化             │
                  │  MERGE / DEPRECATE / PROMOTE│
                  └─────────────┬─────────────┘
                                ↓（数据充足时）
                  ┌───────────────────────────┐
                  │  L4 用户建模               │
                  │  多维画像构建              │
                  └─────────────┬─────────────┘
                                ↓（每次写入后）
                  ┌───────────────────────────┐
                  │  L5 对抗验证               │
                  │  一致性 + 回归 + 衰减      │
                  └───────────────────────────┘

召回路径（独立于进化）：
用户消息 → L0 混合召回 → RRF 融合 → Top-K 注入 context
```

---

### L0 — 混合召回

**问题**：纯向量搜索对精确术语匹配差。纯关键词搜索理解不了"进化"和"越来越聪明"是同一个意思。

**方案**：BM25 + 向量搜索，RRF 融合。

```
RRF_score(d) = Σ 1 / (k + rank_i(d))    k = 60
```

两路排序：
1. **BM25**：SQLite 关键词搜索 — 精确匹配术语、缩写、代号
2. **768 维向量**：`nomic-embed-text`（274MB）本地 embedding — 语义理解

**为什么用 RRF 而不是加权平均？** RRF 与分数尺度无关。BM25 分数范围 0–25，cosine 范围 0–1。加权平均需要归一化，参数难调。RRF 只看排名位置 — 自动处理两路排序器的质量差异。

**优雅降级**：
- Ollama + nomic-embed-text 可用 → 完整 RRF
- Ollama 没装 embedding 模型 → 纯 BM25
- 没有 Ollama → SQLite LIKE 关键词搜索

---

### L1 — 经验提取

**问题**：多数 Agent 让 LLM 自由决定记什么。结果：同一件事存 5 遍，琐碎信息占 40%+，没有质量过滤。

**方案**：结构化四维提取 + 4Gate 质量门控。

每轮对话后 LLM 返回结构化 JSON：

```json
{
  "task": "用户要做什么",
  "strategy": "选了什么方案",
  "outcome": "结果如何，成功还是失败",
  "insight": "可复用的经验总结"
}
```

**4Gate 质量门控**：
1. **任务成功门** — 失败的对话不提取（避免存垃圾）
2. **复杂度门** — < 30 字符 = trivial，过滤掉"你好""谢谢""好的"
3. **去重门** — cosine > 0.85 的已有记忆不重复存
4. **完整度门** — 四个维度都必须有实质内容（≥ 10 字符）

**实测**：约 27% 对话被 4Gate 过滤，73% 有效存储率。

---

### L2 — 技能生成

**问题**：经验是一次性的（"那次分析了 Dify 竞品"）。技能是可复用的（"怎么做竞品分析"）。用了 20 次后，Agent 应该自己总结出方法论。

**方案**：聚类相似经验 → LLM 合成技能 → 回测验证。

- **聚类**：贪心 cosine 聚类，阈值 0.7，每簇至少 5 条经验
- **合成**：LLM 收到一个聚类，输出技能定义（标题/内容/适用场景/置信度）
- **回测**：把新技能应用到历史问题上，对比原始回答质量

---

### L3 — 跨技能进化

**问题**：技能越积越多，出现冗余（"竞品分析 v1"和"竞品分析 v2"说的是同一件事）和过时。

| 操作 | 触发条件 | 动作 |
|------|----------|------|
| **MERGE** | 两个技能 cosine > 0.8 | 合并，保留高置信度结构 |
| **DEPRECATE** | access_count = 0 且 confidence < 0.5 | 标记废弃，降低召回权重 |
| **PROMOTE** | access_count > 10 且 confidence > 0.8 | 标记核心技能，提升召回权重 |

加**漂移检测**：一个技能 90+ 天未使用且新经验与之矛盾 → 触发重审。

**L3 零 LLM 调用。** MERGE/DEPRECATE/PROMOTE 全是确定性规则操作。这是分层设计的核心：**确定性操作用规则；只有模糊推理才用 LLM。**

---

### L4 — 用户建模

**问题**：Agent 不了解你。同一个问题，给 CEO 和给工程师的回答应该完全不同。

**方案**：自动从对话中构建多维用户画像。

```json
{
  "communication_style": "直接、数据驱动、不喜欢废话",
  "decision_patterns": "先看数据再下判断。偏好 MVP 验证而非完美方案",
  "recurring_topics": ["AI 趋势", "竞品分析", "产品架构"],
  "expertise_level": "expert",
  "confidence": 0.78
}
```

**更新策略**：增量融合，不是覆盖。新观察和已有画像贝叶斯融合。一次对话不会推翻整个用户模型。

---

### L5 — 对抗验证

记忆引擎的免疫系统。每次写入后自动触发：

- **一致性检查**：新条目 vs 已有知识库。矛盾会被标记，不会被悄悄覆盖。
- **回归保护**：技能更新后，对历史 Top-5 问题回测。质量下降则回滚。
- **衰减**：线性衰减，未使用的条目每 7 天 `access_count -= 1`。access_count = 10 的条目 70 天归零 — 可预测，不像指数衰减永远不到零。

**L5 100% 基于规则，零 LLM 调用。** 验证层不能依赖 LLM — 否则 LLM 幻觉会感染验证结果。

---

## LLM 分层降级策略

| 层级 | 操作 | 计算位置 | 模型 | 频率 |
|------|------|----------|------|------|
| L0 | 向量生成 | 本地 | nomic-embed-text (274MB) | 每轮 |
| L0 | BM25 搜索 | 本地 | SQLite 内置 | 每轮 |
| L1 | 经验提取 | 本地 | qwen2.5:7b (4.7GB) | 每轮 |
| L1 | 质量门控 | 规则 | — | 每轮 |
| L2 | 聚类 | 本地 | Cosine 相似度 | 积累 5+ 条 |
| L2 | 技能合成 | 云端 | 主模型 | 低频 |
| L3 | MERGE/DEPRECATE/PROMOTE | 规则 | — | 周期性 |
| L4 | 画像构建 | 云端 | 主模型 | 低频 |
| L5 | 一致性/回归/衰减 | 规则 | — | 每次写入 |

**高频 = 本地/规则，零 API 成本。低频 = 云端 LLM。**

启动时自动检测：有 Ollama → 本地优先。没有 Ollama → 全部走云端。

---

## 10 个 CXO 角色模板

一条命令创建一个专业 AI 员工：

```bash
leaper init --template cfo
```

| # | 角色 | 模板 ID | 说明 | 专属技能数 |
|---|------|---------|------|-----------|
| 1 | 🎯 CEO Coach — 创业决策教练 | `ceo-coach` | 苏格拉底式提问 + 40 商业框架 | 10 |
| 2 | 💻 CTO — 技术战略顾问 | `cto` | 技术选型、架构设计、安全审计 | 9 |
| 3 | 💰 CFO — 财务战略顾问 | `cfo` | 现金流、融资准备、预算、税务 | 9 |
| 4 | 📣 CMO — 市场增长顾问 | `cmo` | 定位、GTM、获客、竞品监控（含 CRO） | 8 |
| 5 | ⚙️ COO — 运营执行顾问 | `coo` | OKR 追踪、会议管理、SOP 建设 | 7 |
| 6 | 🎯 CPO — 产品战略顾问 | `cpo` | PRD 撰写、路线图、用户故事 | 8 |
| 7 | 👥 CHRO — 人力战略顾问 | `chro` | JD、面试设计、薪酬方案、组织架构 | 8 |
| 8 | ⚖️ CLO — 法务战略顾问 | `clo` | 合同审核、合规、知识产权 | 7 |
| 9 | 🧭 CSO — 首席战略官 | `cso` | 行业分析、情景规划、商业模式 | 9 |
| 10 | 📢 CCO — 品牌传播顾问 | `cco` | 公众号、创始人 IP、舆情、危机公关 | 7 |

**合计 82 个专属技能**，覆盖创业公司从战略到执行的全部核心职能。

---

## 20 个行业适配

通用模板开箱即用。有行业专属版时自动适配：

`ecom` · `adtech` · `invest` · `edu` · `health` · `b2b` · `finance` · `consumer` · `auto` · `mfg` · `realestate` · `energy` · `logistics` · `travel` · `agri` · `construction` · `legal` · `hr` · `fitness` · `media`

**150 个模板目录，709 个配置文件。**

### 三层技能架构

```
L1 行业技能（21 个）  ← 行业专属知识（如电商的 GMV 分析框架）
L2 角色技能（10 个）  ← 角色通用能力（如 CFO 的财务建模方法论）
L3 工位技能（72 个）  ← 具体工作场景（如 CFO 的现金流预测）
```

系统自动匹配：选了 CFO + 电商行业 → 加载 `L1-ecom` + `L2-cfo-financial-modeling` + `L3-cfo-cashflow/budget/cost/...`

---

## 多 Agent 架构

一个进程运行多个 AI 角色：

```bash
leaper init-team    # 交互式向导：添加角色 + Token
leaper run          # 所有 Agent 同时启动（~1GB 内存）
```

每个 Agent 独立拥有：
- **隔离的工作区**（`~/.leaper/agents/{role}/`）
- **隔离的 brain.db**（记忆不会串）
- **独立的 Telegram Bot**（一个 Token 对应一个角色）
- **共享的模型配置**（所有角色用同一个 LLM Provider）

配置示例（`~/.leaper/config.yaml`）：
```yaml
model: claude-sonnet-4-20250514
agents:
  - id: cfo
    workspace: ~/.leaper/agents/cfo
    platforms:
      telegram:
        token: '111:AAA...'
  - id: cto
    workspace: ~/.leaper/agents/cto
    platforms:
      telegram:
        token: '222:BBB...'
```

---

## 15+ 平台连接

单进程连接所有平台，对话跨平台持久化。

| 平台 | 协议 | 配置方式 |
|------|------|----------|
| **Telegram** | Bot API | `TELEGRAM_BOT_TOKEN` |
| **Discord** | discord.js | `DISCORD_BOT_TOKEN` |
| **Slack** | Bolt SDK | `SLACK_BOT_TOKEN` |
| **WhatsApp** | Baileys | config.yaml |
| **Signal** | signal-cli | config.yaml |
| **飞书** | Open API | config.yaml |
| **钉钉** | Stream SDK | config.yaml |
| **Matrix** | matrix-nio | config.yaml |
| **邮件** | IMAP/SMTP | config.yaml |
| **Home Assistant** | REST API | config.yaml |
| **API** | HTTP/WebSocket | 内置 |
| **终端** | 本地 | `leaper chat` |

---

## 40+ 内置工具

| 类别 | 工具 |
|------|------|
| **终端 & 文件** | `terminal` · `file_read` · `file_write` · `file_edit` |
| **搜索 & 网络** | `web_search` · `web_fetch` — 降级链：Firecrawl → Tavily → DuckDuckGo（零配置） |
| **代码 & 开发** | `code_execute` · `git` · `github` |
| **媒体** | `image_generation` · `tts` · `vision` · `pdf_reader` |
| **自动化** | `cron` · `delegation` · `webhook` |

支持 [MCP 协议](https://modelcontextprotocol.io)扩展第三方工具。

---

## 模型支持

| 提供商 | 模型举例 | 配置 |
|--------|---------|------|
| **OpenAI** | GPT-4o, GPT-4.1, o3 | `OPENAI_API_KEY` |
| **Anthropic** | Claude Opus 4, Sonnet 4 | `ANTHROPIC_API_KEY` |
| **OpenRouter** | 200+ 模型 | `OPENROUTER_API_KEY` |
| **Ollama** | qwen2.5, llama3, deepseek-r1 | 本地，零配置 |
| **任意兼容 API** | 聚合平台 / 私有部署 | `base_url` + `api_key` |

模型故障自动切换 fallback。

---

## 前置条件

| 工具 | 版本 | 下载 | 备注 |
|------|------|------|------|
| **Python** | ≥ 3.10 | [python.org/downloads](https://www.python.org/downloads/) | ⚠️ Windows 安装时勾选 "Add python.exe to PATH" |
| **Git** | 任意 | [git-scm.com/download](https://git-scm.com/download/) | 可选，仅开发者需要 |
| **Ollama**（可选） | 任意 | [ollama.com/download](https://ollama.com/download) | 本地模型用。只用云端 API 则不需要 |

> 💡 Windows 安装 Python 后，**关闭并重新打开 PowerShell** 让 PATH 生效。

---

## 快速安装

```bash
pip install leaper-agent
```

**不需要 C++ 编译器。不需要 GPU。**

```bash
leaper init                          # 交互式向导
leaper init --template ceo-coach     # 从模板创建
leaper init-team                     # 多角色团队配置
leaper chat                          # 终端对话
leaper run                           # 启动 Gateway（Telegram 等）
leaper workshop                      # 浏览模板市场
```

---

## 配置

```yaml
# leaper.yaml
name: 'CEO Coach'

model:
  provider: openai
  name: gpt-4o

channel:
  type: telegram

brain:
  enabled: true
  localModel: auto    # auto = 检测 Ollama | off = 仅用云端
```

---

## DB Schema

`brain.db` — 本地 SQLite，1000+ 条记忆通常 < 10MB。

```sql
CREATE TABLE pages (
    slug TEXT PRIMARY KEY,
    title TEXT,
    namespace TEXT,          -- agent/{name} | desk/{name}/{seat} | role/{role} | org
    content TEXT,
    entry_type TEXT,         -- experience | skill | user_model | meta
    confidence REAL,         -- 0.0 - 1.0
    access_count INTEGER,    -- L5 衰减用
    last_accessed TEXT,
    metadata TEXT,           -- JSON 扩展字段
    updated_at TEXT
);

CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    page_slug TEXT REFERENCES pages(slug),
    content TEXT             -- 分块内容，用于向量搜索
);
```

---

## 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `LEAPER_HOME` | 工作目录 | `~/.leaper` |
| `LEAPER_LOCAL_URL` | 本地 Ollama 地址 | `http://localhost:11434/v1` |
| `LEAPER_LOCAL_MODEL` | 本地推理模型 | `qwen2.5:7b` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | — |
| `OPENAI_API_KEY` | OpenAI API Key | — |
| `ANTHROPIC_API_KEY` | Anthropic API Key | — |

---

## 开发者

```bash
git clone https://github.com/Deepleaper/leaper-agent.git
cd leaper-agent
python -m venv venv && source venv/bin/activate
pip install -e ".[all,dev]"
```

### DeepBrain 代码结构（~1951 行）

```
agent/
  leaper_brain.py           # 564 行 — L0 混合召回、DB 操作
  leaper_evolution.py       # 992 行 — L1-L5 进化逻辑
  leaper_orchestrator.py    # 137 行 — 进化调度器
  leaper_seed_loader.py     #        — 工作区文件加载 + OS 注入

plugins/memory/deepbrain/
  provider.py               # 258 行 — Memory Provider 接口
  plugin.yaml
```

---

## 开源协议

Apache-2.0 © [Deepleaper 跃盟科技](https://www.deepleaper.com)
