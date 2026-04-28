"""Leaper Evolution Engine — 6-layer self-improvement system.

L0: hybrid_recall       — delegates to brain.recall() RRF
L1: experience_extract  — Trajectory-Informed 4-dim extraction + quality gates
L2: skill_generate      — topic grouping → embedding clustering → LLM synthesis
L3: skill_evolve        — merge, deprecate, promote, drift detection
L4: user_model_update   — multi-dim user profile + prompt injection
L5: validate            — consistency check, regression test, time decay
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from agent.leaper_brain import LeaperBrain

from agent.leaper_brain import _get_embedding, _cosine_similarity, _now

logger = logging.getLogger(__name__)


# ─── LLM client for evolution ────────────────────────────────────────────────

_evolution_llm = None
_local_llm_cache: dict | None = None
_local_llm_probed = False
_local_hit_count = 0
_cloud_hit_count = 0

_EXTRACTION_BLACKLIST = frozenset({
    '对话分析', '一般', '其他', 'general', 'other', '未知', '聊天'
})


def _get_local_llm() -> dict | None:
    """Lazy-init local LLM (Ollama). Probes once at startup; returns None if unreachable."""
    global _local_llm_cache, _local_llm_probed
    if _local_llm_probed:
        return _local_llm_cache
    _local_llm_probed = True

    base_url = os.environ.get("LEAPER_LOCAL_URL", "http://localhost:11434/v1")
    model = os.environ.get("LEAPER_LOCAL_MODEL", "qwen2.5:7b")

    try:
        import urllib.request
        urllib.request.urlopen(f"{base_url}/models", timeout=3)
    except Exception:
        logger.debug("Local LLM not reachable at %s", base_url)
        return None

    try:
        from openai import OpenAI
        _local_llm_cache = {
            "client": OpenAI(base_url=base_url, api_key="ollama"),
            "model": model,
            "local": True,
        }
        logger.info("Local LLM available: %s @ %s", model, base_url)
        return _local_llm_cache
    except Exception as e:
        logger.warning("Failed to init local LLM: %s", e)
        return None


def _get_cloud_llm() -> dict | None:
    """Lazy-init cloud/aggregated LLM (OpenAI-compatible)."""
    global _evolution_llm
    if _evolution_llm is not None:
        return _evolution_llm

    base_url = os.environ.get("LEAPER_EVOLUTION_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    api_key = os.environ.get("LEAPER_EVOLUTION_API_KEY") or os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("LEAPER_EVOLUTION_MODEL", "")
    if not model:
        try:
            import yaml
            config_path = os.path.join(
                os.environ.get("HERMES_HOME", ""), "config.yaml"
            )
            if os.path.isfile(config_path):
                with open(config_path, "r", encoding="utf-8") as _cf:
                    _cfg = yaml.safe_load(_cf) or {}
                model = (
                    _cfg.get("auxiliary", {}).get("model", "")
                    or _cfg.get("model", {}).get("default", "")
                )
        except Exception:
            pass

    if not base_url or not api_key:
        logger.info("Evolution LLM not configured (no OPENAI_BASE_URL/API_KEY)")
        return None

    try:
        from openai import OpenAI
        _evolution_llm = {
            "client": OpenAI(base_url=base_url, api_key=api_key),
            "model": model,
        }
        logger.info("Evolution LLM initialized: %s @ %s", model, base_url)
        return _evolution_llm
    except Exception as e:
        logger.warning("Failed to init evolution LLM: %s", e)
        return None


def _call_llm(llm: dict, prompt: str, max_tokens: int) -> str | None:
    """Call a single LLM client. Local: temperature=0, timeout=30s. Cloud: no temperature."""
    try:
        kwargs: dict[str, Any] = {
            "model": llm["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if llm.get("local"):
            kwargs["temperature"] = 0
            kwargs["timeout"] = 30
        resp = llm["client"].chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning("LLM call failed (%s): %s", "local" if llm.get("local") else "cloud", e)
        return None


def _validate_extraction(result_text: str) -> tuple[bool, dict]:
    """Quality gate for L1 extraction. Returns (is_valid, parsed_dict_or_reason_dict).

    Field mapping: spec (topic/intent/strategy/knowledge/complexity) →
    actual (topic/user_intent/successful_strategy/new_knowledge/complexity).
    """
    parsed = _parse_llm_json(result_text)
    if not isinstance(parsed, dict):
        return False, {"reason": "invalid JSON"}

    required = ['topic', 'user_intent', 'successful_strategy', 'new_knowledge', 'complexity']
    missing = [k for k in required if k not in parsed]
    if missing:
        return False, {"reason": f"missing fields: {missing}"}

    topic = str(parsed.get('topic') or '')
    if topic in _EXTRACTION_BLACKLIST:
        return False, {"reason": f"generic topic: {topic!r}"}

    knowledge = parsed.get('new_knowledge')
    if knowledge is not None and isinstance(knowledge, str) and len(knowledge) <= 20:
        return False, {"reason": f"knowledge too short ({len(knowledge)} chars)"}

    complexity = str(parsed.get('complexity', ''))
    if complexity not in ('trivial', 'moderate', 'complex'):
        return False, {"reason": f"invalid complexity: {complexity!r}"}

    return True, parsed


def _validate_skill(result_text: str) -> tuple[bool, dict]:
    """Quality gate for L2 skill synthesis. Checks title and content fields."""
    parsed = _parse_llm_json(result_text)
    if not isinstance(parsed, dict):
        return False, {"reason": "invalid JSON"}
    missing = [k for k in ("title", "content") if k not in parsed]
    if missing:
        return False, {"reason": f"missing fields: {missing}"}
    if len(str(parsed.get("title", ""))) <= 5:
        return False, {"reason": "title too short"}
    if len(str(parsed.get("content", ""))) <= 50:
        return False, {"reason": "content too short"}
    return True, parsed


def _validate_user_model(result_text: str) -> tuple[bool, dict]:
    """Quality gate for L4 user profile (stricter)."""
    parsed = _parse_llm_json(result_text)
    if not isinstance(parsed, dict):
        return False, {"reason": "invalid JSON"}
    required = ["communication_style", "expertise_level", "decision_patterns", "recurring_topics"]
    missing = [k for k in required if k not in parsed]
    if missing:
        return False, {"reason": f"missing fields: {missing}"}
    if len(str(parsed.get("communication_style", ""))) <= 20:
        return False, {"reason": "communication_style too short"}
    if len(str(parsed.get("decision_patterns", ""))) <= 20:
        return False, {"reason": "decision_patterns too short"}
    topics = parsed.get("recurring_topics")
    if not isinstance(topics, list) or len(topics) < 2:
        return False, {"reason": "recurring_topics must be list with >= 2 items"}
    if parsed.get("expertise_level") not in ("novice", "intermediate", "expert"):
        return False, {"reason": f"invalid expertise_level: {parsed.get('expertise_level')!r}"}
    conf = parsed.get("confidence")
    if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
        return False, {"reason": f"confidence must be float in [0, 1], got {conf!r}"}
    return True, parsed


def _call_evolution_llm(
    prompt: str, max_tokens: int = 512, require_quality_gate: bool = False,
    quality_gate_fn: Callable | None = None, skip_local: bool = False,
) -> str | None:
    """Tiered LLM call: local first (with optional quality gate) → cloud fallback."""
    global _local_hit_count, _cloud_hit_count

    if not skip_local:
        local = _get_local_llm()
    else:
        local = None
        logger.info("Skipping local LLM (skip_local=True), going straight to cloud")
    if local:
        result = _call_llm(local, prompt, max_tokens)
        if result:
            if not require_quality_gate:
                _local_hit_count += 1
                return result
            gate_fn = quality_gate_fn if quality_gate_fn is not None else _validate_extraction
            valid, info = gate_fn(result)
            if valid:
                _local_hit_count += 1
                logger.info(
                    "Local quality gate passed (hit_rate: %d/%d)",
                    _local_hit_count, _local_hit_count + _cloud_hit_count,
                )
                return result
            logger.info(
                "Local quality gate failed, cloud fallback (reason: %s)",
                info.get("reason", "unknown"),
            )

    cloud = _get_cloud_llm()
    if cloud:
        result = _call_llm(cloud, prompt, max_tokens)
        if result:
            _cloud_hit_count += 1
            if require_quality_gate:
                logger.info("Cloud LLM used (quality gate active)")
            return result

    if require_quality_gate:
        logger.warning("LLM call failed: no LLM available")
    return None


def get_stats() -> dict:
    """Return evolution LLM usage statistics."""
    total = _local_hit_count + _cloud_hit_count
    return {
        "local_hits": _local_hit_count,
        "cloud_hits": _cloud_hit_count,
        "total": total,
        "local_rate": _local_hit_count / total if total else 0.0,
    }


def _parse_llm_json(text: str) -> dict | list | None:
    """Parse JSON from LLM output, stripping markdown code fences."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except Exception:
        return None


