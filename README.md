# ⚡ Leaper Agent

**自进化 AI 员工框架** — 越用越聪明的 AI 助手。

基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent)（MIT），加入 **DeepBrain 自进化记忆引擎** — 这是 Leaper 与所有其他 Agent 框架的核心区别。

---

## 核心差异：记忆

所有 AI Agent 框架都能调 API、连平台、跑工具。**但没有一个真正解决了"记忆"问题。**

| | Hermes / OpenClaw / 其他 | Leaper |
|---|--------------------------|--------|
| **怎么记** | MEMORY.md 纯文本，LLM 随意写 | 四维结构化提取 + 4Gate 质量门控 |
| **记什么** | 什么都记，同一件事存 5 遍 | cosine > 0.85 自动去重，73% 有效存储率 |
| **怎么找** | 全文塞进 context（越来越贵） | BM25 + 768 维向量 RRF 混合召回（成本固定） |
| **会忘吗** | ❌ 只增不减，context 爆炸 | ✅ access_count 衰减，自动遗忘 |
| **会归纳吗** | ❌ | ✅ 经验聚类 → 可复用技能 |
| **懂用户吗** | ❌ | ✅ 多维用户画像，理解你的思维模式 |
| **会自检吗** | ❌ | ✅ 一致性校验 + 回归防护 |
| **月成本** | $30+ 且持续递增 | $3-5 且稳定 |

**一句话：它们是笔记本，Leaper 是大脑。**

---

## DeepBrain 六层进化引擎

| 层 | 能力 | 原理 |
|----|------|------|
| L0 | 精准召回 | BM25 关键词 + 向量语义，RRF 融合排序 |
| L1 | 经验提取 | 每轮对话四维分析（任务/策略/结果/洞察），质量不过关就不存 |
| L2 | 技能生成 | 相似经验聚类，自动归纳为可复用技能 |
| L3 | 技能进化 | 合并冗余、淘汰过时、晋升优质，检测知识漂移 |
| L4 | 用户建模 | 从对话中构建用户心智模型（沟通风格、决策模式、专业领域） |
| L5 | 自我校验 | 一致性检查、回归防护、过期衰减 |

**越用越聪明，不是口号 — 每一层都有实测数据验证。**

所有数据存在本地 SQLite，不上传任何云端。

---

## 3 步开始

```bash
# 1. 安装
pip install leaper-agent

# 2. 配置（交互式向导，问你 API Key 和 Bot Token）
leaper init

# 3. 启动
leaper run
```

或者先在终端试试：
```bash
leaper chat
```

**系统要求**：Python ≥ 3.10，无需 C++ 编译器。

---

## leaper.yaml

```yaml
name: 'CEO 教练'

model:
  provider: openai       # openai | anthropic | ollama | custom
  name: gpt-4o
  apiKey: sk-xxx         # 或放 .env

channel:
  type: telegram
  token: 'bot-token'     # 或放 .env

brain:
  enabled: true
  localModel: auto       # auto = 检测本地 Ollama | off = 全云端
```

一个文件搞定。

---

## 模板

```bash
# 用预置模板创建 AI 员工
leaper init --template ceo-coach
```

**CEO Coach** — 苏格拉底式创业教练，自带 6 层自进化记忆 + 40 个商业分析框架。

更多模板持续更新。

---

## 平台

Telegram · Discord · Slack · WhatsApp · 飞书 · 钉钉 · Matrix · API · CLI — 15+ 平台开箱即用。

---

## 搜索

零配置。没有 API Key 也能搜（DuckDuckGo）。配了 Firecrawl/Tavily 自动升级。

---

## 40+ 内置工具

终端 · 文件 · 代码执行 · 浏览器 · 图片生成 · TTS · 搜索 — 开箱即用。

---

## Workspace 文件

| 文件 | 用途 |
|------|------|
| `EGO.md` | AI 的自我认知和核心规则 |
| `SOUL.md` | 价值观和行为准则 |
| `IDENTITY.md` | 专业身份描述 |
| `USER.md` | 用户画像 |
| `MEMORY.md` | 记忆（自动维护） |

---

## FAQ

**需要 GPU 吗？** 不需要。云端 API 即可。用 Ollama 本地模型需对应硬件。

**数据安全吗？** 所有记忆存本地 SQLite，不上传。

**支持中文吗？** 完全支持。CLI、模板、文档全中文原生。

---

## License

Apache-2.0 © [Deepleaper](https://www.deepleaper.com)

基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent)（MIT © Nous Research）
