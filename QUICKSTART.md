# ⚡ Leaper Agent — 快速开始

从零到一个运行中的 AI 员工，5 分钟。

---

## 前置条件

- **Python 3.10+**（检查：`python --version`）
- **一个 LLM API Key**（OpenAI / Anthropic / 聚合 API 均可）
- **（可选）Telegram Bot Token**（[从 @BotFather 获取](https://t.me/BotFather)）

---

## 第一步：安装

```bash
pip install leaper-agent
```

> 💡 不需要 Git，不需要编译。Windows / macOS / Linux 均可。

验证安装：

```bash
leaper --help
```

---

## 第二步：创建单个 Agent

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
连接平台: telegram
Telegram Bot Token: 123456:ABC...
启用 Leaper Brain: Yes
```

生成的文件：

```
my-agent/
├── leaper.yaml     # 运行配置
└── .env            # API Key（不会上传）
```

---

## 第二步（替代）：创建多角色团队

一次配置多个 AI 角色，每个角色一个独立 Telegram Bot：

```bash
leaper init-team
```

向导会让你逐个添加角色 + Token：

```
全局模型: claude-sonnet-4-20250514

Agent #1
  角色 ID: cfo
  Bot Token: 111:AAA...
  ✓ Agent [cfo] 已添加

Agent #2
  角色 ID: cto
  Bot Token: 222:BBB...
  ✓ Agent [cto] 已添加

（回车结束）

✅ 多 Agent 配置已写入：~/.leaper/config.yaml
```

---

## 第三步：启动

### 方式 A：Telegram Bot

```bash
leaper run
```

打开 Telegram，找到你的 Bot 发消息，就能收到回复了。

### 方式 B：终端对话

```bash
leaper chat
```

直接在命令行对话，不需要 Telegram。

---

## 第四步：定制人格（可选）

在工作区目录下创建 Markdown 文件：

**EGO.md** — 行为规则：
```markdown
# EGO

## 核心规则
所有工具调用对用户完全不可见

## 沟通风格
先给结论，再给分析。不说废话。

## 你绝对不能做的事
把内部错误信息展示给用户
```

**SOUL.md** — 性格与专业：
```markdown
# SOUL
- 务实，不为技术而技术
- 数据驱动，用事实说话
- 直言不讳，该指出的问题直说
```

修改后 `leaper run` 会自动加载。

---

## 使用模板

不想从零写人格？用模板：

```bash
# 浏览所有模板
leaper workshop

# 用 CEO Coach 模板创建
leaper init --template ceo-coach my-coach
cd my-coach
```

10 个 CXO 角色模板可选：

| 模板 ID | 角色 |
|---------|------|
| `ceo-coach` | 🎯 创业决策教练 |
| `cto` | 💻 技术战略顾问 |
| `cfo` | 💰 财务战略顾问 |
| `cmo` | 📣 市场增长顾问 |
| `coo` | ⚙️ 运营执行顾问 |
| `cpo` | 🎯 产品战略顾问 |
| `chro` | 👥 人力战略顾问 |
| `clo` | ⚖️ 法务战略顾问 |
| `cso` | 🧭 首席战略官 |
| `cco` | 📢 品牌传播顾问 |

---

## 使用聚合 API / 兼容 API

不一定用 OpenAI/Anthropic，任何兼容 API 都行。`leaper.yaml`：

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

---

## 使用 Ollama 本地模型

```yaml
provider:
  type: ollama
  model: qwen2.5:7b
  # baseUrl 默认 http://localhost:11434/v1，不用改
```

---

## 配置代理

```yaml
proxy: 'http://127.0.0.1:10809'
```

或者环境变量：

```bash
export LEAPER_PROXY=http://127.0.0.1:10809
```

---

## Brain 记忆引擎

`brain: enabled: true` 开启后，自动：

- **有 Ollama**：本地 embedding + BM25 + 向量混合召回
- **没有 Ollama**：纯 BM25 关键词召回（仍然有效）
- **后装 Ollama**：自动 backfill embedding，无缝切换
- **去重**：相同内容不重复存，cosine > 0.85 自动过滤

查看 Brain 状态：

```bash
leaper status
```

---

## 搜索能力

不需要任何 Key，DuckDuckGo 零配置可用：

```
你：帮我搜一下 Anthropic 最新动态
AI：（自动用 DuckDuckGo 搜索，无需 API Key）
```

要深度搜索，加 key 即可（可选）：

```yaml
tools:
  firecrawl_api_key: fc-xxx
  # 或
  tavily_api_key: tvly-xxx
```

---

## 常用命令

| 命令 | 说明 |
|------|------|
| `leaper init` | 交互式创建单个 Agent |
| `leaper init --template <id>` | 从模板创建 |
| `leaper init-team` | 多角色团队配置 |
| `leaper run` | 启动 Gateway |
| `leaper chat` | 终端对话 |
| `leaper status` | 查看状态 |
| `leaper workshop` | 浏览模板 |

---

## 常见问题

| 问题 | 解决 |
|------|------|
| `leaper` 命令找不到 | Windows：关闭并重新打开 PowerShell |
| Telegram Bot 无回复 | 检查 Token 是否正确，确保没有其他进程在 polling 同一个 Token |
| API 401 报错 | 检查 apiKey 和 baseUrl 是否正确 |
| 连不上 Telegram | 加代理：`proxy: 'http://127.0.0.1:10809'` |
| 中文乱码 | 设环境变量：`PYTHONIOENCODING=utf-8` |

---

## 下一步

- 📖 阅读 [README.md](README.md) 了解 DeepBrain 六层进化原理
- 🎯 试试不同的 CXO 模板
- 🧠 和 Agent 聊 20 轮以上，观察记忆进化效果

---

*Powered by [Deepleaper 跃盟科技](https://www.deepleaper.com)*
