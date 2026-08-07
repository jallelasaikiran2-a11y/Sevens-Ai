import httpx
import os
import asyncio
from dotenv import load_dotenv

load_dotenv(r"d:\Sevens ai\.env")
api_key = os.getenv("GROQ_API_KEY")

async def test_groq():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": "hello"}],
                "temperature": 0.2
            }
        )
        print("Status:", response.status_code)
        if response.status_code == 200:
            print("Response:", response.json()["choices"][0]["message"]["content"])
        else:
            print(response.text)

asyncio.run(test_groq())
