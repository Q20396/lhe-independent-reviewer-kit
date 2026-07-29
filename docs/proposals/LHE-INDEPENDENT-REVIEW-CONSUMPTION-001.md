# LHE Independent Review Consumption 001

**Status:** `PROPOSAL_ONLY`
**Owner:** human-reviewed LHE governance
**Implementation state:** not implemented

## Purpose

Define the smallest safe interface by which an LHE proposal may reference an
Independent Reviewer Kit Delivery Bundle. The interface transports evidence and
limits; it does not transport authority.

## Required immutable inputs

An LHE-side proposal may reference all of the following, exactly:

1. target commit and tree;
2. target-identity manifest SHA-256;
3. the complete target-identity manifest, or an immutable content-addressed
   locator from which its exact bytes can be retrieved;
4. delivery-bundle SHA-256;
5. reviewer-kit commit and tree;
6. review-contract SHA-256;
7. changed-path and object-delta SHA-256 values; and
8. limitations and evidence references verbatim or by immutable locator.

The consumer must rehash the supplied manifest bytes and compare the result
with the Bundle's `target_identity_manifest_sha256`. It must then extract the
manifest's candidate commit and tree and compare both with the LHE proposal's
candidate identity; the manifest commit must also equal the Bundle's
`target_commit`. A mismatch, absent field, unreadable immutable locator,
unverifiable hash, or unsupported schema version is a fail-closed
`UNVERIFIED` result.

## Authority invariants

The consumer must reject a Bundle unless:

```text
human_disposition = pending
next_stage_authorized = false
```

Even a structurally valid Bundle has no authority to create a branch, modify a
file, run a provider, install software, access a network, merge, tag, release,
update an installed skill, or promote a candidate. A human may use it to decide
whether to authorize a separate implementation envelope only.

## Consumer result

The only allowed consumer results are:

```text
UNVERIFIED
REQUIRES_HUMAN_DECISION
EVIDENCE_CONFLICT
```

`ACCEPT`, `PASS`, `ELIGIBLE`, `VERIFIED`, `APPROVED`, `PROMOTED`, and
`RELEASE_READY` are forbidden consumer outcomes. This proposal deliberately
does not define an automatic success outcome.

## External architecture boundary

ECC, Graphify, Planning With Files, and other providers may appear only in an
independent Bundle as declared comparative evidence. The LHE consumer must not
install, import, execute, attach, route to, persist data through, or infer
availability from any provider. A future provider requires its own immutable
manifest, default-disabled disposition, explicit effect approval, and separate
implementation envelope.

## Acceptance criteria for a future implementation

- schema validation rejects missing or mismatched identity/hash fields;
- the consumer rehashes the supplied identity manifest and rejects manifest,
  commit, or tree mismatches across manifest, Bundle, and LHE proposal;
- a forged but correctly formatted target or manifest SHA fails closed;
- any authority-escalating Bundle value fails closed;
- recommendations can be displayed but cannot trigger actions;
- a supplied Bundle with external-provider evidence remains non-callable;
- tests prove no filesystem write, process launch, provider loading, network,
  Git operation, install, persistence, merge, tag, or release is performed;
- the implementation documents that it is static input validation, not
  independent review, runtime enforcement, or host enforcement.

## Non-goals

This proposal does not authorize LHE code changes, an LHE runtime database,
background scanners, hooks, an agent swarm, provider installation, remote
connectors, credential access, or persistent project memory.

## Decision gate

Before any LHE implementation, a human must approve a new, exact-path
Implementation Envelope after reviewing this proposal and a fresh target-bound
independent Bundle. This document itself grants nothing.
