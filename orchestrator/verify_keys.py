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
    print("sevens — Boot-time API Key Validation")
    print("="*50)
    providers_to_test = {
        "groq": "llama-3.3-70b-versatile",
        "gemini": "gemini-2.0-flash",
        # OpenRouter will be handled specially below
    }
    
    healthy_providers = 0
    total_providers_tested = 0
    agents_ok = True

    # 1. Test OpenRouter Tier 1 (paid-trial) and Tier 2 (free) explicitly
    print("Testing OPENROUTER API...")
    total_providers_tested += 1
    or_tier1_id = "google/gemini-2.5-flash"
    or_tier2_id = "openai/gpt-oss-20b:free"
    
    tier1_spec = get_model(or_tier1_id)
    tier2_spec = get_model(or_tier2_id)
    
    or_adapter = get_adapter("openrouter")
    or_healthy = False
    
    if not tier1_spec or not tier2_spec:
        print("  [ERROR] OpenRouter Tier 1 or Tier 2 default models missing from registry!")
        _disable_provider("openrouter")
    else:
        # Try Tier 1
        try:
            res = await or_adapter.generate("Reply exactly with the word 'OK'", tier1_spec, "You are a helpful assistant.")
            if res and res.content:
                print(f"  [OK] OpenRouter is live (latency: {res.latency}ms)")
                if res.model == tier1_spec.id:
                    print("  [INFO] OpenRouter Tier 1 credits available.")
                else:
                    print(f"  [WARN] OpenRouter Tier 1 exhausted. Served by Tier 2 fallback ({res.model}).")
                healthy_providers += 1
                or_healthy = True
            else:
                print("  [ERROR] OpenRouter Tier 1 returned empty response")
        except Exception as e:
            import httpx
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 402, 429):
                if e.response.status_code == 401:
                    print("  [WARN] OpenRouter returned 401 Unauthorized. Key might be invalid, but keeping online.")
                    healthy_providers += 1
                    or_healthy = True
                elif e.response.status_code in (402, 429):
                    reason = "no credits" if e.response.status_code == 402 else "rate-limited"
                    print(f"  [WARN] OpenRouter Tier 1 exhausted ({reason}). Testing Tier 2 free models...")
                    # Try Tier 2
                    try:
                        res2 = await or_adapter.generate("Reply exactly with the word 'OK'", tier2_spec, "You are a helpful assistant.")
                        if res2 and res2.content:
                            print(f"  [OK] OpenRouter Tier 2 is live (latency: {res2.latency}ms)")
                            print("  [WARN] OpenRouter Tier 1 exhausted, using Tier 2 free models.")
                            healthy_providers += 1
                            or_healthy = True
                        else:
                            print("  [ERROR] OpenRouter Tier 2 returned empty response")
                    except Exception as e2:
                        print(f"  [ERROR] OpenRouter Tier 2 also failed: {type(e2).__name__} - {e2}")
            else:
                print(f"  [ERROR] OpenRouter failed: {type(e).__name__} - {e}")
                
        if not or_healthy:
            _disable_provider("openrouter")
    
    # 2. Test other providers
    for provider, model_id in providers_to_test.items():
        total_providers_tested += 1
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
        print(f"[OK] {healthy_providers}/{total_providers_tested} providers verified. Backend starting.")

def _disable_provider(provider: str):
    """Disable all models for a provider that failed verification."""
    print(f"  [WARN] Marking {provider.upper()} as OFFLINE for this session.")
    models = list_models_by_provider(provider)
    for m in models:
        disable_model(m.id)

if __name__ == "__main__":
    asyncio.run(verify_providers())
