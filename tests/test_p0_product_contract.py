"""Structural acceptance checks for the P0 product contract.

These tests intentionally verify stable seams (routes, public state APIs, dynamic
context rendering, and project documentation) rather than Streamlit layout or
implementation details.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _parse(relative_path: str) -> ast.Module:
    return ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))


def _defined_functions(tree: ast.AST) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _page_keyword_strings(tree: ast.AST) -> list[dict[str, str]]:
    pages: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "Page"):
            continue
        values: dict[str, str] = {}
        for keyword in node.keywords:
            if (
                keyword.arg in {"title", "url_path"}
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                values[keyword.arg] = keyword.value.value
        pages.append(values)
    return pages


def _literal_mission_chips(relative_path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(relative_path.read_text(encoding="utf-8"))
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        first_arg = node.args[0]
        if (
            name == "mission_chip"
            and isinstance(first_arg, ast.Constant)
            and isinstance(first_arg.value, str)
        ):
            violations.append((node.lineno, first_arg.value))
    return violations


def test_dual_entry_routes_are_first_class_pages():
    pages = _page_keyword_strings(_parse("app.py"))
    routes = {(page.get("title"), page.get("url_path")) for page in pages}

    assert ("Launch Mission", "launch-mission") in routes
    assert ("Creator Opportunity", "creator-opportunity") in routes


def test_state_exposes_active_context_and_transition_boundaries():
    functions = _defined_functions(_parse("components/state.py"))
    required = {
        "active_context",
        "set_active_context",
        "transition_creator_state",
        "ensure_outreach_case",
        "contact_pack_for",
        "refresh_outreach_message",
        "next_linear_creator_state",
        "workflow_events_for",
        "opportunities_for_mission",
    }

    assert required <= functions, f"Missing public P0 state APIs: {sorted(required - functions)}"


def test_views_do_not_render_literal_mission_context_chips():
    violations: list[str] = []
    for view in sorted((ROOT / "views").glob("*.py")):
        for line, value in _literal_mission_chips(view):
            violations.append(f"{view.relative_to(ROOT)}:{line} -> {value!r}")

    assert not violations, (
        "mission_chip labels must come from the active context, not fixed demo text: "
        + "; ".join(violations)
    )


def test_readme_describes_dual_entry_product_and_current_tree():
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert "launch mission" in readme
    assert "creator opportunity" in readme
    for directory in ("components/", "services/", "views/", "tests/"):
        assert directory in readme, f"README repository tree is missing {directory}"


def test_p0_contract_is_present_and_names_acceptance_boundaries():
    contract = (ROOT / "docs" / "06_p0_product_contract.md").read_text(encoding="utf-8")
    required_terms = {
        "Launch Mission",
        "Creator Opportunity",
        "Mission",
        "Opportunity",
        "OutreachCase",
        "active_context",
        "transition_creator_state",
        "closed_lost",
        "Non-goals",
        "acceptance criteria",
    }

    missing = sorted(term for term in required_terms if term.lower() not in contract.lower())
    assert not missing, f"P0 contract is missing: {missing}"
