"""
Leaper Evolution Engine v2.0
Orthogonal knowledge evolution for DeepBrain memory.
L1: Extract → L2: Consolidate → L3: Skill → L4: Profile → L5: Meta
"""

from __future__ import annotations

import re
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING
from collections import defaultdict

import aiosqlite

if TYPE_CHECKING:
    from .leaper_brain import LeaperBrain

logger = logging.getLogger(__name__)


class LeaperEvolution:
    """Orthogonal evolution engine that matures knowledge through 5 levels."""

    def __init__(self, brain: "LeaperBrain") -> None:
        self.brain = brain

    # ─── L1: Extract ────────────────────────────────────────────────────

    async def evolve_l1_extract(self, conversation: list[dict]) -> list[dict]:
        """Extract structured knowledge entries from a conversation.

        Each message in conversation: {"role": str, "content": str, "timestamp"?: str}
        Returns list of extracted entries that passed the 4-Gate filter.
        """
        extracted: list[dict] = []

        for msg in conversation:
            content = msg.get("content", "").strip()
            if not content or msg.get("role") == "system":
                continue

            entries = self._parse_knowledge(content, msg.get("role", "user"))
            for entry in entries:
                # Apply 4-Gate filter from brain
                if await self._passes_4gate(entry):
                    entry["id"] = str(uuid.uuid4())
                    entry["created_at"] = datetime.now(timezone.utc).isoformat()
                    entry["status"] = "active"
                    entry["access_count"] = 0
                    entry["source"] = "conversation"
                    extracted.append(entry)

        # Persist extracted entries
        if extracted:
            await self._store_entries(extracted)

        logger.info(f"L1 Extract: {len(extracted)} entries from {len(conversation)} messages")
        return extracted

    def _parse_knowledge(self, content: str, role: str) -> list[dict]:
        """Parse text into candidate knowledge entries."""
        entries: list[dict] = []

        sentences = re.split(r"[。！？\n.!?]+", content)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= 4]

        for sentence in sentences:
            category = self._classify_category(sentence, role)
            confidence = self._estimate_confidence(sentence, role)

            if confidence < 0.3:
                continue

            entries.append({
                "content": sentence,
                "category": category,
                "confidence": confidence,
            })

        return entries

    def _classify_category(self, text: str, role: str) -> str:
        """Classify text into: fact, preference, event, skill."""
        preference_signals = ["喜欢", "偏好", "prefer", "love", "hate", "讨厌", "习惯", "倾向", "想要"]
        event_signals = ["昨天", "今天", "明天", "上周", "下周", "刚才", "yesterday", "today", "tomorrow", "happened"]
        skill_signals = ["步骤", "方法", "如何", "怎么", "how to", "always", "never", "规则", "流程", "should"]

        text_lower = text.lower()

        if any(s in text_lower for s in preference_signals):
            return "preference"
        if any(s in text_lower for s in event_signals):
            return "event"
        if any(s in text_lower for s in skill_signals):
            return "skill"
        return "fact"

    def _estimate_confidence(self, text: str, role: str) -> float:
        """Estimate confidence score for an extracted entry."""
        confidence = 0.6

        # User statements are higher confidence than assistant inferences
        if role == "user":
            confidence += 0.15

        # Hedging language reduces confidence
        hedges = ["可能", "也许", "maybe", "perhaps", "might", "不确定", "probably", "大概"]
        if any(h in text.lower() for h in hedges):
            confidence -= 0.2

        # Definitive language increases confidence
        definites = ["一定", "肯定", "always", "definitely", "确定", "必须"]
        if any(d in text.lower() for d in definites):
            confidence += 0.1

        return max(0.0, min(1.0, confidence))

    async def _passes_4gate(self, entry: dict) -> bool:
        """Apply brain's 4-Gate filter: Relevance, Novelty, Consistency, Actionability."""
        # Gate 1: Relevance — minimum content length
        if len(entry["content"]) < 4:
            return False

        # Gate 2: Novelty — check for duplicates
        existing = await self._find_similar_entries(entry["content"], threshold=0.85)
        if existing:
            return False

        # Gate 3: Consistency — check for direct contradictions (soft gate)
        # Contradictions lower confidence but don't block — record as transitions
        conflicts = await self._find_conflicts(entry)
        if conflicts:
            entry["confidence"] = max(0.3, entry["confidence"] - 0.2)
            entry["has_conflicts"] = True
            # Record temporal transitions for each superseded entry
            for old_entry in conflicts:
                await self.brain.record_transition(
                    old_entry=old_entry,
                    new_entry=entry,
                    transition_type="supersede",
                )

        # Gate 4: Actionability — skill entries must contain actionable content
        if entry["category"] == "skill" and len(entry["content"]) < 10:
            return False

        return True

    # ─── L2: Consolidate ────────────────────────────────────────────────

    async def evolve_l2_consolidate(self) -> list[dict]:
        """Cluster similar active entries and merge them into consolidated entries."""
        consolidated: list[dict] = []

        async with aiosqlite.connect(self.brain.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM entries WHERE status = 'active' ORDER BY category, created_at"
            )
            rows = await cursor.fetchall()

        if not rows:
            return consolidated

        entries = [dict(r) for r in rows]

        # Group by category
        by_category: dict[str, list[dict]] = defaultdict(list)
        for e in entries:
            by_category[e["category"]].append(e)

        for category, group in by_category.items():
            clusters = self._cluster_entries(group, threshold=0.6)

            for cluster in clusters:
                if len(cluster) < 2:
                    continue

                merged = self._merge_cluster(cluster, category)
                merged["id"] = str(uuid.uuid4())
                merged["created_at"] = datetime.now(timezone.utc).isoformat()
                merged["status"] = "active"
                merged["source"] = "consolidation"
                merged["source_ids"] = json.dumps([e["id"] for e in cluster])
                merged["access_count"] = sum(e.get("access_count", 0) for e in cluster)

                consolidated.append(merged)

                # Record consolidation transitions
                for original in cluster:
                    await self.brain.record_transition(
                        old_entry=original,
                        new_entry=merged,
                        transition_type="consolidate",
                    )

                # Mark originals
                async with aiosqlite.connect(self.brain.db_path) as db:
                    ids = [e["id"] for e in cluster]
                    placeholders = ",".join("?" * len(ids))
                    await db.execute(
                        f"UPDATE entries SET status = 'consolidated' WHERE id IN ({placeholders})",
                        ids,
                    )
                    await db.commit()

        # Store consolidated entries
        if consolidated:
            await self._store_entries(consolidated)

        logger.info(f"L2 Consolidate: {len(consolidated)} merged entries")
        return consolidated

    def _cluster_entries(self, entries: list[dict], threshold: float) -> list[list[dict]]:
        """Cluster entries by keyword similarity using greedy approach."""
        used = set()
        clusters: list[list[dict]] = []

        for i, entry_a in enumerate(entries):
            if i in used:
                continue
            cluster = [entry_a]
            used.add(i)

            for j in range(i + 1, len(entries)):
                if j in used:
                    continue
                sim = self._keyword_similarity(entry_a["content"], entries[j]["content"])
                if sim >= threshold:
                    cluster.append(entries[j])
                    used.add(j)

            clusters.append(cluster)

        return clusters

    def _merge_cluster(self, cluster: list[dict], category: str) -> dict:
        """Merge a cluster of entries into a single consolidated entry."""
        # Pick the longest content as base, append unique info from others
        cluster_sorted = sorted(cluster, key=lambda e: len(e["content"]), reverse=True)
        base = cluster_sorted[0]["content"]

        # Average confidence, capped at 0.95
        avg_confidence = sum(e.get("confidence", 0.5) for e in cluster) / len(cluster)
        confidence = min(0.95, avg_confidence + 0.05 * (len(cluster) - 1))

        return {
            "content": base,
            "category": category,
            "confidence": confidence,
        }

    # ─── L3: Skill Promotion ────────────────────────────────────────────

    async def evolve_l3_skill(self) -> list[dict]:
        """Promote L2 entries to 'skill' type if access_count >= 2 and confidence >= 0.8."""
        promoted: list[dict] = []

        async with aiosqlite.connect(self.brain.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM entries
                   WHERE status = 'active'
                     AND category != 'skill'
                     AND access_count >= 2
                     AND confidence >= 0.8"""
            )
            rows = await cursor.fetchall()

            for row in rows:
                entry = dict(row)
                # Promote to skill
                await db.execute(
                    "UPDATE entries SET category = 'skill', updated_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), entry["id"]),
                )
                entry["category"] = "skill"
                promoted.append(entry)

            await db.commit()

        logger.info(f"L3 Skill: {len(promoted)} entries promoted")
        return promoted

    # ─── L4: Profile ────────────────────────────────────────────────────

    async def evolve_l4_profile(self, user_id: str) -> dict:
        """Build/update user profile across 4 dimensions from knowledge entries."""
        profile = {
            "user_id": user_id,
            "personality": [],
            "preference": [],
            "expertise": [],
            "context": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        async with aiosqlite.connect(self.brain.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM entries WHERE status = 'active' AND confidence >= 0.6"
            )
            rows = await cursor.fetchall()

        personality_signals = ["性格", "人格", "personality", "内向", "外向", "风格"]
        preference_signals = ["喜欢", "偏好", "prefer", "习惯", "倾向"]
        expertise_signals = ["擅长", "专业", "expert", "skill", "精通", "经验"]
        context_signals = ["工作", "公司", "项目", "team", "role", "职位"]

        for row in rows:
            entry = dict(row)
            content = entry["content"].lower()

            if any(s in content for s in personality_signals):
                profile["personality"].append(entry["content"])
            if any(s in content for s in preference_signals):
                profile["preference"].append(entry["content"])
            if any(s in content for s in expertise_signals):
                profile["expertise"].append(entry["content"])
            if any(s in content for s in context_signals):
                profile["context"].append(entry["content"])

        # Persist profile using the brain's profiles schema
        # (agent_id, dimension, key, value, confidence, evidence_ids, updated_at)
        now = profile["updated_at"]
        async with aiosqlite.connect(self.brain.db_path) as db:
            for dimension in ("personality", "preference", "expertise", "context"):
                items = profile[dimension]
                if not items:
                    continue
                value_json = json.dumps(items, ensure_ascii=False)
                await db.execute(
                    """INSERT INTO profiles (id, agent_id, dimension, key, value, confidence, evidence_ids, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(agent_id, dimension, key) DO UPDATE SET
                         value = excluded.value,
                         updated_at = excluded.updated_at""",
                    (
                        f"{user_id}_{dimension}",
                        user_id,
                        dimension,
                        "l4_summary",
                        value_json,
                        0.8,
                        "[]",
                        now,
                    ),
                )
            await db.commit()

        logger.info(f"L4 Profile: updated for user {user_id}")
        return profile

    # ─── L5: Meta Health ────────────────────────────────────────────────

    async def evolve_l5_meta(self) -> dict:
        """Compute knowledge base health metrics."""
        async with aiosqlite.connect(self.brain.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Total active entries
            cursor = await db.execute("SELECT * FROM entries WHERE status = 'active'")
            entries = [dict(r) for r in await cursor.fetchall()]

        total = len(entries)
        if total == 0:
            return {
                "consistency_score": 1.0,
                "coverage_score": 0.0,
                "decay_report": {"stale_count": 0, "stale_ratio": 0.0},
                "total_entries": 0,
            }

        # Consistency: entries without conflicts
        conflict_count = sum(1 for e in entries if e.get("has_conflicts") or self._has_json_field(e, "has_conflicts"))
        consistency_score = (total - conflict_count) / total

        # Coverage: how many dimensions are represented
        dimensions = {"fact", "preference", "event", "skill"}
        present = {e["category"] for e in entries if e["category"] in dimensions}
        coverage_score = len(present) / len(dimensions)

        # Decay report
        stale_entries = [e for e in entries if self._is_stale(e)]
        decay_report = {
            "stale_count": len(stale_entries),
            "stale_ratio": len(stale_entries) / total if total else 0.0,
            "stale_ids": [e["id"] for e in stale_entries[:20]],
        }

        report = {
            "consistency_score": round(consistency_score, 3),
            "coverage_score": round(coverage_score, 3),
            "decay_report": decay_report,
            "total_entries": total,
            "by_category": {cat: sum(1 for e in entries if e["category"] == cat) for cat in dimensions},
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"L5 Meta: consistency={report['consistency_score']}, coverage={report['coverage_score']}")
        return report

    def _has_json_field(self, entry: dict, field: str) -> bool:
        """Check if a JSON-stored metadata field is truthy."""
        meta = entry.get("metadata")
        if not meta:
            return False
        try:
            data = json.loads(meta) if isinstance(meta, str) else meta
            return bool(data.get(field))
        except (json.JSONDecodeError, AttributeError):
            return False

    # ─── Full Evolution ─────────────────────────────────────────────────

    async def run_full_evolution(self) -> dict:
        """Run L2→L3→L4→L5 in sequence. L1 is triggered externally per conversation."""
        summary: dict = {}

        l2 = await self.evolve_l2_consolidate()
        summary["l2_consolidated"] = len(l2)

        l3 = await self.evolve_l3_skill()
        summary["l3_promoted"] = len(l3)

        # L4 for default user
        l4 = await self.evolve_l4_profile("default")
        summary["l4_dimensions"] = {
            k: len(v) for k, v in l4.items() if isinstance(v, list)
        }

        l5 = await self.evolve_l5_meta()
        summary["l5_health"] = l5

        logger.info(f"Full evolution complete: {summary}")
        return summary

    # ─── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _keyword_similarity(text1: str, text2: str) -> float:
        """Jaccard similarity using Chinese bigrams + English words."""
        def extract_keywords(text: str) -> set[str]:
            keywords: set[str] = set()
            # English words
            eng_words = re.findall(r"[a-zA-Z]{2,}", text.lower())
            keywords.update(eng_words)
            # Chinese bigrams
            chinese = re.findall(r"[\u4e00-\u9fff]+", text)
            for segment in chinese:
                for i in range(len(segment) - 1):
                    keywords.add(segment[i : i + 2])
            return keywords

        kw1 = extract_keywords(text1)
        kw2 = extract_keywords(text2)

        if not kw1 and not kw2:
            return 0.0

        intersection = kw1 & kw2
        union = kw1 | kw2

        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _is_stale(entry: dict, half_life_days: int = 90) -> bool:
        """Check if entry has decayed past its half-life threshold."""
        created = entry.get("created_at")
        if not created:
            return False

        try:
            if isinstance(created, str):
                # Handle both Z and +00:00 formats
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            else:
                return False
        except (ValueError, TypeError):
            return False

        now = datetime.now(timezone.utc)
        age_days = (now - created_dt).days

        # Past half-life: stale if not accessed recently
        access_count = entry.get("access_count", 0)
        # Each access extends effective half-life by 30 days
        effective_half_life = half_life_days + (access_count * 30)

        return age_days > effective_half_life

    # ─── Storage Helpers ────────────────────────────────────────────────

    async def _store_entries(self, entries: list[dict]) -> None:
        """Persist entries to the database."""
        async with aiosqlite.connect(self.brain.db_path) as db:
            for entry in entries:
                metadata = {}
                if entry.get("has_conflicts"):
                    metadata["has_conflicts"] = True
                if entry.get("source"):
                    metadata["source"] = entry["source"]
                await db.execute(
                    """INSERT OR REPLACE INTO entries
                       (id, agent_id, entry_type, content, category, confidence,
                        access_count, last_accessed, source_ids, metadata,
                        created_at, updated_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry["id"],
                        self.brain.agent_id,
                        entry.get("source", "knowledge"),
                        entry["content"],
                        entry["category"],
                        entry.get("confidence", 0.5),
                        entry.get("access_count", 0),
                        None,
                        entry.get("source_ids"),
                        json.dumps(metadata, ensure_ascii=False),
                        entry.get("created_at", datetime.now(timezone.utc).isoformat()),
                        datetime.now(timezone.utc).isoformat(),
                        entry.get("status", "active"),
                    ),
                )
            await db.commit()

    async def _find_similar_entries(self, content: str, threshold: float = 0.85) -> list[dict]:
        """Find existing entries similar to the given content."""
        async with aiosqlite.connect(self.brain.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM entries WHERE status = 'active'"
            )
            rows = await cursor.fetchall()

        similar = []
        for row in rows:
            entry = dict(row)
            sim = self._keyword_similarity(content, entry["content"])
            if sim >= threshold:
                similar.append(entry)

        return similar

    async def _find_conflicts(self, entry: dict) -> list[dict]:
        """Find entries that potentially conflict with the given entry.

        Simple heuristic: same category, high similarity but containing negation.
        """
        negation_pairs = [
            ("不", ""), ("没有", "有"), ("不是", "是"),
            ("don't", "do"), ("not", ""), ("never", "always"),
        ]

        async with aiosqlite.connect(self.brain.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM entries WHERE status = 'active' AND category = ?",
                (entry["category"],),
            )
            rows = await cursor.fetchall()

        conflicts = []
        for row in rows:
            existing = dict(row)
            sim = self._keyword_similarity(entry["content"], existing["content"])
            if sim < 0.4:
                continue

            # Check for negation patterns
            for neg, pos in negation_pairs:
                if (neg in entry["content"] and pos in existing["content"]) or \
                   (pos in entry["content"] and neg in existing["content"]):
                    conflicts.append(existing)
                    break

        return conflicts
