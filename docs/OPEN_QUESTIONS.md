# OPEN QUESTIONS — contradictions and ambiguities in the specification

PDF p. 5 grants **academic freedom on contradiction**: where the book
contradicts itself, we may choose one reading and proceed, *provided the choice
is stated explicitly in the report* — where the contradiction was identified,
what was chosen, and why. A reasoned, documented choice is not held against the
team.

This file is that record. Everything here must reach the final `README.md`
academic report.

Two things this freedom does **not** cover:

- **Appendix F remains the single binding source for numeric values** even in
  the presence of contradiction (PDF p. 5).
- Where two readings materially change compliance, the question is escalated
  rather than silently resolved.

Status key: **RESOLVED** (settled by source priority; recorded in
[DECISIONS.md](DECISIONS.md)) · **CONTRADICTORY** (the PDF says two incompatible
things) · **NEGOTIATE** (must be agreed with the opponent team before a match) ·
**ESCALATE** (needs the lecturer, or a decision the user must make).

> **Second-pass audit (2026-07-28).** Re-verified against the PDF pages
> themselves rather than a text extraction. Three entries moved: **Q-1** and
> **Q-4** are resolved by the PDF's own narrative rather than only by our source
> priority; **Q-7** is resolved on two independent grounds and no longer needs
> escalation. **Q-12 remains the sole item requiring outside input.** Details in
> each entry and in [COMPLIANCE_AUDIT.md](COMPLIANCE_AUDIT.md) Part 1.

---

## Q-1 — `num_games`: Appendix F says 6 FIXED, the example config ships 1

**Status: CONTRADICTORY — but resolved by the PDF itself.**
→ see [DECISIONS.md](DECISIONS.md) D-2.

**Second-pass finding: the PDF resolves the usage question in its own words.**
PDF p. 130 (verified against the rendered page) states that 1 is *"a single
demonstration sub-game"* and that *"the full league series requires
`[num_sub_games]` sub-games"*. So the document tells us plainly what to run in a
league match: 6. The residual inconsistency is only in the *status label* — a
value cannot literally be FIXED at 6 while the shipped example carries 1 — but
that inconsistency has no operational consequence once the narrative is read.

Downgraded from "unresolved contradiction" to "contradictory labelling, resolved
usage". The competing interpretations were: (a) 6 always, since FIXED admits no
variation; (b) 1 is a legitimate configurable default. Reading (b) is excluded
for league play by the p. 130 sentence itself.

- Appendix F table 18 row 1 (PDF p. 154): `[num_sub_games]` = **6**, status
  **FIXED** ("deviation disqualifies the team").
- Appendix B example `config/game.json` (PDF p. 129): `"num_games": 1`.
- Appendix B narrative (PDF p. 130): *"the `num_games` field is sent by default
  with the value 1 (a single example sub-game); the full league series requires
  `[num_sub_games]` sub-games."*

A parameter cannot simultaneously be FIXED at 6 and default to 1. The narrative
suggests the intent is that 1 is a demo convenience and 6 is the league value,
but Appendix F's FIXED status admits no such split.

**Resolution:** Source priority rule 1 — Appendix F overrides every numerical
example elsewhere. **We ship 6.** A local demo may override it, but no config
used in a counting league match may carry anything but 6.

**Residual risk:** if an opponent team ships the Appendix B example verbatim,
the config-hash exchange will fail and neither side will be able to play until
the discrepancy is discussed. Raise it in negotiation proactively.

---

## Q-2 — Turn order is never specified

**Status: NEGOTIATE.**

The PDF never states whether the cop or the thief moves first. What it fixes
(Ch. 4, PDF p. 43) is that decay is applied *at the end of each full turn — after
both the cop and the thief have completed their move*, so turns are paired.
Chapter 8's state machine is symmetric and role-agnostic.

**Our design** ([PROTOCOL.md](PROTOCOL.md) §5): simultaneous moves under
commit-reveal — both peers commit before either reveals — which dissolves the
question rather than answering it, and is what the commit-reveal machinery is
for. Must be confirmed with the opponent, since a peer expecting strict
alternation will deadlock against a peer expecting simultaneity.

