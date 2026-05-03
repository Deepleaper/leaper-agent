"""
LeaperBrain - DeepBrain Memory Engine for Leaper Agent v2.0

Async SQLite-backed knowledge store with 4-Gate extraction and BM25+MMR recall.
"""

from __future__ import annotations

import json
import math
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import aiosqlite

TZ_UTC = timezone.utc


# ---------------------------------------------------------------------------
# Tokenisation helpers
# ---------------------------------------------------------------------------

_EN_WORD_RE = re.compile(r"[a-zA-Z0-9]+")
_ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_STOPWORDS = frozenset(
    {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
     "have", "has", "had", "do", "does", "did", "will", "would", "shall",
     "should", "may", "might", "must", "can", "could", "of", "in", "to",
     "for", "with", "on", "at", "from", "by", "as", "it", "its", "this",
     "that", "and", "or", "but", "not", "no", "if", "so", "up", "out",
     "about", "into", "over", "after", "than", "也", "的", "了", "在",
     "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
     "上", "这", "他", "她", "它", "们", "个", "中", "大", "为"}
)


def tokenize(text: str) -> list[str]:
    """Extract keywords: English words (lowered) + Chinese char bigrams."""
    tokens: list[str] = []
    # English words
    for m in _EN_WORD_RE.finditer(text):
        w = m.group().lower()
        if w not in _STOPWORDS and len(w) > 1:
            tokens.append(w)
    # Chinese bigrams
    chars = [c for c in text if _ZH_CHAR_RE.match(c)]
    for i in range(len(chars) - 1):
        bg = chars[i] + chars[i + 1]
        if bg not in _STOPWORDS:
            tokens.append(bg)
    # single Chinese chars that didn't form bigrams (for short text)
    if len(chars) == 1 and chars[0] not in _STOPWORDS:
        tokens.append(chars[0])
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Entity Extraction (lightweight, no external deps)
# ---------------------------------------------------------------------------

_ENTITY_PATTERNS = [
    # CamelCase or PascalCase (e.g., LangGraph, CrewAI, DeepBrain)
    re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]*)+)\b"),
    # ALL CAPS acronyms 2-6 chars (e.g., API, SDK, MRD)
    re.compile(r"\b([A-Z]{2,6})\b"),
    # Chinese proper nouns preceded by markers (rough heuristic)
    re.compile(r"(?:叫|是|用|即|如|：)([^\s，。、]{2,6})"),
    # @-mentions or quoted names
    re.compile(r"[「\"']([^「\"']{2,20})[」\"']"),
]


def extract_entities(text: str) -> set[str]:
    """Extract lightweight named entities from text for retrieval boosting."""
    entities: set[str] = set()
    for pat in _ENTITY_PATTERNS:
        for m in pat.finditer(text):
            ent = m.group(1) if pat.groups else m.group(0)
            # Filter out common English words that happen to be uppercase
            if ent.isupper() and len(ent) <= 1:
                continue
            entities.add(ent.lower())
    return entities


def _now_iso() -> str:
    return datetime.now(TZ_UTC).isoformat()


# ---------------------------------------------------------------------------
# 4-Gate Knowledge Filters
# ---------------------------------------------------------------------------

def relevance_gate(content: str, context: str) -> float:
    """Score 0-1: how relevant content is to the conversation context."""
    c_tok = set(tokenize(content))
    x_tok = set(tokenize(context))
    if not c_tok:
        return 0.0
    overlap = len(c_tok & x_tok)
    # At least some overlap means relevant
    ratio = overlap / max(len(c_tok), 1)
    # Boost if content is substantial
    length_bonus = min(len(content) / 200, 0.3)
    return min(ratio + length_bonus, 1.0)


def novelty_gate(content: str, existing_entries: list[dict]) -> float:
    """Score 0-1: how novel this content is vs existing knowledge."""
    if not existing_entries:
        return 1.0
    c_tok = set(tokenize(content))
    max_sim = 0.0
    for entry in existing_entries:
        e_tok = set(tokenize(entry.get("content", "")))
        sim = _jaccard(c_tok, e_tok)
        if sim > max_sim:
            max_sim = sim
    return 1.0 - max_sim


def confidence_gate(content: str) -> float:
    """Score 0-1: heuristic confidence based on content quality signals."""
    score = 0.5
    # Longer, more detailed content = higher confidence
    if len(content) > 100:
        score += 0.15
    if len(content) > 300:
        score += 0.1
    # Contains numbers / data points
    if re.search(r"\d+", content):
        score += 0.1
    # Hedging language lowers confidence
    hedges = ["maybe", "perhaps", "might", "不确定", "可能", "也许", "似乎"]
    if any(h in content.lower() for h in hedges):
        score -= 0.15
    # Assertion keywords boost
    assertions = ["确认", "confirmed", "verified", "实测", "proven"]
    if any(a in content.lower() for a in assertions):
        score += 0.15
    return max(0.1, min(score, 1.0))


