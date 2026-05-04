<p align="center">
  <h1 align="center">🚀 Leaper Agent</h1>
  <p align="center">
    <strong>Self-learning AI Agent Framework with 6-Layer Evolving Memory</strong>
  </p>
  <p align="center">
    Build AI employees that get smarter every day — not chatbots that forget everything.
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
  <a href="https://github.com/Deepleaper/leaper-agent">Homepage</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#deepbrain-6-layer-memory">Architecture</a> ·
  <a href="https://github.com/Deepleaper/leaper-agent-cn">中国版</a> ·
  <a href="https://github.com/Deepleaper/opc-deepbrain">DeepBrain 独立引擎</a>
</p>

---

> **Leaper Agent** = [Hermes Agent](https://github.com/hermes-ai/hermes-agent) (battle-tested open-source agent runtime) + **DeepBrain 6-Layer Memory Evolution Engine**. We track Hermes upstream releases for maximum international compatibility, and layer our self-evolving memory system on top — giving agents the ability to continuously learn, distill, and govern knowledge across conversations.
>
> **Leaper Agent** = [Hermes Agent](https://github.com/hermes-ai/hermes-agent)（成熟开源 Agent 运行时）+ **DeepBrain 六层记忆进化引擎**。基座同步 Hermes 版本更新，保证海外兼容性最大化；差异化核心是我们的自进化记忆系统 —— 让 AI 在持续交互中自动学习、提炼、治理知识。不是聊天机器人，是会成长的 AI 员工。

## What Changed: Why 6-Layer Memory Matters

| Capability | LangChain | CrewAI | AutoGPT | Mem0 | **Leaper Agent** |
|---|---|---|---|---|---|
| **Memory persistence** | ❌ DIY | ❌ None | Short-term | ✅ Key-value | ✅ **6-layer evolution** |
| **Auto knowledge extraction** | ❌ | ❌ | ❌ | ✅ Basic | ✅ **4Gate filtering** |
| **Knowledge governance** (conflict/decay/merge) | ❌ | ❌ | ❌ | ❌ | ✅ **L3 governance** |
| **User profiling** | ❌ | ❌ | ❌ | Partial | ✅ **L4 multi-dim** |
| **Consistency guard** (regression/anomaly) | ❌ | ❌ | ❌ | ❌ | ✅ **L5 guardian** |
| **Multi-agent isolation** | ❌ | Partial | ❌ | ❌ | ✅ **1-process N-agents** |
| **Ready-to-use templates** | ❌ | ❌ | ❌ | ❌ | ✅ **10 CXO + 140 industry** |
| **Multi-platform** (Telegram/Discord/飞书/钉钉) | ❌ | ❌ | CLI | ❌ | ✅ **6 channels** |

**TL;DR:** Other frameworks help you *call* LLMs. Leaper helps you build AI that *remembers, learns, and grows*.

## Quick Start

```bash
pip install leaper-agent

leaper init                                          # Configure API key & proxy
leaper create ceo-coach --bot-token YOUR_TOKEN       # Create agent from template
leaper start ceo-coach                               # Launch
```

That's it. Open Telegram, talk to your bot — it learns from day one.

## DeepBrain: 6-Layer Memory Evolution

The core engine that makes Leaper agents get smarter over time.

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  L0  Raw Storage         对话 / 文档 / 输入的原始数据              │
  ├─────────────────────────────────────────────────────────────────┤
  │  L1  Structured Extract  4Gate 门控 → 只留有价值的信息              │
  │      ┌──────────┬──────────┬──────────┬──────────┐              │
  │      │ Novelty  │Actionable│ Durable  │ Relevant │              │
  │      └──────────┴──────────┴──────────┴──────────┘              │
  ├─────────────────────────────────────────────────────────────────┤
  │  L2  Skill Synthesis     跨对话聚类 · 知识合并 · 去重              │
  ├─────────────────────────────────────────────────────────────────┤
  │  L3  Knowledge Gov.      冲突检测 · 淘汰 · 晋升 · 漂移检测         │
  ├─────────────────────────────────────────────────────────────────┤
  │  L4  User Profiling      多维特征建模 · 偏好学习                   │
  ├─────────────────────────────────────────────────────────────────┤
  │  L5  Consistency Guard   回归测试 · 时间衰减 · 异常检测            │
  └─────────────────────────────────────────────────────────────────┘
```

### 4Gate: What Gets Remembered

Not everything is worth remembering. Every piece of information passes through 4 gates:

| Gate | Function | Example |
|------|----------|---------|
| **Novelty** | Skip if already known | "Nice weather" → ❌ |
| **Actionable** | Skip if no value | "Hmm ok" → ❌ |
| **Durable** | TTL-classify ephemeral info | "Meeting tomorrow" → short-term |
| **Relevant** | Skip if off-topic | Idle chat noise → ❌ |

## Architecture

```
┌───────────────────────────────────────────────────────┐
│                   Leaper Gateway                       │
│              Route · Auth · Session Mgmt               │
├───────┬───────┬───────┬───────┬───────┬───────────────┤
│  CS   │ Sales │  Ops  │ Coach │  ...  │  Custom       │
│ Agent │ Agent │ Agent │ Agent │       │  Agents       │
├───────┴───────┴───────┴───────┴───────┴───────────────┤
│              DeepBrain 6-Layer Engine                   │
│         (Memory isolated per agent, shared DB)         │
├───────────────────────────────────────────────────────┤
│   Tool System: File · Terminal · Search · Browser ·    │
│   Code Exec · MCP Protocol                             │
├───────────────────────────────────────────────────────┤
│  LLM: OpenAI · Claude · DeepSeek · Qwen · Zhipu ·     │
│        Moonshot · Ollama                               │
├───────────────────────────────────────────────────────┤
│  Channels: Telegram · Discord · 飞书 · 钉钉 ·          │
│            企业微信 · REST API                          │
└───────────────────────────────────────────────────────┘
```

**Key design decisions:**
- **1 process, N agents** — shared infra, isolated memory, low overhead
- **MCP protocol** — extensible tool ecosystem
- **Multi-LLM** — switch providers without code changes
- **Usage billing + cost optimization** built in

## Templates: Ready in Minutes

10 CXO role templates + 140 industry-specific variants:

```bash
leaper templates list                                       # Browse all
leaper create my-cfo --template cfo --bot-token TOKEN       # CFO advisor
leaper create my-cs --template customer-success --industry ecommerce --bot-token TOKEN
leaper start --all                                          # Launch all
```

| Role | What It Does |
|------|-------------|
| CEO Coach | Strategic thinking, decision frameworks, OKR review |
| CTO | Tech stack review, architecture decisions, trend analysis |
| CFO | Financial analysis, cost control, budget planning |
| CMO | Marketing strategy, user growth, competitor analysis |
| Customer Success | Client history, renewal alerts, churn prediction |
| ... | 140+ industry variants (e-commerce, SaaS, healthcare...) |

## Use Cases

**Enterprise**: Onboarding bots that learn company policies · CS agents that remember every client · Tech advisors that accumulate architecture decisions

**Consumer**: Personal coaches that track progress · Study assistants with spaced repetition · Health advisors with longitudinal analysis

**The pattern**: Any scenario where "AI that gets smarter over time" beats "AI that starts from scratch every time."

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Telegram | ✅ Recommended | Full-featured |
| Discord | ✅ | Full-featured |
| 飞书 (Feishu) | ✅ | Native integration |
| 钉钉 (DingTalk) | ✅ | Native integration |
| 企业微信 (WeCom) | ✅ | Native integration |
| REST API | ✅ | For custom frontends |
| 微信 (WeChat) | 🔜 | Coming soon |
| Web UI | 🔜 | Coming soon |

## Configuration

```yaml
# ~/.leaper/global.yaml (generated by leaper init)
api:
  provider: openai            # openai / claude / deepseek / ollama / custom
  base_url: https://api.openai.com/v1
  api_key: sk-xxx
  model: gpt-4o

proxy:
  http: http://127.0.0.1:10809
```

## System Requirements

| | Minimum | Recommended |
|---|---|---|
| Python | 3.10 | 3.12+ |
| RAM | 2 GB | 4 GB+ |
| Network | Required | Stable connection |
| LLM | Any OpenAI-compatible | Claude Opus / GPT-4o |

## Security

- **Approval system** — sensitive operations require human confirmation
- **Sandbox isolation** — tool execution in sandboxed environment
- **Path guard** — restrict file system access per agent

## Roadmap

- [x] DeepBrain 6-layer memory engine + 4Gate
- [x] Template system (10 CXO + 140 industry)
- [x] Multi-agent single-process architecture
- [x] Telegram / Discord / 飞书 / 钉钉 / 企业微信
- [x] MCP protocol support
- [x] Usage billing + cost optimization
- [ ] Web UI management panel
- [ ] WeChat integration
- [ ] Agent-to-agent collaboration
- [ ] Template marketplace (Workshop)
- [ ] Benchmark publication

## License

[MIT](LICENSE) — free for commercial use.

## Related Projects

| Project | Description |
|---------|-------------|
| [leaper-agent-cn](https://github.com/Deepleaper/leaper-agent-cn) | 🇨🇳 中国版 — 国产 LLM 原生适配，国内渠道深度集成 |
| [opc-deepbrain](https://github.com/Deepleaper/opc-deepbrain) | 🧠 独立的六层记忆引擎 — <2000 行，可嵌入任何框架 |

---

<p align="center">
  <a href="https://github.com/Deepleaper"><strong>Deepleaper 跃盟开源</strong></a><br>
  <sub>Building AI that learns. 让 AI 越用越聪明。</sub>
</p>

<p align="center">
  ⭐ Star this repo if you believe AI should remember.
</p>