---

## Q-3 — `technical_loss` has no row in Appendix F

**Status: RESOLVED** → see [DECISIONS.md](DECISIONS.md) D-3.

`scoring.technical_loss: 0` appears in the Appendix B example config
(PDF p. 129); the value 0/0 appears in Chapter 3's scoring table (PDF p. 38) and
in rule E-48 (PDF p. 149, "technical loss 0/0"). But Appendix F table 17
(PDF p. 154) tabulates only five scoring parameters and **does not include
`technical_loss`**.

So the single binding source for numeric values does not bind this one.

**Resolution:** carry `technical_loss: 0` in the shared config, sourced from
Ch. 3 table 2 and E-48, and flag in the report that it is not an Appendix F
parameter and therefore has no MINIMUM/FIXED/NEGOTIABLE status. Treated as
NEGOTIABLE-with-default-0 in the validator. Low risk: both sources agree on 0,
and 0 for both sides is the whole point of the rule.

---

## Q-4 — What exactly goes into the commit hash

**Status: RESOLVED** → see [DECISIONS.md](DECISIONS.md) D-4. **Also NEGOTIATE.**

Three different accounts appear in the PDF:

1. Ch. 5 formula (PDF p. 50): `H = SHA256(State ‖ Move ‖ Intent ‖ Nonce)` — four
   fields.
2. Ch. 5 narrative, same page and PDF p. 51: concatenation is done by canonical
   JSON serialisation with sorted keys and fixed separators, and *"the record
   actually sealed is richer than the four fields here, and also includes the
   verbal hint, the intent classification, the step number and the role"* — the
   sample code comment adds `sub_game`.
3. Ch. 7 replay sketch (PDF p. 74): `SHA256(f"{nonce}|{move}")` — two fields —
   annotated by the PDF itself as *"the sketch simplifies the input for
   illustration; in practice the signature covers the full step components"*.

Account 3 is self-declared illustrative. Accounts 1 and 2 differ, with 2 being
the explicit description of practice.

**Second-pass finding: the PDF resolves the field *set*, not the field *names*.**
Account 2 is not a vague hint — it is an explicit statement of what the
implementation seals, and account 3 is explicitly self-labelled as simplified.
So the document does tell us the record contains: state, move, intent, nonce,
hint, intent classification, step number, role (and `sub_game` per the sample
code comment). What the PDF never fixes is the exact JSON **key spelling and
nesting**, which canonical serialisation makes load-bearing — `"sub_game"` and
`"subGame"` hash differently.

**Resolution:** implement the richer record with canonical JSON serialisation
(the schema in [PROTOCOL.md](PROTOCOL.md) §6.1). This satisfies E-17 (SHA-256
commit-reveal) and E-18 regardless of field set, and honours the explicit
"byte-identical input" requirement.

**Still must be negotiated:** both peers must hash the *same* key spelling or
every audit fails and both sides take a technical loss for a formatting
disagreement. The sealed-record schema is therefore part of the pre-match
agreement and its hash is exchanged at handshake. Reclassified from AMBIGUOUS to
**resolved in substance, negotiate the encoding**.

---

## Q-5 — Three different timeout values, unclear which governs a turn

**Status: NEGOTIATE.**

| Value | Source | Scope stated |
|---|---|---|
| `response_timeout_sec = 30` | Appendix F table 19 row 6 (PDF p. 155), NEGOTIABLE | "timeout for each network request" |
| `watchdog_timeout_sec = 60` | Appendix F table 19 row 7 (PDF p. 155), NEGOTIABLE | "freeze time until Watchdog intervention" |
| `turn_timeout_seconds = 180` | Private TOML skeleton (PDF p. 131) | not stated |
| `timeout_sec = 180` | Ch. 8 watchdog sample code (PDF p. 83) | sample default |

