# TASKS

Dependency-ordered phases, optimised for the fastest path to a working compliant
MVP. Ownership is deliberately unassigned.

**Legend.** `[M]` mandatory for compliance · `[O]` optional enhancement ·
`[P]` process/administrative obligation.

**Exit criterion for every phase:** the system runs **end-to-end** at that
phase's scope, and the phase's tests pass. This follows the PDF's incremental
delivery principle (Ch. 10) — each layer is built, tested and stabilised
*before* the next is laid on it, so at any moment the space of possible faults
is confined to the layer just added.

The PDF's own seven-stage order (Ch. 10, PDF pp. 101–103) is a
**recommendation**, not a rule. Phases below follow it closely because its
rationale is sound, with two deviations noted at Phase 4 and Phase 6.

---

## Phase 0 — Configuration foundation `[M]` ✅ COMPLETE

*No dependencies. Nothing here touches game logic.*
*214 tests passing. Shipped config hashes to `410066bf…fd0a24d`.*

- [x] `[M]` `pyproject.toml`: Python 3.12, src layout, `pytest`. No third-party
      runtime dependency yet — `fastmcp` arrives in Phase 2.
- [x] `[M]` Package skeleton `src/police_thief/` with `config/` and
      `domain/enums.py`.
- [x] `[M]` `config/game.json` (Appendix F values, `num_games: 6` per D-2) plus
      `config/cop.toml.example` and `config/thief.toml.example`. One shared
      constitution; per-role runtime directories (D-23, superseding D-18).
- [x] `[M]` Config loader producing **typed frozen** objects.
- [x] `[M]` Central parameter policy table (`config/policy.py`) — all 32
      Appendix F parameters as data, self-checking at import. **The only module
      permitted to hold an Appendix F literal.**
- [x] `[M]` Validator enforcing FIXED / MINIMUM / NEGOTIABLE semantics.
- [x] `[M]` Canonical JSON helper — single implementation, used by config
      hashing and reserved for commit-reveal, log hashing and artefacts.
- [x] `[M]` `config_sha256` — deterministic, order- and whitespace-independent,
      unaffected by private configuration. **Hash only**; signing waits on Q-12.
- [x] `[M]` Duplicate-key detection via `object_pairs_hook`.
- [x] `[M]` Closed schema — rejects unknown, renamed and missing keys. Field
      names are fixed and binding (PDF p. 130); a silently-ignored key is how two
      peers end up computing different physics while both believe they agreed.
- [x] `[M]` Cross-field validation; derived rules marked `DERIVED` (D-22).
- [x] `[M]` Private config kept separate and forbidden from shadowing a shared
      key (D-21).
- [x] `[M]` `python -m police_thief.config.verify` CLI, non-zero exit on
      failure, no secret material printed.
- [x] `[M]` `tests/config/` — 214 tests.
- [x] `[P]` `plan.md` and `todo.md` at repo root (E-50).
- [ ] `[P]` `docs/prd/` with seven PRD stubs, one per development stage (E-50).
      *Carried into Phase 1 — administrative, not blocking.*

**Starts now, runs in parallel with every phase** (D-20 — these have external
latency that engineering cannot compress):

- [ ] `[P]` Provision the Google Cloud project and OAuth consent screen: enable
      Gmail API, add test users, scope `gmail.send` only. Account setup only —
      the reporting code stays in Phase 9. Consent-screen approval can stall.
- [ ] `[P]` Begin opponent-team coordination. E-31 needs ≥2 counting matches
      against **different** groups, each requiring a negotiated shared config;
      this depends on other people's schedules. Start the conversations before
      the code is ready, not after.

**Exit:** `pytest` runs green on config load/validate.
**Tests:** E-12 (parametrised over every MINIMUM and FIXED parameter), canonical
serialisation key-order independence.

---

## Phase 1 — Base logic, single process `[M]` ✅ COMPLETE

*Depends on Phase 0. Corresponds to PDF stage 1. No network, no crypto, no AI.*
*171 domain tests; 385 total, all passing.*

