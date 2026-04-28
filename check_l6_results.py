import sqlite3, json

db = sqlite3.connect(r'C:\Users\mingjwan\.leaper\brain_test_l6.db')
db.row_factory = sqlite3.Row

total = db.execute('SELECT COUNT(*) FROM leaper_brain').fetchone()[0]
print(f'Total entries: {total}')

# By type
by_type = db.execute('SELECT entry_type, COUNT(*) as c FROM leaper_brain GROUP BY entry_type').fetchall()
for r in by_type:
    print(f'  {r["entry_type"]}: {r["c"]}')

# Content length stats
row = db.execute('SELECT AVG(length(content)) as avg_len, MIN(length(content)) as min_len, MAX(length(content)) as max_len FROM leaper_brain').fetchone()
print(f'\nContent length: avg={row["avg_len"]:.0f}, min={row["min_len"]}, max={row["max_len"]}')

# Topic distribution from metadata
topics = {}
rows = db.execute('SELECT metadata FROM leaper_brain WHERE metadata IS NOT NULL').fetchall()
for r in rows:
    try:
        m = json.loads(r['metadata'])
        t = m.get('topic', 'unknown')
        topics[t] = topics.get(t, 0) + 1
    except:
        pass
print(f'\nTopic distribution:')
for t, c in sorted(topics.items(), key=lambda x: -x[1]):
    print(f'  {t}: {c}')

# Complexity distribution
complexities = {}
for r in rows:
    try:
        m = json.loads(r['metadata'])
        c = m.get('complexity', 'unknown')
        complexities[c] = complexities.get(c, 0) + 1
    except:
        pass
print(f'\nComplexity distribution:')
for c, n in sorted(complexities.items(), key=lambda x: -x[1]):
    print(f'  {c}: {n}')

# Sample 5 entries
print(f'\nSample entries:')
samples = db.execute('SELECT content, metadata FROM leaper_brain ORDER BY RANDOM() LIMIT 5').fetchall()
for s in samples:
    meta = json.loads(s['metadata']) if s['metadata'] else {}
    print(f'  [{meta.get("topic","?")}] {s["content"][:120]}...')

# Recall test
import os, sys
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'
sys.path.insert(0, r'C:\Users\mingjwan\.openclaw\agents\ray-cto\workspace\leaper-python')
from agent.leaper_brain import LeaperBrain
brain = LeaperBrain(r'C:\Users\mingjwan\.leaper\brain_test_l6.db')

print(f'\n=== L0 Recall Test ===')
queries = ["Series C融资", "团队管理", "PMF", "竞品", "焦虑压力"]
for q in queries:
    results = brain.recall(q, top_k=3)
    print(f'  "{q}" → {len(results)} hits')
    for r in results[:2]:
        print(f'    {r.get("content","")[:80]}...')

brain.close()
db.close()
