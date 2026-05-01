"""
LeaperProfile - Multi-dimensional user profile system (L4).
Maintains personality, preference, expertise, and context dimensions.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .leaper_brain import LeaperBrain

DIMENSIONS = ("personality", "preference", "expertise", "context")

# Keywords that suggest profile-relevant content per dimension
_INFERENCE_KEYWORDS = {
    "personality": ["i am", "i'm", "my style", "i tend to", "i prefer to", "i always", "i never"],
    "preference": ["i like", "i prefer", "i want", "i hate", "i don't like", "favorite", "i love"],
    "expertise": ["i work on", "i specialize", "my expertise", "i know", "years of experience", "i built", "i develop"],
    "context": ["i live in", "my role", "my company", "i'm based", "my team", "currently working on"],
}


class LeaperProfile:
    """Multi-dimensional user profile backed by the brain's DB."""

    def __init__(self, brain: "LeaperBrain") -> None:
        self.brain = brain

    async def _ensure_table(self) -> None:
        async with self.brain.db.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                dimension TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.8,
                evidence_ids TEXT DEFAULT '[]',
                updated_at REAL NOT NULL,
                UNIQUE(agent_id, dimension, key)
            )
            """
        ):
            pass
        await self.brain.db.commit()

    async def update_profile(
        self,
        agent_id: str,
        dimension: str,
        key: str,
        value: str,
        confidence: float = 0.8,
        evidence_ids: list | None = None,
    ) -> None:
        """Insert or update a profile fact."""
        if dimension not in DIMENSIONS:
            raise ValueError(f"Invalid dimension: {dimension}. Must be one of {DIMENSIONS}")

        await self._ensure_table()
        evidence_json = json.dumps(evidence_ids or [])
        now = time.time()

        await self.brain.db.execute(
            """
            INSERT INTO profiles (agent_id, dimension, key, value, confidence, evidence_ids, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, dimension, key) DO UPDATE SET
                value = excluded.value,
                confidence = excluded.confidence,
                evidence_ids = excluded.evidence_ids,
                updated_at = excluded.updated_at
            """,
            (agent_id, dimension, key, value, confidence, evidence_json, now),
        )
        await self.brain.db.commit()

    async def get_profile(self, agent_id: str, dimension: str | None = None) -> list[dict]:
        """Retrieve profile entries, optionally filtered by dimension."""
        await self._ensure_table()

        if dimension:
            cursor = await self.brain.db.execute(
                "SELECT dimension, key, value, confidence, evidence_ids, updated_at FROM profiles WHERE agent_id = ? AND dimension = ? ORDER BY confidence DESC",
                (agent_id, dimension),
            )
        else:
            cursor = await self.brain.db.execute(
                "SELECT dimension, key, value, confidence, evidence_ids, updated_at FROM profiles WHERE agent_id = ? ORDER BY dimension, confidence DESC",
                (agent_id,),
            )

        rows = await cursor.fetchall()
        return [
            {
                "dimension": r[0],
                "key": r[1],
                "value": r[2],
                "confidence": r[3],
                "evidence_ids": json.loads(r[4]),
                "updated_at": r[5],
            }
            for r in rows
        ]

    async def get_profile_summary(self, agent_id: str) -> str:
        """Generate a human-readable profile summary."""
        entries = await self.get_profile(agent_id)
        if not entries:
            return f"No profile data for agent '{agent_id}'."

        lines: list[str] = [f"## Profile: {agent_id}\n"]
        by_dim: dict[str, list[dict]] = {}
        for e in entries:
            by_dim.setdefault(e["dimension"], []).append(e)

        for dim in DIMENSIONS:
            items = by_dim.get(dim, [])
            if not items:
                continue
            lines.append(f"### {dim.capitalize()}")
            for item in items:
                conf_bar = "●" * int(item["confidence"] * 5) + "○" * (5 - int(item["confidence"] * 5))
                lines.append(f"- **{item['key']}**: {item['value']} [{conf_bar}]")
            lines.append("")

        return "\n".join(lines)

    async def infer_from_entries(self, agent_id: str) -> int:
        """Scan brain entries to extract profile facts. Returns count of updates."""
        await self._ensure_table()

        cursor = await self.brain.db.execute(
            "SELECT id, content, category FROM entries WHERE agent_id = ? ORDER BY created_at DESC LIMIT 200",
            (agent_id,),
        )
        rows = await cursor.fetchall()

        count = 0
        for entry_id, content, category in rows:
            content_lower = content.lower()
            for dimension, keywords in _INFERENCE_KEYWORDS.items():
                for kw in keywords:
                    idx = content_lower.find(kw)
                    if idx == -1:
                        continue
                    # Extract the sentence containing the keyword
                    start = max(0, content_lower.rfind(".", 0, idx) + 1)
                    end = content_lower.find(".", idx)
                    if end == -1:
                        end = min(len(content), idx + 120)
                    sentence = content[start:end].strip()
                    if len(sentence) < 5:
                        continue

                    # Use keyword + first few words as the key
                    key_words = sentence.split()[:5]
                    key = "_".join(w.lower().strip(".,!?") for w in key_words if w.isalnum())
                    if not key:
                        continue

                    await self.update_profile(
                        agent_id=agent_id,
                        dimension=dimension,
                        key=key,
                        value=sentence,
                        confidence=0.6,
                        evidence_ids=[entry_id],
                    )
                    count += 1
                    break  # one match per dimension per entry is enough

        return count
