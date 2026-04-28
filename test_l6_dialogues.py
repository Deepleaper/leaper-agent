"""
Test L0-L5 evolution engine with 200 real CEO Coach dialogues.
Parse dialogue → feed L1 experience_extract → check quality.
"""
import os, re, json, time
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'

from agent.leaper_brain import LeaperBrain
from agent.leaper_evolution import EvolutionEngine

# Use a separate test db to not pollute production
TEST_DB = r'C:\Users\mingjwan\.leaper\brain_test_l6.db'
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

brain = LeaperBrain(TEST_DB)
evo = EvolutionEngine(brain)

# Parse dialogues
with open(r'C:\Users\mingjwan\.openclaw\agents\ceo-coach\workspace\war-room\coach-ray-dialogue-200.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Split into turns
pattern = r'\*\*#(\d+) \[.*?\] (Ray|Coach)\*\*\s*\n(.*?)(?=\*\*#\d+|\Z)'
matches = re.findall(pattern, content, re.DOTALL)

print(f'Parsed {len(matches)} turns')

# Pair into (user, assistant) rounds
rounds = []
i = 0
while i < len(matches) - 1:
    num1, role1, text1 = matches[i]
    num2, role2, text2 = matches[i+1]
    if role1 == 'Ray' and role2 == 'Coach':
        rounds.append((text1.strip(), text2.strip()))
        i += 2
    else:
        i += 1

print(f'Paired into {len(rounds)} dialogue rounds')

# === L1: Experience Extract ===
print('\n=== L1: Experience Extract ===')
l1_stored = 0
l1_skipped = 0
l1_topics = {}
l1_complexities = {}
l1_total_content_len = 0

for idx, (user_msg, assistant_msg) in enumerate(rounds):
    exp = evo.experience_extract(user_msg, assistant_msg)
    
    complexity = exp.get('complexity', 'unknown')
    l1_complexities[complexity] = l1_complexities.get(complexity, 0) + 1
    
    if not exp.get('_skip_store'):
        entry_id = evo.store_experience(exp)
        if entry_id:
            l1_stored += 1
            topic = exp.get('topic', 'general')
            l1_topics[topic] = l1_topics.get(topic, 0) + 1
            l1_total_content_len += len(exp.get('summary', ''))
    else:
        l1_skipped += 1
    
    if (idx + 1) % 20 == 0:
        print(f'  Processed {idx+1}/{len(rounds)} rounds...')

print(f'\nL1 Results:')
print(f'  Stored: {l1_stored}')
print(f'  Skipped: {l1_skipped}')
print(f'  Avg summary length: {l1_total_content_len / max(l1_stored, 1):.0f} chars')
print(f'  Complexity distribution: {json.dumps(l1_complexities, ensure_ascii=False)}')
print(f'  Topic distribution: {json.dumps(l1_topics, ensure_ascii=False, indent=2)}')

# === L0: Recall Test ===
print('\n=== L0: Recall Test ===')
test_queries = [
    "Series C融资时机",
    "团队管理问题",
    "产品PMF",
    "竞争对手分析",
    "创始人焦虑",
]
for q in test_queries:
    results = brain.recall(q, top_k=3)
    print(f'  "{q}" → {len(results)} results')
    for r in results[:2]:
        preview = r.get('content', '')[:60].replace('\n', ' ')
        print(f'    - {preview}...')

# === L2: Skill Generate (if enough L1) ===
print(f'\n=== L2: Skill Generate (need 5+ L1, have {l1_stored}) ===')
if l1_stored >= 5:
    skills = evo.skill_generate()
    print(f'  Generated {len(skills)} skills')
    for s in skills[:5]:
        print(f'    - {s.get("title", "?")}: {s.get("content", "")[:60]}...')
else:
    print('  Not enough L1 experiences')

# === Stats ===
print('\n=== Brain Stats ===')
import sqlite3
db = sqlite3.connect(TEST_DB)
total = db.execute('SELECT COUNT(*) FROM leaper_brain').fetchone()[0]
by_type = db.execute('SELECT entry_type, COUNT(*) FROM leaper_brain GROUP BY entry_type').fetchall()
print(f'  Total entries: {total}')
for t, c in by_type:
    print(f'    {t}: {c}')
db.close()

brain.close()
print('\n=== DONE ===')