The Appendix F pair is coherent (a request deadline shorter than the process
freeze threshold). The 180s values sit in a private file and in sample code, and
their relationship to the Appendix F pair is never explained. A private value
also cannot weaken a signed condition (PDF p. 132).

**Our reading:** `response_timeout_sec` governs each MCP request;
`watchdog_timeout_sec` governs the process-freeze detector;
`turn_timeout_seconds` is a private, softer budget for the peer's own
end-to-end turn processing (including LLM thinking, itself capped by
`step_deadline_seconds = 30`). Only the first two are on the wire and agreed.
Confirm with the opponent that neither side expects a 180s response deadline.

---

## Q-6 — Grid size: 7×7 or 10×10?

**Status: RESOLVED**, non-issue, recorded to prevent re-litigation.

`[grid_size]` = 7, status **MINIMUM** (Appendix F table 13, PDF p. 152).
Chapter 3 (PDF pp. 34–35) uses 7×7 as the default throughout and contrasts it
with earlier 5×5 versions. But the book's abstract (PDF p. 1) says 10×10, and
Chapter 6's belief-map text and figure 8 (PDF pp. 63–64) show a 10×10 grid
labelled `[grid_size]`.

Not a contradiction in binding terms: MINIMUM 7 means 7 is the floor and 10 is a
legal agreed value. The figures are `EXAMPLE`. **We default to 7** and read the
value from config.

---

## Q-7 — Gmail `mode = "draft"` versus the obligation to send

**Status: RESOLVED** → see [DECISIONS.md](DECISIONS.md) D-5. **Also ESCALATE
(low priority).**

The private TOML skeleton (PDF p. 131) has `[email] mode = "draft"`, and
Appendix D says the reference repo sends *"a JSON report sent as a Gmail
draft"* (PDF p. 139). But E-32 requires reporting results **automatically via
the Gmail interface**, E-51 requires sending the reports **to** the lecturer
address, and Ch. 9 (PDF p. 94) states each team must itself **send** the report,
with non-receipt costing that side its points.

A draft is not received by the lecturer.

**Resolution:** `mode` defaults to `send` for any counting league match. `draft`
is retained as a development/testing convenience only, and the reporting module
refuses to run in `draft` mode when the match is flagged as counting.

**Second-pass finding — the PDF resolves this, on two independent grounds.**

1. **Appendix D p. 141 states the precedence rule explicitly:** *"the repository
   licence is an educational-use licence… **wherever the repository deviates
   from the book, the book and the mandatory parameter table prevail**."* The
   draft-sending behaviour is a property of the reference repository
   (described at PDF p. 139), so it is subordinate by the PDF's own rule.
2. **The TOML skeleton is labelled an example.** PDF p. 130 introduces it as
   *"an abbreviated skeleton"* (שלד מקוצר), and PDF p. 4 makes examples
   non-binding. A mandatory rule (E-32, E-51) outranks an example value.

Reclassified from AMBIGUOUS to **CONTRADICTORY — resolved by the PDF**. The
escalation is no longer needed; the document answers it.

---

## Q-8 — "MINIMUM" semantics for rate-limiter parameters

**Status: NEGOTIATE / ESCALATE (low priority).**

Appendix F p. 155 defines MINIMUM as: negotiable *only in the direction that
makes the game harder (usually increasing the value)*, never an easement below
the tabulated value.

For most parameters that is unambiguous — a larger grid or more required
survival steps is harder. For table 19 rows 1–5 the mapping inverts:
`requests_per_minute = 30` MINIMUM would mean 30 is the *floor*, so raising it
to 60 is "allowed" — but a higher permitted request rate is a **looser** safety
limit, not a harder one, and the whole purpose of E-28/E-29 is to avoid a 429
account block.

**Our reading:** treat 30/2/5/3/100 as the **configured defaults**, and treat
the *protective* direction as the safe one: never send faster than
`requests_per_minute`, never fewer than `retry_backoff_sec` seconds between
retries, never fewer than `max_retries` attempts, never a queue shallower than
`queue_depth`. In practice these are per-peer protective settings that the
opponent does not rely on, so negotiation pressure here is minimal.

