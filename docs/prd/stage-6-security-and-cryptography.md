# Stage 6 — Security and Cryptography

*PDF Ch. 5; stage table PDF pp. 101–103. Corresponds to [TASKS.md](../../TASKS.md) Phase 5, built ahead of Stage 5.*

## What

Wrap the turn protocol in commit-reveal over SHA-256: commit, acknowledge,
reveal (nonce withheld), final reveal. Nonce generation from `secrets`, not
`random`. A hash-chained, tamper-evident audit log. Step-0 hardware/version
declarations, including the commit hash.

## Why

This is the mechanism that lets two mutually distrustful peers agree on what
happened without a referee — the project's central architectural claim.
Getting it wrong is also the highest-consequence mistake available: a hash
mismatch is a technical loss at score zero (E-19, E-36), so this layer is
tested more heavily than any other.

## Scope boundary, and the one deliberate reordering

**Deviation from the PDF's stage order, reasoned in `TASKS.md`.** The PDF
places cloud exposure (Stage 5) before cryptography (Stage 6); this project
builds cryptography first. Rationale: crypto is testable entirely offline and
is the highest-consequence rule cluster (E-17 through E-24, E-36), while
tunnelling is external tooling that adds no testable code of its own.
Inverting keeps the fault space confined to code actually written. The PDF's
stated reason for its order — don't debug crypto through an unproven transport
— is still honoured, because Phase 2 already proved the transport over
localhost before this stage began.

## Milestone (PDF p. 105, observed not just written)

A move is committed in Commit and then revealed in Reveal with a valid Nonce;
Step-0 verifies hardware.

## Status: ✅ Complete

`crypto/sealed.py` (closed ten-key sealed record, D-34), `crypto/nonce.py`
(`secrets.token_hex(16)`, local reuse guard), `crypto/coordinator.py` (the four
phases, duplicate/conflict/replay handling), `crypto/stepzero.py` (declaration
only — signing is **deliberately unimplemented**; see Q-12, escalation to the
lecturer still outstanding as of 2026-08-08), `audit/` (hash-chained JSONL
with an independent verifier). Demonstrated with two real processes; later
extended by Phase 6 (replay verifier) and Phase 7b (Q-20 transport fix). See
TASKS.md Phase 5 and [../REQUIREMENTS.md](../REQUIREMENTS.md) §3.
