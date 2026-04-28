# ⚡ Leaper Agent

**自进化 AI 员工框架** — 不只是调 API 的 Agent，而是一个越用越聪明的 AI 同事。

基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent)（MIT © Nous Research）fork，核心增量是 **DeepBrain 自进化记忆引擎** — 六层闭环进化系统，让 Agent 从经验中学习、归纳、建模、自检。同时继承 Hermes 的全部能力：40+ 工具、15+ 平台、TUI 终端、Cron 调度、子代理委派。

<table>
<tr><td><b>真正的记忆，不是笔记本</b></td><td>现有 Agent 框架的 memory 本质是"LLM 往文件追加文本"。Leaper 的 DeepBrain 引擎对每轮对话做四维结构化提取（任务/策略/结果/洞察），经过 4Gate 质量门控才写入。相似度 > 0.85 的内容自动去重。BM25 + 向量 RRF 混合召回，不再把全部记忆塞进 context。</td></tr>
<tr><td><b>越用越聪明，可验证</b></td><td>L1 提取经验 → L2 聚类为可复用技能 → L3 合并/淘汰/晋升技能 → L4 构建用户心智模型 → L5 一致性校验 + 回归防护。每一层都有质量门控和实测数据，不是 marketing 口号。</td></tr>
<tr><td><b>LLM 分层降级</b></td><td>L0-L2 的 embedding 和提取使用本地 Ollama 小模型（qwen2.5:7b / nomic-embed-text），只有 L3-L4 的归纳推理才调云端 LLM。高频操作零 API 成本。</td></tr>
<tr><td><b>产品级安装体验</b></td><td><code>git clone</code> + <code>pip install -e ".[all]"</code> + <code>leaper init</code> + <code>leaper run</code> — 交互式向导，全程不需要手动改配置文件。纯 Python，无 C++ 编译依赖。</td></tr>
<tr><td><b>15+ 平台开箱即用</b></td><td>Telegram · Discord · Slack · WhatsApp · Signal · 飞书 · 钉钉 · Matrix · Email · Home Assistant · API · CLI — 单 gateway 进程连接所有平台。</td></tr>
<tr><td><b>零配置搜索</b></td><td>DuckDuckGo 兜底，不需要任何 API Key。配了 Firecrawl / Tavily 自动升级为深度搜索。</td></tr>
<tr><td><b>模板系统</b></td><td><code>leaper init --template ceo-coach</code> 一行创建专业 AI 员工。CEO Coach 模板：苏格拉底式教练 + 40 个商业分析框架 + 六层记忆。更多模板持续发布。</td></tr>
</table>

---

## DeepBrain 六层自进化记忆引擎

这是 Leaper 与所有 Agent 框架的核心区别。

### 为什么不用 RAG？

现有 Agent 的"记忆"方案有两种：

1. **MEMORY.md 全文注入** — 把所有记忆写进一个文件，每次对话全部塞进 system prompt。问题：context window 线性增长，成本不可控，50 轮对话后 token 费用翻倍。
2. **RAG 向量检索** — 对记忆做 embedding，每次检索 Top-K。问题：纯向量搜索对精确术语匹配差（"MST 状态机"搜不到"Mission State Transition"），且无法处理记忆的质量衰减和知识冲突。

DeepBrain 的设计选择：**BM25 精确匹配 + 向量语义搜索，RRF 融合排序，六层进化闭环。** 不是 RAG，是认知进化系统。

### 数据流全景

```
用户消息 → Hermes 基座处理 → Agent 回复
                                   ↓
                            sync_turn() 触发
                                   ↓
                     ┌─────────────────────────────┐
                     │  L1 Experience Extract       │
                     │  四维分析 → 4Gate 门控 → 写入  │
                     └──────────────┬───────────────┘
                                   ↓ (积累 5+ 条)
                     ┌─────────────────────────────┐
                     │  L2 Skill Generate           │
                     │  聚类 → 归纳 → 回溯验证       │
                     └──────────────┬───────────────┘
                                   ↓ (定期触发)
                     ┌─────────────────────────────┐
                     │  L3 Cross-Skill Evolution    │
                     │  MERGE / DEPRECATE / PROMOTE │
                     └──────────────┬───────────────┘
                                   ↓ (足够对话数据)
                     ┌─────────────────────────────┐
                     │  L4 User Model               │
                     │  多维画像构建                  │
                     └──────────────┬───────────────┘
                                   ↓ (每次写入后)
                     ┌─────────────────────────────┐
                     │  L5 Adversarial Validation   │
                     │  一致性 + 回归 + 衰减         │
                     └─────────────────────────────┘

召回路径（独立于进化路径）：
用户消息 → L0 Hybrid Recall → RRF 融合 → Top-K 注入 context
```

