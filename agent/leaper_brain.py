"""Leaper Brain — SQLite-backed knowledge store with BM25 + Vector RRF hybrid search.

Provides persistent memory across sessions with:
- RRF (Reciprocal Rank Fusion) combining BM25 (SQL LIKE) + cosine vector search
- Embedding via Ollama /api/embeddings (nomic-embed-text, 768-dim)
- jieba Chinese segmentation for keyword extraction
- DB Schema v2: entry_type, confidence, access_count, last_accessed, metadata, status
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import struct
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Chinese segmentation ────────────────────────────────────────────────────

try:
    import jieba
    jieba.setLogLevel(logging.WARNING)
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False
    logger.info("jieba not installed — falling back to regex tokenization")

# ─── Embedding client ────────────────────────────────────────────────────────

_EMBED_MODEL = os.environ.get("LEAPER_EMBED_MODEL", "nomic-embed-text")
# Base URL only; /api/embeddings is appended below (Ollama native format)
_EMBED_BASE_URL = os.environ.get("LEAPER_EMBED_URL", "http://localhost:11434")

_embed_available: bool | None = None  # lazy probe: None=unknown, True=ok, False=down
_embed_lock = threading.Lock()  # W7 fix: guards first-probe transition under lock


def _get_embedding(text: str) -> list[float] | None:
    """Get embedding vector via Ollama /api/embeddings. Returns None on any failure."""
    global _embed_available
    # W7: double-checked locking — fast path outside, state update inside
    if _embed_available is False:
        return None
    with _embed_lock:
        if _embed_available is False:
            return None
    try:
        import urllib.request
        url = f"{_EMBED_BASE_URL.rstrip('/')}/api/embeddings"
        # Ollama format: {"model": ..., "prompt": ...} — response has top-level "embedding"
        body = json.dumps({"model": _EMBED_MODEL, "prompt": text[:2000]}).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        vec = data["embedding"]
        with _embed_lock:
            _embed_available = True
        return vec
    except Exception as e:
        with _embed_lock:
            if _embed_available is None:
                logger.info("Embedding unavailable (%s) — using keyword fallback", e)
                _embed_available = False
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ─── Schema ──────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leaper_brain (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    keywords    TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT '',
    namespace   TEXT NOT NULL DEFAULT 'default',
    layer       TEXT NOT NULL DEFAULT 'l0',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_namespace ON leaper_brain (namespace);
CREATE INDEX IF NOT EXISTS idx_layer ON leaper_brain (layer);
"""

# Each tuple: (column_name, ALTER SQL)
_MIGRATIONS: list[tuple[str, str]] = [
    ("embedding",    "ALTER TABLE leaper_brain ADD COLUMN embedding BLOB DEFAULT NULL"),
    ("entry_type",   "ALTER TABLE leaper_brain ADD COLUMN entry_type TEXT DEFAULT 'raw'"),
    ("confidence",   "ALTER TABLE leaper_brain ADD COLUMN confidence REAL DEFAULT 0.5"),
    ("access_count", "ALTER TABLE leaper_brain ADD COLUMN access_count INTEGER DEFAULT 0"),
    ("last_accessed","ALTER TABLE leaper_brain ADD COLUMN last_accessed TEXT"),
    ("metadata",     "ALTER TABLE leaper_brain ADD COLUMN metadata TEXT DEFAULT '{}'"),
    ("status",       "ALTER TABLE leaper_brain ADD COLUMN status TEXT DEFAULT 'active'"),
    # v1.1 — Knowledge State Runtime fields
    ("evidence",     "ALTER TABLE leaper_brain ADD COLUMN evidence TEXT"),
    ("valid_from",   "ALTER TABLE leaper_brain ADD COLUMN valid_from TEXT"),
    ("valid_until",  "ALTER TABLE leaper_brain ADD COLUMN valid_until TEXT"),
    ("claim_type",   "ALTER TABLE leaper_brain ADD COLUMN claim_type TEXT DEFAULT 'observation'"),
    ("supersedes",   "ALTER TABLE leaper_brain ADD COLUMN supersedes TEXT"),
]

