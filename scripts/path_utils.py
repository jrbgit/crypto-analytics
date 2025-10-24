#!/usr/bin/env python3
"""
Path utilities for scripts in different directories to find project root
and set up proper import paths.
"""

import sys
from pathlib import Path


def setup_project_paths():
    """
    Set up paths for scripts to import from src/ directory.
    This function can be called from any script in any subdirectory.

    Returns:
        Path: The project root path
    """
    # Get the directory containing the calling script, not this utility
    import inspect

    frame = inspect.currentframe().f_back
    calling_script = Path(frame.f_globals["__file__"]).resolve()

    # Find project root by looking for marker files from the calling script location
    project_root = calling_script.parent

    # Walk up the directory tree to find project root
    while project_root.parent != project_root:
        # Look for project root markers
        if any(
            (project_root / marker).exists()
            for marker in [
                "requirements.txt",
                "README.md",
                "src",
                ".git",
                "docker-compose.yml",
            ]
        ):
            break
        project_root = project_root.parent

    # Add project root and src to Python path if not already there
    project_root_str = str(project_root)
    src_path_str = str(project_root / "src")

    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    if src_path_str not in sys.path:
        sys.path.insert(0, src_path_str)

    return project_root


def get_project_root():
    """Get project root directory."""
    current_file = Path(__file__).resolve()
    project_root = current_file

    # Walk up to find project root
    while project_root.parent != project_root:
        if any(
            (project_root / marker).exists()
            for marker in ["requirements.txt", "README.md", "src", ".git"]
        ):
            break
        project_root = project_root.parent

    return project_root


def get_config_path():
    """Get path to config directory."""
    return get_project_root() / "config"


def get_data_path():
    """Get path to data directory."""
    return get_project_root() / "data"


def get_logs_path():
    """Get path to logs directory."""
    return get_project_root() / "logs"


if __name__ == "__main__":
    # Test the utility
    root = setup_project_paths()
    print(f"Project root: {root}")
    print(f"Config path: {get_config_path()}")
    print(f"Data path: {get_data_path()}")
    print(f"Logs path: {get_logs_path()}")