- [x] `[M]` `domain/state.py` — local truth. **No attribute for the opponent's
      position** (D-9), frozen and slotted so one cannot be attached at runtime.
- [x] `[M]` `domain/coordinates.py`, `domain/board.py` — geometry, bounds, the
      barrier set, deterministic queries. All dimensions from `SharedConfig`.
- [x] `[M]` `domain/rules.py` — legal move set (orthogonal + STAY, no
      diagonals), bounds, barrier occupancy, deterministic legal-action order.
- [x] `[M]` Barrier mechanics: cop-only, placement replaces movement, within one
      step, quota `max_barriers`, permanent, impassable to both, declared
      explicitly (E-15, E-16).
- [x] `[M]` Capture — all three conditions: cop lands on thief's cell; barrier
      on thief's cell (E-46); thief with no legal relocation (E-47, D-26).
- [x] `[M]` `domain/terminal.py` — survival threshold, move ceiling, technical
      loss, structured `TerminalResult`.
- [x] `[M]` `domain/scoring.py` — single entry point, all values from config.
      Tie rule provided separately as match-level (Ch. 9), not a sub-game
      outcome.
- [x] `[M]` `domain/transition.py` — deterministic, pure, validation before
      application so an illegal action never partially modifies state.
- [x] `[M]` `domain/simultaneity.py` — the unresolved Q-2/Q-9 cases isolated
      behind a swappable policy rather than silently decided.
- [x] `[M]` `sim/` — test-only headless harness, trivial deterministic policies,
      `python -m police_thief.sim.headless`.

**Exit criterion met:** two agents move legally on the grid; a move into a
barrier is rejected; coordinate overlap triggers capture; a full sub-game
terminates with a correct score. (PDF stage-1 milestone.)

**Carried forward:** `docs/prd/` seven PRD stubs (E-50), still administrative.

---

## Phase 2 — FastMCP infrastructure, two processes `[M]` ✅ COMPLETE

*Depends on Phase 1. Corresponds to PDF stage 2. Transport and handshake;
turn payloads arrive with commit-reveal in Phase 5.*
*331 new tests; 716 total, all passing. fastmcp pinned at 3.4.5.*

- [x] `[M]` `protocol/` — closed-schema envelope (10 keys), typed payloads per
      message type, canonical-JSON codec with a 64 KiB bound, versioning
      (schema exact, protocol major-compatible), action wire codec (D-30,
      defined now, transmitted from Phase 5).
- [x] `[M]` `peer/server.py` — FastMCP server: `health_check` +
      one generic validated receiver (D-29). Never mutates LocalState; no game
      logic; structured `ok:false` replies rather than transport exceptions.
- [x] `[M]` `peer/client.py` — FastMCP client: gatekeeper-admitted, deadlined,
      bounded retries with preserved message ids; failure taxonomy
      (unavailable / timeout / rejection / invalid response).
- [x] `[M]` `peer/states.py` — 13-state lifecycle machine; illegal transitions
      raise without state change (E-4, E-5); terminal-state immutability;
      idempotent re-entry; timestamped transition history.
- [x] `[M]` `peer/orchestrator.py` — single gateway (E-3); identity checks
      (game id, sender/receiver role); hello→config-hash→ready handshake;
      refuse-to-play on hash mismatch (E-11); dependency-injected throughout.
- [x] `[M]` `peer/registry.py` — bounded idempotency registry (D-31): cached
      replies for exact duplicates, `ConflictingDuplicateError` for id reuse,
      LRU eviction at `queue_depth`.
- [x] `[M]` `peer/gatekeeper.py` — queue → token-bucket rate → concurrency
      admission from Appendix F values (E-28 foundation, reusable for Phase 9).
- [x] `[M]` `peer/deadline.py` — deadline tracker + bounded retry (E-6),
      fire-once watchdog (E-7), fake-clock testable.
- [x] `[M]` `peer/events.py` — operational JSONL log that *refuses* to record
      secrets or opponent positions (D-33). Explicitly not the audit chain.
- [x] `[M]` `peer/run.py` — independent entry point per peer; role from
      private config; non-zero exit on failed handshake; Ctrl+C-safe.
