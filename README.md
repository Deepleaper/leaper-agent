<p align="center">
  <h1 align="center">🚀 Leaper Agent</h1>
  <p align="center">
    <strong>自学习智能体框架。记忆会进化的 AI，用于任何业务场景。</strong><br>
    <em>Self-learning agent framework with evolving memory. Build AI for any business scenario.</em>
  </p>
</p>

<p align="center">
  <a href="https://pypi.org/project/leaper-agent/"><img src="https://img.shields.io/pypi/v/leaper-agent?color=%2334D058&label=PyPI" alt="PyPI"></a>
  <a href="https://pypi.org/project/leaper-agent/"><img src="https://img.shields.io/pypi/dm/leaper-agent" alt="Downloads"></a>
  <a href="https://github.com/Deepleaper/leaper-agent"><img src="https://img.shields.io/github/stars/Deepleaper/leaper-agent?style=social" alt="Stars"></a>
  <a href="https://github.com/Deepleaper/leaper-agent/blob/master/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python"></a>
</p>

<p align="center">
  <a href="#5-分钟部署">5 分钟部署</a> ·
  <a href="#六层记忆引擎">六层记忆引擎</a> ·
  <a href="#业务场景">业务场景</a> ·
  <a href="#模板系统">模板系统</a> ·
  <a href="./docs/README_EN.md">English</a>
</p>

---

## 它是什么？

一个**自学习的智能体搭建框架**。你用它造出来的 AI Agent，会随着使用不断学习、进化、成长——不是每次从零开始的聊天机器人。

适用于任何需要"AI 越用越强"的业务场景：

- 客服 Agent → 记住每个客户的历史和偏好
- 销售 Agent → 积累行业知识和成交经验
- 运营 Agent → 学习公司流程和决策逻辑
- 顾问 Agent → 随时间积累专业判断力
- 内部助手 → 成为最了解你公司的人

**核心差异化：别的框架跑完就忘，Leaper 跑完会变聪明。**

---

## 和其他框架的区别

| | LangChain | CrewAI | AutoGPT | **Leaper Agent** |
|---|---|---|---|---|
| **定位** | LLM 编排 | 多Agent协作 | 自主任务 | **自学习智能体** |
| **记忆** | 需自建 | 无持久 | 短期 | ✅ 六层进化引擎 |
| **自学习** | ❌ | ❌ | ❌ | ✅ 对话自动提取知识 |
| **知识治理** | ❌ | ❌ | ❌ | ✅ 冲突/衰减/聚合 |
| **开箱即用** | 需大量代码 | 需定义 | 配置复杂 | ✅ 模板即用 |
| **多平台** | 无 | 无 | CLI | ✅ Telegram/Discord/飞书/钉钉/API |
| **中文** | 一般 | 差 | 差 | ✅ 原生优化 |

---

## 5 分钟部署

```bash
# 安装
pip install leaper-agent

# 初始化（配 API Key + 代理）
leaper init

# 创建一个 Agent（以 CEO Coach 模板为例）
leaper create ceo-coach --bot-token YOUR_TELEGRAM_BOT_TOKEN

# 启动
leaper start ceo-coach
```

去 Telegram 找你的 bot 对话 —— **一个会自学习的 AI 员工上线了。**

---

## 六层记忆引擎

这是 Leaper 的核心技术。**不是存聊天记录，是构建一个会进化的知识体系。**

```
 Day 1:   Agent 什么都不知道
 Day 7:   记住了用户偏好、业务基本信息
 Day 30:  能关联历史上下文，给出有依据的回复
 Day 90:  比新来的人更了解这个领域
```

### 六层架构

| 层 | 名称 | 做什么 |
|---|---|---|
| L0 | 原始存储 | 对话/文档/输入的原始数据 |
| L1 | 结构化提取 | **4Gate 门控**——只留有价值的信息 |
| L2 | 技能合成 | 跨对话聚类、知识合并、去重 |
| L3 | 知识治理 | 合并 / 淘汰 / 晋升 / 漂移检测 |
| L4 | 用户画像 | 多维特征建模 |
| L5 | 一致性守护 | 回归测试、时间衰减、异常检测 |

### 4Gate 门控

每条信息经过四道门，只有真正有价值的才进入知识库：

| 门 | 作用 | 示例 |
|---|---|---|
| 新颖性 | 已知的不存 | "今天天气好" → ❌ |
| 可操作性 | 无用的不存 | "嗯嗯好的" → ❌ |
| 持久性 | 临时的分级存 | "明天开会" → 短期 |
| 关联性 | 与业务无关的不存 | 闲聊噪音 → ❌ |

---

## 业务场景

Leaper 是通用框架，适配各种业务 Agent 场景：

### 企业内部

