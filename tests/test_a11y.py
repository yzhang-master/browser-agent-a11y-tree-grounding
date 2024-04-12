import xml.etree.ElementTree as ET

from browser_agent_a11y.a11y import build_accessibility_tree, compress_tree, walk_tree
from browser_agent_a11y.html import parse_html
from browser_agent_a11y.observation import observe_document

SOURCE = """
<html><head><title>Search &amp; discovery</title><style>button { color: red }</style></head>
<body><main aria-label="Documentation search">
<h1>Local documentation</h1><p>A long explanatory paragraph with searchable text.</p>
<form action="/search"><label for="query">Search query</label>
<input id="query" name="q" placeholder="ignored when labelled">
<button type="submit">Search</button><button hidden>Hidden action</button></form>
<a href="/help" aria-label="Help & support">help</a>
<input type="checkbox" aria-label="Remember me" checked>
</main></body></html>
"""


def observation(source: str = SOURCE):
    return observe_document(
        parse_html(source), url="http://local.test/", observation_id="1:/"
    )


def test_real_html_to_accessibility_tree_with_names_and_hidden_filtering() -> None:
    tree = build_accessibility_tree(parse_html(SOURCE))
    nodes = walk_tree(tree)
    by_role = {}
    for node in nodes:
        by_role.setdefault(node.role, []).append(node)
    assert by_role["heading"][0].name == "Local documentation"
    assert by_role["textbox"][0].name == "Search query"
    assert by_role["button"][0].name == "Search"
    assert by_role["link"][0].name == "Help & support"
    assert by_role["checkbox"][0].checked is True
    assert all(node.name != "Hidden action" for node in nodes)
    assert all(node.role != "generic" for node in nodes)


def test_stable_element_ids_across_parse_and_unrelated_content_change() -> None:
    first = observation()
    second = observation()
    third = observation(SOURCE.replace("<h1>", "<p>New static note</p><h1>"))
    for name in ("Search query", "Search", "Help & support"):
        first_id = first.node_for_mark(first.mark_for_name(name)).element_id
        second_id = second.node_for_mark(second.mark_for_name(name)).element_id
        third_id = third.node_for_mark(third.mark_for_name(name)).element_id
        assert first_id == second_id == third_id
        assert first_id.startswith("e-")


def test_compression_is_bounded_and_preserves_actionable_marks() -> None:
    obs = observation()
    compressed = compress_tree(obs.tree, marks=obs.marks, max_nodes=6, max_chars=500)
    assert len(compressed) <= 500
    assert "nodes omitted" in compressed
    assert "document" in compressed
    tiny = compress_tree(obs.tree, marks=obs.marks, max_chars=100)
    assert len(tiny) <= 100
    assert "characters omitted" in tiny
    assert compress_tree(obs.tree, max_chars=1) == "…"


def test_set_of_marks_is_actual_valid_svg_with_grounding_metadata() -> None:
    obs = observation()
    root = ET.fromstring(obs.svg)
    assert root.tag.endswith("svg")
    groups = [element for element in root.iter() if "data-mark" in element.attrib]
    assert len(groups) == len(obs.marks) == 4
    assert {element.attrib["data-element-id"] for element in groups} == set(obs.marks)
    assert "<script" not in obs.svg
    assert "Search &amp; discovery" in obs.svg


def test_svg_contains_every_available_mark_beyond_first_screen() -> None:
    source = "".join(f'<button id="b{index}">Button {index}</button>' for index in range(45))
    obs = observation(source)
    root = ET.fromstring(obs.svg)
    groups = [element for element in root.iter() if "data-mark" in element.attrib]
    assert len(obs.marks) == len(groups) == 45
