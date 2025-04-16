"""
Script to run integration tests with control over which tests to run.

Environment variables:
- SKIP_API_TESTS=1: Skip tests that require API access
- TEST_PATTERN: Pytest pattern to select specific tests

Example usage:
python tests/run_tests.py
SKIP_API_TESTS=1 python tests/run_tests.py
TEST_PATTERN="test_cli.py::TestCliIntegration::test_cli_help" python tests/run_tests.py
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    # Determine test pattern
    test_pattern = os.environ.get("TEST_PATTERN", "tests")
    
    # Build pytest command
    cmd = [
        "pytest", 
        "-xvs",  # x=exit on first failure, v=verbose, s=no capture
        test_pattern
    ]
    
    print(f"Running tests: {' '.join(cmd)}")
    
    # Run pytest
    result = subprocess.run(cmd)
    
    # Return pytest's exit code
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