| 场景 | Agent 做什么 |
|------|-------------|
| 新员工 Onboarding | 记住公司制度、回答新人问题、越答越准 |
| 客户成功 | 记住每个客户历史、主动提醒续约/风险 |
| 技术顾问 | 积累架构决策、技术选型经验 |
| 财务助手 | 学习公司财务规则、自动审核异常 |

### 面向用户

| 场景 | Agent 做什么 |
|------|-------------|
| 私人教练 | 记住用户目标和进展，个性化指导 |
| 学习助手 | 跟踪学习进度，智能复习 |
| 健康顾问 | 积累健康数据，长期趋势分析 |
| 行业分析师 | 持续跟踪行业动态，越来越懂 |

### CXO 模板

我们预置了 10 个 CXO 角色模板 + 140+ 行业定制版，适合创业公司快速部署 AI 高管团队：

```bash
leaper create ceo-coach --bot-token TOKEN   # CEO 战略教练
leaper create cfo --bot-token TOKEN         # AI 财务顾问
leaper create cto --bot-token TOKEN         # AI 技术顾问
leaper start --all                          # 一键全启
```

---

## 模板系统

不想从零开始？选个模板直接用：

```bash
# 查看所有可用模板
leaper templates list

# 用模板创建 Agent
leaper create my-agent --template customer-success --bot-token TOKEN

# 行业定制
leaper create my-cfo --template cfo --industry ecommerce --bot-token TOKEN
```

**内置模板**：10 个通用 + 140+ 行业定制。也可以自建模板。

---

## 多 Agent 架构

一个进程跑多个 Agent，共享基础设施：

```
┌──────────────────────────────────────────────┐
│              Leaper Gateway                  │
│           (路由 · 认证 · 会话管理)             │
├─────┬──────┬──────┬──────┬──────┬────────────┤
│ CS  │ Sales│ Ops  │ Coach│ ...  │ 自定义     │
├─────┴──────┴──────┴──────┴──────┴────────────┤
│         DeepBrain 六层记忆引擎                 │
├──────────────────────────────────────────────┤
│ Telegram │ Discord │ 飞书 │ 钉钉 │ API │ Web │
└──────────────────────────────────────────────┘
```

- **1 进程 N Agent**: 资源共享，轻量高效
- **记忆隔离**: 每个 Agent 独立知识库
- **多平台接入**: 一个 Agent 可同时连多个渠道

---

## 支持的平台

| 平台 | 状态 |
|------|------|
| Telegram | ✅ 推荐 |
| Discord | ✅ |
| 飞书 | ✅ |
| 钉钉 | ✅ |
| API Server | ✅ |
| 微信 | 🔜 |
| Web UI | 🔜 |

---

## 配置

```yaml
# ~/.leaper/global.yaml（leaper init 自动生成）
api:
  provider: openai            # openai / claude / ollama / custom
  base_url: https://api.openai.com/v1
  api_key: sk-xxx
  model: gpt-4o

proxy:
  http: http://127.0.0.1:10809

display:
  tool_progress_mode: off     # 不向用户暴露内部细节
```

---

## 系统要求

| 项目 | 最低 | 推荐 |
|------|------|------|
| Python | 3.10 | 3.12+ |
| 内存 | 2 GB | 4 GB+ |
| 网络 | 需要 | 稳定连接 |
| 模型 | 任意 OpenAI 兼容 | Claude Opus / GPT-4o |

---

## Leaper vs OPC

| | **Leaper Agent** | **OPC Agent** |
|---|---|---|
| 定位 | 云端高端智能体框架 | 本地免费 AI 助手 |
| 模型 | 云端 API（GPT-4o / Claude） | 本地 Ollama |
| 网络 | 需要 | 不需要 |
| 费用 | API 费用 | $0 |
| 场景 | 业务 Agent、专业场景 | 私人助手、离线使用 |
| 记忆引擎 | 六层完整引擎 | 简化版（L0-L1） |
| 多平台 | ✅ | Web UI only |

**简单说：要高端体验选 Leaper，要零成本选 OPC。**

---

## 路线图

- [x] 六层记忆进化引擎 + 4Gate 门控
- [x] 模板系统（10 通用 + 140 行业）
- [x] 多 Agent 单进程架构
- [x] Telegram / Discord / 飞书 / 钉钉
- [ ] Web UI 管理面板
- [ ] 微信接入
- [ ] Agent 间协作
- [ ] 模板市场（Workshop）
- [ ] Benchmark 评测发布
- [ ] MCP 协议支持

---

## 致谢

基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent)（MIT, Nous Research）构建。增加了六层记忆引擎、模板系统和多 Agent 架构。

---

## 许可证

[MIT](LICENSE)

---

<p align="center">
  <a href="https://github.com/Deepleaper"><strong>Deepleaper 跃盟开源</strong></a><br>
  <sub>让每台电脑都有自学习的 AI。</sub>
</p>

<p align="center">
  ⭐ 如果有用，请给个 Star。
</p>
