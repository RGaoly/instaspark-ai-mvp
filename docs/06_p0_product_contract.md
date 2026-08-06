# P0 Product Contract: Dual-entry Creator Operations

Status: implementation contract for P0  
Audience: product, design, engineering, and acceptance-test owners  
Scope: the local Streamlit MVP; synthetic data remains acceptable

## 1. P0 outcome

P0 establishes one coherent product and engineering contract before persistence,
real integrations, or a production pilot are added. A reviewer must be able to
enter the product from either a launch plan or a creator-led signal, then see the
same creator-collaboration context and state across the downstream workspace.

P0 is complete only when the two entry points, shared context, core object
boundaries, and state transitions below are represented in the product and
covered by automated structural tests.

## 2. Information architecture and the two entry points

`Launch Mission` and `Creator Opportunity` are peer, first-level navigation
entries. Neither is a renamed version or child step of the other.

### Entry A: Launch Mission

Use this entry when the business starts with a product, market, campaign, or
growth objective and needs to find suitable creators.

Minimum P0 flow:

1. Create or open a Mission.
2. Set that Mission as the active root context.
3. Search, rank, and compare candidate Creators through Match records.
4. Record a human Decision and advance the collaboration state.
5. On approval, create or reuse the corresponding OutreachCase.

### Entry B: Creator Opportunity

Use this entry when the business starts with an observed creator, content trend,
inbound request, or market signal before a launch mission has been selected.

Minimum P0 flow:

1. Open a list of opportunities and select one Opportunity.
2. Set that Opportunity as the active root context.
3. Review its Creator, market, evidence, source, and suggested next action.
4. Qualify or reject it through the same collaboration state machine.
5. An accepted opportunity may be linked to an existing Mission or used to
   create a Mission; that link must preserve the Opportunity and its evidence.
6. On approval, create or reuse the corresponding OutreachCase.

### Shared workspace

`Creator Search & Match`, `Creator Compare`, `Content Studio`, `Outreach
Operations`, and `Growth Review` are downstream workspace views. Their page
headers and context chips must be derived from the active context. They must not
claim a hard-coded product, market, or mission that can conflict with it.

## 3. Core objects and relationships

P0 may keep these objects in Streamlit session state; the names and identifiers
form the migration boundary for a future database.

| Object | Stable identity and minimum responsibility | Key relationships |
| --- | --- | --- |
| `Mission` | `mission_id`; product, objective, markets, language, dates, budget, owner, mission status | Has many Matches, ContentAssets, OutreachCases, and PerformanceEvents |
| `Opportunity` | `opportunity_id`; opportunity type, title, market, status, source, observed time, evidence, suggested action | Belongs to one Creator; may link to zero or one Mission in P0 |
| `Creator` | `creator_id`; durable creator/profile facts | Has many Opportunities and Matches |
| `Match` | `match_id`; creator-to-mission score, gate result, rationale, evidence snapshot | Belongs to exactly one Mission and one Creator |
| `Decision` | `decision_id`; actor, decision, reason code, note, timestamp | Refers to a Creator and the active Mission or Opportunity |
| `OutreachCase` | `outreach_case_id`; owner, collaboration state, channel, next action, timestamps | Refers to a Creator and at least one Mission or Opportunity |
| `ContentAsset` | `content_asset_id`; type, locale, version, review status, provenance | Refers to a Creator and normally a Mission; may preserve its originating Opportunity |
| `PerformanceEvent` | `performance_event_id`; metric, value, time window, source | Refers to a Creator and to the Mission, OutreachCase, or ContentAsset that caused it |

Relationship invariants:

- Every cross-page reference uses IDs, not product names or creator display names.
- Linking an Opportunity to a Mission is additive: the Opportunity remains
  independently addressable and retains its source and evidence.
- A Mission-Creator pair has at most one active Match.
- An approved collaboration has at most one active OutreachCase for the same
  Creator and root context. Repeating approval is idempotent.
- A Decision and state transition record their actor, timestamp, reason, and root
  context so the action is auditable.
- Performance metrics without a source and related IDs are demo-only and must be
  labelled as such; they cannot be presented as attributed outcomes.

## 4. Active-context contract

All downstream pages consume a single session-level active-context object through
the following public functions in `components/state.py`:

