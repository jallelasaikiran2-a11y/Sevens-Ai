import asyncio
import httpx
import json

async def test():
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            "http://localhost:8000/api/orchestrate",
            json={
                "prompt": "Design and implement a completely novel and complex sorting algorithm in Python, explain its time complexity and space complexity, and provide test cases. Make sure it is highly optimized.",
                "expert_mode": True
            }
        )
        data = response.json()
        print("Success:", data.get("success"))
        print("Trust Score:", data.get("confidence_score"))
        
        # Check ensemble
        for agent in data.get("agents_used", []):
            if agent.get("was_ensemble"):
                print(f"Agent {agent['name']} used ENSEMBLE!")
                print(f"Synthesis Model: {agent['synthesis_model']}")
                print(f"Candidates run: {len(agent['ensemble_outputs'])}")
                print(f"Agreement Score: {agent['ensemble_agreement']}")
        
        # Check trust factors
        for tf in data.get("trust_factors", []):
            if tf["name"] == "Ensemble Agreement":
                print(f"Trust Factor: {tf['name']} -> {tf['score']} ({tf['explanation']})")

if __name__ == "__main__":
    asyncio.run(test())