# ─── Engine ──────────────────────────────────────────────────────────────────


class EvolutionEngine:
    """Orchestrates Leaper's 6-layer self-improvement loop."""

    def __init__(self, brain: "LeaperBrain", llm_client: Any = None) -> None:
        self.brain = brain
        self.llm = llm_client  # kept for backward compat
        self._lock = threading.Lock()

    # ── L0: Hybrid Recall ─────────────────────────────────────────────────────

    def hybrid_recall(
        self, query: str, top_k: int = 5, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        """L0: Delegates to brain.recall() which implements RRF internally."""
        results = self.brain.recall(query, top_k=top_k, namespace=namespace)
        logger.debug("L0 hybrid_recall: query=%r → %d results", query, len(results))
        return results

    def format_recall_for_prompt(
        self, query: str, top_k: int = 5, extra_context: str = ""
    ) -> str:
        """Return formatted recalled entries for system prompt injection."""
        results = self.hybrid_recall(query, top_k=top_k)
        parts: list[str] = []
        if results:
            parts.append("[Leaper Brain — Recalled Knowledge]")
            for i, r in enumerate(results, 1):
                snippet = r["content"][:300].replace("\n", " ")
                label = f"[{r['namespace']}|{r.get('entry_type', 'raw')}]"
                parts.append(f"{i}. {label} {snippet}")
        if extra_context:
            parts.append(extra_context)
        return "\n".join(parts)

    # ── L1: Experience Extract ────────────────────────────────────────────────

    def experience_extract(self, user_msg: str, assistant_msg: str) -> dict[str, Any]:
        """L1: Trajectory-Informed 4-dim extraction with 4-gate quality check."""
        result = self._llm_experience_extract(user_msg, assistant_msg)
        if not result:
            result = self._rule_experience_extract(user_msg, assistant_msg)
        if not self._passes_quality_gate(result):
            result["_skip_store"] = True
        return result

    def _llm_experience_extract(
        self, user_msg: str, assistant_msg: str
    ) -> dict[str, Any] | None:
        prompt = f"""分析以下对话轮次，提取结构化经验。返回纯 JSON，不要包含 markdown 代码块。

User: {_truncate(user_msg, 500)}
Assistant: {_truncate(assistant_msg, 800)}

返回 JSON 格式：
{{
  "summary": "一句话总结这轮对话的核心信息（≤100字）",
  "keywords": ["关键词1", "关键词2"],
  "task_success": true,
  "complexity": "trivial/moderate/complex",
  "user_intent": "用户想要什么",
  "topic": "主题分类（如：客户策略/产品设计/融资/团队/技术/其他）",
  "successful_strategy": "助手用了什么有效策略（如没有则null）",
  "failure_recovery": "失败后如何恢复（如无失败则null）",
  "efficiency_tip": "提效技巧或捷径（如无则null）",
  "new_knowledge": "这轮对话中出现的新知识点（如无则null）"
}}

判断标准：
- task_success: 助手是否有效回应了用户需求
- complexity: trivial=打招呼/简单确认, moderate=有实质讨论, complex=深度分析/多维度
- 如果对话没有实质内容，summary 写"闲聊"，complexity 写"trivial"

只返回 JSON。"""

        result = _call_evolution_llm(prompt, max_tokens=500, require_quality_gate=True)
        if not result:
            return None
        parsed = _parse_llm_json(result)
        if not isinstance(parsed, dict):
            return None
        required = ["summary", "keywords", "task_success", "complexity"]
        if not all(k in parsed for k in required):
            logger.warning("L1 LLM missing fields: %s", list(parsed.keys()))
            return None
        parsed["keywords"] = list(parsed.get("keywords", []))[:10]
        parsed.setdefault("tools_used", [])
        parsed.setdefault("user_satisfaction", "unknown")
        return parsed

    def _rule_experience_extract(
        self, user_msg: str, assistant_msg: str
    ) -> dict[str, Any]:
        combined = f"{user_msg}\n{assistant_msg}"
        keywords = _smart_keywords(combined)
        complexity = _estimate_complexity(combined)
        fail_indicators = [
            "error", "sorry", "cannot", "unable",
            "抱歉", "无法", "做不到", "不支持", "出错",
        ]
        task_success = not any(w in assistant_msg.lower() for w in fail_indicators)
        topic = _infer_topic(keywords, user_msg)
        return {
            "keywords": keywords,
            "summary": _smart_summary(combined),
            "task_success": task_success,
            "user_satisfaction": "unknown",
            "complexity": complexity,
            "tools_used": [],
            "topic": topic,
            "user_intent": _truncate(user_msg, 200),
            "successful_strategy": None,
            "failure_recovery": None,
            "efficiency_tip": None,
            "new_knowledge": None,
        }

    def _passes_quality_gate(self, exp: dict[str, Any]) -> bool:
        """4-gate quality check.

        Gate1: complexity != trivial
        Gate2: duplication cosine < 0.9 vs recent experiences (best-effort)
        Gate3: summary length > 15 chars
        Gate4: at least one 4-dim field non-null, or task_success=True
        """
        if exp.get("complexity") == "trivial":
            logger.debug("L1 gate1 fail: trivial")
            return False

        summary = exp.get("summary", "")
        if len(summary) <= 15:
            logger.debug("L1 gate3 fail: summary too short (%d chars)", len(summary))
            return False

        dim_fields = ["successful_strategy", "failure_recovery", "efficiency_tip", "new_knowledge"]
        has_dim = any(exp.get(f) for f in dim_fields)
        if not has_dim and not exp.get("task_success"):
            logger.debug("L1 gate4 fail: no 4-dim content and not successful")
            return False

        # Gate2: dedup via embedding (best-effort, skip on error)
        try:
            query_vec = _get_embedding(summary[:300])
            if query_vec:
                recent = self.brain.get_entries(layer="l1", entry_type="experience", limit=10)
                for entry in recent:
                    entry_vec = _get_embedding(entry["content"][:200])
                    if entry_vec:
                        sim = _cosine_similarity(query_vec, entry_vec)
                        if sim >= 0.9:
                            logger.debug("L1 gate2 fail: duplicate (cosine=%.3f)", sim)
                            return False
        except Exception:
            pass

        return True

    def store_experience(self, exp: dict[str, Any]) -> str:
        """Store a quality-gated experience (layer=l1, entry_type=experience)."""
        if exp.get("_skip_store"):
            return ""
        summary = exp.get("summary", "")
        if not summary:
            return ""
        topic = exp.get("topic", "general")
        # Build rich content: summary + key dimensions for better recall
        content_parts = [summary]
        if exp.get("user_intent"):
            content_parts.append(f"User intent: {exp['user_intent']}")
        if exp.get("successful_strategy"):
            content_parts.append(f"Strategy: {exp['successful_strategy']}")
        if exp.get("new_knowledge"):
            content_parts.append(f"Knowledge: {exp['new_knowledge']}")
        if exp.get("failure_recovery"):
            content_parts.append(f"Recovery: {exp['failure_recovery']}")
        if exp.get("efficiency_tip"):
            content_parts.append(f"Tip: {exp['efficiency_tip']}")
        rich_content = "\n".join(content_parts)
        metadata: dict[str, Any] = {
            "topic": topic,
            "keywords": exp.get("keywords", []),
            "task_success": exp.get("task_success"),
            "complexity": exp.get("complexity"),
            "user_intent": exp.get("user_intent"),
            "successful_strategy": exp.get("successful_strategy"),
            "failure_recovery": exp.get("failure_recovery"),
            "efficiency_tip": exp.get("efficiency_tip"),
            "new_knowledge": exp.get("new_knowledge"),
        }
        entry_id = self.brain.learn(
            content=rich_content,
            source="conversation",
            namespace="experience",
            layer="l1",
            entry_type="experience",
            confidence=0.6 if exp.get("task_success") else 0.4,
            metadata=metadata,
        )
        logger.info("L1 stored experience: %s (topic=%s)", entry_id[:8] if entry_id else "—", topic)
        return entry_id

    # ── L2: Skill Generate ────────────────────────────────────────────────────

    def skill_generate(
        self, experiences: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """L2: topic grouping → embedding clustering → LLM synthesis → backtrace validate."""
        if experiences is None:
            experiences = self.brain.get_entries(
                layer="l1", entry_type="experience", limit=100
            )
        if len(experiences) < 3:
            logger.debug("L2: insufficient experiences (%d)", len(experiences))
            return []

        # Group by topic
        topic_groups: dict[str, list[dict[str, Any]]] = {}
        for exp in experiences:
            meta = exp.get("metadata") or {}
            topic = meta.get("topic") or exp.get("topic", "general")
            topic_groups.setdefault(topic, []).append(exp)

        generated: list[dict[str, Any]] = []
        for topic, group in topic_groups.items():
            if len(group) < 3:
                continue
            clusters = self._cluster_by_embedding(group, threshold=0.6)
            for cluster in clusters:
                if len(cluster) < 3:
                    continue
                skill = self._synthesize_skill(topic, cluster)
                if skill and self._backtrace_validate(skill, cluster):
                    entry_id = self._store_skill(skill)
                    if entry_id:
                        skill["id"] = entry_id
                        generated.append(skill)

        logger.info("L2 skill_generate: generated %d skills", len(generated))
        return generated

    def _cluster_by_embedding(
        self, experiences: list[dict[str, Any]], threshold: float = 0.6
    ) -> list[list[dict[str, Any]]]:
        """Greedy single-link clustering by embedding cosine similarity."""
        vecs: list[list[float] | None] = [
            _get_embedding(exp.get("content", "")[:500]) for exp in experiences
        ]
        if all(v is None for v in vecs):
            return [experiences]

        assigned = [False] * len(experiences)
        clusters: list[list[int]] = []
        for i in range(len(experiences)):
            if assigned[i]:
                continue
            cluster = [i]
            assigned[i] = True
            for j in range(i + 1, len(experiences)):
                if assigned[j]:
                    continue
                vi, vj = vecs[i], vecs[j]
                if vi and vj and _cosine_similarity(vi, vj) >= threshold:
                    cluster.append(j)
                    assigned[j] = True
            clusters.append(cluster)

        return [[experiences[i] for i in c] for c in clusters]

    def _synthesize_skill(
        self, topic: str, cluster: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        exp_texts = "\n".join(
            f"- {e.get('content', '')[:200]}" for e in cluster[:8]
        )
        prompt = f"""基于以下 {topic} 主题的对话经验，合成一个可复用技能。返回纯 JSON。

经验：
{exp_texts}

返回 JSON 格式：
{{
  "name": "技能名称（简洁）",
  "description": "技能说明（≤80字）",
  "triggers": ["触发词/模式1", "触发词/模式2"],
  "procedure": "执行步骤",
  "guardrails": "边界条件或注意事项",
  "success_criteria": "成功标准",
  "confidence": 0.0
}}

如果无明显可复用模式，返回 {{"skip": true, "reason": "原因"}}。只返回 JSON。"""

        skill: dict[str, Any] | None = None
        result = _call_evolution_llm(prompt, max_tokens=600, require_quality_gate=True, quality_gate_fn=_validate_skill)
        if result:
            parsed = _parse_llm_json(result)
            if isinstance(parsed, dict) and not parsed.get("skip") and "name" in parsed:
                if parsed.get("confidence", 0) >= 0.3:
                    skill = parsed
                    skill.update({
                        "topic": topic,
                        "source": "llm",
                        "version": 1,
                        "status": "unverified",
                        "usage_count": 0,
                        "success_count": 0,
                    })
                elif isinstance(parsed, dict) and parsed.get("skip"):
                    logger.debug("L2 LLM skip: %s", parsed.get("reason"))

        if not skill:
            skill = self._rule_skill_generate(topic, cluster)
        return skill

    def _rule_skill_generate(
        self, topic: str, experiences: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        all_kws: list[str] = []
        for exp in experiences:
            meta = exp.get("metadata") or {}
            all_kws.extend(meta.get("keywords", []))
        if not all_kws:
            return None
        freq: dict[str, int] = {}
        for kw in all_kws:
            freq[kw] = freq.get(kw, 0) + 1
        repeated = {kw: cnt for kw, cnt in freq.items() if cnt >= 2}
        if len(repeated) < 2:
            return None
        top_triggers = [kw for kw, _ in sorted(repeated.items(), key=lambda x: -x[1])[:5]]
        return {
            "name": f"{topic}_skill",
            "description": f"Pattern from {len(experiences)} {topic} experiences",
            "triggers": top_triggers,
            "procedure": "; ".join(e.get("content", "")[:80] for e in experiences[:3]),
            "guardrails": "",
            "success_criteria": "",
            "confidence": min(0.3 + len(repeated) * 0.05, 0.6),
            "topic": topic,
            "source": "rule",
            "version": 1,
            "status": "unverified",
            "usage_count": 0,
            "success_count": 0,
        }

    def _backtrace_validate(
        self, skill: dict[str, Any], source_exps: list[dict[str, Any]]
    ) -> bool:
        """Trigger match rate >= 0.4 AND semantic coverage >= 0.3."""
        triggers = skill.get("triggers", [])
        if not triggers or not source_exps:
            return True

        matched = sum(
            1 for exp in source_exps
            if any(t.lower() in exp.get("content", "").lower() for t in triggers)
        )
        trigger_rate = matched / len(source_exps)

        desc = skill.get("description") or skill.get("name", "")
        desc_vec = _get_embedding(desc[:300])
        if desc_vec:
            cover_count = sum(
                1 for exp in source_exps
                if (lambda ev: ev and _cosine_similarity(desc_vec, ev) >= 0.3)(
                    _get_embedding(exp.get("content", "")[:200])
                )
            )
            coverage = cover_count / len(source_exps)
        else:
            coverage = 0.5  # assume ok when embedding unavailable

        ok = trigger_rate >= 0.4 and coverage >= 0.3
        logger.debug(
            "L2 backtrace: trigger_rate=%.2f coverage=%.2f ok=%s",
            trigger_rate, coverage, ok,
        )
        return ok

    def _store_skill(self, skill: dict[str, Any]) -> str:
        desc = skill.get("description") or skill.get("name", "")
        return self.brain.learn(
            content=desc,
            source="evolution_l2",
            namespace="skill",
            layer="l2",
            entry_type="skill",
            confidence=skill.get("confidence", 0.5),
            metadata=skill,
        )

    # ── L3: Skill Evolve ──────────────────────────────────────────────────────

    def skill_evolve(
        self, skills: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """L3: MERGE, DEPRECATE, PROMOTE, SEMANTIC DRIFT."""
        if skills is None:
            skills = self.brain.get_entries(
                layer="l2", entry_type="skill", status="active"
            )
        if not skills:
            return {"merged": [], "deprecated": [], "promoted": [], "drift_alerts": []}

        merged = self._merge_skills(skills)
        deprecated = self._deprecate_skills(skills)
        promoted = self._promote_skills(skills)
        drift_alerts = self._detect_semantic_drift(skills)

        logger.info(
            "L3 skill_evolve: merged=%d deprecated=%d promoted=%d drift=%d",
            len(merged), len(deprecated), len(promoted), len(drift_alerts),
        )
        return {
            "merged": merged,
            "deprecated": deprecated,
            "promoted": promoted,
            "drift_alerts": drift_alerts,
        }

    def _merge_skills(self, skills: list[dict[str, Any]]) -> list[str]:
        """Merge pairs: description cosine > 0.75 OR trigger Jaccard > 0.5."""
        merged_ids: list[str] = []
        processed: set[str] = set()
        n = len(skills)

        for i in range(n):
            si = skills[i]
            si_id = si.get("id", "")
            if si_id in processed:
                continue
            mi = si.get("metadata") or {}
            si_triggers = set(t.lower() for t in mi.get("triggers", []))
            si_desc = mi.get("description") or si.get("content", "")
            si_vec = _get_embedding(si_desc[:300])

            for j in range(i + 1, n):
                sj = skills[j]
                sj_id = sj.get("id", "")
                if sj_id in processed:
                    continue
                mj = sj.get("metadata") or {}
                sj_triggers = set(t.lower() for t in mj.get("triggers", []))
                sj_desc = mj.get("description") or sj.get("content", "")
                sj_vec = _get_embedding(sj_desc[:300])

                desc_sim = (
                    _cosine_similarity(si_vec, sj_vec)
                    if si_vec and sj_vec else 0.0
                )
                union = si_triggers | sj_triggers
                jaccard = len(si_triggers & sj_triggers) / len(union) if union else 0.0

                if desc_sim > 0.75 or jaccard > 0.5:
                    merged = self._llm_merge_skills(mi, mj)
                    if merged:
                        for sid in [si_id, sj_id]:
                            if sid:
                                self.brain.update_status(sid, "deprecated")
                                processed.add(sid)
                        new_id = self._store_skill(merged)
                        if new_id:
                            merged_ids.append(new_id)
                        # only exit inner loop after a successful merge; if merge
                        # failed (LLM returned None) keep searching for other pairs
                        break

        return merged_ids

    def _llm_merge_skills(
        self, s1: dict[str, Any], s2: dict[str, Any]
    ) -> dict[str, Any] | None:
        prompt = f"""将以下两个相似技能合并为一个更强的技能。返回纯 JSON。

技能1：{json.dumps(s1, ensure_ascii=False)[:400]}
技能2：{json.dumps(s2, ensure_ascii=False)[:400]}

返回合并后的技能 JSON（格式同上，新增 merged_from: [name1, name2]）。只返回 JSON。"""

        result = _call_evolution_llm(prompt, max_tokens=600)
        if result:
            parsed = _parse_llm_json(result)
            if isinstance(parsed, dict) and "name" in parsed:
                parsed.setdefault("source", "l3_merge")
                parsed.setdefault("version", 1)
                parsed.setdefault("status", "active")
                parsed.setdefault("usage_count", 0)
                parsed.setdefault("success_count", 0)
                return parsed

        # Rule fallback
        return {
            "name": f"merged_{s1.get('name', 'skill')}",
            "description": (s1.get("description", "") + " / " + s2.get("description", ""))[:200],
            "triggers": list(set(s1.get("triggers", []) + s2.get("triggers", []))),
            "procedure": s1.get("procedure", ""),
            "guardrails": s1.get("guardrails", ""),
            "success_criteria": s1.get("success_criteria", ""),
            "confidence": (s1.get("confidence", 0.5) + s2.get("confidence", 0.5)) / 2,
            "topic": s1.get("topic", "general"),
            "merged_from": [s1.get("name", ""), s2.get("name", "")],
            "source": "l3_merge_rule",
            "version": 1,
            "status": "active",
            "usage_count": 0,
            "success_count": 0,
        }

    def _deprecate_skills(self, skills: list[dict[str, Any]]) -> list[str]:
        """Deprecate stale or consistently low-performing skills."""
        now = datetime.now(timezone.utc)
        deprecated_ids: list[str] = []

        for skill in skills:
            meta = skill.get("metadata") or {}
            usage = meta.get("usage_count", 0)
            success = meta.get("success_count", 0)
            success_rate = success / usage if usage > 0 else 0.0

            last_str = skill.get("updated_at") or skill.get("created_at", "")
            try:
                last_dt = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
                age_days = (now - last_dt).total_seconds() / 86400
            except Exception:
                age_days = 9999

            cond1 = age_days >= 30 and usage < 3
            cond2 = usage >= 5 and success_rate < 0.3

            if cond1 or cond2:
                sid = skill.get("id")
                if sid:
                    self.brain.update_status(sid, "deprecated")
                    deprecated_ids.append(sid)
                    reason = "stale" if cond1 else "low_success"
                    logger.info(
                        "L3 deprecated %s (reason=%s usage=%d rate=%.2f)",
                        sid[:8], reason, usage, success_rate,
                    )

        return deprecated_ids

    def _promote_skills(self, skills: list[dict[str, Any]]) -> list[str]:
        """Promote: usage >= 10 + success_rate >= 0.7 → agent→desk→role."""
        ns_order = ["agent", "desk", "role"]
        promoted_ids: list[str] = []

        for skill in skills:
            meta = skill.get("metadata") or {}
            usage = meta.get("usage_count", 0)
            success = meta.get("success_count", 0)
            success_rate = success / usage if usage > 0 else 0.0

            if usage >= 10 and success_rate >= 0.7:
                current_ns = skill.get("namespace", "agent")
                if current_ns in ns_order:
                    idx = ns_order.index(current_ns)
                    if idx < len(ns_order) - 1:
                        new_ns = ns_order[idx + 1]
                        sid = skill.get("id")
                        if sid:
                            self.brain.update_namespace(sid, new_ns)
                            promoted_ids.append(sid)
                            logger.info(
                                "L3 promoted %s: %s → %s",
                                sid[:8], current_ns, new_ns,
                            )

        return promoted_ids

    def _detect_semantic_drift(
        self, skills: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect drift between skill description and source experiences."""
        alerts: list[dict[str, Any]] = []

        for skill in skills:
            sid = skill.get("id")
            if not sid:
                continue
            meta = skill.get("metadata") or {}
            topic = meta.get("topic", "general")
            desc = meta.get("description") or skill.get("content", "")
            skill_vec = _get_embedding(desc[:300])
            if not skill_vec:
                continue

            source_exps = self.brain.get_entries(layer="l1", entry_type="experience", limit=20)
            topic_exps = [
                e for e in source_exps
                if (e.get("metadata") or {}).get("topic") == topic
            ]
            if not topic_exps:
                continue

            dists: list[float] = []
            for exp in topic_exps[:5]:
                ev = _get_embedding(exp.get("content", "")[:200])
                if ev:
                    dists.append(1.0 - _cosine_similarity(skill_vec, ev))

            if not dists:
                continue
            avg_drift = sum(dists) / len(dists)

            if avg_drift > 0.6:
                new_conf = (skill.get("confidence") or 0.5) * 0.7
                self.brain.update_confidence(sid, new_conf)
                alerts.append({"skill_id": sid, "drift": round(avg_drift, 3), "action": "confidence_reduced"})
                logger.warning("L3 drift >0.6: skill %s drift=%.2f → conf reduced", sid[:8], avg_drift)
            elif avg_drift > 0.4:
                alerts.append({"skill_id": sid, "drift": round(avg_drift, 3), "action": "warning"})
                logger.info("L3 drift warning: skill %s drift=%.2f", sid[:8], avg_drift)

        return alerts

    # ── L4: User Model ────────────────────────────────────────────────────────

    def user_model_update(
        self, conversation: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """L4: Analyze recent experiences → update multi-dim user profile."""
        recent_exps = self.brain.get_entries(layer="l1", entry_type="experience", limit=20)
        if not recent_exps:
            logger.debug("L4: no experiences to analyze")
            return {}

        exp_text = "\n".join(
            f"- [{(e.get('metadata') or {}).get('topic', '?')}] {e.get('content', '')[:150]}"
            for e in recent_exps[:15]
        )
        prompt = f"""分析以下用户对话经验，生成用户画像。返回纯 JSON。

经验记录：
{exp_text}

返回 JSON 格式：
{{
  "communication_style": "用户沟通风格（简洁/详细/技术/非技术 等）",
  "expertise_level": "专业水平（novice/intermediate/expert）",
  "decision_patterns": "决策模式（如：数据驱动/直觉/协商）",
  "recurring_topics": ["常见话题1", "常见话题2"],
  "working_context": "工作背景（如：创业CEO/产品经理/技术负责人）",
  "confidence": 0.0
}}

只返回 JSON。"""

        profile: dict[str, Any] = {}
        # L4 needs deep understanding — skip local, go straight to cloud
        result = _call_evolution_llm(prompt, max_tokens=400, skip_local=True)
        if result:
            parsed = _parse_llm_json(result)
            if isinstance(parsed, dict) and "communication_style" in parsed:
                profile = parsed

        if not profile:
            profile = self._rule_user_profile(recent_exps)

        self._store_user_trait(profile)
        return profile

    def _rule_user_profile(self, experiences: list[dict[str, Any]]) -> dict[str, Any]:
        topic_freq: dict[str, int] = {}
        for exp in experiences:
            t = (exp.get("metadata") or {}).get("topic", "general")
            topic_freq[t] = topic_freq.get(t, 0) + 1
        top_topics = [t for t, _ in sorted(topic_freq.items(), key=lambda x: -x[1])[:5]]
        complex_count = sum(
            1 for e in experiences
            if (e.get("metadata") or {}).get("complexity") == "complex"
        )
        expertise = "expert" if complex_count > len(experiences) * 0.5 else "intermediate"
        return {
            "communication_style": "详细",
            "expertise_level": expertise,
            "decision_patterns": "unknown",
            "recurring_topics": top_topics,
            "working_context": "unknown",
            "confidence": 0.3,
        }

    def _store_user_trait(self, profile: dict[str, Any]) -> str:
        desc = (
            f"用户画像: {profile.get('communication_style', '')} | "
            f"{profile.get('expertise_level', '')} | "
            f"{', '.join((profile.get('recurring_topics') or [])[:3])}"
        )
        existing = self.brain.get_entries(layer="l4", entry_type="user_trait", limit=1)
        if existing:
            entry_id = existing[0]["id"]
            self.brain.update_metadata(entry_id, profile)
            self.brain.update_confidence(entry_id, profile.get("confidence", 0.5))
            with self.brain._lock:
                self.brain.conn.execute(
                    "UPDATE leaper_brain SET content = ?, updated_at = ? WHERE id = ?",
                    (desc, _now(), entry_id),
                )
                self.brain.conn.commit()
            logger.info("L4 updated user_trait: %s", entry_id[:8])
            return entry_id
        return self.brain.learn(
            content=desc,
            source="evolution_l4",
            namespace="user_model",
            layer="l4",
            entry_type="user_trait",
            confidence=profile.get("confidence", 0.5),
            metadata=profile,
        )

    def inject_user_model_to_prompt(self, min_confidence: float = 0.5) -> str:
        """Return high-confidence user traits formatted for context injection."""
        traits = self.brain.get_entries(layer="l4", entry_type="user_trait", limit=3)
        if not traits:
            return ""
        lines: list[str] = ["[用户画像]"]
        for trait in traits:
            conf = trait.get("confidence", 0)
            if conf < min_confidence:
                continue
            meta = trait.get("metadata") or {}
            parts = [
                x for x in [
                    meta.get("communication_style"),
                    meta.get("expertise_level"),
                    ", ".join((meta.get("recurring_topics") or [])[:3]),
                    meta.get("working_context"),
                ]
                if x and x not in ("unknown", "")
            ]
            if parts:
                lines.append(f"- {' | '.join(parts)} (置信度: {conf:.1f})")
        return "\n".join(lines) if len(lines) > 1 else ""

    # ── L5: Validation ────────────────────────────────────────────────────────

    def validate(self, skill: dict[str, Any] | None = None) -> dict[str, Any]:
        """L5: Consistency check, regression test, time decay."""
        consistency_issues = self._check_consistency()
        regression_issues = self._check_regression()
        decayed = self._apply_time_decay()

        logger.info(
            "L5 validate: consistency=%d regression=%d decayed=%d",
            len(consistency_issues), len(regression_issues), decayed,
        )
        return {
            "consistency_issues": consistency_issues,
            "regression_issues": regression_issues,
            "decayed_count": decayed,
            "pass": len(consistency_issues) == 0 and len(regression_issues) == 0,
        }

    def _check_consistency(self) -> list[dict[str, Any]]:
        """LLM detects contradictions within same-topic skill groups."""
        skills = self.brain.get_entries(layer="l2", entry_type="skill", status="active")
        if not skills:
            return []

        topic_groups: dict[str, list[dict[str, Any]]] = {}
        for skill in skills:
            topic = (skill.get("metadata") or {}).get("topic", "general")
            topic_groups.setdefault(topic, []).append(skill)

        issues: list[dict[str, Any]] = []
        for topic, group in topic_groups.items():
            if len(group) < 2:
                continue
            summaries = "\n".join(
                f"- [{s.get('id', '')[:8]}] {s.get('content', '')[:150]}"
                for s in group[:6]
            )
            prompt = f"""检查以下 {topic} 主题技能是否存在矛盾。返回纯 JSON。

技能列表：
{summaries}

返回：{{"has_contradiction": false, "contradictions": []}}
只返回 JSON。"""
            result = _call_evolution_llm(prompt, max_tokens=300)
            if result:
                parsed = _parse_llm_json(result)
                if isinstance(parsed, dict) and parsed.get("has_contradiction"):
                    for c in parsed.get("contradictions", []):
                        issues.append({"topic": topic, **c})

        return issues

    def _check_regression(self) -> list[dict[str, Any]]:
        """Verify skill triggers still match source experiences (version > 1)."""
        skills = self.brain.get_entries(layer="l2", entry_type="skill", status="active")
        issues: list[dict[str, Any]] = []

        for skill in skills:
            meta = skill.get("metadata") or {}
            triggers = meta.get("triggers", [])
            topic = meta.get("topic", "general")
            if not triggers:
                continue

            source_exps = self.brain.get_entries(layer="l1", entry_type="experience", limit=20)
            topic_exps = [
                e for e in source_exps
                if (e.get("metadata") or {}).get("topic") == topic
            ]
            if not topic_exps:
                continue

            matched = sum(
                1 for e in topic_exps
                if any(t.lower() in e.get("content", "").lower() for t in triggers)
            )
            match_rate = matched / len(topic_exps)

            if match_rate < 0.3:
                issues.append({
                    "skill_id": skill.get("id", ""),
                    "topic": topic,
                    "trigger_match_rate": round(match_rate, 3),
                    "issue": "trigger match rate below threshold",
                })
                logger.warning(
                    "L5 regression: skill %s match_rate=%.2f",
                    skill.get("id", "")[:8], match_rate,
                )

        return issues

    def _apply_time_decay(self) -> int:
        """Apply confidence decay: 30d ×0.9, 90d ×0.7."""
        now = datetime.now(timezone.utc)
        all_entries = self.brain.get_entries(status="active", limit=500)
        decayed = 0

        for entry in all_entries:
            last_str = entry.get("updated_at") or entry.get("created_at", "")
            try:
                last_dt = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
                age_days = (now - last_dt).total_seconds() / 86400
            except Exception:
                continue

            conf = entry.get("confidence", 0.5) or 0.5
            if age_days >= 90:
                new_conf = conf * 0.7
            elif age_days >= 30:
                new_conf = conf * 0.9
            else:
                continue

            if new_conf < conf - 0.001:
                self.brain.update_confidence(entry["id"], new_conf)
                decayed += 1

        return decayed


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _smart_keywords(text: str) -> list[str]:
    try:
        import jieba
        words = jieba.cut(text, cut_all=False)
        stopwords = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
            "都", "一", "个", "上", "也", "很", "到", "说", "要", "去",
            "你", "会", "着", "没有", "看", "好", "自己", "这", "那",
            "什么", "可以", "他", "她", "它", "们", "吗", "呢", "吧",
            "啊", "哦", "嗯", "对", "但", "而", "所以", "因为", "如果",
        }
        tokens = [
            w.strip().lower() for w in words
            if len(w.strip()) >= 2 and w.strip() not in stopwords
        ]
    except ImportError:
        tokens = [t.lower() for t in re.findall(r"[a-zA-Z一-鿿]{2,}", text)]

    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:15]


def _smart_summary(text: str) -> str:
    sentences = re.split(r"[。！？\n.!?]", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 10]
    if not sentences:
        return _truncate(text, 200)
    # Take first 2-3 sentences up to 200 chars for richer context
    result = sentences[0]
    for s in sentences[1:3]:
        if len(result) + len(s) + 1 < 200:
            result += "。" + s
        else:
            break
    return _truncate(result, 200)


_TOPIC_MAP = {
    "融资": "融资", "funding": "融资", "valuation": "融资", "investor": "融资",
    "runway": "融资", "burn": "融资", "series": "融资", "raise": "融资",
    "团队": "团队", "team": "团队", "hire": "团队", "recruit": "团队",
    "裁": "团队", "firing": "团队", "cofounder": "团队",
    "产品": "产品", "product": "产品", "pmf": "产品", "mvp": "产品",
    "feature": "产品", "roadmap": "产品", "用户": "产品",
    "技术": "技术", "tech": "技术", "architecture": "技术", "infra": "技术",
    "api": "技术", "model": "技术",
    "营销": "营销", "marketing": "营销", "growth": "营销", "cac": "营销",
    "ltv": "营销", "acquisition": "营销",
    "战略": "战略", "strategy": "战略", "pivot": "战略", "competitive": "战略",
    "竞争": "战略", "market": "战略",
    "心理": "创始人心理", "焦虑": "创始人心理", "压力": "创始人心理",
    "anxiety": "创始人心理", "stress": "创始人心理", "burnout": "创始人心理",
    "sleep": "创始人心理",
}


def _infer_topic(keywords: list[str], user_msg: str) -> str:
    """Infer topic from keywords and user message."""
    combined = " ".join(keywords).lower() + " " + user_msg.lower()
    topic_scores: dict[str, int] = {}
    for trigger, topic in _TOPIC_MAP.items():
        if trigger in combined:
            topic_scores[topic] = topic_scores.get(topic, 0) + 1
    if topic_scores:
        return max(topic_scores, key=topic_scores.get)
    return "general"


def _estimate_complexity(text: str) -> str:
    chars = len(text)
    words = len(text.split())
    if chars >= 200 or words >= 100:
        return "complex"
    if chars >= 30 or words >= 20:
        return "moderate"
    return "trivial"


def _truncate(text: str, n: int) -> str:
    return text[:n] + "…" if len(text) > n else text
