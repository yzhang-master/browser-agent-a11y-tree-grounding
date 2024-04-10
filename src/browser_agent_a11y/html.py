from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "source", "track", "wbr",
}


@dataclass
class DOMNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[DOMNode] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)
    parent: DOMNode | None = field(default=None, repr=False, compare=False)

    @property
    def text(self) -> str:
        return normalize_space(" ".join(self.text_parts))

    @property
    def descendant_text(self) -> str:
        parts = list(self.text_parts)
        for child in self.children:
            if child.tag not in {"script", "style"}:
                parts.append(child.descendant_text)
        return normalize_space(" ".join(parts))

    def ancestors(self) -> list[DOMNode]:
        result = []
        current = self.parent
        while current is not None:
            result.append(current)
            current = current.parent
        return result


def normalize_space(text: str) -> str:
    return " ".join(text.split())


@dataclass
class HTMLDocument:
    root: DOMNode
    source: str = ""

    def find_all(self, tag: str) -> list[DOMNode]:
        found = []

        def visit(node: DOMNode) -> None:
            if node.tag == tag:
                found.append(node)
            for child in node.children:
                visit(child)

        visit(self.root)
        return found

    def by_html_id(self, html_id: str) -> DOMNode | None:
        return next(
            (node for node in self.walk() if node.attrs.get("id") == html_id), None
        )

    def walk(self) -> list[DOMNode]:
        result = []

        def visit(node: DOMNode) -> None:
            result.append(node)
            for child in node.children:
                visit(child)

        visit(self.root)
        return result


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = DOMNode("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        node = DOMNode(tag, {key.lower(): value or "" for key, value in attrs})
        node.parent = self.stack[-1]
        self.stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID_TAGS and self.stack[-1].tag == tag.lower():
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.stack[-1].text_parts.append(normalize_space(data))


def parse_html(source: str) -> HTMLDocument:
    parser = _TreeBuilder()
    parser.feed(source)
    parser.close()
    return HTMLDocument(parser.root, source)
