# ⚡ Leaper Agent — 快速开始

从零到一个运行中的 AI 员工，只需 5 分钟。

---

## 前置条件

- **Python 3.10+**（检查：`python --version`）
- **一个 LLM API Key**（OpenAI / Anthropic / 聚合 API 均可）
- **（可选）Telegram Bot Token**（[从 @BotFather 获取](https://t.me/BotFather)）

---

## 第一步：安装

```bash
git clone https://github.com/Deepleaper/leaper-agent.git
cd leaper-agent
pip install -e ".[messaging]"
```

> 💡 如果只用终端对话不需要 Telegram，可以 `pip install -e .`

验证安装：

```bash
leaper --help
```

---

## 第二步：初始化

```bash
leaper init my-agent
cd my-agent
```

向导会问你几个问题：

```
Agent 名称: CEO 教练
LLM 提供商: openai
模型: gpt-4o
API Key: sk-xxx
消息频道: telegram
Telegram Bot Token: 123456:ABC...
启用 Leaper Brain: Yes
```

完成后目录结构：

```
my-agent/
├── leaper.yaml     # 唯一的配置文件
└── .env            # API Key（自动创建）
```

---

## 第三步：启动

### 方式 A：Telegram Bot

```bash
leaper run
```

打开 Telegram，给你的 Bot 发消息，它就会回复。

### 方式 B：终端对话

```bash
leaper chat
```

直接在命令行对话。

---

## 第四步：自定义人格（可选）

在 `my-agent/` 目录创建 Markdown 文件：

**EGO.md** — 定义 AI 是谁：
```markdown
# EGO

## 我是谁
我是一位经验丰富的创业教练。

## 我的风格
苏格拉底式提问，不直接给答案。

## 工具调用对用户透明
所有后台操作（记忆、搜索）不在回复中暴露。
```

**SOUL.md** — 定义行为准则：
```markdown
# SOUL
- 先问后答
- 不说废话
- 承认不确定性
```

重启 `leaper run` 生效。

---

## 使用模板

不想从零写人格？用模板：

```bash
# 查看可用模板
leaper workshop

# 用 CEO Coach 模板初始化
leaper init --template ceo-coach my-coach
cd my-coach
```

模板包含完整人格设定，开箱即用。

---

## 使用聚合 API / 自定义 API

如果不是标准 OpenAI/Anthropic，在 `leaper.yaml` 设 baseUrl：

```yaml
name: '我的助手'

provider:
  type: openai-compatible
  model: your-model-name
  baseUrl: http://your-api.com/v1
  apiKey: your-key

channel:
  type: telegram
  token: 'bot-token'

brain:
  enabled: true
```

Leaper 会自动配置好一切，不需要手动编辑其他文件。

---

## 使用 Ollama 本地模型

```yaml
provider:
  type: ollama
  model: llama3.2
  # baseUrl 默认 http://localhost:11434/v1，无需填写
```

---

## 使用代理

```yaml
proxy: 'http://127.0.0.1:10809'
```

或设环境变量：

```bash
export LEAPER_PROXY=http://127.0.0.1:10809
```

---

## 🧠 Brain 零配置体验

`brain: enabled: true` 加上就行，其余全自动：

- **向量检索**：自动启用（需要 Ollama + nomic-embed-text）
- **没装 Ollama**？降级到纯 BM25 文本检索，一样能用
- **旧数据补齐**：首次启动自动 backfill embeddings，无需手动操作
- **去重**：同一件事说两遍不会存两条，cosine > 0.85 自动跳过

验证 Brain 工作正常：

```bash
leaper status
# 会显示 Brain 统计：经验条数、技能数、用户画像维度等
```

---

## 🔍 搜索零配置

不配任何 Key，搜索就能用（DuckDuckGo）：

```
你：帮我搜一下 Anthropic 最新动态
AI：（自动用 DuckDuckGo，无需 API Key）
```

想要更好的结果，在 `leaper.yaml` 加（可选）：

```yaml
tools:
  firecrawl_api_key: fc-xxx
  # 或
  tavily_api_key: tvly-xxx
```

配了就自动升级，没配也不影响使用。

---

## 查看状态

```bash
leaper status
```

显示当前配置、Brain 统计等信息。

---

## 下一步

- 📖 阅读 [README.md](README.md) 了解完整功能
- 🧠 了解 [进化引擎](README.md#-进化引擎) 的工作原理
- 📋 探索 [Workshop 模板](README.md#-模板系统-workshop)
- 💬 加入社区讨论

---

## 遇到问题？

| 问题 | 解法 |
|------|------|
| `leaper` 命令找不到 | `pip install -e ".[messaging]"` 重装 |
| Telegram Bot 不回复 | 检查 token 是否正确，确保没有其他进程在 polling 同一 token |
| API 401 错误 | 检查 apiKey 和 baseUrl 是否匹配 |
| 连不上 Telegram | 设置代理：`proxy: 'http://127.0.0.1:10809'` |
| 中文乱码 | 设环境变量：`PYTHONIOENCODING=utf-8` |
