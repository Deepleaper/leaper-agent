"""Leaper CLI — v0.9.3 产品级安装体验

Commands:
  leaper init [--template NAME]  交互式向导，生成 leaper.yaml + .env
  leaper run                     启动 agent（读 leaper.yaml → 拉起 gateway）
  leaper chat                    终端对话（零配置，无 leaper.yaml 也能用）
  leaper workshop                查看可用模板
  leaper status                  查看当前配置状态
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

# ── Optional rich ─────────────────────────────────────────────────────────────
try:
    from rich.console import Console as _RichConsole
    _RICH = True
except ImportError:
    _RICH = False

# ── Output helpers ────────────────────────────────────────────────────────────

def _cprint(msg: str) -> None:
    """Print with rich markup, or strip tags and plain-print as fallback."""
    try:
        if _RICH:
            _RichConsole().print(msg)
        else:
            import re
            print(re.sub(r"\[/?[^\]]*\]", "", msg))
    except UnicodeEncodeError:
        import re
        clean = re.sub(r"\[/?[^\]]*\]", "", msg)
        print(clean.encode("ascii", errors="replace").decode("ascii"))


def _ask(question: str, default: str = "", password: bool = False) -> str:
    """Interactive input — rich Prompt when available, plain input() otherwise."""
    if _RICH and not password:
        from rich.prompt import Prompt
        if default:
            return Prompt.ask(question, default=default)
        return Prompt.ask(question)
    if _RICH and password:
        from rich.prompt import Prompt
        return Prompt.ask(question, password=True)
    # plain fallback
    if password:
        import getpass
        return getpass.getpass(f"{question}: ")
    suffix = f" [{default}]" if default else ""
    val = input(f"{question}{suffix}: ").strip()
    return val or default


def _print_menu(options: list[str]) -> int:
    """Display numbered list, return 1-based index of user choice."""
    for i, opt in enumerate(options, 1):
        _cprint(f"  [[bold]{i}[/bold]] {opt}")
    while True:
        try:
            if _RICH:
                from rich.prompt import Prompt
                raw = Prompt.ask(">").strip()
            else:
                raw = input("> ").strip()
            n = int(raw)
            if 1 <= n <= len(options):
                return n
        except (ValueError, TypeError):
            pass
        except (KeyboardInterrupt, EOFError):
            raise
        _cprint(f"[yellow]请输入 1-{len(options)} 之间的数字[/yellow]")


def _banner() -> None:
    _cprint(
        "\n[bold cyan]Leaper Agent[/bold cyan] [dim]v0.9.3[/dim]  "
        "[dim]Self-Evolving AI Agent Framework[/dim]\n"
    )


# ── Ollama detection ──────────────────────────────────────────────────────────

def _detect_ollama() -> list[dict[str, Any]]:
    """Return list of {name, size_gb} dicts for local Ollama models, or [] if not running."""
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"User-Agent": "leaper-agent/0.9.0"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        models = []
        for m in data.get("models", []):
            size_gb = round(m.get("size", 0) / 1e9, 1)
            models.append({"name": m["name"], "size_gb": size_gb})
        return models
    except Exception:
        return []


# ── leaper init ───────────────────────────────────────────────────────────────

def cmd_init(workspace: str = ".", template: str = "", name: str = "") -> None:
    """交互式向导：4 个问题生成 leaper.yaml + .env"""
    _banner()
    workspace_path = Path(workspace).resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)

    _cprint("[bold]👋 欢迎使用 Leaper Agent！[/bold]\n")

    # ── 模板选择 ─────────────────────────────────────────────────────────────
    if not template:
        _cprint("[bold]要使用模板吗？（推荐首次使用者选择模板）[/bold]")
        # Scan templates/ directory
        templates_dir = Path(__file__).parent / "templates"
        template_options = []
        if templates_dir.exists():
            for d in sorted(templates_dir.iterdir()):
                if d.is_dir() and (d / "template.yaml").exists():
                    tmpl_name = d.name
                    # Try to read display name from template.yaml
                    try:
                        import yaml as _yaml
                        meta = _yaml.safe_load((d / "template.yaml").read_text(encoding="utf-8"))
                        display = meta.get("displayName", tmpl_name)
                        desc = meta.get("description", "")
                        template_options.append((tmpl_name, f"{display} — {desc}" if desc else display))
                    except Exception:
                        template_options.append((tmpl_name, tmpl_name))

        menu_items = [opt[1] for opt in template_options] + ["从零开始（空白配置）"]
        choice = _print_menu(menu_items)
        if choice <= len(template_options):
            template = template_options[choice - 1][0]
            _cprint(f"\n[green]✓[/green] 使用模板：{template}\n")

    # ── 模板模式 ─────────────────────────────────────────────────────────────
    if template:
        _cprint(f"[bold]使用模板：{template}[/bold]\n")
        try:
            from leaper_workshop import download_template, get_template_meta
            meta = get_template_meta(template)
            if meta:
                display = meta.get("displayName", template)
                desc = meta.get("description", "")
                _cprint(f"[green]✓[/green] {display}")
                if desc:
                    _cprint(f"  [dim]{desc}[/dim]\n")
            files = download_template(template, str(workspace_path))
            if files:
                _cprint(f"[dim]已拷贝：{', '.join(files)}[/dim]\n")
        except Exception as exc:
            _cprint(f"[yellow]⚠ 模板加载失败（{exc}），继续手动配置[/yellow]\n")

    # ── Q1: 名字 ─────────────────────────────────────────────────────────────
    if not name and template:
        # Auto-fill name from template
        try:
            import yaml as _yaml
            tmpl_yaml = Path(__file__).parent / "templates" / template / "template.yaml"
            if tmpl_yaml.exists():
                meta = _yaml.safe_load(tmpl_yaml.read_text(encoding="utf-8"))
                name = meta.get("displayName", meta.get("name", ""))
        except Exception:
            pass
    if not name:
        _cprint("[bold]1/4 给你的 AI 取个名字：[/bold]")
        name = _ask("").strip() or "我的 AI 助手"

    # ── Q2: 提供商 ────────────────────────────────────────────────────────────
    _cprint("\n[bold]2/4 选择 AI 模型提供商：[/bold]")
    provider_options = [
        "OpenAI (GPT-4o)",
        "Anthropic (Claude)",
        "兼容 API（聚合平台、自建服务等）",
        "Ollama 本地模型（免费，需本地运行 Ollama）",
    ]
    provider_choice = _print_menu(provider_options)
    provider_map = {1: "openai", 2: "anthropic", 3: "custom", 4: "ollama"}
    provider = provider_map[provider_choice]

    model_name = ""
    api_key = ""
    base_url = ""

    if provider == "ollama":
        _cprint("\n[dim]正在检测本地 Ollama 模型...[/dim]")
        ollama_models = _detect_ollama()
        if ollama_models:
            _cprint("[green]检测到本地 Ollama 模型：[/green]")
            model_options = [
                f"{m['name']} ({m['size_gb']}GB) ✅" for m in ollama_models
            ] + ["手动输入模型名"]
            m_choice = _print_menu(model_options)
            if m_choice <= len(ollama_models):
                model_name = ollama_models[m_choice - 1]["name"]
            else:
                _cprint("[bold]请输入模型名（如 qwen2.5:7b）：[/bold]")
                model_name = _ask("").strip() or "qwen2.5:7b"
            _cprint(f"\n[green]✓[/green] 使用本地模型 {model_name}，无需 API Key，完全离线。")
        else:
            _cprint(
                "[yellow]⚠ 未检测到 Ollama（http://localhost:11434 无响应）[/yellow]\n"
                "[dim]可先继续配置，稍后再启动 Ollama。[/dim]"
            )
            _cprint("\n[bold]请输入模型名（如 qwen2.5:7b）：[/bold]")
            model_name = _ask("").strip() or "qwen2.5:7b"
    elif provider == "openai":
        model_name = "gpt-4o"
        _cprint("\n[bold]3/4 OpenAI API Key（在 platform.openai.com 获取）：[/bold]")
        api_key = _ask("", password=True).strip()
    elif provider == "anthropic":
        model_name = "claude-sonnet-4-6"
        _cprint("\n[bold]3/4 Anthropic API Key（在 console.anthropic.com 获取）：[/bold]")
        api_key = _ask("", password=True).strip()
    else:  # custom
        _cprint("\n[bold]3/4 API Key：[/bold]")
        api_key = _ask("", password=True).strip()
        _cprint("[bold]Base URL（如 https://api.openai-proxy.com/v1）：[/bold]")
        base_url = _ask("").strip()
        _cprint("[bold]模型名（如 gpt-4o）：[/bold]")
        model_name = _ask("").strip() or "gpt-4o"

    # ── Q4: 平台 ──────────────────────────────────────────────────────────────
    _cprint("\n[bold]4/4 连接到哪个平台？[/bold]")
    platform_options = [
        "Telegram（最推荐，扫码即用）",
        "终端对话（先试试）",
        "Discord",
        "飞书",
        "钉钉",
    ]
    plat_choice = _print_menu(platform_options)
    plat_map = {1: "telegram", 2: "terminal", 3: "discord", 4: "feishu", 5: "dingtalk"}
    channel_type = plat_map[plat_choice]

    channel_token = ""
    if channel_type == "telegram":
        _cprint(
            "\n[dim]Telegram Bot Token（从 @BotFather 获取，教程：https://leaper.ai/telegram）：[/dim]"
        )
        channel_token = _ask("").strip()
    elif channel_type == "discord":
        _cprint("\n[dim]Discord Bot Token：[/dim]")
        channel_token = _ask("").strip()
    elif channel_type in ("feishu", "dingtalk"):
        _cprint(f"\n[dim]{channel_type} App Token：[/dim]")
        channel_token = _ask("").strip()

    # ── 写文件 ────────────────────────────────────────────────────────────────
    _write_leaper_yaml(workspace_path, name, provider, model_name, api_key, base_url, channel_type, channel_token)
    _write_dotenv(workspace_path, provider, api_key, channel_type, channel_token)

    _cprint("\n[green]✅ 配置完成！文件已生成：[/green]")
    _cprint(f"   [dim]{workspace_path / 'leaper.yaml'}[/dim]")
    _cprint(f"   [dim]{workspace_path / '.env'}[/dim]")

    # ── 复制模板 .md 文件到 ~/.leaper/ ─────────────────────────────────────
    _deploy_workspace_files(workspace_path, name, template)

    _cprint("\n[bold]下一步：[/bold]")
    _cprint("  [cyan]leaper run[/cyan]    # 启动 agent")
    _cprint("  [cyan]leaper chat[/cyan]   # 先在终端里试试\n")


def _deploy_workspace_files(workspace: Path, name: str, template: str) -> None:
    """Copy template .md files (or generate defaults) into ~/.leaper/ for the base engine to read."""
    import shutil
    leaper_home = Path.home() / ".leaper"
    leaper_home.mkdir(parents=True, exist_ok=True)

    # Remove stale seed marker so seed loader re-reads files
    marker = leaper_home / ".leaper-seeded"
    if marker.exists():
        marker.unlink()

    # Try to find template files
    template_dir = None
    if template:
        candidate = workspace / "templates" / template
        if not candidate.exists():
            # Also check relative to the leaper-python install
            candidate = Path(__file__).parent / "templates" / template
        if candidate.exists():
            template_dir = candidate

    md_files = ["EGO.md", "SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md"]

    if template_dir:
        copied = []
        for f in md_files + ["template.yaml"]:
            src = template_dir / f
            if src.exists():
                shutil.copy2(src, leaper_home / f)
                copied.append(f)
        if copied:
            _cprint(f"   [dim]人格文件已部署到 {leaper_home}: {', '.join(copied)}[/dim]")
    else:
        # Generate minimal defaults
        defaults = {
            "SOUL.md": f"# {name}\n\n我是 {name}，一个由 Leaper Agent 驱动的 AI 助手。\n",
            "IDENTITY.md": f"# IDENTITY\n\n- **Name**: {name}\n- **Powered by**: Leaper Agent\n",
        }
        for fname, content in defaults.items():
            target = leaper_home / fname
            if not target.exists():
                target.write_text(content, encoding="utf-8")
        _cprint(f"   [dim]默认人格文件已生成到 {leaper_home}[/dim]")

    # Also copy .env to ~/.leaper/ for the gateway to read
    env_src = workspace / ".env"
    env_dst = leaper_home / ".env"
    if env_src.exists():
        shutil.copy2(env_src, env_dst)


def _write_leaper_yaml(
    workspace: Path,
    name: str,
    provider: str,
    model_name: str,
    api_key: str,
    base_url: str,
    channel_type: str,
    channel_token: str,
) -> None:
    lines = [
        f"name: '{name}'",
        "model:",
        f"  provider: {provider}",
        f"  name: {model_name}",
    ]
    if api_key:
        lines.append(f"  apiKey: '{api_key}'")
    if base_url:
        lines.append(f"  baseUrl: '{base_url}'")

    if channel_type and channel_type != "terminal":
        lines += ["channel:", f"  type: {channel_type}"]
        if channel_token:
            lines.append(f"  token: '{channel_token}'")

    lines += [
        "brain:",
        "  enabled: true",
        "  localModel: auto",
        "proxy: ''",
    ]
    (workspace / "leaper.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_dotenv(
    workspace: Path,
    provider: str,
    api_key: str,
    channel_type: str,
    channel_token: str,
) -> None:
    lines: list[str] = []
    if api_key:
        if provider == "anthropic":
            lines.append(f"ANTHROPIC_API_KEY={api_key}")
        else:
            lines.append(f"LEAPER_API_KEY={api_key}")
    if channel_token:
        if channel_type == "telegram":
            lines.append(f"TELEGRAM_BOT_TOKEN={channel_token}")
        elif channel_type == "discord":
            lines.append(f"DISCORD_BOT_TOKEN={channel_token}")

    # ── 默认产品配置（隐藏技术细节、关闭引用回复）──
    lines.append("")
    lines.append("# Leaper defaults — do not expose internals to users")
    lines.append("TELEGRAM_REPLY_TO_MODE=off")
    lines.append("HERMES_SHOW_TOOL_CALLS=false")
    lines.append("HERMES_TOOL_PROGRESS_MODE=off")
    lines.append("GATEWAY_ALLOW_ALL_USERS=true")

    (workspace / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── leaper run ────────────────────────────────────────────────────────────────

def cmd_run(workspace: str = ".") -> None:
    """读 leaper.yaml → 转换为 Hermes 格式 → 启动 gateway"""
    _banner()

    yaml_path = _find_leaper_yaml(workspace)
    if yaml_path is None:
        _cprint("[red]❌ 未找到 leaper.yaml[/red]")
        _cprint("\n请先运行：[cyan]leaper init[/cyan]")
        sys.exit(1)

    _bootstrap_env(workspace)

    try:
        from leaper_config import load_leaper_config, config_to_hermes_env, write_hermes_config
    except ImportError as exc:
        _cprint(f"[red]❌ 配置模块加载失败：{exc}[/red]")
        sys.exit(1)

    try:
        cfg = load_leaper_config(yaml_path)
    except Exception as exc:
        _cprint(f"[red]❌ 读取 leaper.yaml 失败：{exc}[/red]")
        sys.exit(1)

    agent_name = cfg.get("name", "AI 助手")

    env_vars = config_to_hermes_env(cfg)
    for k, v in env_vars.items():
        os.environ.setdefault(k, v)

    leaper_home = Path(os.environ.get("LEAPER_HOME", str(Path.home() / ".leaper")))
    leaper_home.mkdir(parents=True, exist_ok=True)
    write_hermes_config(cfg, leaper_home)

    # Copy .env and .md files to ~/.leaper/ if not already there
    import shutil
    ws = Path(workspace).resolve()
    env_src = ws / ".env"
    if env_src.exists():
        shutil.copy2(env_src, leaper_home / ".env")
    for md_name in ("EGO.md", "SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md"):
        md_src = ws / md_name
        if md_src.exists():
            shutil.copy2(md_src, leaper_home / md_name)

    channel = cfg.get("channel", {})
    channel_type = channel.get("type", "")

    # 检查 brain Ollama
    brain = cfg.get("brain", {})
    if brain.get("enabled", True) and brain.get("localModel", "auto") == "auto":
        ollama_ok = bool(_detect_ollama())
        if not ollama_ok:
            _cprint(
                "[yellow]⚠ 本地 Ollama 未检测到（http://localhost:11434 无响应）[/yellow]\n"
                "  记忆引擎将使用云端模型（API 消耗略增）。\n"
                "  如需本地模型：1. 安装 Ollama  2. ollama serve  3. ollama pull qwen2.5:7b\n"
            )

    if channel_type and channel_type != "terminal":
        token_env = {
            "telegram": "TELEGRAM_BOT_TOKEN",
            "discord": "DISCORD_BOT_TOKEN",
        }.get(channel_type)
        if token_env and not channel.get("token") and not os.environ.get(token_env, ""):
            _cprint(f"[red]❌ 未设置 {channel_type} Token[/red]")
            _cprint(f"\n请在 leaper.yaml 的 channel.token 或 .env 的 {token_env} 中设置")
            sys.exit(1)

        _cprint(f"[bold green]🚀 {agent_name} 已上线！[/bold green]")
        if channel_type == "telegram":
            _cprint("[dim]📱 打开 Telegram，给你的 Bot 发消息试试[/dim]")
        _cprint("\n[dim]按 Ctrl+C 停止[/dim]\n")

        try:
            import asyncio
            from gateway.run import start_gateway
            asyncio.run(start_gateway())
        except KeyboardInterrupt:
            _cprint(f"\n[dim]{agent_name} 已停止。再见！[/dim]\n")
        except Exception as exc:
            _handle_gateway_error(exc, channel_type)
            sys.exit(1)
    else:
        _cprint(f"[bold green]🚀 {agent_name} 已启动（终端模式）[/bold green]\n")
        _simple_chat_loop(
            provider=cfg.get("model", {}).get("provider", "openai"),
            model=cfg.get("model", {}).get("name", "gpt-4o"),
            api_key=cfg.get("model", {}).get("apiKey", "") or os.environ.get("LEAPER_API_KEY", "") or os.environ.get("OPENAI_API_KEY", ""),
            base_url=cfg.get("model", {}).get("baseUrl", ""),
            agent_name=agent_name,
        )


# ── leaper chat ───────────────────────────────────────────────────────────────

def cmd_chat(workspace: str = ".") -> None:
    """终端对话（零配置：无 leaper.yaml 也能用）"""
    yaml_path = _find_leaper_yaml(workspace)

    if yaml_path is not None:
        _bootstrap_env(workspace)
        from leaper_config import load_leaper_config, config_to_hermes_env
        cfg = load_leaper_config(yaml_path)
        for k, v in config_to_hermes_env(cfg).items():
            os.environ.setdefault(k, v)

        model_cfg = cfg.get("model", {})
        provider = model_cfg.get("provider", "openai")
        model_name = model_cfg.get("name", "gpt-4o")
        api_key = (
            model_cfg.get("apiKey", "")
            or os.environ.get("LEAPER_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
            or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        base_url = model_cfg.get("baseUrl", "")
        agent_name = cfg.get("name", "AI")

        if provider == "ollama":
            base_url = base_url or "http://localhost:11434/v1"
            api_key = api_key or "ollama"

        _simple_chat_loop(provider, model_name, api_key, base_url, agent_name)
        return

    # ── 零配置快速体验模式 ────────────────────────────────────────────────────
    _banner()
    _cprint("[bold]👋 没有检测到配置文件，进入快速体验模式。[/bold]\n")

    ollama_models = _detect_ollama()
    provider = "openai"
    model_name = "gpt-4o"
    api_key = ""
    base_url = ""

    if ollama_models:
        _cprint("[bold]选择模型：[/bold]")
        options = [
            f"Ollama 本地（已检测到 {m['name']} ✅）" for m in ollama_models
        ] + ["输入 OpenAI API Key"]
        choice = _print_menu(options)
        if choice <= len(ollama_models):
            model_name = ollama_models[choice - 1]["name"]
            provider = "ollama"
            base_url = "http://localhost:11434/v1"
            api_key = "ollama"
        else:
            _cprint("\n[bold]OpenAI API Key：[/bold]")
            api_key = _ask("", password=True).strip()
    else:
        _cprint("[bold]选择模型：[/bold]")
        options = ["输入 OpenAI API Key", "输入 Anthropic API Key"]
        choice = _print_menu(options)
        if choice == 1:
            _cprint("\n[bold]OpenAI API Key：[/bold]")
            api_key = _ask("", password=True).strip()
        else:
            _cprint("\n[bold]Anthropic API Key：[/bold]")
            api_key = _ask("", password=True).strip()
            provider = "anthropic"
            model_name = "claude-sonnet-4-6"

    _simple_chat_loop(provider, model_name, api_key, base_url)


def _simple_chat_loop(
    provider: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
    agent_name: str = "AI",
) -> None:
    """简单终端对话循环，支持 OpenAI-compatible API 和 Anthropic。"""
    messages: list[dict[str, str]] = []
    _cprint(f"\n[bold green]🚀 开始对话（输入 /quit 退出）[/bold green]\n")

    while True:
        try:
            user_input = _ask("你").strip()
        except (KeyboardInterrupt, EOFError):
            _cprint("\n[dim]再见！[/dim]\n")
            break

        if not user_input:
            continue
        if user_input in ("/quit", "/exit", "quit", "exit"):
            _cprint("[dim]再见！[/dim]\n")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            reply = _llm_call(provider, model, api_key, base_url, messages)
            messages.append({"role": "assistant", "content": reply})
            _cprint(f"\n[cyan]{agent_name}[/cyan]: {reply}\n")
        except KeyboardInterrupt:
            _cprint("\n[dim]再见！[/dim]\n")
            break
        except Exception as exc:
            _handle_api_error(exc)
            break


def _llm_call(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    messages: list[dict[str, str]],
) -> str:
    if provider == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError("anthropic 包未安装，请运行：pip install anthropic")
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(model=model, max_tokens=2048, messages=messages)  # type: ignore[arg-type]
        return resp.content[0].text  # type: ignore[union-attr]

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai 包未安装，请运行：pip install openai")

    kwargs: dict[str, Any] = {"api_key": api_key or "no-key"}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(model=model, messages=messages)  # type: ignore[arg-type]
    return resp.choices[0].message.content or ""


# ── leaper workshop ───────────────────────────────────────────────────────────

def cmd_workshop() -> None:
    """列出可用模板。"""
    _banner()
    _cprint("[bold]📋 可用模板：[/bold]\n")

    try:
        from leaper_workshop import list_templates
        templates = list_templates()
    except Exception:
        templates = []

    if not templates:
        _cprint("[yellow]暂无可用模板。[/yellow]")
        _cprint("\n本地模板目录为空，且无法连接网络。")
        return

    icons = {"ceo-coach": "🎯", "data-analyst": "📊", "writer": "✍️", "tech-advisor": "💻"}
    for t in templates:
        tname = t.get("name", "")
        icon = t.get("icon", icons.get(tname, "🤖"))
        display = t.get("displayName", tname)
        desc = t.get("description", "")
        src = "[dim](远程)[/dim]" if t.get("source") == "remote" else ""
        _cprint(f"  {icon} [cyan]{tname:<16}[/cyan] {display} — {desc} {src}")

    _cprint(f"\n共 [bold]{len(templates)}[/bold] 个模板。")
    _cprint("使用方法：[cyan]leaper init --template ceo-coach[/cyan]\n")


# ── leaper status ─────────────────────────────────────────────────────────────

def cmd_status(workspace: str = ".") -> None:
    """显示当前配置状态。"""
    _banner()

    yaml_path = _find_leaper_yaml(workspace)
    if yaml_path is None:
        _cprint("[yellow]未找到 leaper.yaml[/yellow]")
        _cprint("运行 [cyan]leaper init[/cyan] 创建配置。")
        return

    from leaper_config import load_leaper_config
    cfg = load_leaper_config(yaml_path)

    model_cfg = cfg.get("model", {})
    channel = cfg.get("channel", {})
    brain = cfg.get("brain", {})

    _cprint(f"  Agent 名称   [bold]{cfg.get('name', '(未设置)')}[/bold]")
    _cprint(f"  模型提供商   {model_cfg.get('provider', 'openai')}")
    _cprint(f"  模型         {model_cfg.get('name', '(未设置)')}")
    _cprint(f"  平台         {channel.get('type', '终端')}")
    _cprint(f"  Brain        {'启用' if brain.get('enabled', True) else '禁用'}")

    db_path = brain.get("dbPath", ".leaper/brain.db")
    db = Path(db_path)
    _cprint(f"  Brain DB     {'[green]已创建[/green]' if db.exists() else '[dim]未创建（首次 run 后生成）[/dim]'}")


# ── Error handling ────────────────────────────────────────────────────────────

def _handle_api_error(exc: Exception) -> None:
    s = str(exc)
    sl = s.lower()
    if "401" in s or ("unauthorized" in sl) or ("invalid" in sl and "key" in sl):
        _cprint("\n[red]❌ API Key 验证失败（401）[/red]")
        _cprint("\n可能原因：")
        _cprint("  1. Key 过期或无效")
        _cprint("  2. baseUrl 与 Key 不匹配")
        _cprint("  3. 账户余额不足")
        _cprint("\n修改：编辑 leaper.yaml 的 model.apiKey，或 .env 中的 LEAPER_API_KEY")
    elif "429" in s or "quota" in sl or ("rate" in sl and "limit" in sl):
        _cprint("\n[red]❌ 请求频率超限或账户余额不足[/red]")
        _cprint("\n请检查账户余额或稍后重试。")
    elif "connect" in sl or "timeout" in sl or "network" in sl or "connection" in sl:
        _cprint("\n[red]❌ 网络连接失败[/red]")
        _cprint("\n可能原因：")
        _cprint("  1. 网络不通")
        _cprint("  2. 需要设置代理：在 leaper.yaml 中添加 proxy: 'http://127.0.0.1:10809'")
    else:
        _cprint(f"\n[red]❌ 请求失败[/red]")
        _cprint(f"  {type(exc).__name__}: {s[:150]}")
        _cprint("\n运行 [cyan]leaper status[/cyan] 检查配置。")


def _handle_gateway_error(exc: Exception, channel_type: str) -> None:
    if channel_type == "telegram":
        _cprint("\n[red]❌ Telegram Bot 连接失败[/red]")
        _cprint("\n可能原因：")
        _cprint("  1. Bot Token 无效（从 @BotFather 重新获取）")
        _cprint("  2. 网络不通（试试在 leaper.yaml 中加 proxy: 'http://127.0.0.1:10809'）")
        _cprint("  3. 另一个进程正在使用同一 Bot Token（关掉其他实例）")
    elif channel_type == "discord":
        _cprint("\n[red]❌ Discord Bot 连接失败[/red]")
        _cprint("\n请检查 Bot Token 是否正确，以及网络连接。")
    else:
        _handle_api_error(exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_leaper_yaml(workspace: str) -> Path | None:
    for candidate in (
        Path(workspace) / "leaper.yaml",
        Path("leaper.yaml"),
        Path.home() / ".leaper" / "leaper.yaml",
    ):
        if candidate.exists():
            return candidate
    return None


def _bootstrap_env(workspace: str) -> None:
    """Load .env from workspace (or cwd), then set LEAPER_HOME defaults."""
    for env_candidate in (Path(workspace) / ".env", Path(".env")):
        if env_candidate.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_candidate)
            except ImportError:
                for line in env_candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())
            break

    leaper_home = os.environ.get("LEAPER_HOME") or str(Path.home() / ".leaper")
    os.environ.setdefault("LEAPER_HOME", leaper_home)
    os.environ.setdefault("HERMES_HOME", leaper_home)


# ── leaper update ────────────────────────────────────────────────────────────

def cmd_update(workspace: str = ".", force: bool = False, dry_run: bool = False) -> None:
    """检查并应用模板 OTA 更新。

    leaper update             — 检查并应用所有可用更新
    leaper update --force     — 强制重新应用（忽略版本号比较）
    leaper update --dry-run   — 只列出可用更新，不实际更新
    """
    _banner()
    _bootstrap_env(workspace)

    try:
        from agent.leaper_template_updater import (
            TemplateUpdater,
            load_agents_from_home,
            DEFAULT_REGISTRY_URL,
        )
    except ImportError as exc:
        _cprint(f"[red]❌ 无法加载更新模块：{exc}[/red]")
        return

    # Read registry_url from global config if set
    registry_url = DEFAULT_REGISTRY_URL
    global_path = Path.home() / ".leaper" / "global.yaml"
    if global_path.exists():
        try:
            import yaml
            gcfg = yaml.safe_load(global_path.read_text(encoding="utf-8")) or {}
            registry_url = gcfg.get("templates", {}).get("registry_url", registry_url)
        except Exception:
            pass

    leaper_home = Path(os.environ.get("LEAPER_HOME", str(Path.home() / ".leaper")))
    updater = TemplateUpdater(registry_url=registry_url, leaper_home=leaper_home)
    agents = load_agents_from_home(leaper_home)

    if not agents:
        _cprint("[yellow]未找到已安装的模板（没有 template.yaml）。[/yellow]")
        _cprint("请先运行 [cyan]leaper init[/cyan] 或 [cyan]leaper create[/cyan]。")
        return

    _cprint(f"[dim]检查 {len(agents)} 个 agent 的模板更新...[/dim]")
    updates = updater.check_for_updates(agents, force=force)

    if not updates:
        _cprint("[green]✓ 所有模板已是最新版本。[/green]")
        return

    _cprint(f"\n[bold]发现 {len(updates)} 个可更新模板：[/bold]")
    for u in updates:
        _cprint(
            f"  [cyan]{u.agent.template_name}[/cyan]  "
            f"[dim]{u.agent.local_version}[/dim] → [green]{u.remote_version}[/green]"
            f"  [dim]({u.agent.agent_id})[/dim]"
        )

    if dry_run:
        _cprint("\n[dim]--dry-run 模式，跳过实际更新。[/dim]")
        return

    _cprint("\n[dim]正在更新...[/dim]")
    updater.apply_updates(updates)
    _cprint(f"\n[green]✅ 已更新 {len(updates)} 个模板。下次对话时自动加载新文件。[/green]\n")


# ── Entry point ───────────────────────────────────────────────────────────────

# ── leaper config ─────────────────────────────────────────────────────────────

def cmd_config(
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    proxy: str = "",
    github_token: str = "",
    show: bool = False,
) -> None:
    """全局配置（API Key、模型、代理），所有 agent 共享。

    leaper config --api-key sk-xxx --base-url http://... --proxy http://127.0.0.1:10809
    leaper config --github-token ghp_xxx  （用于拉取私有模板）
    leaper config --show  查看当前配置
    """
    _banner()
    global_path = Path.home() / ".leaper" / "global.yaml"
    global_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing
    existing: dict[str, Any] = {}
    if global_path.exists():
        try:
            import yaml
            existing = yaml.safe_load(global_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    if show:
        if not existing:
            _cprint("[yellow]尚未配置全局参数。运行 leaper config --api-key ... 进行配置。[/yellow]")
        else:
            _cprint("[bold]当前全局配置：[/bold]")
            for k, v in existing.items():
                display_v = v
                if k == "api_key" and isinstance(v, str) and len(v) > 8:
                    display_v = v[:4] + "..." + v[-4:]
                _cprint(f"  {k}: {display_v}")
        return

    if not any([api_key, base_url, model, proxy, github_token]):
        # Interactive mode
        _cprint("[bold]全局配置（所有 agent 共享）[/bold]\n")
        api_key = _ask("API Key", default=existing.get("api_key", ""), password=True)
        base_url = _ask("Base URL", default=existing.get("base_url", ""))
        model = _ask("默认模型", default=existing.get("model", ""))
        proxy = _ask("代理地址（如 http://127.0.0.1:10809，不需要留空）", default=existing.get("proxy", ""))
        github_token = _ask("GitHub Token（用于拉私有模板，不需要留空）", default=existing.get("github_token", ""), password=True)

    if api_key:
        existing["api_key"] = api_key
    if base_url:
        existing["base_url"] = base_url
    if model:
        existing["model"] = model
    if proxy:
        existing["proxy"] = proxy
    if github_token:
        existing["github_token"] = github_token

    try:
        import yaml
        global_path.write_text(yaml.dump(existing, allow_unicode=True, default_flow_style=False), encoding="utf-8")
        _cprint(f"\n[green]✅ 全局配置已保存到 {global_path}[/green]")
    except ImportError:
        # Fallback without yaml
        lines = [f"{k}: '{v}'" for k, v in existing.items()]
        global_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _cprint(f"\n[green]✅ 全局配置已保存到 {global_path}[/green]")


# ── leaper create ─────────────────────────────────────────────────────────────

def cmd_create(template: str = "", bot_token: str = "", name: str = "") -> None:
    """一条命令创建 agent：leaper create ceo-coach --bot-token xxx

    自动继承全局配置（API Key、模型、代理）。只需指定模板和 bot token。
    """
    _banner()

    # Load global config
    global_path = Path.home() / ".leaper" / "global.yaml"
    global_cfg: dict[str, Any] = {}
    if global_path.exists():
        try:
            import yaml
            global_cfg = yaml.safe_load(global_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    if not global_cfg.get("api_key"):
        _cprint("[red]❌ 请先运行 leaper config 配置全局 API Key[/red]")
        sys.exit(1)

    # Template selection
    if not template:
        _cprint("[bold]选择模板：[/bold]")
        templates_dir = Path(__file__).parent / "templates"
        template_options = []
        if templates_dir.exists():
            for d in sorted(templates_dir.iterdir()):
                if d.is_dir() and (d / "template.yaml").exists():
                    try:
                        import yaml as _yaml
                        meta = _yaml.safe_load((d / "template.yaml").read_text(encoding="utf-8"))
                        display = meta.get("displayName", d.name)
                        desc = meta.get("description", "")
                        template_options.append((d.name, f"{display} — {desc}" if desc else display))
                    except Exception:
                        template_options.append((d.name, d.name))

        if not template_options:
            _cprint("[red]❌ 未找到模板。请检查 templates/ 目录。[/red]")
            sys.exit(1)

        menu_items = [opt[1] for opt in template_options]
        choice = _print_menu(menu_items)
        template = template_options[choice - 1][0]

    # Agent name from template
    if not name:
        try:
            import yaml as _yaml
            tmpl_yaml = Path(__file__).parent / "templates" / template / "template.yaml"
            if tmpl_yaml.exists():
                meta = _yaml.safe_load(tmpl_yaml.read_text(encoding="utf-8"))
                name = meta.get("displayName", meta.get("name", template))
        except Exception:
            name = template

    # Bot token
    if not bot_token:
        _cprint("\n[bold]Telegram Bot Token（从 @BotFather 获取）：[/bold]")
        bot_token = _ask("").strip()

    # Create agent directory
    agents_dir = Path.home() / ".leaper" / "agents" / template
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Copy template .md files and template.yaml
    import shutil
    tmpl_dir = Path(__file__).parent / "templates" / template
    if tmpl_dir.exists():
        copied = []
        for f in tmpl_dir.iterdir():
            if f.suffix == ".md" or f.name == "template.yaml":
                shutil.copy2(f, agents_dir / f.name)
                copied.append(f.name)
        if copied:
            _cprint(f"[dim]模板文件：{', '.join(copied)}[/dim]")

    # Generate leaper.yaml
    provider = "custom" if global_cfg.get("base_url") else "openai"
    model_name = global_cfg.get("model", "gpt-4o")
    api_key = global_cfg.get("api_key", "")
    base_url = global_cfg.get("base_url", "")
    proxy = global_cfg.get("proxy", "")

    _write_leaper_yaml(agents_dir, name, provider, model_name, api_key, base_url, "telegram", bot_token)
    _write_dotenv(agents_dir, provider, api_key, "telegram", bot_token)

    # Add proxy to .env if set
    if proxy:
        with open(agents_dir / ".env", "a", encoding="utf-8") as f:
            f.write(f"\nHTTPS_PROXY={proxy}\nHTTP_PROXY={proxy}\nALL_PROXY={proxy}\n")

    _cprint(f"\n[green]✅ Agent [{name}] 创建成功！[/green]")
    _cprint(f"   目录：{agents_dir}")
    _cprint(f"\n[bold]启动：[/bold]")
    _cprint(f"  [cyan]leaper run --workspace {agents_dir}[/cyan]\n")


# ── leaper init-team ──────────────────────────────────────────────────────────

def cmd_init_team(
    output: str = "",
    model: str = "",
    platform: str = "telegram",
) -> None:
    """交互式向导 — 生成多 Agent config.yaml（每个 Agent 独立 bot token）。

    运行后将在 ~/.leaper/config.yaml（或 --output 指定路径）写入
    包含 agents 列表的多 Agent 配置，可直接用 leaper run 启动。

    Args:
        output:   输出路径（默认 ~/.leaper/config.yaml）。
        model:    默认模型名称（所有 Agent 共用，单个 Agent 可在配置中覆盖）。
        platform: 平台类型，目前仅支持 telegram（默认）。
    """
    import shutil as _shutil
    import yaml as _yaml

    _banner()
    _cprint("[bold cyan]🚀 Leaper 多 Agent 团队向导[/bold cyan]\n")
    _cprint("本向导帮助你为每个 Agent 角色配置独立的 Telegram Bot Token。\n")

    leaper_home = Path.home() / ".leaper"
    leaper_home.mkdir(parents=True, exist_ok=True)

    # ── 选择/确认全局模型 ──────────────────────────────────────────────────────
    if not model:
        # Try to read from existing global config
        global_cfg = {}
        try:
            cfg_path = leaper_home / "config.yaml"
            if cfg_path.exists():
                global_cfg = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
        default_model = global_cfg.get("model", "claude-opus-4-7")
        _cprint("[bold]全局默认模型（每个 Agent 可单独覆盖）：[/bold]")
        model = _ask("模型名称", default=str(default_model)).strip() or str(default_model)

    # ── 收集 Agent 列表 ────────────────────────────────────────────────────────
    agents: list[dict] = []
    _cprint("\n[bold]添加 Agent（输入空行结束）：[/bold]\n")

    while True:
        idx = len(agents) + 1
        _cprint(f"  [bold]Agent #{idx}[/bold]")
        agent_id = _ask("  角色 ID（如 cfo / cto / sales）").strip().lower()
        if not agent_id:
            if agents:
                break
            _cprint("[yellow]至少需要一个 Agent，请继续。[/yellow]")
            continue
        # Sanitise: only alphanumeric and hyphens
        agent_id = "".join(c if c.isalnum() or c == "-" else "_" for c in agent_id)

        agent_model = _ask(f"  模型（留空=使用全局 {model}）").strip()

        bot_token = _ask(f"  Telegram Bot Token（@BotFather 获取）").strip()
        if not bot_token:
            _cprint("[yellow]  Token 为空，已跳过该 Agent。[/yellow]\n")
            continue

        workspace = str(leaper_home / "agents" / agent_id)
        brain_db = str(leaper_home / "agents" / agent_id / "brain.db")

        entry: dict = {
            "id": agent_id,
            "workspace": workspace,
            "brain_db": brain_db,
            "platforms": {
                platform: {"token": bot_token},
            },
        }
        if agent_model:
            entry["model"] = agent_model

        agents.append(entry)

        # Create workspace directory and copy template files if available
        ws_path = Path(workspace)
        ws_path.mkdir(parents=True, exist_ok=True)
        tmpl_dir = Path(__file__).parent / "templates" / agent_id
        if tmpl_dir.exists():
            for f in tmpl_dir.iterdir():
                if f.suffix == ".md" or f.name == "template.yaml":
                    _shutil.copy2(f, ws_path / f.name)

        _cprint(f"  [green]✓ Agent [{agent_id}] 已添加[/green]\n")

        _cprint("  继续添加下一个 Agent？（直接回车 = 结束）")

    if not agents:
        _cprint("[yellow]未添加任何 Agent，已退出。[/yellow]")
        return

    # ── 写出 config.yaml ───────────────────────────────────────────────────────
    config_path = Path(output) if output else leaper_home / "config.yaml"

    # Merge into existing config if present (preserve non-agent keys)
    existing: dict = {}
    if config_path.exists():
        try:
            existing = _yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    existing["model"] = model
    existing["agents"] = agents
    # Remove any legacy top-level platforms block to avoid confusion
    existing.pop("platforms", None)

    config_path.write_text(
        _yaml.dump(existing, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    _cprint(f"\n[green]✅ 多 Agent 配置已写入：{config_path}[/green]")
    _cprint(f"\n[bold]启动所有 Agent：[/bold]")
    _cprint(f"  [cyan]leaper run[/cyan]\n")
    _cprint(f"[dim]每个 Agent 的工作区：{leaper_home / 'agents' / '<agent-id>'}[/dim]\n")


# ── leaper list ───────────────────────────────────────────────────────────────

def cmd_list() -> None:
    """列出所有已创建的 agent"""
    _banner()
    agents_dir = Path.home() / ".leaper" / "agents"
    if not agents_dir.exists():
        _cprint("[yellow]尚未创建任何 agent。运行 leaper create 创建。[/yellow]")
        return

    _cprint("[bold]已创建的 Agent：[/bold]\n")
    for d in sorted(agents_dir.iterdir()):
        if d.is_dir() and (d / "leaper.yaml").exists():
            try:
                import yaml
                cfg = yaml.safe_load((d / "leaper.yaml").read_text(encoding="utf-8"))
                name = cfg.get("name", d.name)
                _cprint(f"  📦 [bold]{name}[/bold] ({d.name})")
                _cprint(f"     [dim]{d}[/dim]")
            except Exception:
                _cprint(f"  📦 {d.name}")


def main() -> None:
    try:
        import fire
        fire.Fire(
            {
                "init": cmd_init,
                "init-team": cmd_init_team,
                "run": cmd_run,
                "chat": cmd_chat,
                "config": cmd_config,
                "create": cmd_create,
                "list": cmd_list,
                "workshop": cmd_workshop,
                "status": cmd_status,
                "update": cmd_update,
            }
        )
    except KeyboardInterrupt:
        _cprint("\n[dim]已取消。[/dim]\n")
    except SystemExit:
        raise
    except Exception as exc:
        _cprint(f"\n[red]❌ 出错了：{type(exc).__name__}: {str(exc)[:200]}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
