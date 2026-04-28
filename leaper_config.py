"""Leaper Config — reads leaper.yaml and maps to Hermes gateway/config.py.

Supports two leaper.yaml formats:
  New (v0.9.0+):  model.provider / model.name / model.apiKey / model.baseUrl
  Old (v0.7.x):   provider.type  / provider.model / provider.apiKey / provider.baseUrl

Priority chain:
  1. leaper.yaml in current directory (workspace)
  2. ~/.leaper/leaper.yaml (user global)
  3. Environment variables
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False


def load_leaper_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load and return the merged Leaper configuration dict."""
    candidates: list[Path] = []
    if config_path:
        candidates.append(Path(config_path))
    candidates.append(Path("leaper.yaml"))
    candidates.append(Path.home() / ".leaper" / "leaper.yaml")

    cfg: dict[str, Any] = {}
    for path in candidates:
        if path.exists():
            cfg = _read_yaml(path)
            break

    cfg = _normalize_config(cfg)
    cfg = _apply_env_overrides(cfg)
    return cfg


def _read_yaml(path: Path) -> dict[str, Any]:
    if not _YAML_OK:
        raise RuntimeError("pyyaml is not installed. Run: pip install pyyaml")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _normalize_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Bridge old (provider.type) → new (model.provider) format for backward compat."""
    if "provider" in cfg and "model" not in cfg:
        old = cfg.pop("provider")
        cfg["model"] = {
            "provider": old.get("type", "openai"),
            "name": old.get("model", "gpt-4o"),
            "apiKey": old.get("apiKey", ""),
            "baseUrl": old.get("baseUrl", ""),
        }
    cfg.setdefault("model", {})
    cfg.setdefault("channel", {})
    cfg.setdefault("brain", {})
    return cfg


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    """Apply LEAPER_ environment variable overrides."""
    model = cfg.setdefault("model", {})
    channel = cfg.setdefault("channel", {})
    brain = cfg.setdefault("brain", {})

    if v := os.environ.get("LEAPER_PROVIDER"):
        model["provider"] = v
    if v := os.environ.get("LEAPER_MODEL"):
        model["name"] = v
    if v := os.environ.get("LEAPER_API_KEY"):
        model["apiKey"] = v
    if v := os.environ.get("LEAPER_BASE_URL"):
        model["baseUrl"] = v

    if v := os.environ.get("LEAPER_TELEGRAM_TOKEN"):
        channel.setdefault("type", "telegram")
        channel["token"] = v

    if v := os.environ.get("LEAPER_BRAIN_DB"):
        brain["dbPath"] = v

    if v := os.environ.get("LEAPER_PROXY") or os.environ.get("HTTP_PROXY"):
        cfg["proxy"] = v

    return cfg


def config_to_hermes_env(cfg: dict[str, Any]) -> dict[str, str]:
    """Convert a Leaper config dict into environment variables for Hermes gateway."""
    env: dict[str, str] = {}
    model = cfg.get("model", {})
    channel = cfg.get("channel", {})
    brain = cfg.get("brain", {})

    api_key = model.get("apiKey", "")
    provider_type = model.get("provider", "openai").lower()

    if api_key:
        if provider_type == "anthropic":
            env["ANTHROPIC_API_KEY"] = api_key
        else:
            env["OPENAI_API_KEY"] = api_key
            env["LEAPER_API_KEY"] = api_key

    if v := model.get("baseUrl"):
        env["OPENAI_BASE_URL"] = v

    if v := model.get("name"):
        env["HERMES_MODEL"] = v

    channel_type = channel.get("type", "")
    if channel_type == "telegram":
        if v := channel.get("token"):
            env["TELEGRAM_BOT_TOKEN"] = v
        if allowed := os.environ.get("TELEGRAM_ALLOWED_USERS"):
            env.setdefault("TELEGRAM_HOME_CHANNEL", allowed.split(",")[0].strip())
    elif channel_type == "discord":
        if v := channel.get("token"):
            env["DISCORD_BOT_TOKEN"] = v

    if brain.get("enabled", True):
        if v := brain.get("dbPath"):
            env["LEAPER_BRAIN_DB"] = v
        env["HERMES_MEMORY_PROVIDER"] = "leaper"

    if v := cfg.get("proxy"):
        env["HTTP_PROXY"] = v
        env["HTTPS_PROXY"] = v
        env["ALL_PROXY"] = v

    if v := cfg.get("name"):
        env["HERMES_AGENT_NAME"] = v

    return env


def write_hermes_config(cfg: dict[str, Any], leaper_home: Path | None = None) -> None:
    """Write a minimal Hermes-compatible config.yaml into the Leaper home dir."""
    if not _YAML_OK:
        return

    home = leaper_home or (Path.home() / ".leaper")
    home.mkdir(parents=True, exist_ok=True)
    config_path = home / "config.yaml"

    model = cfg.get("model", {})
    channel = cfg.get("channel", {})

    provider_type = model.get("provider", "openai").lower()
    model_name = model.get("name", "gpt-4o")
    base_url = model.get("baseUrl", "")
    api_key = model.get("apiKey", "")

    hermes_cfg: dict[str, Any] = {}

    model_cfg: dict[str, Any] = {}
    if model_name:
        model_cfg["default"] = model_name

    if provider_type == "ollama":
        # Ollama exposes an OpenAI-compatible endpoint
        model_cfg["base_url"] = base_url or "http://localhost:11434/v1"
        model_cfg["api_key"] = "ollama"
    elif base_url and provider_type not in ("openai", "anthropic"):
        # Custom / compatible API
        provider_name = "leaper-api"
        model_cfg["provider"] = f"custom:{provider_name}"
        model_cfg["base_url"] = base_url
        hermes_cfg["providers"] = {
            provider_name: {
                "base_url": base_url,
                "api_key": api_key or "no-key-required",
                "model": model_name,
            }
        }
    elif base_url:
        model_cfg["base_url"] = base_url

    if model_cfg:
        hermes_cfg["model"] = model_cfg

    if cfg.get("brain", {}).get("enabled", True):
        hermes_cfg["memory"] = {"provider": "leaper"}

    channel_type = channel.get("type", "")
    if channel_type == "telegram":
        hermes_cfg["platform"] = "telegram"
    elif channel_type == "discord":
        hermes_cfg["platform"] = "discord"
    elif channel_type == "feishu":
        hermes_cfg["platform"] = "feishu"
    elif channel_type == "dingtalk":
        hermes_cfg["platform"] = "dingtalk"

    if base_url and api_key and provider_type not in ("openai", "anthropic", "ollama"):
        aux_cfg: dict[str, Any] = {
            "model": model_name,
            "base_url": base_url,
            "api_key": api_key,
            "provider": "custom:leaper-api",
        }
        hermes_cfg["auxiliary"] = aux_cfg

    if v := cfg.get("name"):
        hermes_cfg["agent_name"] = v

    hermes_cfg["approvals"] = {"mode": "off"}

    if hermes_cfg:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(hermes_cfg, f, allow_unicode=True)
