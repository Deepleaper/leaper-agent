"""Leaper Workshop — template marketplace for Leaper Agent workspaces.

Provides local and remote template discovery and download.
Remote source: https://github.com/Deepleaper/leaper-templates

Usage:
    from leaper_workshop import list_templates, download_template

    templates = list_templates()
    files_written = download_template("ceo-coach", "./my-workspace")
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REMOTE_URL = "https://raw.githubusercontent.com/Deepleaper/leaper-templates/master/index.json"
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_FETCH_TIMEOUT = 8
_GITHUB_API_BASE = "https://api.github.com/repos/Deepleaper/leaper-templates/contents"


def _get_github_token() -> str:
    """Read GitHub token from global config or env."""
    # Env var first
    token = os.environ.get("LEAPER_GITHUB_TOKEN", "")
    if token:
        return token
    # Global config
    global_path = Path.home() / ".leaper" / "global.yaml"
    if global_path.exists():
        try:
            import yaml
            cfg = yaml.safe_load(global_path.read_text(encoding="utf-8")) or {}
            return cfg.get("github_token", "")
        except Exception:
            pass
    return ""


def _github_headers() -> dict[str, str]:
    headers = {"User-Agent": "leaper-agent/0.9.4", "Accept": "application/vnd.github.v3.raw"}
    token = _get_github_token()
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def list_templates() -> list[dict[str, Any]]:
    """Return combined list of local + remote templates.

    Remote fetch is attempted first and merged with local.
    Falls back to local-only when network is unavailable.
    """
    local = _load_local_templates()
    try:
        remote = _fetch_remote_index()
        by_name: dict[str, dict] = {t["name"]: t for t in local}
        for t in remote:
            if t["name"] not in by_name:
                t.setdefault("source", "remote")
                by_name[t["name"]] = t
        return list(by_name.values())
    except Exception as exc:
        logger.debug("Workshop: remote fetch failed, using local only: %s", exc)
        return local


def download_template(name: str, target_dir: str) -> list[str]:
    """Copy or download template files into target_dir.

    Tries local bundled templates first, then falls back to remote GitHub download.
    Also assembles 3-layer skill paths (L1 industry + L2 role + L3 workstation)
    and writes them into the generated config.yaml as skills.external_dirs.

    Returns list of filenames written (skips files that already exist).
    Raises RuntimeError if the template cannot be found anywhere.
    """
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    local_path = _TEMPLATES_DIR / name
    if local_path.exists() and local_path.is_dir():
        written = _copy_local_template(local_path, target)
        # Assemble skills from 3-layer inheritance
        skill_dirs = _assemble_skills(local_path, _TEMPLATES_DIR)
        if skill_dirs:
            _inject_skill_dirs(target / "config.yaml", skill_dirs)
        return written

    try:
        written = _download_remote_template(name, target)
        return written
    except Exception as exc:
        raise RuntimeError(
            f"Template '{name}' not found locally and remote download failed: {exc}"
        ) from exc


def get_template_meta(name: str) -> dict[str, Any] | None:
    """Return metadata dict for a named template, or None if not found."""
    for t in list_templates():
        if t.get("name") == name:
            return t
    return None


# ── Internal helpers ──────────────────────────────────────────────────────────


# === Skill assembly (3-layer inheritance) ===
def _assemble_skills(template_dir: Path, templates_root: Path) -> list[str]:
    """Assemble skill paths from template.yaml (L1 + L2 + L3 with inheritance)."""
    import yaml

    template_yaml = template_dir / "template.yaml"
    if not template_yaml.exists():
        return []

    with open(template_yaml, 'r', encoding='utf-8') as f:
        meta = yaml.safe_load(f) or {}

    skills_root = templates_root.parent / "skills"
    skill_paths: list[str] = []

    # Handle inheritance (extends: cfo → load parent's skills first)
    extends = meta.get("extends")
    if extends:
        parent_dir = templates_root / extends
        parent_skills = _assemble_skills(parent_dir, templates_root)
        skill_paths.extend(parent_skills)

    # L1: Industry skill (auto from industry field)
    industry = meta.get("industry")
    if industry:
        l1_path = skills_root / "L1-industry" / industry
        if l1_path.exists():
            skill_paths.append(str(l1_path))

    # L2 + L3 from skills field
    skills_cfg = meta.get("skills", {})
    for l2_name in skills_cfg.get("L2", []):
        l2_path = skills_root / "L2-role" / l2_name
        if l2_path.exists():
            skill_paths.append(str(l2_path))

    for l3_name in skills_cfg.get("L3", []):
        l3_path = skills_root / "L3-workstation" / l3_name
        if l3_path.exists():
            skill_paths.append(str(l3_path))

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for p in skill_paths:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def _inject_skill_dirs(config_path: Path, skill_dirs: list[str]) -> None:
    """Write skill_dirs into config.yaml under skills.external_dirs."""
    import yaml

    config: dict = {}
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

    config.setdefault("skills", {})["external_dirs"] = skill_dirs

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    logger.info("Workshop: injected %d skill dirs into %s", len(skill_dirs), config_path)


def _load_local_templates() -> list[dict[str, Any]]:
    if not _TEMPLATES_DIR.exists():
        return []
    results: list[dict[str, Any]] = []
    for item in sorted(_TEMPLATES_DIR.iterdir()):
        if not item.is_dir() or item.name.startswith(("__", ".")):
            continue
        meta_file = item / "template.yaml"
        if meta_file.exists():
            try:
                import yaml
                data: dict = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
                data.setdefault("source", "local")
                results.append(data)
            except Exception as exc:
                logger.warning("Workshop: cannot parse %s: %s", meta_file, exc)
        else:
            results.append({
                "name": item.name,
                "displayName": item.name,
                "description": "(local template — no template.yaml found)",
                "source": "local",
            })
    return results


def _fetch_remote_index() -> list[dict[str, Any]]:
    url = f"{_GITHUB_API_BASE}/index.json?ref=master"
    req = urllib.request.Request(url, headers=_github_headers())
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
        data: dict = json.loads(resp.read())
    return data.get("templates", [])


def _copy_local_template(src: Path, target: Path) -> list[str]:
    written: list[str] = []
    for item in sorted(src.iterdir()):
        if item.name in ("__pycache__", "__init__.py") or item.name.startswith("."):
            continue
        dest = target / item.name
        if not dest.exists():
            shutil.copy2(item, dest)
            written.append(item.name)
            logger.info("Workshop: copied %s", item.name)
    return written


def _download_remote_template(name: str, target: Path) -> list[str]:
    # Fetch template.yaml via GitHub API (supports private repos)
    yaml_url = f"{_GITHUB_API_BASE}/templates/{name}/template.yaml?ref=master"
    req = urllib.request.Request(yaml_url, headers=_github_headers())
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
        import yaml
        meta: dict = yaml.safe_load(resp.read()) or {}

    files: list[str] = meta.get("files", [])
    if not files:
        raise ValueError(f"Remote template '{name}' has no files listed in template.yaml")

    written: list[str] = []
    for fname in files:
        dest = target / fname
        if dest.exists():
            continue
        file_url = f"{_GITHUB_API_BASE}/templates/{name}/{fname}?ref=master"
        req2 = urllib.request.Request(file_url, headers=_github_headers())
        with urllib.request.urlopen(req2, timeout=_FETCH_TIMEOUT) as resp2:
            dest.write_bytes(resp2.read())
        written.append(fname)
        logger.info("Workshop: downloaded %s", fname)

    return written
