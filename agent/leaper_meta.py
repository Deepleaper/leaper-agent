"""
LeaperMeta - Knowledge system self-assessment (L5).
Computes consistency, coverage, decay, and overall health metrics.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .leaper_brain import LeaperBrain

# Word pairs that suggest contradiction
_CONTRADICTION_PAIRS = [
    ("always", "never"),
    ("love", "hate"),
    ("prefer", "avoid"),
    ("best", "worst"),
    ("increase", "decrease"),
    ("yes", "no"),
    ("true", "false"),
    ("good", "bad"),
    ("like", "dislike"),
    ("support", "oppose"),
    ("agree", "disagree"),
    ("enable", "disable"),
    ("accept", "reject"),
]


class LeaperMeta:
    """Knowledge system self-assessment and maintenance."""

    def __init__(self, brain: "LeaperBrain") -> None:
        self.brain = brain

    async def compute_consistency(self, agent_id: str) -> float:
        """
        Compute consistency as % of entries without detected conflicts.
        Checks pairs of entries in the same category for contradiction keywords.
        Returns a float between 0.0 and 1.0.
        """
        cursor = await self.brain.db.execute(
            "SELECT id, content, category FROM entries WHERE agent_id = ? ORDER BY category",
            (agent_id,),
        )
        rows = await cursor.fetchall()

        if len(rows) < 2:
            return 1.0

        conflicting_ids: set[int] = set()

        # Group by category for efficient comparison
        by_category: dict[str, list[tuple[int, str]]] = {}
        for row_id, content, category in rows:
            by_category.setdefault(category or "general", []).append((row_id, content.lower()))

        for entries in by_category.values():
            # Only check within same category, limit comparisons for performance
            limit = min(len(entries), 50)
            for i in range(limit):
                for j in range(i + 1, limit):
                    id_a, text_a = entries[i]
                    id_b, text_b = entries[j]
                    if _has_contradiction(text_a, text_b):
                        conflicting_ids.add(id_a)
                        conflicting_ids.add(id_b)

        total = len(rows)
        consistent = total - len(conflicting_ids)
        return consistent / total if total > 0 else 1.0

    async def compute_coverage(self, agent_id: str) -> dict:
        """
        Count entries per category and per dimension (from profiles table).
        Returns {"categories": {cat: count}, "dimensions": {dim: count}, "total": int}.
        """
        result: dict = {"categories": {}, "dimensions": {}, "total": 0}

        # Entries by category
        cursor = await self.brain.db.execute(
            "SELECT COALESCE(category, 'uncategorized'), COUNT(*) FROM entries WHERE agent_id = ? GROUP BY category",
            (agent_id,),
        )
        for cat, count in await cursor.fetchall():
            result["categories"][cat] = count
            result["total"] += count

        # Profile dimensions
        try:
            cursor = await self.brain.db.execute(
                "SELECT dimension, COUNT(*) FROM profiles WHERE agent_id = ? GROUP BY dimension",
                (agent_id,),
            )
            for dim, count in await cursor.fetchall():
                result["dimensions"][dim] = count
        except Exception:
            # profiles table may not exist yet
            pass

        return result

    async def compute_decay_report(self, agent_id: str, half_life_days: int = 90) -> dict:
        """
        Report on stale vs fresh entries based on half-life threshold.
        Returns {"fresh": int, "stale": int, "total": int, "avg_age_days": float}.
        """
        now = time.time()
        threshold = now - (half_life_days * 86400)

        cursor = await self.brain.db.execute(
            "SELECT created_at FROM entries WHERE agent_id = ?",
            (agent_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            return {"fresh": 0, "stale": 0, "total": 0, "avg_age_days": 0.0}

        fresh = sum(1 for (ts,) in rows if ts >= threshold)
        stale = len(rows) - fresh
        avg_age = sum((now - ts) / 86400 for (ts,) in rows) / len(rows)

        return {
            "fresh": fresh,
            "stale": stale,
            "total": len(rows),
            "avg_age_days": round(avg_age, 1),
        }

    async def run_health_check(self, agent_id: str) -> dict:
        """Combine all metrics into a single health report."""
        consistency = await self.compute_consistency(agent_id)
        coverage = await self.compute_coverage(agent_id)
        decay = await self.compute_decay_report(agent_id)

        # Overall health score (weighted)
        freshness_ratio = decay["fresh"] / max(decay["total"], 1)
        health_score = (consistency * 0.4) + (freshness_ratio * 0.3) + (min(coverage["total"] / 100, 1.0) * 0.3)

        return {
            "health_score": round(health_score, 3),
            "consistency": round(consistency, 3),
            "coverage": coverage,
            "decay": decay,
            "freshness_ratio": round(freshness_ratio, 3),
        }

    async def apply_decay(self, agent_id: str, half_life_days: int = 90) -> int:
        """
        Reduce confidence of stale entries using exponential decay.
        Returns count of entries affected.
        """
        now = time.time()
        cursor = await self.brain.db.execute(
            "SELECT id, created_at, confidence FROM entries WHERE agent_id = ? AND confidence > 0.1",
            (agent_id,),
        )
        rows = await cursor.fetchall()

        count = 0
        half_life_secs = half_life_days * 86400

        for entry_id, created_at, confidence in rows:
            age_secs = now - created_at
            if age_secs <= half_life_secs:
                continue

            # Exponential decay: new_conf = confidence * 0.5^(age/half_life)
            decay_factor = math.pow(0.5, age_secs / half_life_secs)
            new_confidence = round(confidence * decay_factor, 4)
            new_confidence = max(new_confidence, 0.1)  # floor at 0.1

            if new_confidence < confidence:
                await self.brain.db.execute(
                    "UPDATE entries SET confidence = ? WHERE id = ?",
                    (new_confidence, entry_id),
                )
                count += 1

        if count > 0:
            await self.brain.db.commit()

        return count


def _has_contradiction(text_a: str, text_b: str) -> bool:
    """Check if two texts contain contradictory keyword pairs."""
    for word_pos, word_neg in _CONTRADICTION_PAIRS:
        if (word_pos in text_a and word_neg in text_b) or (word_neg in text_a and word_pos in text_b):
            # Additional check: ensure they're about the same subject (share 2+ content words)
            words_a = set(text_a.split()) - {"the", "a", "an", "is", "are", "was", "were", "i", "to", "and", "or", "of", "in", "on", "it"}
            words_b = set(text_b.split()) - {"the", "a", "an", "is", "are", "was", "were", "i", "to", "and", "or", "of", "in", "on", "it"}
            if len(words_a & words_b) >= 2:
                return True
    return False
