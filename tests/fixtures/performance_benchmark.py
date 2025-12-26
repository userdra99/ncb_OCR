#!/usr/bin/env python3
"""Performance benchmark for CPU-mode OCR processing."""

import asyncio
import sys
import time
from pathlib import Path
import statistics

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.services.ocr_service import OCRService
from src.utils.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)


async def benchmark_ocr_performance(iterations=10):
    """Run performance benchmark on OCR service."""
    print(f"\n⏱️  OCR Performance Benchmark (CPU Mode)")
    print("=" * 80)
    print(f"Iterations: {iterations}")
    print(f"Test image: malaysian_receipt_test.jpg")
    print("=" * 80)

    test_receipt = Path("/app/data/temp/test_receipt.jpg")

    if not test_receipt.exists():
        print(f"❌ Test receipt not found: {test_receipt}")
        return False

    try:
        # Initialize OCR service
        print("\n📦 Initializing OCR service...")
        init_start = time.time()
        ocr_service = OCRService()
        init_time = time.time() - init_start
        print(f"✅ OCR initialized in {init_time:.3f}s")

        # Warm-up run
        print("\n🔥 Warm-up run...")
        warmup_start = time.time()
        _ = await ocr_service.extract_structured_data(test_receipt)
        warmup_time = time.time() - warmup_start
        print(f"✅ Warm-up complete in {warmup_time:.3f}s")

        # Benchmark runs
        print(f"\n🏁 Running {iterations} benchmark iterations...")
        raw_times = []
        struct_times = []
        total_times = []
        confidences = []

        for i in range(iterations):
            # Raw extraction timing
            raw_start = time.time()
            ocr_result = await ocr_service.extract_text(test_receipt)
            raw_time = time.time() - raw_start
            raw_times.append(raw_time)

            # Structured extraction timing
            struct_start = time.time()
            extraction_result = await ocr_service.extract_structured_data(test_receipt)
            struct_time = time.time() - struct_start
            struct_times.append(struct_time)
            total_times.append(raw_time + struct_time)
            confidences.append(extraction_result.confidence_score)

            print(f"   Run {i+1}/{iterations}: {struct_time:.3f}s (confidence: {extraction_result.confidence_score:.2%})")

        # Calculate statistics
        print("\n" + "=" * 80)
        print("📊 BENCHMARK RESULTS")
        print("=" * 80)

        print("\n⏱️  Raw OCR Extraction:")
        print(f"   Mean:   {statistics.mean(raw_times):.3f}s")
        print(f"   Median: {statistics.median(raw_times):.3f}s")
        print(f"   Min:    {min(raw_times):.3f}s")
        print(f"   Max:    {max(raw_times):.3f}s")
        print(f"   StdDev: {statistics.stdev(raw_times):.3f}s" if len(raw_times) > 1 else "")

        print("\n🏥 Structured Data Extraction:")
        print(f"   Mean:   {statistics.mean(struct_times):.3f}s")
        print(f"   Median: {statistics.median(struct_times):.3f}s")
        print(f"   Min:    {min(struct_times):.3f}s")
        print(f"   Max:    {max(struct_times):.3f}s")
        print(f"   StdDev: {statistics.stdev(struct_times):.3f}s" if len(struct_times) > 1 else "")

        print("\n📈 Total Processing Time:")
        print(f"   Mean:   {statistics.mean(total_times):.3f}s")
        print(f"   Median: {statistics.median(total_times):.3f}s")
        print(f"   Min:    {min(total_times):.3f}s")
        print(f"   Max:    {max(total_times):.3f}s")
        print(f"   StdDev: {statistics.stdev(total_times):.3f}s" if len(total_times) > 1 else "")

        print("\n🎯 Confidence Scores:")
        print(f"   Mean:   {statistics.mean(confidences):.2%}")
        print(f"   Median: {statistics.median(confidences):.2%}")
        print(f"   Min:    {min(confidences):.2%}")
        print(f"   Max:    {max(confidences):.2%}")

        print("\n⚡ Throughput:")
        avg_time = statistics.mean(total_times)
        throughput = 3600 / avg_time  # receipts per hour
        print(f"   Average: {1/avg_time:.2f} receipts/second")
        print(f"   Per Hour: {throughput:.0f} receipts/hour")

        print("\n" + "=" * 80)
        print("✅ BENCHMARK COMPLETED")
        print("=" * 80)

        return True

    except Exception as e:
        logger.error(f"Benchmark failed: {e}", exc_info=True)
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    success = asyncio.run(benchmark_ocr_performance(iterations))
    sys.exit(0 if success else 1)
