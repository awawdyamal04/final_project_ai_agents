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
- **`capture_claim` design (see §14).** PRD-level requirements for the
  feature are now specified; implementation has not started
  (`feat/capture-claim`, docs-only phase, 2026-08-17).
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

---

## 14. Feature: `capture_claim` (E-21, E-22) — design specification

**Status: documentation and design only, on `feat/capture-claim`.** No
`src/` or `tests/` file has been touched for this feature. This section is
the WHAT; [plan.md](plan.md) §`capture_claim` is the HOW;
[docs/CAPTURE_CLAIM_VERIFICATION.md](docs/CAPTURE_CLAIM_VERIFICATION.md) is
the pre-execution design verification report; `todo.md` §"capture_claim
implementation" is the granular execution checklist. Every claim below is
traced to a PDF page or to an existing repository file, independently
re-verified against `police_thief_p2p.pdf` for this task rather than taken
on the strength of `docs/COMPLIANCE_AUDIT.md` alone.

### 14.1 Problem

A live peer cannot adjudicate a capture — `LocalState` structurally has no
attribute for the opponent's position (E-8, E-9, D-9) — so today's live
peers simply play to the configured turn ceiling and stop
(`survival_threshold` / `max_moves`), regardless of whether a capture
happened earlier. Only the **offline** replay verifier discovers the true
terminal turn, after the match, from both sealed logs (D-41). This is
architecturally correct for *reconstruction*, but it means a live match
currently has no way to stop early on a genuine capture, and there is no
live mechanism at all for a cop to honestly declare "I got you" or for a
thief to be held to a truthful answer while the match is still running.
Confirmed empirically: a real 35-turn run whose replay found the capture at
turn 30 (`results/q19_gui_proof.md`, `docs/DECISIONS.md` D-44 "separately
confirmed" note).

### 14.2 Assignment requirement

- **E-21** (PDF p. 145): *"Mandatory: declare truth only at the moment a
  thief is caught."* Sanction: immediate disqualification for denial of
  reality.
- **E-22** (PDF p. 145): *"Prohibition: never falsely declare a capture; a
  false declaration carries immediate disqualification."* Sanction: score
  zero, technical loss, no right of appeal.
- **Chapter 3 narrative, independently re-read for this task** (PDF pp.
  38–39, Ch. 3 "Iron rules: movement and truth declaration" and the scoring
  table): *"Successful capture: the cop lands on the thief's cell and
  declares Capture Claim"* is literally the scoring table's definition of
  the capture outcome row. *"When the cop declares (Capture Claim), the
  thief is under a cryptographic obligation to answer truthfully. An
  attempt to lie at this stage will necessarily be discovered at the
  audit-log stage (the Capture protocol) and will carry total systemic
  disqualification."* And, on enforcement: *"A capture declaration is
  therefore not a question of trust between opponents but of proof
  verifiable after the fact: every response is signed and recorded in the
  log, and any attempt to deny the true state will be discovered at the
  log-audit stage and lead to disqualification."*
- These are the **only** places in the 160-page PDF that discuss capture
  declaration. A full-text keyword search (this task, `/tmp/pdf_fixed.txt`,
  reconstructed RTL) for `capture_claim`/`תפיסה`/`הכרזה` outside Ch. 3 and
  Appendix E returns nothing relevant. There is **no dedicated protocol
  chapter, no message schema, no field catalogue, and no explicit statement
  of whether the match halts immediately** on a claim. `docs/PROTOCOL.md`
  §6.5 already contains a **prior, unimplemented design sketch** for the
  wire shape (request/response JSON), explicitly flagged at the top of that
  file as "design-only" — it is reused and cross-checked here, not treated
  as an independent authority.

### 14.0 Classification key (used throughout this section)

Every design point below is tagged **[A]**, **[B]** or **[C]**:

- **[A] ASSIGNMENT-MANDATED** — stated or directly entailed by E-21/E-22 or
  another mandatory rule; not a choice.
- **[B] OUR DESIGN DECISION** — a reasonable implementation choice the PDF
  does not dictate; presented as a proposal, never as a lecturer requirement.
- **[C] STILL UNRESOLVED** — genuinely open; requires either opponent-team
  agreement or lecturer input; not invented here.

The full enumeration is `docs/CAPTURE_CLAIM_VERIFICATION.md`'s classification
table; this section applies the same tags inline.

### 14.3 Actors

- **Cop** **[A]** — is the party who declares a Capture Claim (Ch. 3
  scoring table: "the cop lands on the thief's cell and declares Capture
  Claim"). This is the **primary, mandatory-path initiator**. Per E-9 the
  cop can never verify a claim locally; every cop-initiated claim is a
  belief pending the thief's answer, not a fact.
- **Thief** **[A]** — is under a cryptographic obligation to answer a
  cop's claim truthfully (E-21: truth only; E-22's mirror obligates the
  cop not to claim falsely). This response obligation is the thief's
  mandatory role. **[B] Optional extension:** the thief may additionally
  use its own internal, fully self-evaluable knowledge (§14.9) to decide
  *when to proactively signal* a suspected capture rather than only
  responding when accused — but this proactive path is **not** how E-21/
  E-22 compliance is satisfied, is not mandatory, and must never be
  presented as equivalent to the cop-initiated flow. See §14.8.1.
- **Replay verifier** **[A]** (offline, post-match, D-41, pre-existing and
  unaffected by this feature) — remains the sole omniscient adjudicator of
  record. A live claim/response exchange is evidence fed into the audit
  log for replay to check, never a substitute for replay's own independent
  recomputation. See §14.11's live-vs-authoritative distinction.

### 14.4 Inputs

- The claiming peer's own `LocalState` (position, barriers, turn number).
- The three existing pure capture-evaluation functions in
  `domain/capture.py` (`evaluate_movement_capture`,
  `evaluate_barrier_capture`, `evaluate_trapped_capture`,
  `evaluate_full_turn_capture`) — already implemented, already used by
  `sim/harness.py` (Phase 1 offline self-play) and `replay/verifier.py`
  (post-match), never yet called from `peer/orchestrator.py`.
  `domain/enums.py::CaptureReason` and `domain/capture.py::CaptureVerdict`
  already model exactly the three grounds named in the PDF and in E-46/E-47.
- The opponent's most recently revealed move/barrier action (already on the
  wire via the existing `reveal` message, §6.4 of `docs/PROTOCOL.md`).

