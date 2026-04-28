"""Resume L1 extraction for remaining dialogues, with embedding."""
import os, sys, re, json, time
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'
sys.path.insert(0, r'C:\Users\mingjwan\.openclaw\agents\ray-cto\workspace\leaper-python')

from agent.leaper_brain import LeaperBrain
from agent.leaper_evolution import EvolutionEngine

TEST_DB = r'C:\Users\mingjwan\.leaper\brain_test_l6.db'
brain = LeaperBrain(TEST_DB)
evo = EvolutionEngine(brain)

# Parse dialogues
with open(r'C:\Users\mingjwan\.openclaw\agents\ceo-coach\workspace\war-room\coach-ray-dialogue-200.md', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'\*\*#(\d+) \[.*?\] (Ray|Coach)\*\*\s*\n(.*?)(?=\*\*#\d+|\Z)'
matches = re.findall(pattern, content, re.DOTALL)
print(f'Parsed {len(matches)} turns', flush=True)

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

print(f'Total rounds: {len(rounds)}', flush=True)

# Skip already processed (28 rounds)
SKIP = 28
rounds = rounds[SKIP:]
print(f'Remaining: {len(rounds)} rounds (skipping first {SKIP})', flush=True)

stored = 0
skipped = 0
errors = 0

for idx, (user_msg, assistant_msg) in enumerate(rounds):
    try:
        exp = evo.experience_extract(user_msg, assistant_msg)
        if not exp.get('_skip_store'):
            entry_id = evo.store_experience(exp)
            if entry_id:
                stored += 1
        else:
            skipped += 1
    except Exception as e:
        errors += 1
        if errors <= 3:
            print(f'  ERROR at round {SKIP+idx+1}: {e}', flush=True)
    
    if (idx + 1) % 10 == 0:
        print(f'  Progress: {idx+1}/{len(rounds)} | stored={stored} skipped={skipped} errors={errors}', flush=True)

print(f'\n=== DONE ===', flush=True)
print(f'Stored: {stored}', flush=True)
print(f'Skipped: {skipped}', flush=True)
print(f'Errors: {errors}', flush=True)

# Backfill any missing embeddings
print(f'\nBackfilling embeddings...', flush=True)
count = brain.backfill_embeddings(batch_size=20)
print(f'Backfilled: {count}', flush=True)

# Final stats
import sqlite3
db = sqlite3.connect(TEST_DB)
total = db.execute('SELECT COUNT(*) FROM leaper_brain').fetchone()[0]
embedded = db.execute('SELECT COUNT(*) FROM leaper_brain WHERE embedding IS NOT NULL').fetchone()[0]
print(f'\nFinal: {total} entries, {embedded} with embedding', flush=True)
db.close()
brain.close()
