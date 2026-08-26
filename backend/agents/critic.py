import json
import logging
from .base import call_llm_json

logger = logging.getLogger(__name__)

async def critic_agent(idea: str, research: dict, plan: dict) -> dict:
    logger.info("Starting critic_agent")
    fallback = {
        "overall_verdict": "needs_revision",
        "criteria": {
            "accurate": { "pass": False, "note": "Unable to generate — please retry." },
            "verifiable": { "pass": False, "note": "Unable to generate — please retry." },
            "scalable": { "pass": False, "note": "Unable to generate — please retry." },
            "actionable": { "pass": False, "note": "Unable to generate — please retry." }
        },
        "flagged_issues": [],
        "suggested_fixes": []
    }
    try:
        research_str = json.dumps(research)
        plan_str = json.dumps(plan)
        
        total_prompt_chars = len(research_str) + len(plan_str)
        logger.info(f"[critic_agent] Prompt payload size: research={len(research_str)} chars, plan={len(plan_str)} chars, total={total_prompt_chars} chars")

        system_prompt = (
            "You are an expert Technical Critic. Review the provided project plan against four criteria: accurate, verifiable, scalable, actionable. "
            "Do not regenerate the plan — only flag issues and give a pass/fail verdict. "
            "If any criterion fails, overall_verdict must be 'needs_revision' and flagged_issues/suggested_fixes must be non-empty. "
            "Keep notes concise (< 50 words). "
            "Every criterion's note must name the specific missing or problematic element — never a vague restatement of the criterion name itself."
        )
        user_prompt = f"""
Idea: "{idea}"
Research: {research_str}
Plan: {plan_str}

Generate JSON:
{{
  "overall_verdict": "ready | needs_revision",
  "criteria": {{
    "accurate": {{ "pass": true, "note": "string, 1 sentence" }},
    "verifiable": {{ "pass": true, "note": "string, 1 sentence" }},
    "scalable": {{ "pass": true, "note": "string, 1 sentence" }},
    "actionable": {{ "pass": true, "note": "string, 1 sentence" }}
  }},
  "flagged_issues": ["string, 1 sentence each — empty list if none"],
  "suggested_fixes": ["string, 1 sentence each — empty list if none"]
}}
"""
        result = await call_llm_json(system_prompt, user_prompt)
        logger.info("Successfully completed critic_agent")
        return result
    except Exception as e:
        logger.error(f"[critic_agent] {type(e).__name__}: {e}", exc_info=True)
        return fallback
