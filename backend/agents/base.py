import os
import json
import logging
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
from groq import AsyncGroq

# Load environment variables
current_dir = os.path.dirname(os.path.abspath(__file__))
# Look for .env in parent (backend/.env) or current directory
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
load_dotenv(os.path.join(backend_dir, ".env"))
load_dotenv(os.path.join(current_dir, ".env"))

logger = logging.getLogger(__name__)

# Shared Groq Client
api_key = os.getenv("GROQ_API_KEY", "").strip()
client = AsyncGroq(api_key=api_key) if api_key and api_key != "your_key_here" else None

# Diagnostics
_tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
_github_token = os.getenv("GITHUB_TOKEN", "").strip()
logger.info(f"[STARTUP] GROQ_API_KEY present: {bool(api_key and api_key != 'your_key_here')}")
logger.info(f"[STARTUP] TAVILY_API_KEY present: {bool(_tavily_key)}, valid (non-placeholder): {bool(_tavily_key and _tavily_key != 'your_tavily_api_key_here')}")
logger.info(f"[STARTUP] GITHUB_TOKEN present: {bool(_github_token)}, valid (non-placeholder): {bool(_github_token and _github_token != 'your_github_token_here')}")

# Model Configuration (configurable via GROQ_MODEL in .env)
GROQ_MODEL = os.getenv("GROQ_MODEL", "").strip() or "openai/gpt-oss-120b"

async def call_llm_json(system_prompt: str, user_prompt: str, retry: bool = True, temperature: float = 0.7, model: str = None) -> dict:
    if not client:
        raise ValueError("Groq client not configured")
        
    target_model = model or GROQ_MODEL

    async def make_call(prompt_suffix=""):
        res = await client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + prompt_suffix}
            ],
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        return res.choices[0].message.content

    content = await make_call()
    
    def parse_content(text):
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    try:
        return parse_content(content)
    except Exception:
        if retry:
            logger.info("Retrying call_llm_json due to parse failure")
            content = await make_call("\nReturn valid JSON only, no other text")
            try:
                return parse_content(content)
            except Exception as e:
                raise ValueError(f"Failed to parse JSON twice. Raw output: {content}") from e
        else:
            raise ValueError(f"Failed to parse JSON. Raw output: {content}")
