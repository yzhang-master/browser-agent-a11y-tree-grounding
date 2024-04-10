from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .browser import LocalBrowser
from .grounding import AgentAction, GroundingError, ground_action
from .observation import Observation


def estimate_tokens(text: str) -> int:
    return len(re.findall(r"[\w]+|[^\w\s]", text, flags=re.UNICODE))


@dataclass(frozen=True)
class Intent:
    kind: str
    name: str = ""
    text: str = ""
    value: str = ""


class ScriptedPolicy:
    """Turns semantic intents into actions addressed by current screenshot marks."""

    def __init__(self, intents: list[Intent]) -> None:
        self.intents = intents
        self.index = 0

    def act(self, observation: Observation) -> AgentAction:
        if self.index >= len(self.intents):
            return AgentAction("finish", observation_id=observation.observation_id)
        intent = self.intents[self.index]
        self.index += 1
        if intent.kind in {"finish", "go_back"}:
            return AgentAction(intent.kind, observation_id=observation.observation_id)
        mark = observation.mark_for_name(intent.name)
        return AgentAction(
            intent.kind,
            mark,
            observation.observation_id,
            intent.text,
            intent.value,
        )


class Policy(Protocol):
    def act(self, observation: Observation) -> AgentAction: ...


@dataclass
class StepRecord:
    action: str
    url: str
    compressed_tokens: int
    full_html_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "url": self.url,
            "compressed_tokens": self.compressed_tokens,
            "full_html_tokens": self.full_html_tokens,
        }


@dataclass
class AgentRun:
    success: bool
    steps: list[StepRecord] = field(default_factory=list)
    final_url: str = ""
    error: str = ""
    wall_seconds: float = 0.0

    @property
    def tokens_per_step(self) -> float:
        if not self.steps:
            return 0.0
        return sum(step.compressed_tokens for step in self.steps) / len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "steps": [step.to_dict() for step in self.steps],
            "final_url": self.final_url,
            "error": self.error,
            "wall_seconds": self.wall_seconds,
            "tokens_per_step": self.tokens_per_step,
        }


class BrowserAgent:
    def __init__(self, browser: LocalBrowser) -> None:
        self.browser = browser

    def run(
        self,
        policy: Policy,
        goal: Callable[[LocalBrowser], bool],
        *,
        max_steps: int = 12,
    ) -> AgentRun:
        started = time.perf_counter()
        run = AgentRun(False)
        observation = self.browser.observe()
        for _ in range(max_steps):
            try:
                action = policy.act(observation)
                grounded = ground_action(action, observation)
            except (GroundingError, KeyError, ValueError) as error:
                run.error = str(error)
                break
            run.steps.append(
                StepRecord(
                    action.kind,
                    self.browser.current_url,
                    estimate_tokens(observation.compressed_tree),
                    estimate_tokens(self.browser.document.source),
                )
            )
            observation = self.browser.execute(grounded)
            if action.kind == "finish":
                run.success = goal(self.browser)
                if not run.success:
                    run.error = "policy finished without satisfying the goal"
                break
        else:
            run.error = "maximum steps exhausted"
        run.final_url = self.browser.current_url
        run.wall_seconds = time.perf_counter() - started
        return run
