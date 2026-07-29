# ADR-0005: Review Advisor and Doctor

**Status:** Proposal
**Design state:** Proposed
**Implementation state:** Not implemented

## Context

ECC's catalog, profile, preview, and doctor experience reduces the cost of
choosing an appropriate capability. An independent review platform should
offer the same clarity, but its advisor must not silently repair, install, or
activate anything.

## Decision

The future Advisor accepts a user goal, target identity, declared environment,
and allowed permission set. It returns a proposed review profile, selected
packs, required evidence, exclusions, and a human-decision boundary.

The future Doctor reports stable states and reason codes:

```text
declared
locally_observed
unverified
blocked
unsupported
```

It may report an exact preview plan, such as files that a future sandbox task
would read or write. It may not run that plan.

## Required output

```text
profile recommendation
module and pack identities
target compatibility
permission and side-effect summary
missing evidence
limitations
recommended next safe action
```

## Non-goals

- Auto-install, repair, sync, update, or uninstall.
- Network discovery, credential access, account operations, or hooks.
- Declaring an external provider installed, callable, or verified from a
manifest alone.

## Consequences

The platform can become easy to use like ECC while retaining the rule that a
diagnostic report is evidence, not authority.
