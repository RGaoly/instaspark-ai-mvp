# Phase 0 — Product Architecture Refactor

## Goal

Establish a stable dual-entry, seven-route Streamlit product shell aligned with
the InstaSpark AI P0 product contract:

1. Launch Mission
2. Creator Opportunity
3. Creator Search & Match
4. Creator Compare
5. Content Studio
6. Outreach Operations
7. Growth Review

## Deliverables

- Shared black / navy / yellow visual system
- Streamlit multipage navigation
- Shared page header, mission context and card components
- Service boundaries for mission, matching, content, campaign and learning
- Structural tests
- No new business logic yet

## Acceptance criteria

- `streamlit run app.py` opens Mission Control.
- Both entry pages and all five shared-workspace pages can be opened from the sidebar.
- All downstream pages derive their label and filters from one active context.
- State changes follow the shared collaboration state machine and retain audit evidence.
- All pages share the same visual system.
- No page raises an exception.
- Existing scoring tests continue to pass.
- New Phase 0 structural tests pass.
