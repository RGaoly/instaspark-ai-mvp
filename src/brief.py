from __future__ import annotations


def generate_brief(mission: dict, creator: dict) -> str:
    product = mission["product"]
    market = mission["market"]
    scenario = ", ".join(mission["target_topics"])
    creator_name = creator["creator_name"]

    if mission["language"].lower().startswith("span"):
        return f"""# Brief de colaboración — {product}

**Creador:** {creator_name}  
**Mercado:** {market}

## Objetivo
Mostrar cómo {product} ayuda a capturar escenas de {scenario} con una narrativa natural y creíble.

## Mensajes obligatorios
- Demostrar el producto en una situación real.
- Explicar la propuesta de valor con palabras propias.
- Incluir una llamada a la acción clara.

## Entregables sugeridos
- 1 video vertical de 30–60 segundos
- 2 clips cortos reutilizables
- 3 fotos o miniaturas

## Guardrails
- No inventar especificaciones.
- No hacer comparaciones no verificadas.
- Confirmar permisos de música, imagen y uso publicitario.
"""

    return f"""# Collaboration Brief — {product}

**Creator:** {creator_name}  
**Market:** {market}

## Objective
Show how {product} supports real-world {scenario} storytelling in the creator's native style.

## Mandatory messages
- Demonstrate the product in a real use case.
- Explain the value proposition in the creator's own words.
- Include a clear call to action.

## Suggested deliverables
- 1 vertical video, 30–60 seconds
- 2 reusable short clips
- 3 stills or thumbnails

## Guardrails
- Do not invent specifications.
- Avoid unverified competitor comparisons.
- Confirm music, likeness, whitelisting, and paid-usage rights.
"""
