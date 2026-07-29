# ADR-0001: Independent Review Platform Constitution

**Status:** Proposal
**Design state:** Proposed
**Implementation state:** Not implemented

## Context

The Independent Reviewer Kit verifies commit-bound target identity and evidence
bindings. It must remain able to review LHE from outside LHE. The broader
platform may use ECC-inspired catalogs, profiles, adapters, and diagnostics,
but those conveniences must not let the reviewed system approve or verify
itself.

## Decision

The platform has five distinct planes:

```text
Trust Kernel -> Review Catalog -> Review Packs -> Policy Checker -> Delivery
```

- **Trust Kernel** derives target identity, validates evidence artifacts, and
  verifies non-authorizing verdict contracts.
- **Review Catalog** describes selectable review modules, components, and
  profiles.
- **Review Packs** implement independent review lenses such as governance,
  productization, code-context provenance, and workstream resilience.
- **Policy Checker** evaluates a pinned LHE policy snapshot as an input. It
  never imports, executes, or treats live LHE as the review authority.
- **Delivery** packages findings, evidence references, limitations, and a
  recommendation envelope for a human decision.

## Invariants

1. A reviewed target and this platform must have distinct Git common
   directories and non-overlapping canonical worktree roots.
2. No review profile, pack, adapter, or doctor grants execution, merge,
   release, installation, network, hook, persistence, or configuration
   authority.
3. `declared`, `installed`, `callable`, `observed`, and `verified` are
   distinct states.
4. A provider result, recommendation, successful check, or verdict does not
   grant human approval or promotion authority.
5. The platform may recommend an LHE implementation envelope, but cannot
   modify LHE without a separately authorized task in the LHE repository.

## Non-goals

- Replacing ECC, Graphify, Planning With Files, or LHE.
- Running target code, target hooks, or target installers.
- Creating a hosted runtime, persistent global memory, or background scanner.
- Proving human independence, trusted host integrity, signatures, attestation,
  semantic correctness, or release authorization.

## Consequences

The platform can evolve an ECC-like product surface without becoming a large
agent runtime. Extra capability remains review-pack content and must pass
through the Trust Kernel and Policy Checker before it can influence an LHE
recommendation.
