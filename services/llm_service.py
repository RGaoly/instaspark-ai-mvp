"""LLM service — OpenAI-compatible API integration for content generation.

Supports any OpenAI-compatible provider (DeepSeek, OpenAI, Moonshot, etc.)
by configuring LLM_BASE_URL and LLM_API_KEY in .env.

When LLM_API_KEY is configured, generates dynamic briefs, hooks, scripts
and localized content via the Chat Completions API.
When the key is absent, falls back to deterministic mock content so the app
remains fully functional in development and demo mode.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from infra.config import LLM_MAX_TOKENS, LLM_TEMPERATURE, _resolve_secret

logger = logging.getLogger(__name__)


def _llm_api_key() -> str:
    return _resolve_secret("LLM_API_KEY", "")


def _llm_base_url() -> str:
    return _resolve_secret("LLM_BASE_URL", "https://api.deepseek.com")


def _llm_model() -> str:
    return _resolve_secret("LLM_MODEL", "deepseek-chat")


def is_llm_available() -> bool:
    """Return True if an LLM API key is configured."""
    return bool(_llm_api_key())


def generation_mode_label() -> str:
    """Operator-facing source label for generated copy."""
    return "AI generated" if is_llm_available() else "Template demo"


def _join(values: Any, fallback: str = "") -> str:
    if values is None:
        return fallback
    if isinstance(values, (list, tuple)):
        text = ", ".join(str(item) for item in values if str(item).strip())
        return text or fallback
    text = str(values).strip()
    return text or fallback


def _grounding_facts(
    mission: dict[str, Any],
    creator: dict[str, Any],
    *,
    tone: str | None = None,
    checklist: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Facts the model (or template) must stay inside — no invented specs."""
    selected_tone = (tone or mission.get("brand_tone") or "").strip() or "not specified"
    selected_checklist = checklist if checklist is not None else mission.get("quality_checklist")
    return (
        f"Product: {mission.get('product', 'the product')}\n"
        f"Mission title: {mission.get('title') or mission.get('name') or 'Active launch'}\n"
        f"Objective: {mission.get('objective', 'Validate product-market fit with creator-led content.')}\n"
        f"Primary market: {mission.get('market', 'global')}\n"
        f"Language: {mission.get('language', 'local language')}\n"
        f"Markets: {_join(mission.get('markets'), mission.get('market', 'global'))}\n"
        f"Target topics: {_join(mission.get('target_topics'), 'creator-relevant use cases')}\n"
        f"Target styles: {_join(mission.get('target_styles'), 'the creator native style')}\n"
        f"Brand tone: {selected_tone}\n"
        f"Quality checklist: {_join(selected_checklist, 'none selected')}\n"
        f"Budget USD: {mission.get('budget_usd', 0)}\n"
        f"Owner: {mission.get('owner', 'Mission owner')}\n"
        f"Creator: {creator.get('creator_name', 'the creator')}\n"
        f"Creator id: {creator.get('creator_id', 'unknown')}\n"
        f"Creator market: {creator.get('primary_market', mission.get('market', 'global'))}\n"
        f"Creator topics: {_join(creator.get('topics'), 'not specified')}\n"
        f"Creator styles: {_join(creator.get('styles'), 'not specified')}\n"
        f"Followers: {int(creator.get('followers') or 0):,}\n"
        f"Engagement rate: {creator.get('engagement_rate', 'n/a')}\n"
        "Constraint: do not invent product specifications, prices, or unverified claims."
    )


