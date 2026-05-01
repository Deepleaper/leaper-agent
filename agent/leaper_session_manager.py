"""Session management with isolation and timeout."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class LeaperSessionManager:
    """Manages isolated chat sessions with automatic expiration.

    Each session is stored as a JSON file keyed by agent_id and chat_id.
    Sessions expire after a configurable timeout.
    """

    def __init__(self, sessions_dir: str, timeout_hours: int = 24) -> None:
        self.sessions_dir = Path(sessions_dir)
        self.timeout_seconds = timeout_hours * 3600
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, agent_id: str, chat_id: str) -> Path:
        safe_name = f"{agent_id}_{chat_id}.json".replace("/", "_").replace("\\", "_")
        return self.sessions_dir / safe_name

    def get_or_create(self, agent_id: str, chat_id: str) -> dict:
        """Get existing session or create a new one.

        Args:
            agent_id: Agent identifier.
            chat_id: Chat/conversation identifier.

        Returns:
            Session dict with keys: id, agent_id, chat_id, messages, created_at, updated_at.
        """
        path = self._session_path(agent_id, chat_id)

        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                # Check if expired
                age = time.time() - data.get("updated_at", data.get("created_at", 0))
                if age < self.timeout_seconds:
                    return data
                else:
                    logger.info("Session expired: %s/%s", agent_id, chat_id)
                    path.unlink(missing_ok=True)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Corrupt session file %s: %s", path, e)
                path.unlink(missing_ok=True)

        # Create new session
        session = {
            "id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "chat_id": chat_id,
            "messages": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self.save(session)
        return session

    def save(self, session: dict) -> None:
        """Persist session to disk.

        Args:
            session: Session dict to save. Must contain agent_id and chat_id.
        """
        session["updated_at"] = time.time()
        path = self._session_path(session["agent_id"], session["chat_id"])
        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(path)
        except OSError as e:
            logger.error("Failed to save session %s: %s", session.get("id"), e)
            tmp_path.unlink(missing_ok=True)
            raise

    def cleanup_expired(self) -> int:
        """Delete all expired sessions.

        Returns:
            Number of sessions deleted.
        """
        deleted = 0
        now = time.time()

        for path in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                age = now - data.get("updated_at", data.get("created_at", 0))
                if age >= self.timeout_seconds:
                    path.unlink()
                    deleted += 1
            except (json.JSONDecodeError, OSError):
                path.unlink(missing_ok=True)
                deleted += 1

        if deleted:
            logger.info("Cleaned up %d expired sessions", deleted)
        return deleted

    def list_sessions(self, agent_id: str) -> list[dict]:
        """List all active sessions for an agent.

        Args:
            agent_id: Agent identifier to filter by.

        Returns:
            List of session summary dicts (id, chat_id, created_at, updated_at, message_count).
        """
        results: list[dict] = []
        now = time.time()

        for path in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("agent_id") != agent_id:
                    continue
                age = now - data.get("updated_at", data.get("created_at", 0))
                if age >= self.timeout_seconds:
                    continue
                results.append({
                    "id": data["id"],
                    "chat_id": data.get("chat_id", ""),
                    "created_at": data.get("created_at", 0),
                    "updated_at": data.get("updated_at", 0),
                    "message_count": len(data.get("messages", [])),
                })
            except (json.JSONDecodeError, OSError):
                continue

        return sorted(results, key=lambda x: x["updated_at"], reverse=True)
