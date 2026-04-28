# Leaper Agent

**Self-Evolving AI Agent Framework** — An AI colleague that actually learns from experience.

Most AI agents are stateless. Every conversation starts from zero. Leaper is different: it extracts structured experiences from every interaction, clusters them into reusable skills, builds a mental model of you, and validates its own knowledge for consistency. Six layers of evolution, running continuously.

<table>
<tr><td><b>Real Memory, Not a Notepad</b></td><td>Every conversation is analyzed along four dimensions (task/strategy/outcome/insight), filtered through 4-gate quality control, deduplicated at cosine > 0.85, and stored in a local SQLite database. BM25 + vector hybrid recall with RRF fusion — not "dump everything into context".</td></tr>
<tr><td><b>Gets Smarter Over Time</b></td><td>L1 extracts experiences → L2 clusters into reusable skills → L3 merges/deprecates/promotes across skills → L4 builds a user mental model → L5 validates consistency + runs regression checks. Each layer has quality gates and measurable metrics.</td></tr>
<tr><td><b>Local-First LLM Strategy</b></td><td>High-frequency operations (embedding, extraction, validation) run on local Ollama models. Only infrequent reasoning tasks (skill synthesis, user modeling) call cloud LLMs. Deterministic operations use rules, not LLM.</td></tr>
<tr><td><b>Product-Grade Install</b></td><td><code>pip install leaper-agent && leaper init && leaper run</code> — interactive wizard, no manual config editing. Pure Python, zero native compilation dependencies.</td></tr>
<tr><td><b>15+ Platforms Out of the Box</b></td><td>Telegram · Discord · Slack · WhatsApp · Signal · Feishu · DingTalk · Matrix · Email · Home Assistant · API · CLI — single gateway process connects all platforms.</td></tr>
<tr><td><b>Zero-Config Search</b></td><td>DuckDuckGo fallback needs no API key. Add Firecrawl / Tavily keys for deep search.</td></tr>
<tr><td><b>Template System</b></td><td><code>leaper init --template ceo-coach</code> creates a professional AI employee in one command. CEO Coach template: Socratic coaching + 40 business frameworks + six-layer memory.</td></tr>
</table>

---

## DeepBrain: Six-Layer Self-Evolution Engine

This is what makes Leaper fundamentally different from every other agent framework.

### Why Not RAG?

Existing agent "memory" falls into two patterns:

