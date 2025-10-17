#!/usr/bin/env python3
"""
Type hints validation script with gradual improvement approach.

Instead of overwhelming with all mypy errors, this script provides
a structured approach to gradually improve type coverage.
"""

import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths

def run_mypy_on_file(file_path: str) -> Tuple[int, str]:
    """Run mypy on a single file and return error count and output."""
    try:
        result = subprocess.run(
            ["mypy", file_path, "--ignore-missing-imports", "--show-error-codes"],
            capture_output=True,
            text=True
        )
        # Count errors (lines that don't start with "Success:")
        lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
        error_lines = [line for line in lines if not line.startswith("Success:") and line.strip()]
        return len(error_lines), result.stdout
    except subprocess.CalledProcessError as e:
        return -1, f"Failed to run mypy: {e}"

def analyze_type_coverage():
    """Analyze type coverage across the project."""
    project_root = setup_project_paths()
    
    print("🔍 Analyzing type hint coverage...")
    
    # Files to check in order of priority (core functionality first)
    priority_files = [
        "src/models/database.py",
        "src/utils/logging_config.py", 
        "src/utils/url_filter.py",
        "src/models/storage_service.py",
        "src/collectors/livecoinwatch.py",
    ]
    
    results = []
    
    for file_path in priority_files:
        full_path = project_root / file_path
        if full_path.exists():
            error_count, output = run_mypy_on_file(str(full_path))
            results.append((file_path, error_count, output))
            
            if error_count == 0:
                print(f"✅ {file_path} - No type errors")
            elif error_count > 0:
                print(f"⚠️  {file_path} - {error_count} type errors")
            else:
                print(f"❌ {file_path} - Failed to check")
        else:
            print(f"❓ {file_path} - File not found")
    
    # Summary
    print(f"\n📊 Type Coverage Summary:")
    clean_files = sum(1 for _, count, _ in results if count == 0)
    total_files = len([r for r in results if r[1] >= 0])
    
    if total_files > 0:
        coverage = (clean_files / total_files) * 100
        print(f"Files with no type errors: {clean_files}/{total_files} ({coverage:.1f}%)")
    
    # Show details for files with errors
    print(f"\n📝 Detailed Results:")
    for file_path, error_count, output in results:
        if error_count > 0:
            print(f"\n--- {file_path} ({error_count} errors) ---")
            # Show first few errors as examples
            lines = output.split('\n')[:10]  # First 10 lines
            for line in lines:
                if line.strip() and not line.startswith("Success:"):
                    print(f"  {line}")
            if len(output.split('\n')) > 10:
                print(f"  ... and {len(output.split('\n')) - 10} more errors")
    
    return results

def suggest_improvements():
    """Suggest gradual improvements for type hints."""
    print(f"\n💡 Type Hint Improvement Suggestions:")
    print("1. Start with utility modules (fewer dependencies)")
    print("2. Add return type hints to functions first")
    print("3. Add parameter type hints gradually")
    print("4. Use 'from __future__ import annotations' for forward references")
    print("5. Consider using mypy ignore comments for complex cases: # type: ignore")
    
    print(f"\n🛠️  Common fixes:")
    print("- Replace 'datetime.UTC' with 'datetime.timezone.utc' for Python 3.10 compatibility")
    print("- Add Optional[] for parameters that can be None")  
    print("- Use typing.Dict, typing.List instead of dict, list for older Python")
    print("- Add type hints to class attributes")

def main():
    """Main type checking function."""
    print("🎯 Type Hints Validation - Gradual Improvement Approach")
    print("=" * 60)
    
    results = analyze_type_coverage()
    suggest_improvements()
    
    # Return status based on results
    errors = sum(count for _, count, _ in results if count > 0)
    if errors == 0:
        print(f"\n🎉 All checked files have clean type hints!")
        return 0
    else:
        print(f"\n⚠️  Found {errors} total type errors across checked files.")
        print("This is normal - type hints can be improved gradually.")
        return 0  # Don't fail CI for type hints (yet)

if __name__ == "__main__":
    sys.exit(main())