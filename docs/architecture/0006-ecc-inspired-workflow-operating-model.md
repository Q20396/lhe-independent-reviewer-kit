# ADR-0006: ECC-Inspired Workflow Operating Model

**Status:** Proposal
**Design state:** Proposed
**Implementation state:** Not implemented

## Context

The platform needs a daily developer experience that is easy to discover and
use, while preserving the independent evidence and client-authority boundaries
of the Reviewer Kit. An ECC-inspired workflow model provides a useful product
shape: catalogued workflows, concise entry points, reusable playbooks, durable
task artifacts, and clear deliverables.

LHE is valuable for governance, evidence, release boundaries, and recovery,
but should not become the primary user interface, a general Agent runtime, or a
container for every workflow and provider.

## Decision

Adopt an ECC-inspired **Workflow Layer** as the primary operating model. Treat
LHE as an explicit, optional Governance Adapter. Keep the Independent Reviewer
Kit independent of both.

```text
Client goal / Spec
  -> Workflow Catalog
  -> Workflow Pack
  -> Workstream Capsule
  -> optional bounded Worker Provider
  -> Delivery artifacts

LHE Governance Adapter: invoked only when a declared risk boundary applies
Independent Reviewer Kit: independently binds target, evidence, and limits
Client: sole authority for execution, escalation, and disposition
```

## Responsibilities

| Plane | Owns | Must not own |
| --- | --- | --- |
| Workflow Layer | discoverability, Specs, playbooks, workstream progression, deliverables | approval, release authority, provider installation, global memory |
| Workstream Capsule | non-sensitive goal, acceptance criteria, phase, evidence references, blockers, next safe action | credentials, private source material, unrestricted logs, authority |
| Worker Provider | a client-approved, bounded run inside an explicit envelope | self-approval, scope expansion, persistent global state, promotion |
| LHE Adapter | policy, evidence requirements, high-risk gates, release/install boundaries | daily workflow UI, implicit routing, Swarm runtime |
| Independent Reviewer Kit | object identity, evidence bindings, limitations, non-authorizing delivery bundles | target execution, provider invocation, LHE modification |
| Client | permission, escalation, merge/release/install disposition | delegation by opaque agent output |

## Governance Adapter triggers

The Workflow Layer must request LHE governance only for declared risk classes,
including dependency changes, cross-boundary writes, external network/provider
use, credentials or sensitive data, merge/tag/release/installation actions, or
regulated-domain work. Low-risk drafting and static analysis do not require
LHE to dominate the workflow.

## Worker Provider boundary

A provider is `declared_disabled` by default. Before any one-run execution,
the client must separately approve the immutable provider source/version,
target, effects, allowed paths, network domains, tools, budget, stop conditions,
and rollback. A static manifest, receipt, test, or Bundle never supplies that
authorization.

## Non-goals

- copying ECC code, instructions, hooks, or distribution behavior;
- importing, installing, or invoking ECC, Graphify, Planning With Files, or a
  Swarm framework;
- an automatic router, global background scan, database, or persistent memory;
- embedding Agent runtime, worker dispatch, or provider lifecycle in LHE Core;
- treating a successful check or recommendation as client approval.

## Consequences

Future implementation begins with static Workflow Pack and Workstream Capsule
contracts in the independent platform. A future LHE change must be separately
enveloped, target-bound, independently reviewed, and client-approved. The
platform intentionally postpones real provider execution until a specific,
client-authorized provider intake is accepted.
