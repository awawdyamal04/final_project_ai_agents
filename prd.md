# PRD — Product Requirements Document

Mandatory repository content (Appendix E rule 50, PDF p. 149) and the **WHAT**
stage of the Vibe-Coding lifecycle (Idea → **PRD** → Plan → TODO → Verify →
Execute → Test → Document → Push).

This document defines **what the system must do and why**. The **how** — modular
architecture, file layout, data and execution flow — lives in
[plan.md](plan.md), [TASKS.md](TASKS.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Every requirement here is traced to `police_thief_p2p.pdf` (the sole authoritative
source) via the extraction documents under `docs/`. Nothing is invented; where the
PDF is silent or contradictory, the open question is named rather than resolved by
fabrication.

---

## 1. Project title

**Distributed Cops-and-Robbers over a Peer-to-Peer Network** — an academic final
project for *Orchestration of AI Agents*, Department of Computer Science,
University of Haifa, 2026 (Dr. Yoram Segal, book version 3.0.0).

---

## 2. Assignment goal

Build the **smallest reliable, fully compliant** implementation of a two-agent
pursuit game — a *cop* and a *thief* — played on a discrete grid by **two
autonomous, symmetric peers with no central referee**. Neither peer may see the
other's true position during play. Integrity between two mutually distrustful
peers is guaranteed by cryptography (commit-reveal over SHA-256) and verified
after the fact by an offline replay verifier — not by trust and not by a shared
server.

The priority ordering (from the brief) is, in order: (1) mandatory compliance,
(2) an end-to-end working system, (3) automated verification, (4) minimal
implementation complexity, (5) reliability, (6) strategy quality, (7) visual
polish.

---

## 3. Problem definition

A cop pursues a thief on a finite `[grid_size]`×`[grid_size]` grid (default
7×7, Appendix F, MINIMUM). Each turn both agents move orthogonally (or stay);
the cop may alternatively place a permanent barrier within one step of itself.
The thief wins by surviving `[survival_threshold]` full turns (default 35); the
cop wins by capturing the thief. Capture occurs when (a) the cop lands on the
thief's cell, (b) a barrier is placed on the thief's cell (E-46), or (c) the
thief has no legal relocation (E-47).

The defining difficulty is **decentralisation under partial observation and
possible deception**:

- There is **no external judge** (E-1, E-2). Both peers must compute the same
  physics from a byte-identical shared configuration (E-11); an identical config
  *is* an identical physics engine.
- Neither peer may access or display the opponent's true position during a live
  match (E-8, E-9) — the heaviest-sanction rules in the specification.
- A peer perceives the opponent only through a **decaying scent field** it
  cannot forge, and a **verbal hint** that may be a lie. Only the verbal channel
  can deceive.
- Because there is no referee, either peer could cheat by changing a committed
  move; **commit-reveal over SHA-256** makes that detectable at audit (E-17,
  E-18, E-19).

---

## 4. Research / engineering question

*Can two symmetric, mutually distrustful agents play a fair, verifiable pursuit
game to completion over a real peer-to-peer network — with no central referee,
no shared live state, and no agent ever seeing the opponent's true position —
such that every mandatory rule is enforced structurally and every outcome is
independently reconstructible from the sealed logs alone?*

This is an **engineering / systems** question, not a machine-learning one:
success is measured by compliance and verifiability, not by win rate. Strategy
quality ranks sixth of seven priorities.

---

## 5. Inputs

- **Shared configuration** `config/game.json` — the signed "constitution",
  byte-identical on both sides, carrying all 32 Appendix F parameters. Its
  `config_sha256` is exchanged at handshake; a mismatch means refusing to play
  (E-11). See [docs/PARAMETERS.md](docs/PARAMETERS.md).
- **Private per-peer configuration** `config/<role>/game.toml` — local only,
  never signed, never on the wire: role, network port, opponent URL, strategy
  class, LLM provider/mode, email target, group identity. May not shadow any
  shared key (D-21).
- **Network messages** from the opponent peer — a closed-schema FastMCP
  envelope carrying handshake, commit, acknowledge, reveal and final-reveal
  payloads. Validated on ingress and egress.
- **No external dataset** — see §12.

---

## 6. Outputs

- **Hash-chained append-only audit log** (JSONL) per peer, sealed at end of
  sub-game into the canonical `log_<game_id>_g<NN>.json` artefact.
- **Four JSON match artefacts** (Phase 9): `declaration_<game_id>.json`,
  `config_<game_id>_g<NN>.json`, `log_<game_id>_g<NN>.json`,
  `result_<game_id>.json`, committed under `matches/<game_id>/` (Appendix F §2).
- **Replay verdict** — `VERIFIED OK` / `TAMPERED` / `INCOMPLETE` /
  `POLICY MISMATCH`, produced offline from both peers' logs (D-41).
- **Live GUI evidence** — belief-map + turn-banner screenshots (see
  [results/](results/README.md)).
- **Emailed report** (Phase 9) — `result_file` sent as a Gmail attachment to the
  lecturer's reporting address (E-32, E-34, E-51).

---

## 7. Required architecture and methods

Full detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md);
[docs/PROTOCOL.md](docs/PROTOCOL.md) for the wire contract. Mandatory shape:

