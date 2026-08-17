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
- `screenshots/q19_cop_final_35.png` / `screenshots/q19_thief_final_35.png` —
  automated end-of-match PNG screenshots from the real Windows 35-turn `--gui`
  proof run (`game_id` `q19-final-proof-35-01`), captured the moment
  `GAME COMPLETE` actually rendered.
- `q20_transport_proof.md` — root cause, fix and end-to-end evidence for the
  Q-20 two-process transport stall.
- `q19_gui_proof.md` — root causes, fixes and end-to-end evidence for the
  Q-19 `--gui` lifecycle defects (view-state publication, screenshot timing,
  Ctrl+C/close shutdown, benign lifespan `CancelledError`).

## Status notes

- The full test suite baseline is **1563 passed, 1 skipped, 0 failed**
  (Windows; `game_id` `q19-final-proof-35-01` verification run). See the
  repository `README.md`.
- A **complete real HTTP two-process match is proven**: 35 turns, both processes
  exit 0, final reveal over all 35 turns, mutual audit both directions, both
  audit chains `Verified OK` (179 records each), independent replay
  `VERIFIED OK` — survival on turn 35, winner thief, cop 5 / thief 10. Q-20 is
  resolved; see [q20_transport_proof.md](q20_transport_proof.md).
- **Q-19 is resolved.** A real Windows 35-turn `--gui` match completes,
  displays `GAME COMPLETE` correctly, captures automated PNG screenshots,
  shuts down cleanly with no benign-cancellation traceback, and verifies at
  every layer (Final Reveal, mutual audit, both audit chains). See
  [q19_gui_proof.md](q19_gui_proof.md).
- A **separately confirmed compliance gap**, found while investigating why
  that same run's live peers played 35 turns while the offline replay found
  the capture at turn 30 (expected under D-41, not a Q-19 defect):
  `capture_claim` (E-21/E-22) — the PDF's own mechanism for a live mid-match
  stop — is documented in `docs/PROTOCOL.md` but not implemented in `src/`.
  Tracked in `docs/COMPLIANCE_AUDIT.md` Part 9 and `todo.md`; not implemented
  yet.
- Still outstanding: no league matches, Gmail reports or public-tunnel runs
  have occurred yet.