**触发点**：`provider.py:sync_turn()` — Hermes 基座在每轮对话结束后调用 `memory_manager.sync_all()`，DeepBrain 作为 Memory Provider 插件接收调用。

```
run_agent.py:12499 → _sync_external_memory_for_turn()
  → run_agent.py:4279 sync_all()
    → memory_manager.py:214
      → provider.sync_turn()          # DeepBrain 入口
        → evolution.experience_extract()  # L1
        → orchestrator.maybe_evolve()     # L2-L5 按条件触发
```

---

### L0 — Hybrid Recall（混合召回）

**问题**：纯向量搜索对精确术语匹配差。用户问"MST 的状态转移规则"，向量搜索可能返回"状态机设计模式"这种语义相近但实际无关的内容。纯关键词搜索又无法理解"进化"和"越用越聪明"是同一个概念。

**方案**：BM25 + 向量搜索，RRF 融合排序。

**RRF 公式**：

```
RRF_score(d) = Σ 1 / (k + rank_i(d))
```

其中 `k = 60`（标准 RRF 常数），`rank_i(d)` 是文档 `d` 在第 `i` 个排序器中的排名。两路排序器：

1. **BM25**：基于 SQLite 的关键词搜索，精确匹配术语、缩写、代号
2. **768 维向量**：使用 `nomic-embed-text`（274MB）本地生成 embedding，语义理解

**为什么是 RRF 而不是加权平均？** RRF 对分数尺度不敏感 — BM25 分数范围 0-25，向量 cosine 范围 0-1，直接加权需要归一化且参数难调。RRF 只看排名，两路质量差异大时自动降权。

**降级策略**：
- 有 Ollama + nomic-embed-text → 完整 RRF
- 有 Ollama 无 embedding 模型 → 纯 BM25
- 无 Ollama → SQLite LIKE 关键词搜索

```python
# leaper_brain.py 核心调用
def hybrid_recall(self, query: str, top_k: int = 10) -> list[dict]:
    bm25_results = self._bm25_search(query, top_k=50)
    vector_results = self._vector_search(query, top_k=50)
    return self._rrf_fuse(bm25_results, vector_results, top_k=top_k)
```

---

### L1 — Experience Extract（经验提取）

**问题**：Hermes 的 Background Review 是一个 53 字的 prompt（"review this conversation and decide what to remember"），LLM 自由发挥写什么就存什么。结果：同一件事存 5 遍，trivial 信息占 40%+，无法过滤低质量记忆。

**方案**：结构化四维提取 + 4Gate 质量门控。

#### 四维提取

每轮对话结束后，LLM 被要求返回 JSON：

```json
{
  "task": "用户要求做什么",
  "strategy": "Agent 选择了什么方法",
  "outcome": "结果如何，是否成功",
  "insight": "从这次对话中提炼的可复用洞察"
}
```

**为什么是四个维度？** 来自认知科学的经验学习模型（Kolb's Experiential Learning Cycle）：具体经验(task) → 反思观察(strategy) → 抽象概念化(insight) → 主动实验(outcome)。四维覆盖了一次学习的完整闭环。

#### 4Gate 质量门控

```python
# leaper_evolution.py 门控逻辑
def _should_store(self, experience: dict) -> bool:
    # Gate 1: 任务必须成功
    if not experience.get("task_success"):
        return False  # 失败经验不存（V1 策略，V2 会引入失败学习）
    
    # Gate 2: 复杂度过滤
    complexity = self._estimate_complexity(experience)
    if complexity == "trivial":  # < 30 字符
        return False  # "你好" "谢谢" 不值得存
    
    # Gate 3: 去重
    similar = self.brain.hybrid_recall(experience["task"], top_k=3)
    if similar and similar[0]["score"] > 0.85:
        return False  # 已有高度相似的经验
    
    # Gate 4: 完整性
    for field in ["task", "strategy", "outcome", "insight"]:
        if not experience.get(field) or len(experience[field]) < 10:
            return False  # 四维必须完整且有实质内容
    
    return True
```

