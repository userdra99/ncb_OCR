#!/usr/bin/env python3
"""Validate .env.example has all required environment variables."""

import re
from pathlib import Path
from typing import Set

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def extract_env_vars_from_example() -> Set[str]:
    """Extract all environment variables from .env.example."""
    env_example = PROJECT_ROOT / ".env.example"
    env_vars = set()

    if not env_example.exists():
        print(f"❌ {env_example} not found")
        return env_vars

    with open(env_example) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var_name = line.split("=")[0].strip()
                if var_name:
                    env_vars.add(var_name)

    return env_vars


def extract_env_vars_from_settings() -> Set[str]:
    """Extract all environment variable references from settings.py."""
    settings_file = PROJECT_ROOT / "src" / "config" / "settings.py"
    env_vars = set()

    if not settings_file.exists():
        print(f"❌ {settings_file} not found")
        return env_vars

    with open(settings_file) as f:
        content = f.read()

    # Find all alias= declarations
    pattern = r'alias="([A-Z_]+)"'
    matches = re.findall(pattern, content)
    env_vars.update(matches)

    return env_vars


def extract_env_vars_from_dockercompose() -> Set[str]:
    """Extract environment variables from docker-compose.yml."""
    docker_compose = PROJECT_ROOT / "docker-compose.yml"
    env_vars = set()

    if not docker_compose.exists():
        print(f"⚠️  {docker_compose} not found")
        return env_vars

    with open(docker_compose) as f:
        for line in f:
            line = line.strip()
            # Match lines like: - VARIABLE_NAME=value or - VARIABLE_NAME=${...}
            if line.startswith("- ") and "=" in line:
                var_name = line[2:].split("=")[0].strip()
                if var_name and var_name[0].isupper():
                    env_vars.add(var_name)

    return env_vars


def main():
    """Validate environment variables."""
    print("🔍 Environment Variable Validation")
    print("=" * 70)

    # Extract variables from different sources
    example_vars = extract_env_vars_from_example()
    settings_vars = extract_env_vars_from_settings()
    docker_vars = extract_env_vars_from_dockercompose()

    print(f"\n📊 Variables Found:")
    print(f"  .env.example:     {len(example_vars)} variables")
    print(f"  settings.py:      {len(settings_vars)} variables")
    print(f"  docker-compose:   {len(docker_vars)} variables")

    # Check for missing variables in .env.example
    missing_in_example = settings_vars - example_vars
    if missing_in_example:
        print(f"\n⚠️  Missing in .env.example ({len(missing_in_example)}):")
        for var in sorted(missing_in_example):
            print(f"    - {var}")
    else:
        print(f"\n✅ All settings.py variables documented in .env.example")

    # Check for extra variables in .env.example (not used in settings.py)
    extra_in_example = example_vars - settings_vars - docker_vars
    if extra_in_example:
        print(f"\n⚠️  In .env.example but not in settings.py ({len(extra_in_example)}):")
        for var in sorted(extra_in_example):
            print(f"    - {var} (may be Docker-only or unused)")

    # Check for Docker-only variables
    docker_only = docker_vars - settings_vars - example_vars
    if docker_only:
        print(f"\n📦 Docker-only variables ({len(docker_only)}):")
        for var in sorted(docker_only):
            print(f"    - {var}")

    # Summary
    print(f"\n" + "=" * 70)
    if not missing_in_example:
        print("✅ VALIDATION PASSED: All required variables documented")
        return 0
    else:
        print("❌ VALIDATION FAILED: Some variables missing from .env.example")
        return 1


if __name__ == "__main__":
    exit(main())