def _call_llm(system_prompt: str, user_prompt: str) -> str | None:
    """Call LLM Chat Completions API and return the response text.

    Returns None on any error so callers can fall back to mock content.
    """
    if not is_llm_available():
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=_llm_api_key(), base_url=_llm_base_url())
        response = client.chat.completions.create(
            model=_llm_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.warning("LLM API call failed, falling back to mock: %s", exc)
        return None


# ─── Brief Generation ──────────────────────────────────────────


def generate_brief(
    mission: dict[str, Any],
    creator: dict[str, Any],
    *,
    tone: str | None = None,
    checklist: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Generate a collaboration brief as Markdown.

    Uses OpenAI if available, otherwise returns a deterministic mock brief.
    """
    product = mission.get("product", "the product")
    market = mission.get("market", "global")
    scenario = _join(mission.get("target_topics"), "storytelling")
    creator_name = creator.get("creator_name", "the creator")
    selected_tone = (tone or mission.get("brand_tone") or "").strip()
    selected_checklist = list(checklist if checklist is not None else mission.get("quality_checklist") or [])

    if is_llm_available():
        system_prompt = (
            "You are a brand marketing strategist. Generate a concise, "
            "actionable creator collaboration brief in Markdown format. "
            "Include sections: Objective, Audience, Core Message, Must-Show, "
            "Shot List, Do/Don't. Stay inside the supplied facts. "
            "Honor the selected brand tone and quality checklist. "
            "Do not invent product specs. Keep it under 400 words."
        )
        result = _call_llm(
            system_prompt,
            _grounding_facts(mission, creator, tone=selected_tone, checklist=selected_checklist),
        )
        if result:
            return result

    # Fallback: deterministic mock brief
    return _mock_brief(
        product,
        market,
        scenario,
        creator_name,
        tone=selected_tone,
        checklist=selected_checklist,
    )


def _mock_brief(
    product: str,
    market: str,
    scenario: str,
    creator_name: str,
    *,
    tone: str | None = None,
    checklist: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Return a deterministic mock brief for development/demo mode."""
    tone_line = (tone or "").strip() or "not specified"
    checklist_items = [item for item in (checklist or []) if str(item).strip()]
    checklist_md = (
        "\n".join(f"- {item}" for item in checklist_items) if checklist_items else "- none selected"
    )
    return f"""# Collaboration Brief — {product}

**Creator:** {creator_name}
**Market:** {market}
**Brand tone:** {tone_line}

## Objective
Show how {product} supports real-world {scenario} storytelling in a {tone_line} voice.

## Audience
Action-camera users, outdoor creators and travel storytellers across {market}.

## Core Message
Capture every angle without missing the moment — {product} keeps the story open.

## Quality checklist
{checklist_md}

## Must-Show
- Product demonstrated in a real use case
- Key feature highlighted naturally
- Creator's authentic verdict
- Clear call to action

## Shot List
- Wide establishing shot
- Immersive POV sequence
- Subject + environment context
- Close-up of key feature
- Reframe reveal example
- CTA end card

## Do / Don't
**Do:** Use natural light, keep edits cinematic, show real movement, disclose paid partnership.
**Don't:** Invent specifications, make unverified competitor claims, perform unsafe stunts.
"""


# ─── Localized Content Generation ──────────────────────────────


def generate_localized_content(
    mission: dict[str, Any],
    creator: dict[str, Any],
    *,
    tone: str | None = None,
    checklist: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, str]]:
    """Generate localized hooks, captions and CTAs for each target market.

    Returns a list of dicts with keys: market, language, flag, hook, caption, cta, disclosure.
    Falls back to mock content when LLM is unavailable.
    """
    product = mission.get("product", "the product")
    markets = mission.get("markets", ["United States", "Mexico"])
    selected_tone = (tone or mission.get("brand_tone") or "").strip() or "on-brand"
    selected_checklist = list(
        checklist if checklist is not None else mission.get("quality_checklist") or []
    )

    market_configs = {
        "United States": {"language": "English", "flag": "US"},
        "Mexico": {"language": "Espanol", "flag": "MX"},
    }

    if is_llm_available():
        system_prompt = (
            "You are a localization expert for social media content. "
            "Generate platform-native hooks, captions and CTAs for each market. "
            "Honor the selected brand tone and quality checklist. "
            "Return valid JSON array with objects containing: "
            "market, language, flag, hook, caption, cta, disclosure. "
            "Keep hooks under 15 words, captions under 40 words."
        )
        result = _call_llm(
            system_prompt,
            _grounding_facts(
                mission,
                creator,
                tone=selected_tone,
                checklist=selected_checklist,
            ),
        )
        if result:
            try:
                parsed = json.loads(result)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM localized content JSON, using mock")

    # Fallback: mock localized content
    return _mock_localized_content(
        product,
        markets,
        market_configs,
        tone=selected_tone,
        checklist=selected_checklist,
    )


def _mock_localized_content(
    product: str,
    markets: list[str],
    market_configs: dict[str, dict[str, str]],
    *,
    tone: str | None = None,
    checklist: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, str]]:
    """Return deterministic mock localized content."""
    tone_line = (tone or "").strip() or "on-brand"
    checklist_note = _join(checklist, "none selected")
    templates = {
        "English": {
            "hook": f"{tone_line} hook: One camera. Every angle. Every moment. This is the {product}.",
            "caption": (
                f"From sunrise trails to city nights — the {product} captures it all. "
                f"Voice: {tone_line}. Checklist: {checklist_note}."
            ),
            "cta": f"Tap the link to explore the {product} and start capturing every angle.",
            "disclosure": "#ad - Paid partnership",
        },
        "Espanol": {
            "hook": f"{tone_line}: Una camara. Todos los angulos. Cada momento. Esta es la {product}.",
            "caption": (
                f"Desde rutas al amanecer hasta noches en la ciudad — la {product} captura todo. "
                f"Tono: {tone_line}. Checklist: {checklist_note}."
            ),
            "cta": f"Toca el enlace para conocer la {product} y captura cada angulo.",
            "disclosure": "#ad - Colaboracion pagada",
        },
    }

    results = []
    for market in markets:
        config = market_configs.get(market, {"language": "English", "flag": "US"})
        lang = config["language"]
        template = templates.get(lang, templates["English"])
        results.append({
            "market": market,
            "language": lang,
            "flag": config["flag"],
            **template,
        })
    return results


