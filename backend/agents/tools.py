import os
import re
import logging
import xml.etree.ElementTree as ET
import httpx
from .base import call_llm_json

logger = logging.getLogger(__name__)

async def fetch_tavily(query: str):
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key or key == "your_tavily_api_key_here":
        logger.warning("[fetch_tavily] TAVILY_API_KEY missing or placeholder — skipping")
        return []
    try:
        async with httpx.AsyncClient() as c:
            res = await c.post("https://api.tavily.com/search", json={
                "api_key": key,
                "query": query,
                "search_depth": "basic",
                "max_results": 5
            }, timeout=10.0)
            res.raise_for_status()
            data = res.json()
            results = [{"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", ""), "source": "web"} for r in data.get("results", [])]
            logger.info(f"[fetch_tavily] Success — {len(results)} results returned for query: {query[:80]}")
            return results
    except httpx.HTTPStatusError as e:
        logger.error(f"[fetch_tavily] HTTP {e.response.status_code}: {e.response.text[:500]}")
        return []
    except Exception as e:
        logger.error(f"[fetch_tavily] {type(e).__name__}: {e}")
        return []

async def fetch_github(query: str):
    token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token and token != "your_github_token_here":
        headers["Authorization"] = f"token {token}"
    else:
        logger.warning("[fetch_github] GITHUB_TOKEN missing or placeholder — using unauthenticated (lower rate limit)")
    try:
        async with httpx.AsyncClient() as c:
            res = await c.get(f"https://api.github.com/search/repositories?q={query}&per_page=5", headers=headers, timeout=10.0)
            res.raise_for_status()
            data = res.json()
            results = [{"title": r.get("full_name", ""), "url": r.get("html_url", ""), "snippet": r.get("description", ""), "source": "github"} for r in data.get("items", [])]
            logger.info(f"[fetch_github] {len(results)} results for query: {query}")
            return results
    except httpx.HTTPStatusError as e:
        logger.error(f"[fetch_github] HTTP {e.response.status_code}: {e.response.text[:500]}")
        return []
    except Exception as e:
        logger.error(f"[fetch_github] {type(e).__name__}: {e}")
        return []

async def fetch_arxiv(query: str):
    try:
        async with httpx.AsyncClient() as c:
            query_safe = query.replace(" ", "+")
            res = await c.get(f"https://export.arxiv.org/api/query?search_query=all:{query_safe}&start=0&max_results=3", timeout=10.0)
            res.raise_for_status()
            root = ET.fromstring(res.text)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            results = []
            for entry in root.findall('atom:entry', ns):
                title_el = entry.find('atom:title', ns)
                url_el = entry.find('atom:id', ns)
                summary_el = entry.find('atom:summary', ns)
                
                title = title_el.text if title_el is not None else ""
                url = url_el.text if url_el is not None else ""
                summary = summary_el.text if summary_el is not None else ""
                
                results.append({
                    "title": title.strip().replace('\n', ' '), 
                    "url": url.strip(), 
                    "snippet": summary.strip().replace('\n', ' '), 
                    "source": "arxiv"
                })
            logger.info(f"[fetch_arxiv] Success — {len(results)} results returned for query: {query[:80]}")
            return results
    except httpx.HTTPStatusError as e:
        logger.error(f"[fetch_arxiv] HTTP {e.response.status_code}: {e.response.text[:500]}")
        return []
    except Exception as e:
        logger.error(f"[fetch_arxiv] {type(e).__name__}: {e}")
        return []