**complexity 判定**：基于字符数而非 LLM 判断（实测发现中文场景下 LLM 把所有对话都判为"moderate"）：
- `< 30 字符` → trivial（"你好"、"谢谢"、"ok"）
- `30-200 字符` → moderate
- `≥ 200 字符` → complex

**实测数据**：约 27% 的对话被 4Gate 过滤，73% 有效存储率。Gate 1 过滤约 8%，Gate 2 过滤约 12%，Gate 3 过滤约 5%，Gate 4 过滤约 2%。

---

### L2 — Skill Generate（技能生成）

**问题**：经验是一次性的（"那次分析了 Dify 竞品"），技能是可复用的（"怎么做竞品分析"）。Agent 用了 20 次之后应该自己总结出方法论。

**方案**：相似经验聚类 → LLM 归纳技能 → 回溯验证。

#### 聚类

```python
def _cluster_experiences(self, experiences: list[dict]) -> list[list[dict]]:
    """基于 cosine similarity 的贪心聚类"""
    clusters = []
    used = set()
    for i, exp in enumerate(experiences):
        if i in used:
            continue
        cluster = [exp]
        for j, other in enumerate(experiences[i+1:], i+1):
            if j not in used and self._cosine_sim(exp, other) > 0.7:
                cluster.append(other)
                used.add(j)
        if len(cluster) >= 5:  # 至少 5 条相似经验才值得归纳
            clusters.append(cluster)
    return clusters
```

**为什么阈值是 0.7？** 0.8 太严，同一类任务的表述差异会被拆成多个小簇；0.6 太松，不相关的经验会被错误聚合。0.7 是在 CEO Coach 场景下测试得到的经验值。

#### 技能合成

LLM 接收一组聚类后的经验，输出技能定义：

```json
{
  "title": "竞品技术架构分析",
  "content": "1. 先搜索目标公司最近6个月的技术博客和招聘信息...",
  "applicable_scenarios": ["竞品分析", "技术选型", "架构评审"],
  "confidence": 0.82,
  "source_experiences": ["27d9522a", "88b15224", "0a05f7cb", ...]
}
```

**质量门控**：`title` > 5 字符，`content` > 50 字符。防止 LLM 生成空壳技能。

#### 回溯验证

技能生成后，对源经验做回测：用新技能重新回答历史问题，对比原始回答的质量。如果新技能没有带来质量提升，降低 confidence 但不删除（可能是数据量不够）。

---

### L3 — Cross-Skill Evolution（跨技能进化）

**问题**：技能会随时间累积冗余（"竞品分析 v1"和"竞品分析 v2"说的是同一件事），也会过时（半年前的技术判断可能已经过时）。

**方案**：三种进化操作 + 漂移检测。

| 操作 | 触发条件 | 动作 |
|------|---------|------|
| **MERGE** | 两技能 cosine > 0.8 | 合并为一个，保留高 confidence 版本的结构 |
| **DEPRECATE** | access_count = 0 且 confidence < 0.5 | 标记为废弃，降低召回权重 |
| **PROMOTE** | access_count > 10 且 confidence > 0.8 | 标记为核心技能，提高召回权重 |

**漂移检测**：对比技能的创建时间和最近使用时间，如果 > 90 天未使用且期间有新经验与其矛盾，触发 review 流程。

**为什么 L3 不用 LLM？** MERGE/DEPRECATE/PROMOTE 的判断逻辑是确定性的（基于 cosine 相似度和 access_count），不需要 LLM 的模糊推理。这是分层降级设计的核心：**确定性操作用规则，模糊推理才用 LLM**。

---

### L4 — User Model（用户建模）

**问题**：Agent 不了解用户。同一个问题，对 CEO 和对工程师应该给完全不同的回答。

**方案**：从对话中自动构建多维用户画像。

```json
{
  "communication_style": "直接、数据驱动，不喜欢废话和没有结论的分析",
  "decision_patterns": "先看数据再做判断，倾向于 MVP 验证而非完美方案",
  "recurring_topics": ["AI 技术趋势", "竞品分析", "产品架构", "团队管理"],
  "expertise_level": "expert",
  "confidence": 0.78
}
```