### 14.5 Outputs

- **[B]** A new signed, logged `CAPTURE_CLAIM` record and a signed, logged
  `CAPTURE_CLAIM_RESPONSE` record (exact schema: §14.8).
- **[A]** An audit-log entry pair, hash-chained like every other record
  (E-19, D-37), so a false claim or false denial is exposed at the same
  final-audit stage everything else is (per the PDF quote in §14.2).
- **[B]** The live behavioural consequence adopted in §14.13: on a
  confirmed claim, entry into `CLAIM_PENDING_AUDIT` and no further turns;
  on a denial, the match continues; in all cases the claim/response pair is
  recorded for the final, authoritative audit (§14.11).

### 14.6 Allowed information

**[A], directly bounded by E-8/E-9.** A peer's own true position; its own
barrier placements (already public per E-15/E-16); the opponent's *already
revealed* move or barrier action for the current turn (already public); a
claim's ground/kind (`landed` / `barrier_on_thief` / `no_legal_move`) — the
cop declaring a suspicion is not a leak, since the claim is a public
accusation about an outcome, not a disclosure of anyone's hidden state; and,
in the response, **only** a boolean verdict (`confirm` / `deny`) plus
protocol bookkeeping (`claim_id`, `sub_game_number`, `turn_number`,
`responder_role`) and cryptographic binding/commitment metadata already
permitted elsewhere in this protocol (§14.8's schema). **Nothing else is
sent.** `capture_claim` is not a path for revealing opponent location —
this section exists specifically to say that explicitly, because a
response naturally *could* carry the thief's true cell (it would even make
the response "more verifiable" in a naive design) and it must not.

### 14.7 Forbidden information

**[A] — a direct, non-negotiable consequence of E-8/E-9; not a design
choice available to weigh against convenience.**

- **The cop must never receive, in a claim response or anywhere else in
  this feature: the thief's position, the thief's nonce, any of the
  thief's unrevealed actions, global/objective board truth, or any other
  hidden state.** The response schema (§14.8) is deliberately minimal for
  exactly this reason — it is not an oversight to fix later, it is the
  point.
- The opponent's true position must never appear in `LocalState`, in the
  live GUI (`gui/live.py`, `gui/view_model.py`), in stdout, or in any field
  reachable before an exchange that legitimately discloses it under the
  *existing* rules (D-9's structural guarantee must not be weakened by this
  feature).
