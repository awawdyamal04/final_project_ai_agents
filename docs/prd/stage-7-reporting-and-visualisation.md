# Stage 7 — Reporting and Visualisation Shell

*PDF Ch. 9, Ch. 7, App. A; stage table PDF pp. 101–103. Spans [TASKS.md](../../TASKS.md) Phases 6 (replay), 7 (live GUI) and 9 (Gmail reporting).*

## What

Three deliverables the PDF bundles into one stage because each consumes
layers built earlier: the Gmail API report (OAuth 2.0, JSON attachment, never
free text — E-33, E-34), the live GUI's belief heatmap and turn banner, and
the offline replay viewer/verifier.

## Why

The PDF is explicit that this is built last precisely because it has nothing
of its own to prove — it renders and reports on state that the crypto,
domain and strategy layers already produced. Building it earlier would risk
polishing a display for physics that hadn't stabilised yet.

## Scope boundary

This project splits the PDF's single Stage 7 across three `TASKS.md` phases
rather than one, because the three deliverables have different dependencies
(the GUI needs only the belief map from Stage 4 and the state machine from
Stage 2; the replay verifier needs the crypto log from Stage 6; Gmail
reporting needs a real match to report on, so realistically follows Stage 5).
That split is a sequencing choice, not a scope change — all three are still
required for this stage to be complete.

## Milestone (PDF p. 105, observed not just written)

A match summary is sent by Gmail; the GUI displays the state; the Replay App
reconstructs a recorded round.

## Status: Partially complete

- **Replay verifier — ✅ complete** (`TASKS.md` Phase 6). Four verdicts
  (VERIFIED OK / TAMPERED / INCOMPLETE / POLICY MISMATCH), demonstrated against
  a real 35-turn two-process game reconstructing a capture independently.
- **Live GUI — ✅ complete, one known limitation** (`TASKS.md` Phase 7).
  Belief heatmap, turn banner, no field for the opponent's true position by
  construction. **Q-19**: runs beyond ~6 turns under `--gui` destabilise the
  FastMCP server (known limitation, not a compliance failure — the mandatory
  screenshots are already produced and league play does not require the GUI).
  A retest was attempted 2026-08-02 (`results/q19_gui_*.eps`, uncommitted as of
  2026-08-08) but not concluded.
- **Gmail reporting — not started** (`TASKS.md` Phase 9). Depends on Google
  Cloud/OAuth provisioning, which had not begun as of 2026-08-08
  (`todo.md`, "Start now — external latency").

See [../REQUIREMENTS.md](../REQUIREMENTS.md) §5–§6 for the traced rules.
