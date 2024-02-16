from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass
class DOMNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[DOMNode] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).split())


@dataclass
class HTMLDocument:
    root: DOMNode

    def find_all(self, tag: str) -> list[DOMNode]:
        found = []

        def visit(node: DOMNode) -> None:
            if node.tag == tag:
                found.append(node)
            for child in node.children:
                visit(child)

        visit(self.root)
        return found


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = DOMNode("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = DOMNode(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in {"area", "br", "hr", "img", "input", "meta", "source"}:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.stack[-1].text_parts.append(data.strip())


def parse_html(source: str) -> HTMLDocument:
    parser = _TreeBuilder()
    parser.feed(source)
    parser.close()
    return HTMLDocument(parser.root)