- No numeric position protocol inside the verbal/hint channel (E-26, E-27)
  — unaffected by this feature, but must not be accidentally reopened by a
  careless claim-payload design that piggybacks on the hint field.
- The claim/response record must not disclose the nonce (E-18) — nonces
  stay hidden until `final_reveal`, exactly as for ordinary turn records,
  **unless the PDF is later found to say otherwise explicitly** (it does
  not, as of this pass); a capture-claim record is not a special exemption
  from E-18.

### 14.8 Message flow

**Primary flow — [A] shape, [B] field names.** The mandatory shape (cop
declares, thief answers truthfully) is E-21/E-22 directly; the exact field
names below are a design proposal, not lecturer-prescribed text:

```
COP   → THIEF : CAPTURE_CLAIM
THIEF → COP   : CAPTURE_CLAIM_RESPONSE   (confirm | deny)
```

Proposed schema (`plan.md`'s `protocol/capture_claim.py`), deliberately
excluding any coordinate or hidden-state field per §14.6/§14.7:

```jsonc
// CaptureClaim  (police -> thief)
{
  "claim_id":       "<uuid4>",
  "sub_game_number": 1,
  "turn_number":    17,
  "claimant_role":  "police",
  "claim_kind":     "landed",   // "landed" | "barrier_on_thief" | "no_legal_move"
  "commitment":     { "…crypto binding metadata, §14.10…" }
}
// CaptureClaimResponse  (thief -> police)
{
  "claim_id":        "<uuid4>",   // echoes the claim being answered
  "sub_game_number":  1,
  "turn_number":      17,
  "responder_role":  "thief",
  "verdict":         "confirm",   // "confirm" | "deny" -- nothing else
  "commitment":      { "…crypto binding metadata, §14.10…" }
}
```

No `claimed_cell`, no `thief_cell`, no nonce, no board state — intentionally
narrower than the earlier `docs/PROTOCOL.md` §6.5 sketch this design started
from, corrected for §14.6/§14.7.

#### 14.8.1 Optional extension — thief self-detection **[B], not E-21/E-22**

The thief may, using only information it already legitimately has
(§14.9), independently know the true outcome of a turn before any cop
claim arrives. Two ways this may be used, both **optional and clearly
secondary to the primary flow above**:

1. **Internal only (no wire message).** The thief uses this knowledge
   solely to make sure its `CAPTURE_CLAIM_RESPONSE` is truthful when a cop
   claim does arrive. This is not really an "extension" — it is simply how
   E-21 compliance is achieved correctly — and requires no new message type.
2. **Proactive signal (a genuine design extension, [B]).** The thief could
   additionally send an unsolicited claim-shaped message when it detects
   `barrier_on_thief` or `no_legal_move` on its own. If built at all, this
   must be a clearly separate, clearly optional code path — **not** the
   mechanism that satisfies E-21/E-22, which is specifically about the
   thief's obligation to answer *the cop's* claim truthfully. A thief that
   never proactively signals anything is still fully compliant, provided it
   answers truthfully when claimed.

### 14.9 Architecture insight (read-only finding, informs §14.8.1 only)

Re-deriving from the data each of the three capture conditions actually
needs: `evaluate_full_turn_capture(movement, thief_state, config, policy)`
requires `thief_state` (own) and `movement` (both peers' revealed actions).
After the cop's move/barrier for the turn is revealed (already on the wire,
§6.4), **the thief has every input needed to call the existing, unmodified
`evaluate_full_turn_capture` for all three grounds** — landed-on-thief (via
the simultaneity policy, itself Q-18-consistent since the policy is a
parameter — see §14.9.1), barrier-on-thief (E-46), and no-legal-move (E-47)
— without any new capture-detection logic. This is what makes the thief's
`CAPTURE_CLAIM_RESPONSE` **capable of being truthful by construction**
(§14.8.1 point 1) and is also the technical basis for the *optional*
proactive-signal extension (§14.8.1 point 2) — **it is not, on its own,
grounds to make thief-initiation the primary or mandatory flow**, which
Correction 1 of this pass explicitly rejected. The cop, symmetrically, can
*never* self-verify any of the three grounds live (E-9), so a cop-initiated
claim is structurally always a belief pending the thief's truthful answer,
exactly as the PDF's Ch. 3 wording describes.

#### 14.9.1 Q-18 and Q-12 — explicit interaction labels

- **Q-18 [does not change; stays out of scope of this feature] [A that
  Q-18 is separate].** Q-18 governs only how one turn's simultaneous
  movement/barrier collision is resolved (`SimultaneityPolicy`); it is not
  a lecturer ruling — `BLOCKED_MOVE_BECOMES_STAY` is the harness's
  demonstration default, not a resolved requirement (`docs/OPEN_QUESTIONS.md`
  Q-18). `capture_claim` **consumes** whichever policy is negotiated for a
  given match — `evaluate_full_turn_capture(..., policy)` already takes it
  as a parameter — it does not resolve, weaken, or take a position on Q-18.
- **Q-12 [separate scope, not fully irrelevant] [C for league-level
  compliance].** Q-12 concerns the step-zero hardware-declaration signing
  key, a different signature context from per-turn/per-claim commitments.
  **[B]** This design proposes that `capture_claim` authentication reuse
  the *existing, already-established* per-turn commitment/identity
  primitives (§14.10), which do not depend on the step-zero key — so
  implementation of `capture_claim` itself can proceed independently of
  Q-12's resolution. **[C]** However, if a future audit or the lecturer
  determines that step-zero's signing key is *also* required for
  full/final league-level compliance of every signed artefact in the
  match (not just the step-zero declaration itself), that would reopen a
  dependency this design does not currently assume. Q-12 remains escalated
  and unresolved in `docs/OPEN_QUESTIONS.md`; this feature does not close
  it and should not be read as having done so.

### 14.10 Security requirements — **[B], explicitly not [A]**

The assignment requires truthfulness and after-the-fact verifiability
(E-21, E-22, and the Ch. 3 "signed and recorded in the log" language); it
does **not** name or mandate any specific cryptographic schema for
`capture_claim`. The choice of *which* mechanism satisfies that requirement
is ours:

- **[B]** Reuse the existing per-turn Commit-Reveal
  `SHA256(canonical_json_bytes(...))` scheme (D-34/D-35) for the
  claim/response record rather than inventing a second cryptographic
  system. This is a design decision, not an assignment mandate — the PDF's
  wording is satisfied by *any* mechanism that is signed, logged, and
  checkable after the fact; reusing an existing, already-tested primitive
  is preferred here on cost/risk grounds (`plan.md`), not because the PDF
  requires this specific primitive.
- **[A]** Nonces and any hidden action data must remain secret until the
  existing permitted reveal/audit stage (E-18) — this constraint is
  unchanged and inherited, not something this feature may relax, and the
  PDF gives no indication that capture_claim is an exception.
- **[B, but scoped by A]** Q-12 does not block this feature (§14.9.1); the
  claim/response signing depends only on already-established per-turn
  commitment primitives.
- **[A]** A false claim (cop) or false denial (thief) must be exposed at
  the same final-audit mutual-verification stage as every other tampering
  (E-19, E-22) — not by a separate, weaker live-only check.
- **[A, restated from §14.7]** The claim/response exchange must not create
  a new channel for leaking the opponent's position outside what E-8/E-9
  already permit.

### 14.11 Audit requirements, and the live-vs-authoritative distinction

**[A]** A claim and its response are each a first-class, hash-chained audit
record (parallel to existing `commit`/`reveal`/`final_reveal` records), not
a side channel outside the existing `audit/writer.py` / `audit/chain.py`
machinery — this follows directly from the PDF's "signed and recorded in
the log" language and from the project's existing audit discipline (no
component may hold state outside the hash-chained log).

