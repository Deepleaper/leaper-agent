<div align="center">

# 🚀 Leaper Agent

### Self-Evolving AI Agent Framework — Multi-Provider, Multi-Agent, with Built-in Memory

### 自进化 AI Agent 框架 — 多模型、多智能体、内置记忆引擎

[![PyPI version](https://img.shields.io/pypi/v/leaper-agent.svg)](https://pypi.org/project/leaper-agent/)
[![Downloads](https://img.shields.io/pypi/dm/leaper-agent.svg)](https://pypi.org/project/leaper-agent/)
[![GitHub stars](https://img.shields.io/github/stars/deepleaper/leaper-agent.svg)](https://github.com/deepleaper/leaper-agent/stargazers)
[![License](https://img.shields.io/badge/License-BSL--1.1-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

[Website](https://www.deepleaper.com) · [Quick Start](#-quick-start) · [Features](#-features) · [中国版](https://github.com/deepleaper/leaper-agent-cn)

</div>

---

## ✨ Why Leaper Agent?

Most agent frameworks treat every conversation as a blank slate. **Leaper Agent** is different — it **learns from every interaction** and gets smarter over time, powered by [DeepBrain](https://github.com/deepleaper/opc-deepbrain)'s 6-layer self-evolving memory.

Built on top of [Hermes Agent](https://github.com/hermes-agent), enhanced with persistent memory, multi-agent orchestration, and production-ready integrations.

## 🎯 Features

- 🧠 **Self-Evolving Memory** — DeepBrain 6-layer memory: your agent remembers, consolidates, and evolves
- 🔌 **Multi-Provider** — OpenAI, Anthropic Claude, Google Gemini, and more. Switch with one line
- 🤝 **Multi-Agent** — Orchestrate multiple agents with different roles and specialties
- 🤖 **Telegram Integration** — Deploy as a Telegram bot in minutes
- 🎭 **Role Templates** — Pre-built personas (CTO, Analyst, Writer…) or create your own
- 🔧 **MCP Support** — Model Context Protocol for tool/plugin extensibility
- 📡 **Streaming** — Real-time streaming responses out of the box

## 🚀 Quick Start

```bash
# 1. Install
pip install leaper-agent

# 2. Set your API key (pick one)
export OPENAI_API_KEY=sk-xxx
# or: export ANTHROPIC_API_KEY=sk-ant-xxx
# or: export GEMINI_API_KEY=xxx

# 3. Initialize
leaper-agent init

# 4. Chat!
leaper-agent chat
```

### As a Telegram Bot

```bash
export TELEGRAM_BOT_TOKEN=your-token
leaper-agent serve --telegram
```

### Multi-Agent Setup

```python
from leaper_agent import Agent, Team

researcher = Agent(role="researcher", provider="openai", model="gpt-4o")
writer = Agent(role="writer", provider="anthropic", model="claude-sonnet-4-20250514")

team = Team(agents=[researcher, writer])
result = team.run("Research and write an article about quantum computing")
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│           Leaper Agent Core             │
├─────────┬──────────┬───────────────────┤
│ OpenAI  │ Claude   │ Gemini  │ ...     │
├─────────┴──────────┴───────────────────┤
│         Role Templates & Tools          │
├─────────────────────────────────────────┤
│         Multi-Agent Orchestration       │
├─────────────────────────────────────────┤
│         🧠 DeepBrain Memory Engine      │
│    6-Layer Self-Evolving Knowledge      │
│    ┌──────────────────────────────┐     │
│    │  4-Gate Quality Control      │     │
│    │  Relevance → Novelty →       │     │
│    │  Consistency → Utility       │     │
│    └──────────────────────────────┘     │
└─────────────────────────────────────────┘
```

## 🔌 Supported Providers

| Provider | Models | Status |
|----------|--------|--------|
| OpenAI | GPT-4o, GPT-4o-mini, o1/o3 | ✅ |
| Anthropic | Claude Sonnet, Opus, Haiku | ✅ |
| Google | Gemini 2.0, 2.5 | ✅ |
| Ollama | Any local model | ✅ |

## 🎭 Built-in Role Templates

```bash
# Use a pre-built role
leaper-agent chat --role cto
leaper-agent chat --role analyst
leaper-agent chat --role writer

# Create your own
leaper-agent role create my-role
```

## 🧠 Memory in Action

```python
from leaper_agent import Agent

agent = Agent(provider="openai", model="gpt-4o", memory=True)

# Session 1
agent.chat("My name is Ray, I'm building an AI startup")

# Session 2 — agent remembers!
agent.chat("What's my name?")  # → "Your name is Ray..."
```

## 🇨🇳 China Version / 中国版

For users in China with Chinese LLM providers (通义千问、DeepSeek、文心一言):

```bash
pip install leaper-agent-cn
```

→ [Leaper Agent CN](https://github.com/deepleaper/leaper-agent-cn)

## 📄 License

[BSL-1.1](LICENSE) — see LICENSE for details.

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

📧 Contact: [tech@deepleaper.com](mailto:tech@deepleaper.com)

---

<div align="center">

**Built with ❤️ by [Deepleaper Technology / 跃盟科技](https://www.deepleaper.com)**

*Agents that learn. Agents that evolve. Agents that remember.*

</div>