- `active_context()` returns a defensive copy of the current context.
- `set_active_context(...)` changes the root context and validates the referenced
  Mission or Opportunity.

The context contains:

| Field | Meaning |
| --- | --- |
| `entry_type` | `mission` or `opportunity` |
| `mission_id` | Active/linked Mission ID, otherwise `None` |
| `opportunity_id` | Active/originating Opportunity ID, otherwise `None` |
| `creator_id` | Selected Creator ID, otherwise `None` |
| `label` | Human-readable label generated from the referenced data |

Rules:

- A context has exactly one root: `mission_id` when `entry_type=mission`, or
  `opportunity_id` when `entry_type=opportunity`.
- Linking an opportunity to a mission may populate both IDs, but `entry_type`
  continues to identify the root that the user entered through.
- Creator selection updates `creator_id` without silently changing the root.
- A page with no valid active root presents an explicit empty state and a link to
  one of the two entry points. It never substitutes a fixed demo label.
- Switching root clears incompatible page selections but does not delete domain
  records or audit history.

## 5. Unified collaboration state machine

Mission-first and opportunity-first work use one ordered state vocabulary:

```text
discovered -> qualified -> shortlisted -> approved -> contacted -> negotiating
           -> contracted -> content_in_review -> published -> measured
```

`closed_lost` is a terminal exit allowed from `discovered` through
`negotiating`. A creator may be disqualified during evaluation by moving to
`closed_lost` with a reason; published work is corrected through audit events,
not by silently rewinding it.

The public transition boundary is `transition_creator_state(...)`. It must:

1. reject transitions not in the allowed transition map;
2. append an audit event containing previous state, next state, actor, timestamp,
   reason, Creator ID, and active root IDs;
3. preserve the current state when validation fails; and
4. call `ensure_outreach_case(...)` when entering `approved`, so approval and the
   Outreach Operations view cannot diverge.

`ensure_outreach_case(...)` is idempotent and returns the existing active case or
creates exactly one case for the Creator and active root context.

## 6. P0 scope and non-goals

### In scope

- Peer routes for Launch Mission and Creator Opportunity.
- A useful synthetic Opportunity dataset/list and selection interaction.
- Shared active context and dynamic context labels on downstream pages.
- The core object shapes above represented as session-state records or typed
  dictionaries with stable IDs.
- Validated collaboration transitions, transition audit events, and automatic
  OutreachCase hand-off on approval.
- Documentation, repository map, and automated P0 structural acceptance tests.

### Non-goals

- A production database, authentication, roles, or multi-user concurrency.
- Live creator-platform ingestion, scraping, CRM, contract, payment, or messaging
  integrations.
- Model-backed generation, real campaign attribution, or production analytics.
- Full CRUD for every object, historical backfill, or migration tooling.
- Production hosting, monitoring, SLA enforcement, or a public pilot environment.

These are P1/P2 concerns. P0 must leave explicit interfaces for them without
claiming they are already delivered.

## 7. P0 acceptance criteria

P0 is accepted when all of the following are true:

1. Navigation exposes `Launch Mission` and `Creator Opportunity` as peer routes,
   and both routes render without an exception.
2. Selecting either root produces a valid `active_context()` and the downstream
   page label follows that context.
3. No view passes a fixed string literal to `mission_chip(...)`.
4. `components/state.py` exposes `active_context`, `set_active_context`,
   `transition_creator_state`, and `ensure_outreach_case`.
5. Invalid state transitions are rejected without mutation; valid transitions
   append an auditable event.
6. Entering `approved` creates one OutreachCase, and repeated approval or
   re-rendering does not create duplicates.
7. Opportunity-to-Mission linking preserves both IDs and the original evidence.
8. Existing scoring tests and all P0 structural tests pass.
9. README describes the dual-entry product, current demo limitations, complete
   project directory, local start command, and test command.

## 8. Deferred end-to-end scenarios

The following become required in P1 when persistence and UI testing are added:

- Mission path: Mission -> Match -> Decision -> OutreachCase.
- Opportunity path: Opportunity -> qualification -> Mission link -> OutreachCase.
- Cross-module path: approved collaboration -> ContentAsset -> publication ->
  attributable PerformanceEvent.