1. **Full-context injection** — Write everything to MEMORY.md, stuff it all into the system prompt every turn. Problem: context window grows linearly, costs become uncontrollable after 50 conversations.
2. **RAG vector retrieval** — Embed memories, retrieve Top-K each turn. Problem: pure vector search is poor at exact term matching ("MST state machine" won't match "Mission State Transition"), and cannot handle knowledge decay or conflicts.

DeepBrain's approach: **BM25 exact matching + vector semantic search, RRF fusion ranking, six-layer evolution loop.** Not RAG — a cognitive evolution system.

### Data Flow

```
User message → Core engine processes → Agent replies
                                          ↓
                                    sync_turn() triggers
                                          ↓
                            ┌─────────────────────────────┐
                            │  L1 Experience Extract       │
                            │  4D analysis → 4Gate → store │
                            └──────────────┬───────────────┘
                                          ↓ (5+ entries accumulated)
                            ┌─────────────────────────────┐
                            │  L2 Skill Generate           │
                            │  cluster → synthesize → test │
                            └──────────────┬───────────────┘
                                          ↓ (periodic)
                            ┌─────────────────────────────┐
                            │  L3 Cross-Skill Evolution    │
                            │  MERGE / DEPRECATE / PROMOTE │
                            └──────────────┬───────────────┘
                                          ↓ (sufficient data)
                            ┌─────────────────────────────┐
                            │  L4 User Model               │
                            │  Multi-dimensional profiling │
                            └──────────────┬───────────────┘
                                          ↓ (after every write)
                            ┌─────────────────────────────┐
                            │  L5 Adversarial Validation   │
                            │  consistency + regression    │
                            │  + decay                     │
                            └─────────────────────────────┘

Recall path (independent of evolution):
User message → L0 Hybrid Recall → RRF fusion → Top-K injected into context
```

---

### L0 — Hybrid Recall

**Problem**: Pure vector search is bad at exact term matching. Pure keyword search can't understand that "evolution" and "gets smarter" mean the same thing.

**Solution**: BM25 + vector search, RRF fusion.

```
RRF_score(d) = Σ 1 / (k + rank_i(d))    where k = 60
```

Two rankers:
1. **BM25**: SQLite keyword search — exact matches for terms, abbreviations, codenames
2. **768-dim vectors**: `nomic-embed-text` (274MB) local embedding — semantic understanding

**Why RRF over weighted average?** RRF is scale-invariant. BM25 scores range 0–25, cosine scores range 0–1. Weighted averaging requires normalization with hard-to-tune parameters. RRF only looks at rank positions — automatically handles quality differences between rankers.

**Graceful degradation**:
- Ollama + nomic-embed-text available → full RRF
- Ollama without embedding model → BM25 only
- No Ollama → SQLite LIKE keyword search

```python
def hybrid_recall(self, query: str, top_k: int = 10) -> list[dict]:
    bm25_results = self._bm25_search(query, top_k=50)
    vector_results = self._vector_search(query, top_k=50)
    return self._rrf_fuse(bm25_results, vector_results, top_k=top_k)
```

---

### L1 — Experience Extract

**Problem**: Most agents let the LLM freely decide what to remember. Result: the same thing stored 5 times, trivial info taking up 40%+ of memory, no quality filtering.

**Solution**: Structured 4-dimensional extraction + 4-gate quality control.

#### Four Dimensions

After each conversation turn, the LLM returns structured JSON:

```json
{
  "task": "What the user asked for",
  "strategy": "What approach was chosen",
  "outcome": "What happened, success or failure",
  "insight": "Reusable takeaway from this interaction"
}
```

Based on Kolb's Experiential Learning Cycle: concrete experience (task) → reflective observation (strategy) → abstract conceptualization (insight) → active experimentation (outcome).

#### 4-Gate Quality Control

```python
def _should_store(self, experience: dict) -> bool:
    # Gate 1: Task must succeed
    if not experience.get("task_success"):
        return False
    
    # Gate 2: Complexity filter
    complexity = self._estimate_complexity(experience)
    if complexity == "trivial":  # < 30 chars
        return False  # "hello", "thanks", "ok" not worth storing
    
    # Gate 3: Deduplication
    similar = self.brain.hybrid_recall(experience["task"], top_k=3)
    if similar and similar[0]["score"] > 0.85:
        return False
    
    # Gate 4: Completeness — all four dimensions must have substance
    for field in ["task", "strategy", "outcome", "insight"]:
        if not experience.get(field) or len(experience[field]) < 10:
            return False
    
    return True
```

**Complexity detection**: Character count, not LLM judgment. In practice, LLMs classify almost everything as "moderate" in Chinese. `< 30 chars` = trivial, `30–200` = moderate, `≥ 200` = complex.

**Measured**: ~27% of conversations filtered by 4Gate, 73% effective storage rate.

---

### L2 — Skill Generate

**Problem**: Experiences are one-off ("analyzed Dify competitor that time"). Skills are reusable ("how to do competitor analysis"). After 20 uses, the agent should have synthesized its own methodology.

**Solution**: Cluster similar experiences → LLM synthesizes skill → backtesting validation.

- **Clustering**: Greedy cosine-similarity clustering, threshold 0.7, minimum 5 experiences per cluster
- **Synthesis**: LLM receives a cluster, outputs a skill definition with title, content, applicable scenarios, confidence score
- **Quality gate**: `title` > 5 chars, `content` > 50 chars
- **Backtesting**: Apply the new skill to historical questions, compare quality against original answers

**Why 0.7 threshold?** 0.8 is too strict — variations in phrasing split the same topic into tiny clusters. 0.6 is too loose — unrelated experiences get grouped together. 0.7 is empirically tuned on CEO Coach conversations.

---

### L3 — Cross-Skill Evolution

**Problem**: Skills accumulate redundancy ("competitor analysis v1" and "competitor analysis v2" say the same thing) and become stale.

| Operation | Trigger | Action |
|-----------|---------|--------|
| **MERGE** | Two skills cosine > 0.8 | Merge, keep higher-confidence structure |
| **DEPRECATE** | access_count = 0 and confidence < 0.5 | Mark deprecated, lower recall weight |
| **PROMOTE** | access_count > 10 and confidence > 0.8 | Mark core skill, boost recall weight |

Plus **drift detection**: if a skill hasn't been used in 90+ days and new experiences contradict it, trigger review.

**L3 uses zero LLM calls.** MERGE/DEPRECATE/PROMOTE are deterministic operations based on cosine similarity and access counts. This is core to the tiered design: **deterministic operations use rules; only fuzzy reasoning uses LLM.**

---

### L4 — User Model

**Problem**: The agent doesn't know you. The same question should get completely different answers for a CEO vs. an engineer.

**Solution**: Automatically build a multi-dimensional user profile from conversations.

```json
{
  "communication_style": "Direct, data-driven, dislikes fluff",
  "decision_patterns": "Data first, then judgment. Prefers MVP validation over perfect plans",
  "recurring_topics": ["AI trends", "competitor analysis", "product architecture"],
  "expertise_level": "expert",
  "confidence": 0.78
}
```

**Strict validation**: 4 required fields, minimum length checks (no single-word profiles like "friendly"), topic list must have ≥ 2 items, expertise must be an enum value, confidence must be 0–1.

**Update strategy**: Incremental merge, not overwrite. New observations fuse with existing profile, confidence updated via Bayesian update. One conversation won't overturn the entire user model.

---

### L5 — Adversarial Validation

The immune system for the memory engine. Triggers automatically after every write:

- **Consistency check**: New entry vs. existing knowledge base. Contradictions are flagged, not silently overwritten.
- **Regression protection**: After skill updates, backtest against top-5 historical questions. If quality drops, rollback.
- **Decay**: Linear decay, `access_count -= 1` every 7 days for untouched entries. An entry with `access_count = 10` reaches zero in 70 days — predictable, unlike exponential decay that never reaches zero.

**L5 is 100% rule-based. Zero LLM calls.** The validation layer cannot depend on LLM — otherwise LLM hallucinations would infect validation results.

---

## LLM Tiered Degradation

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

Auto-detection at startup: Ollama available → local-first. No Ollama → everything goes through cloud.

```bash
LEAPER_LOCAL_URL=http://localhost:11434/v1   # Custom Ollama address
LEAPER_LOCAL_MODEL=qwen2.5:14b               # Use a larger local model
```

---

## Platform Connectivity (15+ Channels)

Single gateway process connects all platforms. Conversations persist across platforms.

| Platform | Protocol | Config |
|----------|----------|--------|
| **Telegram** | Bot API | `TELEGRAM_BOT_TOKEN` |
| **Discord** | discord.js | `DISCORD_BOT_TOKEN` |
| **Slack** | Bolt SDK | `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` |
| **WhatsApp** | Baileys (no Business API needed) | `config.yaml` |
| **Signal** | signal-cli | `config.yaml` |
| **Feishu** | Open API | `config.yaml` |
| **DingTalk** | Stream SDK | `config.yaml` |
| **Matrix** | matrix-nio | `config.yaml` |
| **Email** | IMAP/SMTP | `config.yaml` |
| **LINE** | Messaging API | `config.yaml` |
| **Mattermost** | WebSocket | `config.yaml` |
| **IRC** | irc-framework | `config.yaml` |
| **Home Assistant** | REST API | `config.yaml` |
| **API** | HTTP/WebSocket | Built-in |
| **CLI** | Local terminal | `leaper chat` |

**Security**: DM pairing codes for unknown senders, user whitelists, group ID whitelists, mention-only mode, tool execution approval.

---

## 40+ Built-in Tools

### Terminal & Files
`terminal` · `file_read` · `file_write` · `file_edit` — shell execution with timeout, atomic writes, surgical edits.

### Search & Web
`web_search` · `web_fetch` · `web_scrape` — degradation chain: Firecrawl → Tavily → DuckDuckGo. Zero-config.

### Code & Dev
`code_execute` · `git` · `github` — sandboxed execution, full Git/GitHub API.

### Media
`image_generation` · `tts` · `vision` · `pdf_reader` — fal.ai / DALL-E / ElevenLabs / multimodal analysis.

### Automation
`cron` · `delegation` · `webhook` — scheduled tasks, parallel sub-agents, HTTP callbacks.

All tools support [MCP](https://modelcontextprotocol.io) protocol for extending with third-party tool servers.

---

## TUI Terminal Interface

Full terminal UI, not just readline:

- Multi-line editing for code and long text
- Slash command auto-completion
- Conversation history with cross-session persistence
- Streaming tool call output
- `Ctrl+C` interrupt and redirect
- `/new` · `/model` · `/compress` session management

```bash
leaper chat                    # Start terminal conversation
leaper chat --model gpt-4o     # Specify model
```

---

## Cron Scheduling

Built-in scheduler with cron expressions. Tasks run in isolated sessions, results delivered to any connected platform.

```yaml
cron:
  daily-report:
    schedule: "0 8 * * *"
    task: "Generate today's action items summary"
    deliver_to: telegram
```

---

## Sub-Agent Delegation

Complex tasks can be split across parallel sub-agents, each with independent context windows:

```
User: "Analyze these 5 competitors"
         ↓
Main Agent → Spawns 5 sub-agents (parallel)
         ↓
Main Agent ← Aggregates 5 reports → User
```

---

## Workspace Files

Agent persona, memory, and rules are defined through Markdown files — no code needed:

| File | Purpose | Loading |
|------|---------|---------|
| `EGO.md` | Core rules and behavioral boundaries | Always loaded |
| `SOUL.md` | Values, communication style, expertise | Always loaded |
| `IDENTITY.md` | One-line identity | Always loaded |
| `USER.md` | User profile | Always loaded |
| `MEMORY.md` | Persistent memory | Seed once, then recall on demand |
| `AGENTS.md` | Multi-agent collaboration rules | Always loaded |

`MEMORY.md` uses **seed-and-recall**: loaded fully on first conversation, then only relevant sections recalled via L0 Hybrid Recall. This solves the "more memory = more expensive context" problem.

---

## Model Support

| Provider | Examples | Config |
|----------|---------|--------|
| **OpenAI** | GPT-4o, GPT-4.1, o3 | `OPENAI_API_KEY` |
| **Anthropic** | Claude Opus 4, Sonnet 4 | `ANTHROPIC_API_KEY` |
| **OpenRouter** | 200+ models | `OPENROUTER_API_KEY` |
| **Ollama** | qwen2.5, llama3, deepseek-r1 | Local, zero config |
| **Custom** | Any OpenAI-compatible API | `base_url` + `api_key` |

Failover: automatic fallback when primary model is unavailable.

---

## Quick Install

```bash
pip install leaper-agent
```

**Requirements**: Python ≥ 3.10. No C++ compiler. No GPU.

```bash
leaper init                          # Interactive wizard
leaper init --template ceo-coach     # Create from template
leaper chat                          # Terminal conversation
leaper run                           # Start gateway (Telegram, etc.)
leaper workshop                      # Browse available templates
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

## Template System

```bash
leaper workshop                      # List templates
leaper init --template ceo-coach     # Install template
```

Templates are pre-configured file sets (YAML + Markdown), not hardcoded logic. Fork any template and modify freely.

### CEO Coach

Socratic startup coach designed for CEOs and founders:

- **Coaching philosophy**: Ask before answering, never decide for the user
- **40 business frameworks**: Porter's Five Forces, SWOT, Flywheel, TAM/SAM/SOM, Jobs-to-be-Done...
- **Six-layer memory**: Remembers your strategic preferences, past decisions, recurring concerns
- **Strict behavioral boundaries**: No internal tool exposure, no technical details leaked, no error messages shown to users

---

## DB Schema

`brain.db` — local SQLite, typically < 10MB for 1000+ entries.

```sql
CREATE TABLE pages (
    slug TEXT PRIMARY KEY,
    title TEXT,
    namespace TEXT,          -- agent/{name} | desk/{name}/{seat} | role/{role} | org
    content TEXT,
    entry_type TEXT,         -- experience | skill | user_model | meta
    confidence REAL,         -- 0.0 - 1.0
    access_count INTEGER,    -- used for L5 decay
    last_accessed TEXT,
    metadata TEXT,           -- JSON extension field
    updated_at TEXT
);

CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    page_slug TEXT REFERENCES pages(slug),
    content TEXT             -- chunked content for vector search
);
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LEAPER_HOME` | Working directory | `~/.leaper` |
| `LEAPER_LOCAL_URL` | Local Ollama address | `http://localhost:11434/v1` |
| `LEAPER_LOCAL_MODEL` | Local inference model | `qwen2.5:7b` |
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
  leaper_brain.py           # 564 lines — L0 hybrid recall, DB operations
  leaper_evolution.py       # 992 lines — L1-L5 evolution logic
  leaper_orchestrator.py    # 137 lines — evolution scheduler
  leaper_seed_loader.py     #           — workspace file loading + OS injection

plugins/memory/deepbrain/
  provider.py               # 258 lines — Memory Provider interface
  plugin.yaml
```

### Extending the Memory Engine

Implement the `MemoryProvider` base class:

1. Create a directory under `plugins/memory/`
2. Implement `sync_turn()` / `recall()` / `store()`
3. Declare in `plugin.yaml`
4. Set `memory.provider: your-provider` in config

---

## License

Apache-2.0 © [Deepleaper](https://www.deepleaper.com)
