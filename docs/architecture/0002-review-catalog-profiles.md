# ADR-0002: Review Catalog, Modules, Components, and Profiles

**Status:** Proposal
**Design state:** Proposed
**Implementation state:** Not implemented

## Context

ECC demonstrates that users choose an understandable profile or component more
reliably than they assemble a large collection of instructions by hand. This
platform needs the same discoverability for review capabilities, without
turning selection into installation or execution.

## Decision

Use four catalog levels:

```text
Review profile -> Review component -> Review module -> Review pack
```

- A **pack** is a versioned review method with a defined input and output.
- A **module** groups packs with shared scope and risk characteristics.
- A **component** is a user-facing selection that resolves to modules.
- A **profile** is a named, explicit set of components.

Every module declaration must include at least:

```yaml
id:
kind:
version:
source_locator:
targets:
dependencies:
cost:
stability:
invocation_mode:
required_permissions:
side_effects:
network_behavior:
hook_behavior:
persistence_behavior:
evidence_outputs:
limitations:
rollback:
verification_state:
```

## Initial profiles

| Profile | Permitted work | Explicit exclusions |
|---|---|---|
| `minimal-verification` | Target identity and artifact hash checks | Target execution, network, install, hooks |
| `architecture-review` | Static review packs and source-backed recommendations | LHE modification, provider installation |
| `provider-intake` | Manifest, permission, dependency, and risk assessment | Download, install, account access |
| `release-review` | Supplied release evidence and rollback review | Tag, release, deployment, marketplace actions |

No initial `full` profile exists. A profile may only recommend an action plan;
it cannot invoke a pack with side effects.

## Consequences

The catalog can provide ECC-like discoverability and a future advisor/doctor,
while LHE remains a policy check rather than an installer or agent harness.
