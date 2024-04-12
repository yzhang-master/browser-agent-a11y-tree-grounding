from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .a11y import AccessibilityNode, build_accessibility_tree, compress_tree, walk_tree
from .html import HTMLDocument


@dataclass
class Observation:
    observation_id: str
    url: str
    title: str
    document: HTMLDocument
    tree: AccessibilityNode
    marks: dict[str, str]
    compressed_tree: str
    svg: str

    def node_for_mark(self, mark: str) -> AccessibilityNode | None:
        element_id = next(
            (element_id for element_id, value in self.marks.items() if value == mark), None
        )
        if element_id is None:
            return None
        return next(
            (node for node in walk_tree(self.tree) if node.element_id == element_id), None
        )

    def mark_for_name(self, name: str) -> str:
        normalized = name.casefold()
        for node in walk_tree(self.tree):
            if node.interactive and node.name.casefold() == normalized:
                return self.marks[node.element_id]
        raise KeyError(f"no interactive element named {name!r}")


def render_set_of_marks_svg(
    url: str,
    title: str,
    root: AccessibilityNode,
    marks: dict[str, str],
) -> str:
    nodes = walk_tree(root)[1:]
    width = 960
    height = max(180, 110 + 48 * len(nodes))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Set of marks for {escape(title)}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="28" y="34" font-family="sans-serif" font-size="20" '
        f'font-weight="bold">{escape(title)}</text>',
        '<text x="28" y="60" font-family="monospace" font-size="12" '
        f'fill="#475569">{escape(url)}</text>',
    ]
    depths = {}

    def record_depth(node: AccessibilityNode, depth: int) -> None:
        depths[node.element_id] = depth
        for child in node.children:
            record_depth(child, depth + 1)

    record_depth(root, -1)
    for index, node in enumerate(nodes):
        y = 82 + index * 48
        depth = max(0, depths[node.element_id])
        x = 28 + min(depth, 5) * 22
        interactive = node.element_id in marks
        fill = "#eff6ff" if interactive else "#ffffff"
        stroke = "#2563eb" if interactive else "#e2e8f0"
        parts.append(
            f'<g data-element-id="{node.element_id}"'
            + (f' data-mark="{marks[node.element_id]}"' if interactive else "")
            + ">"
        )
        parts.append(
            f'<rect x="{x}" y="{y}" width="{width - x - 28}" height="38" rx="5" '
            f'fill="{fill}" stroke="{stroke}"/>'
        )
        label = f"{node.role}: {node.name}"
        if node.value:
            label += f" = {node.value}"
        parts.append(
            f'<text x="{x + 12}" y="{y + 24}" font-family="sans-serif" font-size="14" '
            f'fill="#0f172a">{escape(label[:95])}</text>'
        )
        if interactive:
            mark = marks[node.element_id]
            parts.append(
                f'<rect x="4" y="{y + 3}" width="28" height="28" rx="4" fill="#dc2626"/>'
            )
            parts.append(
                f'<text x="18" y="{y + 22}" text-anchor="middle" font-family="monospace" '
                f'font-size="14" font-weight="bold" fill="#ffffff">{escape(mark)}</text>'
            )
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def observe_document(
    document: HTMLDocument,
    *,
    url: str,
    observation_id: str,
    max_nodes: int = 80,
    max_chars: int = 6000,
) -> Observation:
    tree = build_accessibility_tree(document)
    interactive = [node for node in walk_tree(tree) if node.interactive]
    marks = {node.element_id: str(index) for index, node in enumerate(interactive, 1)}
    title_nodes = document.find_all("title")
    title = title_nodes[0].descendant_text if title_nodes else url
    return Observation(
        observation_id,
        url,
        title,
        document,
        tree,
        marks,
        compress_tree(tree, marks=marks, max_nodes=max_nodes, max_chars=max_chars),
        render_set_of_marks_svg(url, title, tree, marks),
    )
