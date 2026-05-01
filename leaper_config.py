"""Leaper config management — global + per-agent YAML configs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class LeaperConfig:
    """Manages ~/.leaper global config and per-agent configs."""

    def __init__(self, home_dir: str | None = None) -> None:
        self.home = Path(home_dir) if home_dir else Path.home() / ".leaper"
        self.agents_dir = self.home / "agents"
        self.global_file = self.home / "global.yaml"

    # ── global ──────────────────────────────────────────────

    def load_global(self) -> dict[str, Any]:
        if not self.global_file.exists():
            return {}
        with open(self.global_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_global(self, config: dict[str, Any]) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        with open(self.global_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    # ── per-agent ───────────────────────────────────────────

    def _agent_dir(self, name: str) -> Path:
        return self.agents_dir / name

    def _agent_file(self, name: str) -> Path:
        return self._agent_dir(name) / "agent.yaml"

    def load_agent(self, name: str) -> dict[str, Any]:
        p = self._agent_file(name)
        if not p.exists():
            return {}
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_agent(self, name: str, config: dict[str, Any]) -> None:
        d = self._agent_dir(name)
        d.mkdir(parents=True, exist_ok=True)
        with open(self._agent_file(name), "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    def list_agents(self) -> list[str]:
        if not self.agents_dir.exists():
            return []
        return sorted(
            d.name
            for d in self.agents_dir.iterdir()
            if d.is_dir() and (d / "agent.yaml").exists()
        )

    def get_db_path(self, agent_name: str) -> str:
        agent_cfg = self.load_agent(agent_name)
        if db := agent_cfg.get("db_path"):
            return str(db)
        return str(self._agent_dir(agent_name) / "leaper.db")

    def get_workspace(self, agent_name: str) -> str:
        agent_cfg = self.load_agent(agent_name)
        if ws := agent_cfg.get("workspace"):
            return str(ws)
        return str(self._agent_dir(agent_name) / "workspace")
