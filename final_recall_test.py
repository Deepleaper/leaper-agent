import os, sys, json
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'
sys.path.insert(0, r'C:\Users\mingjwan\.openclaw\agents\ray-cto\workspace\leaper-python')
from agent.leaper_brain import LeaperBrain
import sqlite3

brain = LeaperBrain(r'C:\Users\mingjwan\.leaper\brain_test_l6.db')

queries = ['Series C融资时机', '团队管理和合伙人', '产品PMF验证', '竞争对手分析', '创始人焦虑和压力', '组织架构调整', 'CEO教练方法论']
for q in queries:
    results = brain.recall(q, top_k=3)
    print(f'\n"{q}" -> {len(results)} hits', flush=True)
    for r in results[:3]:
        score = r.get('score', 0)
        preview = r.get('content', '')[:100].replace('\n', ' ')
        print(f'  [{score:.3f}] {preview}...', flush=True)

db = sqlite3.connect(r'C:\Users\mingjwan\.leaper\brain_test_l6.db')
rows = db.execute('SELECT metadata FROM leaper_brain WHERE metadata IS NOT NULL').fetchall()
topics = {}
for r in rows:
    try:
        m = json.loads(r[0])
        t = m.get('topic', '?')
        topics[t] = topics.get(t, 0) + 1
    except: pass
print(f'\n\nTopic distribution ({sum(topics.values())} total):', flush=True)
for t, c in sorted(topics.items(), key=lambda x: -x[1]):
    print(f'  {t}: {c}', flush=True)
db.close()
brain.close()
