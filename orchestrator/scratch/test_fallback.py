import asyncio
from unittest.mock import patch
import httpx
from orchestrator.brain.executor import get_adapter
from orchestrator.brain.model_registry import get_model

async def test():
    adapter = get_adapter("openrouter")
    spec = get_model("deepseek/deepseek-r1")
    
    # We want it to fail for deepseek-r1 (402), 
    # then fail for the next model (429), 
    # then succeed for the 3rd.
    
    original_post = httpx.AsyncClient.post
    
    call_count = 0
    async def mock_post(self, url, **kwargs):
        nonlocal call_count
        call_count += 1
        
        # Mock response object
        response = httpx.Response(status_code=200, json={
            "choices": [{"message": {"content": "mocked ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10}
        }, request=httpx.Request("POST", url))
        
        if call_count == 1:
            # Primary model fails with 402
            response.status_code = 402
            
        elif call_count == 2:
            # First free model fails with 429
            response.status_code = 429
            
        return response
        
    with patch("httpx.AsyncClient.post", new=mock_post):
        try:
            res = await adapter.generate("test prompt", spec, "sys")
            print(f"Final success with model: {res.model}")
        except Exception as e:
            print(f"Failed entirely: {e}")

if __name__ == "__main__":
    asyncio.run(test())
