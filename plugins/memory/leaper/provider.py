"""LeaperMemoryProvider — adapter connecting LeaperBrain to Hermes MemoryProvider."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from agent.memory_provider import MemoryProvider

# P0 fix: correct import paths (agent.leaper_*, not leaper.*)
from agent.leaper_brain import LeaperBrain
from agent.leaper_orchestrator import LeaperOrchestrator


def _run(coro):
    """Run an async coroutine from sync context, reusing loop if possible."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
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
        db_dir = os.path.join(home, "agents", agent_id)
        db_path = os.path.join(db_dir, "leaper.db")
        workspace_dir = kwargs.get("workspace_dir", os.path.join(db_dir, "workspace"))

        # P1 fix: match LeaperOrchestrator.__init__(agent_id, db_path, workspace_dir)
        # Orchestrator creates its own Brain internally, so we don't pass brain=
        self.orchestrator = LeaperOrchestrator(
            agent_id=agent_id,
            db_path=db_path,
            workspace_dir=workspace_dir,
        )

        _run(self.orchestrator.initialize())

        # Keep a reference to the brain created by orchestrator
        self.brain = self.orchestrator.brain

    def system_prompt_block(self) -> str:
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
        # P1 fix: match on_response(session_id, user_msg, assistant_msg)
        if self.orchestrator:
            sid = session_id or self._session_id
            _run(
                self.orchestrator.on_response(
                    session_id=sid,
                    user_msg=user_content,
                    assistant_msg=assistant_content,
                )
            )

    def on_session_end(self, messages: list[dict[str, Any]]) -> None:
        # P1 fix: match on_session_end(session_id)
        if self.orchestrator:
            _run(self.orchestrator.on_session_end(session_id=self._session_id))

    def on_pre_compress(self, messages: list[dict[str, Any]]) -> str:
        """Extract knowledge from messages before context compression.

        Note: LeaperOrchestrator doesn't have extract_knowledge() directly.
        Knowledge extraction happens automatically in on_response() via brain.extract_knowledge().
        For pre-compress, we do a batch extraction through the brain directly.
        """
        if not self.brain:
            return ""
        try:
            _run(self.brain.extract_knowledge(messages))
            return "leaper: extracted knowledge from compressed messages"
        except Exception:
            return ""

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """No additional tools exposed by Leaper memory provider."""
        return []

    def shutdown(self) -> None:
        if self.orchestrator:
            _run(self.orchestrator.shutdown())
            self.orchestrator = None
        self.brain = None
