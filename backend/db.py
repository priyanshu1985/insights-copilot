import os
import json
import logging
# pyrefly: ignore [missing-import]
from supabase import create_client, Client
from datetime import datetime

logger = logging.getLogger(__name__)

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    # Prefer service role key (bypasses RLS) for server-side operations;
    # fall back to SUPABASE_KEY for backwards compat during transition.
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.environ.get("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables are missing.")
    return create_client(url, key)

def init_db():
    url = os.environ.get("SUPABASE_URL", "").strip()
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    anon_key = os.environ.get("SUPABASE_KEY", "").strip()
    key = service_key or anon_key
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables are missing. Startup halted.")
    key_type = "service_role" if service_key else "anon (WARNING: RLS will block writes)"
    logger.info(f"Supabase configured pointing to {url} using {key_type} key")

def save_history(idea: str, result: dict, user_id: str = None):
    try:
        supabase = get_supabase()
        payload = {
            "idea": idea,
            "result": result
        }
        if user_id:
            payload["user_id"] = user_id
        supabase.table("history").insert(payload).execute()
    except Exception as e:
        logger.error(f"Failed to save history to Supabase: {e}")

def get_all_history_summaries(user_id: str = None, saved_only: bool = False):
    try:
        supabase = get_supabase()
        
        # 1. Fetch saved workspace IDs if filtering is needed or to map is_saved state
        saved_query = supabase.table("workspaces").select("id")
        if user_id:
            saved_query = saved_query.eq("user_id", user_id)
        saved_query = saved_query.eq("is_saved", True)
        saved_res = saved_query.execute()
        saved_ids = {row["id"] for row in saved_res.data} if saved_res.data else set()

        # 2. Query history items
        query = supabase.table("history").select("id, idea, timestamp, workspace_id:result->workspace_id")
        if user_id:
            query = query.eq("user_id", user_id)
            
        if saved_only:
            if not saved_ids:
                return []
            query = query.in_("result->>workspace_id", list(saved_ids))
            
        query = query.order("id", desc=True)
        response = query.execute()
        
        result_data = []
        for row in (response.data or []):
            ws_id = row.get("workspace_id")
            result_data.append({
                "id": row["id"],
                "idea": row["idea"],
                "timestamp": row["timestamp"],
                "workspace_id": ws_id,
                "is_saved": ws_id in saved_ids if ws_id else False
            })
        return result_data
    except Exception as e:
        logger.error(f"Failed to get history summaries from Supabase: {e}")
        return []

def get_history_by_id(history_id: int, user_id: str = None):
    try:
        supabase = get_supabase()
        query = supabase.table("history").select("result")
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.eq("id", history_id).execute()
        if response.data and len(response.data) > 0:
            result_payload = response.data[0]["result"]
            ws_id = result_payload.get("workspace_id")
            if ws_id:
                ws_res = supabase.table("workspaces").select("is_saved").eq("id", ws_id).execute()
                is_saved = ws_res.data[0]["is_saved"] if ws_res.data else False
                result_payload["is_saved"] = is_saved
                
                # Fetch active chat_history from workspace if exists
                ws_data = get_workspace(ws_id, user_id)
                if ws_data:
                    result_payload["chat_history"] = ws_data.get("chat_history", [])
                else:
                    result_payload["chat_history"] = []
            else:
                result_payload["chat_history"] = []
            return result_payload
        return None
    except Exception as e:
        logger.error(f"Failed to get history item {history_id} from Supabase: {e}")
        return None

def create_workspace(workspace_id: str, idea: str, research: dict, plan: dict, user_id: str = None, critique: dict = None):
    try:
        supabase = get_supabase()
        research_data = dict(research) if research else {}
        if critique is not None:
            research_data["_critique"] = critique
            
        payload = {
            "id": workspace_id,
            "idea": idea,
            "research_json": research_data,
            "plan_json": plan,
            "is_saved": False,
            "user_id": user_id
        }
        supabase.table("workspaces").insert(payload).execute()
    except Exception as e:
        logger.error(f"Failed to create workspace in Supabase: {e}")

