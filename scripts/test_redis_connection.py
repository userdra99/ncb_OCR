#!/usr/bin/env python3
"""Test Redis connection from inside Docker container."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import redis.asyncio as aioredis
from src.config.settings import settings

async def test_connection():
    """Test Redis connection."""
    print(f"Testing Redis connection to: {settings.redis.url}")

    try:
        redis_client = await aioredis.from_url(
            settings.redis.url,
            decode_responses=True
        )

        # Test ping
        pong = await redis_client.ping()
        print(f"✅ Redis PING successful: {pong}")

        # Test scan for job keys
        cursor = 0
        job_count = 0
        cursor, keys = await redis_client.scan(cursor=cursor, match="job:*", count=100)
        job_count = len(keys)
        print(f"✅ Redis SCAN successful: Found {job_count} job keys (cursor: {cursor})")

        await redis_client.close()
        print("✅ Redis connection test PASSED")
        return 0

    except Exception as e:
        print(f"❌ Redis connection test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(asyncio.run(test_connection()))
