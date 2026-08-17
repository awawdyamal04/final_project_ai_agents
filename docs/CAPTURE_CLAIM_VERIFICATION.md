# `capture_claim` (E-21/E-22) — design verification report

**Phase: Verify, per the Vibe-Coding lifecycle (Idea → PRD → Plan → TODO →
Verify → Execute → Push).** Produced before any implementation, on
`feat/capture-claim`. This is the answer set the user's Phase 6 explicitly
asked for; `prd.md` §14 is the WHAT this report verifies, `plan.md`'s
`capture_claim` section is the HOW, `todo.md`'s matching section is the
execution checklist. Nothing in this report has been implemented — it is a
readiness check.

All PDF citations below were independently re-extracted for this task from
`police_thief_p2p.pdf` (160 pages), reconstructed from pypdf's
visually-reversed RTL output by reversing each line and un-reversing
Latin/digit runs, per `CLAUDE.md` §1. Page numbers are the PDF's own absolute
page numbers (already matching this repository's existing citation
convention in `docs/REQUIREMENTS.md`), not book pages.

---

### 0. Master classification table

Every design point in this report and in `prd.md` §14 / `plan.md` is tagged
**[A] ASSIGNMENT-MANDATED**, **[B] OUR DESIGN DECISION**, or **[C] STILL
UNRESOLVED**. This table is the single place all three lists are gathered;
individual answers below cite it rather than re-deriving it.

**[A] Assignment-mandated — not a choice:**

1. E-21 (thief must answer truthfully when genuinely caught) and E-22 (cop
   must never falsely declare a capture) verbatim, PDF p. 145.
2. The cop is the party who **declares** — Ch. 3's scoring table: "the cop
   lands on the thief's cell and declares Capture Claim" (PDF p. 38). The
   cop-initiated flow is the primary, mandatory shape.
3. The thief is under a **cryptographic obligation to answer truthfully**
   once claimed (PDF p. 38–39).
4. Truth is established **not by live trust but by a signed, logged record
   checked at the final audit stage** (PDF p. 39) — the live-vs-authoritative
   distinction (§11 below) follows directly from this sentence.
5. The three underlying capture grounds (landed / E-46 barrier / E-47
   trapped) — already implemented in `domain/capture.py`, unrelated to and
   unaffected by this feature.
6. Nonces stay secret until the existing reveal/audit stage (E-18) —
   unchanged, no exception for capture_claim.
7. A false claim or false denial carries immediate disqualification / score
   zero / technical loss / no appeal (E-19, E-21, E-22).
8. The response must never carry the thief's position, nonce, unrevealed
   action, or other hidden state — a direct, non-negotiable consequence of
   E-8/E-9, not a design choice weighed against convenience.
9. A capture_claim ends the current sub-game (this repository's single
   `game_id` match), not a wider league series this repository has never
   implemented — moderate-to-high confidence from the config schema's
   `sub_game_number`/`num_games` fields (PDF pp. 94, 95, 129, 131).

**[B] Our design decisions — proposals, never presented as lecturer
requirements:**

1. The exact wire schema and field names (§4 below; `prd.md` §14.8).
2. Reusing the existing per-turn Commit-Reveal signature primitive for
   claim/response signing, rather than inventing a second cryptographic
   system (§7 below; `prd.md` §14.10).
3. The optional thief-proactive-self-signal extension — clearly secondary
   to, and never a substitute for, the mandatory cop-initiated flow
   (`prd.md` §14.8.1).
4. The `CLAIM_PENDING_AUDIT` runtime mechanism for halting further turns on
   a confirmed live claim, while denial allows play to continue (§9 below;
   `prd.md` §14.13).
5. Reading capture_claim as **augmenting** D-41 rather than replacing it
   (§"D-41 comparison" below) — a design inference from shared language,
   not a literal PDF citation.
6. Module boundaries and file layout (`plan.md`).

**[C] Still unresolved — not invented, requires agreement or lecturer
input:**

1. The precise mechanism by which a cop forms enough suspicion to issue a
   claim at all, given it structurally cannot verify its own landing cell
   (E-9) — the PDF describes the outcome, not the trigger heuristic.
2. Whether immediate-stop mechanics more precise than `CLAIM_PENDING_AUDIT`
   are specified somewhere this task did not find.
