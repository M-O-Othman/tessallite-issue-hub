import os
import json
import platform
from pathlib import Path
from typing import Dict, Any

def get_config_file_path() -> Path:
    """Determine OS-specific path for config.json (Section 17.2)."""
    system = platform.system()
    if system == "Windows":
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            return Path(app_data) / "Tessallite" / "IssueHub" / "config.json"
        return Path.home() / "AppData" / "Roaming" / "Tessallite" / "IssueHub" / "config.json"
    else:
        # Linux/macOS/BSD
        config_home = os.environ.get("XDG_CONFIG_HOME", "")
        if config_home:
            return Path(config_home) / "tessallite-issue-hub" / "config.json"
        return Path.home() / ".config" / "tessallite-issue-hub" / "config.json"

def load_user_config() -> Dict[str, Any]:
    """Load JSON config file if it exists."""
    path = get_config_file_path()
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # Tolerant loading
            return {}
    return {}

def resolve_config(cli_args: Any) -> Dict[str, Any]:
    """Resolve configuration based on precedence rules:
    1. CLI option
    2. Env variable
    3. User-level config file
    """
    user_conf = load_user_config()
    
    resolved = {}
    
    # URL
    resolved["url"] = (
        getattr(cli_args, "url", None)
        or os.environ.get("ISSUE_HUB_URL")
        or user_conf.get("ISSUE_HUB_URL")
        or "http://localhost:8080"
    )
    # Token
    resolved["token"] = (
        getattr(cli_args, "token", None)
        or os.environ.get("ISSUE_HUB_TOKEN")
        or user_conf.get("ISSUE_HUB_TOKEN")
        or ""
    )
    # Project
    resolved["project"] = (
        getattr(cli_args, "project", None)
        or os.environ.get("ISSUE_HUB_PROJECT")
        or user_conf.get("ISSUE_HUB_PROJECT")
        or ""
    )
    # Repository
    resolved["repository"] = (
        getattr(cli_args, "repository", None)
        or os.environ.get("ISSUE_HUB_REPOSITORY")
        or user_conf.get("ISSUE_HUB_REPOSITORY")
        or ""
    )
    # Branch
    resolved["branch"] = (
        getattr(cli_args, "branch", None)
        or os.environ.get("ISSUE_HUB_BRANCH")
        or user_conf.get("ISSUE_HUB_BRANCH")
        or ""
    )
    # Worktree
    resolved["worktree"] = (
        getattr(cli_args, "worktree", None)
        or os.environ.get("ISSUE_HUB_WORKTREE")
        or user_conf.get("ISSUE_HUB_WORKTREE")
        or ""
    )
    
    return resolved
