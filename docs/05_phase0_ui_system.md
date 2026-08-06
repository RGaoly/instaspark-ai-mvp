# Phase 0 UI System

## Objective

Rebuild the Streamlit front end to match the visual and workflow language in the
InstaSpark AI opening report, especially pages 9-15:

1. Launch Mission Dashboard
2. Creator Opportunity
3. Creator Search & Match
4. Creator Compare
5. Content Studio
6. Outreach Operations
7. Growth Review

## Design principles

- Light enterprise workspace rather than a dark marketing landing page.
- Fixed 228 px navigation rail with one source of navigation.
- Dense 12-column dashboard layout optimized for 1440-1600 px screens.
- Yellow is reserved for primary actions and mission state.
- Blue communicates information, green communicates healthy outcomes, and
  orange/red communicate risks.
- Tables support scanning; detail panels support decision-making.
- Every page has a visible next action.

## Phase 0 boundaries

This release provides a polished, interactive front-end demonstration using
synthetic data and in-memory session state. Production data connectors,
persistent workflow events, model calls, and attribution pipelines remain later
phases.

## Compatibility

- Streamlit 1.39 or later
- Python 3.9 or later
- No external JavaScript framework
- No external image or font dependency