3. Whether a future multi-sub-game league layer will need its own claim
   semantics (out of current scope).
4. Whether Q-12's step-zero signing key will turn out to also be required
   for full league-level signature compliance beyond the step-zero
   declaration itself (§17 below).

---

### 1. What exactly do E-21 and E-22 require?

- **E-21** (PDF p. 145, Appendix E rule 21): *"חובה מכריזים אמת בלבד בעת
  תפיסת גנב"* — "Mandatory: declare truth only at the moment a thief is
  caught." Sanction: *"פסילה מיידית בגין הכחשת מציאות"* — immediate
  disqualification for denial of reality. Read together with the Ch. 3
  narrative (PDF p. 39: *"a capture declaration is therefore not a question
  of trust... any attempt to deny the true state will be discovered at the
  log-audit stage"*), E-21 is the **thief's** obligation: when genuinely
  caught, answer truthfully rather than deny it.
- **E-22** (PDF p. 145, Appendix E rule 22): *"איסור אין מכריזים כוזבות על
  תפיסה; הכרזת שקר"* — "Prohibition: never falsely declare a capture; a
  false declaration..." Sanction: *"ציון אפס... פסילה מיידית והפסד טכני
  ללא יכולת ערעור"* — score zero, immediate disqualification, technical
  loss, no right of appeal. This is the **cop's** obligation: never claim a
  capture that did not happen.
- Both are framed in Ch. 3 (PDF pp. 38–39, "Iron rules: movement and truth
  declaration") as two faces of one mechanism: the cop declares
  (`Capture Claim`), the thief is under a cryptographic obligation to
  answer truthfully, and truth is enforced not by trust but by a signed,
  logged response checked at the final audit.

### 2. What parts already exist?

- `domain/capture.py` — `evaluate_movement_capture`, `evaluate_barrier_capture`,
  `evaluate_trapped_capture`, `evaluate_full_turn_capture`: pure functions
  implementing the three mandatory capture grounds (landed-on-thief,
  E-46 barrier-on-thief, E-47 no-legal-move). Its own docstring already
  names "the real game, the capture-claim protocol (E-21, E-22)" as one of
  three intended call sites, alongside the Phase-1 harness and the replay
  verifier — i.e. this file was written anticipating the feature.
- `domain/enums.py::CaptureReason` and `domain/capture.py::CaptureVerdict` —
  already model exactly the three grounds needed.
- `sim/harness.py` and `replay/verifier.py` — both already call the
  `domain/capture.py` functions, as the offline (Phase 1 self-play) and
  post-match (replay) adjudicators respectively.
- `docs/PROTOCOL.md` §6.5 — a prior, explicitly "design-only" wire-format
  sketch (request: `claimed_cell`, `reason`; response: `confirmed`,
  `thief_cell`) written during an earlier documentation pass, never
  implemented. Reused as a starting point in `plan.md`, not treated as
  authoritative on its own.
- `docs/COMPLIANCE_AUDIT.md` Part 9 (2026-08-09) and `docs/DECISIONS.md`
  D-44's "separately confirmed" note — the prior finding that triggered
  this feature branch.

### 3. What exact parts are missing?

Confirmed by direct source search (`grep -ri "capture_claim\|CAPTURE_CLAIM"
src/`, this task): **no `MessageType.CAPTURE_CLAIM`** in
`protocol/messages.py`'s closed enum (currently `HEALTH_CHECK` … `CRYPTO_ERROR`,
no capture-related member); **no handler** in `peer/orchestrator.py` (which
has zero calls to any `domain/capture.py` function at all — confirmed by
grep); **no wiring** in `peer/run.py::_play_turns`; **no audit-record type**
for a claim/response pair; **no replay-side check** that cross-references a
logged claim against the independently recomputed `TerminalResult`. Every
piece of *evaluation* logic exists; every piece of *live wire-up* does not.

### 4. What new protocol messages are actually required?

**[A] shape, [B] fields.** Two messages, and their direction is
assignment-mandated (Correction 1 of this pass): `CAPTURE_CLAIM` (cop →
thief — the cop is the party the PDF describes as declaring) and
`CAPTURE_CLAIM_RESPONSE` (thief → cop — the party under the truthful-answer
obligation). This supersedes this report's earlier draft, which presented a
thief-initiated form as an equally weighted alternative; it is not —
thief-initiated signalling is, at most, an optional extension (`prd.md`
§14.8.1), never a substitute for the mandatory direction above.

The exact field names are **[B]**, not literally specified by the PDF,
which describes the obligation, not a schema:

```
CaptureClaim         (police -> thief)
  claim_id, sub_game_number, turn_number, claimant_role, claim_kind, commitment
CaptureClaimResponse (thief -> police)
  claim_id, sub_game_number, turn_number, responder_role, verdict, commitment
```

`claim_kind` carries the suspected ground (`landed`/`barrier_on_thief`/
`no_legal_move`); `verdict` is `confirm`/`deny` only. **No coordinate, no
cell, no nonce, in either message** — this report's earlier draft's
response sketch (`confirmed`, `thief_cell`) is corrected here; see Q5.

### 5. What data can be sent without violating the partial-information rule?

**[A], directly bounded by E-8/E-9.** The claimant's own true position and
action (always legitimately its own); the opponent's own already-revealed
action for the current turn (already public via the existing `reveal`
message); the claim's `claim_kind` in a cop-initiated claim (a public
accusation about an outcome, not a disclosure of hidden state); and, in the
response, **only** a `confirm`/`deny` verdict plus protocol bookkeeping
(`claim_id`, `sub_game_number`, `turn_number`, `responder_role`) and
cryptographic commitment/binding metadata already permitted elsewhere in
this protocol. **The thief's true cell is never sent, in the response or
anywhere else in this feature** — this corrects an error in this report's
earlier draft, which had proposed including `thief_cell` inside the signed
response record on the reasoning that a value inside a cryptographic record
is not a "display leak." That reasoning does not hold: the cop is the
direct recipient of the response message regardless of what a GUI displays,
so any field in it is disclosed to the cop the moment the message is
received, sealed or not. `capture_claim` is explicitly **not** a path for
revealing opponent location. Full detail in `prd.md` §14.6–§14.7.