---

## Q-9 — Capture resolution under simultaneous movement

**Status: NEGOTIATE.**

Given simultaneous moves (Q-2), edge cases the PDF does not address:

- The cop moves onto the cell the thief just vacated — capture, or miss?
- The cop and thief swap cells (pass through each other) — capture, or miss?
- Both conditions for capture and for reaching `survival_threshold` complete on
  the same turn — which wins?

Chapter 3 defines capture as *"the cop lands on the thief's cell"* (PDF p. 38),
which reads naturally as *post-move positions coincide*.

**Our reading:** evaluate capture on **post-move positions only**. A swap is not
a capture; landing on a vacated cell is not a capture. If capture and survival
threshold coincide, capture takes precedence (the cop's claim is evaluated
before the step counter reaches the threshold). Must be agreed explicitly, since
it materially changes outcomes.

---

## Q-10 — Axis orientation: text says down, figure shows up

**Status: RESOLVED**, low severity.

Chapter 3 (PDF p. 34) states the default origin is the top-left corner *"(the
vertical axis grows downward)"*. Figure 3 (PDF p. 36) draws the 7×7 arena with
row 0 at the **bottom** and row 6 at the top. Additionally, Chapter 6's
Manhattan worked example (PDF p. 64) places the cop at (2,2), and calls (3,2)
"north" — which with a downward-growing vertical axis would be *south*.

**Resolution:** diagrams and worked examples are `EXAMPLE` and non-binding
(PDF p. 4). Follow the Chapter 3 **text**: origin top-left, vertical axis grows
downward, cells addressed `(row, col)`. `N` decreases row. Since
`axis_origin_corner` and `axis_start_index` are NEGOTIABLE but must be
**identical** on both sides, this is settled explicitly in the shared config, so
the ambiguity has no runtime consequence once agreed.

Note also that Ch. 3 uses `(row, col)` while the belief-map figure (PDF p. 64)
labels axes `x (column)` and `y (row)`. We use `(row, col)` throughout, per the
Chapter 3 text.

---

## Q-11 — Is a Live GUI mandatory in its own right?

**Status: RESOLVED**, treated as mandatory.

Appendix E has no rule "you must build a live GUI". E-8 and E-9 constrain *what
the live interface may display*, presupposing one exists. E-20 makes only the
**replay viewer** explicitly mandatory.

However: Chapter 9's mandatory README contents (PDF p. 97) list screenshots from
the Live GUI as *"an absolute obligation"*; Appendix C's submission checklist
(PDF p. 136) requires "screenshots of the belief map (GUI)" as *attached*; and
Chapter 11's final checklist (PDF p. 113) requires the Live GUI and Replay App
to display the game in real time and in replay.

**Resolution:** a Live GUI is mandatory in effect, via the submission
requirements. Build it. Its scope is nonetheless minimal: belief heatmap + turn
banner is exactly what the PDF describes.

---

## Q-12 — Step-0 signing key

**Status: ESCALATE.**

Ch. 5 (PDF p. 56) says the step-zero specification *"is packed into a JSON
string and cryptographically signed using **a pre-supplied key**, so it cannot be
forged after the fact."*

The PDF never says who supplies this key, where it comes from, what algorithm it
uses, or how the counterpart verifies it. No Appendix F parameter and no
Appendix A instruction covers it.

**Cannot be resolved from the document.** Options: (a) the lecturer distributes
a key out of band; (b) each team generates a keypair and exchanges public keys
at handshake; (c) "signed" loosely means SHA-256 hashed and committed, in line
with the rest of the project's mechanisms.

**Interim position:** implement (c) — canonical JSON + SHA-256, exchanged and
locked at handshake — since it satisfies "cannot be forged after the fact"
against the log, uses machinery the project already mandates, and requires no
external secret. **Do not fabricate a key or key-distribution scheme.** Ask the
lecturer before the first counting match; if a key is in fact supplied, swapping
the hash for a signature is a contained change behind the crypto module's
interface.