**严格门控**（防止 LLM 编造画像）：

```python
def _validate_user_model(self, model: dict) -> bool:
    # 字段完整性
    required = ["communication_style", "decision_patterns", 
                "recurring_topics", "expertise_level"]
    if not all(model.get(f) for f in required):
        return False
    
    # 实质性检查（不能是空洞的描述）
    if len(model["communication_style"]) < 20:
        return False  # "友好" 这种一个词不算
    if len(model["decision_patterns"]) < 20:
        return False
    
    # 列表检查
    if not isinstance(model["recurring_topics"], list) or len(model["recurring_topics"]) < 2:
        return False  # 至少 2 个话题才有建模意义
    
    # 枚举检查
    if model["expertise_level"] not in ("beginner", "intermediate", "expert"):
        return False
    
    # 置信度范围
    if not 0 <= model.get("confidence", 0) <= 1:
        return False
    
    return True
```

**更新策略**：画像不是覆盖写，而是增量 merge — 新观察与旧画像融合，confidence 按贝叶斯更新。避免一次对话就推翻整个用户画像。

---

### L5 — Adversarial Validation（对抗校验）

记忆系统的免疫系统。每次写入新条目后自动触发：

#### 一致性检查

新条目 vs 现有知识库。如果发现矛盾（例如新经验说"Dify 用了 PostgreSQL"但旧记忆说"Dify 用了 MySQL"），标记冲突而非静默覆盖。

#### 回归防护

技能更新后，对 Top-5 历史问题做回测。如果新版技能的回答质量低于旧版，回滚并标记需要人工审核。

#### 衰减机制

```python
def _decay_access_count(self):
    """每 7 天衰减一次，未访问的条目 access_count 递减"""
    self.db.execute("""
        UPDATE pages 
        SET access_count = MAX(0, access_count - 1)
        WHERE last_accessed < datetime('now', '-7 days')
        AND access_count > 0
    """)
```

**为什么是 -1 而不是 ×0.9？** 线性衰减比指数衰减更可预测 — 一条 access_count=10 的记忆会在 70 天后归零，开发者可以精确计算衰减时间。指数衰减永远不会到 0，导致僵尸条目累积。

**L5 全部用规则实现，零 LLM 调用。** 这是有意的设计 — 校验层本身不能依赖 LLM，否则 LLM 的幻觉会感染校验结果。

---

## LLM 分层降级

不是所有操作都需要云端大模型。DeepBrain 的核心设计原则：**确定性操作用规则/本地模型，模糊推理才用云端 LLM。**

| 层 | 操作类型 | 计算来源 | 模型 | 调用频率 |
|----|---------|---------|------|---------|
| L0 | 向量生成 | 本地 | nomic-embed-text (274MB) | 每次对话 |
| L0 | BM25 搜索 | 本地 | SQLite 内置 | 每次对话 |
| L1 | 经验提取 | 本地 | qwen2.5:7b (4.7GB) | 每次对话 |
| L1 | 质量门控 | 规则 | — | 每次对话 |
| L2 | 经验聚类 | 本地 | cosine similarity | 每 5+ 条经验 |
| L2 | 技能归纳 | 云端 | 主模型 | 低频 |
| L3 | MERGE/DEPRECATE/PROMOTE | 规则 | — | 定期 |
| L3 | 漂移检测 | 规则 | — | 定期 |
| L4 | 画像构建 | 云端 | 主模型 | 低频 |
| L4 | 画像验证 | 规则 | — | 每次画像更新 |
| L5 | 一致性/回归/衰减 | 规则 | — | 每次写入 |

**高频操作（L0 召回、L1 门控、L5 校验）= 本地/规则，零 API 成本。**
**低频操作（L2 归纳、L4 建模）= 云端 LLM，但一个月可能只触发几十次。**

**自动检测**：启动时检测本地 Ollama 可用性。有 Ollama → 本地优先。无 Ollama → 全走云端主模型。通过环境变量覆盖：

```bash
LEAPER_LOCAL_URL=http://localhost:11434/v1   # 自定义 Ollama 地址
LEAPER_LOCAL_MODEL=qwen2.5:14b               # 切换更大的本地模型
```

