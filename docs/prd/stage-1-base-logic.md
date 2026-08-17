# Stage 1 — Base Logic

*PDF Ch. 3; stage table PDF pp. 101–103. Corresponds to [TASKS.md](../../TASKS.md) Phase 1.*

## What

The game's physics in one process, no network, no crypto, no AI. A grid of
`grid_size`, orthogonal movement only, barrier placement up to `max_barriers`,
and capture by coordinate overlap or by imprisonment (no legal relocation).

## Why

Every later stage depends on this being right and cheap to test. Getting
capture, barriers and scoring correct in a single process — before there are
two processes, a network, or cryptography to blame instead — confines the
first round of bugs to the smallest possible surface. The PDF's own rationale
for building this first (Ch. 10) is the same one that governs the whole
project's phase order: prove a layer before the next is laid on it.

## Scope boundary

No FastMCP, no commit-reveal, no strategy module, no scent, no language. A
trivial fixed policy (or a human driving both sides) is enough to exercise the
rules.

## Milestone (PDF p. 105, observed not just written)

Two agents move legally on a `grid_size` grid; a move into a `max_barriers`
barrier is rejected; coordinate overlap triggers capture.

## Status: ✅ Complete

`domain/state.py`, `domain/board.py`, `domain/rules.py`, `domain/capture.py`,
`domain/terminal.py`, `domain/scoring.py`, `domain/transition.py`,
`domain/simultaneity.py`, exercised by `sim/headless.py`. 171 domain tests at
the time this phase closed. See TASKS.md Phase 1 for the full checklist and
[../REQUIREMENTS.md](../REQUIREMENTS.md) §2 for the traced rules (E-13
through E-16, E-46 through E-48).
