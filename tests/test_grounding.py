import pytest

from browser_agent_a11y.grounding import AgentAction, GroundingError, ground_action
from browser_agent_a11y.html import parse_html
from browser_agent_a11y.observation import observe_document


def make_observation():
    return observe_document(
        parse_html(
            '<label for="q">Query</label><input id="q">'
            '<button>Go</button><a href="/next">Next page</a>'
            '<button disabled>Disabled</button>'
        ),
        url="http://local.test/",
        observation_id="7:/",
    )


def test_action_grounding_resolves_mark_to_stable_element() -> None:
    obs = make_observation()
    mark = obs.mark_for_name("Go")
    action = AgentAction("click", mark, "7:/")
    grounded = ground_action(action, obs)
    assert grounded.node.role == "button"
    assert grounded.node.name == "Go"
    assert grounded.node.element_id in obs.marks


def test_grounding_rejects_stale_unknown_and_wrong_role_actions() -> None:
    obs = make_observation()
    with pytest.raises(GroundingError, match="stale"):
        ground_action(AgentAction("click", obs.mark_for_name("Go"), "6:/"), obs)
    with pytest.raises(GroundingError, match="unknown mark"):
        ground_action(AgentAction("click", "999", "7:/"), obs)
    with pytest.raises(GroundingError, match="cannot type a button"):
        ground_action(
            AgentAction("type", obs.mark_for_name("Go"), "7:/", text="hello"), obs
        )
    with pytest.raises(GroundingError, match="unknown mark"):
        ground_action(AgentAction("click", "4", "7:/"), obs)


def test_json_action_schema_is_checked() -> None:
    action = AgentAction.from_json(
        '{"kind":"type","mark":"1","observation_id":"7:/","text":"abc"}'
    )
    assert action.text == "abc"
    with pytest.raises(GroundingError):
        AgentAction.from_json('{"kind":"click","mark":1}')
    with pytest.raises(GroundingError):
        ground_action(AgentAction("delete", "1", "7:/"), make_observation())
