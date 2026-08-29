# Feature Specification: Alternate Inference Endpoint

**Feature ID**: `008-alternate-inference-endpoint`

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Business Capability**: Provider Portability

**Business Actors**: Critic agent; Orchestrator; Operator

**Input**: User description: "Serve one of the system's reasoning roles from a self-hosted model on independent GPU infrastructure, selected by configuration, with automatic fallback to the primary provider."

## Business Context

### Business Goal

Serve one of the system's reasoning roles from a self-hosted model on independent
GPU infrastructure, selected by configuration, with automatic fallback to the
primary provider.

### Business Value

The system's reasoning layer is provider-agnostic by design. Demonstrating that
claim against a genuinely different provider — rather than asserting it — is what
makes the port boundary real. The critic role is the natural candidate: it is
high-volume, structurally simple, and its output is validated against a schema
before use, so a weaker model is tolerable where a frontier model is not.

### Governance

This is the additive second-sponsor integration governed by **Constitution
Article VIII**. It is provisioned as a background task from a fixed time,
assessed once, and deleted from the configuration if it is not serving by then.
It must never be on the critical path of the demonstration, and **no other
specification may depend on it**. When its configuration is unset, the whole
system behaves exactly as it does today.

### Dependencies

This feature **composes** the following and changes none of their behaviour when
its configuration is unset:

- **Specification 002 — Step Execution and Evidence**: the alternate endpoint is
  addressed through the same reasoning port; its responses go through the same
  structured-schema rejection mechanism.
- **Specification 005 — Critic Evaluation and Promotion**: the routed role is the
  critic; the alternate response is validated with the same schema
  (`validate_verdict`); the alternate wait bound is derived from the critic wait
  bound; the deterministic exit-status ranking remains the final safety net after
  the primary provider.
- **Specification 006 — Timeline Console**: the console shows, for each verdict,
  which provider produced it.
- **Specification 007 — Demo Harness**: the alternate endpoint's latency must not
  push the demonstration path past its declared budget.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A reasoning role runs on a different provider, by config alone (Priority: P1)

The operator points the critic role at a self-hosted endpoint by setting its
configuration — an endpoint address and a model name. On the next run, the
critic's verdict is produced by that endpoint. No code is changed; unsetting the
configuration restores the previous behaviour.

**Why this priority**: This is the feature and the point Article VIII makes — the
port boundary is real only if a genuinely different provider can be swapped in by
configuration.

**Independent Test**: With the alternate configuration set to a reachable
endpoint, run a round that requires a verdict; confirm the verdict was produced
by the alternate endpoint and that no code differs from the run with it unset.

**Acceptance Scenarios**:

1. **Given** the alternate endpoint configuration is set and the endpoint is
   reachable, **When** a verdict is needed, **Then** the request goes to the
   alternate endpoint and its response is used.
2. **Given** the alternate configuration is unset, **When** a verdict is needed,
   **Then** the request goes to the primary provider and the system behaves
   exactly as before this feature.
3. **Given** the alternate configuration is changed between runs, **When** each
   run produces a verdict, **Then** the change takes effect with no code
   modification.

---

### User Story 2 - The alternate response is held to the same standard (Priority: P1)

A response from the alternate endpoint is addressed through the same reasoning
port and validated against the same schema as a primary-provider response. A
non-conforming response from the alternate endpoint is rejected the same way a
non-conforming primary response is rejected.

**Why this priority**: A weaker model is tolerable for the critic precisely
because its output is schema-checked before use. If the alternate got a softer
check, "provider-agnostic" would be a lie and a malformed verdict could reach the
promotion.

**Independent Test**: Feed the alternate endpoint a prompt that elicits a
malformed verdict; confirm it is rejected by the identical schema check applied
to the primary, and that the run proceeds to fallback rather than acting on the
bad response.

**Acceptance Scenarios**:

1. **Given** the alternate endpoint returns a structurally valid verdict, **When**
   it is validated, **Then** it passes the identical schema check the primary's
   response passes.
2. **Given** the alternate endpoint returns a non-conforming response, **When**
   it is validated, **Then** it is rejected by the same rule that rejects a
   non-conforming primary response, and the run proceeds to fallback.
3. **Given** the same malformed response shape, **When** it comes from the
   primary and from the alternate, **Then** both are rejected identically.

---

