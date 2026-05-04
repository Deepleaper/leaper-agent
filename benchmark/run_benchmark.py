"""Leaper Agent — 六层进化记忆引擎 Benchmark
运行方式: python benchmark/run_benchmark.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import traceback
from typing import Any
from unittest.mock import MagicMock, patch

# ── ensure project root on path ──────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── force UTF-8 on Windows ───────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ── pretty table ─────────────────────────────────────────────────────────────

def _table(rows: list[tuple[str, int, int, str]]) -> str:
    lines = []
    w = [30, 6, 7, 40]
    sep = "+" + "+".join("-" * (c + 2) for c in w) + "+"
    def row_line(cells, widths):
        return "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)) + " |"
    lines.append(sep)
    lines.append(row_line(["Dimension", "Score", "Max", "Notes"], w))
    lines.append(sep)
    for name, score, max_score, note in rows:
        lines.append(row_line([name, score, max_score, note[:38]], w))
    lines.append(sep)
    return "\n".join(lines)


# ── mock helpers ──────────────────────────────────────────────────────────────

def _make_extraction_json(**overrides) -> str:
    base = {
        "summary": "用户询问融资策略，助手提供了详细的A轮融资路线图",
        "keywords": ["融资", "A轮", "投资人"],
        "task_success": True,
        "complexity": "complex",
        "user_intent": "了解A轮融资的最佳时机和策略",
        "topic": "融资",
        "successful_strategy": "给出清晰的融资里程碑和投资人接触顺序",
        "failure_recovery": None,
        "efficiency_tip": "先联系战略投资人建立信任",
        "new_knowledge": "A轮融资通常需要3-6个月，建议提前准备数据室和财务模型",
        "claim_type": "inference",
        "evidence": "用户明确表示正在准备A轮，当前ARR 200万",
    }
    base.update(overrides)
    return json.dumps(base, ensure_ascii=False)


def _make_skill_json(**overrides) -> str:
    base = {
        "title": "A轮融资准备技能",
        "name": "A轮融资准备技能",
        "description": "系统化准备A轮融资，包含数据室准备、投资人接触策略和谈判技巧的完整流程",
        "triggers": ["融资", "A轮", "investor", "raise"],
        "procedure": "1. 准备财务模型 2. 建立数据室 3. 接触战略投资人 4. Term sheet谈判",
        "guardrails": "不承诺具体估值，保持多条线并行",
        "success_criteria": "收到2个以上term sheet",
        "confidence": 0.75,
    }
    base.update(overrides)
    return json.dumps(base, ensure_ascii=False)


def _make_user_model_json(**overrides) -> str:
    base = {
        "communication_style": "直接简洁，偏好数据驱动的决策建议",
        "expertise_level": "expert",
        "decision_patterns": "数据驱动，快速迭代，风险可控",
        "recurring_topics": ["融资", "产品", "团队"],
        "working_context": "初创公司CEO",
        "confidence": 0.8,
    }
    base.update(overrides)
    return json.dumps(base, ensure_ascii=False)


def _make_mock_llm_response(text: str):
    """Return a mock OpenAI-style response object."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ════════════════════════════════════════════════════════════════════════════
# D1: L1 Experience Extract
# ════════════════════════════════════════════════════════════════════════════

