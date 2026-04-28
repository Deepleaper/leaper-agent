"""DeepBrain Memory Provider plugin."""
from plugins.memory.deepbrain.provider import DeepBrainMemoryProvider

__all__ = ["DeepBrainMemoryProvider"]


def register(ctx):
    """Register the DeepBrain memory provider with the agent runtime."""
    ctx.register_memory_provider(DeepBrainMemoryProvider())
