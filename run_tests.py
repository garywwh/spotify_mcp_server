#!/usr/bin/env python3
"""
Test runner script for spotify_mcp_server.

This script provides various options for running tests with different configurations.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running {description}:")
        print(f"Exit code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run tests for spotify_mcp_server")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "all"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage report"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run tests without coverage for faster execution"
    )
    parser.add_argument(
        "--file",
        help="Run tests from specific file"
    )
    parser.add_argument(
        "--function",
        help="Run specific test function"
    )
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    
    # Add coverage if requested and not in fast mode
    if args.coverage and not args.fast:
        cmd.extend([
            "--cov=src/spotify_mcp_server",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--cov-report=xml"
        ])
    
    # Determine test selection
    if args.file:
        if args.function:
            cmd.append(f"tests/{args.file}::{args.function}")
        else:
            cmd.append(f"tests/{args.file}")
    elif args.function:
        cmd.extend(["-k", args.function])
    elif args.type == "unit":
        cmd.extend([
            "tests/test_utils.py",
            "tests/test_spotify_api.py",
            "tests/test_server.py"
        ])
    elif args.type == "integration":
        cmd.append("tests/test_integration.py")
    else:  # all
        cmd.append("tests/")
    
    # Add fast mode options
    if args.fast:
        cmd.extend([
            "--tb=short",
            "--no-cov"
        ])
    
    # Run the tests
    success = run_command(cmd, f"Running {args.type} tests")
    
    if success:
        print(f"\n✅ {args.type.title()} tests completed successfully!")
        if args.coverage and not args.fast:
            print("\n📊 Coverage report generated:")
            print("  - Terminal: See above")
            print("  - HTML: htmlcov/index.html")
            print("  - XML: coverage.xml")
    else:
        print(f"\n❌ {args.type.title()} tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()