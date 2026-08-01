import asyncio
import os
import sys
from dotenv import load_dotenv

# Ensure dotenv is loaded before anything else
load_dotenv(override=True)

from brain.model_registry import get_model, best_models, list_models_by_provider, disable_model
from brain.executor import get_adapter
from brain.agent_registry import AGENTS

async def verify_providers():
    print("\n" + "="*50)
    print("VEXORA — Boot-time API Key Validation")
    print("="*50)
    providers_to_test = {
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "google/gemini-2.5-flash",
        "gemini": "gemini-2.0-flash"
    }
    
    healthy_providers = 0
    agents_ok = True
    
    for provider, model_id in providers_to_test.items():
        print(f"Testing {provider.upper()} API...")
        model_spec = get_model(model_id)
        if not model_spec:
            print(f"  [ERROR] Default model {model_id} not in registry!")
            _disable_provider(provider)
            continue
            
        try:
            adapter = get_adapter(provider)
            # Trivial ping request
            res = await adapter.generate("Reply exactly with the word 'OK'", model_spec, "You are a helpful assistant.")
            if res and res.content:
                print(f"  [OK] {provider.upper()} is live (latency: {res.latency}ms)")
                healthy_providers += 1
            else:
                print(f"  [ERROR] {provider.upper()} returned empty response")
                _disable_provider(provider)
        except Exception as e:
            import httpx
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 402, 429):
                if e.response.status_code == 401:
                    print(f"  [WARN] {provider.upper()} returned 401 Unauthorized. Key might be invalid, but keeping online for execution.")
                elif e.response.status_code == 402:
                    print(f"  [WARN] {provider.upper()} returned 402 Payment Required. Key is valid, but account has no credits. Free models will still work.")
                else:
                    print(f"  [WARN] {provider.upper()} returned 429 Too Many Requests. Key is valid, but rate-limited. Will attempt during execution.")
                healthy_providers += 1
            else:
                print(f"  [ERROR] {provider.upper()} failed: {type(e).__name__} - {e}")
                _disable_provider(provider)

    print("\nVerifying Agent configurations...")
    for agent_name, agent_spec in AGENTS.items():
        cap = agent_spec.preferred_model_capability
        candidates = best_models(cap, limit=5)
        if not candidates:
            candidates = best_models("coding", limit=5)
        
        if not candidates:
            print(f"  [ERROR] Agent {agent_name} has no primary candidates (all capable providers are offline)!")
            agents_ok = False
            continue
            
        primary = candidates[0]
        fallback = None
        for cand in candidates:
            if cand.provider != primary.provider and cand.is_available:
                fallback = cand
                break
                
        if not fallback:
            # In a degraded state (e.g. only Groq is online), fallback might genuinely be missing.
            # We just warn instead of failing the startup.
            print(f"  [WARN] Agent {agent_name} has NO cross-provider fallback available.")

    print("="*50)
    if healthy_providers == 0:
        print("[FATAL] All AI providers failed. Cannot start orchestrator.")
        sys.exit(1)
    elif not agents_ok:
        print("[FATAL] Agents cannot resolve required capabilities. Cannot start.")
        sys.exit(1)
    else:
        print(f"[OK] {healthy_providers}/{len(providers_to_test)} providers verified. Backend starting.")

def _disable_provider(provider: str):
    """Disable all models for a provider that failed verification."""
    print(f"  [WARN] Marking {provider.upper()} as OFFLINE for this session.")
    models = list_models_by_provider(provider)
    for m in models:
        disable_model(m.id)

if __name__ == "__main__":
    asyncio.run(verify_providers())