async def fetch_semantic_scholar(query: str):
    """Semantic Scholar search — uses S2_API_KEY if available for higher rate limits."""
    s2_key = os.getenv("S2_API_KEY")
    headers = {}
    if s2_key:
        headers["x-api-key"] = s2_key
    else:
        logger.warning("[fetch_semantic_scholar] S2_API_KEY missing — using unauthenticated (strict rate limit)")

    try:
        async with httpx.AsyncClient() as c:
            res = await c.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={"query": query, "limit": 4, "fields": "title,abstract,url,tldr"},
                headers=headers,
                timeout=10.0,
            )
            res.raise_for_status()
            data = res.json()
            out = []
            for p in data.get("data", []):
                tldr = (p.get("tldr") or {}).get("text") if p.get("tldr") else None
                out.append({
                    "title": p.get("title", ""),
                    "url": p.get("url", ""),
                    "snippet": tldr or (p.get("abstract") or "")[:300],
                    "source": "semantic_scholar",
                })
            logger.info(f"[fetch_semantic_scholar] Success — {len(out)} results returned for query: {query[:80]}")
            return out
    except httpx.HTTPStatusError as e:
        logger.error(f"[fetch_semantic_scholar] HTTP {e.response.status_code}: {e.response.text[:500]}")
        return []
    except Exception as e:
        logger.error(f"[fetch_semantic_scholar] {type(e).__name__}: {e}")
        return []

async def refine_search_queries(idea: str) -> dict:
    """
    Turns the raw idea into three purpose-specific queries so each API
    gets a query it can actually use well, instead of one generic sentence.
    """
    system_prompt = (
        "You are a search query specialist. Given a project idea, produce three distinct, keyword-dense "
        "search queries optimized for different search engines. Do not repeat the same phrasing across all three. "
        "CRITICAL: The academic_query must use terms from the idea's actual domain (e.g., for an ecology/plant-related idea, "
        "use ecology/botany/horticulture terms — not generic engineering or control-systems jargon unless the idea is literally "
        "about engineering). Do not default to abstract technical vocabulary that doesn't match the idea's subject matter.\n"
        "CRITICAL: For the technical_query, use a dual strategy: If the idea is common (e.g., 'study buddy'), retain the "
        "exact domain identity to find exact repos. If the idea is highly niche or rare (e.g., 'terrarium AI'), extract the "
        "core technical components (e.g., 'plant climate monitoring IoT') so GitHub actually returns related results instead of 0. "
        "Never just return generic tech stacks like 'react nodejs chatbot'."
    )
    user_prompt = f"""
Idea: "{idea}"
Generate JSON:
{{
  "market_query": "string — 4-8 keywords for finding existing commercial products/competitors",
  "academic_query": "string — 3-6 keywords in academic phrasing for research papers",
  "technical_query": "string — 3-6 keywords (e.g., 'AI study buddy', not 'react nlp chatbot')"
}}
"""
    try:
        return await call_llm_json(system_prompt, user_prompt)
    except Exception as e:
        logger.error(f"Failed to refine queries: {e}")
        return {
            "market_query": idea,
            "academic_query": idea,
            "technical_query": idea
        }

def filter_academic_results(results: list, idea: str, query: str) -> list:
    """Filter academic results by requiring at least one non-generic keyword overlap with the idea or query."""
    stopwords = {
        "a", "an", "the", "and", "or", "but", "if", "for", "with", "to", "of", "in", "on", "at",
        "app", "application", "software", "system", "systems", "development", "management", 
        "sustainable", "artificial", "intelligence", "ai", "machine", "learning", "ml",
        "platform", "tool", "using", "based", "approach", "method", "model", "data", "analysis",
        "that", "helps", "people", "build", "create", "make", "smart", "automated", "technology",
        "project", "solution", "framework", "web", "mobile", "design", "implementation"
    }
    
    # Extract words from both the raw idea and the LLM-translated academic query
    idea_words = set(re.findall(r'\b[a-z]{3,}\b', idea.lower()))
    query_words = set(re.findall(r'\b[a-z]{3,}\b', query.lower()))
    
    # Remove 's' at the end for basic plural matching (e.g., terrariums -> terrarium)
    idea_words = {w[:-1] if w.endswith('s') else w for w in idea_words}
    query_words = {w[:-1] if w.endswith('s') else w for w in query_words}
    
    core_keywords = (idea_words | query_words) - stopwords
    
    if not core_keywords:
        return results

    filtered = []
    for r in results:
        title = r.get("title", "")
        title_words = set(re.findall(r'\b[a-z]{3,}\b', title.lower()))
        title_words = {w[:-1] if w.endswith('s') else w for w in title_words}
        
        if core_keywords.intersection(title_words):
            filtered.append(r)
        else:
            logger.info(f"Dropped off-topic academic source: {title}")
            
    return filtered
