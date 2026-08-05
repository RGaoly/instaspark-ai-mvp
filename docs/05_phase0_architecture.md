# Phase 0 — Product Architecture Refactor

## Goal

Establish a stable six-module Streamlit product shell aligned with the original
InstaSpark AI construction blueprint:

1. Launch Mission
2. Creator Search & Match
3. Creator Compare
4. Content Studio
5. Outreach Operations
6. Growth Review

## Deliverables

- Shared black / navy / yellow visual system
- Streamlit multipage navigation
- Shared page header, mission context and card components
- Service boundaries for mission, matching, content, campaign and learning
- Structural tests
- No new business logic yet

## Acceptance criteria

- `streamlit run app.py` opens Mission Control.
- All six pages can be opened from the sidebar.
- All pages share the same visual system.
- No page raises an exception.
- Existing scoring tests continue to pass.
- New Phase 0 structural tests pass.