def consistency_gate(content: str, existing_entries: list[dict]) -> float:
    """Score 0-1: does content conflict with existing knowledge?
    1.0 = fully consistent, 0.0 = strong contradiction detected."""
    if not existing_entries:
        return 1.0
    c_tok = set(tokenize(content))
    # Simple heuristic: check for negation patterns against similar entries
    negation_words = {"not", "no", "never", "don't", "doesn't", "didn't",
                      "won't", "不", "没", "未", "非", "无", "别"}
    c_has_neg = bool(negation_words & set(content.lower().split()))
    for entry in existing_entries:
        e_tok = set(tokenize(entry.get("content", "")))
        sim = _jaccard(c_tok, e_tok)
        if sim < 0.3:
            continue
        # High similarity + different negation polarity = possible conflict
        e_has_neg = bool(negation_words & set(entry.get("content", "").lower().split()))
        if sim > 0.5 and c_has_neg != e_has_neg:
            return max(0.2, 1.0 - sim)
    return 1.0


# ---------------------------------------------------------------------------
# LeaperBrain
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    entry_type TEXT,
    content TEXT,
    category TEXT,
    confidence REAL DEFAULT 0.8,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    source_ids TEXT,
    metadata TEXT,
    created_at TEXT,
    updated_at TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    session_id TEXT,
    role TEXT,
    content TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    dimension TEXT,
    key TEXT,
    value TEXT,
    confidence REAL DEFAULT 0.8,
    evidence_ids TEXT,
    updated_at TEXT,
    UNIQUE(agent_id, dimension, key)
);