---

## Q-13 — Does the lecturer's address need the config file per match, by email or by repo?

**Status: RESOLVED**, both.

Appendix F §2 (PDF p. 156) requires: each match's config file **attached to the
GitHub repository**, and for each match **an email to the lecturer containing
the commit number** used. Ch. 9 requires the four JSON artefacts, of which
`[config_file]` is one, and `[result_file]` is the one emailed.

**Resolution:** commit all four artefacts per match under `matches/<game_id>/`,
and email `[result_file]` (which carries the commit hash per sub-game, E-53) to
`[agent_reporting_address]`. This satisfies both obligations without inventing a
separate email.

---

## Q-20 — Two-process transport stall

**Status: RESOLVED.** Root cause proven, fixed, and demonstrated by a complete
35-turn two-process HTTP match. → see [DECISIONS.md](DECISIONS.md) D-42 and
[../results/q20_transport_proof.md](../results/q20_transport_proof.md).

Not a FastMCP fault and not a specification question — a defect of ours.

### The proven cause: stdout PIPE backpressure

The runtime built its operational event sink as `JsonEventSink(echo=True)`, so
every event was also written to stdout with a synchronous
`print(..., flush=True)`; uvicorn added one INFO line per HTTP request on the
same stream. Both subprocess launchers captured stdout with
`stdout=subprocess.PIPE` and did **not** drain it while the game ran.

An OS pipe buffer is finite. Once it filled, the next `print` blocked — and it
blocked *inside the asyncio event loop*, because the sink is called from the
turn coroutines. The process therefore stayed alive and never crashed, but its
FastMCP server could no longer accept or answer connections while the loop was
parked in a blocking write. From the opposite peer this looks exactly like the
symptom recorded below: a live opponent whose server has stopped listening. The
diagnostic measured roughly 40 seconds of event-loop lag at the moment of the
freeze.

This explains every observation at once — why it was independent of client
design, why it always landed near the same turn (the same volume of output fills
the same buffer), and why the identical turn sequence ran to 35 turns in-process
(no pipe involved).

### The fix

- `JsonEventSink` echo is now **false by default** in `peer/run.py`; the JSONL
  operational log and the cryptographic audit chain are unchanged and still
  written in full.
- A new `--verbose` CLI flag re-enables live stdout echo explicitly, for
  watching a run by hand.
- `PeerServer` defaults uvicorn to `log_level="warning"`, removing the
  per-request INFO flood while keeping warnings and errors.
- `stateless_http=True` and `json_response=True` are kept as transport
  simplifications. They were introduced while the session-accumulation
  hypothesis was live; they are safe and reduce moving parts, but they are
  **not** what fixed this.

### Verification

- Two real peer processes, real loopback HTTP FastMCP, `game_id`
  `real-game-001`: **35 turns completed**, both processes exited 0, no
  `PeerTimeoutError`, no `send_unacknowledged`, and no in-play
  connection-refused channel restart (`transport_diagnostics`: primary channel
  71 calls / 0 failures / 0 restarts, control channel 4 calls / 0 failures /
  0 restarts).
- Final reveal verified all 35 turns; mutual audit verified both directions;
  both audit chains report `Verified OK (179 records)`.
- Independent offline replay over both logs: **`VERIFIED OK`** — survival on
  turn 35, winner thief, cop 5 / thief 10.
- Regression tests: `tests/peer/test_http_stress.py` (repeated real HTTP
  session reopens against a live server) and
  `tests/peer/test_stdout_backpressure.py` (two real peer subprocesses played
  through deliberately **undrained** stdout pipes).
- Full suite: **1467 passed, 3 skipped, 0 failed.**

### Historical debugging record (kept deliberately)

The two earlier fixes below were real and are retained. The next-turn pending
buffer (one turn of tolerance) works and is unchanged. So is the anyio fix: a
FastMCP `Client` is built on cancel scopes that must be entered and exited by
the *same task*, and the old code opened a session in the startup task and tore
it down from a turn task. anyio raised `RuntimeError` and — the damaging part —
every subsequent reopen raised too, so one blip killed a channel permanently.
Each session now lives inside its own worker task and is never touched from
outside it. Neither fix, however, was the cause of the stall.

