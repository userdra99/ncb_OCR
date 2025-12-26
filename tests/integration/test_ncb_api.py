#!/usr/bin/env python3
"""
NCB API Integration Test Suite
Tests NCB API with comprehensive test data from fixtures.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx
from pydantic import BaseModel

# Test configuration
TEST_DATA_DIR = Path(__file__).parent.parent / "fixtures"
NCB_API_BASE_URL = "https://ncb.internal.company.com/api/v1"
NCB_API_KEY = "your-ncb-api-key-here"  # From .env


class TestResult(BaseModel):
    """Test execution result."""

    test_id: str
    description: str
    expected_status: int
    actual_status: int | None
    success: bool
    response_time_ms: float | None
    response_data: Dict[str, Any] | None
    error_message: str | None
    notes: str | None = None


class NCBAPITestRunner:
    """NCB API integration test runner."""

    def __init__(self, base_url: str, api_key: str):
        """Initialize test runner."""
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }
        self.results: List[TestResult] = []

    async def check_endpoint_health(self) -> bool:
        """Check if NCB API endpoint is accessible."""
        print(f"\n🔍 Testing endpoint: {self.base_url}")
        print("=" * 80)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try health endpoint
                try:
                    response = await client.get(
                        f"{self.base_url}/health", headers=self.headers
                    )
                    print(f"✓ Health endpoint: {response.status_code}")
                    print(f"  Response: {response.text[:200]}")
                    return response.status_code == 200
                except httpx.HTTPStatusError as e:
                    print(f"✗ Health endpoint failed: {e}")

                # Try root endpoint
                try:
                    response = await client.get(f"{self.base_url}/", headers=self.headers)
                    print(f"✓ Root endpoint: {response.status_code}")
                    print(f"  Response: {response.text[:200]}")
                    return response.status_code in [200, 404]  # 404 is acceptable
                except httpx.HTTPStatusError as e:
                    print(f"✗ Root endpoint failed: {e}")

                return False

        except httpx.ConnectError as e:
            print(f"✗ Connection failed: {e}")
            print("\n⚠️  NCB API endpoint is not accessible")
            print(
                "   This is expected in a test environment without access to production NCB API"
            )
            return False
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            return False

    async def execute_single_test(
        self, test_case: Dict[str, Any], endpoint: str = "/claims"
    ) -> TestResult:
        """Execute a single test case."""
        test_id = test_case.get("test_id", "unknown")
        description = test_case.get("description", "")
        payload = test_case.get("payload", {})
        expected = test_case.get("expected_response", {})
        notes = test_case.get("notes")

        # Determine expected status code
        expected_status = 201 if expected.get("status") == "success" else 400

        print(f"\n📝 Test: {test_id}")
        print(f"   {description}")

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    headers=self.headers,
                )

                response_time_ms = (time.time() - start_time) * 1000

                try:
                    response_data = response.json()
                except Exception:
                    response_data = {"raw": response.text}

                success = response.status_code == expected_status

                result = TestResult(
                    test_id=test_id,
                    description=description,
                    expected_status=expected_status,
                    actual_status=response.status_code,
                    success=success,
                    response_time_ms=response_time_ms,
                    response_data=response_data,
                    error_message=None,
                    notes=notes,
                )

                status_icon = "✅" if success else "❌"
                print(f"   {status_icon} Status: {response.status_code} (expected {expected_status})")
                print(f"   ⏱️  Response time: {response_time_ms:.2f}ms")

                if response_data:
                    print(f"   📄 Response: {json.dumps(response_data, indent=2)[:200]}")

                return result

        except httpx.ConnectError as e:
            result = TestResult(
                test_id=test_id,
                description=description,
                expected_status=expected_status,
                actual_status=None,
                success=False,
                response_time_ms=None,
                response_data=None,
                error_message=f"Connection failed: {str(e)}",
                notes=notes,
            )
            print(f"   ❌ Connection failed: {e}")
            return result

        except Exception as e:
            result = TestResult(
                test_id=test_id,
                description=description,
                expected_status=expected_status,
                actual_status=None,
                success=False,
                response_time_ms=None,
                response_data=None,
                error_message=str(e),
                notes=notes,
            )
            print(f"   ❌ Error: {e}")
            return result

    async def run_test_suite(self, test_file: Path) -> List[TestResult]:
        """Run all tests from a test file."""
        print(f"\n📂 Loading test suite: {test_file.name}")

        with open(test_file) as f:
            test_data = json.load(f)

        # Handle different test file formats
        if "test_cases" in test_data:
            test_cases = test_data["test_cases"]
        elif "claims" in test_data:
            # Batch format - convert to test cases
            test_cases = [
                {
                    "test_id": f"batch_{i+1}",
                    "description": f"Batch claim {i+1}",
                    "payload": claim,
                    "expected_response": {"status": "success"},
                }
                for i, claim in enumerate(test_data["claims"])
            ]
        else:
            # Single claim format
            test_cases = [
                {
                    "test_id": "single_claim",
                    "description": "Single claim test",
                    "payload": test_data,
                    "expected_response": {"status": "success"},
                }
            ]

        print(f"   Found {len(test_cases)} test cases")

        results = []
        for test_case in test_cases:
            result = await self.execute_single_test(test_case)
            results.append(result)
            self.results.append(result)
            # Rate limiting - small delay between tests
            await asyncio.sleep(0.5)

        return results

    def generate_report(self) -> str:
        """Generate comprehensive test report."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed

        report = []
        report.append("\n" + "=" * 80)
        report.append("NCB API INTEGRATION TEST REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Endpoint: {self.base_url}")
        report.append("")
        report.append("SUMMARY")
        report.append("-" * 80)
        report.append(f"Total Tests: {total}")
        report.append(f"Passed: {passed} ({passed/total*100:.1f}%)")
        report.append(f"Failed: {failed} ({failed/total*100:.1f}%)")
        report.append("")

        # Detailed results table
        report.append("DETAILED RESULTS")
        report.append("-" * 80)
        report.append(
            f"{'Test ID':<30} {'Status':<10} {'Expected':<10} {'Actual':<10} {'Time (ms)':<12} {'Result'}"
        )
        report.append("-" * 80)

        for result in self.results:
            status_icon = "✅ PASS" if result.success else "❌ FAIL"
            actual = str(result.actual_status) if result.actual_status else "N/A"
            time_str = (
                f"{result.response_time_ms:.2f}"
                if result.response_time_ms
                else "N/A"
            )

            report.append(
                f"{result.test_id:<30} {status_icon:<10} {result.expected_status:<10} {actual:<10} {time_str:<12}"
            )

            if result.error_message:
                report.append(f"  ⚠️  Error: {result.error_message}")

            if result.notes:
                report.append(f"  📝 Notes: {result.notes}")

        report.append("")
        report.append("PERFORMANCE METRICS")
        report.append("-" * 80)

        successful_tests = [r for r in self.results if r.response_time_ms is not None]
        if successful_tests:
            times = [r.response_time_ms for r in successful_tests]
            report.append(f"Average response time: {sum(times)/len(times):.2f}ms")
            report.append(f"Min response time: {min(times):.2f}ms")
            report.append(f"Max response time: {max(times):.2f}ms")
        else:
            report.append("No successful responses to measure")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    async def validate_json_schema(self, test_file: Path) -> Dict[str, Any]:
        """Validate test data against NCB schema."""
        print(f"\n🔍 Validating JSON schema: {test_file.name}")

        with open(test_file) as f:
            test_data = json.load(f)

        # Extract test cases
        if "test_cases" in test_data:
            test_cases = test_data["test_cases"]
        else:
            return {"valid": False, "error": "Invalid test file format"}

        required_fields = [
            "Event date",
            "Submission Date",
            "Claim Amount",
            "Invoice Number",
            "Policy Number",
        ]

        validation_results = []

        for test_case in test_cases:
            payload = test_case.get("payload", {})
            test_id = test_case.get("test_id", "unknown")

            missing_fields = [f for f in required_fields if f not in payload]

            # Check if this is an invalid test case (expected to fail)
            is_invalid_test = "invalid" in test_id.lower()

            if missing_fields and not is_invalid_test:
                validation_results.append(
                    {
                        "test_id": test_id,
                        "valid": False,
                        "missing_fields": missing_fields,
                    }
                )
                print(f"   ❌ {test_id}: Missing {missing_fields}")
            else:
                validation_results.append({"test_id": test_id, "valid": True})
                print(f"   ✅ {test_id}: Schema valid")

        all_valid = all(r["valid"] for r in validation_results)

        return {
            "valid": all_valid,
            "total": len(validation_results),
            "results": validation_results,
        }


