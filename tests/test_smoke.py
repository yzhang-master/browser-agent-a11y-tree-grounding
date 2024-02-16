from browser_agent_a11y import parse_html


def test_html_smoke() -> None:
    document = parse_html("<main><button>Save</button></main>")
    assert document.find_all("button")[0].text == "Save"
