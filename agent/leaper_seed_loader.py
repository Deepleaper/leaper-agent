"""Leaper Seed Loader — auto-load workspace .md files into brain and system prompt.

ALWAYS_LOAD files are injected into every system prompt.
All other .md files (except EXCLUDE list) are seeded into the brain once.
"""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.leaper_brain import LeaperBrain

logger = logging.getLogger(__name__)

ALWAYS_LOAD = frozenset(["EGO.md", "SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md"])
EXCLUDE = frozenset(["README.md", "CHANGELOG.md", "LICENSE.md"])
_SEED_MARKER = ".leaper-seeded"


def load_workspace_files(workspace_dir: str | Path, brain: "LeaperBrain") -> dict:
    """Scan workspace_dir for .md files and load them into brain + system prompt.

    Returns a dict with:
      - system_prompt_block (str): content for the system prompt
      - seeded_count (int): number of files newly seeded into the brain
      - always_load_files (list[str]): files injected into prompt
    """
    workspace = Path(workspace_dir)
    if not workspace.exists():
        logger.debug("Workspace dir does not exist: %s", workspace)
        return {"system_prompt_block": "", "seeded_count": 0, "always_load_files": []}

    marker = workspace / _SEED_MARKER
    already_seeded = marker.exists()

    md_files = _scan_md_files(workspace)
    prompt_parts: list[str] = []
    always_loaded: list[str] = []
    seeded_count = 0

    for rel_path in md_files:
        name = Path(rel_path).name
        if name in EXCLUDE:
            continue

        full_path = workspace / rel_path
        try:
            content = full_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Cannot read %s: %s", full_path, e)
            continue

        if name in ALWAYS_LOAD:
            prompt_parts.append(f"### {name}\n{content.strip()}")
            always_loaded.append(name)
        elif not already_seeded:
            brain.learn(
                content=content.strip(),
                source=str(rel_path),
                namespace="workspace",
            )
            seeded_count += 1

    if not already_seeded and seeded_count > 0:
        try:
            from datetime import datetime, timezone
            marker.write_text(datetime.now(timezone.utc).isoformat())
        except OSError:
            pass
        logger.info("LeaperSeedLoader: seeded %d files from %s", seeded_count, workspace)

    # Build runtime environment block
    os_name = platform.system()  # Windows, Linux, Darwin
    os_version = platform.version()
    shell = "PowerShell" if os_name == "Windows" else os.environ.get("SHELL", "/bin/bash")
    runtime_block = (
        f"## Runtime Environment\n"
        f"- OS: {os_name} {os_version}\n"
        f"- Shell: {shell}\n"
        f"- Home: {Path.home()}\n"
        f"- Use {'PowerShell' if os_name == 'Windows' else 'bash'} commands (not {'Linux' if os_name == 'Windows' else 'Windows'} commands)\n"
        f"- File paths use {'backslash' if os_name == 'Windows' else 'forward slash'}"
    )

    all_parts = [runtime_block] + prompt_parts

    return {
        "system_prompt_block": "\n\n".join(all_parts),
        "seeded_count": seeded_count,
        "always_load_files": always_loaded,
    }


def _scan_md_files(directory: Path, prefix: str = "") -> list[str]:
    """Recursively collect relative paths of all .md files, skipping hidden dirs."""
    results: list[str] = []
    try:
        with os.scandir(directory) as it:
            for entry in sorted(it, key=lambda e: e.name):
                rel = f"{prefix}/{entry.name}" if prefix else entry.name
                if entry.is_file() and entry.name.endswith(".md"):
                    results.append(rel)
                elif entry.is_dir() and not entry.name.startswith("."):
                    results.extend(_scan_md_files(Path(entry.path), rel))
    except PermissionError:
        pass
    return results
