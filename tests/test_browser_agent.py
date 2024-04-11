from urllib.parse import parse_qs, urlsplit

from browser_agent_a11y.agent import BrowserAgent, Intent, ScriptedPolicy
from browser_agent_a11y.browser import LocalBrowser, LocalWebsite
from browser_agent_a11y.grounding import AgentAction, ground_action

HOME = """
<title>Local docs</title><main><h1>Documentation</h1>
<p>This paragraph makes the original HTML substantially larger than its compressed tree.
It contains no actions and can safely be omitted by an agent focused on the current goal.</p>
<form action="/search"><label for="query">Query</label><input id="query" name="q">
<button type="submit">Search</button></form></main>
"""


def search_route(url: str) -> str:
    query = parse_qs(urlsplit(url).query).get("q", [""])[0]
    return f"""
    <title>Results</title><main><h1>Results for {query}</h1>
    <a href="/docs/grounding">Grounding guide</a><a href="/docs/other">Other guide</a>
    </main>
    """


DOCS = "<title>Guide</title><main><h1>Set-of-marks grounding</h1><p>Local success.</p></main>"


def make_browser() -> LocalBrowser:
    return LocalBrowser(
        LocalWebsite({"/": HOME, "/search": search_route, "/docs/grounding": DOCS})
    )


def test_typing_and_form_submission_grounded_by_marks() -> None:
    browser = make_browser()
    initial = browser.observe()
    query_id = initial.node_for_mark(initial.mark_for_name("Query")).element_id
    typed = browser.execute(
        ground_action(
            AgentAction(
                "type", initial.mark_for_name("Query"), initial.observation_id, text="grounding"
            ),
            initial,
        )
    )
    assert typed.node_for_mark(typed.mark_for_name("Query")).value == "grounding"
    assert typed.node_for_mark(typed.mark_for_name("Query")).element_id == query_id
    results = browser.execute(
        ground_action(
            AgentAction("click", typed.mark_for_name("Search"), typed.observation_id), typed
        )
    )
    assert browser.current_url == "http://local.test/search?q=grounding"
    assert "Results for grounding" in results.compressed_tree
    docs = browser.execute(
        ground_action(
            AgentAction(
                "click", results.mark_for_name("Grounding guide"), results.observation_id
            ),
            results,
        )
    )
    assert docs.url == "http://local.test/docs/grounding"
    assert "Set-of-marks grounding" in docs.compressed_tree


def test_scripted_agent_completes_deterministic_local_task() -> None:
    browser = make_browser()
    policy = ScriptedPolicy(
        [
            Intent("type", "Query", text="grounding"),
            Intent("click", "Search"),
            Intent("click", "Grounding guide"),
            Intent("finish"),
        ]
    )
    run = BrowserAgent(browser).run(policy, lambda state: state.current_url.endswith("grounding"))
    assert run.success, run.error
    assert [step.action for step in run.steps] == ["type", "click", "click", "finish"]
    assert run.tokens_per_step > 0
    assert run.tokens_per_step < sum(step.full_html_tokens for step in run.steps) / len(run.steps)


def test_checkbox_select_and_get_form_state() -> None:
    page = """
    <form action="/saved"><label><input type="checkbox" name="subscribe">Subscribe</label>
    <label for="theme">Theme</label><select id="theme" name="theme">
    <option value="light">Light</option><option value="dark">Dark</option></select>
    <button>Save preferences</button></form>
    """
    browser = LocalBrowser(LocalWebsite({"/": page, "/saved": "<h1>Saved</h1>"}))
    policy = ScriptedPolicy(
        [
            Intent("click", "Subscribe"),
            Intent("select", "Theme", value="dark"),
            Intent("click", "Save preferences"),
            Intent("finish"),
        ]
    )
    run = BrowserAgent(browser).run(
        policy, lambda state: state.current_url.startswith("http://local.test/saved?")
    )
    assert run.success, run.error
    query = parse_qs(urlsplit(browser.current_url).query)
    assert query == {"subscribe": ["on"], "theme": ["dark"]}
