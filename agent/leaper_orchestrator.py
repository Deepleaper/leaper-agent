"""
LeaperOrchestrator - Main orchestrator tying all Leaper subsystems together.
Does NOT call the LLM directly; provides context and processes results.
"""

from __future__ import annotations

import os
from typing import Any

from .leaper_brain import LeaperBrain
from .leaper_evolution import LeaperEvolution
from .leaper_profile import LeaperProfile
from .leaper_meta import LeaperMeta
from .leaper_prompt_builder import LeaperPromptBuilder
from .leaper_queue_manager import LeaperQueueManager
from .leaper_session_manager import LeaperSessionManager


class LeaperOrchestrator:
    """
    Main orchestrator for the Leaper agent system.

    Responsibilities:
    - Initialize all subsystems (brain, evolution, profile, meta, prompt, queue, session)
    - Handle incoming messages: build context + prompt for external LLM
    - Process responses: store, extract knowledge, trigger evolution
    - Does NOT call the LLM (that's Hermes's job)
    """

    def __init__(self, agent_id: str, db_path: str, workspace_dir: str) -> None:
        self.agent_id = agent_id
        self.db_path = db_path
        self.workspace_dir = workspace_dir

        # Subsystems (initialized in initialize())
        self.brain: LeaperBrain | None = None
        self.evolution: LeaperEvolution | None = None
        self.profile: LeaperProfile | None = None
        self.meta: LeaperMeta | None = None
        self.prompt_builder: LeaperPromptBuilder | None = None
        self.queue: LeaperQueueManager | None = None
        self.session_manager: LeaperSessionManager | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Create and initialize all subsystems."""
        if self._initialized:
            return

        # Ensure workspace exists
        os.makedirs(self.workspace_dir, exist_ok=True)

        # Core brain
        self.brain = LeaperBrain(db_path=self.db_path, agent_id=self.agent_id)
        await self.brain.initialize()

        # Knowledge evolution
        self.evolution = LeaperEvolution(brain=self.brain)

        # Profile system
        self.profile = LeaperProfile(brain=self.brain)

        # Meta/health assessment
        self.meta = LeaperMeta(brain=self.brain)

        # Prompt builder
        self.prompt_builder = LeaperPromptBuilder(
            workspace_dir=self.workspace_dir,
            brain=self.brain,
        )

        # Message queue
        self.queue = LeaperQueueManager()

        # Session manager
        sessions_dir = os.path.join(os.path.dirname(self.db_path), "sessions")
        self.session_manager = LeaperSessionManager(sessions_dir=sessions_dir)

        self._initialized = True

    def _check_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("Orchestrator not initialized. Call initialize() first.")

    async def handle_message(self, session_id: str, user_message: str) -> str:
        """
        Full agent loop for an incoming message.

        Flow: queue → recall → prompt → return prompt string.
        The actual LLM call is external (Hermes). This returns the assembled prompt/context.
        """
        self._check_initialized()

        # 1. Enqueue message
        await self.queue.enqueue(session_id=session_id, message=user_message)

        # 2. Recall relevant knowledge
        recalled = await self.brain.recall(query=user_message, limit=5)

        # 3. Build prompt with context
        prompt = await self.prompt_builder.build(query=user_message, session_id=session_id)

        # 4. Append recalled memories to prompt
        if recalled:
            memory_block = "\n\n## 相关记忆\n"
            for entry in recalled:
                memory_block += f"- [{entry.get('category', 'general')}] {entry['content'][:200]}\n"
            prompt += memory_block

        return prompt

    async def on_response(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """
        Post-response processing: store messages and trigger knowledge extraction.
        """
        self._check_initialized()

        # Store messages
        await self.brain.store_message(session_id=session_id, role="user", content=user_msg)
        await self.brain.store_message(session_id=session_id, role="assistant", content=assistant_msg)

        # Extract knowledge from the exchange
        conversation = [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ]
        await self.brain.extract_knowledge(conversation)

    async def on_session_end(self, session_id: str) -> None:
        """
        Trigger evolution when a session ends.
        """
        self._check_initialized()

        # Run full evolution cycle
        await self.evolution.run_full_evolution()

        # Update profile from new entries
        await self.profile.infer_from_entries(agent_id=self.agent_id)

    async def shutdown(self) -> None:
        """Gracefully shut down all subsystems."""
        if self.brain:
            await self.brain.close()

        self._initialized = False
        self.brain = None
        self.evolution = None
        self.profile = None
        self.meta = None
        self.prompt_builder = None
        self.queue = None
        self.session_manager = None