- [x] `[M]` `scripts/run_two_peers.py` — launches two real processes;
      demonstrated: symmetric READY, delayed start, config mismatch (both
      refuse, both exit 1), peer unavailable (exit 1), clean shutdown.

**Exit criterion met:** two real OS processes handshake over HTTP FastMCP,
verify identical config hashes, and both reach READY with no central process.

**Deferred to Phase 5 deliberately:** the cryptographic match log (the JSONL
here is operational telemetry only, D-33), turn messages, and the
`(game_id, sub_game, step, role)` idempotency key — Phase 2's key is
`message_id`; the turn-scoped key needs turns to exist.

**Carried forward:** `docs/prd/` seven PRD stubs (E-50).

---

## Phase 3 — Strategy module, "blind" `[M]`

*Depends on Phase 2. Corresponds to PDF stage 3. Full information; no scent, no
language, no deception yet.*

- [ ] `[M]` `strategy/base.py` — `BrainBase` with `_pick_move` / `_decide_move`,
      wired at the mandated seam: after hint decode, before commit packing.
- [ ] `[M]` `strategy/heuristic.py` — Manhattan-distance policy against a known
      target (D-14).
- [ ] `[M]` Strategy class selection via `config/game.toml → [strategy]`.

**Exit:** given a known target location, the agent computes and executes the
shortest path with no manual intervention. (PDF stage-3 milestone.)
**Tests:** shortest-path correctness; legality of every emitted move; strategy
module is genuinely separable (swap the brain, everything else unchanged).

---

## Phase 4 — Scent, belief and natural language `[M]` (partially COMPLETE)

**Done:** scent emission/decay from config (D-39), Bayesian belief map with
impossible-cell exclusion (D-40), `BaseStrategy` + `LocalView`, deterministic
cop and thief heuristics, per-peer `OpponentTracker`, strategy wired in before
sealing. 1342 tests; 20 automated games all terminate; two real processes play
6 strategy-driven crypto turns with mutual audit `Verified OK`.

**Not done, deliberately:** the natural-language hint layer (template provider)
and the LLM modes. The `hint` field is already sealed and revealed end to end,
so that layer plugs in without a protocol change.

**Original plan below.**

## Phase 4 — Scent, belief and natural language `[M]` (original)

*Depends on Phase 3. Corresponds to PDF stage 4 — the PDF calls this the most
sensitive stage.*

**Deviation from PDF ordering:** the PDF folds LLM integration into this stage.
We implement the **template** verbal provider only (D-13), deferring any actual
model. Template is the PDF's own default and costs zero tokens, so this is a
narrowing of scope, not a reordering.

- [ ] `[M]` `domain/scent.py` — emission window, radial falloff, decay
      `τ(t+1) = max(0, (1−ρ)·τ(t) + Δτ)`, applied **once per full turn** after
      both moves.
- [ ] `[M]` Each peer observes **only the opponent's** field.
- [ ] `[M]` `domain/belief.py` — Bayesian belief map with a hint-reliability
      coefficient; updated from scent and from received hints.
- [ ] `[M]` `strategy/verbal.py` — the `template` provider: produce a hint,
      classify an incoming hint. Zero tokens, deterministic.
- [ ] `[M]` Hint validation: ≤ `hint_max_words`; reject numeric position
      encodings (E-26, E-27).
- [ ] `[M]` `intent` flag (`truth` / `lie`) carried and later sealed.
- [ ] `[M]` Strategy switches to belief-driven target selection.

**Exit:** free-language reporting is translated into inference; the scent map
updates and decays every step; the verbal layer produces a hint (true or false).
(PDF stage-4 milestone.)
**Tests:** all of §4 in [ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md), plus
E-25, E-26, E-27.

---

## Phase 5 — Security and cryptography `[M]` ✅ COMPLETE
*(delivered as "Phase 3" in the session sequence; 591 new tests, 1307 total)*

- [x] `[M]` `crypto/sealed.py` — closed ten-key sealed record (D-34),
      `SHA256(canonical_json_bytes(record))`, versioned schema, `state` as a
      hash so a position never reaches the wire.
