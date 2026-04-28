"""Test tiered LLM: local-first + quality gate + cloud fallback."""
import os, sys, json, time
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'
sys.path.insert(0, '.')

from agent.leaper_evolution import (
    _get_local_llm, _get_cloud_llm, _call_evolution_llm,
    _validate_extraction, _local_hit_count, _cloud_hit_count,
    EvolutionEngine
)
from agent.leaper_brain import LeaperBrain

# T1: Local LLM probe
print('=== T1: Local LLM Probe ===', flush=True)
local = _get_local_llm()
print(f'  Local available: {local is not None}', flush=True)
if local:
    print(f'  Model: {local["model"]}', flush=True)

# T2: Cloud LLM probe
print('\n=== T2: Cloud LLM Probe ===', flush=True)
cloud = _get_cloud_llm()
print(f'  Cloud available: {cloud is not None}', flush=True)

# T3: Quality gate test
print('\n=== T3: Quality Gate ===', flush=True)
good = '{"topic":"团队管理","intent":"解决合伙人冲突","strategy":"苏格拉底式提问","knowledge":"直面问题比回避更有效，但需要准备对方的反应预案","complexity":"moderate"}'
bad1 = '{"topic":"其他","intent":"聊天","strategy":"回答","knowledge":"ok","complexity":"moderate"}'
bad2 = 'not json at all'

for label, text in [("good", good), ("bad_topic", bad1), ("bad_json", bad2)]:
    valid, parsed = _validate_extraction(text)
    print(f'  {label}: valid={valid}', flush=True)

# T4: L1 with quality gate (3 real cases)
print('\n=== T4: L1 Tiered Extraction ===', flush=True)
brain = LeaperBrain(r'C:\Users\mingjwan\.leaper\brain_test_l6.db')
evo = EvolutionEngine(brain)

cases = [
    ("我决定直接跟他说他的短板，然后建议引入一个HR来辅助他管理团队",
     "你终于突破了之前的回避模式。问你一个问题：当你跟他说的时候，他的第一反应是什么？"),
    ("他没说什么",
     "没说什么有两种可能：一是他默认了，二是他还没消化。你当时什么感觉？"),
    ("我们现在种子用户从10家缩到3家了",
     "从10缩到3，你觉得是筛选还是流失？这两个的含义完全不同。"),
]

for i, (user, asst) in enumerate(cases):
    t0 = time.time()
    exp = evo.experience_extract(user, asst)
    elapsed = time.time() - t0
    print(f'\n  Case {i+1} ({elapsed:.1f}s):', flush=True)
    print(f'    topic: {exp.get("topic")}', flush=True)
    print(f'    intent: {exp.get("intent","")[:60]}', flush=True)
    print(f'    strategy: {exp.get("strategy","")[:60]}', flush=True)
    print(f'    knowledge: {exp.get("knowledge","")[:60]}', flush=True)
    print(f'    complexity: {exp.get("complexity")}', flush=True)
    print(f'    _skip_store: {exp.get("_skip_store", False)}', flush=True)

# Import current counts
from agent import leaper_evolution
print(f'\n=== Stats ===', flush=True)
print(f'  Local hits: {leaper_evolution._local_hit_count}', flush=True)
print(f'  Cloud hits: {leaper_evolution._cloud_hit_count}', flush=True)

brain.close()
print('\nDONE', flush=True)