def run_d1() -> tuple[int, str]:
    score = 0
    notes = []
    try:
        from agent.leaper_brain import LeaperBrain
        from agent.leaper_evolution import EvolutionEngine, _call_evolution_llm

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        brain = LeaperBrain(db_path)
        engine = EvolutionEngine(brain)

        user_msg = "我们公司正在准备A轮融资，当前ARR 200万，应该怎么准备？"
        assistant_msg = "A轮融资建议：1. 准备详细财务模型 2. 建立数据室 3. 提前3-6个月接触投资人，先从战略投资人开始"

        # Test 1: basic extraction returns dict with required fields
        with patch("agent.leaper_evolution._call_evolution_llm", return_value=_make_extraction_json()):
            exp = engine.experience_extract(user_msg, assistant_msg)

        if isinstance(exp, dict):
            score += 2
            notes.append("returns dict")
        else:
            notes.append("FAIL: not a dict")
            brain.close()
            return score, "; ".join(notes)

        # Test 2: 4-dim fields present
        dim_fields = ["successful_strategy", "failure_recovery", "efficiency_tip", "new_knowledge"]
        present = [f for f in dim_fields if f in exp]
        if len(present) >= 3:
            score += 2
            notes.append("4-dim fields ok")
        else:
            notes.append(f"4-dim partial ({len(present)}/4)")

        # Test 3: Gate1 — trivial is rejected
        trivial_json = _make_extraction_json(complexity="trivial", summary="ok")
        with patch("agent.leaper_evolution._call_evolution_llm", return_value=trivial_json):
            trivial_exp = engine.experience_extract("hi", "hello")
        if trivial_exp.get("_skip_store"):
            score += 2
            notes.append("gate1 trivial ok")
        else:
            notes.append("gate1 fail")

        # Test 4: Gate3 — short summary rejected
        short_json = _make_extraction_json(summary="short", complexity="moderate")
        with patch("agent.leaper_evolution._call_evolution_llm", return_value=short_json):
            short_exp = engine.experience_extract("test", "test reply")
        if short_exp.get("_skip_store"):
            score += 2
            notes.append("gate3 short-summary ok")
        else:
            notes.append("gate3 fail")

        # Test 5: store_experience writes to DB
        exp_nonskip = dict(exp)
        exp_nonskip.pop("_skip_store", None)
        eid = engine.store_experience(exp_nonskip)
        if eid:
            score += 2
            notes.append("store_experience ok")
        else:
            notes.append("store returned empty")

        brain.close()

    except NotImplementedError:
        notes.append("PLACEHOLDER — 0 pts")
        return 0, "; ".join(notes)
    except Exception as e:
        notes.append(f"ERROR: {e}")
        traceback.print_exc()

    return score, "; ".join(notes)


# ════════════════════════════════════════════════════════════════════════════
# D2: L2 Skill Generate
# ════════════════════════════════════════════════════════════════════════════