- [x] `[M]` `crypto/nonce.py` — `secrets.token_hex(16)`, lowercase hex, local
      reuse guard (D-35).
- [x] `[M]` `crypto/coordinator.py` — the four PDF phases, duplicate/conflict/
      replay handling, abandonment that discards the pending nonce, final-reveal
      verification.
- [x] `[M]` **E-18 honoured**: the per-turn reveal carries no nonce; all nonces
      are disclosed only in `FINAL_REVEAL` (D-36). The reveal schema has no
      nonce field, so omission is structural.
- [x] `[M]` `audit/` — hash-chained append-only JSONL, explicit genesis, and an
      independent verifier detecting modification, deletion, insertion,
      reordering, duplicate ids and malformed lines (D-37).
- [x] `[M]` Turn states added to the state machine; the only edge into
      `REVEAL_ALLOWED` is from `BOTH_COMMITS_RECEIVED`, and into `APPLYING_TURN`
      from `BOTH_REVEALS_VERIFIED`.
- [x] `[M]` `crypto/stepzero.py` — interface and declaration only. Signing
      **deliberately unimplemented**; Q-12 remains open and no key scheme was
      invented.
- [x] `[M]` Demonstrated with two real processes: 2 crypto turns, mutual audit
      both directions, chain `Verified OK`; plus tampered action, tampered
      nonce, opponent unavailable, and offline audit-tamper detection.

**Deferred, correctly:** deadline/watchdog integration was already delivered in
Phase 2. The capture claim (E-21/E-22) and the two-log game replay (E-20) are
Phase 6.

---

## Phase 5 — Security and cryptography `[M]` (original plan, superseded above)

*Depends on Phase 4.*

**Deviation from PDF ordering:** the PDF places cloud exposure (stage 5) before
cryptography (stage 6). We invert. Rationale: crypto is testable entirely
offline and is the highest-consequence rule cluster (E-17 through E-24, plus
E-19's score-zero sanction), whereas tunnelling is external tooling that adds no
testable code. Inverting keeps the fault space confined to code we wrote. The
PDF's stated reason for its order — *don't debug crypto through an unproven
transport* — is honoured, because Phase 2 already proved the transport over
localhost.

- [ ] `[M]` `crypto/commit.py` — canonical sealed record per D-4;
      `SHA256(canonical_json(record))`; nonce via `secrets.token_hex(16)`.
- [ ] `[M]` Four-phase sequencing: commit → acknowledge → reveal (**nonce
      withheld**) → final reveal (E-17, E-18).
- [ ] `[M]` `crypto/audit.py` — mutual audit recomputing every hash; mismatch ⇒
      technical loss, score 0 (E-19, E-36).
- [ ] `[M]` Config-hash exchange in `hello`; refuse to play on mismatch (E-11).
- [ ] `[M]` Scent-model hash including the numeric example; refuse on mismatch
      (E-23).
- [ ] `[M]` `crypto/step_zero.py` — hardware + code version + team + sub-game +
      **commit hash** (E-24, E-53), sealed per D-8.
- [ ] `[M]` Capture claim with the thief's truthful sealed response (E-21,
      E-22).
- [ ] `[M]` Deadline tracker and watchdog (E-6, E-7) — deferred to here because
      they need a real protocol to guard.

**Exit:** a move is committed then revealed with a valid nonce; step-zero
verifies hardware; a deliberately tampered log is caught by the audit. (PDF
stage-6 milestone.)
**Tests:** all of §3 in [ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md), plus
E-6, E-7.

---

## Phase 6 — Replay verifier `[M]` ✅ COMPLETE
*18 new tests; 1360 total. Real 35-turn two-process game replays VERIFIED OK,
reconstructing a capture at turn 30 (cop 20, thief 5).*

- [x] `[M]` `replay/verifier.py` — loads both logs, verifies both chains,
      matches by game/sub-game/turn, re-hashes every commitment against the
      revealed nonces in both directions, checks each turn reveal against its
      final sealed record, re-applies the physics and simultaneity policy, and
      recomputes the winner and score independently (D-41).
