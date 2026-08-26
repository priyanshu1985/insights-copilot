import json
import logging
from typing import List
from datetime import datetime
from collections import Counter
from .base import call_llm_json

logger = logging.getLogger(__name__)

def compute_milestone_pace(all_completions: List[dict]) -> dict:
    try:
        pool_deltas = []
        qualifying_workspace_count = 0
        
        for ws in all_completions:
            completions = ws.get("completions", [])
            if len(completions) >= 2:
                # Ensure sorted by completed_at
                completions_sorted = sorted(
                    completions,
                    key=lambda x: datetime.fromisoformat(x["completed_at"].replace("Z", "+00:00"))
                )
                
                qualifying_workspace_count += 1
                for i in range(1, len(completions_sorted)):
                    prev_ts = datetime.fromisoformat(completions_sorted[i-1]["completed_at"].replace("Z", "+00:00"))
                    curr_ts = datetime.fromisoformat(completions_sorted[i]["completed_at"].replace("Z", "+00:00"))
                    delta_days = (curr_ts - prev_ts).total_seconds() / (24 * 3600)
                    pool_deltas.append(delta_days)
                    
        if not pool_deltas:
            return {"avg_days": None, "label": "Not enough data", "workspace_count": 0}
            
        avg_days = sum(pool_deltas) / len(pool_deltas)
        avg_days = round(avg_days, 1)
        
        return {"avg_days": avg_days, "label": f"{avg_days} days per milestone", "workspace_count": qualifying_workspace_count}
    except Exception as e:
        logger.error(f"Failed to compute milestone pace: {e}")
        return {"avg_days": None, "label": "Not enough data", "workspace_count": 0}

async def generate_founder_insight(workspace_summaries: List[dict]) -> dict:
    logger.info("Starting generate_founder_insight")
    if len(workspace_summaries) < 2:
        return {"total_ideas": len(workspace_summaries), "insufficient_data": True}
        
    total_ideas = len(workspace_summaries)
    
    scores = []
    weak_criteria = []
    tech_stacks = []
    risk_dist = {"low": 0, "medium": 0, "high": 0}
    
    for w in workspace_summaries:
        # Score calculation matching WorkspaceDashboard.jsx
        criteria = w.get("critique", {}).get("criteria", {})
        total_crit = len(criteria)
        passed_crit = sum(1 for v in criteria.values() if isinstance(v, dict) and v.get("pass"))
        base_score = round((passed_crit / total_crit) * 100) if total_crit > 0 else 75
        
        market_potential = min(95, max(60, 100 - len(w.get("research", {}).get("existing_solutions", [])) * 7))
        tech_feasibility = min(95, max(50, 60 + len(w.get("plan", {}).get("tech_stack", [])) * 4))
        
        scalable_pass = criteria.get("scalable", {}).get("pass", False) if isinstance(criteria.get("scalable"), dict) else False
        actionable_pass = criteria.get("actionable", {}).get("pass", False) if isinstance(criteria.get("actionable"), dict) else False
        business_viability = 85 if (scalable_pass and actionable_pass) else (75 if scalable_pass else 65)
        
        # COMPOSITE SCORE FORMULA — must stay in sync with WorkspaceDashboard.jsx's startupScore calculation.
        startup_score = round((base_score + market_potential + tech_feasibility + business_viability) / 4)
        scores.append(startup_score)
        
        # Weak criteria
        for k, v in criteria.items():
            if isinstance(v, dict) and not v.get("pass"):
                weak_criteria.append(k)
                
        # Risk calculation
        flagged_issues = w.get("critique", {}).get("flagged_issues", [])
        flagged_count = len(flagged_issues)
        if flagged_count == 0:
            risk_dist["low"] += 1
        elif flagged_count <= 2:
            risk_dist["medium"] += 1
        else:
            risk_dist["high"] += 1
                
        # Tech stack
        tech_stacks.extend(w.get("plan", {}).get("tech_stack", []))
        
    avg_score = round(sum(scores) / len(scores)) if scores else 0
    
    most_common_weak_criterion = Counter(weak_criteria).most_common(1)[0][0] if weak_criteria else "None"
    most_common_tech_stack = [item[0] for item in Counter(tech_stacks).most_common(3)]
    
    system_prompt = (
        "You are an expert Startup Advisor analyzing a founder's past projects. "
        "Given these exact statistics about a user's past project ideas, write a 2-3 sentence personalized insight "
        "referencing the specific numbers provided, plus one specific, actionable suggestion for their next idea. "
        "Do not invent any statistic not given to you."
    )
    
    stats_payload = {
        "total_ideas": total_ideas,
        "avg_score": avg_score,
        "most_common_weak_criterion": most_common_weak_criterion,
        "most_common_tech_stack": most_common_tech_stack
    }
    
    user_prompt = f"""
Statistics: {json.dumps(stats_payload)}

Generate JSON:
{{
  "total_ideas": {total_ideas},
  "avg_score": {avg_score},
  "most_common_weak_criterion": "{most_common_weak_criterion}",
  "most_common_tech_stack": {json.dumps(most_common_tech_stack)},
  "insight": "string, 2-3 sentences",
  "suggested_focus": "string, 1 sentence"
}}
"""
    try:
        result = await call_llm_json(system_prompt, user_prompt)
        # Ensure stats are accurate regardless of what LLM hallucinates
        result["total_ideas"] = total_ideas
        result["avg_score"] = avg_score
        result["most_common_weak_criterion"] = most_common_weak_criterion
        result["most_common_tech_stack"] = most_common_tech_stack
        result["risk_distribution"] = risk_dist
        logger.info("Successfully completed generate_founder_insight")
        return result
    except Exception as e:
        logger.error(f"Failed generate_founder_insight: {e}")
        return {
            **stats_payload,
            "insight": "Unable to generate insight at this time.",
            "suggested_focus": "Keep iterating on your ideas."
        }
