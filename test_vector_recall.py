"""Test vector+BM25 hybrid recall with real dialogues."""
import os, sys, time
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'
sys.path.insert(0, r'C:\Users\mingjwan\.openclaw\agents\ray-cto\workspace\leaper-python')

from agent.leaper_brain import LeaperBrain

# Use the test db that already has 28 entries
TEST_DB = r'C:\Users\mingjwan\.leaper\brain_test_l6.db'
brain = LeaperBrain(TEST_DB)

# T1: embedding works
print('=== T1: Embedding ===')
from agent.leaper_brain import _get_embedding
vec = _get_embedding("融资策略分析")
print(f'  dims: {len(vec) if vec else 0}')
assert vec and len(vec) == 768, "Embedding failed"
print('  PASS')

# T2: backfill existing entries
print('\n=== T2: Backfill ===')
count = brain.backfill_embeddings(batch_size=10)
print(f'  Backfilled: {count}')
assert count > 0, "No backfill"
print('  PASS')

# T3: recall with vector
print('\n=== T3: Hybrid Recall ===')
queries = ["Series C融资时机", "团队管理", "产品PMF", "竞争对手", "创始人焦虑"]
for q in queries:
    results = brain.recall(q, top_k=3)
    print(f'\n  "{q}" → {len(results)} hits')
    for r in results[:3]:
        preview = r.get('content', '')[:100].replace('\n', ' ')
        print(f'    [{r.get("score",0):.3f}] {preview}...')

# T4: stats with lock (W8 fix)
print('\n=== T4: Stats ===')
stats = brain.get_stats()
print(f'  {stats}')

brain.close()
print('\n=== ALL DONE ===')
