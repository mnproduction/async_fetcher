#!/usr/bin/env python3
"""
Development utility script for common tasks.

Usage:
    python scripts/dev.py <command>

Commands:
    lint        - Run linting checks
    format      - Format code
    test        - Run all tests
    test-unit   - Run unit tests only
    test-int    - Run integration tests only
    test-e2e    - Run E2E tests only
    coverage    - Run tests with coverage report
    clean       - Clean build artifacts
    setup       - Setup development environment
"""

import subprocess
import sys
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def run_command(cmd: list[str], description: str) -> int:
    """Run a command and return the exit code."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=False)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
        else:
            print(f"❌ {description} failed with exit code {result.returncode}")
        return result.returncode
    except KeyboardInterrupt:
        print(f"\n⚠️  {description} interrupted by user")
        return 130


def lint() -> int:
    """Run linting checks."""
    return run_command(["uv", "run", "ruff", "check", "."], "Linting")


def format_code() -> int:
    """Format code."""
    exit_code = run_command(["uv", "run", "ruff", "format", "."], "Formatting")
    if exit_code == 0:
        # Run linting after formatting to fix any import sorting issues
        exit_code = run_command(
            ["uv", "run", "ruff", "check", "--fix", "."], "Auto-fixing lint issues"
        )
    return exit_code


def test_unit() -> int:
    """Run unit tests."""
    return run_command(["uv", "run", "pytest", "-m", "unit", "--tb=short", "-v"], "Unit tests")


def test_integration() -> int:
    """Run integration tests."""
    return run_command(
        ["uv", "run", "pytest", "-m", "integration", "--tb=short", "-v"], "Integration tests"
    )


def test_e2e() -> int:
    """Run E2E tests."""
    return run_command(
        ["uv", "run", "pytest", "-m", "e2e and not cloudflare", "--tb=short", "-v"], "E2E tests"
    )


def test_all() -> int:
    """Run all tests."""
    return run_command(["uv", "run", "pytest", "--tb=short", "-v"], "All tests")


def coverage() -> int:
    """Run tests with coverage."""
    return run_command(
        [
            "uv",
            "run",
            "pytest",
            "-m",
            "not e2e",
            "--cov=api",
            "--cov=toolkit",
            "--cov=settings",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-fail-under=75",
        ],
        "Tests with coverage",
    )


def clean() -> int:
    """Clean build artifacts."""
    import shutil

    artifacts = [
        ".pytest_cache",
        ".coverage",
        "htmlcov",
        ".ruff_cache",
        "dist",
        "build",
        "*.egg-info",
    ]

    cleaned = []
    for pattern in artifacts:
        if "*" in pattern:
            # Handle glob patterns
            for path in PROJECT_ROOT.glob(pattern):
                if path.exists():
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    cleaned.append(str(path))
        else:
            path = PROJECT_ROOT / pattern
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                cleaned.append(str(path))

    if cleaned:
        print(f"🧹 Cleaned: {', '.join(cleaned)}")
    else:
        print("🧹 Nothing to clean")
    return 0


def setup() -> int:
    """Setup development environment."""
    commands = [
        (["uv", "sync", "--extra", "test", "--extra", "linters"], "Installing dependencies"),
        (["uv", "run", "pre-commit", "install"], "Setting up pre-commit hooks (optional)"),
    ]

    for cmd, desc in commands:
        exit_code = run_command(cmd, desc)
        if exit_code != 0 and "pre-commit" not in cmd[1]:
            return exit_code

    print("🚀 Development environment setup complete!")
    print("\nNext steps:")
    print("1. Copy .env.example to .env and configure your settings")
    print("2. Start FlareSolverr: docker-compose up flaresolverr")
    print("3. Run tests: python scripts/dev.py test")
    return 0


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    command = sys.argv[1].lower().replace("-", "_")

    commands = {
        "lint": lint,
        "format": format_code,
        "test": test_all,
        "test_unit": test_unit,
        "test_int": test_integration,
        "test_e2e": test_e2e,
        "coverage": coverage,
        "clean": clean,
        "setup": setup,
    }

    if command not in commands:
        print(f"❌ Unknown command: {sys.argv[1]}")
        print(__doc__)
        return 1

    return commands[command]()


if __name__ == "__main__":
    sys.exit(main())
