# results/

Submission artefacts and generated evidence for the Distributed
Cops-and-Robbers P2P project. This directory holds **observed** output only —
nothing here is hand-authored or fabricated. Where a result has not yet been
generated, it is simply absent; it is never invented.

This directory will contain:

- **Verified game outputs** — completed sub-game / match results and their
  terminal states.
- **Replay reports** — offline replay-verifier verdicts (`VERIFIED OK`,
  `TAMPERED`, `INCOMPLETE`, `POLICY MISMATCH`) reconstructed from both peers'
  sealed logs.
- **Benchmark summaries** — headless-simulation statistics (outcomes, winners,
  turn counts, barrier usage) from `scripts/run_games.py`.
- **League-match evidence** — per-match artefacts and confirmations for counting
  matches against different groups (Phase 9–10).
- **Screenshots** — Live GUI belief map and the Replay viewer showing
  `Verified OK`, both mandatory submission artefacts (Ch. 9, PDF p. 97).
- **Plots and tables** — any figures referenced by the academic README.

## Current contents

- `screenshots/live_cop.png` — Live GUI belief map, cop peer.
- `screenshots/live_thief.png` — Live GUI belief map, thief peer.

## Status notes

- The full test suite baseline is **1465 passed, 3 skipped, 0 failed** (1468
  collected). See the repository `README.md`.
- A full **long real HTTP two-process match is not yet proven** — the transport
  stall Q-20 is an open blocker (see [prd.md](../prd.md) §13 and
  [docs/OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md)). No league matches, Gmail
  reports or public-tunnel runs have occurred yet.
