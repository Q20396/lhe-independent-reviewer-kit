# ADR-0009: Tracer-Bullet Dependency Map

## Status

Accepted as a dependency-free, static planning contract.

## Decision

Large work is represented as small, independently verifiable tracer bullets.
Each item declares a deliverable, acceptance criteria, evidence references, and
blocking item identifiers. The map rejects duplicate IDs, unknown blockers,
self-blockers, and cycles.

This adopts the useful vertical-slice and explicit-blocker ideas from external
engineering workflows. It does not create issues, select workers, run a
provider, mutate a target repository, or execute a planned item.

## Authority

Every item stays `proposed`, declares no effects, and has execution disabled.
The map itself and its items retain no approval state. Client authority remains
pending at the map level.

## Non-goals

- automatic ticket/issue creation;
- automatic frontier selection or dispatch;
- background work, subagents, hooks, or network access;
- replacing a target project's own tracker or plan.
