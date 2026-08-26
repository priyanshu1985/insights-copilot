import os
import sys
import asyncio
# pyrefly: ignore [missing-import]
import httpx
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure backend directory is in path and env is loaded
backend_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(backend_dir, ".env"))

print("=" * 60)
print("INSIGHTS-COPILOT ENVIRONMENT & CREDENTIALS CHECKER")
print("=" * 60)

async def test_groq():
    print("\n1. Testing GROQ_API_KEY...")
    key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "").strip() or "openai/gpt-oss-120b"
    if not key or key == "your_key_here":
        print("   [FAIL] GROQ_API_KEY is missing or placeholder.")
        return False
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=key)
        res = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'OK'"}],
            max_tokens=10,
            temperature=0.1
        )
        response_text = res.choices[0].message.content.strip()
        print(f"   [PASS] Groq API connection successful! (Model: {model}, Response: '{response_text}')")
        return True
    except Exception as e:
        print(f"   [FAIL] Groq API Failed: {e}")
        return False

async def test_tavily():
    print("\n2. Testing TAVILY_API_KEY...")
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key or key == "your_tavily_api_key_here":
        print("   [FAIL] TAVILY_API_KEY is missing or placeholder.")
        return False
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("https://api.tavily.com/search", json={
                "api_key": key,
                "query": "startup validation",
                "search_depth": "basic",
                "max_results": 1
            }, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                results_count = len(data.get("results", []))
                print(f"   [PASS] Tavily API successful! ({results_count} result returned)")
                return True
            else:
                print(f"   [FAIL] Tavily API returned HTTP {res.status_code}: {res.text}")
                return False
    except Exception as e:
        print(f"   [FAIL] Tavily API Failed: {e}")
        return False

async def test_github():
    print("\n3. Testing GITHUB_TOKEN...")
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token or token == "your_github_token_here":
        print("   [WARN] GITHUB_TOKEN is missing or placeholder (unauthenticated fallback will be used).")
        return False
    try:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}"
        }
        async with httpx.AsyncClient() as client:
            res = await client.get("https://api.github.com/rate_limit", headers=headers, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                core_rate = data.get("resources", {}).get("core", {})
                limit = core_rate.get("limit")
                remaining = core_rate.get("remaining")
                print(f"   [PASS] GitHub Token is VALID! (Rate limit: {remaining}/{limit} remaining)")
                return True
            else:
                print(f"   [FAIL] GitHub Token returned HTTP {res.status_code}: {res.text}")
                return False
    except Exception as e:
        print(f"   [FAIL] GitHub Token Test Failed: {e}")
        return False

async def test_telegram():
    print("\n4. Testing TELEGRAM_BOT_TOKEN...")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "your_telegram_bot_token_here":
        print("   [WARN] TELEGRAM_BOT_TOKEN is missing or placeholder.")
        return False
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                if data.get("ok"):
                    bot_info = data.get("result", {})
                    print(f"   [PASS] Telegram Bot Token is VALID! (Bot: @{bot_info.get('username')}, Name: {bot_info.get('first_name')})")
                    return True
                else:
                    print(f"   [FAIL] Telegram getMe failed: {data}")
                    return False
            else:
                print(f"   [FAIL] Telegram API returned HTTP {res.status_code}: {res.text}")
                return False
    except Exception as e:
        print(f"   [FAIL] Telegram Bot Test Failed: {e}")
        return False

def test_supabase():
    print("\n5. Testing SUPABASE Connection & Credentials...")
    url = os.getenv("SUPABASE_URL", "").strip()
    anon_key = os.getenv("SUPABASE_KEY", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    if not url:
        print("   [FAIL] SUPABASE_URL is missing.")
        return False
    
    from supabase import create_client
    
    # Test Service Role Key first
    service_role_ok = False
    if service_key:
        try:
            client = create_client(url, service_key)
            res = client.table("history").select("id").limit(1).execute()
            print(f"   [PASS] Supabase SERVICE_ROLE_KEY is working! Connected to {url}")
            service_role_ok = True
        except Exception as e:
            print(f"   [FAIL] Supabase with SERVICE_ROLE_KEY failed: {e}")
    else:
        print("   [WARN] SUPABASE_SERVICE_ROLE_KEY is not set.")

    # Test Anon Key
    anon_ok = False
    if anon_key:
        try:
            client = create_client(url, anon_key)
            res = client.table("history").select("id").limit(1).execute()
            print(f"   [PASS] Supabase ANON KEY is working! Connected to {url}")
            anon_ok = True
        except Exception as e:
            print(f"   [WARN] Supabase with ANON KEY notice/error: {e}")
    else:
        print("   [WARN] SUPABASE_KEY is not set.")
        
    return bool(service_role_ok or anon_ok)

async def main():
    results = {}
    results["Groq"] = await test_groq()
    results["Tavily"] = await test_tavily()
    results["GitHub"] = await test_github()
    results["Telegram"] = await test_telegram()
    results["Supabase"] = test_supabase()
    
    print("\n" + "=" * 60)
    print("SUMMARY OF CREDENTIAL CHECKS")
    print("=" * 60)
    for service, status in results.items():
        icon = "[PASS] ACTIVE" if status else "[FAIL] INACTIVE"
        print(f"  {service.ljust(12)} : {icon}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