Five client topologies were measured before the cause was found. All failed,
and the last three failed at the *same turn*:

| Topology | Fails at |
|---|---|
| Fresh `Client` per message | turn 1 |
| Shared session, unguarded | turn 3-5 |
| Shared session + lock | turn 5-8 |
| Two channels, shared-object sessions | turn 6 |
| Two channels, worker-task sessions | turn 6, repeatably |

The captured error was
`RuntimeError: Client failed to connect: All connection attempts failed`.

Hypotheses that were **ruled out** by measurement: turn ordering (the buffer
works, visible in the logs); client concurrency (five topologies, same wall);
cancellation damage to a session (reproduced in isolation, recovers cleanly);
the protocol, crypto and strategy layers (the identical turn sequence reached 35
turns in-process).

The hypothesis that was **wrong**: server-side session accumulation in FastMCP's
streamable-HTTP transport — half-open `GET /mcp` streams filling a session table
or connection limit. It fitted the symptom and motivated the move to
`stateless_http=True`, but the stall survived that change. The cause was on the
*writing* side of the process, not the listening side.

**Effect on Q-19.** Q-19 was previously recorded as the same underlying fault.
That link is now unproven: the mechanism identified here is not GUI-specific, so
whether it also explains the `--gui` instability has **not** been demonstrated.
Q-19 remains open and untested against this fix.

---

## Q-19 — Long `--gui` runs destabilise the FastMCP server

