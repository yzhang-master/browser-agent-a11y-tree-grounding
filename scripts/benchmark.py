from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from browser_agent_a11y.agent import BrowserAgent, Intent, ScriptedPolicy
from browser_agent_a11y.browser import LocalBrowser, LocalWebsite


@dataclass(frozen=True)
class WebTask:
    name: str
    browser: LocalBrowser
    intents: list[Intent]


def docs_site() -> LocalWebsite:
    home = """
    <title>Local documentation</title><main><h1>Documentation</h1>
    <p>Static introductory text adds raw HTML tokens but no action needed for the task.
    The accessibility representation retains headings and actionable controls.</p>
    <form action="/search"><label for="query">Query</label><input id="query" name="q">
    <button type="submit">Search</button></form><a href="/about">About this site</a></main>
    """

    def search(url: str) -> str:
        query = parse_qs(urlsplit(url).query).get("q", [""])[0]
        return f"""
        <title>Search results</title><main><h1>Results for {query}</h1>
        <p>Only local, deterministic documents are indexed.</p>
        <a href="/docs/grounding">Grounding guide</a>
        <a href="/docs/accessibility">Accessibility guide</a></main>
        """

    return LocalWebsite(
        {
            "/": home,
            "/search": search,
            "/docs/grounding": "<title>Grounding</title><main><h1>Grounding complete</h1></main>",
            "/docs/accessibility": (
                "<title>A11y</title><main><h1>Accessibility complete</h1></main>"
            ),
            "/about": "<title>About</title><main><h1>Local only</h1></main>",
        }
    )


def preference_browser() -> LocalBrowser:
    page = """
    <title>Preferences</title><main><h1>Local preferences</h1>
    <form action="/saved"><label><input type="checkbox" name="subscribe">Subscribe</label>
    <label for="theme">Theme</label><select id="theme" name="theme">
    <option value="light">Light</option><option value="dark">Dark</option></select>
    <button>Save preferences</button></form></main>
    """
    return LocalBrowser(LocalWebsite({"/": page, "/saved": "<h1>Saved</h1>"}))


def tasks() -> list[WebTask]:
    return [
        WebTask(
            "grounding-search",
            LocalBrowser(docs_site()),
            [
                Intent("type", "Query", text="grounding"),
                Intent("click", "Search"),
                Intent("click", "Grounding guide"),
                Intent("finish"),
            ],
        ),
        WebTask(
            "accessibility-search",
            LocalBrowser(docs_site()),
            [
                Intent("type", "Query", text="accessibility"),
                Intent("click", "Search"),
                Intent("click", "Accessibility guide"),
                Intent("finish"),
            ],
        ),
        WebTask(
            "about-navigation",
            LocalBrowser(docs_site()),
            [Intent("click", "About this site"), Intent("finish")],
        ),
        WebTask(
            "preferences-form",
            preference_browser(),
            [
                Intent("click", "Subscribe"),
                Intent("select", "Theme", value="dark"),
                Intent("click", "Save preferences"),
                Intent("finish"),
            ],
        ),
    ]


def goal(task: WebTask) -> bool:
    browser = task.browser
    if task.name == "grounding-search":
        return browser.current_url == "http://local.test/docs/grounding"
    if task.name == "accessibility-search":
        return browser.current_url == "http://local.test/docs/accessibility"
    if task.name == "about-navigation":
        return browser.current_url == "http://local.test/about"
    query = parse_qs(urlsplit(browser.current_url).query)
    return urlsplit(browser.current_url).path == "/saved" and query == {
        "subscribe": ["on"],
        "theme": ["dark"],
    }


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "results"
    screenshots = output / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    runs = []
    for task in tasks():
        initial = task.browser.observe()
        (screenshots / f"{task.name}-initial.svg").write_text(initial.svg)
        run = BrowserAgent(task.browser).run(
            ScriptedPolicy(task.intents), lambda _browser, task=task: goal(task)
        )
        final = task.browser.observe()
        (screenshots / f"{task.name}-final.svg").write_text(final.svg)
        compressed = sum(step.compressed_tokens for step in run.steps)
        full_html = sum(step.full_html_tokens for step in run.steps)
        runs.append(
            {
                "task": task.name,
                "success": run.success,
                "steps": len(run.steps),
                "compressed_tokens": compressed,
                "full_html_tokens": full_html,
                "tokens_per_step": run.tokens_per_step,
                "token_reduction_fraction": 1 - compressed / full_html,
                "final_url": run.final_url,
                "error": run.error,
                "wall_seconds": run.wall_seconds,
            }
        )
    result = {
        "measured_at": datetime.now().astimezone().isoformat(),
        "environment": "deterministic in-memory local websites; no browser package or network",
        "tokenizer": "regex word/punctuation estimate, not provider tokenizer",
        "screenshots": "deterministic SVG wireframes with marks, not pixel browser captures",
        "runs": runs,
        "summary": {
            "success": sum(run["success"] for run in runs),
            "tasks": len(runs),
            "tokens_per_step": sum(run["compressed_tokens"] for run in runs)
            / sum(run["steps"] for run in runs),
            "token_reduction_fraction": 1
            - sum(run["compressed_tokens"] for run in runs)
            / sum(run["full_html_tokens"] for run in runs),
        },
    }
    output.mkdir(exist_ok=True)
    (output / "local_benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = [
        "# Local web-task benchmark",
        "",
        f"Measured: `{result['measured_at']}`",
        "",
        "All pages and policies are local and deterministic. Tokens are regex estimates; SVGs ",
        "are wireframe set-of-marks renderings. No external web benchmark was run.",
        "",
        "| Task | Success | Steps | Compressed | Raw HTML | Tokens/step | Reduction |",
        "|---|:---:|---:|---:|---:|---:|---:|",
    ]
    for run in runs:
        lines.append(
            f"| {run['task']} | {run['success']} | {run['steps']} | "
            f"{run['compressed_tokens']} | {run['full_html_tokens']} | "
            f"{run['tokens_per_step']:.1f} | {run['token_reduction_fraction']:.1%} |"
        )
    lines += [
        "",
        f"Overall task success: **{result['summary']['success']}/{result['summary']['tasks']}**. ",
        "Aggregate compressed-token reduction: "
        f"**{result['summary']['token_reduction_fraction']:.1%}**.",
        "",
    ]
    (output / "local_benchmark.md").write_text("\n".join(lines))
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
