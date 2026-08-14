"""One-off codemod: route view-rendered strings through the i18n layer.

Rewrites `st.markdown(...)` to the localizing `md(...)` renderer, wraps
`st.tabs([...])` label lists in `labels(...)`, and wraps literal widget labels
in `t(...)`. Kept in the repo so the transformation is auditable rather than
appearing as an unexplained hand edit.

Only single-line string literals are wrapped by AST span, because CPython
reports inaccurate end positions for implicitly concatenated strings.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

LABEL_CALLS = {
    "button",
    "caption",
    "subheader",
    "header",
    "text_input",
    "text_area",
    "selectbox",
    "radio",
    "toast",
    "number_input",
    "checkbox",
    "expander",
    "download_button",
    "metric",
}

# Keyword arguments whose literal values are also shown to the operator.
LABEL_KEYWORDS = {"placeholder", "help", "label"}


class _Index:
    """Maps AST positions to string indices.

    `ast` reports `col_offset` as a UTF-8 byte offset, so lines containing
    characters such as `…` or `—` shift every column that follows.
    """

    def __init__(self, source: str) -> None:
        self._lines = source.splitlines(keepends=True)
        self._starts = [0]
        for line in self._lines:
            self._starts.append(self._starts[-1] + len(line))

    def at(self, lineno: int, byte_col: int) -> int:
        line = self._lines[lineno - 1]
        char_col = len(line.encode("utf-8")[:byte_col].decode("utf-8", "ignore"))
        return self._starts[lineno - 1] + char_col


def _single_line_span(node: ast.AST, index: _Index) -> tuple[int, int] | None:
    if node.lineno != node.end_lineno:
        return None
    return index.at(node.lineno, node.col_offset), index.at(node.lineno, node.end_col_offset)


def _is_plain_string(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and bool(node.value.strip())


def transform(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    source = original
    tree = ast.parse(source)
    index = _Index(source)
    edits: list[tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue

        # Labels are localized regardless of receiver, so column-scoped widgets
        # such as `controls[3].button(...)` are covered too.
        if node.func.attr in LABEL_CALLS:
            for keyword in node.keywords:
                if keyword.arg in LABEL_KEYWORDS and _is_plain_string(keyword.value):
                    span = _single_line_span(keyword.value, index)
                    if span:
                        edits.append((*span, f"t({source[span[0]:span[1]]})"))

        if not node.args:
            continue
        target = node.args[0]
        is_streamlit = isinstance(node.func.value, ast.Name) and node.func.value.id == "st"

        if node.func.attr == "tabs" and is_streamlit and isinstance(target, ast.List):
            span = _single_line_span(target, index)
            if span and all(_is_plain_string(item) for item in target.elts):
                edits.append((*span, f"labels({source[span[0]:span[1]]})"))
            continue

        if node.func.attr in LABEL_CALLS and _is_plain_string(target):
            span = _single_line_span(target, index)
            if span:
                edits.append((*span, f"t({source[span[0]:span[1]]})"))

    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]

    # Paren matching is unnecessary here: only the callee name changes.
    source = re.sub(r"\bst\.markdown\(", "md(", source)

    if source == original:
        return False

    new_imports = {}
    ui_names = [name for name, pattern in (("labels", r"\blabels\("), ("md", r"\bmd\(")) if re.search(pattern, source)]
    if ui_names and "from components.ui import" not in source:
        new_imports["components.ui"] = f"from components.ui import {', '.join(ui_names)}\n"
    if re.search(r"(?<![\w.])t\(", source) and "from components.i18n import" not in source:
        new_imports["components.i18n"] = "from components.i18n import t\n"

    for module, statement in sorted(new_imports.items(), reverse=True):
        source = _insert_component_import(source, module, statement)

    path.write_text(source, encoding="utf-8")
    return True


def _insert_component_import(source: str, module: str, statement: str) -> str:
    """Insert an import into the existing `components.*` block, keeping it sorted."""
    lines = source.splitlines(keepends=True)
    insert_at = None
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ImportFrom) or not (node.module or "").startswith("components."):
            continue
        if (node.module or "") < module:
            insert_at = max(insert_at or 0, node.end_lineno)
        elif insert_at is None:
            insert_at = node.lineno - 1
            break
    if insert_at is None:
        marker = "import streamlit as st\n"
        return source.replace(marker, f"{marker}\n{statement}", 1)
    lines.insert(insert_at, statement)
    return "".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    changed = []
    for path in sorted((root / "views").glob("*.py")):
        if path.name == "__init__.py":
            continue
        if transform(path):
            changed.append(path.name)
    print(f"transformed {len(changed)} views: {', '.join(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
