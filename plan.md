# PLAN

Work plan. Mandatory repository content (Appendix E rule 50, PDF p. 149).

The detailed, dependency-ordered breakdown lives in [TASKS.md](TASKS.md); this
file states the strategy those phases serve.

---

## Objective

Build the **smallest reliable implementation** that satisfies every mandatory
requirement in `police_thief_p2p.pdf`. Not the most capable agent — the most
compliant, verifiable and complete system.

## Approach

**Build in verified vertical slices.** Each phase produces a system that runs
end-to-end at its own scope and passes its own tests before the next phase
begins. At any moment, the space of possible faults is confined to the layer
just added. This is the specification's own incremental-delivery principle
(Ch. 10), and it is the reason the plan resists the temptation to start with the
interesting parts — cryptography, tunnels, language models — before the boring
parts are proven.

**Compliance is designed in, not inspected in.** The rules with the heaviest
sanctions (never show the opponent's true position; never share state between
roles; never lower a mandatory parameter) are enforced by structure — an absent
attribute, an import-graph constraint, a config validator — so that a violation
surfaces as a failing test rather than as a disqualification discovered at
submission.

**Every mandatory behaviour has a named verification.** Test functions carry
their rule ID, so the compliance argument is greppable rather than assertive.
[docs/ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) is the map from the 55 rules
to the tests and procedures that discharge them.

## Sequence

1. **Foundation** — config model, validator, canonical serialisation, test
   skeleton.
2. **Base logic** — grid, movement, barriers, capture, scoring, single process.
3. **Transport** — FastMCP server and client, state machine, orchestrator, two
   processes.
4. **Intelligence** — strategy module, scent physics, belief map, verbal layer.
5. **Integrity** — commit-reveal, mutual audit, step-zero, deadlines, watchdog.
6. **Evidence** — replay verifier and viewer; live GUI.
7. **Reach** — public exposure via tunnel; a real remote match.
8. **Reporting** — the four JSON artefacts, Gatekeeper, Gmail.
9. **League** — negotiation, warm-ups, counting matches.
10. **Submission** — two repositories, academic README, screenshots, tag.

Cryptography deliberately precedes cloud exposure, inverting the specification's
recommended order. The rationale — crypto is offline-testable and carries the
heaviest sanctions, while the transport was already proven over localhost — is
recorded in [TASKS.md](TASKS.md) Phase 5. The specification's own reason for its
ordering is honoured; only the sequence differs.

## Risks and how the plan absorbs them

**Two peers must compute identically.** In a judge-free protocol, any divergence
in serialisation, physics or schema makes every audit fail. Mitigated by a single
canonical-JSON helper used everywhere, by exchanging config and scent-model
hashes before play, and by negotiating the sealed-record schema with each
opponent rather than assuming it.

**The specification contradicts itself in six places.** Mitigated by mechanical
source priority, by logging every contradiction in
[docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) rather than resolving it
silently, and by routing every choice into the final academic report — which the
specification explicitly permits, provided the choice is stated.

**One requirement cannot be resolved from the document.** The step-zero signing
key (Q-12) has no stated source. An interim SHA-256 commitment stands in; the
question is escalated to the lecturer before the first counting match rather
than closed by invention.

**Reporting is a live account with a hard quota.** Mitigated by building the
reporting shell last, behind three cumulative gates, with send-only scope.

## Out of scope

Reinforcement learning, paid LLM APIs, Docker, databases, cloud infrastructure,
web frameworks, and any abstraction without a second concrete use. Strategy
quality ranks sixth of seven in the project's priority ordering, below
compliance, working system, verification, simplicity and reliability; visual
polish ranks last.

---

## `capture_claim` (E-21/E-22) — architecture plan

**Status: design only (`feat/capture-claim`). No code written.** WHAT lives in
[prd.md](prd.md) §14; the design verification report is
[docs/CAPTURE_CLAIM_VERIFICATION.md](docs/CAPTURE_CLAIM_VERIFICATION.md);
the granular checklist is `todo.md`. This section states HOW the feature
should eventually be built, without writing any of it yet.

### The constraint driving every choice here

Five files are already over the lecturer's 150-line limit and are exactly the
files a naive implementation would grow: `peer/orchestrator.py` (1059),
`replay/verifier.py` (518), `protocol/messages.py` (423),
`crypto/coordinator.py` (419), and (post-Q-19-refactor) `peer/run.py` (406).
This feature must not make any of them worse. The Q-19 refactor
(`docs/DECISIONS.md` D-44) already established the working pattern for this
project — small sibling modules holding the new logic, with a minimal-footprint
hook (a few lines, often behind a local `TYPE_CHECKING`-guarded or
function-body import to dodge circularity) in the file that must dispatch to
it. Repeat that pattern here rather than inventing a new one.