**[A] The live response is evidence and protocol state, not a verdict.**
Two distinct things must never be conflated:

1. **Live response** — the `CAPTURE_CLAIM_RESPONSE`'s `confirm`/`deny`
   verdict, received during play. It changes protocol *state* (§14.13) and
   is logged, but it is **not**, on its own, proof of anything — either
   side could in principle send it falsely, which is exactly what E-21/E-22
   forbid and exactly what final audit exists to catch.
2. **Later authoritative verification** — the final mutual audit and
   `replay/verifier.py`'s independent recomputation remain the only
   process that actually *establishes* whether: the cop's claim was
   truthful; the cop's claim was false; the thief's confirmation was
   truthful; the thief's denial was false. `replay/verifier.py` must read
   a logged claim/response pair (if present) and **check it against its
   own independent recomputation of `TerminalResult` — never adopt it**.
   A logged claim is evidence to be checked, never a shortcut around D-41's
   "replay trusts neither peer."

Neither side is ever trusted merely because it sent a response. This
distinction is the load-bearing correction of this pass and must be
preserved through implementation, not only through documentation.

### 14.12 Replay relationship — **augments D-41; does not replace it**

**[B], but stated as the adopted design position, not a toss-up between
alternatives.** `capture_claim` **augments** D-41; it does not replace it,
and D-41's existing behaviour remains fully available:

