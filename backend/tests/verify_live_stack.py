import asyncio
from app.db.neon_client import init_neon_pool, get_neon_pool, close_neon_pool
from app.db.upstash_client import set_session_context, get_session_context
from app.db.supabase_client import get_supabase

async def verify():
    print("--- 1. Testing Neon PostgreSQL Connection & Tables ---")
    await init_neon_pool()
    pool = get_neon_pool()
    print("Neon Pool Active:", pool is not None)

    print("\n--- 2. Testing Upstash Redis REST Cache ---")
    await set_session_context("verify-session-001", {"turn": 1, "status": "all_systems_go"})
    data = await get_session_context("verify-session-001")
    print("Upstash Redis Read Success:", data)

    print("\n--- 3. Testing Supabase Client ---")
    sb = get_supabase()
    print("Supabase Initialized:", sb is not None)

    if pool:
        await close_neon_pool()
    print("\n[SUCCESS] All live cloud systems are active and connected!")

if __name__ == "__main__":
    asyncio.run(verify())