### User Story 3 - Failure of the alternate never stalls the run, and is recorded (Priority: P1)

When the alternate endpoint is unreachable, times out within its bound, or
returns a response that fails validation, the system falls back to the primary
provider. If the primary also fails, the deterministic exit-status ranking takes
over. Every verdict records which provider produced it — the alternate, the
primary, or the deterministic fallback.

**Why this priority**: Article VIII — the additive integration must never be on
the critical path. A demo that hangs because a self-hosted GPU box is slow is a
failed demo. And Article X — the record must say which provider judged, so the
claim is truthful.

**Independent Test**: Run a round three ways — alternate unreachable, alternate
timing out, alternate returning junk — and separately a run where the primary
also fails; confirm a winner is promoted in every case and the verdict record
names the provider that actually produced it.

**Acceptance Scenarios**:

1. **Given** the alternate endpoint is unreachable, **When** a verdict is needed,
   **Then** the primary provider produces it and the verdict record says
   "primary".
2. **Given** the alternate endpoint does not respond within its bound, **When**
   the bound elapses, **Then** the primary provider produces the verdict and the
   record says "primary"; the wait did not exceed the bound.
3. **Given** the alternate endpoint returns an invalid response, **When** it is
   rejected, **Then** the primary provider produces the verdict and the record
   says "primary".
4. **Given** the alternate and the primary both fail, **When** the verdict is
   produced, **Then** the deterministic exit-status ranking decides it and the
   record says "deterministic-fallback".
5. **Given** any successful alternate verdict, **When** the record is read,
   **Then** it says "alternate".

---

### User Story 4 - The alternate's latency cannot overrun the demonstration budget (Priority: P1)

The time the system waits on the alternate endpoint is bounded, and that bound is
set so that a slow alternate — even one that times out on every call — cannot push
the demonstration path past its declared budget.

**Why this priority**: Constitution Articles VIII and XI — the demonstration runs
live within two minutes; a self-hosted endpoint on independent infrastructure is
exactly the kind of thing that is slow at the wrong moment.

**Independent Test**: Configure the alternate endpoint to be slower than its
bound; run the demonstration path; confirm the path completes within its budget
and every verdict fell back to the primary within the bound.

**Acceptance Scenarios**:

1. **Given** an alternate endpoint slower than its bound, **When** a verdict is
   requested, **Then** the system waits no longer than the bound before falling
   back.
2. **Given** the alternate times out on every verdict of a demonstration run,
   **When** the run completes, **Then** the total path time is still within the
   demonstration budget.
3. **Given** the alternate bound, **When** it is compared to the critic wait
   bound, **Then** it is no greater — the alternate cannot wait longer than the
   critic role is already allowed.

---

### User Story 5 - The console shows who judged (Priority: P2)

For every verdict the console displays which provider produced it — alternate,
primary, or deterministic fallback — so a viewer, and a judge, can see the
provider-portability claim being exercised rather than asserted.

**Why this priority**: The business value is *demonstrating* portability. If the
screen does not say which provider judged, the demonstration is back to
assertion.

**Independent Test**: Run a round served by the alternate and a round that fell
back to the primary; open the console; confirm each verdict shows the correct
provider label.

**Acceptance Scenarios**:

1. **Given** a verdict produced by the alternate endpoint, **When** the console
   renders it, **Then** it shows the provider as the alternate.
2. **Given** a verdict that fell back to the primary, **When** the console
   renders it, **Then** it shows the provider as the primary.
3. **Given** a verdict decided by the deterministic ranking, **When** the console
   renders it, **Then** it shows the provider as the deterministic fallback.

---

### User Story 6 - Undelivered, the demonstration is still complete and truthful (Priority: P1)

If this feature is not delivered — the alternate endpoint is never provisioned or
is deleted from the configuration after the one-time assessment — the
demonstration runs unchanged, the whole system behaves as it did before, and
nothing in the demonstration claims an alternate provider was used.

**Why this priority**: Article VIII — the additive integration carries a stop
line; if it is reduced to decoration by time pressure, that is stated plainly and
the demo does not overclaim.

**Independent Test**: With the alternate configuration unset, run the full test
suite and the demonstration path; confirm every result is identical to a run
before this feature existed and no output mentions an alternate provider.

**Acceptance Scenarios**:

1. **Given** the alternate configuration is unset, **When** the full offline test
   suite runs, **Then** every prior test passes unchanged.