def run_d2() -> tuple[int, str]:
    score = 0
    notes = []
    try:
        from agent.leaper_brain import LeaperBrain
        from agent.leaper_evolution import EvolutionEngine

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        brain = LeaperBrain(db_path)
        engine = EvolutionEngine(brain)

        # Seed 5 experiences with same topic
        exp_contents = [
            "用户询问A轮融资策略，助手建议提前准备数据室和财务模型\nUser intent: 融资时机\nStrategy: 数据驱动谈判",
            "讨论投资人接触顺序，建议先联系战略投资人建立信任\nUser intent: 投资人关系\nStrategy: 战略优先",
            "分析融资材料准备，重点在于ARR增长曲线和单位经济模型\nUser intent: 材料准备\nKnowledge: 投资人看重LTV/CAC比率",
            "用户面临down round风险，助手分析了防稀释条款的谈判策略\nUser intent: 融资条款\nStrategy: 保留优先清算权",
            "Series A估值讨论，基于可比公司分析给出合理区间\nUser intent: 估值方法\nKnowledge: 通常5-10x ARR",
        ]
        for content in exp_contents:
            brain.learn(
                content=content,
                layer="l1",
                entry_type="experience",
                namespace="experience",
                metadata={"topic": "融资", "keywords": ["融资", "A轮", "investor"], "complexity": "complex"},
            )

        # Mock: embedding returns None (forces rule-based clustering = one cluster)
        # Mock: LLM returns valid skill JSON
        with patch("agent.leaper_evolution._get_embedding", return_value=None), \
             patch("agent.leaper_evolution._call_evolution_llm", return_value=_make_skill_json()):
            skills = engine.skill_generate()

        # Test 1: returns list
        if isinstance(skills, list):
            score += 2
            notes.append("returns list")
        else:
            notes.append("FAIL: not a list")
            brain.close()
            return score, "; ".join(notes)

        # Test 2: at least one skill generated
        if len(skills) >= 1:
            score += 2
            notes.append(f"{len(skills)} skill(s) generated")
        else:
            notes.append("no skills generated")

        # Test 3: skill stored in DB
        db_skills = brain.get_entries(layer="l2", entry_type="skill")
        if db_skills:
            score += 2
            notes.append("skill in DB")
        else:
            notes.append("skill not in DB")

        # Test 4: backtrace validate directly
        skill_dict = {
            "name": "融资技能",
            "description": "A轮融资准备和投资人接触策略",
            "triggers": ["融资", "investor"],
            "confidence": 0.7,
        }
        exps = brain.get_entries(layer="l1", entry_type="experience")
        with patch("agent.leaper_evolution._get_embedding", return_value=None):
            bt = engine._backtrace_validate(skill_dict, exps)
        if isinstance(bt, bool):
            score += 2
            notes.append(f"backtrace={bt}")
        else:
            notes.append("backtrace not bool")

        # Test 5: insufficient experiences returns []
        empty_brain = LeaperBrain(tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
        empty_engine = EvolutionEngine(empty_brain)
        result = empty_engine.skill_generate([])
        if result == []:
            score += 2
            notes.append("empty input → []")
        else:
            notes.append("empty input not []")
        empty_brain.close()

        brain.close()

    except NotImplementedError:
        notes.append("PLACEHOLDER — 0 pts")
        return 0, "; ".join(notes)
    except Exception as e:
        notes.append(f"ERROR: {e}")
        traceback.print_exc()

    return score, "; ".join(notes)


# ════════════════════════════════════════════════════════════════════════════
# D3: L3 Skill Evolve
# ════════════════════════════════════════════════════════════════════════════

def run_d3() -> tuple[int, str]:
    score = 0
    notes = []
    try:
        from agent.leaper_brain import LeaperBrain
        from agent.leaper_evolution import EvolutionEngine
        from datetime import datetime, timezone, timedelta

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        brain = LeaperBrain(db_path)
        engine = EvolutionEngine(brain)

        # Test 1: empty skills → returns empty result dict
        with patch("agent.leaper_evolution._get_embedding", return_value=None):
            result = engine.skill_evolve([])
        expected_keys = {"merged", "deprecated", "promoted", "drift_alerts"}
        if isinstance(result, dict) and expected_keys.issubset(result.keys()):
            score += 2
            notes.append("empty → result dict ok")
        else:
            notes.append(f"FAIL: result keys={list(result.keys()) if isinstance(result, dict) else result}")

        # Test 2: deprecate stale skill (age>=30d, usage<3)
        # Insert a "stale" skill with old timestamp via direct SQL
        old_ts = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        stale_id = brain.learn(
            content="旧技能描述",
            layer="l2",
            entry_type="skill",
            namespace="agent",
            metadata={"usage_count": 1, "success_count": 0, "topic": "融资", "triggers": ["融资"]},
        )
        # Backdate it
        with brain._lock:
            brain.conn.execute(
                "UPDATE leaper_brain SET updated_at = ?, created_at = ? WHERE id = ?",
                (old_ts, old_ts, stale_id),
            )
            brain.conn.commit()

        stale_skill = brain.get_entries(layer="l2", entry_type="skill")[0]
        with patch("agent.leaper_evolution._get_embedding", return_value=None):
            result2 = engine.skill_evolve([stale_skill])
        if stale_id in result2.get("deprecated", []):
            score += 3
            notes.append("stale deprecation ok")
        else:
            notes.append("stale not deprecated")

        # Test 3: promote skill (usage>=10, success_rate>=0.7)
        promote_id = brain.learn(
            content="高使用率技能",
            layer="l2",
            entry_type="skill",
            namespace="agent",
            metadata={"usage_count": 15, "success_count": 12, "topic": "产品", "triggers": ["产品"]},
        )
        promote_skill = brain.get_entries(layer="l2", entry_type="skill", namespace="agent")
        promote_skill = [s for s in promote_skill if s["id"] == promote_id]
        if promote_skill:
            with patch("agent.leaper_evolution._get_embedding", return_value=None):
                result3 = engine.skill_evolve(promote_skill)
            if promote_id in result3.get("promoted", []):
                score += 3
                notes.append("promotion ok")
            else:
                notes.append("promotion not triggered")
        else:
            notes.append("promote skill not found")

        # Test 4: merge call structure (with mocked LLM + embeddings)
        merged_json = json.dumps({
            "name": "merged_skill",
            "description": "合并后的融资和产品技能，涵盖核心业务场景",
            "triggers": ["融资", "产品"],
            "procedure": "步骤1 步骤2",
            "confidence": 0.7,
            "merged_from": ["融资技能", "产品技能"],
        }, ensure_ascii=False)

        skill_a_id = brain.learn(
            content="融资策略技能描述内容",
            layer="l2", entry_type="skill", namespace="agent",
            metadata={"usage_count": 2, "success_count": 1, "topic": "融资",
                      "triggers": ["融资", "A轮"], "description": "融资策略"},
        )
        skill_b_id = brain.learn(
            content="融资执行技能描述内容",
            layer="l2", entry_type="skill", namespace="agent",
            metadata={"usage_count": 2, "success_count": 1, "topic": "融资",
                      "triggers": ["融资", "投资人"], "description": "融资执行"},
        )
        skills_ab = [s for s in brain.get_entries(layer="l2", entry_type="skill")
                     if s["id"] in (skill_a_id, skill_b_id)]

        fake_vec = [0.1] * 768
        with patch("agent.leaper_evolution._get_embedding", return_value=fake_vec), \
             patch("agent.leaper_evolution._call_evolution_llm", return_value=merged_json):
            result4 = engine.skill_evolve(skills_ab)

        if result4.get("merged"):
            score += 2
            notes.append("merge triggered")
        else:
            notes.append("merge not triggered (may need higher cosine)")

        brain.close()

    except NotImplementedError:
        notes.append("PLACEHOLDER — 0 pts")
        return 0, "; ".join(notes)
    except Exception as e:
        notes.append(f"ERROR: {e}")
        traceback.print_exc()

    return score, "; ".join(notes)


# ════════════════════════════════════════════════════════════════════════════
# D4: L4 User Profile
# ════════════════════════════════════════════════════════════════════════════

def run_d4() -> tuple[int, str]:
    score = 0
    notes = []
    try:
        from agent.leaper_brain import LeaperBrain
        from agent.leaper_evolution import EvolutionEngine

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        brain = LeaperBrain(db_path)
        engine = EvolutionEngine(brain)

        # Seed experiences
        for i in range(8):
            topic = "融资" if i < 4 else "产品"
            brain.learn(
                content=f"用户{i}讨论{topic}问题，深入分析了市场竞争格局和用户增长策略",
                layer="l1",
                entry_type="experience",
                namespace="experience",
                metadata={"topic": topic, "complexity": "complex"},
            )

        # Test 1: no experiences → empty dict
        empty_brain = LeaperBrain(tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
        empty_engine = EvolutionEngine(empty_brain)
        result_empty = empty_engine.user_model_update()
        if result_empty == {}:
            score += 2
            notes.append("no-exp → {} ok")
        else:
            notes.append("no-exp result non-empty")
        empty_brain.close()

        # Test 2: LLM path returns profile with required fields
        with patch("agent.leaper_evolution._call_evolution_llm", return_value=_make_user_model_json()):
            profile = engine.user_model_update()

        req = ["communication_style", "expertise_level", "decision_patterns", "recurring_topics"]
        if isinstance(profile, dict) and all(k in profile for k in req):
            score += 3
            notes.append("profile fields ok")
        else:
            notes.append(f"profile missing fields: {[k for k in req if k not in profile]}")

        # Test 3: expertise_level valid enum
        if profile.get("expertise_level") in ("novice", "intermediate", "expert"):
            score += 2
            notes.append("expertise valid")
        else:
            notes.append(f"expertise invalid: {profile.get('expertise_level')}")

        # Test 4: stored in DB as user_trait
        traits = brain.get_entries(layer="l4", entry_type="user_trait")
        if traits:
            score += 2
            notes.append("user_trait stored")
        else:
            notes.append("user_trait not in DB")

        # Test 5: rule fallback works (LLM returns None)
        with patch("agent.leaper_evolution._call_evolution_llm", return_value=None):
            profile2 = engine.user_model_update()
        if isinstance(profile2, dict) and profile2.get("expertise_level"):
            score += 1
            notes.append("rule fallback ok")
        else:
            notes.append("rule fallback fail")

        brain.close()

    except NotImplementedError:
        notes.append("PLACEHOLDER — 0 pts")
        return 0, "; ".join(notes)
    except Exception as e:
        notes.append(f"ERROR: {e}")
        traceback.print_exc()

    return score, "; ".join(notes)


# ════════════════════════════════════════════════════════════════════════════
# D5: L5 Validate
# ════════════════════════════════════════════════════════════════════════════

def run_d5() -> tuple[int, str]:
    score = 0
    notes = []
    try:
        from agent.leaper_brain import LeaperBrain
        from agent.leaper_evolution import EvolutionEngine
        from datetime import datetime, timezone, timedelta

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        brain = LeaperBrain(db_path)
        engine = EvolutionEngine(brain)

        # Test 1: empty DB → validate returns expected structure
        with patch("agent.leaper_evolution._call_evolution_llm", return_value='{"has_contradiction": false, "contradictions": []}'):
            result = engine.validate()
        expected = {"consistency_issues", "regression_issues", "decayed_count", "pass"}
        if isinstance(result, dict) and expected.issubset(result.keys()):
            score += 2
            notes.append("validate structure ok")
        else:
            notes.append(f"validate bad structure: {list(result.keys()) if isinstance(result, dict) else result}")

        # Test 2: time decay — entry >90d old should be decayed
        old_ts = (datetime.now(timezone.utc) - timedelta(days=95)).isoformat()
        eid = brain.learn(content="旧知识，可能已过期", layer="l1", entry_type="experience",
                          confidence=0.8, namespace="experience")
        with brain._lock:
            brain.conn.execute(
                "UPDATE leaper_brain SET updated_at=?, created_at=? WHERE id=?",
                (old_ts, old_ts, eid),
            )
            brain.conn.commit()

        with patch("agent.leaper_evolution._call_evolution_llm", return_value='{"has_contradiction": false, "contradictions": []}'):
            result2 = engine.validate()

        if result2.get("decayed_count", 0) >= 1:
            score += 3
            notes.append("time decay (90d×0.7) ok")
        else:
            notes.append("time decay not triggered")

        # Test 3: 30d decay
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f2:
            db2 = LeaperBrain(f2.name)
        e2 = EvolutionEngine(db2)
        mid_ts = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
        eid2 = db2.brain.learn(content="中等时间的知识条目", layer="l1",
                               entry_type="experience", confidence=0.8,
                               namespace="experience") if hasattr(db2, "brain") else \
               db2.learn(content="中等时间的知识条目", layer="l1",
                         entry_type="experience", confidence=0.8, namespace="experience")
        # db2 IS a LeaperBrain here
        with db2._lock:
            db2.conn.execute(
                "UPDATE leaper_brain SET updated_at=?, created_at=? WHERE id=?",
                (mid_ts, mid_ts, eid2),
            )
            db2.conn.commit()
        with patch("agent.leaper_evolution._call_evolution_llm", return_value='{"has_contradiction": false, "contradictions": []}'):
            result3 = e2.validate()
        if result3.get("decayed_count", 0) >= 1:
            score += 2
            notes.append("30d decay ok")
        else:
            notes.append("30d decay not triggered")
        db2.close()

        # Test 4: consistency check called (mocked LLM returns contradiction)
        skill_id = brain.learn(
            content="技能1: 建议早期激进扩张",
            layer="l2", entry_type="skill",
            namespace="agent",
            metadata={"topic": "战略", "triggers": ["扩张"]},
        )
        brain.learn(
            content="技能2: 建议保守谨慎增长",
            layer="l2", entry_type="skill",
            namespace="agent",
            metadata={"topic": "战略", "triggers": ["增长"]},
        )
        contradiction_resp = json.dumps({
            "has_contradiction": True,
            "contradictions": [{"desc": "激进扩张 vs 保守增长"}],
        })
        with patch("agent.leaper_evolution._call_evolution_llm", return_value=contradiction_resp):
            result4 = engine.validate()
        if result4.get("consistency_issues"):
            score += 3
            notes.append("contradiction detected ok")
        else:
            notes.append("contradiction not detected")

        brain.close()

    except NotImplementedError:
        notes.append("PLACEHOLDER — 0 pts")
        return 0, "; ".join(notes)
    except Exception as e:
        notes.append(f"ERROR: {e}")
        traceback.print_exc()

    return score, "; ".join(notes)


# ════════════════════════════════════════════════════════════════════════════
# D6: End-to-End (L0→L5, 20 rounds)
# ════════════════════════════════════════════════════════════════════════════

_SIMULATED_CONVOS = [
    ("如何制定A轮融资策略？", "建议先完成数据室准备，预计需要3个月时间"),
    ("团队核心成员离职怎么办？", "应立即进行知识转移和招聘补位，重点关注关键岗位的备份"),
    ("产品PMF如何验证？", "通过NPS调查和留存数据验证，目标是40%以上的用户认为不可替代"),
    ("融资材料如何准备？", "包含财务模型、市场分析、竞争格局、团队介绍四个核心模块"),
    ("如何应对投资人的due diligence？", "提前准备完整的法律文件和财务记录，设立专门的数据室"),
    ("产品路线图如何规划？", "基于用户调研和商业目标，按季度制定里程碑，保持灵活性"),
    ("如何建立技术团队？", "优先招募有创业经验的技术骨干，建立代码审查和CI/CD文化"),
    ("用户增长遇到瓶颈怎么办？", "分析用户旅程中的流失点，优化关键转化漏斗，尝试新的获客渠道"),
    ("如何管理投资人关系？", "定期发送月度更新邮件，及时分享坏消息，建立透明的沟通机制"),
    ("公司估值如何确定？", "基于可比公司乘数，结合ARR增长率和市场空间，通常5-15x ARR"),
    ("如何优化产品留存率？", "关注Aha moment的触达速度，优化onboarding流程，建立习惯养成机制"),
    ("联创关系出现分歧怎么处理？", "建立清晰的决策权边界，定期进行价值观对齐，必要时寻求第三方调解"),
    ("如何规划市场进入策略？", "从细分市场切入，建立标杆客户，通过口碑扩散到主流市场"),
    ("技术债如何管理？", "设立专门的技术债还债冲刺，保持20%开发时间用于基础设施优化"),
    ("如何激励核心团队？", "股权激励结合现金，建立透明的晋升通道，给予充分的自主权"),
    ("客户获取成本如何降低？", "优化内容营销和SEO，建立客户推荐计划，提升销售效率"),
    ("产品定价策略如何制定？", "基于价值定价而非成本加成，参考竞品和客户支付意愿"),
    ("如何应对竞争对手？", "聚焦差异化优势，提升产品壁垒，加速关键功能的开发迭代"),
    ("创始人心理压力如何缓解？", "建立创始人互助社群，保持规律运动，定期与心理咨询师沟通"),
    ("如何准备B轮融资？", "在A轮基础上，重点展示可重复的商业模式和规模化增长潜力"),
]


def run_d6() -> tuple[int, str]:
    score = 0
    notes = []
    try:
        from agent.leaper_brain import LeaperBrain
        from agent.leaper_evolution import EvolutionEngine

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        brain = LeaperBrain(db_path)
        engine = EvolutionEngine(brain)

        stored_count = 0

        # Run 20 conversation rounds
        for i, (user_msg, assistant_msg) in enumerate(_SIMULATED_CONVOS):
            # Vary complexity to pass gate1
            complexity = "complex" if i % 3 != 0 else "moderate"
            topic_map = {0: "融资", 1: "团队", 2: "产品", 3: "融资", 4: "融资",
                         5: "产品", 6: "团队", 7: "产品", 8: "融资", 9: "融资",
                         10: "产品", 11: "团队", 12: "战略", 13: "技术", 14: "团队",
                         15: "营销", 16: "产品", 17: "战略", 18: "创始人心理", 19: "融资"}
            topic = topic_map.get(i, "general")

            ext_json = _make_extraction_json(
                complexity=complexity,
                topic=topic,
                summary=f"第{i+1}轮: {user_msg[:40]}",
                new_knowledge=f"本轮关键知识: {assistant_msg[:60]}",
            )

            with patch("agent.leaper_evolution._call_evolution_llm", return_value=ext_json):
                exp = engine.experience_extract(user_msg, assistant_msg)

            if not exp.get("_skip_store"):
                eid = engine.store_experience(exp)
                if eid:
                    stored_count += 1

        # Test 1: meaningful experiences stored (>=10 of 20)
        if stored_count >= 10:
            score += 2
            notes.append(f"{stored_count}/20 stored")
        else:
            notes.append(f"only {stored_count}/20 stored")

        # Test 2: L2 skill generation from accumulated experiences
        with patch("agent.leaper_evolution._get_embedding", return_value=None), \
             patch("agent.leaper_evolution._call_evolution_llm", return_value=_make_skill_json()):
            skills = engine.skill_generate()

        if skills:
            score += 2
            notes.append(f"L2: {len(skills)} skill(s)")
        else:
            notes.append("L2: no skills")

        # Test 3: L3 evolve runs without error
        with patch("agent.leaper_evolution._get_embedding", return_value=None), \
             patch("agent.leaper_evolution._call_evolution_llm", return_value='{"name":"merged","description":"merged skill description with enough chars","triggers":[]}'):
            evo_result = engine.skill_evolve()

        if isinstance(evo_result, dict):
            score += 2
            notes.append("L3 ran ok")
        else:
            notes.append("L3 failed")

        # Test 4: L4 user profile synthesized
        with patch("agent.leaper_evolution._call_evolution_llm", return_value=_make_user_model_json()):
            profile = engine.user_model_update()

        if profile.get("expertise_level"):
            score += 2
            notes.append(f"L4: expertise={profile['expertise_level']}")
        else:
            notes.append("L4: no profile")

        # Test 5: L5 validate runs
        with patch("agent.leaper_evolution._call_evolution_llm",
                   return_value='{"has_contradiction": false, "contradictions": []}'):
            val_result = engine.validate()

        if isinstance(val_result, dict) and "pass" in val_result:
            score += 2
            notes.append(f"L5: pass={val_result['pass']}, decayed={val_result['decayed_count']}")
        else:
            notes.append("L5 validate failed")

        brain.close()

    except NotImplementedError:
        notes.append("PLACEHOLDER — 0 pts")
        return 0, "; ".join(notes)
    except Exception as e:
        notes.append(f"ERROR: {e}")
        traceback.print_exc()

    return score, "; ".join(notes)


# ════════════════════════════════════════════════════════════════════════════
# Main runner
# ════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 72)
    print("  Leaper Agent — 六层进化记忆引擎 Benchmark")
    print("=" * 72)

    dimensions = [
        ("D1: L1 经验提取",   run_d1, 10),
        ("D2: L2 技能合成",   run_d2, 10),
        ("D3: L3 知识整合",   run_d3, 10),
        ("D4: L4 用户画像",   run_d4, 10),
        ("D5: L5 元认知",     run_d5, 10),
        ("D6: 端到端进化",    run_d6, 10),
    ]

    rows = []
    total = 0
    max_total = 0

    for name, fn, max_score in dimensions:
        print(f"\n  Running {name}...")
        try:
            score, notes = fn()
        except Exception as e:
            score, notes = 0, f"CRASH: {e}"
        total += score
        max_total += max_score
        rows.append((name, score, max_score, notes))
        status = "✓" if score == max_score else ("△" if score > 0 else "✗")
        print(f"    {status} {score}/{max_score}  {notes}")

    print("\n" + "=" * 72)
    print(_table(rows))
    bar_filled = int(total / max_total * 40)
    bar = "█" * bar_filled + "░" * (40 - bar_filled)
    pct = total / max_total * 100
    print(f"\n  Total: {total}/{max_total}  [{bar}] {pct:.1f}%")

    grade = (
        "S (优秀)" if pct >= 90 else
        "A (良好)" if pct >= 75 else
        "B (合格)" if pct >= 60 else
        "C (待改进)" if pct >= 40 else
        "D (需重构)"
    )
    print(f"  Grade: {grade}")
    print("=" * 72 + "\n")

    return 0 if total >= max_total * 0.6 else 1


if __name__ == "__main__":
    sys.exit(main())
