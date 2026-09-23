from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run(*args: str, cwd: Path) -> str:
    try:
        result = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=3, check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def git_info() -> tuple[str, str]:
    override_sha = os.environ.get("GIT_SHA")
    override_branch = os.environ.get("GIT_BRANCH")
    if override_sha and override_branch:
        return override_sha, override_branch

    cwd = Path(__file__).resolve().parent.parent
    sha = override_sha or _run("git", "rev-parse", "HEAD", cwd=cwd) or "unknown"
    branch = override_branch or _run("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=cwd) or "unknown"
    return sha, branch