def delete_workspace(workspace_id: str, user_id: str = None):
    try:
        supabase = get_supabase()
        query = supabase.table("workspaces").delete().eq("id", workspace_id)
        if user_id:
            query = query.eq("user_id", user_id)
        query.execute()

        # Also delete matching records from history table
        history_query = supabase.table("history").delete().eq("result->>workspace_id", workspace_id)
        if user_id:
            history_query = history_query.eq("user_id", user_id)
        history_query.execute()
    except Exception as e:
        logger.error(f"Failed to delete workspace from Supabase: {e}")
        raise e

def delete_history_item(history_id: int, user_id: str = None):
    try:
        supabase = get_supabase()
        query = supabase.table("history").delete().eq("id", history_id)
        if user_id:
            query = query.eq("user_id", user_id)
        query.execute()
    except Exception as e:
        logger.error(f"Failed to delete history item {history_id} from Supabase: {e}")
        raise e


def get_workspace(workspace_id: str, user_id: str = None):
    try:
        supabase = get_supabase()
        query = supabase.table("workspaces").select("*").eq("id", workspace_id)
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            research = dict(row["research_json"] or {})
            critique = research.pop("_critique", {})
            # Try to get chat_history from column, or fallback to research_json
            chat_history = row.get("chat_history")
            if chat_history is None:
                chat_history = research.pop("chat_history", [])
            else:
                # Remove from research if it was popped out or is in there
                research.pop("chat_history", None)
            return {
                "id": row["id"],
                "idea": row["idea"],
                "research": research,
                "plan": row["plan_json"],
                "is_saved": row.get("is_saved", False),
                "critique": critique,
                "chat_history": chat_history,
                "tags": row.get("tags") or []
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get workspace {workspace_id} from Supabase: {e}")
        return None

def get_workspace_by_idea(idea: str, user_id: str):
    try:
        supabase = get_supabase()
        query = supabase.table("workspaces").select("*").ilike("idea", idea.strip())
        if user_id:
            query = query.eq("user_id", user_id)
        res = query.execute()
        if res.data:
            row = res.data[0]
            research = dict(row["research_json"] or {})
            critique = research.pop("_critique", {})
            # extract chat_history
            chat_history = row.get("chat_history")
            if chat_history is None:
                chat_history = research.pop("chat_history", [])
            else:
                research.pop("chat_history", None)
            return {
                "id": row["id"],
                "idea": row["idea"],
                "research": research,
                "plan": row["plan_json"],
                "is_saved": row.get("is_saved", False),
                "critique": critique,
                "chat_history": chat_history,
                "tags": row.get("tags") or []
            }
        return None
    except Exception as e:
        logger.error(f"Failed to find workspace by idea '{idea}': {e}")
def get_workspaces_for_user(user_id: str):
    try:
        supabase = get_supabase()
        res = supabase.table("workspaces").select("*").eq("user_id", user_id).execute()
        return res.data if res.data else []
    except Exception as e:
        logger.error(f"Failed to get workspaces for user {user_id}: {e}")
        return []

def update_workspace_research(workspace_id: str, research: dict, user_id: str = None):
    try:
        supabase = get_supabase()
        # Retrieve existing workspace to preserve critique data
        query = supabase.table("workspaces").select("research_json").eq("id", workspace_id)
        if user_id:
            query = query.eq("user_id", user_id)
        res = query.execute()
        
        updated_research = dict(research) if research else {}
        if res.data:
            existing_critique = (res.data[0].get("research_json") or {}).get("_critique")
            if existing_critique:
                updated_research["_critique"] = existing_critique

        query = supabase.table("workspaces").update({
            "research_json": updated_research
        }).eq("id", workspace_id)
        if user_id:
            query = query.eq("user_id", user_id)
        query.execute()
    except Exception as e:
        logger.error(f"Failed to update workspace research in Supabase: {e}")
        raise e

def toggle_save_workspace(workspace_id: str, user_id: str = None):
    try:
        supabase = get_supabase()
        query = supabase.table("workspaces").select("is_saved")
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.eq("id", workspace_id).execute()
        
        if not response.data:
            raise ValueError(f"Workspace {workspace_id} not found or not owned by user.")
            
        current_saved = response.data[0].get("is_saved", False)
        new_saved = not current_saved
        
        from datetime import datetime, timezone
        
        update_data = {"is_saved": new_saved}
        if new_saved:
            update_data["saved_at"] = datetime.now(timezone.utc).isoformat()
            
        update_query = supabase.table("workspaces").update(update_data).eq("id", workspace_id)
        if user_id:
            update_query = update_query.eq("user_id", user_id)
        update_query.execute()
        
        return {"workspace_id": workspace_id, "is_saved": new_saved}
    except Exception as e:
        logger.error(f"Failed to toggle save for workspace {workspace_id}: {e}")
        raise e

def link_telegram(chat_id: str, workspace_id: str):
    try:
        supabase = get_supabase()
        supabase.table("telegram_links").upsert({
            "chat_id": str(chat_id),
            "workspace_id": workspace_id,
            "current_milestone_index": 0,
            "linked_at": "now()",
            "last_reminder_at": None
        }).execute()
    except Exception as e:
        logger.error(f"Failed to link telegram {chat_id} to {workspace_id} in Supabase: {e}")

def get_telegram_link(chat_id: str):
    try:
        supabase = get_supabase()
        response = supabase.table("telegram_links").select("*").eq("chat_id", str(chat_id)).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to get telegram link {chat_id} from Supabase: {e}")
        return None

def update_milestone_index(chat_id: str, new_index: int):
    try:
        supabase = get_supabase()
        supabase.table("telegram_links").update({
            "current_milestone_index": new_index,
            "last_reminder_at": None
        }).eq("chat_id", str(chat_id)).execute()
    except Exception as e:
        logger.error(f"Failed to update milestone index for {chat_id} in Supabase: {e}")

def get_all_telegram_links():
    try:
        supabase = get_supabase()
        response = supabase.table("telegram_links").select("*").execute()
        return response.data
    except Exception as e:
        logger.error(f"Failed to get all telegram links from Supabase: {e}")
        return []

def update_last_reminder(chat_id: str):
    try:
        supabase = get_supabase()
        supabase.table("telegram_links").update({
            "last_reminder_at": "now()"
        }).eq("chat_id", str(chat_id)).execute()
    except Exception as e:
        logger.error(f"Failed to update last_reminder_at for {chat_id} in Supabase: {e}")

def get_user_settings(user_id: str) -> dict:
    try:
        supabase = get_supabase()
        response = supabase.table("user_settings").select("theme, primary_model, experience_level").eq("user_id", user_id).execute()
        if response.data:
            row = response.data[0]
            return {
                "theme": row.get("theme", "dark"),
                "primary_model": row.get("primary_model", "gemini"),
                "experience_level": row.get("experience_level", "intermediate")
            }
        
        default_settings = {"user_id": user_id, "theme": "dark", "primary_model": "gemini", "experience_level": "intermediate"}
        try:
            supabase.table("user_settings").insert(default_settings).execute()
        except Exception as insert_err:
            logger.warning(f"Could not insert user settings (table might be missing): {insert_err}")
        return {"theme": "dark", "primary_model": "gemini", "experience_level": "intermediate"}
    except Exception as e:
        logger.error(f"Failed to get user settings: {e}")
        return {"theme": "dark", "primary_model": "gemini", "experience_level": "intermediate"}

def update_user_settings(user_id: str, theme: str, primary_model: str = None, experience_level: str = None) -> dict:
    try:
        if theme not in ["light", "dark"]:
            raise ValueError("Theme must be 'light' or 'dark'")
        if primary_model and primary_model not in ["gemini", "grok"]:
            raise ValueError("Primary model must be 'gemini' or 'grok'")
        if experience_level and experience_level not in ["beginner", "intermediate", "advanced"]:
            raise ValueError("Experience level must be 'beginner', 'intermediate', or 'advanced'")
            
        payload = {
            "user_id": user_id,
            "theme": theme,
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
        if primary_model:
            payload["primary_model"] = primary_model
        if experience_level:
            payload["experience_level"] = experience_level
            
        supabase = get_supabase()
        try:
            supabase.table("user_settings").upsert(payload).execute()
        except Exception as upsert_err:
            logger.warning(f"Could not upsert user settings (table might be missing): {upsert_err}")
            
        ret = {"theme": theme}
        if primary_model:
            ret["primary_model"] = primary_model
        if experience_level:
            ret["experience_level"] = experience_level
        return ret
    except Exception as e:
        logger.error(f"Failed to update user settings: {e}")
        ret = {"theme": theme}
        if primary_model:
            ret["primary_model"] = primary_model
        if experience_level:
            ret["experience_level"] = experience_level
        return ret

def get_telegram_link_by_workspace_id(workspace_id: str):
    try:
        supabase = get_supabase()
        response = supabase.table("telegram_links").select("*").eq("workspace_id", workspace_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to get telegram link for workspace {workspace_id}: {e}")
        return None

def save_mentor_chat(workspace_id: str, question: str, answer: str, user_id: str = None):
    try:
        supabase = get_supabase()
        payload = {
            "workspace_id": workspace_id,
            "question": question,
            "answer": answer
        }
        if user_id:
            payload["user_id"] = user_id
        supabase.table("mentor_chats").insert(payload).execute()
    except Exception as e:
        logger.error(f"Failed to save mentor chat for workspace {workspace_id}: {e}")

def update_workspace_chat_history(workspace_id: str, chat_history: list, user_id: str = None):
    try:
        supabase = get_supabase()
        # Try updating the chat_history column directly
        try:
            query = supabase.table("workspaces").update({
                "chat_history": chat_history
            }).eq("id", workspace_id)
            if user_id:
                query = query.eq("user_id", user_id)
            query.execute()
        except Exception as col_err:
            # Column doesn't exist, fallback to saving inside research_json
            logger.info(f"chat_history column not found or error, falling back to research_json: {col_err}")
            query = supabase.table("workspaces").select("research_json").eq("id", workspace_id)
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.execute()
            if res.data:
                research = dict(res.data[0].get("research_json") or {})
                research["chat_history"] = chat_history
                
                query_update = supabase.table("workspaces").update({
                    "research_json": research
                }).eq("id", workspace_id)
                if user_id:
                    query_update = query_update.eq("user_id", user_id)
                query_update.execute()
    except Exception as e:
        logger.error(f"Failed to update chat history for workspace {workspace_id}: {e}")
        raise e

def mark_milestone_complete(workspace_id: str, user_id: str = None) -> dict:
    try:
        supabase = get_supabase()
        
        query = supabase.table("workspaces").select("current_milestone_index, milestone_completions, plan_json").eq("id", workspace_id)
        if user_id:
            query = query.eq("user_id", user_id)
        res = query.execute()
        
        if not res.data:
            raise ValueError(f"Workspace {workspace_id} not found.")
            
        row = res.data[0]
        current_index = row.get("current_milestone_index") or 0
        milestone_completions = row.get("milestone_completions") or []
        plan_json = row.get("plan_json") or {}
        roadmap = plan_json.get("roadmap", [])
        total_milestones = len(roadmap)
        
        if current_index >= total_milestones:
            raise ValueError('All milestones already completed')
            
        from datetime import datetime, timezone
        updated_list = list(milestone_completions)
        updated_list.append({"index": current_index, "completed_at": datetime.now(timezone.utc).isoformat()})
        
        new_index = current_index + 1
        
        # update workspaces
        update_ws_query = supabase.table("workspaces").update({
            "current_milestone_index": new_index,
            "milestone_completions": updated_list
        }).eq("id", workspace_id)
        if user_id:
            update_ws_query = update_ws_query.eq("user_id", user_id)
        update_ws_query.execute()
        
        # update telegram_links
        try:
            supabase.table("telegram_links").update({
                "current_milestone_index": new_index
            }).eq("workspace_id", workspace_id).execute()
        except Exception as tel_err:
            logger.warning(f"Failed to sync milestone to telegram link: {tel_err}")
            
        return {
            "workspace_id": workspace_id,
            "current_milestone_index": new_index,
            "milestone_completions": updated_list,
            "total_milestones": total_milestones
        }
    except Exception as e:
        logger.error(f"Failed to mark milestone complete for workspace {workspace_id}: {e}")
        raise e

def get_all_workspaces_milestone_data(user_id: str) -> list[dict]:
    try:
        supabase = get_supabase()
        res = supabase.table("workspaces").select("id, milestone_completions").eq("user_id", user_id).execute()
        
        result = []
        for row in (res.data or []):
            result.append({
                "workspace_id": row["id"],
                "milestone_completions": row.get("milestone_completions") or []
            })
        return result
    except Exception as e:
        logger.error(f"Failed to get milestone data for user {user_id}: {e}")
        return []
