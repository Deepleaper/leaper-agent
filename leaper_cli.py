"""Leaper Agent CLI — zero-dependency entry point (argparse only, PyYAML for config)."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

from leaper_config import LeaperConfig

# ── Helpers ─────────────────────────────────────────────────


def _pid_file(config: LeaperConfig, name: str) -> Path:
    return Path(config.get_workspace(name)).parent / "agent.pid"


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        pid = int(path.read_text().strip())
        return pid if _is_running(pid) else None
    except (ValueError, OSError):
        return None


# ── Commands ────────────────────────────────────────────────


def cmd_config(args: argparse.Namespace) -> None:
    """Interactive global config setup."""
    cfg = LeaperConfig()
    current = cfg.load_global()

    print("Leaper Global Configuration")
    print("Press Enter to keep current value.\n")

    fields = [
        ("api_key", "API Key", True),
        ("model", "Model (e.g. gpt-4o)", False),
        ("proxy", "HTTP Proxy", False),
        ("base_url", "API Base URL", False),
    ]

    for key, label, is_secret in fields:
        cur = current.get(key, "")
        display = ("***" + cur[-4:]) if is_secret and cur else (cur or "(not set)")
        val = input(f"  {label} [{display}]: ").strip()
        if val:
            current[key] = val

    cfg.save_global(current)
    print("\n✅ Config saved to", cfg.global_file)


def cmd_create(args: argparse.Namespace) -> None:
    """Create a new agent directory."""
    cfg = LeaperConfig()

    if args.name in cfg.list_agents():
        print(f"❌ Agent '{args.name}' already exists.")
        sys.exit(1)

    agent_cfg: dict = {
        "name": args.name,
        "template": args.template or "default",
        "created_at": datetime.now().isoformat(),
    }
    if args.bot_token:
        agent_cfg["bot_token"] = args.bot_token

    cfg.save_agent(args.name, agent_cfg)

    # Create workspace dir
    ws = Path(cfg.get_workspace(args.name))
    ws.mkdir(parents=True, exist_ok=True)

    print(f"✅ Agent '{args.name}' created at {cfg._agent_dir(args.name)}")


def cmd_start(args: argparse.Namespace) -> None:
    """Start agent(s)."""
    cfg = LeaperConfig()

    if args.all:
        agents = cfg.list_agents()
        if not agents:
            print("No agents found.")
            return
        for name in agents:
            _start_one(cfg, name)
    elif args.name:
        _start_one(cfg, args.name)
    else:
        print("❌ Specify agent name or --all")
        sys.exit(1)


def _start_one(cfg: LeaperConfig, name: str) -> None:
    if name not in cfg.list_agents():
        print(f"❌ Agent '{name}' not found.")
        return

    pid_path = _pid_file(cfg, name)
    if _read_pid(pid_path):
        print(f"⚠️  Agent '{name}' is already running (PID {pid_path.read_text().strip()}).")
        return

    agent_dir = str(cfg._agent_dir(name))
    env = {**os.environ, "LEAPER_AGENT_ID": name, "LEAPER_HOME": str(cfg.home)}

    proc = subprocess.Popen(
        [sys.executable, "-m", "hermes.gateway", "--agent-dir", agent_dir],
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    pid_path.write_text(str(proc.pid))
    print(f"🚀 Agent '{name}' started (PID {proc.pid})")


def cmd_stop(args: argparse.Namespace) -> None:
    """Stop a running agent."""
    cfg = LeaperConfig()
    pid_path = _pid_file(cfg, args.name)
    pid = _read_pid(pid_path)

    if not pid:
        print(f"Agent '{args.name}' is not running.")
        pid_path.unlink(missing_ok=True)
        return

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"🛑 Agent '{args.name}' stopped (PID {pid})")
    except OSError as e:
        print(f"❌ Failed to stop: {e}")
    finally:
        pid_path.unlink(missing_ok=True)


def cmd_list(args: argparse.Namespace) -> None:
    """List all agents with status."""
    cfg = LeaperConfig()
    agents = cfg.list_agents()

    if not agents:
        print("No agents found. Create one with: leaper create <name>")
        return

    print(f"{'Name':<20} {'Status':<12} {'Template':<15} {'Created'}")
    print("-" * 65)

    for name in agents:
        acfg = cfg.load_agent(name)
        pid = _read_pid(_pid_file(cfg, name))
        status = f"🟢 running ({pid})" if pid else "⚫ stopped"
        tpl = acfg.get("template", "-")
        created = acfg.get("created_at", "-")[:10]
        print(f"{name:<20} {status:<12} {tpl:<15} {created}")


def cmd_status(args: argparse.Namespace) -> None:
    """Show agent details."""
    cfg = LeaperConfig()

    if args.name not in cfg.list_agents():
        print(f"❌ Agent '{args.name}' not found.")
        sys.exit(1)

    acfg = cfg.load_agent(args.name)
    pid = _read_pid(_pid_file(cfg, args.name))

    print(f"Agent: {args.name}")
    print(f"Status: {'running (PID ' + str(pid) + ')' if pid else 'stopped'}")
    print(f"Directory: {cfg._agent_dir(args.name)}")
    print(f"Workspace: {cfg.get_workspace(args.name)}")
    print(f"DB: {cfg.get_db_path(args.name)}")
    print(f"Template: {acfg.get('template', '-')}")
    print(f"Created: {acfg.get('created_at', '-')}")


def cmd_workshop_list(args: argparse.Namespace) -> None:
    """List available templates."""
    # Built-in templates; extensible via registry
    templates = [
        ("default", "Blank agent with minimal config"),
        ("telegram-bot", "Telegram bot with conversation memory"),
        ("discord-bot", "Discord bot with slash commands"),
        ("api-server", "HTTP API agent with REST endpoints"),
        ("rag-agent", "RAG-powered agent with document ingestion"),
    ]
    print(f"{'ID':<20} {'Description'}")
    print("-" * 55)
    for tid, desc in templates:
        print(f"{tid:<20} {desc}")


def cmd_workshop_install(args: argparse.Namespace) -> None:
    """Install a template from the workshop."""
    cfg = LeaperConfig()
    tpl_dir = cfg.home / "templates" / args.id

    if tpl_dir.exists():
        print(f"Template '{args.id}' is already installed.")
        return

    # Placeholder: in production this would fetch from a registry
    tpl_dir.mkdir(parents=True, exist_ok=True)
    (tpl_dir / "template.yaml").write_text(
        f"id: {args.id}\ninstalled_at: {datetime.now().isoformat()}\n"
    )
    print(f"✅ Template '{args.id}' installed to {tpl_dir}")


# ── Parser ──────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leaper",
        description="Leaper Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              leaper config                          Setup global config
              leaper create my-bot --template telegram-bot
              leaper start my-bot
              leaper list
              leaper workshop list
        """),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # config
    sub.add_parser("config", help="Interactive global config setup")

    # create
    p_create = sub.add_parser("create", help="Create a new agent")
    p_create.add_argument("name", help="Agent name")
    p_create.add_argument("--template", "-t", default="default", help="Template to use")
    p_create.add_argument("--bot-token", help="Bot token (e.g. Telegram)")

    # start
    p_start = sub.add_parser("start", help="Start agent(s)")
    p_start.add_argument("name", nargs="?", help="Agent name")
    p_start.add_argument("--all", action="store_true", help="Start all agents")

    # stop
    p_stop = sub.add_parser("stop", help="Stop a running agent")
    p_stop.add_argument("name", help="Agent name")

    # list
    sub.add_parser("list", help="List all agents with status")

    # status
    p_status = sub.add_parser("status", help="Show agent details")
    p_status.add_argument("name", help="Agent name")

    # workshop
    p_ws = sub.add_parser("workshop", help="Template workshop")
    ws_sub = p_ws.add_subparsers(dest="ws_command", required=True)
    ws_sub.add_parser("list", help="List available templates")
    p_ws_install = ws_sub.add_parser("install", help="Install a template")
    p_ws_install.add_argument("id", help="Template ID")

    return parser


# ── Dispatch ────────────────────────────────────────────────

_DISPATCH = {
    "config": cmd_config,
    "create": cmd_create,
    "start": cmd_start,
    "stop": cmd_stop,
    "list": cmd_list,
    "status": cmd_status,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "workshop":
        if args.ws_command == "list":
            cmd_workshop_list(args)
        elif args.ws_command == "install":
            cmd_workshop_install(args)
    elif args.command in _DISPATCH:
        _DISPATCH[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
