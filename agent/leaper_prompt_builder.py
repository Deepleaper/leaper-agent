"""Layered prompt assembly for Leaper agents."""

from __future__ import annotations

import logging
import os
import platform
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LeaperPromptBuilder:
    """Builds layered system prompts from workspace files and memory.

    Assembly order:
    1. Role template (SOUL.md)
    2. User info (USER.md)
    3. Work guide (AGENTS.md)
    4. Memory injection (recall top-5, max 2000 chars)
    5. Environment info
    6. Conversation rules
    """

    def __init__(self, workspace_dir: str, brain: Any) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.brain = brain

    async def build(self, query: str, session_id: str = "") -> str:
        """Build full system prompt for the given query.

        Args:
            query: Current user query (used for memory recall).
            session_id: Optional session ID for context.

        Returns:
            Complete system prompt string.
        """
        sections: list[str] = []

        # 1. Role template
        soul = self._load_file("SOUL.md")
        if soul:
            sections.append(soul)

        # 2. User info
        user = self._load_file("USER.md")
        if user:
            sections.append(user)

        # 3. Work guide
        agents = self._load_file("AGENTS.md")
        if agents:
            sections.append(agents)

        # 4. Memory injection
        memory_text = await self._recall_memory(query)
        if memory_text:
            sections.append(f"## Relevant Memory\n\n{memory_text}")

        # 5. Environment info
        env_info = self._build_env_info(session_id)
        sections.append(env_info)

        # 6. Conversation rules
        rules = self._load_file("RULES.md")
        if rules:
            sections.append(rules)
        else:
            sections.append(self._default_rules())

        return "\n\n---\n\n".join(sections)

    async def _recall_memory(self, query: str) -> str:
        """Recall relevant memories for the query.

        Args:
            query: Query to search memory for.

        Returns:
            Formatted memory text, truncated to max chars.
        """
        if not query or not self.brain:
            return ""

        try:
            results = await self.brain.recall(query, top_k=5)
            if not results:
                return ""

            parts: list[str] = []
            for item in results:
                title = item.get("title", "")
                content = item.get("content", item.get("text", ""))
                if content:
                    entry = f"- **{title}**: {content}" if title else f"- {content}"
                    parts.append(entry)

            return self._truncate("\n".join(parts), max_chars=2000)
        except Exception as e:
            logger.warning("Memory recall failed: %s", e)
            return ""

    def _build_env_info(self, session_id: str = "") -> str:
        """Build environment context section."""
        lines = [
            "## Environment",
            f"- OS: {platform.system()} {platform.release()}",
            f"- Python: {platform.python_version()}",
            f"- Workspace: {self.workspace_dir}",
            f"- Time: {time.strftime('%Y-%m-%d %H:%M %Z')}",
        ]
        if session_id:
            lines.append(f"- Session: {session_id}")
        return "\n".join(lines)

    def _load_file(self, filename: str) -> str:
        """Load a workspace file with graceful fallback.

        Args:
            filename: File name relative to workspace directory.

        Returns:
            File content as string, or empty string if not found.
        """
        path = self.workspace_dir / filename
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8")
                return content.strip()
        except OSError as e:
            logger.warning("Failed to load %s: %s", filename, e)
        return ""

    def _truncate(self, text: str, max_chars: int = 2000) -> str:
        """Truncate text to max_chars, adding ellipsis if truncated.

        Args:
            text: Text to truncate.
            max_chars: Maximum character length.

        Returns:
            Truncated text.
        """
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 20] + "\n... [truncated]"

    @staticmethod
    def _default_rules() -> str:
        return (
            "## Conversation Rules\n\n"
            "- Be concise and direct\n"
            "- Use structured output for complex answers\n"
            "- Admit uncertainty rather than guess\n"
            "- Ask clarifying questions when needed"
        )