### Proposed modules (none written yet; names are proposals, not commitments)

Labels below follow `prd.md` §14.0: **[A]** the module's *purpose* is
assignment-mandated; **[B]** its *shape/existence as a separate file* is our
design choice. All schema field names are **[B]** — see `prd.md` §14.8 for
the adopted schema (`claim_id`, `sub_game_number`, `turn_number`,
`claimant_role`/`responder_role`, `claim_kind`, `verdict`, `commitment`; no
coordinates, no nonce, no thief position anywhere in either payload —
`prd.md` §14.6/§14.7).

- **`protocol/capture_claim.py`** **[A purpose / B shape]** (new, target <
  100 lines) — the closed schema for `CAPTURE_CLAIM` (cop → thief,
  primary/mandatory direction) and `CAPTURE_CLAIM_RESPONSE` (thief → cop,
  `confirm`/`deny` only) as dataclasses with `to_dict`/`from_dict`,
  following the same closed-schema discipline as the rest of
  `protocol/messages.py`. Validation responsibilities living here, not
  scattered: reject wrong `sender_role`/`claimant_role`/`responder_role`
  combinations, reject a response to an unknown `claim_id`, treat a repeat
  of the same `claim_id` idempotently (return the already-logged response,
  not a second independent one), reject a `turn_number` that is stale or
  in the future relative to the state machine's current turn.
  `protocol/messages.py` itself gains only the two new `MessageType` enum
  members and their payload-key table row — a few lines, not new logic —
  everything else lives in the new module and is imported by
  `protocol/messages.py`, not inlined into it.
- **`crypto/capture_claim_seal.py`** **[B]** (new, target < 60 lines) —
  claim/response signing. Calls the *existing* `crypto/sealed.py`
  `commit()`/`verify()` primitives with the claim record's own field set;
  does **not** add a new cryptographic primitive and does **not** touch
  `crypto/coordinator.py` — the claim/response exchange is not a fifth
  Commit-Reveal phase, it is a signed record shaped like the others and
  audited the same way (`prd.md` §14.10, explicitly labelled a design
  decision there, not an assignment mandate).
- **`domain/capture_claim.py`** **[A purpose / B shape]** (new, target <
  80 lines) — calls the *existing, unmodified* `domain/capture.py`
  functions (`evaluate_full_turn_capture`, `evaluate_barrier_capture`,
  `evaluate_trapped_capture`) with the caller's own `LocalState` plus the
  opponent's already-revealed action to produce a `CaptureVerdict`. Two
  call sites, one mandatory and one optional (`prd.md` §14.8.1): **(1,
  mandatory, [A])** the thief calls this when a `CAPTURE_CLAIM` arrives, to
  make sure its `confirm`/`deny` response is truthful — this is how E-21 is
  actually satisfied, not a separate feature; **(2, optional, [B])** if the
  proactive self-signal extension is built, the thief also calls this
  unprompted each turn. Both call sites share the same function; only the
  *trigger* differs. No new capture-detection logic — this is wiring, per
  `prd.md` §14.9. `domain/capture.py` itself (124 lines) is left alone.
- **`peer/capture_claim_runtime.py`** **[A purpose / B shape]** (new,
  target < 110 lines) — primary, mandatory responsibility: **cop-side**
  claim issuance (`CAPTURE_CLAIM`, always a belief per E-9 — `prd.md`
  §14.3) and **thief-side** response handling (`CAPTURE_CLAIM_RESPONSE` via
  `domain/capture_claim.py` call site 1). Also owns the `CLAIM_PENDING_AUDIT`
  protocol-state transition on a confirmed claim (`prd.md` §14.13, a design
  decision, not an assignment citation). The optional thief-proactive-signal
  extension (§14.8.1 point 2, call site 2), if built, is a clearly separate
  function in this same module, not entangled with the mandatory path, so
  it can be omitted entirely without affecting compliance. `peer/orchestrator.py`
  gains only a dispatch-table entry for the two new `MessageType`s pointing
  at this module (mirrors how `peer/run.py` calls `gui_runtime.py`/
  `gui_main.py` today — D-44). `peer/run.py`'s `_play_turns` gains, at
  most, one conditional early-exit check reading the `CLAIM_PENDING_AUDIT`
  state — not new claim logic inline.