- [x] `[M]` Four verdicts: VERIFIED OK / TAMPERED / INCOMPLETE / POLICY
      MISMATCH. Ten tampering cases demonstrated against real logs.
- [x] `[M]` `replay/viewer.py` — offline board render with both positions,
      barriers, actions, hints and intent, result and stamp. Live code is
      asserted never to import it.
- [x] `[M]` `sub_game_start` / `sub_game_end` records so preconditions and
      claims are checkable.

**Original plan below.**

## Phase 6 — Replay verifier `[M]` (original)

*Depends on Phase 5. Brought forward from the PDF's stage 7 because it is the
strongest automated check we have on the crypto layer, and a mandatory
submission artefact in its own right (E-20).*

- [ ] `[M]` `replay/verifier.py` — **pure function** over a log file, returning
      `Verified OK` / `TAMPERED` plus the offending entry (D-12). Shared with
      the end-of-match mutual audit — one implementation, not two.
- [ ] `[M]` `replay/viewer.py` — Tkinter window: load `[log_file]`, step
      forward/backward, green `Verified OK` stamp or red `TAMPERED` banner.
- [ ] `[M]` Log sealing: JSONL → canonical `log_<game_id>_g<NN>.json` (D-15).
- [ ] `[M]` `replay --log <path>` entry point.

**Exit:** clean log ⇒ `Verified OK`; single-character tamper ⇒ `TAMPERED`;
viewer steps through a recorded sub-game.
**Tests:** E-19, E-20, tamper parametrised across every sealed field.

---

## Phase 7 — Live GUI `[M]` ✅ COMPLETE (one limitation, Q-19)
*34 new tests; 1394 total. Two-process GUI game completes with mutual audit
`Verified OK`; screenshots in `results/screenshots/`.*

- [x] `[M]` `gui/view_model.py` — frozen `LiveView` with no field for the
      opponent's position, so a renderer cannot draw one.
- [x] `[M]` `gui/live.py` — belief heatmap, sensed scent, own cell, barriers,
      turn banner, status panel, hint with declared intent, errors.
- [x] `[M]` Tk on the main thread, peer asyncio in a worker; frozen snapshots
      cross the boundary lock-free.
- [x] `[M]` Headless by default — `--gui` is opt-in, so tests and CLI runs are
      unchanged.
- [x] `[M]` Screenshot capture for the submission evidence.
- [ ] `[M]` Q-19: runs beyond ~6 turns under `--gui` destabilise the server.

**Original plan below.**

## Phase 7 — Live GUI `[M]` (original)

*Depends on Phase 4 (belief) and Phase 2 (state machine). Independent of
Phases 5–6, so it can proceed in parallel.*

- [ ] `[M]` `gui/live.py` — Tkinter: belief heatmap grid, deeper colour = higher
      probability; own position marked; barriers marked.
- [ ] `[M]` Turn banner: green `YOUR TURN` on receipt; grey `LOCKED` after
      commit, with input ignored while locked.
- [ ] `[M]` GUI constructed with handles to local-truth and belief modules
      **only** (D-9, E-8, E-9).
- [ ] `[M]` Tk main thread + asyncio worker thread with a queue drained by
      `root.after()`.

**Exit:** the GUI displays a live sub-game; no window can show the opponent's
true position.
**Tests:** E-8, E-9 — including the structural assertion that the live state
object has no opponent-position attribute.

---

## Phase 7b — Transport stabilisation, Q-20 `[M]` ✅ COMPLETE
*2 new tests; 1467 passed, 3 skipped, 0 failed. A real 35-turn two-process HTTP
match now completes, audits and replays `VERIFIED OK`.*

Unplanned, and the blocker that stood between a working local system and
Phase 8. Recorded as its own phase because it is the only work whose deliverable
is a *proof* rather than a feature.

- [x] `[M]` Root cause proven: **stdout PIPE backpressure**, not FastMCP
      session accumulation. A synchronous `print(..., flush=True)` from inside
      the asyncio loop, plus uvicorn's per-request INFO lines, filled an
      undrained capture pipe; the blocked write parked the event loop, so each
      process stayed alive while its server stopped accepting connections
      (~40 s of measured loop lag).
