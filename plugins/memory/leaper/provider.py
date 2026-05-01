"""LeaperMemoryProvider — adapter connecting LeaperBrain to Hermes MemoryProvider."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from agent.memory_provider import MemoryProvider

# Leaper core imports (expected in the same package tree)
from leaper.brain import LeaperBrain
from leaper.orchestrator import LeaperOrchestrator


def _run(coro):
    """Run an async coroutine from sync context, reusing loop if possible."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside a loop — schedule and block (threaded fallback)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class LeaperMemoryProvider(MemoryProvider):
    """Hermes-compatible memory provider backed by LeaperBrain."""

    def __init__(self) -> None:
        self.brain: LeaperBrain | None = None
        self.orchestrator: LeaperOrchestrator | None = None
        self._session_id: str = ""

    # ── MemoryProvider interface ────────────────────────────

    def name(self) -> str:
        return "leaper"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._session_id = session_id

        # Resolve paths
        home = os.environ.get("HERMES_HOME") or str(Path.home() / ".leaper")
        agent_id = kwargs.get("agent_id", os.environ.get("LEAPER_AGENT_ID", "default"))
        db_path = os.path.join(home, "agents", agent_id, "leaper.db")

        self.brain = LeaperBrain(db_path=db_path, agent_id=agent_id)
        self.orchestrator = LeaperOrchestrator(
            brain=self.brain,
            agent_id=agent_id,
            session_id=session_id,
        )

        _run(self.brain.initialize())
        _run(self.orchestrator.initialize())

    def system_prompt_block(self) -> str:
        # Memory is injected via prefetch, not system prompt
        return ""

    def prefetch(self, query: str, session_id: str = "") -> str:
        if not self.brain:
            return ""

        MAX_CHARS = 2000
        results = _run(self.brain.recall(query, limit=5))
        if not results:
            return ""

        lines: list[str] = ["[Leaper Memory Context]"]
        total = len(lines[0])
        for r in results:
            content = r.get("content", "") if isinstance(r, dict) else str(r)
            entry = f"- {content}"
            if total + len(entry) + 1 > MAX_CHARS:
                break
            lines.append(entry)
            total += len(entry) + 1

        return "\n".join(lines)

    def sync_turn(
        self, user_content: str, assistant_content: str, session_id: str = ""
    ) -> None:
        if self.orchestrator:
            _run(
                self.orchestrator.on_response(
                    user_content=user_content,
                    assistant_content=assistant_content,
                )
            )

    def on_session_end(self, messages: list[dict[str, Any]]) -> None:
        if self.orchestrator:
            _run(self.orchestrator.on_session_end(messages=messages))

    def on_pre_compress(self, messages: list[dict[str, Any]]) -> str:
        """Extract knowledge from messages before context compression."""
        if not self.orchestrator:
            return ""
        return _run(self.orchestrator.extract_knowledge(messages=messages))

    def shutdown(self) -> None:
        if self.orchestrator:
            _run(self.orchestrator.shutdown())
            self.orchestrator = None
        self.brain = None
