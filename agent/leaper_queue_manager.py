"""Message queue with collect mode and debounce."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _SessionQueue:
    messages: list[str] = field(default_factory=list)
    last_enqueue: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class LeaperQueueManager:
    """Per-session message queue with debounce and cap.

    Collects rapid-fire messages and combines them after a debounce period.
    When the queue exceeds cap, older messages are summarized or dropped
    based on the drop policy.
    """

    def __init__(
        self,
        debounce_ms: int = 1000,
        cap: int = 20,
        drop: str = "summarize",
    ) -> None:
        self.debounce_s = debounce_ms / 1000.0
        self.cap = cap
        self.drop = drop  # 'summarize' | 'oldest' | 'newest'
        self._queues: dict[str, _SessionQueue] = defaultdict(_SessionQueue)

    async def enqueue(self, session_id: str, message: str) -> None:
        """Add a message to the session queue.

        Args:
            session_id: Session identifier.
            message: Message text to enqueue.
        """
        q = self._queues[session_id]
        async with q.lock:
            q.messages.append(message)
            q.last_enqueue = time.monotonic()

            # Apply cap
            if len(q.messages) > self.cap:
                self._apply_cap(q)

    def _apply_cap(self, q: _SessionQueue) -> None:
        """Trim queue when it exceeds cap."""
        overflow = len(q.messages) - self.cap

        if self.drop == "oldest":
            q.messages = q.messages[overflow:]
        elif self.drop == "newest":
            q.messages = q.messages[: self.cap]
        else:  # summarize
            # Combine overflow messages into a summary prefix
            old = q.messages[:overflow]
            summary = f"[{len(old)} earlier messages summarized]: " + " | ".join(
                m[:50] for m in old
            )
            q.messages = [summary] + q.messages[overflow:]

    async def drain(self, session_id: str) -> list[str]:
        """Wait for debounce period then return all collected messages.

        Waits until no new messages arrive within the debounce window,
        then drains and returns the queue.

        Args:
            session_id: Session identifier.

        Returns:
            List of collected messages (may be empty if queue was empty).
        """
        q = self._queues[session_id]

        # Wait for debounce - check if more messages arrive
        while True:
            await asyncio.sleep(self.debounce_s)
            async with q.lock:
                elapsed = time.monotonic() - q.last_enqueue
                if elapsed >= self.debounce_s:
                    # Debounce satisfied, drain
                    messages = q.messages[:]
                    q.messages.clear()
                    return messages

    async def get_combined(self, session_id: str) -> str:
        """Drain queue and combine into a single prompt string.

        Args:
            session_id: Session identifier.

        Returns:
            Combined message text. Multiple messages are joined with newlines.
        """
        messages = await self.drain(session_id)
        if not messages:
            return ""
        if len(messages) == 1:
            return messages[0]
        return "\n".join(f"[{i+1}/{len(messages)}] {m}" for i, m in enumerate(messages))

    def pending_count(self, session_id: str) -> int:
        """Return number of pending messages for a session."""
        q = self._queues.get(session_id)
        return len(q.messages) if q else 0

    def clear(self, session_id: str) -> None:
        """Clear queue for a session."""
        if session_id in self._queues:
            self._queues[session_id].messages.clear()
