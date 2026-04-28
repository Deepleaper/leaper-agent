import os, time
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'

# Test 1: topic inference
from agent.leaper_evolution import _infer_topic, _smart_summary, _estimate_complexity
print('=== Topic Inference ===')
tests = [
    (["funding", "series", "valuation"], "Should I raise Series C?", "融资"),
    (["team", "hire", "engineer"], "Should I hire a CTO?", "团队"),
    (["product", "pmf", "user"], "Have we found PMF yet?", "产品"),
    (["strategy", "pivot"], "Should we pivot?", "战略"),
    (["焦虑", "压力", "sleep"], "I can't sleep", "创始人心理"),
    (["hello", "thanks"], "Hi there", "general"),
]
for kws, msg, expected in tests:
    result = _infer_topic(kws, msg)
    tag = 'PASS' if result == expected else 'FAIL'
    print(f'  {tag}: {msg[:30]} -> {result} (expected {expected})')

# Test 2: improved summary (longer)
print('\n=== Smart Summary ===')
text = "We need to decide on Series C timing. The market is competitive. Three competitors raised last quarter. Our runway is 14 months but fundraising takes 3-6 months."
summary = _smart_summary(text)
print(f'  Summary ({len(summary)}c): {summary}')
assert len(summary) >= 80, f'Summary too short: {len(summary)}'
print('  PASS: summary >= 80 chars')

# Test 3: store_experience writes rich content
print('\n=== Rich Content Storage ===')
from agent.leaper_evolution import EvolutionEngine
from agent.leaper_brain import LeaperBrain
brain = LeaperBrain(r'C:\Users\mingjwan\.leaper\brain.db')
evo = EvolutionEngine(brain)

exp = {
    "summary": "CEO is considering Series C at lower valuation vs waiting 6 months",
    "keywords": ["series c", "valuation", "runway"],
    "task_success": True,
    "complexity": "complex",
    "topic": "融资",
    "user_intent": "Decide on Series C timing given competitive pressure",
    "successful_strategy": "Asked CEO to consider what changes in 6 months and real decision window",
    "new_knowledge": "Fundraising takes 3-6 months, so 14 months runway = 8-11 months real window",
    "failure_recovery": None,
    "efficiency_tip": None,
}
entry_id = evo.store_experience(exp)
print(f'  Stored: {entry_id[:8]}')

# Verify content is rich
import sqlite3
db = sqlite3.connect(r'C:\Users\mingjwan\.leaper\brain.db')
row = db.execute('SELECT content, length(content) as clen FROM leaper_brain WHERE id = ?', (entry_id,)).fetchone()
print(f'  Content length: {row[1]} chars')
print(f'  Content preview: {row[0][:200]}')
assert row[1] > 150, f'Content still too short: {row[1]}'
print('  PASS: rich content stored')

# Test 4: brain_learn dedup
print('\n=== Dedup ===')
from plugins.memory.leaper.provider import LeaperMemoryProvider
p = LeaperMemoryProvider()
p.initialize('test-dedup', agent_workspace='hermes')
r1 = p._handle_learn({"content": "CEO is considering Series C at lower valuation vs waiting 6 months for better terms"})
print(f'  First: {r1[:80]}')
r2 = p._handle_learn({"content": "CEO is considering Series C at lower valuation vs waiting 6 months for better terms"})
print(f'  Dupe:  {r2[:80]}')
import json
d2 = json.loads(r2)
assert d2.get("stored") == False or d2.get("reason") == "duplicate", "Dedup failed"
print('  PASS: duplicate rejected')

print('\n=== ALL PASSED ===')
brain.close()
db.close()