### 6. At what point can nonces/actions legally be revealed?

**Unchanged by this feature.** E-18 (PDF p. 145) and the existing
`reveal`/`final_reveal` design (`docs/PROTOCOL.md` §§6.4/6.6, PDF pp. 51–52)
already fix this: an action is revealed at the ordinary per-turn `reveal`
step, but its nonce is withheld until `final_reveal`, at the end of the
match, when all nonces are disclosed together for mutual audit. A
capture-claim record is not a special exemption — its own nonce (if the
claim/response is sealed the same way as an ordinary turn, per §7 below)
follows the identical rule. The PDF gives no reason to believe capture_claim
should behave differently, and this task did not find one.

### 7. How is a claim cryptographically verified?

**[B] — the assignment requires truthfulness/verifiability, not a specific
schema.** E-21/E-22 and the Ch. 3 narrative require *that* a claim be
signed, logged, and checkable after the fact; the PDF names no particular
mechanism for achieving that. The PDF's own words — "every response is
signed and recorded in the log... any attempt to deny the true state will
be discovered at the log-audit stage" (PDF p. 39) — happen to describe
exactly the shape of the *existing* Commit-Reveal mechanism
(`crypto/sealed.py`'s `commit()`/`verify()` over
`SHA256(canonical_json_bytes(...))`, D-34/D-35), which is why the
recommended design (`plan.md`) reuses that mechanism rather than inventing
a fifth cryptographic step alongside Commit/Acknowledge/Reveal/
Final-Reveal — but this is a decision made on cost/risk grounds (an
existing, already-tested primitive vs. a new one), not because the PDF
mandates this specific primitive. A different but equally verifiable
mechanism would equally satisfy E-21/E-22 as written.

### 8. What should happen on a valid claim?

**[A]** The claim is logged, the thief's truthful confirmation is logged.
**[B]** The runtime response is entry into a `CLAIM_PENDING_AUDIT`
protocol state: no further game turns are issued, but `final_reveal` and
mutual audit still run to completion — they are not skipped, because they
remain the actual proof mechanism (§11). The eventual `TerminalResult`
(`reason=CAPTURE`, scored per `config.scoring.capture_cop`/`capture_thief`
— `domain/terminal.py::capture()` already exists and needs no change) is
still established by the audit/replay process, not asserted directly from
the live confirmation. **[C]** Whether "valid claim confirmed" must
immediately stop further live turns is this design's own conservative
reading, not a PDF citation — the PDF defines *what counts as a capture*
but not the exact runtime stop mechanism. See Q10 and Q15 below, and
`prd.md` §14.13.

