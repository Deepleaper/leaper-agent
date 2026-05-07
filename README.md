<div align="center">

# 🚀 Leaper Agent

### The Agent Framework That Actually Remembers

### Hermes-Compatible Agent Orchestration + DeepBrain 6-Layer Evolving Memory

[![PyPI version](https://img.shields.io/pypi/v/leaper-agent.svg)](https://pypi.org/project/leaper-agent/)
[![Downloads](https://img.shields.io/pypi/dm/leaper-agent.svg)](https://pypi.org/project/leaper-agent/)
[![GitHub stars](https://img.shields.io/github/stars/deepleaper/leaper-agent.svg)](https://github.com/deepleaper/leaper-agent/stargazers)
[![License](https://img.shields.io/badge/License-BSL--1.1-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

[Website](https://www.deepleaper.com) · [Quick Start](#-quick-start) · [Why Memory Matters](#-why-memory-matters) · [中国版](https://github.com/deepleaper/leaper-agent-cn)

</div>

---

## 🤔 The Problem

Every agent framework gives you tool-calling and multi-model support. **None of them give you real memory.**

- CrewAI? Flat key-value store, resets between runs.
- AutoGen? Conversation history only, no knowledge evolution.
- LangGraph? Checkpoints, not understanding.
- Hermes Agent? Skill files on disk — smart, but static.

**Your agent forgets everything the moment the session ends.**

## 💡 The Solution

**Leaper Agent = [Hermes Agent](https://github.com/hermes-agent) base + [DeepBrain](https://github.com/deepleaper/opc-deepbrain) memory engine.**

We took the proven Hermes Agent architecture — its agent loop, tool runtime, and multi-provider support — and integrated DeepBrain's 6-layer self-evolving memory engine. The result: **an agent that gets smarter every time you talk to it.**

```
Session 1: "I'm building a SaaS product with FastAPI and React."
Session 2: "What stack should I use for the admin panel?"
→ Agent recalls your tech choices, suggests FastAPI Admin + React
→ No manual context injection. It just knows.
```

## 🧠 Why Memory Matters

| What happens | Without memory | With DeepBrain |
|-------------|---------------|----------------|
| You mention your tech stack | Forgotten next session | Remembered forever, evolves over time |
| You correct the agent | Same mistake tomorrow | Learns the correction, never repeats |
| You have 50 conversations | Each starts from zero | Agent builds a knowledge graph of YOU |
| Knowledge conflicts | Silently contradicts itself | 4-Gate system detects & resolves conflicts |

### 6-Layer Memory Architecture

```
┌─────────────────────────────────────────┐
│  Layer 5: Meta-Knowledge               │
│  "I know your tech preferences well,   │
│   but I'm uncertain about your budget"  │
├─────────────────────────────────────────┤
│  Layer 4: Archived — Historical ref     │
├─────────────────────────────────────────┤
│  Layer 3: Consolidated — Cross-session  │
├─────────────────────────────────────────┤
│  Layer 2: Long-Term — Validated facts   │
├─────────────────────────────────────────┤
│  Layer 1: Short-Term — Recent context   │
├─────────────────────────────────────────┤
│  Layer 0: Flash — Current session       │
└─────────────────────────────────────────┘
    ↑ Auto-promotion via 4-Gate QC ↑
    (Relevance · Novelty · Consistency · Utility)
```

This isn't RAG. This isn't vector search. This is **knowledge that evolves** — facts get validated, promoted, consolidated, and the agent develops meta-awareness of what it knows well and what it doesn't.

## 🚀 Quick Start

```bash
# Install
pip install leaper-agent

# Set your API key
export OPENAI_API_KEY=sk-xxx
# or: export ANTHROPIC_API_KEY=sk-ant-xxx
# or: export GEMINI_API_KEY=xxx

# Create an agent with the CEO Coach template
leaper create my-agent --template ceo-coach

# Start
leaper start my-agent
```

### Deploy as Telegram Bot

```bash
leaper create my-bot --template ceo-coach --bot-token YOUR_TELEGRAM_TOKEN
leaper start my-bot
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         Leaper Agent Runtime            │
│    (Hermes-compatible agent loop)       │
├─────────┬──────────┬──────────┬────────┤
│ OpenAI  │ Claude   │ Gemini   │ Ollama │
├─────────┴──────────┴──────────┴────────┤
│         Agent Orchestration             │
│    Role templates · Tool calling        │
├─────────────────────────────────────────┤
│      🧠 DeepBrain Memory Engine         │
│   6-Layer · 4-Gate · Zero Dependencies  │
│   SQLite-only · 100% Local · Evolving   │
└─────────────────────────────────────────┘
```

**Key difference from Hermes:** Hermes stores skills as static Markdown files. Leaper Agent's DeepBrain **automatically extracts, validates, and evolves knowledge** from every conversation — no manual curation needed.

## ⚡ Hermes Compatibility

Leaper Agent is built on the Hermes Agent foundation. If you're familiar with Hermes, you'll feel at home:

- Same agent loop architecture
- Same multi-provider model support
- Same tool runtime
- **Plus:** 6-layer evolving memory that Hermes doesn't have

## 🔌 Supported Providers

| Provider | Models | Status |
|----------|--------|--------|
| OpenAI | GPT-4o, GPT-4o-mini, o1/o3 | ✅ |
| Anthropic | Claude Sonnet, Opus, Haiku | ✅ |
| Google | Gemini 2.0, 2.5 | ✅ |
| Ollama | Any local model | ✅ |

## 📊 vs Other Frameworks

| | Leaper Agent | Hermes | CrewAI | AutoGen | LangGraph |
|---|:---:|:---:|:---:|:---:|:---:|
| Memory that evolves | ✅ 6-layer | ❌ Static files | ❌ Flat KV | ❌ Chat history | ❌ Checkpoints |
| Knowledge quality control | ✅ 4-Gate | ❌ | ❌ | ❌ | ❌ |
| Meta-knowledge | ✅ | ❌ | ❌ | ❌ | ❌ |
| Multi-provider | ✅ | ✅ | ✅ | ✅ | ✅ |
| Zero memory dependencies | ✅ SQLite only | N/A | ❌ Redis/Qdrant | ❌ | ❌ Vector DB |
| Hermes compatible | ✅ | ✅ | ❌ | ❌ | ❌ |

## 🇨🇳 China Version / 中国版

For Chinese LLM providers (DeepSeek, 通义千问, 智谱, Moonshot) + 150 role templates:

```bash
pip install leaper-agent-cn
```

→ [Leaper Agent CN](https://github.com/deepleaper/leaper-agent-cn)

## 🔗 Ecosystem

| Project | Description |
|---------|-------------|
| [OPC DeepBrain](https://github.com/deepleaper/opc-deepbrain) | Standalone memory engine (use in any framework) |
| [OPC Agent](https://github.com/deepleaper/opc-agent) | Local-first agent with Ollama |
| [Leaper Agent CN](https://github.com/deepleaper/leaper-agent-cn) | China-optimized with 150 templates |

## 📄 License

[BSL-1.1](LICENSE) — Free for non-competitive use. Converts to Apache-2.0 after 4 years.

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

📧 Contact: [tech@deepleaper.com](mailto:tech@deepleaper.com)

---

<div align="center">

**Built with ❤️ by [Deepleaper Technology / 跃盟科技](https://www.deepleaper.com)**

*Other agents forget. Leaper Agent evolves.*

</div>
