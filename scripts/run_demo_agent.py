import asyncio, httpx, os
from dotenv import load_dotenv
load_dotenv()

URL = os.getenv("TRACEGUARD_URL", "http://localhost:8000")
FAILURES = ["infinite_loop","hallucination","tool_misuse","context_overflow","empty_response"]

async def main():
    print("🛡️ TraceGuard AI — Demo\n" + "="*40)
    async with httpx.AsyncClient() as c:
        for f in FAILURES:
            print(f"🔥 Simulating: {f}")
            r = await c.post(f"{URL}/api/webhook/simulate",
                             json={"failure_hint": f}, timeout=30)
            print(f"   → {r.status_code} | failure_id: {r.json().get('failure_id')}")
            await asyncio.sleep(2)
    print("\n✅ Done! Open http://localhost:5173")

asyncio.run(main())