- **`audit/capture_claim_records.py`** **[A purpose / B shape]** (new,
  target < 60 lines) — the claim and response audit-record shapes,
  hash-chained like every other record via the existing
  `audit/writer.py`/`audit/chain.py` machinery (called, not modified).
  `audit/records.py` (already 160 lines) is not extended.
- **`replay/capture_claim_check.py`** **[A purpose / B shape]** (new,
  target < 100 lines) — reads a claim/response pair out of a sealed log, if
  present, and **checks it against, never adopts it in place of**, the
  independently recomputed `TerminalResult` (`prd.md` §14.11's
  live-vs-authoritative distinction; D-41's existing four-verdict model
  gains a fifth comparison outcome, not a fifth adjudicator — the exact
  verdict shape is a `docs/DECISIONS.md` entry to write at implementation
  time, per `todo.md`). `replay/verifier.py` gains a small call-out to this
  module at the point it already builds `TerminalResult`; the
  recomputation logic itself is unchanged and remains the sole source of
  truth.

### Tests (responsibility-grouped from the start, learning from Q-19)

One file per module above (`tests/protocol/test_capture_claim.py`,
`tests/crypto/test_capture_claim_seal.py`,
`tests/domain/test_capture_claim.py` — a new file, not a further extension of
`tests/domain/test_capture.py` which is already 192 lines —
`tests/peer/test_capture_claim_runtime.py`,
`tests/audit/test_capture_claim_records.py`,
`tests/replay/test_capture_claim_check.py`), plus one
`tests/peer/test_capture_claim_integration.py` for the two-peer, real-process
proof (mirrors `tests/peer/test_run_gui_playthrough.py`'s shape), and one
`tests/peer/test_capture_claim_optional_extension.py` kept **separate** from
`test_capture_claim_runtime.py` so the mandatory cop-initiated flow's tests
never depend on the optional thief-proactive-signal extension existing —
if that extension is skipped entirely, only this one file's tests are
skipped, not the compliance-critical ones. `todo.md`'s "capture_claim
implementation" checklist enumerates every individual test case (20+
categories, including the boundary/idempotency/role-rejection cases this
correction pass added). Each file kept under 150 lines by splitting further
the moment it would not be, exactly as `tests/gui/test_capture_trigger.py`
was split into a `_tk` and an `_ordering` sibling during the Q-19 pass.

### Sequencing (smallest reliable slice first)

1. `domain/capture_claim.py` + its tests — pure wiring over existing pure
   functions, no network, no crypto, fastest to verify.
2. `protocol/capture_claim.py` + its tests — schema only, no behaviour,
   including the role/duplicate/stale-turn rejection tests.
3. `crypto/capture_claim_seal.py` + its tests — signing over the new schema.
4. `audit/capture_claim_records.py` + its tests — logging the signed records.
5. **Before writing `peer/capture_claim_runtime.py`:** confirm or revise the
   `CLAIM_PENDING_AUDIT` design in `prd.md` §14.13 is still the intended
   mechanism (it is explicitly labelled a design decision, not settled
   fact) — this is a real decision point, not paperwork, since it
   determines `_play_turns`'s early-exit condition.
6. `peer/capture_claim_runtime.py` (mandatory cop-initiates/thief-responds
   path first, optional self-signal extension only after) + orchestrator/
   run.py dispatch hooks + its tests — the only step that touches the live
   turn loop.
7. `replay/capture_claim_check.py` + its tests — closes the loop back to
   D-41, including the "no existing D-41 behaviour regresses when no claim
   is present" regression test.
8. Two-peer real-process integration proof, full regression suite, Ruff,
   line-count sweep — the same four gates every prior phase in this project
   has closed on.

This mirrors `TASKS.md` Phase 5's existing (currently unchecked) capture_claim
item, made concrete enough to execute step by step; it does not replace that
item, it is its expansion.

### Explicitly not in this plan

A full repository-wide 150-line compliance pass (tracked separately, per the
Q-19 refactor's own final report); a multi-sub-game league runner (`prd.md`
§14.13 scopes capture_claim to a single sub-game/match); resolving Q-12 or
Q-18 (neither blocks this feature, `prd.md` §14.9.1); any change to
Commit-Reveal, Final Reveal, scoring, belief/scent, or the GUI; any field in
either payload capable of carrying a coordinate, a position, or a nonce
(`prd.md` §14.6/§14.7 — this is a hard boundary for the whole plan, not a
detail to revisit during implementation); treating the optional
thief-proactive-signal extension as equivalent to, or a substitute for, the
mandatory cop-initiated flow.