2. **Given** the alternate configuration is unset, **When** the demonstration
   path runs, **Then** it is byte-for-byte the same path as before this feature,
   and the verdict record says "primary" (or "deterministic-fallback").
3. **Given** the alternate endpoint was assessed and found not serving, **When**
   its configuration is removed, **Then** the system and the demonstration are
   unaffected and no claim of an alternate provider is made.

---

### Edge Cases

- What happens when the alternate configuration is partially set — an address but
  no model name, or the reverse? The alternate is treated as unset (absent):
  routing requires a complete configuration; an incomplete one is ignored, not an
  error.
- What happens when the alternate endpoint is reachable but consistently returns
  invalid verdicts? Every round falls back to the primary, every record says
  "primary", and the one-time assessment (a contract test) flags the alternate as
  not serving — it should then be removed from the configuration.
- What happens when the alternate endpoint succeeds on some rounds and fails on
  others within one run? Each verdict records its own provider; the run has a mix
  of "alternate" and "primary" records and that is correct, not an error.
- What happens when the primary provider is also unavailable and the alternate
  produced nothing usable? The deterministic exit-status ranking decides the
  verdict; the record says "deterministic-fallback"; the loop still closes.
- What happens when the alternate endpoint returns a valid verdict *after* its
  bound elapsed and the primary already produced one? The late alternate response
  is discarded; the primary's verdict stands; the record says "primary".
- What happens when the alternate configuration is set but points at an address
  that is not an inference endpoint at all? Treated as unreachable — fall back to
  primary, record "primary", and the contract test fails the availability check.
- What happens when a role other than the critic is pointed at an alternate
  endpoint? The same routing mechanism applies; only the critic is wired for the
  demonstration, but the requirement is general (any role, by configuration).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-008-01**: The system MUST permit any reasoning role to be routed to a
  distinct endpoint, selected by configuration (an endpoint address and a model
  name), with no code change to switch it on, off, or between endpoints.
- **FR-008-02**: The system MUST address the alternate endpoint through the same
  reasoning port as the primary provider — no separate interface, no bypass.
- **FR-008-03**: The system MUST validate a response from the alternate endpoint
  against the same schema, by the same rule, as a response from the primary
  provider, and MUST reject a non-conforming alternate response identically to a
  non-conforming primary response.
- **FR-008-04**: The system MUST fall back to the primary provider when the
  alternate endpoint is unreachable, does not respond within its bound, or
  returns a response that fails validation; MUST fall back to the deterministic
  exit-status ranking if the primary also fails; and MUST record, on each
  verdict, which provider produced it — one of "alternate", "primary", or
  "deterministic-fallback".
- **FR-008-05**: The system MUST bound the time it waits on the alternate
  endpoint, and that bound MUST be no greater than the critic wait bound, so a
  slow or unresponsive alternate cannot extend the demonstration path beyond its
  declared budget.
- **FR-008-06**: The system MUST make the producing provider of each verdict
  available for display, and the console MUST show it — "alternate", "primary",
  or "deterministic-fallback".
- **FR-008-07**: The system MUST treat the alternate endpoint as absent whenever
  its configuration is unset or incomplete, and in that condition MUST run
  identically to the system without this feature.
- **FR-008-08**: The alternate endpoint MUST be placed on the demonstration path
  only after a contract test has verified it is reachable and returns a
  conforming verdict; until then the demonstration uses the primary provider.

### Non-Functional Requirements

- **NFR-008-01**: Provisioning the alternate endpoint MUST be a background task,
  started from a fixed time and assessed once; no other specification may take a
  dependency on its availability, and its absence MUST NOT block or degrade any
  other feature.
- **NFR-008-02**: The alternate endpoint's availability MUST be verified by the
  contract-test layer (a live test, skipped when the configuration is unset)
  before it is used on the demonstration path.
- **NFR-008-03**: The demonstration MUST remain complete and truthful when this
  feature is not delivered — undelivered, the system and the demonstration are
  unchanged and make no claim of an alternate provider.
- **NFR-008-04**: The routing and fallback logic MUST be verifiable offline — a
  pure-logic layer with stub endpoints — separately from any live endpoint.

### Key Entities

- **Alternate Endpoint Configuration**: The address and model name that select a
  self-hosted endpoint for a reasoning role. Complete (both present) enables
  routing for that role; incomplete or unset means the role uses the primary
  provider.
