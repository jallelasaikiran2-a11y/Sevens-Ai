import httpx
import os
from dotenv import load_dotenv

load_dotenv(r"d:\Sevens ai\.env")
api_key = os.getenv("GEMINI_API_KEY")

prompt = "hello, say this is a test"
system_prompt = "You are a conversational agent."

response = httpx.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
    json={
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.2,
        }
    }
)
print("Status:", response.status_code)
print("Response text:", response.text)
