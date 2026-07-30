import asyncio, os
from brain.executor import GeminiAdapter
from brain.model_registry import MODELS

async def main():
    a = GeminiAdapter()
    r = await a.generate('hello, say this is a test', MODELS['gemini-2.5-flash'], 'You are a chat agent.')
    print("RESPONSE:", repr(r.content))

asyncio.run(main())
