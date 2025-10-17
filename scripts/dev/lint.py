#!/usr/bin/env python3
"""
Development script for running code quality checks.
"""

import sys
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths

def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n🔍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def main():
    """Run all code quality checks."""
    project_root = setup_project_paths()
    
    print("🚀 Running code quality checks...")
    
    checks = [
        ("flake8 src/ scripts/ tests/ --max-line-length=88 --extend-ignore=E203,W503", "Flake8 linting"),
        ("black --check --diff src/ scripts/ tests/", "Black formatting check"),
        ("mypy src/ --ignore-missing-imports", "MyPy type checking"),
    ]
    
    results = []
    for cmd, description in checks:
        success = run_command(cmd, description)
        results.append((description, success))
    
    # Summary
    print(f"\n📊 Summary:")
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for description, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {description}")
    
    print(f"\n{passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 All quality checks passed!")
        return 0
    else:
        print("⚠️  Some quality checks failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())