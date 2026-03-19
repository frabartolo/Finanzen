#!/usr/bin/env python3
"""
Kompatibilität: leitet zu pytest weiter.
Bevorzugt: pytest tests/test_categorization.py -v
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "pytest",
            str(ROOT / "tests" / "test_categorization.py"),
            str(ROOT / "tests" / "test_categorization_rules.py"),
            "-v",
            "--tb=short",
        ]
    )


if __name__ == "__main__":
    sys.exit(main())
