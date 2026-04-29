# Leaper Agent

**A Self-Evolving AI Agent Framework** — the AI colleague that actually learns from experience.

Most AI agents are stateless. Every conversation starts from zero. They don't remember what worked, what failed, or who you are. Leaper is different: it extracts structured experiences from every interaction, clusters them into reusable skills, builds a mental model of you, and validates its own knowledge for consistency. Six layers of evolution, running continuously.

---

## Install in 30 Seconds

```bash
pip install leaper-agent
leaper init
leaper run
```

No C++ compiler. No GPU. Pure Python. Windows, macOS, Linux.

---

## What Makes This Different

| Feature | How It Works |
|---------|-------------|
| **Real Memory** | Every conversation analyzed on 4 dimensions (task / strategy / outcome / insight), filtered through 4-gate quality control, deduplicated at cosine > 0.85, stored in local SQLite. BM25 + vector hybrid recall with RRF fusion. |
| **Gets Smarter Over Time** | L1 extracts experiences → L2 clusters into skills → L3 merges/deprecates/promotes → L4 builds user model → L5 validates consistency. Each layer has quality gates and measurable metrics. |
| **Local-First LLM** | High-frequency ops (embedding, extraction, validation) run on local Ollama. Only infrequent reasoning (skill synthesis, user modeling) calls cloud. Deterministic operations use rules, never LLM. |
| **Product-Grade UX** | Interactive wizard. No YAML editing. No CLI gymnastics. |
| **15+ Platforms** | Telegram · Discord · Slack · WhatsApp · Signal · Feishu · DingTalk · Matrix · Email · Home Assistant · API · CLI — one process, all channels. |
| **Zero-Config Search** | DuckDuckGo works out of the box. No API key needed. Add Firecrawl/Tavily for deep search. |
| **Template System** | 10 CXO roles × 20 industries = 150 ready-to-use configurations. One command to deploy. |

---

## DeepBrain: Six-Layer Self-Evolution Engine

This is the core differentiator. Not RAG. Not a notepad. A cognitive evolution system.

### The Problem with Existing Approaches

**Approach 1: Full-context injection.** Write everything to MEMORY.md, inject it all every turn. Context grows linearly. After 50 conversations, costs are uncontrollable and the model drowns in noise.