**Status: KNOWN LIMITATION (ours, not the specification's).** *Found in Phase 6.*

Under `--gui`, Tk must own the main thread, so the peer's asyncio loop runs in a
worker. Past roughly six commit-reveal turns the FastMCP HTTP server then stops
answering and a turn fails on "opponent commitment never arrived". Headless runs
are unaffected -- a 35-turn two-process game completes and audits cleanly.

Ruled out: redraw cost (skipping unchanged frames did not help) and signal
handling (guarded). The remaining suspect is the uvicorn/FastMCP server's
behaviour when its loop is not on the main thread.

Not a specification question and not a compliance failure -- the mandatory
artefacts (belief-map screenshots) are produced, and league play does not need
the GUI. Options if it needs fixing: run the GUI as a separate process reading
the operational JSONL, or drive Tk from the asyncio loop at a very low frame
rate. Recorded rather than hidden.

---

## Q-18 — A barrier landing on the cell the opponent already chose

**Status: NEGOTIATE.** *Found in Phase 4, running full games.*

Both peers choose from the same pre-turn board, so neither acts illegally, yet
the cop's barrier can land on the very cell the thief had already picked. One of
the two actions then cannot be carried out.

Four readings, none excluded by the specification: the thief's move fails and it
stays; the move succeeds and the barrier lands behind it; the placement fails,
pre-empted; or the collision is itself a capture.

The test harness applies the first, named `BLOCKED_MOVE_BECOMES_STAY`, **only so
a demonstration terminates**. It is not a ruling. Two peers applying different
readings would compute different boards from identical action sequences, which
surfaces as a failed audit costing both sides the match.

---

## Q-17 — Revealed actions make the belief map nearly redundant

**Status: NEGOTIATE.** *Raised in Phase 4.*

Both start cells are signed shared conditions and every action is revealed each
turn, so a peer can dead-reckon its opponent's exact position. Traced over a
real game, the cop's belief peak matched the thief's true cell on every turn.

That sits oddly with the belief/scent apparatus, which exists precisely because
the opponent is meant to be hidden. Either the reveal is meant to be coarser
than an exact action, or the intended uncertainty is only *within* a turn --
you do not know their move when choosing yours, which commit-reveal already
guarantees.

The belief machinery is therefore built to carry genuine uncertainty
(diffusion when a move is unknown, scent as a likelihood, impossible-cell
exclusion) and simply happens to be well-informed under the present reveal
semantics. Not resolved unilaterally.

---

## Q-16 — In-turn reveal cannot be hash-verified (a property, not a defect)

**Status: RESOLVED by the PDF — recorded because it is counter-intuitive.**
*Raised in Phase 3.*

A natural expectation is that a peer verifies the opponent's commitment when
the reveal arrives. **It cannot**, and this follows directly from the PDF.

PDF p. 51, on the Reveal step: *"The agent sends the opponent the action (Move)
and the verbal sentence. **The Nonce remains hidden at this stage**, to prevent
premature reverse-engineering of the signatures."* And on the final step:
*"Only at the end of the whole game are all Nonce values revealed, for full
mutual audit."* E-18 makes nonce secrecy mandatory, sanctioned by
disqualification.

Since the commitment is `SHA256(… ‖ nonce)`, a peer holding a reveal without the
nonce has nothing to recompute. So the verification schedule is:

| When | What is checked |
|---|---|
| On reveal, in-turn | **Binding**: schema, game id, sub-game, turn, role, prior commitment exists, action structurally valid |
| At final reveal, end of match | **The commitment itself**: recompute `SHA256(canonical(record))` and compare (E-19, E-36) |

This is why tampering is caught at the audit rather than during play, exactly as
Ch. 5 (PDF p. 55) describes. It also means an *implementation* that verified
hashes in-turn would necessarily have shipped the nonce early and broken E-18.

**Consequence to carry forward:** a peer cannot refuse an illegal-looking move
on cryptographic grounds mid-turn. It can and does reject it on *physics*
grounds — the opposing agent enforces the rules (PDF p. 38) — and any
inconsistency between what was revealed and what was committed surfaces at the
audit, where the sanction is a technical loss.

---

## Q-15 — May the cop barrier the cell it is standing on?

**Status: NEGOTIATE.** *Discovered in Phase 1.*

PDF p. 37 lists the legal placement targets explicitly: *"any cell within one
step of it — **the cell it stands on itself**, or one of the four orthogonally
adjacent cells"*. So placing a barrier on one's own cell is permitted in as many
words.

But the same sentence says the cell "becomes impassable to **both** players
until the end of the game". The PDF never says what happens to a cop standing on
a cell it has just made impassable. Three readings, none excluded by the text:

1. **The cop is now trapped there.** Every move out is a move *from* a blocked
   cell, which the rules do not forbid — only entry is forbidden — so on this
   reading the cop can still leave but never return. This is the reading we
   implement, because the movement rule constrains destinations only.
2. **The cop cannot move at all**, having barriered itself in place. This makes
   the action self-destructive and effectively dead.
3. **The placement is illegal in practice**, and the PDF's phrase is loose.

We implement reading 1: `validate_move` checks the *destination* for barriers
and says nothing about the origin, so a cop that barriers its own cell may walk
away and may not come back. Note this also makes `STAY` illegal for that cop,
since `STAY`'s destination is the blocked cell it occupies — a consequence that
falls out of the rule rather than being written into it.

**Impact if the opponent reads it differently:** low but real. A cop that
barriers its own cell and then moves would, under reading 2, have made an
illegal move — and an illegal move is rejected by the opposing agent (PDF p. 38)
and can escalate to a technical loss. Worth one sentence in negotiation; the
tactic is unlikely to be worth using either way.

---

## Q-14 — `min_games_to_pass` = 2 matches, but E-31 says "matches against different groups"

**Status: RESOLVED**, non-issue, recorded for clarity.

E-31 (PDF p. 147) and Ch. 9 (PDF p. 86) require correct operation of at least
`[min_games_to_pass]` **against different groups**; Appendix C's checklist
(PDF p. 136) says "at least two matches against different groups: 2 and above".
Appendix F sets `min_games_to_pass = 2` FIXED, and `max_games_per_team = 10`
FIXED.

Combined with E-52 (only one counting match per opponent), this means: **at
least 2 distinct opponents, at most 10 distinct opponents.** No contradiction.