---

## DB Schema

`brain.db` 使用 SQLite，核心表结构：

```sql
CREATE TABLE pages (
    slug TEXT PRIMARY KEY,       -- UUID，如 '27d9522a'
    title TEXT,                  -- 条目标题
    namespace TEXT,              -- 四层隔离：agent/desk/role/org
    content TEXT,                -- 主体内容
    entry_type TEXT,             -- 'experience' | 'skill' | 'user_model' | 'meta'
    confidence REAL,             -- 0.0 - 1.0，质量置信度
    access_count INTEGER,        -- 被召回次数，用于 L5 衰减
    last_accessed TEXT,          -- 最近被召回的时间
    metadata TEXT,               -- JSON，扩展字段
    updated_at TEXT              -- 最近更新时间
);

CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    page_slug TEXT,              -- 关联 pages.slug
    content TEXT,                -- 分块内容（用于向量搜索）
    FOREIGN KEY (page_slug) REFERENCES pages(slug)
);
```

**四层 namespace 隔离**：

| 层 | Namespace | 用途 | 示例 |
|----|-----------|------|------|
| L1 | `agent/{name}` | Agent 实例级 | `agent/ceo-coach` |
| L2 | `desk/{name}/{seat}` | 工位级 | `desk/ceo-coach/strategy` |
| L3 | `role/{role}` | 角色级共享 | `role/coach` |
| L4 | `org` | 组织级 | `org`（只通过 L3 evolve 写入） |

**为什么不用向量数据库？** brain.db 的典型大小 < 10MB（1000+ 条目）。SQLite 在这个量级下比 Chroma / Pinecone 更快、更简单、零外部依赖。向量存在 `chunks` 表，BM25 用 LIKE 搜索（sql.js 不支持 FTS5），性能在 10K 条目以下没有瓶颈。

---

## 平台连接（15+ 渠道）

Leaper 继承 Hermes 的完整 Gateway 架构。单进程连接所有平台，对话跨平台延续。

| 平台 | 协议 | 配置方式 |
|------|------|---------|
| **Telegram** | Bot API (grammY) | `TELEGRAM_BOT_TOKEN` 或 `config.yaml` |
| **Discord** | discord.js | `DISCORD_BOT_TOKEN` |
| **Slack** | Bolt SDK | `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` |
| **WhatsApp** | Baileys (无需 Business API) | `config.yaml` |
| **Signal** | signal-cli | `config.yaml` |
| **飞书** | Open API | `config.yaml` |
| **钉钉** | Stream SDK | `config.yaml` |
| **微信（企业微信）** | Callback API | `config.yaml` |
| **Matrix** | matrix-nio | `config.yaml` |
| **Email** | IMAP/SMTP | `config.yaml` |
| **LINE** | Messaging API | `config.yaml` |
| **Mattermost** | WebSocket | `config.yaml` |
| **IRC** | irc-framework | `config.yaml` |
| **API** | HTTP/WebSocket | 内置，无需配置 |
| **CLI** | 本地终端 | `leaper chat` |

**Gateway 架构**：

```
Telegram / Discord / Slack / WhatsApp / 飞书 / 钉钉 / ...
               │
               ▼
┌───────────────────────────────┐
│          Gateway              │
│   单进程，多平台，多会话      │
│   session 隔离 + 消息路由     │
└──────────────┬────────────────┘
               │
               ├─ Agent Runtime（对话 + 工具调用）
               ├─ Memory Provider（DeepBrain）
               ├─ Cron Scheduler（定时任务）
               └─ Tool Registry（40+ 工具）
```

**安全模型**：
- **DM 配对**：未知发送者收到配对码，需手动批准
- **用户白名单**：`TELEGRAM_ALLOWED_USERS` 控制谁能和 Bot 对话
- **群组控制**：按群 ID 白名单，支持 mention-only 模式
- **工具审批**：敏感命令执行前需用户确认

---

## 40+ 内置工具

不只是 API wrapper — 每个工具都经过生产验证，带错误处理和超时控制。

### 终端与文件

| 工具 | 能力 | 备注 |
|------|------|------|
| `terminal` | 执行 shell 命令 | 支持 bash/PowerShell/zsh，带超时和输出捕获 |
| `file_read` | 读取文件 | 支持文本、图片、PDF |
| `file_write` | 写入文件 | 创建目录、原子写入 |
| `file_edit` | 精确编辑 | 搜索替换，不需要重写整个文件 |

