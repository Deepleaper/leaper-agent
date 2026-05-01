"""End-to-end test L2-L5 with 48 real experiences in brain_test_l6.db."""
import os, sys, json, time, tempfile, shutil
_tmpdir = tempfile.mkdtemp()
os.environ['HERMES_HOME'] = _tmpdir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.leaper_brain import LeaperBrain
from agent.leaper_evolution import EvolutionEngine

TEST_DB = os.path.join(_tmpdir, 'brain_test_l6.db')
brain = LeaperBrain(TEST_DB)
evo = EvolutionEngine(brain)

# Force L1 count so L2 triggers
evo._l1_count = 10

print('=== L2: Skill Generate ===', flush=True)
t0 = time.time()
skills = evo.skill_generate()
print(f'  Time: {time.time()-t0:.1f}s', flush=True)
print(f'  Generated: {len(skills)} skills', flush=True)
for i, s in enumerate(skills[:10]):
    title = s.get('title', '?')
    content = s.get('content', '')[:80]
    print(f'  [{i+1}] {title}: {content}...', flush=True)

# Check if skills were stored
import sqlite3
db = sqlite3.connect(TEST_DB)
skill_count = db.execute("SELECT COUNT(*) FROM leaper_brain WHERE entry_type='skill'").fetchone()[0]
print(f'  Skills in DB: {skill_count}', flush=True)

print('\n=== L3: Cross-Skill Evolution ===', flush=True)
t0 = time.time()
l3_result = evo.skill_evolve()
print(f'  Time: {time.time()-t0:.1f}s', flush=True)
print(f'  Result: {json.dumps(l3_result, ensure_ascii=False, default=str)[:300]}', flush=True)

# Check skill changes
skill_count_after = db.execute("SELECT COUNT(*) FROM leaper_brain WHERE entry_type='skill'").fetchone()[0]
print(f'  Skills after L3: {skill_count_after}', flush=True)

print('\n=== L4: User Model ===', flush=True)
t0 = time.time()
profile = evo.update_user_model()
print(f'  Time: {time.time()-t0:.1f}s', flush=True)
if profile:
    print(f'  Profile: {json.dumps(profile, ensure_ascii=False, default=str)[:300]}', flush=True)
else:
    print('  No profile generated', flush=True)

# Check user model in DB
um_count = db.execute("SELECT COUNT(*) FROM leaper_brain WHERE entry_type='user_model'").fetchone()[0]
print(f'  User models in DB: {um_count}', flush=True)

print('\n=== L5: Adversarial Validation ===', flush=True)
t0 = time.time()
validation = evo.adversarial_validate()
print(f'  Time: {time.time()-t0:.1f}s', flush=True)
if validation:
    print(f'  Result: {json.dumps(validation, ensure_ascii=False, default=str)[:300]}', flush=True)
else:
    print('  No validation result', flush=True)

print('\n=== Final DB Stats ===', flush=True)
by_type = db.execute('SELECT entry_type, COUNT(*) FROM leaper_brain GROUP BY entry_type ORDER BY COUNT(*) DESC').fetchall()
for t, c in by_type:
    print(f'  {t}: {c}', flush=True)
total = db.execute('SELECT COUNT(*) FROM leaper_brain').fetchone()[0]
embedded = db.execute('SELECT COUNT(*) FROM leaper_brain WHERE embedding IS NOT NULL').fetchone()[0]
print(f'  Total: {total}, Embedded: {embedded}', flush=True)

db.close()
brain.close()
shutil.rmtree(_tmpdir, ignore_errors=True)
print('\n=== ALL LAYERS DONE ===', flush=True)
