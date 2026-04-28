import os, sys, json, time, sqlite3
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'
sys.path.insert(0, '.')
from agent.leaper_brain import LeaperBrain
from agent.leaper_evolution import EvolutionEngine

brain = LeaperBrain(r'C:\Users\mingjwan\.leaper\brain_test_l6.db')
evo = EvolutionEngine(brain)

print('=== L5: Adversarial Validation ===', flush=True)
t0 = time.time()
val = evo.validate()
print(f'Time: {time.time()-t0:.1f}s', flush=True)
print(f'Result: {json.dumps(val, ensure_ascii=False, default=str)[:800]}', flush=True)

print('\n=== Final Stats ===', flush=True)
db = sqlite3.connect(r'C:\Users\mingjwan\.leaper\brain_test_l6.db')
by_type = db.execute('SELECT entry_type, COUNT(*) FROM leaper_brain GROUP BY entry_type ORDER BY COUNT(*) DESC').fetchall()
for t, c in by_type:
    print(f'  {t}: {c}', flush=True)
total = db.execute('SELECT COUNT(*) FROM leaper_brain').fetchone()[0]
print(f'  Total: {total}', flush=True)
db.close()
brain.close()
print('\nDONE', flush=True)