**Approach 2: RAG vector retrieval.** Embed memories, retrieve Top-K. Pure vector search fails at exact term matching ("MST state machine" won't match "Mission State Transition"). Can't handle knowledge decay, conflicts, or quality filtering.

**DeepBrain's approach:** BM25 exact matching + vector semantic search, RRF fusion ranking, six-layer evolution loop with quality gates at every stage.

---

### L0 — Hybrid Recall

Two-path retrieval fused with Reciprocal Rank Fusion:

```
RRF_score(d) = Σ 1 / (k + rank_i(d))    k = 60
```

- **Path 1 — BM25**: SQLite keyword search. Exact matches for terms, abbreviations, codenames.
- **Path 2 — 768-dim vectors**: `nomic-embed-text` (274MB) local embedding. Semantic understanding.

**Why RRF?** Scale-invariant. BM25 scores range 0–25, cosine ranges 0–1. Weighted averaging needs normalization with fragile parameters. RRF only looks at rank positions.

**Graceful degradation:**
- Ollama + embedding model → full RRF hybrid
- Ollama without embedding → BM25 only
- No Ollama at all → SQLite LIKE keyword fallback

---

### L1 — Experience Extraction

After each conversation turn, structured 4-dimensional extraction:

```json
{
  "task": "What the user needed",
  "strategy": "What approach was chosen",
  "outcome": "Success or failure, and why",
  "insight": "Reusable takeaway"
}
```

**4-Gate Quality Control:**
1. **Success gate** — failed conversations don't get stored (no garbage in)
2. **Complexity gate** — < 30 chars = trivial ("hi", "thanks", "ok") → filtered
3. **Dedup gate** — cosine > 0.85 with existing entry → skip
4. **Completeness gate** — all four fields must have substance (≥ 10 chars each)

**Measured:** ~27% of conversations filtered. 73% effective storage rate.

---

### L2 — Skill Generation

Experiences are one-shot ("analyzed Dify competitor that time"). Skills are reusable ("how to do competitor analysis"). After accumulating enough similar experiences, the system synthesizes methodology.

- **Clustering**: Greedy cosine-similarity, threshold 0.7, minimum 5 experiences per cluster
- **Synthesis**: LLM receives cluster → outputs skill (title, content, applicable scenarios, confidence)
- **Backtesting**: Apply new skill to historical questions, compare quality against originals

---

### L3 — Cross-Skill Evolution

Skills accumulate redundancy and become stale. L3 handles lifecycle:

| Operation | Trigger | Action |
|-----------|---------|--------|
| **MERGE** | Two skills cosine > 0.8 | Combine, keep higher-confidence structure |
| **DEPRECATE** | access_count = 0, confidence < 0.5 | Mark deprecated, lower recall weight |
| **PROMOTE** | access_count > 10, confidence > 0.8 | Mark core, boost recall weight |

Plus **drift detection**: skill unused 90+ days and contradicted by new experiences → trigger review.

**L3 uses zero LLM calls.** Entirely deterministic operations on cosine similarity and access counts.

---

### L4 — User Modeling

Automatically builds multi-dimensional user profile from conversations:

```json
{
  "communication_style": "Direct, data-driven, hates fluff",
  "decision_patterns": "Data first, then judgment. Prefers MVP over perfection",
  "recurring_topics": ["AI trends", "competitor analysis", "product architecture"],
  "expertise_level": "expert",
  "confidence": 0.78
}
```

**Update strategy**: Incremental Bayesian merge, not overwrite. One conversation won't overturn the entire model.

---

### L5 — Adversarial Validation

The immune system. Triggers after every write:

- **Consistency check**: New entry vs. existing knowledge. Contradictions flagged, not silently overwritten.
- **Regression protection**: After skill updates, backtest top-5 historical questions. Quality drops → rollback.
- **Decay**: Linear, `access_count -= 1` every 7 days for untouched entries. Predictable (unlike exponential decay that never reaches zero).

**L5 is 100% rule-based. Zero LLM calls.** The validation layer cannot depend on the thing it's validating.

---

### LLM Tiering Strategy

| Layer | Operation | Compute | Model | Frequency |
|-------|-----------|---------|-------|-----------|
| L0 | Vector generation | Local | nomic-embed-text (274MB) | Every turn |
| L0 | BM25 search | Local | SQLite built-in | Every turn |
| L1 | Experience extraction | Local | qwen2.5:7b (4.7GB) | Every turn |
| L1 | Quality gating | Rules | — | Every turn |
| L2 | Clustering | Local | Cosine similarity | Per 5+ experiences |
| L2 | Skill synthesis | Cloud | Primary model | Infrequent |
| L3 | MERGE/DEPRECATE/PROMOTE | Rules | — | Periodic |
| L4 | Profile building | Cloud | Primary model | Infrequent |
| L5 | Consistency/regression/decay | Rules | — | Every write |

**High-frequency = local/rules, zero API cost. Low-frequency = cloud LLM.**

---

## 10 CXO Role Templates

One command to create a professional AI employee:

```bash
leaper init --template cfo
```

| # | Role | Template ID | What It Does | Skills |
|---|------|-------------|--------------|--------|
| 1 | 🎯 CEO Coach | `ceo-coach` | Socratic questioning + 40 business frameworks | 10 |
| 2 | 💻 CTO | `cto` | Tech strategy, architecture, security audit | 9 |
| 3 | 💰 CFO | `cfo` | Cash flow, fundraising, budgets, tax planning | 9 |
| 4 | 📣 CMO | `cmo` | Positioning, GTM, acquisition, competitor intel | 8 |
| 5 | ⚙️ COO | `coo` | OKR tracking, meeting management, SOPs | 7 |
| 6 | 🎯 CPO | `cpo` | PRDs, roadmaps, user stories, metrics | 8 |
| 7 | 👥 CHRO | `chro` | JDs, interview design, comp, org structure | 8 |
| 8 | ⚖️ CLO | `clo` | Contract review, compliance, IP strategy | 7 |
| 9 | 🧭 CSO | `cso` | Industry analysis, scenario planning, business models | 9 |
| 10 | 📢 CCO | `cco` | Brand comms, founder IP, crisis PR, sentiment | 7 |

**82 specialized skills** covering every core function from strategy to execution.

Each template includes: SOUL.md (personality), EGO.md (behavioral rules), config.yaml, L2/L3 skill sets, and a pre-configured brain.

---

## Industry Adaptations (Pro)

Generic templates work out of the box. Industry-specific versions provide deeper domain knowledge and workflows:

`ecom` · `adtech` · `invest` · `edu` · `health` · `b2b` · `finance` · `consumer` · `auto` · `mfg` · `realestate` · `energy` · `logistics` · `travel` · `agri` · `construction` · `legal` · `hr` · `fitness` · `media`

**20 industries × 7 roles = 140 industry templates.** Available through Leaper Pro subscription.

### Three-Layer Skill Architecture

```
L1 Industry Skills (21)    ← Domain knowledge (e.g., ecommerce GMV analysis)   [Pro]
L2 Role Skills (10)        ← Role capabilities (e.g., CFO financial modeling)   [Open Source]
L3 Workstation Skills (72) ← Concrete scenarios (e.g., CFO cash flow forecast) [Open Source]
```

Automatic matching: CFO + ecommerce → loads `L1-ecom` + `L2-cfo-financial-modeling` + `L3-cfo-cashflow/budget/cost/...`

---

## Multi-Agent Architecture

Run multiple AI roles from a single process:

```bash
leaper init-team    # Interactive wizard: add roles + tokens
leaper run          # All agents start together (~1GB RAM total)
```

Each agent gets:
- **Isolated workspace** (`~/.leaper/agents/{role}/`)
- **Isolated brain.db** (memories never cross-contaminate)
- **Independent bot** (one Telegram token per role)
- **Shared model config** (one LLM provider for all)

```yaml
# ~/.leaper/config.yaml
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

## 15+ Platform Connections

Single gateway process. Conversations persist across platforms.

| Platform | Protocol | Config |
|----------|----------|--------|
| **Telegram** | Bot API | `TELEGRAM_BOT_TOKEN` |
| **Discord** | discord.js | `DISCORD_BOT_TOKEN` |
| **Slack** | Bolt SDK | `SLACK_BOT_TOKEN` |
| **WhatsApp** | Baileys | config.yaml |
| **Signal** | signal-cli | config.yaml |
| **Feishu** | Open API | config.yaml |
| **DingTalk** | Stream SDK | config.yaml |
| **Matrix** | matrix-nio | config.yaml |
| **Email** | IMAP/SMTP | config.yaml |
| **Home Assistant** | REST API | config.yaml |
| **API** | HTTP/WebSocket | Built-in |
| **CLI** | Local terminal | `leaper chat` |

---

## 40+ Built-in Tools

| Category | Tools |
|----------|-------|
| **Terminal & Files** | `terminal` · `file_read` · `file_write` · `file_edit` |
| **Search & Web** | `web_search` · `web_fetch` — degradation: Firecrawl → Tavily → DuckDuckGo (zero-config) |
| **Code & Dev** | `code_execute` · `git` · `github` |
| **Media** | `image_generation` · `tts` · `vision` · `pdf_reader` |
| **Automation** | `cron` · `delegation` · `webhook` |

Extends via [MCP protocol](https://modelcontextprotocol.io) for third-party tool servers.

---

## Model Support

| Provider | Examples | Config |
|----------|---------|--------|
| **OpenAI** | GPT-4o, GPT-4.1, o3 | `OPENAI_API_KEY` |
| **Anthropic** | Claude Opus 4, Sonnet 4 | `ANTHROPIC_API_KEY` |
| **OpenRouter** | 200+ models | `OPENROUTER_API_KEY` |
| **Ollama** | qwen2.5, llama3, deepseek-r1 | Local, zero config |
| **Any compatible** | Aggregator platforms, private deployments | `base_url` + `api_key` |

Automatic failover when primary model is unavailable.

---

## Prerequisites

| Tool | Version | Download | Notes |
|------|---------|----------|-------|
| **Python** | ≥ 3.10 | [python.org/downloads](https://www.python.org/downloads/) | Windows: check "Add python.exe to PATH" |
| **Git** | any | [git-scm.com/download](https://git-scm.com/download/) | Optional, only for development |
| **Ollama** | any | [ollama.com/download](https://ollama.com/download) | Optional. For local models. Not needed if using cloud API only |

---

## Quick Start

```bash
pip install leaper-agent

leaper init                          # Interactive wizard
leaper init --template ceo-coach     # Create from template
leaper init-team                     # Multi-role team setup
leaper chat                          # Terminal conversation
leaper run                           # Start gateway (Telegram, etc.)
leaper workshop                      # Browse template marketplace
```

---

## Configuration

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
  localModel: auto    # auto = detect Ollama | off = cloud only
```

---

## Workspace Files

Agent identity and rules live in Markdown — no code needed:

| File | Purpose | Loading |
|------|---------|---------|
| `EGO.md` | Behavioral rules and boundaries | Always |
| `SOUL.md` | Personality, expertise, communication style | Always |
| `IDENTITY.md` | One-line identity | Always |
| `USER.md` | User profile | Always |
| `MEMORY.md` | Long-term memory seed | Seed once, then recall on demand |
| `AGENTS.md` | Multi-agent collaboration rules | Always |

---

## DB Schema

`brain.db` — local SQLite, typically < 10MB for 1000+ entries.

```sql
CREATE TABLE pages (
    slug TEXT PRIMARY KEY,
    title TEXT,
    namespace TEXT,
    content TEXT,
    entry_type TEXT,     -- experience | skill | user_model | meta
    confidence REAL,     -- 0.0 - 1.0
    access_count INTEGER,
    last_accessed TEXT,
    metadata TEXT,       -- JSON
    updated_at TEXT
);

CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    page_slug TEXT REFERENCES pages(slug),
    content TEXT
);
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LEAPER_HOME` | Working directory | `~/.leaper` |
| `LEAPER_LOCAL_URL` | Ollama address | `http://localhost:11434/v1` |
| `LEAPER_LOCAL_MODEL` | Local model | `qwen2.5:7b` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | — |
| `OPENAI_API_KEY` | OpenAI API Key | — |
| `ANTHROPIC_API_KEY` | Anthropic API Key | — |

---

## Development

```bash
git clone https://github.com/Deepleaper/leaper-agent.git
cd leaper-agent
python -m venv venv && source venv/bin/activate
pip install -e ".[all,dev]"
```

### DeepBrain Code Structure (~1951 lines)

```
agent/
  leaper_brain.py           # 564 lines — L0 hybrid recall, DB ops
  leaper_evolution.py       # 992 lines — L1-L5 evolution logic
  leaper_orchestrator.py    # 137 lines — evolution scheduler
  leaper_seed_loader.py     #           — workspace loading + OS injection

plugins/memory/deepbrain/
  provider.py               # 258 lines — Memory Provider interface
  plugin.yaml
```

---

## License

Apache-2.0 © [Deepleaper](https://www.deepleaper.com)