- [x] `[M]` Fix: event-sink `echo=False` by default in `peer/run.py`; new
      `--verbose` flag to opt back in; `PeerServer` uvicorn
      `log_level="warning"`. JSONL operational logging and the hash-chained
      audit log are unchanged and remain authoritative (D-42).
- [x] `[M]` `stateless_http=True` / `json_response=True` retained as transport
      simplifications — safe, but explicitly **not** the fix.
- [x] `[M]` Regression guards over real sockets:
      `tests/peer/test_http_stress.py` (45 real HTTP sessions across reopen
      cycles and a concurrent burst) and
      `tests/peer/test_stdout_backpressure.py` (two real peer subprocesses
      played through deliberately undrained stdout pipes).
- [x] `[M]` End-to-end proof, `game_id` `real-game-001`: 35 turns completed,
      both processes exit 0, no `PeerTimeoutError`, no `send_unacknowledged`, no
      connection-refused restart; final reveal over all 35 turns; mutual audit
      both directions; both audit chains `Verified OK` (179 records each);
      independent replay `VERIFIED OK` — survival on turn 35, winner thief,
      cop 5 / thief 10.
- [x] `[M]` Evidence recorded in
      [results/q20_transport_proof.md](results/q20_transport_proof.md).

**Exit criterion met:** two real OS processes play a full sub-game to its
terminal condition over real HTTP, and an independent offline replay agrees.

**Not addressed here:** Q-19 (`--gui` instability) was previously assumed to
share this cause. That link is unproven and Q-19 has not been retested against
the fix; it stays open.

---

## Phase 8 — Public exposure and a real remote match `[M]`

*Depends on Phases 2–7. Corresponds to PDF stage 5.*

- [ ] `[M]` Bind the server to a host/port suitable for tunnelling.
- [ ] `[M]` Document the tunnel procedure in `README.md` (ngrok or Localtonet —
      external tooling, not our code).
- [ ] `[M]` Opponent URL from `config/game.toml → [network] opponent_url`.
- [ ] `[M]` Timeout and retry behaviour validated against real network latency,
      not just a fake clock.
- [ ] `[M]` Play a full match against a peer on a **different machine**.

**Exit:** an agent on a remote machine connects via the tunnel and plays a full
round. (PDF stage-5 milestone.)
**Tests:** E-10 (manual, off-host handshake); E-6 under real latency.

---

## Phase 9 — Reporting shell `[M]`

*Depends on Phase 8. Corresponds to PDF stage 7. The PDF is explicit that this
is built last because it consumes every layer beneath it.*

- [ ] `[M]` `report/build.py` — the four artefacts: `declaration_<game_id>.json`,
      `config_<game_id>_g<NN>.json`, `log_<game_id>_g<NN>.json`,
      `result_<game_id>.json`. Mandatory fields: both teams' GitHub links (four
      total), per-sub-game commit hash, total tokens consumed.
- [ ] `[M]` `report/gatekeeper.py` — Quota Manager → Token Bucket → DOS
      Detector, in that order, fail fast (E-28, E-29).
- [ ] `[M]` `report/gmail.py` — OAuth 2.0, scope **`gmail.send` only** (E-30);
      JSON as **attachment**, never free text (E-33, E-34); honour 429 with
      backoff.
- [ ] `[M]` Recipient fixed to `rmisegal+uoh26finalgame@gmail.com` (E-51).
- [ ] `[M]` Send gated on `result_agreement` (E-35) and a passed audit (E-36).
- [ ] `[M]` `mode` defaults to `send`; `draft` refused for counting matches
      (D-5).
- [ ] `[M]` `matches/<game_id>/` artefact store, committed (Appendix F §2).
- [ ] `[M]` Counted-match ledger driving the E-37 declaration, derived from
      artefacts rather than hand-set (E-38).
