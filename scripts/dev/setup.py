#!/usr/bin/env python3
"""
Development setup script for crypto-analytics project.
"""

import sys
import subprocess
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths, get_config_path

def run_command(cmd, description, check=True):
    """Run a command with proper error handling."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} is not compatible. Requires Python 3.10+")
        return False

def setup_environment():
    """Set up the development environment."""
    project_root = setup_project_paths()
    
    print("🚀 Setting up crypto-analytics development environment...\n")
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install dependencies
    success = run_command(
        "pip install -e .[dev]", 
        "Installing project dependencies with development extras"
    )
    if not success:
        print("⚠️  Falling back to requirements.txt...")
        success = run_command(
            "pip install -r requirements.txt", 
            "Installing dependencies from requirements.txt"
        )
        if not success:
            return False
    
    # Check environment file
    config_env = get_config_path() / ".env"
    config_example = get_config_path() / ".env.example"
    
    if not config_env.exists() and config_example.exists():
        print("📋 Setting up environment configuration...")
        try:
            import shutil
            shutil.copy(config_example, config_env)
            print(f"✅ Created {config_env} from template")
            print(f"⚠️  Please edit {config_env} with your API keys and configuration")
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")
    elif config_env.exists():
        print(f"✅ Environment file exists at {config_env}")
    else:
        print(f"⚠️  No environment template found at {config_example}")
    
    # Initialize database (if needed)
    print("\n🗄️  Database setup...")
    db_init_script = project_root / "src" / "models" / "init_db.py"
    if db_init_script.exists():
        run_command(
            f"python {db_init_script}", 
            "Initializing database",
            check=False  # Don't fail if database already exists
        )
    
    # Create logs directory if it doesn't exist
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    print(f"✅ Logs directory ready at {logs_dir}")
    
    return True

def main():
    """Main setup function."""
    if setup_environment():
        print("\n🎉 Development environment setup complete!")
        print("\n📚 Next steps:")
        print("  1. Edit config/.env with your API keys")
        print("  2. Run: python scripts/dev/lint.py (to check code quality)")
        print("  3. Run: python scripts/analysis/monitor_progress.py (to check system status)")
        print("  4. Start analysis: python scripts/analysis/run_medium_limited.py")
        return 0
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())