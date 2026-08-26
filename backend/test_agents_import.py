import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

print("Testing direct package imports...")
from agents.base import client, call_llm_json
from agents.tools import fetch_tavily, fetch_github, fetch_arxiv, fetch_semantic_scholar, refine_search_queries, filter_academic_results
from agents.research import research_agent
from agents.planner import planner_agent
from agents.critic import critic_agent
from agents.mentor import mentor_agent
from agents.insights import compute_milestone_pace, generate_founder_insight

print("[SUCCESS] Submodule imports succeeded!")

print("Testing top-level package imports (backwards compatibility)...")
from agents import (
    client as groq_client,
    research_agent as r_agent,
    planner_agent as p_agent,
    critic_agent as c_agent,
    mentor_agent as m_agent,
    generate_founder_insight as g_insight,
    compute_milestone_pace as c_pace
)

assert callable(r_agent), "research_agent is not callable"
assert callable(p_agent), "planner_agent is not callable"
assert callable(c_agent), "critic_agent is not callable"
assert callable(m_agent), "mentor_agent is not callable"
assert callable(g_insight), "generate_founder_insight is not callable"
assert callable(c_pace), "compute_milestone_pace is not callable"

print("[SUCCESS] All agents are successfully imported and callable from top-level package!")
