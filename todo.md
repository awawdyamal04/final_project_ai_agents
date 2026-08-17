# TODO

Mandatory repository content (Appendix E rule 50, PDF p. 149).

Live task list. The full phased breakdown with exit criteria is in
[TASKS.md](TASKS.md); this file tracks what is actually in flight.

---

## Done

- [x] Read `police_thief_p2p.pdf` end to end (160 pages, Hebrew RTL)
- [x] Extract all 55 Appendix E mandatory rules with sanctions and PDF pages
- [x] Extract all 32 Appendix F parameters with value, type, status and owner
- [x] Classify every requirement MANDATORY / RECOMMENDED / EXAMPLE
- [x] Design the minimum architecture
- [x] Design the FastMCP protocol and message schemas
- [x] Map every mandatory rule to a test or deterministic procedure
- [x] Log all contradictions and ambiguities
- [x] Record decisions with reasoning and reversal conditions
- [x] Compliance audit of the documentation against the PDF
- [x] `.gitignore` covering every secret named in the specification
- [x] Initial documentation commit
- [x] **Second-pass audit against the rendered PDF pages** (not text extraction):
      all 55 rules and all 32 parameters re-verified visually; three gaps found
      and fixed (transition-function agreement, binding field names, log record
      schema)
- [x] **Q-20 — two-process HTTP transport stall: root cause proven and fixed.**
      Cause was stdout PIPE backpressure blocking the asyncio loop, not FastMCP
      session accumulation. Event-sink echo now off by default, `--verbose` to
      opt in, uvicorn at `log_level="warning"`; JSONL and audit logging
      unchanged (D-42).
- [x] Q-20 regression tests over real sockets — `tests/peer/test_http_stress.py`
      (repeated real HTTP session reopens) and
      `tests/peer/test_stdout_backpressure.py` (two real peer subprocesses with
      undrained stdout pipes)
- [x] Q-20 end-to-end proof — 35-turn two-process real-HTTP match, both
      processes exit 0, final reveal over all 35 turns, mutual audit both
      directions, both audit chains `Verified OK` (179 records each),
      independent replay `VERIFIED OK` (survival turn 35; thief; cop 5,
      thief 10). Recorded in `results/q20_transport_proof.md`.
- [x] Full suite re-run after the fix: 1467 passed, 3 skipped, 0 failed
- [x] Phases 3 and 4 (strategy heuristics, scent, belief, template verbal
      layer with hint validation and sealed `intent`) were actually complete
      in the imported baseline; `TASKS.md` previously understated this —
      corrected 2026-08-08.
