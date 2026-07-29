# ADR-0003: Pinned LHE Policy Snapshot Checker

**Status:** Proposal
**Design state:** Proposed
**Implementation state:** Not implemented

## Context

The platform must assess whether a recommendation is compatible with LHE's
governance principles, while remaining independent of LHE's live checkout,
runtime, installed skill, and self-description.

## Decision

The Policy Checker consumes an explicitly supplied, immutable LHE policy
snapshot. A snapshot must identify:

```text
source repository locator
commit and tree identity
selected policy paths
path inventory hash
content hashes
retrieved-at time
known limitations
```

The checker may return only:

```text
eligible
blocked
unverified
requires_human_decision
```

`eligible` means the supplied static policy snapshot contains no detected
contract conflict. It never means that a provider may execute or that an LHE
change is approved.

## Required checks

Before a recommendation can be marked eligible, the checker must establish:

1. target identity is valid;
2. the selected profile and packs are declared;
3. requested permissions and side effects are disclosed;
4. a bounded evidence plan and limitations are present;
5. a recommendation envelope does not claim merge, release, installation, or
   runtime authority.

## Non-goals

- Dynamic import of LHE Python, scripts, plugins, or installed skills.
- Treating LHE as the platform's source of truth.
- Replacing human legal, operational, or release decisions.

## Consequences

LHE provides a versioned policy language, not a controlling runtime. The
platform remains able to identify gaps in that language through its external
review packs.
