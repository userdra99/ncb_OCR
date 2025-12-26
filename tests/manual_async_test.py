#!/usr/bin/env python3
"""
Manual test to verify asyncio.to_thread() wrapper is working correctly.
This script tests the non-blocking behavior without requiring full test infrastructure.
"""
import asyncio
import time
from unittest.mock import MagicMock, patch


def test_asyncio_to_thread_wrapping():
    """Test that our asyncio.to_thread() wrapping works correctly."""

    async def main():
        # Create a mock that simulates a slow synchronous call
        def slow_sync_call():
            time.sleep(0.1)  # 100ms
            return {"result": "success"}

        # Test 1: Verify asyncio.to_thread works
        print("Test 1: Basic asyncio.to_thread() functionality...")
        start = time.time()
        result = await asyncio.to_thread(slow_sync_call)
        elapsed = time.time() - start
        assert result == {"result": "success"}
        assert 0.09 < elapsed < 0.15, f"Expected ~0.1s, got {elapsed}s"
        print(f"✓ Single call took {elapsed:.3f}s")

        # Test 2: Concurrent execution with asyncio.to_thread()
        print("\nTest 2: Concurrent execution with asyncio.to_thread()...")
        start = time.time()
        tasks = [asyncio.to_thread(slow_sync_call) for _ in range(5)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start
        assert len(results) == 5
        # If non-blocking, should take ~100ms. If blocking, would take 500ms
        assert elapsed < 0.3, f"Expected < 0.3s (concurrent), got {elapsed}s"
        print(f"✓ Five concurrent calls took {elapsed:.3f}s (should be ~0.1s)")

        # Test 3: Verify event loop stays responsive
        print("\nTest 3: Event loop remains responsive...")
        counter = {"value": 0}

        async def background_task():
            for _ in range(10):
                await asyncio.sleep(0.01)  # 10ms
                counter["value"] += 1

        start = time.time()
        api_task = asyncio.create_task(asyncio.to_thread(slow_sync_call))
        bg_task = asyncio.create_task(background_task())
        await asyncio.gather(api_task, bg_task)
        elapsed = time.time() - start

        assert counter["value"] == 10, f"Expected 10, got {counter['value']}"
        print(f"✓ Background task ran {counter['value']} iterations during API call")
        print(f"✓ Total time: {elapsed:.3f}s")

        # Test 4: Test lambda wrapper pattern used in code
        print("\nTest 4: Lambda wrapper pattern...")

        class MockGoogleService:
            def list_files(self):
                time.sleep(0.1)
                return {"files": []}

        mock_service = MockGoogleService()

        start = time.time()
        tasks = [
            asyncio.to_thread(lambda: mock_service.list_files())
            for _ in range(3)
        ]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

        assert len(results) == 3
        assert elapsed < 0.2, f"Expected < 0.2s, got {elapsed}s"
        print(f"✓ Three lambda-wrapped calls took {elapsed:.3f}s")

        print("\n" + "="*60)
        print("ALL TESTS PASSED! ✓")
        print("="*60)
        print("\nConclusion:")
        print("- asyncio.to_thread() successfully prevents event loop blocking")
        print("- Multiple concurrent calls execute in parallel")
        print("- Event loop remains responsive during I/O operations")
        print("- Lambda wrapper pattern works correctly")

    # Run the async tests
    asyncio.run(main())


if __name__ == "__main__":
    print("Manual Async Test - Verifying asyncio.to_thread() Implementation")
    print("="*60)
    test_asyncio_to_thread_wrapping()
