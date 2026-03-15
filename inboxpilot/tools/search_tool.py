"""
inboxpilot/tools/search_tool.py
Web search tool — demo mode returns mock results.
"""
from __future__ import annotations
import time
from typing import List, Dict

MOCK_SEARCH_DB: Dict[str, List[Dict[str, str]]] = {
    "sarah chen company": [
        {
            "title": "Sarah Chen - VP Finance at Acme Corp",
            "snippet": "Sarah Chen leads the finance division at Acme Corp with 10+ years in tech.",
            "url": "https://linkedin.com/in/sarah-chen-finance",
        }
    ],
    "mike johnson partner": [
        {
            "title": "Mike Johnson - Solutions Architect at PartnerCo",
            "snippet": "Mike specializes in API integration and enterprise software.",
            "url": "https://linkedin.com/in/mike-johnson-arch",
        }
    ],
    "python weekly newsletter": [
        {
            "title": "Python Weekly - curated Python news",
            "snippet": "Weekly digest of Python articles, projects, and tutorials.",
            "url": "https://pythonweekly.com",
        }
    ],
}


def web_search_demo(query: str, num_results: int = 3, latency_ms: int = 300) -> List[Dict[str, str]]:
    """Return mock search results for demo mode."""
    time.sleep(latency_ms / 1000)
    query_lower = query.lower()
    for key, results in MOCK_SEARCH_DB.items():
        if any(word in query_lower for word in key.split()):
            return results[:num_results]
    return [
        {
            "title": f"Results for: {query}",
            "snippet": "No specific mock data available for this query.",
            "url": "https://example.com/search",
        }
    ]
