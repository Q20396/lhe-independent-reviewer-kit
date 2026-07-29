# ADR-0004: External Review Pack Contract

**Status:** Proposal
**Design state:** Proposed
**Implementation state:** Not implemented

## Context

Reviewing LHE only through LHE's own concepts creates blind spots. ECC,
Graphify, and Planning With Files provide useful external perspectives, but
must not become undeclared runtime dependencies or authorities.

## Decision

Every review pack produces a structured, non-authorizing recommendation:

```text
pack identity
target identity
questions asked
source statements and locators
evidence references
FACT / INFERENCE / UNKNOWN separation
findings and limitations
proposed implementation envelope
acceptance criteria
non-goals and rollback
```

Initial packs are:

| Pack | External question it asks |
|---|---|
| `lhe-governance` | Are scope, authority, evidence, recovery, and promotion boundaries explicit? |
| `ecc-productization` | Are capabilities discoverable, profile-selectable, diagnosable, and reversible? |
| `graph-context-provenance` | Can architecture claims be tied to commit-bound structural evidence and source locations? |
| `workstream-resilience` | Can a long task resume with minimal non-sensitive state after context loss? |
| `release-assurance` | Are release claims distinguishable from tag, CI, installed, and runtime facts? |

## Boundaries

- External-tool statements are comparative source statements, not authority.
- A Graphify-like pack may initially consume only supplied static artifacts;
  it may not scan a target checkout or install Graphify.
- A Planning With Files-like pack may review a supplied state contract; it may
  not read IDE session stores or create persistent task files by default.
- An ECC-like pack may review catalog/profile ergonomics; it may not install
  agents, rules, hooks, or user-level configuration.

## Consequences

The platform gains genuinely different review lenses without copying external
code, claiming their behavior, or broadening the current authority boundary.
