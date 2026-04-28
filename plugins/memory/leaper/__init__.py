"""Leaper Memory Provider plugin."""
from plugins.memory.leaper.provider import LeaperMemoryProvider

__all__ = ["LeaperMemoryProvider"]


def register(ctx):
    """Register the Leaper memory provider with the agent runtime."""
    ctx.register_memory_provider(LeaperMemoryProvider())
