"""
VEXORA Research Engine — Real Web Search via Tavily API

Provides grounded retrieval for the Research Agent.
Every response includes a `sources` array: [{title, url, snippet}].
If retrieval fails, sets `low_confidence_no_retrieval: true`.
"""

from __future__ import annotations
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def search_web(query: str, max_results: int = 5) -> dict:
    """
    Perform a real web search using the Tavily API.

    Returns:
        {
            "success": bool,
            "results": [{"title": str, "url": str, "snippet": str}],
            "low_confidence_no_retrieval": bool,
            "raw_answer": str | None,
        }
    """
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        print("[WARN] TAVILY_API_KEY not set. Research Agent will use model memory only.")
        return {
            "success": False,
            "results": [],
            "low_confidence_no_retrieval": True,
            "raw_answer": None,
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": max_results,
                    "include_answer": True,
                    "include_raw_content": False,
                }
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for r in data.get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:300],
                })

            return {
                "success": True,
                "results": results,
                "low_confidence_no_retrieval": len(results) == 0,
                "raw_answer": data.get("answer"),
            }

    except Exception as e:
        print(f"[RESEARCH] Tavily search failed: {e}")
        return {
            "success": False,
            "results": [],
            "low_confidence_no_retrieval": True,
            "raw_answer": None,
        }


def format_sources_for_prompt(search_results: dict) -> str:
    """
    Format search results into a context block for the Research Agent's prompt.
    """
    if not search_results.get("success") or not search_results.get("results"):
        return (
            "\n[WARNING: No web search results were retrieved. "
            "You MUST flag this in your response by stating that no real-time sources "
            "were available and your answer is based on training data only.]\n"
        )

    lines = ["\n## Web Search Results (Real-Time Sources)\n"]

    if search_results.get("raw_answer"):
        lines.append(f"**Summary:** {search_results['raw_answer']}\n")

    for i, r in enumerate(search_results["results"], 1):
        lines.append(f"### Source {i}: {r['title']}")
        lines.append(f"**URL:** {r['url']}")
        lines.append(f"**Snippet:** {r['snippet']}")
        lines.append("")

    lines.append(
        "Use these sources in your response. Cite URLs where relevant. "
        "Include a 'Sources' section at the end of your response listing all used URLs."
    )

    return "\n".join(lines)
