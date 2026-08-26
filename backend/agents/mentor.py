import json
import logging
from .base import call_llm_json

logger = logging.getLogger(__name__)

async def mentor_agent(idea: str, research: dict, plan: dict, question: str, experience_level: str = "intermediate") -> dict:
    logger.info("Starting mentor_agent")
    fallback = {
        "answer": "Unable to generate — please retry.",
        "learning_resources": []
    }
    try:
        level_instruction = {
            "beginner": "The user is a beginner. Use plain language, no unexplained jargon, 3-4 short sentences, and use an analogy if it helps.",
            "intermediate": "The user has intermediate experience. Assume basic software and startup familiarity.",
            "advanced": "The user is advanced. Be precise and dense, skip basic definitions."
        }.get(experience_level, "The user has intermediate experience. Assume basic software and startup familiarity.")
        
        system_prompt = (
            "You are an expert Startup Mentor. Answer a specific follow-up question from the user. "
            "Ground your answer in the provided research and plan. Don't answer from generic knowledge if the provided dicts contain the answer. "
            "learning_resources: 0-3 items, only include if genuinely relevant to the question. "
            f"Keep answer concise. {level_instruction}"
        )
        user_prompt = f"""
Idea: "{idea}"
Research: {json.dumps(research)}
Plan: {json.dumps(plan)}
Question: "{question}"

Generate JSON:
{{
  "answer": "string, 2-5 sentences",
  "learning_resources": [
    {{ "title": "string, name of the resource", "url": "string, a valid URL" }}
  ]
}}
"""
        result = await call_llm_json(system_prompt, user_prompt)
        logger.info("Successfully completed mentor_agent")
        return result
    except Exception as e:
        logger.error(f"Failed mentor_agent: {e}")
        return fallback
