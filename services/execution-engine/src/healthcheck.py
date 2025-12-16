#!/usr/bin/env python3
"""
Healthcheck para Execution Engine
"""
import sys
import asyncio
import aiohttp

async def check_health():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8001/health', timeout=5) as resp:
                if resp.status == 200:
                    print("✅ Execution Engine healthy")
                    return 0
                else:
                    print(f"❌ Health check failed: {resp.status}")
                    return 1
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return 1

if __name__ == "__main__":
    result = asyncio.run(check_health())
    sys.exit(result)
