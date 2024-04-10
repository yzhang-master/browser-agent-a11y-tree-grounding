from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .html import DOMNode, HTMLDocument, normalize_space

INTERACTIVE_ROLES = {"link", "button", "textbox", "checkbox", "radio", "combobox"}
_INCLUDED_ROLES = INTERACTIVE_ROLES | {
    "main",
    "navigation",
    "form",
    "heading",
    "list",
    "listitem",
    "img",
    "text",
    "status",
}


@dataclass
class AccessibilityNode:
    element_id: str
    role: str
    name: str
    dom: DOMNode = field(repr=False, compare=False)
    value: str = ""
    checked: bool | None = None
    disabled: bool = False
    children: list[AccessibilityNode] = field(default_factory=list)

    @property
    def interactive(self) -> bool:
        return self.role in INTERACTIVE_ROLES and not self.disabled


def _hidden(node: DOMNode) -> bool:
    style = node.attrs.get("style", "").replace(" ", "").lower()
    return (
        "hidden" in node.attrs
        or node.attrs.get("aria-hidden", "").lower() == "true"
        or node.attrs.get("type", "").lower() == "hidden"
        or "display:none" in style
        or "visibility:hidden" in style
    )


def _role(node: DOMNode) -> str:
    if explicit := node.attrs.get("role"):
        return explicit.lower()
    tag = node.tag
    if tag == "a" and "href" in node.attrs:
        return "link"
    if tag == "button":
        return "button"
    if tag == "input":
        input_type = node.attrs.get("type", "text").lower()
        if input_type in {"checkbox", "radio"}:
            return input_type
        if input_type in {"button", "submit", "reset"}:
            return "button"
        return "textbox"
    if tag == "select":
        return "combobox"
    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return "heading"
    if tag in {"nav", "main", "form", "img"}:
        return tag if tag != "nav" else "navigation"
    if tag in {"ul", "ol"}:
        return "list"
    if tag == "li":
        return "listitem"
    if tag in {"p", "output"}:
        return "text" if tag == "p" else "status"
    return "generic"


def _label_for(node: DOMNode, document: HTMLDocument) -> str:
    node_id = node.attrs.get("id")
    if node_id:
        for label in document.find_all("label"):
            if label.attrs.get("for") == node_id:
                return label.descendant_text
    for ancestor in node.ancestors():
        if ancestor.tag == "label":
            return ancestor.descendant_text
    return ""


def _name(node: DOMNode, document: HTMLDocument, role: str) -> str:
    if label := node.attrs.get("aria-label"):
        return normalize_space(label)
    if labelled_by := node.attrs.get("aria-labelledby"):
        labels = [
            target.descendant_text
            for target_id in labelled_by.split()
            if (target := document.by_html_id(target_id)) is not None
        ]
        if labels:
            return normalize_space(" ".join(labels))
    if role in INTERACTIVE_ROLES | {"combobox"}:
        if label := _label_for(node, document):
            return label
    if role == "img":
        return normalize_space(node.attrs.get("alt", ""))
    if role == "button" and node.tag == "input":
        return normalize_space(node.attrs.get("value", "Submit"))
    if role == "textbox":
        return normalize_space(node.attrs.get("placeholder", ""))
    if role == "combobox":
        selected = next(
            (
                option
                for option in node.children
                if option.tag == "option" and "selected" in option.attrs
            ),
            None,
        )
        return selected.descendant_text if selected is not None else ""
    return node.descendant_text


def build_accessibility_tree(document: HTMLDocument) -> AccessibilityNode:
    root = AccessibilityNode("root", "document", "", document.root)
    signatures: dict[str, int] = {}

    def make_id(node: DOMNode, role: str, name: str) -> str:
        anchor = node.attrs.get("data-element-id") or node.attrs.get("id", "")
        signature = f"{anchor}|{node.tag}|{role}|{name}"
        ordinal = signatures.get(signature, 0)
        signatures[signature] = ordinal + 1
        digest = hashlib.sha256(f"{signature}|{ordinal}".encode()).hexdigest()[:12]
        return f"e-{digest}"

    def visit(node: DOMNode) -> list[AccessibilityNode]:
        if _hidden(node) or node.tag in {"script", "style", "head", "template"}:
            return []
        role = _role(node)
        name = _name(node, document, role)
        children = []
        for child in node.children:
            children.extend(visit(child))
        if role not in _INCLUDED_ROLES:
            return children
        if role in {"text", "listitem", "heading"} and not name:
            return children
        value = node.attrs.get("value", "") if role == "textbox" else ""
        if role == "combobox":
            value = next(
                (
                    option.attrs.get("value", option.descendant_text)
                    for option in node.children
                    if option.tag == "option" and "selected" in option.attrs
                ),
                "",
            )
        checked = "checked" in node.attrs if role in {"checkbox", "radio"} else None
        disabled = "disabled" in node.attrs or node.attrs.get("aria-disabled") == "true"
        result = AccessibilityNode(
            make_id(node, role, name),
            role,
            name,
            node,
            value,
            checked,
            disabled,
            children,
        )
        return [result]

    root.children = visit(document.root)
    return root


def walk_tree(root: AccessibilityNode) -> list[AccessibilityNode]:
    result = []

    def visit(node: AccessibilityNode) -> None:
        result.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return result


def compress_tree(
    root: AccessibilityNode,
    *,
    marks: dict[str, str] | None = None,
    max_nodes: int = 80,
    max_chars: int = 6000,
) -> str:
    if max_nodes <= 0 or max_chars <= 0:
        raise ValueError("compression limits must be positive")
    marks = marks or {}
    lines = []
    omitted = 0

    def visit(node: AccessibilityNode, depth: int) -> None:
        nonlocal omitted
        if len(lines) >= max_nodes:
            omitted += 1
            return
        parts = [f"{'  ' * depth}{node.role}"]
        if node.name:
            parts.append(json.dumps(node.name, ensure_ascii=False))
        if node.element_id in marks:
            parts.append(f"[mark={marks[node.element_id]} id={node.element_id}]")
        if node.value:
            parts.append(f"value={json.dumps(node.value, ensure_ascii=False)}")
        if node.checked is not None:
            parts.append(f"checked={str(node.checked).lower()}")
        if node.disabled:
            parts.append("disabled=true")
        lines.append(" ".join(parts))
        for child in node.children:
            visit(child, depth + 1)

    visit(root, 0)
    if omitted:
        lines.append(f"… {omitted} nodes omitted")
    output = "\n".join(lines)
    if len(output) > max_chars:
        output = output[: max_chars - 20].rstrip() + "\n… characters omitted"
    return output