- [x] Independently re-verified the test suite outside the documented
      environment (Python 3.10 + `tomli` shim, since 3.12 wasn't available):
      1465 passed, 3 skipped, 2 failed. Both failures are
      `tests/peer/test_http_stress.py` and
      `tests/peer/test_stdout_backpressure.py` — the two tests that open real
      OS sockets/subprocesses — and both failures trace to this verification
      sandbox's forced SOCKS proxy injection and process resource limits, not
      to the code. Treat the documented 1467/0-failed baseline as confirmed;
      re-run on a clean Python 3.12 host before trusting a "failed" result
      from either of those two files specifically.
- [x] **Wired the `[strategy]` class override** (`police_class`/`thief_class`)
      that had existed as a documented but unread config key since Phase 0.
      `strategy/heuristics.py::load_strategy()` imports, instantiates and
      validates a configured brain, failing fast (`StrategyLoadError`) rather
      than silently running the shipped default (D-43). New tests in
      `tests/strategy/` and `tests/peer/test_orchestrator.py`.
- [x] **Added Ruff** (`pyproject.toml [tool.ruff]`, line-length 100, target
      py312, `select = [E, F, W, I, UP, B, C4, SIM]`). Fixed everything it
      found: 126 auto-fixed (unused imports, import order, pyupgrade), plus
      hand fixes for `try/except/pass` → `contextlib.suppress`, ambiguous `l`
      loop variables, `dict()` → literal, explicit `zip(..., strict=)`, a
      couple of collapsible `if`s, and two intentionally-blind
      `pytest.raises(Exception)` assertions documented with `# noqa: B017`
      rather than narrowed (narrowing would have weakened what those two
      tests actually guarantee — see the inline comments). `ruff check .`
      is clean; full suite re-verified after every batch of fixes, 1474
      passed throughout (no regressions).
- [x] **Created `docs/prd/`** — seven stage PRD stubs (E-50), one per PDF
      Ch. 10 stage, each cross-referencing `TASKS.md` and stating current
      status. Was carried unchecked through every phase in `TASKS.md`; closed
      2026-08-08.
- [x] **Q-19 — `--gui` lifecycle: four separate defects found and fixed.**
      View-state publication timing (`GAME COMPLETE` shown too late), the
      automated PNG screenshot trigger, Ctrl+C/window-close shutdown
      signalling, and a benign uvicorn-internal lifespan `CancelledError`
      traceback — each fixed independently, each with its own regression
      tests (D-44). Verified on real Windows: `game_id`
      `q19-final-proof-35-01`, 35 turns, `GAME COMPLETE` displayed correctly,
      PNG screenshots captured, clean shutdown with no traceback, Final
      Reveal + mutual audit + both audit chains verified, full suite 1563
      passed / 1 skipped / 0 failed. Recorded in `results/q19_gui_proof.md`.

## Start now — external latency, runs in parallel (D-20)

- [ ] Provision Google Cloud project + OAuth consent screen (`gmail.send` scope,
      test users). Account setup only; reporting code stays in Phase 9.
      **Not started as of 2026-08-08.**
- [ ] Begin opponent-team coordination — two counting matches against different
      groups are mandatory and depend on other people's schedules.
      **Not started as of 2026-08-08.**

## Next — `capture_claim` (E-21/E-22), a confirmed compliance gap

**Status: design complete (`prd.md` §14, `plan.md`
`capture_claim` architecture plan,
[docs/CAPTURE_CLAIM_VERIFICATION.md](docs/CAPTURE_CLAIM_VERIFICATION.md)),
implementation not started.** `docs/COMPLIANCE_AUDIT.md` Part 9 has the
original finding. Branch: `feat/capture-claim`. Every task below is
intentionally granular so each can be executed and verified one at a time,
per the Q-19 refactor's lesson that one broad change hides which part
actually broke. **None of these may be marked done until the corresponding
code exists and its own tests pass — this file must not claim
implementation that has not happened.**

**Explicit test coverage checklist (every category required by this pass's
correction — none may be silently dropped; each is elaborated with its
implementation context in the categorized sections below):**
- [ ] Cop initiates claim (primary/mandatory flow, `[A]`)
- [ ] Thief **cannot** initiate a mandatory E-21 claim path — a test proving
      E-21/E-22 compliance holds with the optional self-signal extension
      absent/disabled entirely (guards against ever conflating the two,
      per Correction 1)
- [ ] Truthful confirmation (genuine capture, thief confirms)
- [ ] Truthful denial (no capture, thief denies)
- [ ] False cop claim detected at audit (E-22)
- [ ] False thief denial detected at audit (E-21)
- [ ] No hidden opponent position leaks (claim or response payload)
- [ ] No nonce leaks before the allowed reveal/audit stage (E-18)
- [ ] Duplicate claim idempotency (same `claim_id` re-sent gets the same
      logged response, not a second independent one)
- [ ] Stale **and** future `turn_number` claims both rejected
- [ ] Malformed claim rejected (closed-schema `ProtocolValidationError`)
- [ ] Wrong sender role rejected (e.g. a claim with `claimant_role: "thief"`
      on the mandatory path, or a response with `responder_role: "police"`)
- [ ] Claim/response survives a `to_dict`/`from_dict` serialization round
      trip unchanged
- [ ] A confirmed claim stops future game turns **under our
      `CLAIM_PENDING_AUDIT` design** (prd.md §14.13 — phrase the test and
      its name so it is clear this proves *our* chosen mechanism, not an
      assignment-mandated one)
- [ ] `final_reveal` still runs to completion after a confirmed claim (not
      skipped — prd.md §14.13)
- [ ] Mutual audit still runs to completion after a confirmed claim
- [ ] Replay agrees with a live confirmed claim (recomputed `TerminalResult`
      matches the logged claim/response)
- [ ] Replay detects disagreement when a logged claim contradicts the
      independently recomputed `TerminalResult`
- [ ] Q-18's negotiated `SimultaneityPolicy` is respected — capture_claim
      evaluation uses whichever policy is configured, not a hardcoded one
- [ ] No existing D-41 replay behaviour regresses when no claim is present
      in the log (full backward compatibility with every log produced
      before this feature existed)
- [ ] Real two-peer integration test producing at least one genuine
      exchange end to end

**Protocol definitions**
- [ ] Design the closed `CAPTURE_CLAIM` / `CAPTURE_CLAIM_RESPONSE` payload
      schema in a new `protocol/capture_claim.py` (dataclasses, not inline
      dicts) — fields per `prd.md` §14.8 only (`claim_id`,
      `sub_game_number`, `turn_number`, `claimant_role`/`responder_role`,
      `claim_kind`, `verdict`, `commitment`); **no coordinate, cell, or
      nonce field, ever** (`prd.md` §14.6/§14.7)
- [ ] Add the two `MessageType` enum members + payload-key table row to
      `protocol/messages.py` (minimal addition only — see `plan.md`)

**Serialization validation**
- [ ] `to_dict`/`from_dict` round-trip tests for the new schema
- [ ] Reject malformed/unknown-key claim payloads the same way the existing
      envelope does (closed schema, `ProtocolValidationError`)
- [ ] Reject a claim/response referencing a stale **or future**
      `turn_number`
- [ ] Reject a claim/response with the wrong `claimant_role`/`responder_role`
      for its message type
- [ ] Idempotent handling of a duplicate `claim_id`

**Peer handling**
- [ ] `peer/capture_claim_runtime.py`: **primary, mandatory path** —
      cop-side claim issuance (`CAPTURE_CLAIM`, belief-based, always
      pending thief confirmation — cop can never self-verify, E-9) and
      thief-side response handling (`CAPTURE_CLAIM_RESPONSE`, dispatching
      to `domain/capture_claim.py` to compute a truthful verdict)
- [ ] **[B, optional extension, explicitly not part of E-21/E-22
      compliance]** thief proactive self-signal path (barrier-on-thief,
      no-legal-move) — if built at all, in a clearly separate function from
      the mandatory path above, and covered by its own,
      separately-skippable test file (`plan.md` "Tests")
- [ ] Orchestrator dispatch-table entries for the two new `MessageType`s
      (minimal footprint in `peer/orchestrator.py`, per `plan.md`)
- [ ] `_play_turns` early-exit hook implementing `CLAIM_PENDING_AUDIT`
      (deferred until §Terminal state below is settled or explicitly
      documented as a design decision — do not implement the exit first)

**Information-boundary checks**
- [ ] Structural test: the `CAPTURE_CLAIM_RESPONSE` payload has no field
      capable of carrying the thief's position, nonce, unrevealed action,
      or any other hidden state (prd.md §14.6/§14.7 — this is the core
      regression guard for Correction 2)
- [ ] Structural test: `LocalState` still has no opponent-position
      attribute after this feature exists (regression guard on D-9)
- [ ] Structural test: the live GUI never renders a value sourced from a
      claim/response record before that record is legitimately public

**Cryptographic verification**
- [ ] `crypto/capture_claim_seal.py` reusing `crypto/sealed.py`
      `commit()`/`verify()` — no new primitive (labelled `[B]`, prd.md
      §14.10 — reuse is a design choice on cost/risk grounds, not an
      assignment mandate)
- [ ] Nonce-secrecy test: claim/response record never carries a nonce early
      (same discipline as ordinary `reveal`, E-18)
- [ ] False-claim detection test (E-22): cop claims falsely, caught at audit
- [ ] False-denial detection test (E-21): thief denies falsely, caught at
      audit
- [ ] Explicit test that a live `confirm`/`deny` verdict is **not**, on its
      own, treated as proof of anything (prd.md §14.11's live-vs-
      authoritative distinction) — i.e. a confirmed claim that audit later
      contradicts must still be caught, not waved through because it was
      "confirmed live"

**Audit logging**
- [ ] `audit/capture_claim_records.py` — claim/response as first-class
      hash-chained records via the existing `audit/writer.py`/`chain.py`
- [ ] Audit-chain integrity test: tampering with a claim/response record is
      detected the same way as tampering with any other record

**Terminal state**
- [ ] Confirm or revise the `CLAIM_PENDING_AUDIT` design (prd.md §14.13,
      labelled `[B]`, a design decision made in this correction pass, not
      an assignment citation) before wiring `_play_turns`
- [ ] `domain/terminal.py` / `TerminalResult` interaction: does a confirmed
      claim produce a `TerminalResult` synchronously, or only replay does —
      decide and document in `docs/DECISIONS.md`
- [ ] Test: on denial, gameplay continues and the denial remains logged/
      auditable (prd.md §14.13)

**Scoring**
- [ ] Confirm `evaluate_full_turn_capture`'s `CaptureReason` maps 1:1 to the
      claim `claim_kind` field (`landed` / `barrier_on_thief` /
      `no_legal_move`) with a test, not by inspection alone
- [ ] Confirm scoring (`config.scoring.capture_cop`/`capture_thief`) is
      unaffected — capture_claim changes *when* a result is known, not the
      scoring table itself

**Replay**
- [ ] `replay/capture_claim_check.py` — compare a logged claim/response
      against the independently recomputed `TerminalResult`, **checking
      it, never adopting it** (prd.md §14.11)
- [ ] Extend D-41's four-verdict model with a fifth comparison outcome
      (claim agrees / claim disagrees / no claim present) — decide whether
      this is a new verdict or an annotation on an existing one, in
      `docs/DECISIONS.md`
- [ ] Test: replay agrees with a genuine, truthful live claim
- [ ] Test: replay detects and flags disagreement when a logged claim
      contradicts the independent recomputation
- [ ] Test: capture_claim evaluation respects whichever `SimultaneityPolicy`
      is configured (Q-18 consumption, not resolution — prd.md §14.9.1)
- [ ] Regression test: replay's `VERIFIED OK` is unweakened when no claim
      is present in the log (backward compatibility with every existing log)

**Unit tests**
- [ ] One test file per new module (see `plan.md` "Tests" — none share a
      file with an unrelated existing suite)

**Integration tests**
- [ ] A fixture reproducing a real trapped-thief/landed-on/barrier-on-thief
      board state, proving identical terminal turn/reason/winner/score
      between the live claim path and the independent replay path
- [ ] Test: `final_reveal` and mutual audit both still run to completion
      after a confirmed claim (not short-circuited)

**Two-peer real run**
- [ ] Real two-process match producing at least one genuine capture_claim
      exchange end to end (mirrors the Q-19/Q-20 proof runs)
- [ ] Resulting audit log passes mutual audit and replay `VERIFIED OK`

**Regression suite**
- [ ] Full `pytest -q` green, no regression against the pre-feature
      baseline (1551 passed / 4 pre-existing sandbox-only failures / 8
      skipped, this sandbox; confirm the documented Windows baseline
      separately)

**Ruff**
- [ ] `ruff check .` clean after every new module, not only at the end

**Python line-count verification**
- [ ] `find src tests -name "*.py" -exec wc -l {} + | sort -nr | awk '$1 > 150'`
      shows no new file introduced by this feature over 150 lines

**Documentation**
- [ ] `docs/COMPLIANCE_AUDIT.md` Part 9: correct E-21/E-22 from
      documentation-era `COVERED` to implementation-era `COVERED` — only
      once the above is actually true
- [ ] `docs/ACCEPTANCE_TESTS.md`: move the `test_e21_...`/`test_e22_...`
      entries out of "remains a specification for a later phase" once real
      tests exist
- [ ] `docs/DECISIONS.md`: new decision entry recording the terminal-state
      and replay-relationship choices actually made during implementation
- [ ] `README.md`: update once there is real, verified behaviour to report
      (not before)

**Git commit/push**
- [ ] Small commits after each verified module (per `CLAUDE.md` §4), not
      one large commit at the end
- [ ] Push only on explicit instruction — not implied by this checklist
      existing

## Next — Phase 8, public exposure and a real remote match

Phases 0–7b are complete (see `TASKS.md`). The next unimplemented mandatory
phase is Phase 8:

- [ ] Bind the server to a host/port suitable for tunnelling
- [ ] Document the tunnel procedure in `README.md` (ngrok or Localtonet)
- [ ] Opponent URL from `config/game.toml → [network] opponent_url` (key exists;
      confirm it's actually read end to end for a non-localhost host)
- [ ] Timeout/retry behaviour validated against real network latency
- [ ] Play a full match against a peer on a different machine — depends on
      opponent-team coordination above

## Blocked / needs an answer

- [ ] **Q-12 — step-zero signing key.** The specification says the declaration is
      signed "with a pre-supplied key" but never says who supplies it, what
      algorithm, or how it is verified. Interim: SHA-256 commitment (D-8).
      **Ask the lecturer before the first counting match.** Do not invent a key
      scheme.

## Must be negotiated with each opponent team

Before any counting match. These are properties of a judge-free protocol — both
sides must compute identically, so both sides must agree first.

- [ ] Shared config values, including `num_games` = 6 (Q-1)
- [ ] Sealed-record schema for the commit hash (Q-4)
- [ ] Turn model — simultaneous under commit-reveal (Q-2)
- [ ] Capture resolution under simultaneous movement (Q-9)
- [ ] Scent emission/decay model with its concrete numeric example (E-23)
- [ ] Response and watchdog timeouts (Q-5)

## Before submission

- [ ] Split into two repositories, cop and thief
- [ ] Academic README in both, with all six mandatory components
- [ ] Document every contradiction choice in the README
- [ ] Screenshots: live belief map; replay showing `Verified OK`
- [ ] Verify no secret anywhere in **full** git history
- [ ] Annotated tag `v1.0-submission`, pushed
- [ ] Moodle: PDF form unaltered, one submission per member, 8-character group
      code, self-grade for code quality only
