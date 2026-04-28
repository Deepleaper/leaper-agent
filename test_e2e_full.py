import os, json, time
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'

from plugins.memory.leaper.provider import LeaperMemoryProvider
p = LeaperMemoryProvider()
p.initialize('e2e-test', agent_workspace='hermes')

spb = p.system_prompt_block()
print('=== T1: System Prompt Injection ===')
v21_checks = {
    'cognitive_journal': any(x in spb for x in ['cognitive', 'journal', 'log', '认知日志', '认知']),
    'ray_info': 'Ray' in spb and 'Deepleaper' in spb,
    'browser_ban': 'browser_navigate' in spb,
    'tool_invisible': 'CRITICAL' in spb,
    'frameworks': 'Pre-mortem' in spb and 'First Principles' in spb,
    'search_tool': 'web_search_tool' in spb,
    'runtime_os': 'Windows' in spb,
    'short_sentences': any(x in spb for x in ['short', 'brief', 'one question', '短句', '一次只问一个']),
}
passed = 0
for k, v in v21_checks.items():
    tag = 'PASS' if v else 'FAIL'
    if v: passed += 1
    print(f'  {tag}: {k}')
print(f'Score: {passed}/{len(v21_checks)}')

print('\n=== T2: Brain Recall ===')
result = p.handle_tool_call('brain_recall', {'query': 'CEO strategy decision'})
print(f'Recall: {len(str(result))} chars')

print('\n=== T3: Brain Learn ===')
result = p.handle_tool_call('brain_learn', {
    'content': 'E2E test: Ray considering Series C timing - tension between now vs 6 months',
    'title': 'e2e-test-funding'
})
print(f'Learn: {str(result)[:80]}')

print('\n=== T4: Prefetch ===')
ctx = p.prefetch('Series C funding timing', session_id='e2e-test')
print(f'Prefetch: {len(ctx)} chars')

print('\n=== T5: Sync Turn (L1) ===')
p.sync_turn(
    'I have been thinking for weeks about whether to raise Series C now at lower valuation or wait 6 months. Our burn rate is 2M per month with 14 months runway. Three competitors raised last quarter.',
    'This is a classic founder dilemma. What specifically would change in 6 months - a product milestone, revenue target, or market shift? If you raise now at lower valuation, what is the actual cost - dilution or something else? With 14 months runway but 3-6 months fundraising, your real decision window is 8-11 months.',
    session_id='e2e-test'
)
time.sleep(8)
entries = p.brain.recall('Series C funding', top_k=5)
l1_entries = [e for e in entries if e.get('entry_type') == 'experience']
print(f'L1 experience entries: {len(l1_entries)}')

print('\n=== T6: DuckDuckGo Search ===')
from tools.web_tools import web_search_tool, _get_backend
backend = _get_backend()
print(f'Backend: {backend}')
result = web_search_tool('AI startup Series C 2026', limit=3)
data = json.loads(result)
web = data.get('data', {}).get('web', [])
print(f'Results: {len(web)}')

all_pass = passed == len(v21_checks) and len(web) > 0
print(f'\n=== {"ALL PASSED" if all_pass else "SOME FAILED"} ===')
