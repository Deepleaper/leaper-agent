"""Test Knowledge State Runtime (v1.0.2) — end-to-end validation."""
import os
import sys
import tempfile

# Force a clean brain.db for testing
_test_dir = tempfile.mkdtemp()
_test_db = os.path.join(_test_dir, "brain.db")
os.environ["LEAPER_BRAIN_DB"] = _test_db

from agent.leaper_brain import LeaperBrain
from agent.leaper_evolution import EvolutionEngine

def test_schema_migration():
    """Test: new columns exist after init."""
    brain = LeaperBrain(db_path=_test_db)
    # Check columns
    cursor = brain.conn.execute("PRAGMA table_info(leaper_brain)")
    cols = {row[1] for row in cursor.fetchall()}
    required = {"evidence", "valid_from", "valid_until", "claim_type", "supersedes"}
    missing = required - cols
    assert not missing, f"Missing columns: {missing}"
    print("✅ Schema migration: all 5 KSR columns present")
    return brain

def test_learn_with_ksr_fields(brain):
    """Test: learn() accepts and stores KSR fields."""
    entry_id = brain.learn(
        content="Ray is CEO of Deepleaper",
        source="test",
        claim_type="fact",
        evidence="User said: I am the CEO of Deepleaper",
        valid_from="2026-04-30T00:00:00+00:00",
    )
    assert entry_id, "learn() returned empty id"
    
    # Read it back
    row = brain.conn.execute(
        "SELECT claim_type, evidence, valid_from, valid_until, supersedes FROM leaper_brain WHERE id = ?",
        (entry_id,)
    ).fetchone()
    assert row[0] == "fact", f"claim_type={row[0]}"
    assert "CEO" in row[1], f"evidence={row[1]}"
    assert row[2] is not None, "valid_from is None"
    assert row[3] is None, "valid_until should be None"
    assert row[4] is None, "supersedes should be None"
    print("✅ learn() stores KSR fields correctly")
    return entry_id

def test_supersedes(brain, old_id):
    """Test: supersedes marks old entry as 'superseded'."""
    new_id = brain.learn(
        content="Ray is CEO and Founder of Deepleaper",
        source="test",
        claim_type="fact",
        evidence="Updated info from conversation",
        supersedes=old_id,
    )
    # Check old entry status
    old_row = brain.conn.execute(
        "SELECT status, valid_until FROM leaper_brain WHERE id = ?", (old_id,)
    ).fetchone()
    assert old_row[0] == "superseded", f"old status={old_row[0]}"
    assert old_row[1] is not None, "old valid_until should be set"
    print("✅ supersedes: old entry marked superseded with valid_until")
    return new_id

def test_recall_filters_superseded(brain, old_id, new_id):
    """Test: recall does NOT return superseded entries."""
    results = brain.recall("Ray CEO Deepleaper", top_k=10)
    result_ids = [r["id"] for r in results]
    assert old_id not in result_ids, "Superseded entry should be filtered out"
    assert new_id in result_ids, "Active entry should be returned"
    print("✅ recall() filters out superseded entries")

def test_recall_filters_expired(brain):
    """Test: recall does NOT return expired entries."""
    expired_id = brain.learn(
        content="Temporary fact that expired",
        source="test",
        claim_type="fact",
        valid_until="2020-01-01T00:00:00+00:00",  # Already expired
    )
    results = brain.recall("Temporary fact expired", top_k=10)
    result_ids = [r["id"] for r in results]
    assert expired_id not in result_ids, "Expired entry should be filtered out"
    print("✅ recall() filters out expired entries (valid_until)")

def test_l1_extraction():
    """Test: L1 rule extraction includes claim_type and evidence."""
    brain = LeaperBrain(db_path=_test_db)
    evo = EvolutionEngine(brain)
    exp = evo._rule_experience_extract(
        "我是王冉，做AI情景智能的",
        "你好王冉！AI情景智能是很有前景的方向。"
    )
    assert "claim_type" in exp, "Missing claim_type in rule extract"
    assert exp["claim_type"] == "observation"
    assert "evidence" in exp, "Missing evidence in rule extract"
    print(f"✅ L1 rule extract: claim_type={exp['claim_type']}, evidence present")

def test_format_recall_shows_claim_type(brain):
    """Test: format_recall_for_prompt shows claim_type."""
    evo = EvolutionEngine(brain)
    prompt_text = evo.format_recall_for_prompt("Ray CEO")
    assert "fact" in prompt_text or "observation" in prompt_text, \
        f"claim_type not in prompt: {prompt_text[:200]}"
    assert "conf=" in prompt_text, f"confidence not in prompt: {prompt_text[:200]}"
    print("✅ format_recall_for_prompt shows claim_type + confidence")

def test_update_status_sets_valid_until(brain):
    """Test: deprecating an entry sets valid_until."""
    eid = brain.learn(content="Some skill to deprecate", source="test")
    brain.update_status(eid, "deprecated")
    row = brain.conn.execute(
        "SELECT valid_until FROM leaper_brain WHERE id = ?", (eid,)
    ).fetchone()
    assert row[0] is not None, "valid_until not set on deprecate"
    print("✅ update_status('deprecated') sets valid_until")

if __name__ == "__main__":
    print(f"Testing with DB: {_test_db}\n")
    brain = test_schema_migration()
    old_id = test_learn_with_ksr_fields(brain)
    new_id = test_supersedes(brain, old_id)
    test_recall_filters_superseded(brain, old_id, new_id)
    test_recall_filters_expired(brain)
    test_l1_extraction()
    test_format_recall_shows_claim_type(brain)
    test_update_status_sets_valid_until(brain)
    print(f"\n🎉 ALL 7 TESTS PASSED — Knowledge State Runtime v1.0.2 verified")
