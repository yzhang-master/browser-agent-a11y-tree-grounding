from __future__ import annotations

import json
from dataclasses import dataclass

from .a11y import AccessibilityNode
from .observation import Observation


class GroundingError(ValueError):
    pass


@dataclass(frozen=True)
class AgentAction:
    kind: str
    mark: str = ""
    observation_id: str = ""
    text: str = ""
    value: str = ""

    @classmethod
    def from_json(cls, source: str) -> AgentAction:
        payload = json.loads(source)
        if not isinstance(payload, dict) or not isinstance(payload.get("kind"), str):
            raise GroundingError("action must be an object with a string kind")
        fields = {key: payload.get(key, "") for key in ("mark", "observation_id", "text", "value")}
        if not all(isinstance(value, str) for value in fields.values()):
            raise GroundingError("action fields must be strings")
        return cls(payload["kind"], **fields)


@dataclass(frozen=True)
class GroundedAction:
    action: AgentAction
    node: AccessibilityNode | None


def ground_action(action: AgentAction, observation: Observation) -> GroundedAction:
    if action.observation_id != observation.observation_id:
        raise GroundingError("stale or missing observation id")
    if action.kind in {"finish", "go_back"}:
        return GroundedAction(action, None)
    node = observation.node_for_mark(action.mark)
    if node is None:
        raise GroundingError(f"unknown mark: {action.mark!r}")
    if not node.interactive:
        raise GroundingError(f"mark {action.mark} is not actionable")
    supported = {
        "click": {"link", "button", "checkbox", "radio"},
        "type": {"textbox"},
        "select": {"combobox"},
    }
    if action.kind not in supported:
        raise GroundingError(f"unsupported action: {action.kind}")
    if node.role not in supported[action.kind]:
        raise GroundingError(f"cannot {action.kind} a {node.role}")
    if action.kind == "type" and not action.text:
        raise GroundingError("type action requires non-empty text")
    if action.kind == "select" and not action.value:
        raise GroundingError("select action requires a value")
    return GroundedAction(action, node)
