import asyncio
import os
import sys
from dotenv import load_dotenv

# Ensure dotenv is loaded before anything else
load_dotenv()

from brain.model_registry import get_model
from brain.executor import get_adapter
from brain.agent_registry import AGENTS
from brain.model_registry import best_models

async def verify_providers():
    print("\n" + "="*50)
    print("VEXORA — Boot-time API Key Validation")
    print("="*50)
    
    providers_to_test = {
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "deepseek/deepseek-r1",
        "gemini": "gemini-2.5-flash"
    }
    
    all_ok = True
    
    for provider, model_id in providers_to_test.items():
        print(f"Testing {provider.upper()} API...")
        model_spec = get_model(model_id)
        if not model_spec:
            print(f"  [ERROR] Default model {model_id} not in registry!")
            all_ok = False
            continue
            
        try:
            adapter = get_adapter(provider)
            # Trivial ping request
            res = await adapter.generate("Reply exactly with the word 'OK'", model_spec, "You are a helpful assistant.")
            if res and res.content:
                print(f"  [OK] {provider.upper()} is live (latency: {res.latency}ms)")
            else:
                print(f"  [ERROR] {provider.upper()} returned empty response")
                all_ok = False
        except Exception as e:
            print(f"  [ERROR] {provider.upper()} failed: {e}")
            all_ok = False

    print("\nVerifying Agent configurations...")
    for agent_name, agent_spec in AGENTS.items():
        cap = agent_spec.preferred_model_capability
        candidates = best_models(cap, limit=5)
        if not candidates:
            candidates = best_models("coding", limit=5)
        
        if not candidates:
            print(f"  [ERROR] Agent {agent_name} has no primary candidates!")
            all_ok = False
            continue
            
        primary = candidates[0]
        fallback = None
        for cand in candidates:
            if cand.provider != primary.provider and cand.is_available:
                fallback = cand
                break
                
        if not fallback:
            print(f"  [ERROR] Agent {agent_name} cannot resolve a fallback with a different provider!")
            all_ok = False

    print("="*50)
    if not all_ok:
        print("[FATAL] Startup validation failed. See errors above.")
        sys.exit(1)
    else:
        print("[OK] All providers verified. Agent fallbacks validated.")

if __name__ == "__main__":
    asyncio.run(verify_providers())
