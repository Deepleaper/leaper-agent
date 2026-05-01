"""Context Engine with auto-compression and memory extraction."""

from __future__ import annotations

import logging
from typing import Any

from agent.context_compressor import ContextCompressor

logger = logging.getLogger(__name__)


class LeaperContextEngine:
    """Manages context window usage with automatic compression.

    When token usage exceeds the configured threshold, extracts important
    knowledge to brain memory and compresses older messages into a summary.
    """

    def __init__(
        self,
        brain: Any,
        max_tokens: int = 128_000,
        compress_threshold: float = 0.7,
        compression_model: str | None = None,
    ) -> None:
        self.brain = brain
        self.max_tokens = max_tokens
        self.compress_threshold = compress_threshold
        self.compression_model = compression_model
        self._current_tokens = 0
        self._compressor = ContextCompressor(model=compression_model)

    @property
    def token_budget(self) -> int:
        return int(self.max_tokens * self.compress_threshold)

    def update_from_response(self, usage: dict[str, int]) -> None:
        """Update token tracking from an LLM response usage dict.

        Args:
            usage: Dict with 'prompt_tokens' and/or 'total_tokens' keys.
        """
        self._current_tokens = usage.get("prompt_tokens", usage.get("total_tokens", self._current_tokens))

    def should_compress(self, prompt_tokens: int | None = None) -> bool:
        """Check if context compression is needed.

        Args:
            prompt_tokens: Override current token count. If None, uses tracked value.

        Returns:
            True if token usage exceeds threshold.
        """
        tokens = prompt_tokens if prompt_tokens is not None else self._current_tokens
        return tokens >= self.token_budget

    async def pre_compress_save(self, messages: list[dict]) -> None:
        """Extract and save important knowledge before compression.

        Scans messages for extractable knowledge (decisions, facts, preferences)
        and persists them to brain memory.

        Args:
            messages: Conversation messages about to be compressed.
        """
        if not messages:
            return

        # Build extraction content from messages
        content_parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            text = msg.get("content", "")
            if text and role in ("user", "assistant"):
                content_parts.append(f"[{role}]: {text}")

        if not content_parts:
            return

        combined = "\n".join(content_parts[-20:])  # Last 20 messages max

        try:
            await self.brain.extract_and_save(combined)
            logger.info("Pre-compression memory extraction completed (%d messages)", len(content_parts))
        except Exception as e:
            logger.warning("Memory extraction failed (non-fatal): %s", e)

    async def compress(
        self,
        messages: list[dict],
        focus_topic: str | None = None,
    ) -> tuple[str, list[dict]]:
        """Compress older messages into a summary, keeping recent ones.

        Splits messages into old (to compress) and recent (to keep).
        Generates a summary of old messages and returns it with remaining messages.

        Args:
            messages: Full conversation history.
            focus_topic: Optional topic to emphasize in summary.

        Returns:
            Tuple of (summary_text, remaining_messages).
        """
        if len(messages) <= 4:
            return "", messages

        # Save knowledge before compressing
        await self.pre_compress_save(messages)

        # Keep the last 25% of messages (minimum 2)
        keep_count = max(2, len(messages) // 4)
        old_messages = messages[:-keep_count]
        remaining = messages[-keep_count:]

        # Build text for compression
        text_parts: list[str] = []
        for msg in old_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if content:
                text_parts.append(f"[{role}]: {content}")

        raw_text = "\n".join(text_parts)

        # Use compressor to generate summary
        try:
            summary = await self._compressor.compress(
                raw_text,
                focus=focus_topic,
                max_output_tokens=1000,
            )
        except Exception as e:
            logger.error("Compression failed: %s", e)
            # Fallback: simple truncation
            summary = raw_text[:2000] + "\n... [truncated due to compression error]"

        self._current_tokens = 0  # Reset after compression
        logger.info(
            "Compressed %d messages into summary (%d chars), keeping %d messages",
            len(old_messages),
            len(summary),
            len(remaining),
        )

        return summary, remaining
