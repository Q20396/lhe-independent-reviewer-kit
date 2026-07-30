# ADR 0007: Declared-Disabled Provider Lifecycle

Status: Accepted contract boundary; no provider is implemented or activated.

## Decision

An external provider may be recorded only as `declared_disabled` when a
public-read-only intake has bound its repository, commit, tree, parent, and
selected source blobs. The record is neither an installation instruction nor a
capability grant.

The LangGraph Swarm example is a worker-orchestration candidate. ECC is a
workflow-pack candidate with a materially wider installation and runtime
surface. Both remain outside the reviewer runtime and have no default effects.

## Required promotion sequence

1. Client selects a concrete task and explicitly approves a provider trial.
2. A separate intake fixes the exact package closure, distributions, hashes,
   licenses, platform, and known-risk review.
3. A separate isolated-run envelope defines model credentials, network,
   tools, data classification, state boundary, stop conditions, and evidence.
4. An independent review evaluates the resulting evidence. It cannot grant a
   promotion, release, installation, or LHE change.

No document can skip a stage. Customer authority remains `pending`; an example
manifest never makes a provider callable.

## Non-goals

- installing ECC, LangGraph Swarm, Graphify, or Planning With Files. In
  particular, an ECC installer must not be run because its documented clone
  path can install Node dependencies;
- hooks, background scanning, automatic routing, persistent provider state, or
  model/API credential use;
- changing LHE or making the reviewer kit a worker orchestration runtime.
