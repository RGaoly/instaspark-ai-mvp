from __future__ import annotations

import html
import math
from typing import Iterable, Sequence

from components.data import AVATAR_GRADIENTS, SPARKLINES


def esc(value: object) -> str:
    return html.escape(str(value))


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "AI"
    return "".join(p[0] for p in parts[:2]).upper()


def avatar(name: str, index: int = 0, size: str = "mini") -> str:
    cls = "is-mini-avatar" if size == "mini" else "is-profile-avatar"
    gradient = AVATAR_GRADIENTS[index % len(AVATAR_GRADIENTS)]
    return f'<div class="{cls}" style="background:{gradient}">{esc(initials(name))}</div>'


def badge(text: str, tone: str = "gray") -> str:
    return f'<span class="is-badge is-badge-{tone}">{esc(text)}</span>'


def sparkline(values: Sequence[float], color: str = "#2577F1") -> str:
    if not values:
        values = [0, 1]
    width, height, pad = 120, 18, 1.5
    low, high = min(values), max(values)
    span = max(high - low, 1)
    pts = []
    for idx, value in enumerate(values):
        x = pad + idx * (width - 2 * pad) / max(len(values) - 1, 1)
        y = height - pad - ((value - low) / span) * (height - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg class="is-spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
        'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )


def metric_cards(metrics: Iterable[tuple[str, str, str, str]]) -> str:
    cards = []
    for idx, (label, value, delta, note) in enumerate(metrics):
        note_html = f'<div class="is-metric-note">{esc(note)}</div>' if note else ""
        cards.append(
            '<div class="is-metric">'
            '<div class="is-metric-top">'
            f'<div class="is-metric-label">{esc(label)}</div>'
            '<div class="is-metric-icon"><i></i><i class="thin"></i></div>'
            '</div>'
            f'<div class="is-metric-value">{esc(value)}</div>'
            f'<div class="is-metric-delta">{esc(delta)}</div>'
            f'{sparkline(SPARKLINES[idx % len(SPARKLINES)])}'
            f'{note_html}'
            '</div>'
        )
    return '<div class="is-metric-grid">' + "".join(cards) + '</div>'


def mini_kpis(metrics: Iterable[tuple[str, str, str]]) -> str:
    cards = []
    for label, value, note in metrics:
        cards.append(
            '<div class="is-kpi-mini">'
            f'<label>{esc(label)}</label><strong>{esc(value)}</strong><small>{esc(note)}</small>'
            '</div>'
        )
    return '<div class="is-kpi-strip">' + "".join(cards) + '</div>'


def dots(score: float, count: int = 5) -> str:
    active = max(0, min(count, int(round(float(score) / 100 * count))))
    return '<div class="is-dot-row">' + "".join(
        f'<i class="is-dot{" on" if i < active else ""}"></i>' for i in range(count)
    ) + '</div>'


def score_ring(score: float) -> str:
    value = int(round(float(score)))
    return f'<div class="is-score-ring" style="--score:{value}"><span>{value}</span></div>'


def scorebar(label: str, score: float, color: str = "#16A36A") -> str:
    value = max(0.0, min(100.0, float(score)))
    return (
        '<div class="is-scorebar">'
        f'<label>{esc(label)}</label>'
        f'<div class="is-scorebar-track"><div class="is-scorebar-fill" style="width:{value:.1f}%;background:{color}"></div></div>'
        f'<span>{value:.0f}/100</span>'
        '</div>'
    )


def page_header(title: str, subtitle: str, badge_text: str | None = None, badge_tone: str = "yellow") -> str:
    badge_html = badge(badge_text, badge_tone) if badge_text else ""
    return (
        '<div class="is-page-head">'
        f'<div><h1 class="is-page-title">{esc(title)}</h1><div class="is-page-subtitle">{esc(subtitle)}</div></div>'
        f'<div>{badge_html}</div>'
        '</div>'
    )


def mission_chip(text: str, *, light: bool = False) -> str:
    cls = "is-mission-chip is-light" if light else "is-mission-chip"
    return f'<span class="{cls}"><span class="is-mission-dot"></span>{esc(text)}</span>'


def ai_badge(text: str = "AI Generated") -> str:
    return f'<span class="is-ai-badge">{esc(text)}</span>'


def nl_search_shell(hint: str) -> str:
    return (
        '<div class="is-nl-search">'
        '<span class="is-nl-icon">✦</span>'
        '<span class="is-nl-label">NL Search</span>'
        f'<span class="is-nl-hint">{esc(hint)}</span>'
        '</div>'
    )


def card(title: str, body: str, *, flat: bool = False) -> str:
    cls = "is-card is-card-flat is-card-pad" if flat else "is-card is-card-pad"
    return f'<div class="{cls}"><div class="is-card-title">{esc(title)}</div><div class="is-card-caption" style="margin-top:5px">{esc(body)}</div></div>'


def pct_width(value: float, max_value: float) -> int:
    return int(max(4, min(100, math.floor(value / max_value * 100))))