- **Routed Reasoner**: The reasoning-port implementation for a role whose
  configuration selects an alternate endpoint. It tries the alternate first
  within the alternate wait bound, then the primary; it exposes which underlying
  provider answered the most recent call.
- **Primary Provider**: The existing reasoning endpoint used by every role by
  default and as the fallback for a routed role.
- **Alternate Wait Bound**: The maximum time to wait on the alternate endpoint
  before falling back — no greater than the critic wait bound.
- **Verdict Provider Label**: The value recorded on a verdict for which provider
  produced it — "alternate", "primary", or "deterministic-fallback". Surfaced by
  the console.
- **Availability Check**: The one-time contract test that confirms the alternate
  endpoint is reachable and returns a conforming verdict, gating its use on the
  demonstration path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With a complete alternate configuration and a reachable endpoint,
  100% of that role's verdicts are produced by the alternate endpoint and
  recorded as "alternate".
- **SC-002**: A non-conforming alternate response is rejected by the identical
  rule that rejects a non-conforming primary response, in 100% of cases, and the
  run proceeds to fallback.
- **SC-003**: When the alternate is unreachable, times out, or returns an invalid
  response, 100% of verdicts fall back to the primary and are recorded as
  "primary"; when the primary also fails, they are recorded as
  "deterministic-fallback".
- **SC-004**: The system never waits longer than the alternate wait bound on the
  alternate endpoint, and that bound is ≤ the critic wait bound.
- **SC-005**: A demonstration run in which the alternate times out on every
  verdict still completes within the demonstration budget.
- **SC-006**: The console shows the correct producing provider for 100% of
  verdicts.
- **SC-007**: With the alternate configuration unset, 100% of the pre-existing
  offline test suite passes unchanged, and the demonstration path is identical to
  a run before this feature.
- **SC-008**: No specification 000–007 changes behaviour, and no test 000–007
  changes outcome, as a result of this feature when the alternate is unset.
- **SC-009**: The alternate endpoint is used on the demonstration path only after
  its availability check has passed.
- **SC-010**: The routing and fallback logic passes its tests with stub
  endpoints, no network, and no credentials.

## Assumptions

- **The routed role for the demonstration is the critic** (Specification 005),
  selected by `CRITIC_BASE_URL` and `CRITIC_MODEL` in the environment; both unset
  means no alternate. The mechanism is general to any reasoning role, but only
  the critic is wired for the demonstration.
- **The same reasoning port** is Specification 002's reasoning port; **the same
  schema** is Specification 005's verdict validation.
- **The primary provider** is the existing reasoning endpoint (`LLM_BASE_URL` /
  `LLM_MODEL`).
- **The alternate wait bound is derived from Specification 005's critic wait
  bound** — the same value or a fraction of it — so the demonstration budget
  (Specification 007) cannot be exceeded by the alternate's latency.
- **"Which provider produced it" is recorded on the verdict record**
  (Specification 005) as one of "alternate" / "primary" /
  "deterministic-fallback", and the console (Specification 006) surfaces it.
- **The deterministic exit-status fallback** (Specification 005, FR-005-07)
  remains the final safety net, tried after the primary provider.
- **Provisioning the self-hosted endpoint is operational work** — standing up a
  model server on independent GPU infrastructure — done as a background task and
  not part of this repository's code. This feature is the routing, the fallback,
  the recording, and the availability check.
- **"No code change" to switch endpoints** means the selection is entirely by
  configuration read at run start; changing `CRITIC_BASE_URL` between runs is
  sufficient.
- **The offline layer uses stub endpoints** — in-process objects that stand in
  for the alternate and primary — so routing and fallback are tested with no
  network.

## Out of Scope

- Training or fine-tuning the self-hosted model.
- Routing by cost, load, latency history, or any policy other than
  "alternate first, then primary, then deterministic".
- Any dependency of another specification on this one — 000–007 must not import,
  assume, or require the alternate endpoint.
- Provisioning scripts or infrastructure-as-code for the GPU server — that is
  operational, not part of this feature.
- Routing more than one role to an alternate endpoint in the demonstration — the
  mechanism is general but only the critic is wired.
- Caching, batching, or streaming alternate responses.
- Any change to the primary provider or to the strategist role.
