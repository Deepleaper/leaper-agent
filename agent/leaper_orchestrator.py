"""Leaper Orchestrator — counter-based and timer-based evolution trigger.

Triggering rules:
  Every turn   → L1 (experience_extract + store)
  Every 5 L1s  → L2 (skill_generate)
  Every 3 L1s  → L4 (user_model_update)
  Every 24h    → L3 (skill_evolve) + L5 (validate)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.leaper_brain import LeaperBrain
    from agent.leaper_evolution import EvolutionEngine

logger = logging.getLogger(__name__)

_L2_EVERY_N_L1 = 5
_L4_EVERY_N_L1 = 3
_CRON_MIN_INTERVAL_S = 86400  # 24 h


class LeaperOrchestrator:
    """Coordinates evolution layer invocations based on turn counts and timers."""

    def __init__(self, brain: "LeaperBrain", evolution: "EvolutionEngine") -> None:
        self.brain = brain
        self.evolution = evolution
        self._lock = threading.Lock()
        self._turn_count: int = 0
        # Start at -1 so the first increment produces 0, preventing a modulo-0
        # false trigger on the very first turn if the > 0 guard is ever removed.
        self._l1_count: int = -1
        self._last_cron_ts: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def on_turn_complete(
        self, user_content: str, assistant_content: str
    ) -> dict[str, Any]:
        """Called after each conversation turn.

        Increments turn counter synchronously, then dispatches all LLM-calling
        work (L1/L2/L4) to a background thread so the caller is never blocked.
        Returns {} immediately; results are logged inside the background thread.
        """
        with self._lock:
            self._turn_count += 1

        # Run L1 extraction and downstream L2/L4 in a background thread to
        # avoid blocking the caller with synchronous LLM calls.
        def _run_evolution() -> None:
            l1_stored = False
            try:
                exp = self.evolution.experience_extract(user_content, assistant_content)
                exp_id = self.evolution.store_experience(exp)
                l1_stored = bool(exp_id)
                logger.info(
                    "Orchestrator L1: stored=%s complexity=%s success=%s",
                    l1_stored, exp.get("complexity"), exp.get("task_success"),
                )
            except Exception as e:
                logger.warning("Orchestrator L1 error: %s", e)

            with self._lock:
                if l1_stored:
                    self._l1_count += 1
                l1_count = self._l1_count

            # ── L2 every 5 L1s ────────────────────────────────────────────────
            if l1_count > 0 and l1_count % _L2_EVERY_N_L1 == 0:
                try:
                    skills = self.evolution.skill_generate()
                    logger.info("Orchestrator L2: generated %d skills", len(skills))
                except Exception as e:
                    logger.warning("Orchestrator L2 error: %s", e)

            # ── L4 every 3 L1s ────────────────────────────────────────────────
            if l1_count > 0 and l1_count % _L4_EVERY_N_L1 == 0:
                try:
                    profile = self.evolution.user_model_update()
                    logger.info(
                        "Orchestrator L4: user model updated (expertise=%s)",
                        profile.get("expertise_level"),
                    )
                except Exception as e:
                    logger.warning("Orchestrator L4 error: %s", e)

        threading.Thread(target=_run_evolution, daemon=True).start()
        return {}

    def on_cron(self) -> dict[str, Any]:
        """Called by a scheduler (e.g., CronCreate). Runs L3 + L5 if 24h have passed."""
        now = time.time()
        with self._lock:
            elapsed = now - self._last_cron_ts
            if elapsed < _CRON_MIN_INTERVAL_S:
                hours_left = (_CRON_MIN_INTERVAL_S - elapsed) / 3600
                logger.debug("Orchestrator cron: skipped (%.1fh remaining)", hours_left)
                return {"skipped": True, "hours_until_next": round(hours_left, 1)}
            self._last_cron_ts = now

        results: dict[str, Any] = {}

        # ── L3 ────────────────────────────────────────────────────────────────
        try:
            l3_result = self.evolution.skill_evolve()
            results["l3"] = l3_result
            logger.info("Orchestrator L3: %s", l3_result)
        except Exception as e:
            logger.warning("Orchestrator L3 error: %s", e)
            results["l3"] = {"error": str(e)}

        # ── L5 ────────────────────────────────────────────────────────────────
        try:
            l5_result = self.evolution.validate()
            results["l5"] = l5_result
            logger.info("Orchestrator L5: %s", l5_result)
        except Exception as e:
            logger.warning("Orchestrator L5 error: %s", e)
            results["l5"] = {"error": str(e)}

        return results

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            # max(0, ...) guards against the -1 sentinel initial value producing
            # a misleading "1 L1 until L2" display before any L1 is stored.
            effective = max(0, self._l1_count)
            return {
                "turn_count": self._turn_count,
                "l1_count": self._l1_count,
                "last_cron_ts": self._last_cron_ts,
                "next_l2_in": _L2_EVERY_N_L1 - (effective % _L2_EVERY_N_L1),
                "next_l4_in": _L4_EVERY_N_L1 - (effective % _L4_EVERY_N_L1),
            }
