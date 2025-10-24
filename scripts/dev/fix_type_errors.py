"""Fix common type errors across the codebase."""

import os
import re
from pathlib import Path


def fix_file(filepath):
    """Fix common type errors in a Python file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content

    # Fix timezone.utc -> timezone.utc (Python 3.10 compatibility)
    # First ensure timezone is imported if timezone.utc is used
    if "timezone.utc" in content:
        if "from datetime import" in content and "timezone" not in content:
            content = re.sub(
                r"from datetime import ([^(\n]+)",
                r"from datetime import \1, timezone",
                content,
            )
        elif "import datetime" in content and "datetime.timezone" not in content:
            # timezone.utc will become datetime.timezone.utc
            pass
        # Replace timezone.utc with timezone.utc or datetime.timezone.utc
        if "from datetime import" in content:
            content = content.replace("timezone.utc", "timezone.utc")
        else:
            content = content.replace("timezone.utc", "datetime.timezone.utc")

    # Fix Optional parameters (PEP 484 no_implicit_optional)
    # Pattern: def func(param: Type = None) -> should be -> def func(param: Type | None = None)
    # This is complex, so we'll handle it manually

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    return False


def main():
    """Process all Python files."""
    fixed_count = 0
    for root in ["src", "scripts"]:
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                if filename.endswith(".py"):
                    filepath = os.path.join(dirpath, filename)
                    if fix_file(filepath):
                        print(f"Fixed: {filepath}")
                        fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