- **With a confirmed live claim:** live peers may stop issuing further
  turns early (§14.13's `CLAIM_PENDING_AUDIT` design) and proceed toward
  final reveal and mutual audit sooner than the configured ceiling.
- **Without a claim (or with a denied one):** D-41's existing behaviour is
  unchanged and remains fully possible — live peers may play to the
  configured turn ceiling, and offline replay determines the first true
  terminal state exactly as it does today, with no dependency on this
  feature existing at all.
- **In both cases, replay remains authoritative.** A confirmed live claim
  never substitutes for replay's independent recomputation (§14.11); it
  only changes *when* a match may stop issuing turns, never *who* has the
  final word on what actually happened.

This reading follows from the PDF's own "not a question of trust... but of
proof verifiable after the fact, at the log-audit stage" language (§14.2) —
the same after-the-fact-verification principle D-41 already implements —
but the PDF never uses the word "replay" in the capture_claim passage, so
this remains a design inference **[B]**, not a literal citation, and is
recorded as such rather than presented as an assignment requirement.

### 14.13 Scoring / termination relationship

**[A] Sub-game scope, high confidence:** a capture_claim, once truthfully
confirmed, ends the current **sub-game** (one `game_id` run — what this
repository already calls "the match"), not the wider **league series** the
PDF's own config schema separately tracks via `num_games` /
`sub_game_number` (PDF p. 129, p. 131). This repository has never
implemented a multi-sub-game league runner, so "does capture_claim end the
whole match" resolves to "yes, the whole (single) match this repository
plays" under current scope.

**[B] Recommended runtime mechanism, since the PDF does not specify one.**
The PDF defines *what counts as a capture* but not the exact runtime
mechanism for stopping future turns after a claim exchange — that silence
is deliberately not filled with an invented "the PDF requires this." The
conservative, adopted design:

- After a claim is **confirmed** live: the peer enters a
  `CLAIM_PENDING_AUDIT` (terminal-pending) protocol state. No additional
  game turns are issued. `final_reveal` and mutual audit still execute in
  full — they are not skipped, since they remain the actual proof
  mechanism (§14.11). Replay remains authoritative over the outcome.
- If the claim is **denied**: gameplay may continue. The denial is logged
  and remains auditable; nothing about a denial forces an early stop.
- If audit later proves a false claim or a false denial (regardless of
  what the live verdict was): apply the assignment's existing
  technical-loss/disqualification rule (E-19, E-21, E-22) exactly as it
  would apply to any other detected tampering.

**[C] Genuinely unresolved, and stated as such:** the PDF does not
explicitly define immediate-stop mechanics beyond what is inferred above;
this design is the safest reading consistent with §14.11's live-vs-
authoritative distinction, not a citation. See
`docs/CAPTURE_CLAIM_VERIFICATION.md` Q8/Q10 for the full reasoning.

### 14.14 Failure cases

- Cop claims falsely (no actual capture) → E-22 → immediate
  disqualification, score 0, no appeal — **[A]**, established at final
  audit (§14.11), which may or may not also be caught live.
- Thief denies falsely (was actually captured) → E-21 → immediate
  disqualification for "denial of reality" — **[A]**, same audit-time
  establishment.
- Claim/response message malformed, out of turn order, references a stale
  `turn_number`, is sent by the wrong `sender_role` (e.g. a
  `CAPTURE_CLAIM_RESPONSE` claiming `responder_role: "police"`), or is a
  duplicate of an already-answered `claim_id` → **[B]** rejected under the
  same closed-schema/state-machine discipline as every other message (§0 of
  `docs/PROTOCOL.md`) — not a new error class, an instance of the existing
  `ProtocolValidationError` / illegal-transition handling. Duplicate
  `claim_id` handling should be idempotent (the same claim re-sent gets the
  same logged response, not a second independent one), matching the
  existing envelope's `message_id`-based idempotency (§0.1).
- Peer times out mid-claim → **[A]** existing deadline/watchdog machinery
  (E-6, E-7) applies unchanged; a capture claim is not exempt from response
  timeouts.

### 14.15 Success criteria

1. **[A]** A cop-initiated `CAPTURE_CLAIM` and a thief
   `CAPTURE_CLAIM_RESPONSE` are each a schema-validated, signed,
   hash-chained audit record, and this primary flow works without any
   optional extension enabled.
2. **[B, optional]** If the thief self-detection extension (§14.8.1) is
   built, it reuses the existing `domain/capture.py` functions verbatim —
   no duplicated capture logic — and its absence does not affect criterion
   1's compliance.
3. **[A]** `replay/verifier.py` cross-checks any logged claim against its
   own independent recomputation and flags disagreement distinctly
   (extending D-41's four-verdict model, not replacing it, §14.12).
4. **[A]** A false claim or false denial is provably caught at final audit
   (E-21, E-22) in a dedicated test — for both the cop-initiates and
   thief-responds direction.
5. **[B]** No new module introduced for this feature exceeds 150 lines
   (lecturer line-count rule, same discipline as the Q-19 refactor, D-44).
6. **[A]** Existing structural information-boundary guarantees (E-8, E-9,
   D-9) are unweakened — a dedicated boundary test proves the
   `CAPTURE_CLAIM_RESPONSE` payload carries no field capable of disclosing
   the thief's position, nonce, unrevealed action, or any other hidden
   state (§14.6/§14.7).

### 14.16 Acceptance criteria

- `pytest -q` green with the new capture_claim tests included, and the
  full existing suite unaffected (no regression in the Q-19/Q-20 baseline).
- `ruff check .` clean.
- `find src tests -name "*.py" | xargs wc -l` shows no new file over 150
  lines introduced by this feature.
- A dedicated test asserts the `CAPTURE_CLAIM_RESPONSE` schema has no field
  that could carry a position, coordinate or nonce (a structural guard, not
  only a behavioural one — mirrors how `LocalState`'s missing attribute is
  tested today).
- A real two-process run (as used for the Q-19/Q-20 proofs) demonstrates at
  least one genuine capture_claim exchange end to end, with the resulting
  audit log passing mutual audit and replay `VERIFIED OK`.
- `docs/COMPLIANCE_AUDIT.md` Part 9's E-21/E-22 rows are corrected from
  documentation-era `COVERED` to implementation-era `COVERED` only once
  the above is true — not before.

### 14.17 Master classification — A / B / C

- **[A] — explicitly supported by the assignment, not a choice:**
  E-21/E-22's two rules verbatim; the Ch. 3 scoring-table trigger ("cop
  lands, declares Capture Claim") establishing the **cop as the primary
  initiator**; the thief's cryptographic truth obligation to *answer* a
  claim; enforcement via signed, logged responses checked at **final
  audit, not live trust** (§14.11); the three capture grounds (landed /
  E-46 barrier / E-47 trapped) themselves (already implemented, unrelated
  to this feature); a capture_claim ending the current sub-game/match (not
  the wider, unimplemented league series, §14.13); nonces staying secret
  until the existing reveal/audit stage (E-18, unchanged); the response
  payload never carrying the thief's position, nonce, unrevealed action or
  other hidden state (direct E-8/E-9 consequence, §14.6/§14.7).
- **[B] — our design decisions, presented as proposals, never as lecturer
  requirements:** the exact wire schema and field names (§14.8); reusing
  the existing per-turn Commit-Reveal signature primitive rather than a new
  one (§14.10); the optional thief-initiated self-signal extension,
  explicitly secondary to and not a substitute for the mandatory
  cop-initiated flow (§14.8.1); the `CLAIM_PENDING_AUDIT` runtime
  mechanism for halting further turns on a confirmed claim (§14.13);
  where the new protocol/audit/replay code physically lives (`plan.md`);
  that a live claim **augments** D-41 rather than replacing it (§14.12) —
  the augment/coexist reading is adopted as the working design, not
  asserted as a PDF citation.
- **[C] — unresolved, explicitly not invented:** the precise mechanism by
  which a cop forms enough suspicion to issue a claim at all, given it
  structurally cannot verify its own landing cell (E-9) — the PDF describes
  the outcome, not the trigger heuristic; whether immediate-stop mechanics
  beyond the `CLAIM_PENDING_AUDIT` design are more precisely specified
  somewhere this task did not find; whether the multi-sub-game league
  layer (out of current scope) will eventually need its own claim
  semantics; whether Q-12's step-zero key will turn out to also be
  required for full league-level signature compliance (§14.9.1). See
  `docs/CAPTURE_CLAIM_VERIFICATION.md` for the full enumeration and
  reasoning.