- **Exactly two autonomous peers**, cop and thief, run as **two separate OS
  processes** under separate config directories (E-1, E-2). No central referee,
  no shared game-state server, no shared live state.
- **Each peer is simultaneously a FastMCP server and client** — fully symmetric;
  no strong/weak side (Ch. 2). Exposure to the public internet is via an
  external tunnel (E-10; ngrok/Localtonet are examples only).
- **Orchestrator = single gateway** (E-3) that coordinates but decides nothing;
  a **proper state machine** rejects illegal transitions (E-4, E-5).
- **Deadline tracker** guards a single request; **watchdog** guards the whole
  process (E-6, E-7).
- **Local truth enforced structurally**: `LocalState` has *no attribute* for the
  opponent's position — a leak is an `AttributeError` in a test, not a subtle bug
  (D-9). Capture adjudication lives outside the state, in free functions taking
  both positions explicitly (D-28).
- **The LLM participates in the verbal layer only** — produce a hint, classify a
  hint. It never validates moves, verifies hashes, updates authoritative state,
  or picks the move by default (E-25 is a recommendation; the move is always
  decided in Python). Default verbal provider is a zero-token `template` (D-13).
- **All mandatory numeric parameters come from configuration** — no Appendix F
  literal appears in game logic; `config/policy.py` is the sole literal holder
  (D-10).
- **Replay verifier is the only omniscient component**, and it runs offline over
  the sealed logs; live code never imports it (E-20, D-41).

### 7.1 Dec-POMDP description

The game is modelled as a **Decentralised Partially-Observable Markov Decision
Process** (Ch. 1, PDF p. 21). Each agent `i` acts on a private observation `Ωᵢ`
that is a strict subset of the true global state `S`; no agent ever holds `S`
during play. Of the Dec-POMDP octuple, the load-bearing component for this
project is the transition function `P`: *"since there is no central server, both
sides must agree on that same transition function — it is encoded in the shared
configuration file."* This is the formal reason the config hash is a
precondition for play (E-11): an identical config **is** an identical transition
function. The `LocalState` design (§7) is the direct structural expression of
`Ωᵢ ⊂ S` — an object able to hold `S` would be modelling a game nobody is
playing.

### 7.2 Scent (pheromone) decay formula

Each move emits a scent field the opponent — and only the opponent — perceives
(Ch. 4, PDF pp. 41, 45); scent cannot be forged. Emission is a radial falloff
over a `[pheromone_grid_size]` (5×5, FIXED) window centred at
`[pheromone_center_intensity]` (0.9, FIXED). Systemic decay is applied **once
per full turn**, after both peers have moved:

```
τ(t+1) = max(0, (1 − ρ) · τ(t) + Δτ)
```

