# UPSTREAM_SYNC.md — Hermes Upstream Sync Status

**Last updated**: 2026-05-04
**Upstream**: `https://github.com/NousResearch/hermes-agent.git` (private, fetch failed)
**Current base**: Hermes v0.11.x (estimated)

---

## Hermes v0.12.0 (2026-04-30) — Pending Sync

The following features were announced in v0.12.0 and need to be evaluated for integration:

| # | Feature | Impact on Leaper | Status |
|---|---------|-----------------|--------|
| 1 | **Autonomous Curator** — auto skill scoring/pruning/merging | May affect plugin discovery; review MemoryProvider interface changes | ⏳ Pending |
| 2 | **Self-improvement loop upgrade** — rubric-based review, active-update biased | Check if MemoryProvider hooks changed | ⏳ Pending |
| 3 | **4 new inference providers** (incl. LM Studio first-class) | No direct impact on memory plugin | ℹ️ Informational |
| 4 | **18+19 messaging platforms** (incl. Teams, QQBot) | No direct impact | ℹ️ Informational |
| 5 | **ComfyUI + TouchDesigner-MCP** built-in | No direct impact | ℹ️ Informational |
| 6 | **TUI cold start -57%** | No direct impact | ℹ️ Informational |

## Action Items

1. **When upstream becomes accessible**: `git fetch upstream && git diff upstream/main --stat` to assess divergence
2. **Priority review**: Items 1 & 2 may change the MemoryProvider base class — verify our `provider.py` still conforms
3. **README update**: Mention Hermes v0.12.0 compatibility once synced

## Local Fixes Applied (2026-05-04)

- **P0 fix**: `plugins/memory/leaper/provider.py` — corrected import paths (`agent.leaper_brain`, `agent.leaper_orchestrator`)
- **P1 fix**: `plugins/memory/leaper/provider.py` — aligned method signatures with `LeaperOrchestrator` actual interface:
  - `__init__`: use `(agent_id, db_path, workspace_dir)` instead of `(brain, agent_id, session_id)`
  - `sync_turn` → `on_response(session_id, user_msg, assistant_msg)`
  - `on_session_end` → `on_session_end(session_id)` instead of `(messages)`
  - `on_pre_compress` → direct `brain.extract_knowledge()` call (orchestrator lacks this method)
