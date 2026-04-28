"""Test L1 extraction quality: qwen2.5:7b vs Claude Opus."""
import os, sys, json, time
os.environ['HERMES_HOME'] = r'C:\Users\mingjwan\.leaper'
sys.path.insert(0, '.')

from openai import OpenAI

# Two clients
local = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
cloud = OpenAI(base_url="http://122.193.22.206:8235/v1", api_key="sk-0dyWto1WwjLwJyZELld2-w")

PROMPT_TEMPLATE = '从以下对话中提取经验。返回JSON：\n{{"topic": "主题", "intent": "用户意图", "strategy": "助手策略", "knowledge": "可复用知识", "complexity": "trivial|moderate|complex"}}\n\n用户: {user}\n助手: {assistant}'

# Test cases from real dialogues
cases = [
    {
        "user": "我决定直接跟他说他的短板，然后建议引入一个HR来辅助他管理团队",
        "assistant": "你终于突破了之前的回避模式。问你一个问题：当你跟他说的时候，他的第一反应是什么？"
    },
    {
        "user": "他没说什么",
        "assistant": "没说什么有两种可能：一是他默认了，二是他还没消化。你当时什么感觉？"
    },
    {
        "user": "压力大脾气就变差了，失去了团队的信任",
        "assistant": "你在描述问题，但不是他的反应。他具体说了什么？做了什么？"
    }
]

for i, case in enumerate(cases):
    prompt = PROMPT_TEMPLATE.format(user=case["user"], assistant=case["assistant"])
    
    # Local
    t0 = time.time()
    try:
        r1 = local.chat.completions.create(
            model="qwen2.5:7b", messages=[{"role":"user","content":prompt}],
            max_tokens=300, temperature=0
        )
        local_result = r1.choices[0].message.content
        local_time = time.time() - t0
    except Exception as e:
        local_result = f"ERROR: {e}"
        local_time = 0
    
    # Cloud
    t0 = time.time()
    try:
        r2 = cloud.chat.completions.create(
            model="ray_MaaS_Cl_Opus_4.7_20260416_cache",
            messages=[{"role":"user","content":prompt}],
            max_tokens=300, temperature=0
        )
        cloud_result = r2.choices[0].message.content
        cloud_time = time.time() - t0
    except Exception as e:
        cloud_result = f"ERROR: {e}"
        cloud_time = 0
    
    print(f'\n=== Case {i+1} ===', flush=True)
    print(f'User: {case["user"][:50]}...', flush=True)
    print(f'\n[LOCAL qwen2.5:7b] ({local_time:.1f}s):', flush=True)
    print(f'  {local_result[:200]}', flush=True)
    print(f'\n[CLOUD Claude Opus] ({cloud_time:.1f}s):', flush=True)
    print(f'  {cloud_result[:200]}', flush=True)

print('\nDONE', flush=True)