- [ ] `[P]` OAuth setup per Appendix A: enable Gmail API, consent screen, test
      users, `gmail.send` scope, desktop credentials, first authorisation.
      **`credentials.json` and `token.json` into `.gitignore` before any
      commit** (E-39, E-40) — already covered by the shipped `.gitignore`.

**Exit:** a match summary is sent by Gmail with the JSON attached and arrives
intact. (PDF stage-7 milestone.)
**Tests:** all of §5 and §6 in
[ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md).

---

## Phase 10 — League play `[M][P]`

*Depends on Phase 9.*

- [ ] `[P]` Negotiate with each opponent team before playing: shared config
      values, sealed-record schema (D-4), turn model (D-6), capture resolution
      (D-7), scent model + numeric example (E-23). See the NEGOTIATE items in
      [OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md).
- [ ] `[P]` Warm-up matches (uncounted, permitted and recommended) for
      calibration.
- [ ] `[M]` At least `min_games_to_pass` = 2 counting matches against
      **different** groups (E-31); at most `max_games_per_team` = 10.
- [ ] `[M]` Exactly one counting match per opponent (E-52).
- [ ] `[M]` Both sides send their own report for every counting match (E-35).
- [ ] `[M]` Commit each match's artefacts.
- [ ] `[P]` Escalate [OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) Q-12
      (step-zero signing key) to the lecturer **before** the first counting
      match.

---

## Phase 11 — Submission `[M][P]`

*Depends on Phase 10.*

- [ ] `[M]` Split into two repositories, cop and thief (D-16, E-49).
- [ ] `[M]` `README.md` in **both** repos with all six mandatory components
      (Ch. 9, PDF p. 97) — see the checklist in
      [ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) §7.
- [ ] `[M]` Document every contradiction choice from
      [OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) in the README — where
      identified, what chosen, why (PDF p. 5).
- [ ] `[M]` Screenshots: Live GUI belief map; Replay showing `Verified OK`.
- [ ] `[M]` Cross-link the two repositories in both READMEs.
- [ ] `[M]` `prd.md`, `plan.md`, `todo.md` present in both repos (E-50).
- [ ] `[M]` Verify no secret anywhere in **full git history**, not just HEAD
      (E-39).
- [ ] `[M]` Annotated tag `v1.0-submission`, pushed (E-41).
- [ ] `[P]` Repos public, or shared with `rmisegal@gmail.com`.
- [ ] `[P]` Moodle: PDF form with no field altered or moved (E-43); one
      submission per member (E-44); 8-character group code (E-45); self-grade
      for **code quality only** (E-55).

---

## Optional enhancements `[O]`

Not to be started until every `[M]` item above is complete and verified.

- [ ] `[O]` `ollama` verbal provider — local model, zero API tokens.
- [ ] `[O]` `claude_api` / `claude_cli` providers. Note the brief excludes paid
      LLM APIs; treat as out of scope unless that changes.
- [ ] `[O]` `every_n_steps` throttling for the verbal layer.
- [ ] `[O]` Richer movement policy — minimax / expectimax over the belief map,
      barrier-trap planning.
- [ ] `[O]` Reinforcement learning (Q-Learning). **Explicitly optional**; the
      course did not teach it; only after all mandatory work is verified.
- [ ] `[O]` Learning curves in the README — only meaningful if RL is used.
- [ ] `[O]` Research and performance-analysis report
      (`RESEARCH-REPORT-Performance-Analysis.md`) — the PDF marks this
      "highly recommended".
- [ ] `[O]` Visual polish beyond the mandated heatmap and banner. Lowest
      priority in the stated ordering.

---

## Implementation notes carried forward

- **Watchdog placement.** Phase 5 ships it as an asyncio task. If the loop
  itself can wedge, it must be promoted to a separate thread. Decide by
  measurement — deliberately induce a loop stall and observe whether the task
  still fires — not by speculation.
- **`--sub-games N` override.** Development convenience only; must be refused
  when a match is flagged as counting (D-2).
- **One canonical-JSON implementation.** Config hashing, commit hashing and
  artefact writing must all call the same helper. Two implementations will
  eventually disagree, and the failure mode is a failed audit in a real match.