### 搜索与网络

| 工具 | 能力 | 备注 |
|------|------|------|
| `web_search` | 网页搜索 | 降级链：Firecrawl → Tavily → DuckDuckGo |
| `web_fetch` | 抓取网页 | URL → Markdown，带 maxChars 截断 |
| `web_scrape` | 深度抓取 | Firecrawl 提供（需 API Key） |

### 代码与开发

| 工具 | 能力 | 备注 |
|------|------|------|
| `code_execute` | 执行代码 | Python/Node/Shell，沙箱隔离 |
| `git` | Git 操作 | commit/push/pull/branch |
| `github` | GitHub API | Issues/PRs/Actions |

### 媒体与生成

| 工具 | 能力 | 备注 |
|------|------|------|
| `image_generation` | 图片生成 | fal.ai / DALL-E（需 API Key） |
| `tts` | 文字转语音 | ElevenLabs / 系统 TTS |
| `vision` | 图片理解 | 多模态模型分析图片内容 |
| `pdf_reader` | PDF 读取 | 自动缓存到 `~/.leaper/cache/documents/` |

### 自动化

| 工具 | 能力 | 备注 |
|------|------|------|
| `cron` | 定时任务 | 自然语言定义，支持投递到任意平台 |
| `delegation` | 子代理 | 并行生成子 Agent 处理独立任务 |
| `webhook` | 外部触发 | HTTP 回调触发 Agent 动作 |