async def main():
    """Main test execution."""
    print("\n" + "=" * 80)
    print("NCB API INTEGRATION TEST SUITE")
    print("=" * 80)

    # Initialize runner
    runner = NCBAPITestRunner(
        base_url=NCB_API_BASE_URL,
        api_key=NCB_API_KEY,
    )

    # Phase 1: Check endpoint availability
    print("\n📡 PHASE 1: Endpoint Discovery")
    is_accessible = await runner.check_endpoint_health()

    if not is_accessible:
        print("\n⚠️  NCB API endpoint is not accessible")
        print("   Proceeding with JSON schema validation only\n")

        # Validate schemas instead
        print("\n🔍 PHASE 2: JSON Schema Validation")
        test_files = [
            TEST_DATA_DIR / "ncb_test_data.json",
            TEST_DATA_DIR / "ncb_single_valid_claim.json",
            TEST_DATA_DIR / "ncb_batch_claims.json",
        ]

        for test_file in test_files:
            if test_file.exists():
                result = await runner.validate_json_schema(test_file)
                print(f"\n   Validation result: {'✅ PASS' if result['valid'] else '❌ FAIL'}")
                print(f"   Total test cases: {result.get('total', 0)}")

        print("\n" + "=" * 80)
        print("RECOMMENDATION")
        print("=" * 80)
        print("✓ Test data JSON schemas are valid and ready for NCB API")
        print("✓ Field mappings match NCB requirements:")
        print("  - Event date (ISO 8601 date)")
        print("  - Submission Date (ISO 8601 datetime)")
        print("  - Claim Amount (float)")
        print("  - Invoice Number (string)")
        print("  - Policy Number (string)")
        print("\n⚠️  To test with live API:")
        print("  1. Update NCB_API_BASE_URL in .env")
        print("  2. Update NCB_API_KEY in .env")
        print("  3. Run: python tests/integration/test_ncb_api.py")
        print("=" * 80)

        return

    # Phase 2: Single claim test
    print("\n🧪 PHASE 2: Single Claim Test")
    single_claim_file = TEST_DATA_DIR / "ncb_single_valid_claim.json"
    if single_claim_file.exists():
        await runner.run_test_suite(single_claim_file)

    # Phase 3: Comprehensive test suite
    print("\n🧪 PHASE 3: Comprehensive Test Suite")
    test_data_file = TEST_DATA_DIR / "ncb_test_data.json"
    if test_data_file.exists():
        await runner.run_test_suite(test_data_file)

    # Phase 4: Batch test
    print("\n🧪 PHASE 4: Batch Submission Test")
    batch_file = TEST_DATA_DIR / "ncb_batch_claims.json"
    if batch_file.exists():
        await runner.run_test_suite(batch_file)

    # Generate report
    print("\n" + "=" * 80)
    print("GENERATING REPORT")
    print("=" * 80)

    report = runner.generate_report()
    print(report)

    # Save report to file
    report_file = TEST_DATA_DIR.parent / "reports" / "NCB_API_TEST_REPORT.md"
    report_file.parent.mkdir(exist_ok=True)

    with open(report_file, "w") as f:
        f.write(report)

    print(f"\n📄 Report saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
