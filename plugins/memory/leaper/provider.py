"""Leaper Memory Provider — integrates LeaperBrain into the Hermes memory system.

Wires together:
  - LeaperBrain         — SQLite + RRF hybrid search
  - EvolutionEngine     — L0-L5 self-improvement
  - LeaperOrchestrator  — turn-count and timer-based triggering
  - LeaperSeedLoader    — workspace file injection
  - Tools: brain_recall, brain_learn
"""

from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from agent.memory_provider import MemoryProvider
from agent.leaper_brain import LeaperBrain
from agent.leaper_evolution import EvolutionEngine
from agent.leaper_orchestrator import LeaperOrchestrator
from agent.leaper_seed_loader import load_workspace_files

logger = logging.getLogger(__name__)

_TOOL_RECALL = "brain_recall"
_TOOL_LEARN = "brain_learn"


class LeaperMemoryProvider(MemoryProvider):
    """Pluggable memory provider that uses LeaperBrain + full evolution engine.

    Activated by setting ``memory.provider: leaper`` in leaper.yaml / config.yaml.
    """

    @property
    def name(self) -> str:
        return "leaper"

    def __init__(self) -> None:
        self.brain: LeaperBrain | None = None
        self.evolution: EvolutionEngine | None = None
        self.orchestrator: LeaperOrchestrator | None = None
        self._lock = threading.Lock()
        self._cached_recall: str = ""
        self._workspace_prompt: str = ""
        self._db_path: str = ""
        # Bounded pool so background sync_turn calls cannot spawn unlimited threads.
        self._thread_pool = ThreadPoolExecutor(max_workers=2)

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        # Always resolve leaper_home to an absolute path under user home
        # Use hermes_constants as single source of truth (reads LEAPER_HOME > HERMES_HOME > ~/.leaper)
        try:
            from hermes_constants import get_hermes_home
            leaper_home = str(get_hermes_home())
        except ImportError:
            leaper_home = os.environ.get("LEAPER_HOME", "").strip() \
                or os.environ.get("HERMES_HOME", "").strip() \
                or str(Path.home() / ".leaper")
        leaper_home = str(Path(leaper_home).resolve())
        logger.info("LeaperMemoryProvider: leaper_home=%s, kwargs_hermes_home=%s, env_HERMES_HOME=%s",
                     leaper_home, kwargs.get("hermes_home", "N/A"), os.environ.get("HERMES_HOME", "N/A"))
        db_path = os.environ.get(
            "LEAPER_BRAIN_DB",
            str(Path(leaper_home) / "brain.db"),
        )
        db_path = str(Path(db_path).resolve())
        self._db_path = db_path

        self.brain = LeaperBrain(db_path)
        self.evolution = EvolutionEngine(brain=self.brain)
        self.orchestrator = LeaperOrchestrator(brain=self.brain, evolution=self.evolution)

        workspace = kwargs.get("workspace", "") or kwargs.get("agent_workspace", "")
        if workspace and not Path(workspace).is_absolute():
            # Relative paths are ambiguous at runtime; fall back to leaper_home
            # so seed loading always uses a predictable, user-owned directory.
            logger.warning(
                "workspace '%s' is a relative path; defaulting to leaper_home '%s'",
                workspace, leaper_home,
            )
            workspace = leaper_home
        if workspace and Path(workspace).exists():
            result = load_workspace_files(workspace, self.brain)
            self._workspace_prompt = result["system_prompt_block"]
            if result["seeded_count"] > 0:
                logger.info(
                    "LeaperMemoryProvider: seeded %d files from %s",
                    result["seeded_count"],
                    workspace,
                )

        logger.info("LeaperMemoryProvider initialized (db=%s)", db_path)

    def system_prompt_block(self) -> str:
        parts = [
            "## Leaper Brain\n"
            "You have access to a persistent knowledge store (brain_recall, brain_learn). "
            "Use brain_recall to search for relevant past knowledge before answering complex questions. "
            "Use brain_learn to store important facts, decisions, or patterns for future use.\n\n"
            "**CRITICAL**: All tool usage is invisible to the user. "
            "NEVER mention brain_recall, brain_learn, memory operations, or tool errors in your replies. "
            "Do not say things like '🧠 memory: ...', 'I saved that', 'Let me search my brain', "
            "or expose any error messages. If a tool fails, handle it silently. "
            "Act as if you naturally remember things."
        ]
        if self._workspace_prompt:
            parts.append("\n## Workspace Context\n" + self._workspace_prompt)
        return "\n\n".join(parts)

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self.evolution or not query.strip():
            return ""
        with self._lock:
            user_model_ctx = self.evolution.inject_user_model_to_prompt(min_confidence=0.5)
            recalled = self.evolution.format_recall_for_prompt(
                query, top_k=5, extra_context=user_model_ctx
            )
            self._cached_recall = recalled
        return recalled

    def sync_turn(
        self, user_content: str, assistant_content: str, *, session_id: str = ""
    ) -> None:
        """Trigger orchestrator.on_turn_complete() via the bounded thread pool."""
        if not self.orchestrator:
            return

        def _background() -> None:
            try:
                results = self.orchestrator.on_turn_complete(user_content, assistant_content)  # type: ignore[union-attr]
                logger.debug("sync_turn orchestrator results: %s", results)
            except Exception as e:
                logger.warning("sync_turn background error: %s", e)

        # Use bounded pool (max_workers=2) instead of unbounded threading.Thread
        # to prevent runaway thread creation under sustained load.
        self._thread_pool.submit(_background)

    def on_cron(self) -> dict[str, Any]:
        """Periodic trigger for L3 + L5. Call this from a scheduler every 24h."""
        if not self.orchestrator:
            return {"error": "not initialized"}
        try:
            return self.orchestrator.on_cron()
        except Exception as e:
            logger.warning("on_cron error: %s", e)
            return {"error": str(e)}

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": _TOOL_RECALL,
                "description": (
                    "Search the Leaper Brain for relevant knowledge. "
                    "Use this to recall past experiences, decisions, or learned patterns."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for in the brain",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 5)",
                            "default": 5,
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Optional namespace filter (e.g. 'workspace', 'experience', 'skill')",
                        },
                        "entry_type": {
                            "type": "string",
                            "description": "Optional type filter: 'raw', 'experience', 'skill', 'user_trait'",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": _TOOL_LEARN,
                "description": (
                    "Store new knowledge in the Leaper Brain for future recall. "
                    "Use this for important facts, user preferences, or reusable patterns."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The knowledge content to store",
                        },
                        "source": {
                            "type": "string",
                            "description": "Where this knowledge came from (e.g. 'user', 'research')",
                            "default": "agent",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace for organizing knowledge (default: 'default')",
                            "default": "default",
                        },
                    },
                    "required": ["content"],
                },
            },
        ]

    def handle_tool_call(
        self, tool_name: str, args: dict[str, Any], **kwargs
    ) -> str:
        if tool_name == _TOOL_RECALL:
            return self._handle_recall(args)
        if tool_name == _TOOL_LEARN:
            return self._handle_learn(args)
        raise NotImplementedError(f"Unknown tool: {tool_name}")

    def _handle_recall(self, args: dict[str, Any]) -> str:
        if not self.brain:
            return json.dumps({"error": "Brain not initialized"})
        query = args.get("query", "")
        top_k = int(args.get("top_k", 5))
        namespace = args.get("namespace") or None
        entry_type = args.get("entry_type") or None
        results = self.brain.recall(
            query, top_k=top_k, namespace=namespace, entry_type=entry_type
        )
        if not results:
            return json.dumps({"results": [], "message": "No matching entries found."})
        return json.dumps({
            "results": [
                {
                    "content": r["content"][:400],
                    "source": r["source"],
                    "namespace": r["namespace"],
                    "entry_type": r.get("entry_type", "raw"),
                    "score": round(r["score"], 4),
                }
                for r in results
            ],
            "total": len(results),
        })

    def _handle_learn(self, args: dict[str, Any]) -> str:
        if not self.brain:
            return json.dumps({"error": "Brain not initialized"})
        content = args.get("content", "").strip()
        if not content:
            return json.dumps({"error": "content cannot be empty"})
        if len(content) < 15:
            return json.dumps({"error": "content too short, need at least 15 chars"})
        # Dedup: check if very similar content already exists
        existing = self.brain.recall(content, top_k=1)
        if existing:
            from difflib import SequenceMatcher
            sim = SequenceMatcher(None, content.lower(), existing[0].get("content", "").lower()).ratio()
            if sim > 0.85:
                return json.dumps({"stored": False, "reason": "duplicate", "similar_id": existing[0].get("id", "")})
        source = args.get("source", "agent")
        namespace = args.get("namespace", "default")
        entry_id = self.brain.learn(
            content=content, source=source, namespace=namespace
        )
        return json.dumps({"stored": True, "id": entry_id, "namespace": namespace})

    def get_config_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "key": "db_path",
                "description": "Path to the SQLite brain database",
                "required": False,
                "default": "~/.leaper/brain.db",
                "env_var": "LEAPER_BRAIN_DB",
            }
        ]

    def shutdown(self) -> None:
        self._thread_pool.shutdown(wait=False)
        if self.brain:
            self.brain.close()
            logger.info("LeaperMemoryProvider: brain closed")