### 9. What should happen on an invalid claim?

**[A]** A false cop claim → immediate disqualification, score 0, technical
loss, no appeal — exactly the existing `technical_loss()` outcome
(`domain/terminal.py`), attributed to the cop. Symmetrically (E-21), a
false thief denial → immediate disqualification for "denial of reality."
Both are, in the PDF's own words, things "discovered at the log-audit
stage" — i.e. detection is established by the audit process, live response
notwithstanding.

**[A] Critical distinction (Correction 4 of this pass — this report's
earlier draft did not make this explicit enough):** the **live** response
(`confirm`/`deny`) and the **later authoritative verification** are not the
same event and must never be conflated. Neither the cop's claim nor the
thief's response is trusted merely because it was sent. Concretely, final
audit/replay must be able to distinguish all four of: the cop's claim was
truthful; the cop's claim was false; the thief's confirmation was truthful;
the thief's denial was false — as four independently checkable outcomes,
not inferred from whether a live response merely arrived. A thief that
"confirms" but whose own logged state (once revealed) contradicts that
confirmation must still be caught by replay — the live confirmation does
not pre-empt that check. See `prd.md` §14.11.

### 10. Does capture_claim end only the sub-game or the whole match?

**Bucket A (PDF-supported, moderate-to-high confidence):** the **sub-game**
(what this repository already calls one `game_id` run — `domain/terminal.py`'s
own docstring: "the structured result of a finished **sub-game**"). Evidence:
the private per-peer config (`docs/PROTOCOL.md`-adjacent, PDF p. 131)
carries a `sub_game_number` field; the mandatory pre-match declaration file
covers "the whole game (including the sub-games)" (PDF p. 94); the results
file is described as "a summary of all sub-games: each team's score in each
mini-game and the cumulative result" (PDF p. 95); and the shared config
example (PDF p. 129) has a top-level `num_games` field distinct from any
single game's own parameters. This repository has never implemented a
multi-sub-game league runner — `num_games`/`sub_game_number` exist in the
schema but no code iterates them — so in the **current** scope, "the whole
match this repository plays" and "one sub-game" are the same thing. A future
league-runner layer, if built, is out of scope for this feature (`plan.md`
"Explicitly not in this plan").

### 11. How should audit logs represent the claim?

**Bucket B:** a first-class, hash-chained record pair (claim, response),
parallel in shape to the existing `commit`/`reveal`/`final_reveal` records,
written through the existing `audit/writer.py`/`audit/chain.py` machinery —
not a new logging mechanism, not a side channel, and not embedded inside an
existing record type (`plan.md`'s `audit/capture_claim_records.py`).

### 12. How should replay verify the claim?

**Bucket B, constrained by D-41 (bucket A given D-41 already exists):**
replay must **check, not adopt** — read a logged claim/response pair if
present, independently recompute the `TerminalResult` exactly as it does
today (unchanged), and flag agreement or disagreement as an extension of
D-41's four-verdict model (`VERIFIED OK` / `TAMPERED` / `INCOMPLETE` /
`POLICY MISMATCH`). Whether disagreement becomes a fifth verdict or an
annotation on an existing one is left to implementation-time design
(`todo.md` "Terminal state" / "Replay" sections) and must be recorded in
`docs/DECISIONS.md` when decided, not assumed here.

### 13. What existing code paths would be affected?

