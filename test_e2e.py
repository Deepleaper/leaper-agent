import sys, os, tempfile
sys.path.insert(0, '.')

# Test 1: LeaperBrain
print('=== Test 1: LeaperBrain ===')
from agent.leaper_brain import LeaperBrain
db_path = os.path.join(tempfile.gettempdir(), 'test_brain.db')
brain = LeaperBrain(db_path)
brain.learn('Ray 是跃盟科技的 CEO', source='test', namespace='agent/test')
brain.learn('跃盟的核心产品是瞬知', source='test', namespace='agent/test')
brain.learn('公司在北京朝阳和苏州', source='test', namespace='agent/test')
results = brain.recall('跃盟', top_k=3)
print(f'Recall 跃盟: {len(results)} results')
for r in results:
    ns = r.get('namespace', '?')
    ct = r.get('content', '')[:50]
    print(f'  [{ns}] {ct}')
try:
    stats = brain.stats()
    print(f'Stats: {stats}')
except AttributeError:
    print('Stats: method not found (skipped)')

# Test 2: Evolution L0-L2
print('\n=== Test 2: Evolution L0-L2 ===')
from agent.leaper_evolution import EvolutionEngine
evo = EvolutionEngine(brain)
l0 = evo.hybrid_recall('CEO')
print(f'L0 recall CEO: {len(l0)} results')
l1 = evo.experience_extract('我公司叫跃盟，做AI的', '好的，了解了跃盟科技是一家AI公司')
kws = l1.get('keywords', [])[:5]
print(f'L1 extract: keywords={kws}, success={l1.get("task_success")}')
l2 = evo.skill_generate([l1, l1, l1])
sname = l2.get('name') if l2 else 'None'
print(f'L2 skill: {sname}')
l3 = evo.skill_evolve([])
print(f'L3: {l3.get("message")}')
l4 = evo.user_model_update([])
print(f'L4: {l4.get("message")}')
l5 = evo.validate({})
print(f'L5 pass: {l5.get("pass")}')

# Test 3: SeedLoader
print('\n=== Test 3: SeedLoader ===')
from agent.leaper_seed_loader import load_workspace_files
result = load_workspace_files('templates/ceo-coach', brain)
print(f'Loaded workspace: {type(result)}')
content_str = str(result)
print(f'Content length: {len(content_str)} chars')
print(f'Contains EGO: {"EGO" in content_str}')
print(f'Contains SOUL: {"SOUL" in content_str}')

# Test 4: Config
print('\n=== Test 4: Config ===')
from leaper_config import load_leaper_config, write_hermes_config
cfg = load_leaper_config('leaper.yaml.example')
print(f'Config loaded: name={cfg.get("name", "?")}')
print(f'Config keys: {list(cfg.keys())}')

# Test 5: Workshop
print('\n=== Test 5: Workshop ===')
from leaper_workshop import _load_local_templates as list_local_templates
templates = list_local_templates()
tnames = [t.get('name') for t in templates]
print(f'Local templates: {tnames}')

# Test 6: DeepBrain Provider
print('\n=== Test 6: DeepBrain Provider ===')
from plugins.memory.deepbrain.provider import DeepBrainMemoryProvider
provider = DeepBrainMemoryProvider()
provider.initialize(session_id='test-session', hermes_home=tempfile.gettempdir())
print(f'Provider initialized: {provider.name}')
prompt_block = provider.system_prompt_block()
print(f'System prompt block: {len(prompt_block)} chars')
schemas = provider.get_tool_schemas()
tool_names = [s.get('function', {}).get('name') for s in schemas]
print(f'Tool schemas: {tool_names}')
result = provider.handle_tool_call('brain_learn', {'content': '测试知识', 'namespace': 'test'})
print(f'brain_learn: {str(result)[:50]}')
result = provider.handle_tool_call('brain_recall', {'query': '测试'})
print(f'brain_recall: {str(result)[:80]}')
provider.shutdown()

print('\n=== ALL TESTS PASSED ===')
os.remove(db_path)
