# ADR-0008: Dual-Axis Review Input

## Status

Accepted as a static contract. It is not a review runner, provider integration,
or authority mechanism.

## Decision

An independent review input declares two non-interchangeable axes:

- **Spec**: whether a candidate matches a supplied requirement source.
- **Standards**: whether a candidate matches a supplied standards source.

Both axes are always requested. An axis may state `not-available`, but that is
an explicit review limitation, not a pass. A provided source has a kind,
locator, and content hash. An unavailable axis has only a controlled `none`
kind and locator explaining the absence; it must not claim a source-content
hash. The input also binds a review-request identity and target commit.

This borrows the useful separation in external engineering workflows without
running their skills, agents, installers, hooks, or subagents.

## Non-goals

- resolving a target checkout or reading its files;
- fetching issue trackers or external documents;
- evaluating source truth or code semantics;
- starting review workers or subagents;
- granting network, filesystem, Git, merge, release, installation, or provider
  permissions.

## Authority

`human_disposition` is always `pending`; promotion is `not-promoted`; and the
next stage remains unauthorized. A structurally valid input only permits later
human selection of a separately scoped review run.
