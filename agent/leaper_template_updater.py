"""Template OTA updater — checks and applies template updates for Leaper agents."""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Files we own and can update freely
OUR_FILES: frozenset[str] = frozenset({"EGO.md", "SOUL.md", "IDENTITY.md", "AGENTS.md"})
# Files the user owns — never touched by the updater
USER_FILES: frozenset[str] = frozenset({"USER.md", "MEMORY.md", "brain.db", ".env"})

DEFAULT_REGISTRY_URL = "https://raw.githubusercontent.com/Deepleaper/leaper-templates/main"
DEFAULT_CHECK_INTERVAL = 86400  # seconds (24 h)


@dataclasses.dataclass
class AgentEntry:
    agent_id: str      # unique identifier (usually the agent dir name)
    agent_dir: Path    # directory containing the agent's files
    template_name: str
    local_version: str


@dataclasses.dataclass
class UpdateResult:
    agent: AgentEntry
    remote_version: str
    template_meta: dict[str, Any]


class TemplateUpdater:
    def __init__(
        self,
        registry_url: str = DEFAULT_REGISTRY_URL,
        leaper_home: Path | None = None,
    ) -> None:
        self.registry_url = registry_url.rstrip("/")
        self._leaper_home = leaper_home or Path(
            os.environ.get("LEAPER_HOME", str(Path.home() / ".leaper"))
        )
        self._cache_file = self._leaper_home / ".update_cache.json"
        self._cache: dict[str, Any] = self._load_cache()

    # ── Cache ──────────────────────────────────────────────────────────────────

    def _load_cache(self) -> dict[str, Any]:
        if self._cache_file.exists():
            try:
                return json.loads(self._cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_cache(self) -> None:
        try:
            self._leaper_home.mkdir(parents=True, exist_ok=True)
            self._cache_file.write_text(
                json.dumps(self._cache, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("Could not save update cache: %s", exc)

    # ── Public API ─────────────────────────────────────────────────────────────

    def check_for_updates(
        self,
        agents: list[AgentEntry],
        force: bool = False,
    ) -> list[UpdateResult]:
        """Return UpdateResult for every agent whose template has a newer remote version.

        When force=True, return all agents that exist in the remote index regardless
        of local version (useful for leaper update --force).
        """
        try:
            remote_templates = self._fetch_index()
        except Exception as exc:
            logger.warning("Template update check failed to fetch index: %s", exc)
            return []

        remote_by_name = {t["name"]: t for t in remote_templates}
        updates: list[UpdateResult] = []

        for agent in agents:
            remote = remote_by_name.get(agent.template_name)
            if remote is None:
                continue
            remote_ver = remote.get("version", "0.0.0")
            if force or _version_gt(remote_ver, agent.local_version):
                updates.append(UpdateResult(
                    agent=agent,
                    remote_version=remote_ver,
                    template_meta=remote,
                ))

        return updates

    def apply_updates(self, updates: list[UpdateResult]) -> None:
        """Download and apply template updates, protecting user-owned files."""
        for result in updates:
            try:
                self._apply_single(result)
            except Exception as exc:
                logger.error(
                    "Failed to apply update for %s/%s: %s",
                    result.agent.agent_id, result.agent.template_name, exc,
                )

    # ── Internal ───────────────────────────────────────────────────────────────

    def _fetch_index(self) -> list[dict[str, Any]]:
        """Fetch remote index.json with ETag/If-Modified-Since caching."""
        url = f"{self.registry_url}/index.json"
        headers: dict[str, str] = {"User-Agent": "leaper-agent/0.9.5"}

        token = self._get_github_token()
        if token:
            headers["Authorization"] = f"token {token}"

        cached = self._cache.get("index", {})
        if cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        if cached.get("last_modified"):
            headers["If-Modified-Since"] = cached["last_modified"]

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
                new_etag = resp.headers.get("ETag", "")
                new_lm = resp.headers.get("Last-Modified", "")
                data = json.loads(body)
                templates = data.get("templates", [])
                self._cache["index"] = {
                    "etag": new_etag,
                    "last_modified": new_lm,
                    "templates": templates,
                }
                self._save_cache()
                return templates
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                logger.debug("Remote index unchanged (304), using cached data")
                return cached.get("templates", [])
            raise

    def _apply_single(self, result: UpdateResult) -> None:
        agent = result.agent
        meta = result.template_meta
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        backup_dir = self._leaper_home / "backups" / agent.agent_id / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        # files may be dict {filename: checksum} or list [filename, ...]
        raw_files = meta.get("files", {})
        filenames: list[str] = list(raw_files.keys()) if isinstance(raw_files, dict) else list(raw_files)

        base_url = f"{self.registry_url}/templates/{agent.template_name}"
        updated: list[str] = []

        for fname in filenames:
            if fname in USER_FILES:
                continue

            if fname == "config.yaml":
                self._merge_config(
                    agent.agent_dir / "config.yaml",
                    f"{base_url}/config.yaml",
                    backup_dir,
                )
                updated.append(fname)
                continue

            # Only update files we own or the skills/ subtree
            is_ours = fname in OUR_FILES or fname.startswith("skills/")
            if not is_ours:
                continue

            dest = agent.agent_dir / fname
            if dest.exists():
                shutil.copy2(dest, backup_dir / fname)

            content = self._download(f"{base_url}/{fname}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            updated.append(fname)

        # Bump the version recorded in local template.yaml
        self._update_template_version(agent.agent_dir / "template.yaml", result.remote_version)

        logger.info(
            "Applied template update: agent=%s template=%s %s → %s (%s)",
            agent.agent_id,
            agent.template_name,
            agent.local_version,
            result.remote_version,
            ", ".join(updated) if updated else "no files changed",
        )

    def _download(self, url: str) -> bytes:
        headers: dict[str, str] = {"User-Agent": "leaper-agent/0.9.5"}
        token = self._get_github_token()
        if token:
            headers["Authorization"] = f"token {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()

    def _get_github_token(self) -> str:
        token = os.environ.get("LEAPER_GITHUB_TOKEN", "")
        if token:
            return token
        global_path = self._leaper_home / "global.yaml"
        if global_path.exists():
            try:
                import yaml
                cfg = yaml.safe_load(global_path.read_text(encoding="utf-8")) or {}
                return cfg.get("github_token", "")
            except Exception:
                pass
        return ""

    def _merge_config(self, local_path: Path, remote_url: str, backup_dir: Path) -> None:
        """Merge remote config.yaml into local, only adding keys absent locally."""
        import yaml

        try:
            remote_cfg: dict = yaml.safe_load(self._download(remote_url)) or {}
        except Exception as exc:
            logger.debug("Could not fetch remote config.yaml: %s", exc)
            return

        local_cfg: dict = {}
        if local_path.exists():
            try:
                local_cfg = yaml.safe_load(local_path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass
            shutil.copy2(local_path, backup_dir / "config.yaml")

        merged = _deep_merge_new_keys(remote_cfg, local_cfg)
        local_path.write_text(
            yaml.dump(merged, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

    def _update_template_version(self, path: Path, new_version: str) -> None:
        import yaml
        if not path.exists():
            return
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            data["version"] = new_version
            path.write_text(
                yaml.dump(data, default_flow_style=False, allow_unicode=True),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("Could not update template.yaml version: %s", exc)


# ── Utility functions ──────────────────────────────────────────────────────────


def load_agents_from_home(leaper_home: Path | None = None) -> list[AgentEntry]:
    """Discover AgentEntry objects from ~/.leaper/ hierarchy."""
    home = leaper_home or Path(
        os.environ.get("LEAPER_HOME", str(Path.home() / ".leaper"))
    )
    agents: list[AgentEntry] = []

    # Single-agent mode: ~/.leaper/template.yaml
    _try_add_agent(home, "default", agents)

    # Multi-agent mode: ~/.leaper/agents/*/template.yaml
    agents_dir = home / "agents"
    if agents_dir.exists():
        for d in sorted(agents_dir.iterdir()):
            if d.is_dir():
                _try_add_agent(d, d.name, agents)

    return agents


def _try_add_agent(agent_dir: Path, agent_id: str, out: list[AgentEntry]) -> None:
    template_yaml = agent_dir / "template.yaml"
    if not template_yaml.exists():
        return
    try:
        import yaml
        meta = yaml.safe_load(template_yaml.read_text(encoding="utf-8")) or {}
        template_name = meta.get("name", "")
        if not template_name:
            return
        out.append(AgentEntry(
            agent_id=agent_id,
            agent_dir=agent_dir,
            template_name=template_name,
            local_version=meta.get("version", "0.0.0"),
        ))
    except Exception as exc:
        logger.debug("Could not read template.yaml at %s: %s", agent_dir, exc)


def _version_gt(a: str, b: str) -> bool:
    """Return True if semver a > b."""
    try:
        def _parse(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.strip().lstrip("v").split(".")[:3])
        return _parse(a) > _parse(b)
    except (ValueError, TypeError):
        return False


def _deep_merge_new_keys(source: dict, target: dict) -> dict:
    """Recursively merge source into target, only adding absent keys."""
    result = dict(target)
    for key, value in source.items():
        if key not in result:
            result[key] = value
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_new_keys(value, result[key])
    return result