where `ρ = [pheromone_decay]` (0.10 per turn, FIXED) and `Δτ` is the fresh
emission. The radial falloff is modelled as Gaussian with `σ = 1.15`, which
reproduces the PDF's tabulated 5×5 example values to two decimal places
(0.90 / 0.62 / 0.42 / 0.20 / 0.14 / 0.04); this is a project decision (D-39),
and E-23 requires the scent model **and its concrete numeric example** to be
exchanged and cryptographically locked before any counting match.

### 7.3 Belief-update description

Each peer maintains a Bayesian belief map over the hidden opponent's cell
(Ch. 6), updated by a **predict/correct** cycle (D-40):

- **Predict** through the motion model — exact when the opponent's action is
  known, diffusing over legal moves when it is not.
- **Correct** by a scent likelihood of `1 + w · intensity` (so a cell with no
  scent is merely unremarkable, not impossible — trails decay), then exclude
  cells made impossible by barriers/edges and renormalise.
- **Honest fallback** — if contradictory evidence zeroes every cell, reset to
  uniform *minus* the cells just disproven: "I no longer know" is a truthful
  state and must not reinstate a ruled-out cell.

The belief map (never the opponent's true cell) drives target selection and the
GUI heatmap.

### 7.4 Commit-Reveal mechanism

Because there is no referee, move integrity is guaranteed cryptographically
(E-17, E-18, E-19; Ch. 5):

1. **Commit** — each peer seals a closed ten-key record
   `{v, game_id, sub_game, turn, role, state, action, hint, intent, nonce}` as
   `SHA256(canonical_json_bytes(record))` and sends **only the digest** (D-34).
   `state` is a hash of the peer's own pre-move local state, so no position
   reaches the wire. The nonce is 128 bits from `secrets.token_hex(16)` (D-35).
2. **Acknowledge** — both peers confirm receipt of the opposing commitment.
3. **Reveal** — each peer discloses the action and hint **but not the nonce**;
   the reveal schema has no nonce field, so omission is structural (D-36).
   In-turn reveals are checked for *binding* (schema, ids, role, prior
   commitment exists), not for the hash — which cannot be recomputed without the
   nonce (Q-16).
4. **Final reveal** — at the end of the match all nonces are disclosed together;
   each side re-hashes every commitment (mutual audit, E-36). Any mismatch is a
   technical loss with score 0 for the forger (E-19). The audit log is
   append-only and hash-chained, so a single altered character anywhere voids
   the match (D-37).

### 7.5 FastMCP peer-to-peer requirement

Communication is over **FastMCP** (pinned `fastmcp==3.4.5`). Each peer exposes a
minimal, symmetric tool surface — `health_check()` and a single generic
`receive_protocol_message(envelope)` validated receiver (D-29) — and calls the
opponent's identical surface. Messages are an explicit closed-schema envelope
with a 64 KiB bound, versioned (schema exact, protocol major-compatible), and
validated on both ingress and egress. There is no third process, no shared file
and no shared memory between the two peers.

---

## 8. Dataset statement

**No external dataset is required.** The system is a rule-driven multi-agent
simulation: all inputs are the negotiated configuration and the messages the two
peers exchange at run time. There is no training corpus, no benchmark dataset and
no data ingestion pipeline. The default strategy is heuristic (Bayesian belief
map + Manhattan distance, D-14) and the default verbal provider is a
zero-token template (D-13); reinforcement learning — the only route that would
imply generated training data — is explicitly **out of scope** for the mandatory
system (the course did not teach it) and would be optional at best.

---

## 9. Lecturer constraints (mandatory)

Sourced from Appendix E's 55 numbered rules and Appendix F's parameter tables;
full trace in [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md),
[docs/PARAMETERS.md](docs/PARAMETERS.md) and
[docs/COMPLIANCE_AUDIT.md](docs/COMPLIANCE_AUDIT.md). The highest-sanction
clusters:

- **Decentralisation & isolation** — two separate processes, no shared
  memory/state, orchestrator gateway, state machine, deadline + watchdog
  (E-1…E-7).
- **Information boundary** — live interfaces never show the opponent's true
  position or the objective board state (E-8, E-9).
- **Spatial rules** — orthogonal moves only, no diagonals, barriers declared
  openly and never lied about, capture and scoring per the tables (E-11…E-16,
  E-46…E-48).
- **Cryptography** — commit-reveal over SHA-256, nonce secret until match end,
  technical loss on hash mismatch, replay viewer, truthful capture declaration,
  locked scent model, hardware/step-zero declaration (E-17…E-24, E-53).
- **Strategy & network protection** — free natural-language hints only, no
  numeric position protocols, token-bucket rate limiter, DOS detector, send-only
  Gmail scope (E-25…E-30).
- **League & reporting** — ≥2 counting matches against different groups, one per
  opponent, automatic Gmail reporting as a JSON attachment, mutual audit,
  truthful match-count declaration (E-31…E-38, E-51, E-52, E-54).
- **Submission & hygiene** — never push secrets, secrets in `.gitignore`,
  documented git tag, academic README, two cross-linked repositories, mandatory
  repo files (README, /config, PRD, PLAN, TODO), Moodle rules
  (E-39…E-45, E-49, E-50, E-55).
- **Parameters** — 14 FIXED, 9 MINIMUM, 9 NEGOTIABLE; FIXED may never change,
  MINIMUM may only be raised, the tabulated value is always the code default
  (E-12).

---

## 10. Evaluation method

Compliance-first, per the brief:

- **Automated tests** — every mandatory rule maps to a pytest test or a
  deterministic manual procedure named by rule ID
  (`test_e13_rejects_diagonal_move`), so coverage is greppable.
  [docs/ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) is the map.
- **Headless simulation** — full sub-games run in-process with deterministic
  policies to confirm termination and scoring across many start layouts
  (`scripts/run_games.py`).
- **Two-process play** — two real OS processes handshake, verify config hashes,
  and play cryptographically committed turns with mutual audit.
- **Offline replay verification** — both peers' sealed logs are reconstructed
  independently; the verifier recomputes physics, capture, winner and score and
  contradicts any peer's claim (D-41).
- **Structural boundary tests** — assert that `LocalState` has no
  opponent-position attribute and that live code never imports the replay path.

Results are reported only where observed; no fabricated numbers.

---

## 11. Success criteria

1. Every mandatory Appendix E rule is COVERED with a passing test or a
   deterministic procedure ([docs/COMPLIANCE_AUDIT.md](docs/COMPLIANCE_AUDIT.md)).
2. Two independent peer processes play a **complete** match end-to-end over real
   FastMCP HTTP and both reach a terminal result. *(Met — 35 turns, both
   processes exited 0; Q-20 resolved, see §13.)*
3. Both peers' logs pass mutual audit and an independent offline replay returns
   `VERIFIED OK`. *(Met — both audit chains `Verified OK`, 179 records each;
   replay `VERIFIED OK`.)*
4. No live component can access or display the opponent's true position
   (verified structurally).
5. The full test suite is green (current baseline: **1467 passed, 3 skipped,
   0 failed**).
6. All mandatory numeric values come from configuration; no Appendix F literal
   in game logic.

---

## 12. Final deliverables

Per Appendix C, Ch. 9 and Ch. 11:

- **Two GitHub repositories** (cop, thief) with cross-linked READMEs, produced by
  splitting at submission time (D-16, E-49).
- **Academic README** in both repos carrying the six mandatory components: the
  chosen Dec-POMDP model; FastMCP orchestration dilemmas; strategies implemented;
  learning curves (only if RL used); screenshots of the live belief map **and**
  the replay showing `Verified OK`; and the companion-repository link
  (Ch. 9, PDF p. 97).
- **Mandatory repository files** — `README.md`, `/config`, `prd.md`,
  `plan.md`, `todo.md`, per-match config artefacts (E-50).
- **Documented contradiction choices** from
  [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) in the README (PDF p. 5).
- **Per-match artefacts** committed under `matches/<game_id>/`, and each
  `result_file` emailed to the lecturer address (Appendix F §2, E-51).
- **Annotated tag** `v1.0-submission`, pushed (E-41).
- **Moodle submission** — unaltered PDF form, one per member, 8-char group code,
  self-grade for code quality only (E-43…E-45, E-55).

---

## 13. Known open questions

Full record in [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md). Three carried
into the current phase; a fourth (Q-20) has been resolved and is recorded here
because it gated success criterion 2.

- **Q-12 — step-zero signing key (ESCALATE, unresolved).** Ch. 5 (PDF p. 56)
  says the step-zero declaration is signed "with a pre-supplied key" but never
  states who supplies it, which algorithm, or how it is verified. Interim
  position: canonical JSON + SHA-256 commitment (D-8). **No key-distribution
  scheme has been invented; must be asked of the lecturer before the first
  counting match.**
- **Q-18 — barrier landing on a cell the opponent already chose (NEGOTIATE).**
  Both peers act on the same pre-turn board, so the cop's barrier can land on the
  thief's chosen cell. Four readings exist; the harness applies
  `BLOCKED_MOVE_BECOMES_STAY` only so demonstrations terminate — it is not a
  ruling and must be agreed with each opponent.
- **Q-19 — long `--gui` runs destabilise the FastMCP server (RESOLVED).**
  Not one defect: retesting `--gui` against the Q-20 fix (rather than assuming
  it was covered) surfaced four independent GUI-lifecycle problems — a
  view-state publication timing bug (`GAME COMPLETE` shown too late under
  `--hold`), the automated screenshot trigger's timing relative to the actual
  repaint, Ctrl+C/window-close not reaching the worker thread's shutdown
  event, and a benign uvicorn-internal lifespan `CancelledError` traceback
  exposed only once shutdown became orderly. Each fixed independently, each
  with its own regression tests (D-44). **Evidence:** real Windows run
  `game_id` `q19-final-proof-35-01` — 35 turns, `GAME COMPLETE` displayed
  correctly, PNG screenshots captured, clean shutdown with no traceback,
  Final Reveal + mutual audit + both audit chains verified, full suite 1563
  passed / 1 skipped / 0 failed. See
  [results/q19_gui_proof.md](results/q19_gui_proof.md).
- **`capture_claim` (E-21/E-22) — confirmed implementation gap, not yet
  started.** Found while investigating why the Q-19 proof run's live peers
  played 35 turns while the offline replay found the capture at turn 30 (an
  expected divergence under D-41, not a bug — replay is the only component
  that adjudicates). `docs/PROTOCOL.md` documents `capture_claim` as the
  PDF's designed mechanism for a live mid-match stop; `src/` has no
  implementation of it. See [docs/COMPLIANCE_AUDIT.md](docs/COMPLIANCE_AUDIT.md)
  Part 9.
- **Q-20 — two-process HTTP transport stall (RESOLVED).** Root cause proven:
  **stdout PIPE backpressure**. The runtime echoed every operational event with
  a synchronous `print` from inside the asyncio loop while launchers captured
  stdout without draining it; once the pipe buffer filled, the `print` blocked
  the loop, so each process stayed alive while its FastMCP server stopped
  accepting connections. Fixed by defaulting the event-sink echo off (opt in
  with `--verbose`) and uvicorn to `log_level="warning"`; JSONL and audit
  logging are unchanged (D-42). **Evidence:** 35-turn two-process real-HTTP
  match, both processes exit 0, final reveal over all 35 turns, mutual audit
  both directions, both audit chains `Verified OK` (179 records each),
  independent replay `VERIFIED OK` — survival on turn 35, winner thief, cop 5 /
  thief 10. Full suite 1467 passed, 3 skipped, 0 failed. See
  [results/q20_transport_proof.md](results/q20_transport_proof.md).
