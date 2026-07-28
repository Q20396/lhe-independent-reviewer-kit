# Independent Reviewer Kit

`independent-reviewer-kit` is a dependency-free, proposal-stage contract kit
for reviewing a candidate without granting any repository, release, deployment,
or installation authority.

It is deliberately separate from the system under review. It accepts an
immutable review request, checks the local reviewer-kit Git identity, supplied
candidate identity and changed-path manifest, and validates a structured
evidence-to-verdict chain. It does **not** edit a
candidate, invoke tests, access a network, read credentials, fetch a repository,
create a verdict, or perform Git writes.

## Security and independence boundary

The kit provides structural and procedural separation only. A local JSON file
can be forged by a local actor; the first version does not provide a signature,
attestation, trusted timestamp, or proof of human independence. A future
deployment must execute a pinned reviewer-kit revision in an isolated,
read-only environment and bind its evidence to that environment before its
output is described as independently produced.

The kit never treats a `PASS`, a CI result, or a Builder-produced receipt as a
review verdict. Human disposition remains `pending`; promotion and next-stage
authorization remain false. A review-contract hash is explicitly an opaque
hash of approved contract bytes; it does not by itself validate contract
semantics.

## Files

- `contracts/review-request.schema.json` describes the immutable scope a
  reviewer receives.
- `contracts/evidence-manifest.schema.json` describes raw evidence references.
- `contracts/review-verdict.schema.json` describes a non-authorizing verdict.
- `scripts/verify_candidate_identity.py` checks commit, tree, and changed-path
  identity against a review request.
- `scripts/verify_evidence_manifest.py` checks raw artifact paths and hashes,
  verifies evidence against its review request, and validates a verdict's
  evidence references when a verdict is supplied.

## Local checks

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/verify_candidate_identity.py --help
python3 scripts/verify_evidence_manifest.py --help
git diff --check
```

## Non-goals

- replacing human review or approval;
- validating source-code semantics;
- authenticating a reviewer identity;
- signing or attesting an artifact;
- network, GitHub API, CI, package, Marketplace, release, or installed-skill
  operations;
- importing or executing LHE, ECC, Graphify, or Planning with Files.
