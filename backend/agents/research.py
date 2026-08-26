import json
import logging
import asyncio
from datetime import datetime
from .base import call_llm_json
from .tools import (
    refine_search_queries,
    fetch_tavily,
    fetch_github,
    fetch_arxiv,
    fetch_semantic_scholar,
    filter_academic_results
)

logger = logging.getLogger(__name__)

async def research_agent(idea: str) -> dict:
    logger.info(f"Starting research_agent for idea: {idea}")
    fallback = {
        "problem_validation": "Unable to generate — please retry.",
        "market_research_summary": "Unable to generate — please retry.",
        "existing_solutions": [],
        "research_gaps": [],
        "innovation_opportunities": [],
        "unverified_claims": [],
        "sources": [],
        "github_repos": [],
        "apis_datasets": []
    }
    try:
        queries = await refine_search_queries(idea)
        tavily_res, github_res, arxiv_res, s2_res = await asyncio.gather(
            fetch_tavily(queries["market_query"]),
            fetch_github(queries["technical_query"]),
            fetch_arxiv(queries["academic_query"]),
            fetch_semantic_scholar(queries["academic_query"])
        )
        
        academic_res = arxiv_res + s2_res
        filtered_academic_res = filter_academic_results(academic_res, idea, queries["academic_query"])
        
        all_results = tavily_res + github_res + filtered_academic_res
        
        system_prompt = (
            "You are an expert AI Research Assistant. Given a project idea and a list of normalized search\n"
            "results from the web, GitHub, arXiv, and Semantic Scholar, produce a comprehensive,\n"
            "citation-backed research summary. Follow these rules exactly:\n\n"
            "1. CITATIONS: Every claim in problem_validation, market_research_summary,\n"
            "   existing_solutions[].description, and research_gaps[].gap MUST end with a bracketed\n"
            "   citation like [1] or [2][4], referring to the 1-based index of the corresponding entry\n"
            "   in the sources array you return. Never state a claim not grounded in a specific source.\n"
            "   If results are too sparse to support a claim, say so explicitly (e.g., \"limited prior\n"
            "   art found [2]\") rather than inventing detail.\n\n"
            "2. SOURCE ROUTING: existing_solutions must be derived ONLY from entries where source_type\n"
            "   is \"web\" or \"github\". research_gaps must be derived ONLY from entries where source_type\n"
            "   is \"arxiv\" or \"semantic_scholar\" — these represent unresolved problems or limitations\n"
            "   named in academic literature, not general product gaps.\n\n"
            "3. IDEA-SPECIFIC COMPARISON: existing_solutions[].description must relate each competitor\n"
            "   back to the user's specific idea, not describe it in isolation. State what it does AND\n"
            "   why it doesn't fully address this idea (e.g., \"built for restaurants, not hostel-scale\n"
            "   batch cooking\").\n\n"
            "4. GENUINE INNOVATION, NOT RESTATEMENT: innovation_opportunities must NOT simply restate a\n"
            "   gap as an opportunity (e.g., \"no existing tool tracks X\" is a gap, not an innovation).\n"
            "   Each item must propose a specific approach or method, and must reference which\n"
            "   research_gap or existing_solution gap it responds to via the \"addresses\" field.\n\n"
            "5. CITATION GROUNDING: Before citing a source index for a claim, verify that source's\n"
            "   title/snippet actually supports that specific claim's topic. Before citing any source\n"
            "   for research_gaps or problem_validation, check whether that source's title/snippet is\n"
            "   actually about the same subject domain as the idea — not just sharing incidental keywords.\n"
            "   A source only counts as topically relevant if it addresses the idea's specific sub-topic,\n"
            "   not just its broad field. A paper about wildlife resource management is NOT sufficiently\n"
            "   on-topic for a claim about terrarium-specific research, even though both are 'ecology.'\n"
            "   If no source is specific enough, state the gap as an assumption without a citation, or\n"
            "   add it to unverified_claims.\n"
            "   CRITICAL: If absolutely no academic sources are provided or topically relevant, return an\n"
            "   empty array [] for research_gaps rather than inventing a placeholder gap or empty citation.\n\n"
            "6. IMPLICATION REASONING: For every entry in research_gaps, do not simply restate the source's\n"
            "   own conclusion. Each gap string must have two parts: (1) the specific limitation named in the\n"
            "   source, and (2) one sentence explaining what that limitation means for THIS idea specifically —\n"
            "   e.g., not just 'tutoring systems have cognitive adaptability gaps [5]' but 'tutoring systems\n"
            "   struggle to adapt explanations to a student's actual confusion [5] — meaning this AI study buddy\n"
            "   needs a way to detect where a student is stuck, not just whether their answer is right.'\n"
            "   If you cannot connect a source's finding to this specific idea, do not include it as a gap.\n"
            "   Apply this same instruction to unverified_claims and existing_solutions[].gap.\n\n"
            "7. GITHUB REPOS: If the Search Results contain entries with source_type='github', you MUST include\n"
            "   them in the github_repos array. Do not leave the github_repos array empty if GitHub results\n"
            "   were provided to you.\n\n"
            "Respond ONLY with a valid JSON object matching the requested schema. Ensure the schema includes a top-level 'fetched_at' field (leave it as an empty string, the backend will populate it)."
        )
        user_prompt = f"""
Idea: "{idea}"
Search Results: {json.dumps(all_results)}

Generate JSON:
{{
  "problem_validation": "string, 4-6 detailed, intellectual sentences deeply analyzing the problem space with [n] citations",
  "market_research_summary": "string, 6-8 sentences offering a comprehensive and intellectual market analysis with [n] citations",
  "existing_solutions": [
    {{ "name": "string", "description": "string, 2-3 sentences — intellectual analysis of what it does + why it falls short, with [n] citation", "gap": "string, 1 sentence" }}
  ],
  "research_gaps": [
    {{ "gap": "string, 1-2 sentences describing an unresolved problem from academic literature in high detail", "citation": "[n]" }}
  ],
  "innovation_opportunities": [
    {{ "approach": "string, 1-2 sentences — a specific, highly intellectual method or technique", "addresses": "string — which research_gap or existing_solution gap this responds to" }}
  ],
  "sources": [
    {{ "title": "string", "url": "string", "source_type": "web | github | arxiv | semantic_scholar" }}
  ],
  "github_repos": [
    {{ "name": "string", "url": "string", "why_relevant": "string, 1 sentence" }}
  ],
  "apis_datasets": [
    {{ "name": "string", "url": "string", "type": "api | dataset" }}
  ],
  "unverified_claims": ["string — claims made without source support, flagged for transparency"],
  "fetched_at": ""
}}
"""
        result = await call_llm_json(system_prompt, user_prompt)
        result["fetched_at"] = datetime.utcnow().isoformat() + "Z"
        logger.info("Successfully completed research_agent")
        return result
    except Exception as e:
        logger.error(f"[research_agent] {type(e).__name__}: {e}")
        return fallback
