from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlencode, urljoin, urlsplit

from .a11y import walk_tree
from .grounding import GroundedAction, GroundingError
from .html import DOMNode, parse_html
from .observation import Observation, observe_document

Route = str | Callable[[str], str]


class LocalWebsite:
    def __init__(self, routes: dict[str, Route], *, start_url: str = "http://local.test/") -> None:
        self.routes = routes
        self.start_url = start_url

    def render(self, url: str) -> str:
        route = self.routes.get(url)
        if route is None:
            split = urlsplit(url)
            route = self.routes.get(split.path + (f"?{split.query}" if split.query else ""))
            if route is None:
                route = self.routes.get(split.path)
        if route is None:
            return "<title>Not found</title><main><h1>404 Not found</h1></main>"
        return route(url) if callable(route) else route


class LocalBrowser:
    """Deterministic HTML browser: links, forms, fields, history, but no JavaScript."""

    def __init__(self, website: LocalWebsite) -> None:
        self.website = website
        self.current_url = website.start_url
        self.document = parse_html(website.render(self.current_url))
        self.history = [self.current_url]
        self.revision = 1

    def observe(self) -> Observation:
        return observe_document(
            self.document,
            url=self.current_url,
            observation_id=f"{self.revision}:{self.current_url}",
        )

    def _navigate(self, url: str) -> None:
        self.current_url = urljoin(self.current_url, url)
        self.document = parse_html(self.website.render(self.current_url))
        self.history.append(self.current_url)
        self.revision += 1

    @staticmethod
    def _descendants(node: DOMNode, tag: str) -> list[DOMNode]:
        result = []

        def visit(current: DOMNode) -> None:
            if current.tag == tag:
                result.append(current)
            for child in current.children:
                visit(child)

        visit(node)
        return result

    def _submit(self, button: DOMNode) -> None:
        form = next((node for node in button.ancestors() if node.tag == "form"), None)
        if form is None:
            raise GroundingError("button is not inside a form")
        if form.attrs.get("method", "get").lower() != "get":
            raise GroundingError("only deterministic GET forms are supported")
        fields = []
        for field in self._descendants(form, "input") + self._descendants(form, "select"):
            name = field.attrs.get("name")
            if not name or "disabled" in field.attrs:
                continue
            input_type = field.attrs.get("type", "text")
            if input_type in {"checkbox", "radio"} and "checked" not in field.attrs:
                continue
            if field.tag == "select":
                selected = next(
                    (
                        option
                        for option in field.children
                        if option.tag == "option" and "selected" in option.attrs
                    ),
                    None,
                )
                value = (
                    selected.attrs.get("value", selected.descendant_text)
                    if selected is not None
                    else ""
                )
            elif input_type in {"checkbox", "radio"}:
                value = field.attrs.get("value", "on")
            else:
                value = field.attrs.get("value", "")
            fields.append((name, value))
        action = urljoin(self.current_url, form.attrs.get("action", self.current_url))
        separator = "&" if urlsplit(action).query else "?"
        self._navigate(action + (separator + urlencode(fields) if fields else ""))

    def execute(self, grounded: GroundedAction) -> Observation:
        action = grounded.action
        if action.kind == "finish":
            return self.observe()
        if action.kind == "go_back":
            if len(self.history) > 1:
                self.history.pop()
                self.current_url = self.history[-1]
                self.document = parse_html(self.website.render(self.current_url))
                self.revision += 1
            return self.observe()
        if grounded.node is None:
            raise GroundingError("browser action has no grounded node")
        node = next(
            (
                candidate
                for candidate in walk_tree(self.observe().tree)
                if candidate.element_id == grounded.node.element_id
            ),
            None,
        )
        if node is None:
            raise GroundingError("grounded element is no longer present")
        dom = node.dom
        if action.kind == "type":
            dom.attrs["value"] = action.text
            self.revision += 1
        elif action.kind == "select":
            options = [child for child in dom.children if child.tag == "option"]
            selected = next(
                (
                    option
                    for option in options
                    if action.value in {option.attrs.get("value"), option.descendant_text}
                ),
                None,
            )
            if selected is None:
                raise GroundingError(f"unknown option: {action.value}")
            for option in options:
                option.attrs.pop("selected", None)
            selected.attrs["selected"] = ""
            self.revision += 1
        elif action.kind == "click":
            if node.role == "link":
                self._navigate(dom.attrs["href"])
            elif node.role in {"checkbox", "radio"}:
                if node.role == "radio":
                    for other in self.document.find_all("input"):
                        if other.attrs.get("name") == dom.attrs.get("name"):
                            other.attrs.pop("checked", None)
                if "checked" in dom.attrs and node.role == "checkbox":
                    dom.attrs.pop("checked")
                else:
                    dom.attrs["checked"] = ""
                self.revision += 1
            elif dom.tag == "input" and dom.attrs.get("type") == "submit":
                self._submit(dom)
            elif dom.tag == "button" and dom.attrs.get("type", "submit") == "submit":
                self._submit(dom)
            else:
                raise GroundingError("non-submit buttons need a browser JavaScript adapter")
        return self.observe()
