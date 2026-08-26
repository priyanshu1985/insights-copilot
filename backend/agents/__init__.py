"""
Agents Package for Insights Copilot.
Re-exports all agents, clients, and helper utilities for full backwards compatibility.
"""

from .base import client, api_key, call_llm_json
from .tools import (
    fetch_tavily,
    fetch_github,
    fetch_arxiv,
    fetch_semantic_scholar,
    refine_search_queries,
    filter_academic_results
)
from .research import research_agent
from .planner import planner_agent
from .critic import critic_agent
from .mentor import mentor_agent
from .insights import compute_milestone_pace, generate_founder_insight

__all__ = [
    "client",
    "api_key",
    "call_llm_json",
    "fetch_tavily",
    "fetch_github",
    "fetch_arxiv",
    "fetch_semantic_scholar",
    "refine_search_queries",
    "filter_academic_results",
    "research_agent",
    "planner_agent",
    "critic_agent",
    "mentor_agent",
    "compute_milestone_pace",
    "generate_founder_insight",
]
