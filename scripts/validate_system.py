#!/usr/bin/env python3
"""
System Validation Script
Validates that all components of the Claims Data Entry Agent are properly configured and operational.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import redis.asyncio as aioredis
from rich.console import Console
from rich.table import Table


console = Console()


async def check_api_health() -> dict:
    """Check API health endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8080/health", timeout=5.0)
            basic_health = response.json()

            response = await client.get("http://localhost:8080/health/detailed", timeout=5.0)
            detailed_health = response.json()

            return {
                "status": "✅ healthy" if basic_health["status"] == "healthy" else "⚠️  degraded",
                "version": basic_health["version"],
                "components": detailed_health["components"],
                "workers": detailed_health["workers"],
            }
    except Exception as e:
        return {"status": "❌ error", "error": str(e)}


async def check_redis() -> dict:
    """Check Redis connection."""
    try:
        redis_client = await aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
        await redis_client.ping()
        info = await redis_client.info()
        await redis_client.close()

        return {
            "status": "✅ connected",
            "version": info.get("redis_version", "unknown"),
            "memory": info.get("used_memory_human", "unknown"),
        }
    except Exception as e:
        return {"status": "❌ error", "error": str(e)}


def check_credentials() -> dict:
    """Check if all credential files exist."""
    secrets_dir = Path("secrets")
    required_files = {
        "gmail_credentials": secrets_dir / "gmail-oauth-credentials.json",
        "gmail_token": secrets_dir / "gmail_token.json",
        "service_account": secrets_dir / "service-account-credentials.json",
    }

    results = {}
    for name, path in required_files.items():
        if path.exists():
            results[name] = f"✅ found ({path.stat().st_size} bytes)"
        else:
            results[name] = f"❌ missing ({path})"

    return results


def check_environment() -> dict:
    """Check environment configuration."""
    from src.config.settings import settings

    return {
        "app_env": settings.app.env,
        "log_level": settings.app.log_level,
        "redis_url": settings.redis.url,
        "ocr_gpu": "✅ enabled" if settings.ocr.use_gpu else "⚠️  disabled (CPU mode)",
        "ncb_api": settings.ncb.base_url,
    }


async def main():
    """Run all validation checks."""
    console.print("\n[bold cyan]Claims Data Entry Agent - System Validation[/bold cyan]\n")

    # API Health Check
    console.print("[bold]Checking API Health...[/bold]")
    api_health = await check_api_health()

    health_table = Table(title="API Health Status")
    health_table.add_column("Component", style="cyan")
    health_table.add_column("Status", style="green")

    health_table.add_row("Overall Status", api_health.get("status", "unknown"))
    health_table.add_row("Version", api_health.get("version", "unknown"))

    if "components" in api_health:
        for component, status in api_health["components"].items():
            health_table.add_row(f"  {component}", status)

    if "workers" in api_health:
        for worker, status in api_health["workers"].items():
            icon = "✅" if status == "running" else "❌"
            health_table.add_row(f"  {worker}", f"{icon} {status}")

    console.print(health_table)

    # Redis Check
    console.print("\n[bold]Checking Redis...[/bold]")
    redis_status = await check_redis()

    redis_table = Table(title="Redis Status")
    redis_table.add_column("Property", style="cyan")
    redis_table.add_column("Value", style="green")

    for key, value in redis_status.items():
        redis_table.add_row(key, str(value))

    console.print(redis_table)

    # Credentials Check
    console.print("\n[bold]Checking Credentials...[/bold]")
    creds = check_credentials()

    creds_table = Table(title="Credentials Status")
    creds_table.add_column("Credential", style="cyan")
    creds_table.add_column("Status", style="green")

    for name, status in creds.items():
        creds_table.add_row(name, status)

    console.print(creds_table)

    # Environment Check
    console.print("\n[bold]Checking Environment...[/bold]")
    env = check_environment()

    env_table = Table(title="Environment Configuration")
    env_table.add_column("Setting", style="cyan")
    env_table.add_column("Value", style="green")

    for key, value in env.items():
        env_table.add_row(key, str(value))

    console.print(env_table)

    # Overall Assessment
    console.print("\n[bold cyan]Overall Assessment[/bold cyan]")

    issues = []
    if api_health.get("status") == "❌ error":
        issues.append("API is not responding")
    if redis_status.get("status") == "❌ error":
        issues.append("Redis is not accessible")
    if any("❌ missing" in v for v in creds.values()):
        issues.append("Some credentials are missing")

    if not issues:
        console.print("[green]✅ All systems operational[/green]")
        return 0
    else:
        console.print("[yellow]⚠️  Issues detected:[/yellow]")
        for issue in issues:
            console.print(f"  • {issue}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