`protocol/messages.py` (two enum members + one payload-table row — minimal),
`peer/orchestrator.py` (a dispatch-table entry, not new logic inline),
`peer/run.py::_play_turns` (at most one conditional early-exit implementing
`CLAIM_PENDING_AUDIT`, deferred until that design — §8 above, `prd.md`
§14.13 — is confirmed), `replay/verifier.py` (one
call-out at the point `TerminalResult` is already built). `domain/capture.py`,
`crypto/sealed.py`, `crypto/coordinator.py`, `audit/writer.py`,
`audit/chain.py`, the belief/scent/strategy layer, the GUI, and the network
transport layer (Q-20's fix) are **not** expected to change at all. Full
module-by-module breakdown in `plan.md`.

### 14. Which decisions are explicitly specified by the lecturer?

The two rule texts (E-21, E-22) and their sanctions; the Ch. 3 scoring-table
trigger ("cop lands on the thief's cell and declares Capture Claim"); the
three underlying capture grounds (landed / E-46 barrier / E-47 trapped,
already implemented and unaffected by this feature); the thief's
cryptographic truth obligation; that enforcement is via a signed, logged
response checked at audit rather than live trust; that nonces stay hidden
until final reveal (E-18, unchanged); that a false claim or denial carries
immediate disqualification with no appeal.

### 15. Which decisions are still ambiguous?

Listed in full in §0's `[C]` list and `prd.md` §14.17. The two load-bearing
ones: (a) **the trigger mechanism** — the PDF describes the *outcome* ("the
cop declares") but never explains how a cop, structurally unable to see the
thief's position (E-9), forms enough basis to declare a landed-on-thief
claim at all; this task's own architecture finding (§9 above) is that the
thief, not the cop, is the party who can actually self-verify live — a
finding that informs the *optional* extension in `prd.md` §14.8.1, and does
not change who the *mandatory* initiator is (Correction 1 of this pass:
that is the cop, definitively, per §4/§8 above). (b) **halt timing beyond
`CLAIM_PENDING_AUDIT`** — that runtime mechanism (§8 above) is this
design's own conservative proposal, not a PDF citation; a more precise
mechanism, if one exists in material this task did not find, would
supersede it. Neither is invented here; both are recorded as open in
`prd.md` and `todo.md`.

### 16. Does Q-18 interact with capture_claim?

**Yes, but only as a consumer, not a new conflict.** Q-18
(`docs/OPEN_QUESTIONS.md`) governs how one turn's simultaneous
movement/barrier collision is resolved (`SimultaneityPolicy`); it is
explicitly scoped (per the paragraph already added to Q-18 during the Q-19
documentation phase) to *not* touch the separately mandatory E-47. Because
`evaluate_full_turn_capture(movement, thief_state, config, policy)` already
takes the policy as a parameter, any capture_claim implementation that calls
this existing function inherits whatever Q-18 resolution is configured
automatically — capture_claim does not need its own Q-18 answer, it only
needs to keep calling the same function with the same policy argument
(`plan.md`'s `domain/capture_claim.py` design). No new ambiguity is
introduced.

### 17. Does Q-12 affect capture_claim?

**Not proven irrelevant — scoped and reasoned through, not dismissed.**
Q-12 (`docs/OPEN_QUESTIONS.md`) is scoped to the step-zero hardware
declaration's signing key specifically — a single signature over the
pre-match hardware/commit-identifier declaration (PDF p. 56), a different
signing context from the per-turn or per-claim Commit-Reveal signatures
this design reuses (§7 above). **[B]** Because `capture_claim`
authentication is proposed to reuse the *existing, already-established*
per-turn commitment/identity primitives, and those primitives have never
depended on the step-zero key, **implementation of `capture_claim` itself
can proceed independently of Q-12's resolution** — that much follows from
this design's own crypto choice, not from a claim that Q-12 is universally
irrelevant. **[C]** If a future audit, an opponent team, or the lecturer
determines that the step-zero key is *also* required for full/final
league-level compliance of every signed artefact in a match (not only the
step-zero declaration itself), that would reopen a dependency this design
does not currently assume, and Q-12's escalation in `docs/OPEN_QUESTIONS.md`
would then bear on `capture_claim` too. Q-12 remains escalated and
unresolved; this feature does not close it and must not be read as having
done so.

### 18. What is the safest implementation sequence?

Per `plan.md`'s "Sequencing" section: pure domain wiring first (no network,
no crypto — fastest to verify and cheapest to revert), then schema, then
signing, then audit logging, then — only after the `CLAIM_PENDING_AUDIT`
design (§8 above) is confirmed as the intended mechanism, a real decision
point, not paperwork — the live orchestrator/run.py hook (the only step
touching the live turn loop), then replay's check, then the two-peer
real-process proof and full regression sweep. This mirrors the order every
prior mandatory phase in `TASKS.md` was built in: offline-testable,
lower-risk pieces before anything touching the live network turn loop.

### 19. How will we ensure no new >150-line Python files are introduced?

Every proposed module in `plan.md` carries an explicit target line count,
all comfortably under 150 (the largest proposed, `peer/capture_claim_runtime.py`
and `replay/capture_claim_check.py`, target under 100). The same discipline
that closed the Q-19 refactor applies: `wc -l` after every file is written,
a full `find src tests -name "*.py" -exec wc -l {} + | sort -nr | awk
'$1 > 150'` sweep before considering any implementation step complete, and
— learned directly from the Q-19 pass, where two test files crept back over
150 after later edits — a **final** re-sweep immediately before the
end-of-feature report, not only a sweep after the first draft of each file.
`todo.md`'s "Python line-count verification" section makes this an explicit,
separately-checked task rather than an assumption.

### 20. What tests will prove E-21/E-22 compliance?

`todo.md`'s "Explicit test coverage checklist" enumerates every category
required by this pass (cop-initiates; thief-cannot-mandatorily-self-initiate;
truthful confirm/deny; false-claim/false-denial-caught-at-audit; no
position/nonce leak; duplicate-claim idempotency; stale/future-turn
rejection; malformed/wrong-role rejection; serialization round trip;
`CLAIM_PENDING_AUDIT` stop behaviour; `final_reveal`/mutual-audit still
running; replay-agrees and replay-detects-disagreement; Q-18-policy
respected; D-41 no-regression; real two-peer run — 20+ items, none marked
complete), converging on `docs/ACCEPTANCE_TESTS.md`'s existing (currently
unimplemented, "remains a specification for a later phase")
`test_e21_...`/`test_e22_...` placeholders. The two load-bearing ones for
E-21/E-22 specifically: a false-cop-claim test proving immediate
disqualification/score-0/technical-loss (E-22), and a false-thief-denial
test proving immediate disqualification (E-21) — both established at final
audit per §9 above, never inferred from a live response alone.

---

### D-41 comparison — replace, augment, or coexist?

**Based only on the assignment evidence gathered in this pass: augment/coexist,
not replace.**

D-41's own reasoning (`docs/DECISIONS.md`) is that *"a live peer cannot
adjudicate — it never sees its opponent's position — so it plays to the turn
limit and the replay decides where the game actually ended."* Nothing in the
PDF's capture_claim narrative (Ch. 3, PDF pp. 38–39) contradicts this: the
same passage that describes the cop's declaration also says truth is
established "not by trust... but by proof verifiable **after the fact**" and
that a lie "will be discovered **at the log-audit stage**." That is D-41's
own mechanism, described in the PDF in the specific context of capture. The
most literal reading of the PDF's own words is therefore that capture_claim
**augments** D-41 and does not replace it. Concretely, stated as the two
branches D-41's own text already distinguishes:

- **With a confirmed live claim:** live peers may stop issuing further
  turns early (`CLAIM_PENDING_AUDIT`, §8 above) and proceed toward final
  reveal and mutual audit sooner than the configured ceiling — a claim
  gives a match a chance to *know and log* its outcome earlier.
- **Without a claim, or with a denied one:** D-41's existing behaviour is
  completely unchanged and remains fully available — live peers may play
  to the configured turn ceiling exactly as they do today, and offline
  replay determines the first true terminal state with no dependency on
  this feature existing at all.
- **In both branches, replay remains authoritative.** The offline,
  both-logs replay is what actually establishes what happened — a
  confirmed live claim never substitutes for it (§9 above). Nothing in the
  PDF states that a live claim should be trusted over what replay would
  independently reconstruct, and the PDF's own "verifiable after the fact"
  phrasing argues against treating a live claim as self-authenticating.

This reading is recorded as **[B]** in `prd.md` §14.12 (a design decision
informed by, not dictated by, the PDF) because the PDF never explicitly
states the word "replay" in the same sentence as "capture claim" — the
connection is this task's inference from the shared "verified after the
fact, at the audit stage" language, not a literal cross-reference in the
source document. It is nonetheless the adopted design position for
`plan.md`'s sequencing (not one of several options still being weighed),
and would only be revisited if a future, more literal reading surfaces.