# ─── Hook Generation ───────────────────────────────────────────


def generate_hooks(
    mission: dict[str, Any],
    creator: dict[str, Any],
    *,
    tone: str | None = None,
    checklist: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Generate 3 hook variants for social media content.

    Falls back to mock hooks when LLM is unavailable.
    """
    product = mission.get("product", "the product")
    scenario = _join(mission.get("target_topics"), "storytelling")
    selected_tone = (tone or mission.get("brand_tone") or "").strip() or "on-brand"
    selected_checklist = list(checklist if checklist is not None else mission.get("quality_checklist") or [])

    if is_llm_available():
        system_prompt = (
            "You are a social media copywriter. Generate exactly 3 short, "
            "punchy hooks for a creator collaboration video. "
            "Stay inside the supplied product, market and creator facts. "
            "Honor the selected brand tone. "
            "Return one hook per line, no numbering or bullets."
        )
        result = _call_llm(
            system_prompt,
            _grounding_facts(mission, creator, tone=selected_tone, checklist=selected_checklist),
        )
        if result:
            hooks = [line.strip() for line in result.strip().split("\n") if line.strip()]
            if hooks:
                return hooks[:3]

    # Fallback: mock hooks grounded in mission facts
    return [
        f"{selected_tone} opener: one camera. Every angle. This is the {product}.",
        f"What if you never missed the {scenario} shot?",
        f"I stopped choosing the frame. {product} kept the {selected_tone.lower()} story open.",
    ]


# ─── Script Generation ─────────────────────────────────────────


def generate_script(
    mission: dict[str, Any],
    creator: dict[str, Any],
    *,
    tone: str | None = None,
    checklist: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Generate a 30-60 second video script outline.

    Falls back to mock script when LLM is unavailable.
    """
    product = mission.get("product", "the product")
    scenario = _join(mission.get("target_topics"), "storytelling")
    market = mission.get("market", "the target market")
    selected_tone = (tone or mission.get("brand_tone") or "").strip() or "on-brand"
    selected_checklist = list(checklist if checklist is not None else mission.get("quality_checklist") or [])

    if is_llm_available():
        system_prompt = (
            "You are a video script writer. Generate a concise 30-60 second "
            "script outline for a creator collaboration video. Include timestamps "
            "and scene descriptions. Stay inside the supplied facts. "
            "Honor the selected brand tone and quality checklist. "
            "Do not invent product specs. Keep it under 200 words."
        )
        result = _call_llm(
            system_prompt,
            _grounding_facts(mission, creator, tone=selected_tone, checklist=selected_checklist),
        )
        if result:
            return result

    checklist_note = _join(selected_checklist, "none selected")
    return (
        f"0-3s: Immersive {selected_tone} hook — {creator.get('creator_name', 'the creator')} in {market} with {product}\n"
        f"3-15s: Creator challenge — setting up a real {scenario} shot\n"
        f"15-35s: Product proof — {product} demonstrated in a live use case\n"
        f"35-48s: Reframing reveal — showing the unique angle ({checklist_note})\n"
        f"48-60s: Creator verdict and CTA for {product}"
    )