**工具管理**：通过 `config.yaml` 的 toolset 配置启用/禁用。支持 [MCP](https://modelcontextprotocol.io) 协议扩展任意第三方工具服务器。

---

## TUI 终端界面

不只是 readline — 完整的终端 UI：

- **多行编辑**：写代码、写长文不需要一行挤完
- **Slash 命令自动补全**：`/` 触发命令菜单
- **对话历史**：上下键浏览历史，跨 session 持久化
- **流式输出**：工具调用结果实时流式展示
- **中断重定向**：`Ctrl+C` 中断当前操作，发新消息重定向任务
- **会话管理**：`/new` 新对话、`/model` 切换模型、`/compress` 压缩上下文

```bash
leaper chat              # 启动终端对话
leaper chat --model gpt-4o  # 指定模型
```

---

## Cron 定时任务

内置调度器，用自然语言定义定时任务，结果投递到任意已连接平台：

```yaml
# 每天早上 8 点发日报到 Telegram
cron:
  daily-report:
    schedule: "0 8 * * *"
    task: "生成今日待办事项摘要"
    deliver_to: telegram
```

支持：cron 表达式 / 间隔时间 / 一次性定时。任务在独立 session 中运行，不影响主对话。

---

## 子代理委派

复杂任务可以拆分给并行的子 Agent：

```
用户: "分析这 5 个竞品的技术架构"
         ↓
Agent 主进程 → 生成 5 个子 Agent
                ├─ 子 Agent 1: 分析竞品 A
                ├─ 子 Agent 2: 分析竞品 B
                ├─ 子 Agent 3: 分析竞品 C
                ├─ 子 Agent 4: 分析竞品 D
                └─ 子 Agent 5: 分析竞品 E
                         ↓ 并行执行
Agent 主进程 ← 汇总 5 份报告 → 用户
```

子 Agent 有独立的 context window，不消耗主对话的 context 预算。

---

## Workspace 文件系统

每个 Agent 的人格、记忆、规则都通过 Markdown 文件定义 — 无需写代码：

| 文件 | 用途 | 加载策略 | 谁维护 |
|------|------|---------|--------|
| `EGO.md` | 核心规则和行为边界 | `ALWAYS_LOAD` — 每次对话必加载 | 开发者 |
| `SOUL.md` | 价值观、沟通风格、专业领域 | `ALWAYS_LOAD` | 开发者 |
| `IDENTITY.md` | 一行身份描述 | `ALWAYS_LOAD` | 开发者 |
| `USER.md` | 用户画像 | `ALWAYS_LOAD` | 开发者 + L4 自动更新 |
| `MEMORY.md` | 持久记忆 | `SEED_AND_RECALL` — 首次加载，后续按需召回 | L1 自动维护 |
| `AGENTS.md` | 多 Agent 协作规则 | `ALWAYS_LOAD` | 开发者 |

**`SEED_AND_RECALL` 策略**：MEMORY.md 在首次对话时全量加载（seed），后续对话通过 L0 Hybrid Recall 只召回相关段落。这解决了"记忆越多 context 越贵"的根本问题。

**自动排除**：README.md、CHANGELOG.md、LICENSE.md 等非上下文文件不会被加载（`MD_EXCLUDE` 列表）。

**运行环境注入**：`leaper_seed_loader.py` 用 `platform.system()` + `platform.version()` 动态检测 OS，注入到 system prompt。Agent 知道自己在 Windows/Linux/macOS 上，不会用错命令。

---

## 模型支持

支持所有主流 LLM Provider，通过 `config.yaml` 配置切换，无需改代码：

| Provider | 模型示例 | 配置 |
|----------|---------|------|
| **OpenAI** | GPT-4o, GPT-4.1, o3 | `OPENAI_API_KEY` |
| **Anthropic** | Claude Opus 4, Sonnet 4 | `ANTHROPIC_API_KEY` |
| **OpenRouter** | 200+ 模型 | `OPENROUTER_API_KEY` |
| **Ollama** | qwen2.5, llama3, deepseek-r1 | 本地运行，零配置 |
| **自定义** | 任何 OpenAI 兼容 API（NVIDIA NIM、MiniMax 等） | `base_url` + `api_key` |

**模型切换**：修改 `config.yaml` 的 `model` 字段或设置环境变量 `OPENAI_API_KEY` 等。

**Failover**：主模型不可用时自动切换备选。通过 `providers` 配置多个 endpoint。

---

## 搜索降级链

零配置可用 — 不需要任何 API Key 就能搜索：

```
Firecrawl（深度抓取 + 结构化数据）
    ↓ 无 FIRECRAWL_API_KEY
Tavily（搜索 API，免费 1000 次/月）
    ↓ 无 TAVILY_API_KEY
DuckDuckGo（完全免费，零配置，无限制）
```

实现在 `tools/web_tools.py` 的 `_get_backend()` 函数。启动时检测可用后端，运行时自动选择最优。

**使用场景**：
- 用户问"最近 OpenAI 发布了什么" → 自动触发搜索
- Agent 需要验证某个技术判断 → 自动搜索最新信息
- 模板中配置定期搜索任务 → Cron 触发

---

## Quick Install

```bash
git clone https://github.com/Deepleaper/leaper-agent.git
cd leaper-agent
pip install -e ".[all]"
```

**系统要求**：Python ≥ 3.10，无需 C++ 编译器，无需 GPU。

首次配置：

```bash
leaper init                          # 交互式向导（问 API Key、Bot Token）
leaper init --template ceo-coach     # 用模板创建 AI 员工
```

启动：

```bash
leaper chat                          # 终端对话
leaper run                           # 启动 Gateway（连接 Telegram 等平台）
```

---

## leaper.yaml 配置

```yaml
name: 'CEO 教练'

model:
  provider: openai          # openai | anthropic | ollama | openrouter | custom
  name: gpt-4o
  apiKey: sk-xxx            # 或放 .env

channel:
  type: telegram
  token: 'bot-token'        # 或放 .env

brain:
  enabled: true
  localModel: auto          # auto = 检测本地 Ollama | off = 全走云端
```

支持的 LLM Provider：OpenAI · Anthropic · Ollama · OpenRouter · 自定义 endpoint（任何 OpenAI 兼容 API）。通过 `config.yaml` 切换，无需改代码。

---

## 模板系统

```bash
leaper init --template ceo-coach     # 创建 CEO 教练
leaper workshop                      # 查看所有可用模板
```

模板是一组预配置文件（YAML + Markdown），不是硬编码逻辑。每个模板包含：

```
templates/ceo-coach/
  template.yaml       # 模板元信息 + 默认配置
  EGO.md              # AI 的核心规则和行为边界
  SOUL.md             # 价值观、沟通风格、专业领域
  IDENTITY.md         # 身份描述（一行）
  USER.md             # 默认用户画像
  MEMORY.md           # 初始记忆（空，由 L1 自动填充）
  AGENTS.md           # 多 Agent 协作规则
```

**开发者可以 fork 任何模板、修改任何文件。** 模板只是起点，不是约束。

### CEO Coach 模板

苏格拉底式创业教练，专为 CEO / 创始人设计：

- **教练哲学**：先问后答，不替用户做决定，用提问引导思考
- **40 个商业分析框架**：Porter 五力、SWOT、飞轮效应、TAM/SAM/SOM、Jobs-to-be-Done...
- **六层自进化记忆**：记住你的战略偏好、历史决策、反复关注的议题
- **严格的行为边界**：不暴露内部工具调用、不泄露技术细节、报错信息不显示给用户

---

---

## 与 Hermes 的关系

Leaper 是 Hermes Agent 的下游 fork（MIT 协议）。完整保留 Hermes 全部能力，上层增加 DeepBrain 引擎和产品化体验。

| 维度 | Hermes | Leaper |
|------|--------|--------|
| **记忆架构** | Background Review — 53 字 prompt，LLM 自由写入，无结构、无去重、无门控 | DeepBrain — 四维提取 + 4Gate + RRF 混合召回 + 六层进化 |
| **记忆存储** | Hindsight（`api.hindsight.vectorize.io`，第三方 SaaS，智能在云端） | 本地 SQLite（`brain.db`），零外部依赖 |
| **记忆进化** | 无。Background Review 只做"存不存"决策 | L2 技能生成 + L3 跨技能进化 + L4 用户建模 + L5 对抗校验 |
| **LLM 成本** | 所有记忆操作用主模型 | 分层降级，高频操作用本地小模型 |
| **安装** | `curl \| bash`，手动配置 | `pip install` + 交互式向导 |
| **模板** | 无 | Workshop 模板市场 |
| **搜索** | 需配 Firecrawl/Tavily API Key | DuckDuckGo 零配置兜底 |
| **平台** | Linux/macOS/WSL2 | + Windows 原生支持 |

---

## 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `LEAPER_HOME` | 工作目录 | `~/.leaper` |
| `LEAPER_LOCAL_URL` | 本地 Ollama 地址 | `http://localhost:11434/v1` |
| `LEAPER_LOCAL_MODEL` | 本地推理模型 | `qwen2.5:7b` |
| `HERMES_MEMORY_PROVIDER` | 记忆引擎选择 | `leaper` |
| `HERMES_INFERENCE_PROVIDER` | 推理 Provider | 按降级链自动选择 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | — |
| `GATEWAY_ALLOW_ALL_USERS` | 允许所有用户 | `false` |
| `TELEGRAM_REPLY_TO_MODE` | 回复引用模式 | `on` |

兼容 Hermes 的所有环境变量（`HERMES_HOME`、`OPENAI_API_KEY`、`OPENROUTER_API_KEY` 等）。

---

## 开发

```bash
git clone https://github.com/Deepleaper/leaper-agent.git
cd leaper-agent
uv venv venv --python 3.11
source venv/bin/activate          # Windows: venv\Scripts\activate
uv pip install -e ".[all,dev]"
```

### 代码结构

DeepBrain 相关代码（~1951 行）：

```
agent/
  leaper_brain.py           # 564 行 — L0 混合召回、DB 读写、BM25/向量搜索
  leaper_evolution.py        # 992 行 — L1-L5 全部进化逻辑
  leaper_orchestrator.py     # 137 行 — 进化调度器（决定何时触发 L2-L5）
  leaper_seed_loader.py      #         — Workspace 文件加载 + OS 注入

plugins/memory/deepbrain/
  provider.py                # 258 行 — Hermes Memory Provider 接口实现
  plugin.yaml                #         — 插件声明
  __init__.py
```

### 扩展记忆引擎

DeepBrain 通过 Hermes 的 Memory Provider 插件接口接入。如果你想替换或扩展记忆逻辑：

1. 在 `plugins/memory/` 下新建目录
2. 实现 `MemoryProvider` 基类的 `sync_turn()` / `recall()` / `store()` 方法
3. 在 `plugin.yaml` 中声明
4. 配置 `memory.provider: your-provider` in `config.yaml`

---

## License

Apache-2.0 © [Deepleaper](https://www.deepleaper.com)

基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent)（MIT © Nous Research）