# NULL-fill after migrations (idempotent, fast on small tables)
_NULL_FILLS = [
    "UPDATE leaper_brain SET entry_type = 'raw'   WHERE entry_type IS NULL",
    "UPDATE leaper_brain SET confidence = 0.5     WHERE confidence IS NULL",
    "UPDATE leaper_brain SET access_count = 0     WHERE access_count IS NULL",
    "UPDATE leaper_brain SET metadata = '{}'      WHERE metadata IS NULL",
    "UPDATE leaper_brain SET status = 'active'    WHERE status IS NULL",
]

_RRF_K = 60  # RRF constant


class LeaperBrain:
    """SQLite-backed knowledge store with RRF hybrid search."""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._ensure_db()

    def _ensure_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

        for col_name, alter_sql in _MIGRATIONS:
            try:
                self._conn.execute(f"SELECT {col_name} FROM leaper_brain LIMIT 0")
            except sqlite3.OperationalError:
                self._conn.execute(alter_sql)
                self._conn.commit()
                logger.info("Migrated leaper_brain: added column %s", col_name)

        for sql in _NULL_FILLS:
            self._conn.execute(sql)
        self._conn.commit()

        logger.debug("LeaperBrain initialized at %s", self.db_path)

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._ensure_db()
        return self._conn  # type: ignore[return-value]

    # ── Write ─────────────────────────────────────────────────────────────────

    def learn(
        self,
        content: str,
        source: str = "",
        namespace: str = "default",
        layer: str = "l0",
        entry_type: str = "raw",
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
        evidence: str | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        claim_type: str = "observation",
        supersedes: str | None = None,
    ) -> str:
        """Store a knowledge entry. Returns the new entry id."""
        if not content.strip():
            return ""
        entry_id = str(uuid.uuid4())
        now = _now()
        keywords = _extract_keywords(content)
        metadata_json = json.dumps(metadata or {})

        # Insert with embedding=NULL; embedding is filled asynchronously below
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO leaper_brain
                  (id, content, keywords, source, namespace, layer,
                   created_at, updated_at, embedding,
                   entry_type, confidence, access_count, metadata, status,
                   evidence, valid_from, valid_until, claim_type, supersedes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 0, ?, 'active',
                        ?, ?, ?, ?, ?)
                """,
                (
                    entry_id, content.strip(), json.dumps(keywords),
                    source, namespace, layer, now, now,
                    entry_type, confidence, metadata_json,
                    evidence, valid_from or now, valid_until, claim_type, supersedes,
                ),
            )
            # If this entry supersedes another, mark the old one as deprecated
            if supersedes:
                self.conn.execute(
                    "UPDATE leaper_brain SET status = 'superseded' WHERE id = ?",
                    (supersedes,),
                )
            self.conn.commit()

        # Async embedding: background thread writes embedding without blocking learn()
        def _embed_and_update() -> None:
            vec = _get_embedding(content)
            if vec:
                with self._lock:
                    self.conn.execute(
                        "UPDATE leaper_brain SET embedding = ? WHERE id = ?",
                        (_vec_to_blob(vec), entry_id),
                    )
                    self.conn.commit()

        threading.Thread(target=_embed_and_update, daemon=True).start()

        logger.debug(
            "LeaperBrain.learn: %s (ns=%s, type=%s, layer=%s)",
            entry_id, namespace, entry_type, layer,
        )
        return entry_id

    # ── Read ──────────────────────────────────────────────────────────────────

    def recall(
        self,
        query: str,
        top_k: int = 5,
        namespace: str | None = None,
        entry_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """RRF hybrid recall: vector + keyword search fused.

        RRF_score(d) = Σ 1/(60 + rank_i(d))
        Time weighting: <1d ×1.3, <7d ×1.1, ≥30d ×0.9
        entry_type='skill' ×1.2
        """
        if not query.strip():
            return []

        query_vec = _get_embedding(query)
        query_terms = _tokenize_query(query)

        # Shared column list used in all SELECT queries
        _COLS = (
            "id, content, source, namespace, keywords, layer, "
            "entry_type, confidence, created_at, updated_at, embedding, metadata, status"
        )

        # Build base WHERE filter (namespace / entry_type / status / validity)
        where_parts: list[str] = [
            "(status = 'active' OR status IS NULL)",
            "(valid_until IS NULL OR valid_until > ?)",
        ]
        base_params: list[Any] = [_now()]
        if namespace:
            where_parts.append("namespace = ?")
            base_params.append(namespace)
        if entry_type:
            where_parts.append("entry_type = ?")
            base_params.append(entry_type)
        where_clause = " AND ".join(where_parts)

        now_dt = datetime.now(timezone.utc)

        # ── Step 1: BM25 — SQL LIKE pre-filter, score in memory, take top 20 ──────
        bm25_rows: list[sqlite3.Row] = []
        kw_scores: list[tuple[str, float]] = []
        if query_terms:
            # OR-LIKE across up to 5 query terms to get BM25 candidates
            like_parts: list[str] = []
            like_params: list[Any] = []
            for term in query_terms[:5]:
                like_parts.append("(content LIKE ? OR keywords LIKE ?)")
                like_params.extend([f"%{term}%", f"%{term}%"])
            bm25_where = where_clause + " AND (" + " OR ".join(like_parts) + ")"
            with self._lock:
                bm25_rows = self.conn.execute(
                    f"SELECT {_COLS} FROM leaper_brain WHERE {bm25_where}",
                    base_params + like_params,
                ).fetchall()
            # BM25-lite score, keep top 20 candidates
            scored = []
            for row in bm25_rows:
                kws = json.loads(row["keywords"] or "[]")
                score = _keyword_score(query, row["content"], kws)
                scored.append((row["id"], score))
            scored.sort(key=lambda x: x[1], reverse=True)
            kw_scores = scored[:20]

        # ── Step 2: Vector — cosine similarity vs all embedded rows, top 20 ───────
        vec_rows: list[sqlite3.Row] = []
        vec_scores: list[tuple[str, float]] = []
        if query_vec:
            with self._lock:
                vec_rows = self.conn.execute(
                    f"SELECT {_COLS} FROM leaper_brain"
                    f" WHERE {where_clause} AND embedding IS NOT NULL",
                    base_params,
                ).fetchall()
            scored_vec = []
            for row in vec_rows:
                row_vec = _blob_to_vec(row["embedding"])
                score = _cosine_similarity(query_vec, row_vec)
                scored_vec.append((row["id"], score))
            scored_vec.sort(key=lambda x: x[1], reverse=True)
            vec_scores = scored_vec[:20]

        # Fallback: if embedding unavailable and no BM25 hits, nothing to return
        if not kw_scores and not vec_scores:
            return []

        # ── Step 3: RRF fusion — score = Σ 1/(k + rank) ─────────────────────────
        rrf: dict[str, float] = {}
        for rank, (rid, _) in enumerate(kw_scores):
            rrf[rid] = rrf.get(rid, 0.0) + 1.0 / (_RRF_K + rank + 1)
        for rank, (rid, _) in enumerate(vec_scores):
            rrf[rid] = rrf.get(rid, 0.0) + 1.0 / (_RRF_K + rank + 1)

        # Build row_map from both candidate sets (vec_rows may contain rows not in bm25)
        row_map: dict[str, Any] = {row["id"]: row for row in bm25_rows}
        for row in vec_rows:
            if row["id"] not in row_map:
                row_map[row["id"]] = row

        # ── Time weighting + entry-type boost ────────────────────────────────────
        results: list[dict[str, Any]] = []
        for rid, base_score in rrf.items():
            row = row_map.get(rid)
            if not row:
                continue
            try:
                updated = datetime.fromisoformat(
                    row["updated_at"].replace("Z", "+00:00")
                )
                age_days = (now_dt - updated).total_seconds() / 86400
            except Exception:
                age_days = 30

            if age_days < 1:
                time_mult = 1.3
            elif age_days < 7:
                time_mult = 1.1
            elif age_days >= 30:
                time_mult = 0.9
            else:
                time_mult = 1.0

            type_mult = 1.2 if row["entry_type"] == "skill" else 1.0
            final_score = base_score * time_mult * type_mult

            results.append({
                "id": rid,
                "content": row["content"],
                "source": row["source"],
                "namespace": row["namespace"],
                "layer": row["layer"],
                "entry_type": row["entry_type"],
                "confidence": row["confidence"],
                "keywords": json.loads(row["keywords"] or "[]"),
                "score": round(final_score, 6),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "metadata": json.loads(row["metadata"] or "{}"),
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        top = results[:top_k]

        # Update access stats for returned entries
        if top:
            ids = [r["id"] for r in top]
            now_str = _now()
            with self._lock:
                for rid in ids:
                    self.conn.execute(
                        "UPDATE leaper_brain SET access_count = access_count + 1,"
                        " last_accessed = ? WHERE id = ?",
                        (now_str, rid),
                    )
                self.conn.commit()

        return top

    # ── New methods ───────────────────────────────────────────────────────────

    def get_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        """Fetch entries by id list."""
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        with self._lock:
            rows = self.conn.execute(
                f"SELECT * FROM leaper_brain WHERE id IN ({placeholders})", ids
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def update_confidence(self, entry_id: str, new_confidence: float) -> None:
        clamped = max(0.0, min(1.0, new_confidence))
        with self._lock:
            self.conn.execute(
                "UPDATE leaper_brain SET confidence = ?, updated_at = ? WHERE id = ?",
                (clamped, _now(), entry_id),
            )
            self.conn.commit()

    def update_metadata(self, entry_id: str, metadata_dict: dict[str, Any]) -> None:
        with self._lock:
            row = self.conn.execute(
                "SELECT metadata FROM leaper_brain WHERE id = ?", (entry_id,)
            ).fetchone()
            if row:
                existing = json.loads(row["metadata"] or "{}")
                existing.update(metadata_dict)
                self.conn.execute(
                    "UPDATE leaper_brain SET metadata = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(existing), _now(), entry_id),
                )
                self.conn.commit()

    def update_status(self, entry_id: str, status: str) -> None:
        now = _now()
        with self._lock:
            self.conn.execute(
                "UPDATE leaper_brain SET status = ?, updated_at = ?, valid_until = ? WHERE id = ?",
                (status, now, now if status in ("deprecated", "superseded") else None, entry_id),
            )
            self.conn.commit()

    def update_namespace(self, entry_id: str, namespace: str) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE leaper_brain SET namespace = ?, updated_at = ? WHERE id = ?",
                (namespace, _now(), entry_id),
            )
            self.conn.commit()

    def get_entries(
        self,
        layer: str | None = None,
        entry_type: str | None = None,
        namespace: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch entries with optional filters, ordered by updated_at DESC."""
        where_parts: list[str] = []
        params: list[Any] = []
        if layer:
            where_parts.append("layer = ?")
            params.append(layer)
        if entry_type:
            where_parts.append("entry_type = ?")
            params.append(entry_type)
        if namespace:
            where_parts.append("namespace = ?")
            params.append(namespace)
        if status:
            where_parts.append("status = ?")
            params.append(status)
        where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        params.append(limit)
        with self._lock:
            rows = self.conn.execute(
                f"SELECT * FROM leaper_brain {where_clause}"
                f" ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ── Batch embed ───────────────────────────────────────────────────────────

    def backfill_embeddings(self, batch_size: int = 50) -> int:
        """Generate embeddings for all entries where embedding IS NULL.

        Processes rows in batches of batch_size, committing after each batch
        so progress is not lost if interrupted. Returns total count updated.
        """
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, content FROM leaper_brain WHERE embedding IS NULL"
            ).fetchall()
        total = len(rows)
        updated = 0
        for batch_start in range(0, total, batch_size):
            batch = rows[batch_start : batch_start + batch_size]
            for row in batch:
                vec = _get_embedding(row["content"])
                if vec is None:
                    # Embedding service down — stop and report progress
                    logger.info(
                        "Backfill stopped at %d/%d (embedding unavailable)", updated, total
                    )
                    return updated
                with self._lock:
                    self.conn.execute(
                        "UPDATE leaper_brain SET embedding = ? WHERE id = ?",
                        (_vec_to_blob(vec), row["id"]),
                    )
                updated += 1
            # Commit after each batch to persist partial progress
            with self._lock:
                self.conn.commit()
            logger.debug("Backfill: %d/%d embeddings written", updated, total)
        logger.info("Backfilled embeddings: %d/%d entries", updated, total)
        return updated

    # ── Delete / Stats ────────────────────────────────────────────────────────

    def forget(self, entry_id: str) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM leaper_brain WHERE id = ?", (entry_id,))
            self.conn.commit()

    def get_stats(self) -> dict[str, Any]:
        # Run all four queries inside a single lock so the snapshot is consistent.
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) as total, COUNT(DISTINCT namespace) as namespaces"
                " FROM leaper_brain"
            ).fetchone()
            embedded = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM leaper_brain WHERE embedding IS NOT NULL"
            ).fetchone()["cnt"]
            ns_rows = self.conn.execute(
                "SELECT namespace, COUNT(*) as cnt FROM leaper_brain GROUP BY namespace"
            ).fetchall()
            type_rows = self.conn.execute(
                "SELECT entry_type, COUNT(*) as cnt FROM leaper_brain GROUP BY entry_type"
            ).fetchall()
        return {
            "db_path": str(self.db_path),
            "total_entries": row["total"],
            "embedded_entries": embedded,
            "namespaces": row["namespaces"],
            "namespace_breakdown": {r["namespace"]: r["cnt"] for r in ns_rows},
            "type_breakdown": {r["entry_type"]: r["cnt"] for r in type_rows},
            "embedding_model": _EMBED_MODEL if _embed_available else None,
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if "keywords" in d:
        d["keywords"] = json.loads(d.get("keywords") or "[]")
    if "metadata" in d:
        d["metadata"] = json.loads(d.get("metadata") or "{}")
    d.pop("embedding", None)  # don't expose binary blobs
    return d


def _extract_keywords(text: str) -> list[str]:
    import re
    tokens: list[str] = []
    if _HAS_JIEBA:
        for w in jieba.cut(text, cut_all=False):
            w = w.strip()
            if len(w) >= 2 and not w.isspace():
                tokens.append(w.lower())
    else:
        tokens = [t.lower() for t in re.findall(r"[a-zA-Z一-鿿]{2,}", text)]

    stopwords = {
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
        "都", "一", "个", "上", "也", "很", "到", "说", "要", "去",
        "你", "会", "着", "没有", "看", "好", "自己", "这",
        "the", "is", "at", "which", "on", "and", "or", "for", "to",
        "in", "of", "with", "that", "this", "from", "are", "was",
    }
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in seen and t not in stopwords:
            seen.add(t)
            out.append(t)
    return out[:30]


def _tokenize_query(query: str) -> list[str]:
    if _HAS_JIEBA:
        terms = [w.strip() for w in jieba.cut(query, cut_all=False) if len(w.strip()) >= 2]
    else:
        terms = [t.strip() for t in query.split() if len(t.strip()) >= 2]
    return terms[:10]


def _keyword_score(query: str, content: str, keywords: list[str]) -> float:
    """BM25-lite scoring with length normalization."""
    q_terms = _tokenize_query(query)
    if not q_terms:
        return 0.0
    content_lower = content.lower()
    kw_set = set(k.lower() for k in keywords)
    doc_len = len(content_lower)
    avg_len = 500
    k1, b = 1.5, 0.75
    total = 0.0
    for term in q_terms:
        tf = content_lower.count(term.lower())
        if tf == 0 and term.lower() in kw_set:
            tf = 1
        norm_tf = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_len))
        total += norm_tf
    return total / len(q_terms)


# ─── Vector serialization ────────────────────────────────────────────────────


def _vec_to_blob(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _blob_to_vec(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))
