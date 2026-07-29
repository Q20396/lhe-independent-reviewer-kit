# Independent Reviewer Kit

`independent-reviewer-kit` is a dependency-free, proposal-stage contract kit
for reviewing a candidate without granting any repository, release, deployment,
or installation authority.

It is deliberately separate from the system under review. It derives the
candidate from a target checkout's direct Git `HEAD` commit, verifies an
explicit base commit is its ancestor, and binds the resulting object-level
delta, changed paths, reviewer-kit identity, and contract bytes into a
structured evidence-to-verdict chain. It does **not** edit a candidate, invoke
target tests, access a network, read credentials, fetch a repository, create a
verdict, or perform Git writes.

## Security and independence boundary

The kit provides structural and procedural separation only. A local JSON file
can be forged by a local actor; it does not provide a signature, attestation,
trusted timestamp, or proof of human independence. A trusted reviewer-kit
checkout, Python interpreter, Git executable, and host remain bootstrap
preconditions: self-checking tracked blobs cannot prove that the program was
not altered before it ran.

The target checkout is read at the Git object layer only. The adapter does not
run `status`, inspect the target index, or read target working-tree files.
Accordingly, it does not claim that staged, unstaged, untracked, or ignored
target state is clean; it reviews the committed `HEAD` object only. Detached
target `HEAD` is supported. Target and reviewer-kit repositories must have
different canonical Git common directories and non-overlapping canonical
worktree roots.

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
- `scripts/verify_candidate_identity.py` derives a target `HEAD` candidate,
  base/tree identity, safe changed paths, and a deterministic object delta.
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

## Object-only delta contract

The adapter accepts only SHA-1 repositories and direct 40-character commit
object IDs. It rejects tags, trees, blobs, unrelated bases, renames/copies,
unsupported paths, and empty deltas. The target candidate is always the target
checkout's resolved `HEAD`, not a caller-selected candidate revision.

It obtains raw changes with a fixed `git diff-tree` profile and accepts only
single-path `A`, `D`, `M`, and `T` records with six-digit octal modes and full
40-character object IDs. Paths must strictly decode as UTF-8 and be nonempty
relative paths without backslashes, ASCII control characters, empty segments,
`.` or `..`; no Unicode normalization is applied.

`candidate_object_delta_sha256` is the SHA-256 of UTF-8 canonical JSON:

```text
{"entries":[...],"format":"target-object-delta-v1"}
```

Entries are sorted by their UTF-8 path bytes and use keys `path`, `status`,
`old_mode`, `new_mode`, `old_oid`, and `new_oid`. JSON keys are sorted, compact,
and `ensure_ascii=true`; an empty delta therefore has defined bytes but is
blocked rather than accepted.

All Git subprocesses use a minimal environment, disable optional locks,
replace objects, hooks, fsmonitor, pager, external diff, text conversion and
renames, and have bounded output and timeouts. This reduces host/configuration
influence; it does not eliminate the residual TOCTOU risk between object reads
or establish trust in the host Git executable.

## Non-goals

- replacing human review or approval;
- validating source-code semantics;
- reviewing uncommitted target working-tree state;
- authenticating a reviewer identity;
- signing or attesting an artifact;
- network, GitHub API, CI, package, Marketplace, release, or installed-skill
  operations;
- importing or executing LHE, ECC, Graphify, or Planning with Files.