CREATE TABLE IF NOT EXISTS meta (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    metric TEXT,
    value TEXT,
    computed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_entries_agent ON entries(agent_id);
CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(status);
CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category);
CREATE INDEX IF NOT EXISTS idx_messages_agent ON messages(agent_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_profiles_agent ON profiles(agent_id);
CREATE INDEX IF NOT EXISTS idx_profiles_dimension ON profiles(dimension);
CREATE INDEX IF NOT EXISTS idx_meta_agent ON meta(agent_id);

CREATE TABLE IF NOT EXISTS transitions (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    entry_id_old TEXT,
    entry_id_new TEXT,
    category TEXT,
    old_content TEXT,
    new_content TEXT,
    transition_type TEXT DEFAULT 'update',
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_transitions_agent ON transitions(agent_id);
CREATE INDEX IF NOT EXISTS idx_transitions_category ON transitions(category);
"""

# Minimum gate thresholds for knowledge extraction
_GATE_THRESHOLDS = {
    "relevance": 0.15,
    "novelty": 0.25,
    "confidence": 0.3,
    "consistency": 0.3,
}


class LeaperBrain:
    """Async knowledge engine backed by SQLite via aiosqlite."""

    def __init__(self, db_path: str, agent_id: str) -> None:
        self.db_path = db_path
        self.agent_id = agent_id
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open DB and create tables + indexes."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA_SQL)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("LeaperBrain not initialized. Call initialize() first.")
        return self._db

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def store_message(self, session_id: str, role: str, content: str) -> str:
        msg_id = uuid.uuid4().hex
        now = _now_iso()
        await self.db.execute(
            "INSERT INTO messages (id, agent_id, session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, self.agent_id, session_id, role, content, now),
        )
        await self.db.commit()
        return msg_id

    # ------------------------------------------------------------------
    # Entries CRUD
    # ------------------------------------------------------------------

    async def store_entry(
        self,
        entry_type: str,
        content: str,
        category: str = "",
        confidence: float = 0.8,
        source_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        entry_id = uuid.uuid4().hex
        now = _now_iso()
        await self.db.execute(
            "INSERT INTO entries "
            "(id, agent_id, entry_type, content, category, confidence, "
            "access_count, last_accessed, source_ids, metadata, created_at, updated_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 'active')",
            (
                entry_id,
                self.agent_id,
                entry_type,
                content,
                category,
                confidence,
                now,
                json.dumps(source_ids or [], ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False),
                now,
                now,
            ),
        )
        await self.db.commit()
        return entry_id

    async def get_entries(
        self,
        agent_id: str | None = None,
        entry_type: str | None = None,
        status: str = "active",
        limit: int = 50,
    ) -> list[dict]:
        clauses = ["status = ?"]
        params: list[Any] = [status]
        aid = agent_id or self.agent_id
        clauses.append("agent_id = ?")
        params.append(aid)
        if entry_type:
            clauses.append("entry_type = ?")
            params.append(entry_type)
        params.append(limit)
        sql = (
            "SELECT * FROM entries WHERE "
            + " AND ".join(clauses)
            + " ORDER BY updated_at DESC LIMIT ?"
        )
        async with self.db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def update_entry_status(self, entry_id: str, status: str) -> None:
        await self.db.execute(
            "UPDATE entries SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now_iso(), entry_id),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Temporal Transitions
    # ------------------------------------------------------------------

    async def record_transition(
        self,
        old_entry: dict,
        new_entry: dict,
        transition_type: str = "update",
    ) -> str:
        """Record a knowledge transition (fact changed over time).

        Inspired by Zep's temporal knowledge graph — tracks what was true
        before and what replaced it, enabling temporal reasoning queries.
        """
        trans_id = uuid.uuid4().hex
        now = _now_iso()
        await self.db.execute(
            "INSERT INTO transitions "
            "(id, agent_id, entry_id_old, entry_id_new, category, "
            "old_content, new_content, transition_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trans_id,
                self.agent_id,
                old_entry.get("id", ""),
                new_entry.get("id", ""),
                old_entry.get("category", new_entry.get("category", "")),
                old_entry.get("content", ""),
                new_entry.get("content", ""),
                transition_type,
                now,
            ),
        )
        await self.db.commit()
        return trans_id

    async def get_transitions(
        self, category: str | None = None, limit: int = 20
    ) -> list[dict]:
        """Retrieve recent transitions, optionally filtered by category."""
        clauses = ["agent_id = ?"]
        params: list[Any] = [self.agent_id]
        if category:
            clauses.append("category = ?")
            params.append(category)
        params.append(limit)
        sql = (
            "SELECT * FROM transitions WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at DESC LIMIT ?"
        )
        async with self.db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def increment_access(self, entry_id: str) -> None:
        now = _now_iso()
        await self.db.execute(
            "UPDATE entries SET access_count = access_count + 1, last_accessed = ?, updated_at = ? WHERE id = ?",
            (now, now, entry_id),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Knowledge Extraction (4-Gate)
    # ------------------------------------------------------------------

    async def extract_knowledge(self, conversation: list[dict]) -> list[dict]:
        """Extract knowledge entries from a conversation using 4-Gate filtering.

        Each dict in conversation: {"role": str, "content": str}
        Returns list of extracted knowledge dicts that passed all gates.
        """
        if not conversation:
            return []

        # Build context from full conversation
        context = " ".join(msg.get("content", "") for msg in conversation)

        # Get existing entries for novelty/consistency checks
        existing = await self.get_entries(limit=200)

        # Extract candidate knowledge from assistant messages
        # (user messages provide context, assistant messages contain knowledge)
        candidates: list[dict] = []
        for msg in conversation:
            content = msg.get("content", "")
            if not content or len(content.strip()) < 20:
                continue
            # Split long messages into paragraphs as candidates
            paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) >= 20]
            if not paragraphs:
                paragraphs = [content]
            for para in paragraphs:
                candidates.append({
                    "content": para,
                    "role": msg.get("role", "unknown"),
                })

        extracted: list[dict] = []
        for cand in candidates:
            content = cand["content"]

            # Run 4 gates
            rel = relevance_gate(content, context)
            nov = novelty_gate(content, existing)
            conf = confidence_gate(content)
            cons = consistency_gate(content, existing)

            # All gates must pass thresholds
            if (
                rel < _GATE_THRESHOLDS["relevance"]
                or nov < _GATE_THRESHOLDS["novelty"]
                or conf < _GATE_THRESHOLDS["confidence"]
                or cons < _GATE_THRESHOLDS["consistency"]
            ):
                continue

            # Composite confidence
            composite = (rel * 0.2 + nov * 0.3 + conf * 0.3 + cons * 0.2)

            # Categorize
            category = _categorize(content)

            entry_id = await self.store_entry(
                entry_type="knowledge",
                content=content,
                category=category,
                confidence=composite,
                source_ids=[],
                metadata={
                    "gates": {
                        "relevance": round(rel, 3),
                        "novelty": round(nov, 3),
                        "confidence": round(conf, 3),
                        "consistency": round(cons, 3),
                    },
                    "source_role": cand["role"],
                },
            )
            extracted.append({
                "id": entry_id,
                "content": content,
                "category": category,
                "confidence": round(composite, 3),
                "gates": {
                    "relevance": round(rel, 3),
                    "novelty": round(nov, 3),
                    "confidence": round(conf, 3),
                    "consistency": round(cons, 3),
                },
            })

        return extracted

    # ------------------------------------------------------------------
    # Recall (BM25-like + time decay + MMR)
    # ------------------------------------------------------------------

    async def recall(self, query: str, limit: int = 5) -> list[dict]:
        """Retrieve relevant entries using keyword scoring, time decay, and MMR."""
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        query_set = set(query_tokens)

        # Fetch active entries
        async with self.db.execute(
            "SELECT * FROM entries WHERE agent_id = ? AND status = 'active'",
            (self.agent_id,),
        ) as cur:
            rows = await cur.fetchall()

        if not rows:
            return []

        entries = [dict(r) for r in rows]
        n_docs = len(entries)
        now = datetime.now(TZ_UTC)

        # Precompute document frequencies for IDF
        df: dict[str, int] = {}
        entry_tokens: list[set[str]] = []
        for e in entries:
            toks = set(tokenize(e["content"]))
            entry_tokens.append(toks)
            for t in toks:
                df[t] = df.get(t, 0) + 1

        # Score each entry (BM25-inspired tf-idf)
        query_entities = extract_entities(query)
        scored: list[tuple[float, int, set[str]]] = []
        for idx, e in enumerate(entries):
            toks = entry_tokens[idx]
            if not toks:
                continue
            score = 0.0
            for qt in query_tokens:
                if qt in toks:
                    # TF: count presence (binary for simplicity, boosted by token ratio)
                    tf = 1.0
                    idf = math.log((n_docs + 1) / (df.get(qt, 0) + 1)) + 1.0
                    score += tf * idf

            if score <= 0:
                continue

            # Time decay: half-life 30 days based on last_accessed
            last_acc = e.get("last_accessed") or e.get("created_at") or ""
            try:
                la_dt = datetime.fromisoformat(last_acc)
                if la_dt.tzinfo is None:
                    la_dt = la_dt.replace(tzinfo=TZ_UTC)
                days = max((now - la_dt).total_seconds() / 86400, 0)
            except (ValueError, TypeError):
                days = 90  # penalize entries with bad timestamps
            decay = math.exp(-0.693 * days / 30)
            score *= decay

            # Entity linking boost: exact entity matches get 30% boost
            entry_entities = extract_entities(e["content"])
            entity_overlap = query_entities & entry_entities
            if entity_overlap:
                score *= 1.0 + 0.3 * min(len(entity_overlap), 3)

            # Small boost for access_count (log scale)
            ac = e.get("access_count", 0) or 0
            score *= 1.0 + 0.1 * math.log1p(ac)

            scored.append((score, idx, toks))

        # Sort by score desc
        scored.sort(key=lambda x: x[0], reverse=True)

        # MMR deduplication
        selected: list[dict] = []
        selected_token_sets: list[set[str]] = []

        for score, idx, toks in scored:
            if len(selected) >= limit:
                break
            # Check similarity against already-selected
            too_similar = False
            for sel_toks in selected_token_sets:
                if _jaccard(toks, sel_toks) > 0.8:
                    too_similar = True
                    break
            if too_similar:
                continue

            entry = entries[idx]
            # Increment access
            await self.increment_access(entry["id"])

            selected.append({
                "id": entry["id"],
                "content": entry["content"],
                "entry_type": entry["entry_type"],
                "category": entry["category"],
                "confidence": entry["confidence"],
                "score": round(score, 4),
                "access_count": (entry.get("access_count", 0) or 0) + 1,
            })
            selected_token_sets.append(toks)

        return selected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "tech": ["api", "sdk", "code", "bug", "deploy", "server", "database",
             "架构", "技术", "部署", "代码", "接口", "数据库", "模型"],
    "product": ["feature", "ux", "ui", "user", "产品", "功能", "用户",
                "需求", "设计", "体验", "交互"],
    "business": ["revenue", "cost", "customer", "market", "收入", "成本",
                 "客户", "市场", "商业", "融资", "营收"],
    "strategy": ["plan", "roadmap", "vision", "goal", "战略", "规划",
                 "目标", "方向", "路线图"],
    "people": ["team", "hire", "culture", "团队", "招聘", "管理", "人才"],
}


def _categorize(content: str) -> str:
    lower = content.lower()
    scores: dict[str, int] = {}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in lower)
    if not scores or max(scores.values()) == 0:
        return "general"
    return max(scores, key=lambda k: scores[k])
