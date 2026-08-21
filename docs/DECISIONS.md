# DECISIONS

Architecture and interpretation decisions, with the reasoning that produced
them. Decisions that resolve a contradiction in the PDF cross-reference
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) and **must appear in the final `README.md`
academic report**, per the academic-freedom clause (PDF p. 5).

Format: what was decided, why, what it costs, and what would reverse it.

---

## D-1 — Source priority is fixed and mechanical

**Decision.** When sources conflict, resolve in this order:

1. Appendix F parameter tables (numeric values) — PDF pp. 151–159
2. Explicit mandatory rules (Appendix E, and rule boxes in the chapters)
3. Recommendations
4. Illustrative examples, diagrams and sample code — **never** a source of
   requirements

**Why.** PDF p. 4 states the founding principle: a rule is not binding unless
explicitly written as a rule, and all illustrations, examples, code excerpts and
scenarios are a mode of demonstration. PDF p. 5 states that Appendix F remains
the single binding source for quantitative values even under contradiction.

**Cost.** Some intuitively-appealing details in the book's figures are
discarded. Accepted deliberately.

---

## D-2 — `num_games` = 6, not 1

**Decision.** The shipped shared config carries `num_games: 6`. No config used
in a counting league match may carry any other value.

**Why.** Appendix F table 18 sets it to 6 with status FIXED; the Appendix B
example file ships 1. D-1 rule 1 applies. Resolves
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-1.

**Cost.** A demo run is six sub-games long rather than one. Mitigated by a local
`--sub-games N` development override that is refused when the match is flagged
as counting.

**Reversal condition.** The lecturer stating that 1 is intended for league play.

---

## D-3 — `technical_loss: 0` is carried but marked as non-Appendix-F

**Decision.** Ship `scoring.technical_loss: 0` in the shared config; the
validator treats it as NEGOTIABLE with default 0 rather than FIXED.

**Why.** It appears in the Appendix B config example, Ch. 3's scoring table and
E-48, but has no row in Appendix F table 17 — so the binding numeric source does
not bind it. Asserting FIXED status would be inventing a requirement. Resolves
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-3.

**Cost.** None practically; all sources agree on 0.

---

## D-4 — Commit hash covers the rich record, canonically serialised

**Decision (corrected 2026-08-20 — see below).** `H_commit =
SHA256(canonical_json(record_without_nonce) + "|" + nonce)` where the record
is `{v, game_id, sub_game, turn, role, state, action, hint, intent}` plus the
pipe-appended `nonce`, canonically serialised with `sort_keys=True,
separators=(",", ":")`, UTF-8. The schema is agreed with the opponent before
the match and its hash exchanged at handshake.

**Why.** Ch. 5 gives a four-field formula but states in the same passage that
the record actually sealed is richer (hint, intent classification, step, role)
and that canonical JSON serialisation is used so both peers hash byte-identical
input. Ch. 7's two-field sketch is self-declared as simplified. The richer record
also binds more: sealing the hint means a peer cannot swap the hint after
committing to it. Resolves [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-4.

**Cost.** The schema must be negotiated, since a mismatch makes every audit fail.
Accepted — this is inherent to a judge-free design and is why the config-hash
exchange exists.

**Correction (2026-08-20), nonce placement.** The book's v3.0.0 release
publishes three mutually inconsistent commit constructions (a ch.5 listing
that seals the nonce *inside* the hashed JSON object as an ordinary field; a
ch.7/audit-chapter snippet, `SHA256(f"{nonce}|{move}")`, self-declared
illustrative; and the reference implementation's own
`SHA256(canonical(payload)|nonce)`, nonce pipe-appended *outside* the
hashed object). The original D-4 text above implemented the first
(ch.5-listing) form — self-consistent, every local test passed, and the
divergence from the reference form was invisible until checked against an
external conformance kit (`copthief-league-protocol`, a cross-team
interop-vectors project, not the book) whose `vectors/commit_reveal.json`
pins the reference form byte-for-byte. Since this project's own audit
re-hashes only its own revealed records (self-verification never crosses
this line), the bug never surfaced in this repository's test suite; it
would surface only against a real opponent's audit. Switched to the
reference form (`crypto/sealed.py`'s `commitment()`/`commitment_for_mapping()`,
via the new `config/hashing.py::pipe_nonce_commitment`) as the safer of the
two resolutions the interop kit itself offers (switch, or sign a documented
deviation into `config/game.json`) — it costs nothing (the wire schema,
message flow and key set are unchanged; only the internal hash formula
moved) and is what any opponent's audit will assume by default. See
`tests/interop/test_commit_reveal.py` for the regression coverage.

---

## D-5 — Gmail `mode` defaults to `send`, not `draft`

**Decision.** Default `send`. The reporting module refuses `draft` when the
match is flagged as counting.

**Why.** The private TOML skeleton shows `mode = "draft"` and the reference repo
sends drafts, but E-32 requires automatic reporting via Gmail, E-51 requires
sending to the lecturer address, and Ch. 9 states each team must itself send the
report, with non-receipt costing that side its points. A draft never reaches the
lecturer. Resolves [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-7.

**Cost.** Testing must use a throwaway recipient rather than drafts. Acceptable.

---

## D-6 — Simultaneous moves under commit-reveal, not strict alternation

**Decision.** A full turn is one step by each peer, executed simultaneously:
both commit, both acknowledge, both reveal. `step` increments once per full
turn. Scent decay applies once per full turn.

**Why.** The PDF never specifies who moves first, but fixes that decay happens
after *both* have moved — so turns are paired. Commit-reveal exists precisely to
let two mutually distrustful parties act simultaneously without either reacting
to the other. Choosing simultaneity dissolves the unspecified question instead of
resolving it arbitrarily. Addresses [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-2.

**Cost.** Must be agreed with the opponent; a peer expecting alternation will
deadlock. Raised explicitly in negotiation.

---

## D-7 — Capture evaluated on post-move positions only

**Decision.** Capture is true when post-move positions coincide. A cell swap is
not a capture. Moving onto a just-vacated cell is not a capture. If capture and
the survival threshold complete in the same turn, capture wins.

**Why.** Ch. 3 defines capture as the cop *landing on* the thief's cell, which
reads as post-move coincidence. The alternatives are not supported by any text.
Addresses [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-9.

**Cost.** Materially affects outcomes, so it must be agreed explicitly rather
than assumed.

---

## D-8 — Step-0 uses SHA-256 commitment, not a signature, pending clarification

**Decision.** Implement the step-zero declaration as canonical JSON + SHA-256,
exchanged and locked at handshake. Do **not** invent a key-distribution scheme.

**Why.** Ch. 5 refers to signing "with a pre-supplied key" but the PDF never
says who supplies it, what algorithm, or how it is verified. Fabricating one
would be inventing a requirement. A SHA-256 commitment satisfies the stated goal
("cannot be forged after the fact") using machinery the project already
mandates. Addresses [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-12 — which remains
**ESCALATE**: ask the lecturer before the first counting match.

**Cost.** If a real key is supplied later, this changes — but only behind the
crypto module's interface, so the blast radius is one module.

---

## D-9 — Local truth enforced structurally, not by convention

**Decision.** The live-state object has **no attribute** for the opponent's
position — not `None`, not `Optional`. The GUI is constructed with handles to
the local-truth and belief modules only, never to the network layer's raw data.
The replay verifier is the only omniscient component and imports nothing from
the live path.

**Why.** E-8 and E-9 carry the heaviest sanctions in the document
(disqualification of the project for an illegal advantage). A convention that
"we just won't display it" is not testable; an absent attribute is — a leak
becomes an `AttributeError` in a unit test. Cheap to do, and it converts the
highest-consequence rule into a mechanically verified one.

**Cost.** Slightly more plumbing when the replay verifier needs both sides'
data. Contained: the verifier reads logs from disk after the match.

---

## D-10 — Configuration is the only entry point for numeric constants

**Decision.** No numeric value from Appendix F appears as a literal in game
logic. All are read from a typed config object. A validator rejects any config
that lowers a MINIMUM or alters a FIXED value, and runs at load time on both
peers.

**Why.** Appendix F §2 makes defining all values in the config mandatory, and
E-11/E-12 make identity and non-lowering mandatory. Centralising also makes the
byte-identity requirement achievable, and makes "did we use the right value"
a single test rather than a grep.

**Cost.** A config object must be threaded through the domain layer. Cheap and
conventional.

---

## D-11 — Tkinter for both GUI and replay viewer

**Decision.** Tkinter for the Live GUI and the replay viewer.

**Why.** Standard library, zero install, cross-platform, sufficient for a
heatmap grid, a turn banner and step controls — which is the entire mandated
scope. The PDF names Tkinter and PyQt as examples only. Matches the brief's "a
simple GUI technology with minimal setup" and the priority ordering that puts
visual polish last.

**Cost.** Not pretty. Explicitly acceptable given the stated priorities.

---

## D-12 — Pure verifier separated from the viewer

**Decision.** `replay/verifier.py` is a pure function over a log file returning
`Verified OK` / `TAMPERED` with the offending entry. `replay/viewer.py` is the
Tkinter shell around it.

**Why.** E-19 and E-20 are the most testable rules in the document, and a
headless pure function lets pytest assert both the clean case and deliberately
tampered logs without a display. Also lets the same verifier run inside the
mutual audit (E-36) at end of match, so there is one implementation of hash
checking rather than two that can drift.

**Cost.** None.

---

## D-13 — `template` is the default verbal provider

**Decision.** `[trash_talk] provider = "template"`. Zero tokens, no network, no
LLM dependency in the default path.

**Why.** Appendix F table 21 names `template` as the default and states the
entire series can be played at zero tokens in template or ollama mode, moving
the competition onto the movement algorithm. The brief forbids paid LLM APIs and
prefers deterministic templates over optional AI complexity. It also removes an
entire class of nondeterminism from the test suite.

**Cost.** Less colourful bluffing. The provider interface stays swappable, so
adding `ollama` later is a config change.

---

## D-14 — Heuristic brain (Bayes belief + Manhattan) is the MVP strategy; no RL

**Decision.** Ship the Bayesian belief map + Manhattan distance policy. No
reinforcement learning in the MVP.

**Why.** The PDF states plainly that the course did not teach RL, that a fully
strong agent can be built with heuristics alone, and that RL is one optional
tool among three equal-standing routes — with pure heuristics being the
reference implementation's own default. Strategy quality ranks sixth in the
stated priorities, below compliance, working system, verification and
simplicity.

**Cost.** Possibly weaker play against a tuned opponent. Revisit only after every
mandatory requirement is complete and verified.

---

## D-15 — JSONL for the live audit log, sealed JSON for the artefact

**Decision.** Append-only JSON Lines during the match; sealed into the canonical
`log_<game_id>_g<NN>.json` at end of sub-game.

**Why.** E-7 requires the watchdog to extract data in a controlled way after a
crash — a partially-written JSON array is unreadable, a partially-written JSONL
file is fully readable up to the last complete line. The mandated artefact
filename is `.json`, so the seal step converts. Also matches the brief's
"JSON Lines audit logs".

**Cost.** One conversion step. Trivial, and it is the natural place to compute
the end-of-sub-game summary anyway.

---

## D-16 — Two repositories are produced by splitting at submission time

**Decision.** Develop in one repository; produce the two mandated repositories
(cop, thief) at submission, each carrying its role's config tree, its own
`README.md` with the cross-link, and the shared source.

**Why.** E-49 requires two separate GitHub repositories with cross-linked
READMEs. E-1/E-2 require two separate *processes* and separate config
directories — which is a runtime property, satisfied regardless of repository
layout. Developing twice in parallel would duplicate every change and is the
likeliest source of the two sides drifting apart, which is itself a compliance
risk.

**Cost.** A deliberate split step before submission, which must not be
forgotten. Tracked as a mandatory task in [../TASKS.md](../TASKS.md).

**Note.** The user's brief says no GitHub repository is to be created yet. This
decision records the intended end state only.

---

## D-18 — Config paths reconcile Appendix B filenames with Chapter 2 separation

**Decision.** `config/police/game.json`, `config/police/game.toml`,
`config/thief/game.json`, `config/thief/game.toml`.

**Why.** Two PDF passages have to be satisfied at once. Appendix B names the
files `config/game.json` and `config/game.toml` with no role sub-directory
(PDF pp. 126, 130). Chapter 2 requires the two roles to run under **separate
configuration directories**, offering `/config/thief` vs `/config/police` as an
example (PDF p. 31, "for example"). The layout above keeps Appendix B's
filenames and Chapter 2's mandatory separation.

**Cost.** The path is not literally the PDF's. Documented here and in
[PARAMETERS.md](PARAMETERS.md) §2 so it is never mistaken for a quotation.

**Reversal condition.** An opponent or the lecturer expecting the flat
Appendix B path. Trivial to change — it is one constant in the loader.

*Added in the second-pass audit.*

---

## D-19 — The log record schema is defined, and the scent field is not stored

**Decision.** Define an explicit log record schema
([PROTOCOL.md](PROTOCOL.md) §11) carrying commitments, moves, hints, **LLM
discussion fields**, nonce and hash. Do **not** store the rendered scent field
or either peer's position history as data; the verifier recomputes both from the
move sequence plus the config.

**Why.** PDF p. 94 enumerates the mandatory log contents, and the LLM discussion
fields are easy to overlook — the log is not a move list. The first-pass
documentation defined the wire protocol but never the log format, even though
the log is what the replay verifier and the mutual audit actually consume; that
was a real gap.

Not storing the scent field is the more interesting half. A live peer writes
this file, so any global-truth field inside it would put global truth in the
live path — exactly what E-9 forbids. Recomputation from moves costs nothing and
keeps the boundary structural rather than procedural.

**Cost.** The verifier must implement the physics to replay. It has to anyway,
in order to check capture claims.

*Added in the second-pass audit.*

---

## D-20 — Administrative lead-time work starts early, in parallel

**Decision.** Google Cloud / OAuth account provisioning and opponent-team
coordination move out of their code phases and begin in parallel from Phase 0,
as `[P]` tasks.

**Why.** Both have latency that is not ours to control. OAuth consent-screen
configuration requires adding test users and can stall; finding opponent teams
willing to negotiate a shared config and play a counting match depends on other
people's schedules, and E-31 requires at least two such matches against
different groups. Leaving either until its code phase risks the plan being
blocked by something no amount of engineering fixes.

This does **not** mean writing reporting code early — Phase 9 still owns that,
per the PDF's own ordering. It means the *account* and the *relationships* exist
before the code needs them.

**Cost.** None; these are administrative tasks with no code dependency.

*Added in the second-pass audit.*

---

## D-21 — The private config may not shadow a shared key at all

**Decision.** Rather than implementing "shared JSON overrides private TOML", the
loader **rejects** any private file that defines a key owned by the shared
constitution (`PrivateConfigShadowsSharedError`).

**Why.** PDF p. 132 requires the shared values to override any parallel key in
the TOML *"so the private file can never 'weaken' a signed condition"*. The
requirement is the guarantee, not the mechanism. Rejecting the shadowing
delivers that guarantee more strongly than overriding does — a key that is never
accepted can never win, under any future refactor — and it keeps the two
configurations as separate typed objects rather than merging them into one.

Overriding also has a failure mode rejection does not: a team could put
`num_games = 1` in their private file, see it silently ignored, and believe they
had configured something. Rejection tells them.

**Cost.** A team migrating a value from private to shared must delete it from
the TOML rather than leaving it as dead weight. That is the correct outcome.

**Reversal condition.** An opponent insisting on genuine overlay semantics.

*Added in Phase 0.*

---

## D-22 — Derived cross-field rules are marked as derived

**Decision.** Cross-field validation contains seven rules the PDF does not state
verbatim. Each is labelled `DERIVED` in `validation.py` with its justification,
and each is justified by *some documented rule becoming unsatisfiable* if it were
violated — not by general good sense.

The derived rules: distinct start cells (identical cells would satisfy the
capture condition before the first move); `survival_threshold <= max_moves`
(otherwise survival, a documented win condition, is unreachable);
`max_barriers <= cells - 2`; `pheromone_grid_size <= grid_size`; intensity and
decay within `(0, 1]`; `response_timeout_sec < watchdog_timeout_sec` (Ch. 8
separates a per-request deadline from a process-freeze threshold, and inverting
them collapses the distinction); `min_games_to_pass <= max_games_per_team`.

**Why.** The brief forbids inventing requirements, and these are inferences.
Marking them keeps the boundary between quoted and inferred legible to a later
reader — and to the opponent team, since a config we reject and they accept is a
match that never starts.

**Cost.** A negotiated config could in principle be rejected for a rule the PDF
never stated. Mitigated by each rule being a genuine incoherence rather than a
preference.

*Added in Phase 0.*

---

## D-23 — Config paths: one shared file, role directories at runtime

**Decision.** Ship `config/game.json` (the shared constitution) plus
`config/cop.toml.example` and `config/thief.toml.example` as templates. At
runtime each peer reads its own `config/<role>/game.toml`, copied from the
matching template.

**Why.** This supersedes D-18's `config/<role>/game.json`. Appendix B names the
shared file `config/game.json` (PDF pp. 126, 130), and there is only ever *one*
shared constitution — duplicating it per role would create two files that must
be byte-identical to each other as well as to the opponent's, which is a
needless third way for E-11 to fail. Chapter 2's mandatory *separation* concerns
the per-peer runtime configuration, and that is preserved: two processes, two
private files, two config directories.

**Cost.** D-18 is superseded; recorded here rather than edited away so the
reasoning trail stays intact.

*Added in Phase 0.*

---

## D-24 — FIXED floats compare with a tolerance

**Decision.** `_values_equal` compares FIXED float parameters with
`math.isclose(rel_tol=1e-9)` rather than `==`.

**Why.** `pheromone_decay` is tabulated as `0.10`. Today, `0.10` in the file and
`0.10` in the policy table parse to the same double — but that is a property of
these particular literals, not a guarantee of binary floating point. A team
writing `1e-1`, or a future value like `0.3` reached by arithmetic, could differ
in the last bit. Disqualifying a team over a last-bit difference would be a bug,
not enforcement.

Integers and lists still compare exactly; the tolerance applies only where the
representation is genuinely approximate.

**Cost.** In principle a value within 1e-9 of the binding value would pass. No
Appendix F value has neighbours anywhere near that close.

*Added in Phase 0.*

---

## D-25 — Barrier placement is a distinct action, not a flag on a move

**Decision.** Two action types: `Move(direction)` and `PlaceBarrier(cell)`. The
PDF specifies no wire encoding, so this internal representation is ours.

**Why.** PDF p. 37 makes placement an alternative *to* moving: "on a turn where
the cop forgoes movement, it may place a barrier". Modelling it as a flag on a
move would let "move and place" be expressed, which the rule does not permit.
With two types the exclusivity is in the type system and cannot be violated by
a careless caller.

`PlaceBarrier` names the target cell explicitly because the cop must declare
every placement and its exact location and may not place one covertly (E-15,
E-16) — the declaration is part of the action, not an afterthought.

**Cost.** The wire encoding still has to be agreed with the opponent in Phase 2;
this decision constrains only our internals.

*Added in Phase 1.*

---

## D-26 — "No legal move" (E-47) means no legal *relocation*

**Decision.** A thief is trapped when it has no legal move to an adjacent cell.
`STAY` does not rescue it.

**Why.** Read alone, "a thief imprisoned with no legal move whatsoever" would
never trigger: `STAY` is in the FIXED move set, so a legal action always exists.
But the rule's own parenthetical defines the condition precisely — *"all
adjacent cells blocked by barriers and/or board edges"* (PDF p. 37) — which is
about adjacency, not about available actions. Board edges count, so a thief in a
corner needs only two barriers to be trapped.

This is why `rules.py` exposes `legal_relocations` alongside `legal_moves`: the
distinction is what makes the rule expressible at all.

**Cost.** None. The alternative reading makes E-47 dead text.

*Added in Phase 1.*

---

## D-27 — A "step" is a completed full turn

**Decision.** The survival counter and the move ceiling both count **full
turns** — both peers having acted — not individual agent actions.

**Why.** The PDF's own unit of time is the full turn: scent decay is applied
"at the end of each full turn — after both the cop and the thief have completed
their move" (Ch. 4, PDF p. 43). Counting half-turns would make
`survival_threshold` and `max_moves` mean different things on the two sides,
and both are shared config values that must mean the same thing to both peers.

**Cost.** A sub-game runs 35 full turns rather than 35 individual actions —
twice as long in wall-clock terms. Consistent with the PDF's framing.

**Reversal condition.** An opponent counting half-turns; worth confirming
alongside the turn model (Q-2).

*Added in Phase 1.*

---

## D-28 — Capture lives outside `LocalState`, in an adjudicator

**Decision.** Capture evaluation is a set of free functions in
`domain/capture.py` taking both positions as explicit parameters. It is never a
method on `LocalState`, and `LocalState` gains no opponent field to support it.

**Why.** All three capture conditions except E-47 need both positions. Had
capture been a method on the state, the state would have needed the opponent's
position — precisely what E-9 forbids, and the most natural way the rule would
have been broken.

Passing both positions explicitly is more awkward, and that awkwardness is the
feature: every omniscient call site is visible and countable. In Phase 1 the
only caller is the test harness; in the delivered system it is the capture-claim
protocol (E-21, E-22) and the replay verifier — both of which have a *right* to
the information.

`TransitionResult.barrier_cell` exists for the same reason: a barrier placement
can capture (E-46), but the transition function reports the cell and lets the
adjudicator make the comparison, rather than reaching for the thief's position
itself.

**Cost.** Callers must thread both positions through. Contained: three functions.

*Added in Phase 1.*

---

## D-29 — Phase 2 wire protocol: envelope, versions, size bound, tool surface

**Decision.** A single closed-schema envelope (ten keys) wrapping typed
payloads; schema version matched exactly, protocol version compatible on major;
a 64 KiB message bound; and a two-tool FastMCP surface (`health_check`,
`receive_protocol_message`).

**Why.** The PDF prescribes no wire protocol — it prescribes the obligations
one must satisfy (E-11, E-26, E-27) and shows a single illustrative tool
(PDF p. 28). One generic validated receiver beats many handlers because every
extra tool is another place validation can drift. The size bound exists because
an unbounded decoder is a denial-of-service surface (E-29). Exact schema
matching but major-compatible protocol versions: a different schema version is
a different key set with no safe way to guess omissions, while minor protocol
additions must interoperate between two teams who cannot deploy simultaneously.

Turn messages and a `TURN_INTENT` placeholder are deliberately absent: a
message type no state accepts and no code produces is untestable dead code.
They arrive in Phase 5 with the cryptography that gives them meaning.

**Cost.** The whole protocol must be negotiated with each opponent — but that
was already true of everything on the wire (D-4).

**Reversal condition.** Opponent negotiation; the protocol version field exists
precisely so this can change.

*Added in Phase 2.*

---

## D-30 — Action wire encoding

**Decision.** `{"v": 1, "kind": "move", "direction": "N"}` and
`{"v": 1, "kind": "place_barrier", "cell": [r, c]}`. Role-independent; closed
key set per kind; versioned separately from the envelope; well-formedness
checked by the codec, board legality left to the domain.

**Why.** The PDF prescribes no action encoding. Role is omitted because the
envelope already carries `sender_role`, and a second copy of the same fact is a
place for the two to disagree. The codec does not validate against a board
because it has none — legality is the domain's job, and the receiving peer
enforces the physics (PDF p. 38).

Defined in Phase 2 but **transmitted only from Phase 5**: a move sent in the
clear before commit-reveal would let either side react within the same turn,
which is what the commitment scheme exists to prevent.

**Cost.** Key spelling must be agreed with the opponent, since canonical
serialisation makes it load-bearing (Q-4).

*Added in Phase 2.*

---

## D-31 — Duplicates: cached replies for exact repeats, rejection for conflicts

**Decision.** A bounded registry (capacity `queue_depth`, least-recently-
inserted eviction) keyed on message id. Exact duplicate → the cached reply is
returned and no work is redone. Same id with a different payload →
`ConflictingDuplicateError`, logged as evidence. Evicted ids are treated as new.
Payload comparison is by canonical bytes, not `==`.

**Why.** A retry after a lost response is indistinguishable from a duplicate,
so the far end must make repeats safe — and preserving the message id across
retries (which the client does) is what makes that work. A conflicting reuse is
the signature of trying to change a decision after the fact — what commit-reveal
prevents — so it is rejected loudly rather than silently resolved either way.
Canonical-bytes comparison means an opponent whose JSON library orders keys
differently does not have every legitimate retry rejected as a conflict.

**Cost.** An id evicted from a full registry and then retried is re-processed
rather than replayed. Bounded memory is worth that: every handler is
idempotent, so re-processing is harmless, while an unbounded registry is a
memory leak a long series would find.

*Added in Phase 2.*

---

## D-32 — Connection loss is an operational failure, not a game outcome

**Decision.** When the opponent is unreachable, times out beyond bounds, or the
watchdog fires, the peer records a structured failure (`peer_unavailable`,
`watchdog_stall`), transitions to `DISCONNECTED`, winds down cleanly and exits
non-zero. It does **not** declare itself the winner or the opponent the loser.

**Why.** The PDF defines a technical loss for a side that crashes or exceeds
time (Ch. 3, PDF p. 38), but *adjudicating* that is league business — both
teams report to the lecturer, and E-35's dual-report mechanism is exactly how
conflicting accounts get resolved. A peer that declares game outcomes about its
opponent from its own perspective would be acting as its own referee, in a
system whose defining property is that there is none.

**Cost.** A genuinely crashed opponent yields no immediate scored result; it
yields evidence in the operational log for later adjudication. That is the
correct division of authority.

*Added in Phase 2.*

---

## D-33 — The operational log is not the audit chain

**Decision.** Peers write an append-only JSONL operational log (connections,
retries, transitions, handshake results). It is explicitly **not** the
cryptographic match log of PROTOCOL.md §11 — that is hash-chained, sealed, and
arrives in Phase 5. The event sink *refuses* to write records containing
credential-shaped keys or opponent-position keys, raising instead.

**Why.** Two different artefacts with two different guarantees. Conflating them
would invite treating operational telemetry as evidence, which it is not — it
proves nothing about the game and is not verified by anyone. The refusal (rather
than redaction) on forbidden keys means a careless caller gets an exception at
write time, not a leaked token in a file that later gets committed (E-39) or an
opponent position in a file that later gets shared (E-9).

**Cost.** None; the two logs coexist.

*Added in Phase 2.*

---

## D-34 — Sealed-record schema and key spelling

**Decision.** The sealed record is a closed ten-key mapping:
`{v, game_id, sub_game, turn, role, state, action, hint, intent, nonce}`,
hashed as `SHA256(canonical_json_bytes(mapping))`. `v = "1.0"`.

**Why.** The *semantic* field set is mandatory — Ch. 5 (PDF pp. 50–51) names
`State`, `Move`, `Intent`, `Nonce` in the formula and states that the record
actually sealed also includes the hint, the intent classification, the step
number and the role, with the sample code adding `sub_game`. The **key
spelling is prescribed nowhere**, and canonical serialisation makes it
load-bearing: `sub_game` and `subGame` are different commitments. So the schema
is versioned and must be agreed with each opponent (extends D-4).

`state` is the SHA-256 of the committing peer's *own* pre-move local state, not
the state itself. That satisfies the PDF's stated purpose — *"prevents reuse of
an old commitment in a new context"* — without putting a position on the wire.

Deliberately absent: any timestamp (the PDF requires none, and two clocks would
break the byte-identity both peers depend on), private config, opponent
position, board state.

*Added in Phase 3.*

---

## D-35 — Nonce: 128 bits from `secrets`, lowercase hex

**Decision.** `secrets.token_hex(16)` — 32 lowercase hex characters. A local
`NonceGuard` refuses to issue one twice.

**Why.** The PDF fixes no length; the reference implementation uses
`token_hex(16)` (PDF p. 52), so this matches it. `secrets` rather than `random`
because the Mersenne Twister's state is recoverable from its output, and the
nonce is the only thing standing between a commitment and a lookup table over a
move space of tens of elements — which is precisely the dictionary attack
PDF p. 50 says the nonce exists to defeat.

The guard is for *our own bug* (a coordinator reusing a pending record), not for
collisions: at 128 bits, collision is not a consideration.

*Added in Phase 3.*

---

## D-36 — Nonce disclosed only at the final reveal, per E-18

**Decision.** The per-turn `REVEAL` carries the sealed record **without** the
nonce; all nonces are disclosed together in a single `FINAL_REVEAL` at the end
of the match. The reveal message schema has no nonce field at all, so omitting
it is structural rather than remembered.

**Why.** PDF p. 51 is explicit in both directions: the nonce *"remains hidden at
this stage"* during reveal, and *"only at the end of the whole game are all
Nonce values revealed"*. E-18 sanctions disclosure with disqualification.

**This overrides the Phase 3 brief**, which asked for the nonce in the reveal
payload. The PDF is the authoritative source under this project's own stated
priority order, and shipping the nonce early would break a mandatory rule. See
OPEN_QUESTIONS.md Q-16 for the consequence: in-turn reveals are verified for
*binding*, and the commitment hash is verified at the audit.

*Added in Phase 3.*

---

## D-37 — Audit chain: formula, genesis, and the privacy schedule

**Decision.** Each record hashes as
`SHA256(canonical_json_bytes(record minus current_event_hash))`, with
`previous_event_hash` included in that input and a genesis predecessor of 64
zeros. Append-only JSONL, flushed per line. The writer **raises** rather than
filters when handed a forbidden key, and permits a nonce only in a
`final_reveal` record.

**Why.** Excluding the hash from its own input is arithmetic necessity;
including the predecessor's hash is the whole chain — it is the only reason
altering record 3 invalidates record 4. An explicit genesis means record 1 is
verified by the same code path as every other, with no special case.

Raising rather than filtering, because a filtered leak leaves the caller
believing it recorded something it did not. Restricting nonces to the final
reveal enforces E-18 in the log as well as on the wire: a log holding a
commitment *and* its nonce would defeat that commitment for anyone reading the
file.

*Added in Phase 3.*

---

## D-38 — Commit and reveal sends overlap their waits

**Decision.** A peer starts its `COMMIT` (and later `REVEAL`) send as a task and
waits for the opponent's concurrently, settling the send afterwards. A send
whose acknowledgement is lost does not fail the turn if the opponent's own
message proves progress.

**Why.** Found by the two-process demonstration, not by unit tests. Both peers
act simultaneously, so if each blocked on its own send before beginning to
wait, each would hold its event loop inside a request whose answer depends on
the other making progress — a deadlock invisible to any single-sided test. The
same run showed the client was opening a fresh MCP session per message, which
serialised the bidirectional traffic; the client now holds a persistent session
and closes it on error.

**Cost.** Slightly more intricate turn code. Justified: this is the class of bug
that only appears between two real processes, which is where the league runs.

*Added in Phase 3.*

---

## D-39 — Scent radial falloff is Gaussian, sigma = 1.15

**Decision.** Emission at squared distance d2 from the centre is
`center_intensity * exp(-d2 / (2 * 1.15**2))`.

**Why.** The specification fixes the centre intensity, the decay rate and the
window size (all FIXED parameters) and describes the falloff only as "radial".
Its figure, however, tabulates the whole 5x5 field, and sigma = 1.15 reproduces
every one of those values to two decimal places -- 0.90 / 0.62 / 0.42 / 0.20 /
0.14 / 0.04. That table is the only numeric anchor available, and an opponent
reading the same document would most likely fit the same curve.

Still a project decision, and one E-23 already requires to be exchanged and
cryptographically locked with a concrete numeric example before a series. The
model exposes `numeric_example()` for exactly that exchange.

*Added in Phase 4.*

---

## D-40 — Belief map: predict/correct, with an honest fallback

**Decision.** Predict through the motion model (exact when an action is known,
diffusing over legal moves when not), correct by a `1 + w*intensity` scent
likelihood, exclude impossible cells, renormalise. If contradictory evidence
zeroes every cell, reset to uniform *minus* the cells just disproven.

**Why.** The likelihood is `1 + intensity` rather than `intensity` so that a
cell with no scent is merely unremarkable rather than impossible -- trails
decay, and absence of scent is weak evidence, not proof. The fallback matters
because an empty distribution is no basis for any decision; "I no longer know"
is the truthful state, and it must not reinstate a cell we have just ruled out.

*Added in Phase 4.*

---

## D-41 — Replay trusts neither peer, and says how it failed

**Decision.** Four verdicts, not two: `VERIFIED OK`, `TAMPERED`, `INCOMPLETE`,
`POLICY MISMATCH`. Peers log a `sub_game_start` (config hash, board, policy
identifiers) and a `sub_game_end` carrying *claims*; the replay recomputes the
outcome and contradicts a claim rather than adopting it.

**Why.** A live peer cannot adjudicate — it never sees its opponent's position —
so it plays to the turn limit and the replay decides where the game actually
ended. Confirmed in a real run: both peers played 35 turns; the replay found the
capture at turn 30.

The verdicts are distinct because the failures are: a truncated log is a crash,
a broken chain is an accusation, and two peers running different resolution
rules is neither — nobody cheated, they simply were not playing the same game.
Collapsing those into "invalid" would misattribute blame. The policy check runs
*before* the config check for the same reason, and the verifier refuses to
substitute a policy the logs were not produced under (Q-18 stays configurable).

**Cost.** Two extra log records per sub-game. Without them the two logs cannot
be told apart from two peers playing different games.

*Added in Phase 5.*

---

## D-42 — The runtime is quiet by default; `--verbose` is opt-in

**Decision.** `peer/run.py` constructs its event sink with `echo=False`, and a
new `--verbose` flag turns the stdout echo back on. `PeerServer` defaults
uvicorn to `log_level="warning"`. The JSONL operational log and the hash-chained
audit log are untouched and remain **the authoritative record** — nothing was
removed from them, only from stdout. `stateless_http=True` and
`json_response=True` are kept as transport simplifications.

**Why.** This is the fix for Q-20, and the reasoning matters more than the
one-line change. The peer wrote every operational event to stdout with a
synchronous `print(..., flush=True)` called from inside the asyncio turn
coroutines, and uvicorn added an INFO line per request on the same stream. Both
launchers captured that stdout through a pipe they never drained. A pipe buffer
is finite: once full, the next `print` blocks, and blocking there parks the
whole event loop — so the process stayed alive while its FastMCP server stopped
accepting and answering connections. Roughly 40 seconds of loop lag were
measured at the freeze. Reducing the volume of synchronous output to near zero
removes the mechanism entirely rather than widening the margin.

Keeping the file logs authoritative is the point of the split. Diagnostics must
survive being ignored; a peer whose evidence depends on somebody watching its
console is not a peer that can be audited afterwards, and the audit — not the
terminal — is what the specification actually requires (D-33, D-37). `--verbose`
exists because watching a run live is genuinely useful during development; it is
opt-in because doing it under an undrained capture is what caused the fault.

**Two alternatives were rejected, both on the grounds that they treat the
symptom.**

*A dedicated thread for the FastMCP server.* This would let the server keep
answering while the main loop is blocked, and it is the obvious "make the stall
impossible" move. Rejected: the loop would still be blocked, so the peer would
answer requests while unable to compute a turn, converting a visible freeze into
a peer that is reachable and mute — harder to diagnose, not easier. It also adds
a thread boundary to a codebase that deliberately runs one loop per process, and
Q-19 is direct evidence that moving this server off the main thread has its own
failure mode.

*Raising `max_retries` and the timeouts.* Rejected because the blocked peer never
recovers on its own: retrying against a process parked in a blocking write
changes only how long the game takes to fail. It would also mean editing
Appendix F values to paper over a local bug, which inverts the relationship
between the specification and our code — and MINIMUM parameters may only move in
the direction that makes the game harder (Q-8), not looser to accommodate us.

**Cost.** A default run prints little. Accepted: the JSONL log holds strictly
more than stdout ever did, and `--verbose` restores the old behaviour on demand.

**Reversal condition.** None expected for the default. If a future launcher
drains stdout continuously *and* live echo is wanted, `--verbose` already covers
it — the default should still not change, because the next launcher may not
drain.

**Evidence.** [../results/q20_transport_proof.md](../results/q20_transport_proof.md);
resolves [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-20.

*Added 2026-07-31; the proving run is dated 2026-07-30.*

---

## D-43 — The `[strategy]` class override is wired and fails loudly

**Decision.** `strategy/heuristics.py` gains `load_strategy(role_value,
class_path)`. `PeerOrchestrator` now calls it with
`private.strategy.police_class` / `thief_class` instead of calling
`strategy_for(role)` unconditionally. An unset or empty path returns the
shipped heuristic, unchanged. A configured path (`"module.path:ClassName"`) is
imported, instantiated with no arguments, and checked for the `BaseStrategy`
shape (`.choose` callable, `.name` present) before being accepted. Any failure
along that path — bad path syntax, unimportable module, missing class, wrong
shape — raises `StrategyLoadError` at orchestrator construction, not later.

**Why.** `config/*.toml.example` has documented this key
(`police_class = "my_team.strategy:MyPoliceBrain"`) since Phase 0, and
`config/models.py` and `config/loader.py` already parsed it into
`StrategySettings`, but nothing read it — a team could set the key, see no
error, and unknowingly play the shipped default. That is the same class of
silent-substitution risk the project refuses everywhere else: a config-hash
mismatch refuses to play (E-11) rather than falling back to a default, and a
malformed shared key is rejected by the closed schema rather than ignored
(F-2). A strategy override that fails silently would be the one place that
philosophy wasn't applied. Failing at construction, not at first `choose()`
call, means the error surfaces at startup — before a match, not mid-turn.

**Cost.** One more error type (`StrategyLoadError`) a peer's launcher must be
prepared to see and report; in practice `run.py` already exits non-zero on any
unhandled construction error, so no launcher change was needed.

**Reversal condition.** None expected. If a future custom-brain protocol needs
constructor arguments (config, seed, whatever), extend `load_strategy`'s
instantiation step then — the import/validate/fail-fast shape stays.

*Added 2026-08-08, during the post-evaluation cleanup pass that also
reconciled `TASKS.md`/`todo.md` with the actual code state.*

---

## D-44 — Q-19 was four separate GUI-lifecycle defects, not one

**Decision.** Retest `--gui` against the Q-20 fix explicitly rather than
assume it was covered, since `docs/OPEN_QUESTIONS.md`'s own Q-20 entry
recorded that link as unproven. Fix each defect found independently, with its
own regression test, rather than one broad "make the GUI more robust" change.

**Why.** The four defects found have unrelated causes and would not have been
caught by a single fix: `final_status` was published too late (a *timing* bug
in `run.py`, not a rendering bug in `gui/live.py`'s already-correct
`banner_for`); the screenshot trigger needed to fire relative to an actual
repaint, not a published snapshot; Ctrl+C and window-close never reached the
worker thread's shutdown event at all; and a benign uvicorn-internal
`CancelledError` traceback only became visible once shutdown was orderly
enough to expose it. Treating them as one bundle risked declaring Q-19
resolved on the strength of a fix that addressed only the first defect found.

**Cost.** Four smaller, targeted changes and four smaller, targeted test
suites (`tests/gui/test_capture.py`, `tests/gui/test_drive_main_thread.py`,
two tests in `tests/gui/test_live_gui.py`, one in `tests/peer/test_run_cli.py`,
`tests/peer/test_server_shutdown.py`) rather than one. Accepted: each defect
is independently verifiable and independently regressable.

**Evidence.** [../results/q19_gui_proof.md](../results/q19_gui_proof.md) --
real Windows run `game_id` `q19-final-proof-35-01`: 35 turns, `GAME COMPLETE`
displayed correctly, PNG screenshots captured
(`results/screenshots/q19_cop_final_35.png`,
`results/screenshots/q19_thief_final_35.png`), clean shutdown with no
`CancelledError` traceback, Final Reveal over all 35 turns, mutual audit both
directions, both audit chains `Verified OK` (179 records), Windows full suite
1563 passed / 1 skipped / 0 failed. Resolves
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-19.

**Separately confirmed, not fixed here.** The same investigation (verifying
why live played 35 turns while the offline replay found a capture at turn 30
-- itself expected under D-41, not a new defect) surfaced that `capture_claim`
(E-21/E-22), the PDF's own designed mechanism for a live mid-match stop
(`docs/PROTOCOL.md` §6.5), is completely unimplemented in `src/`, despite
`docs/COMPLIANCE_AUDIT.md` marking E-21/E-22 `COVERED`. Tracked as a follow-up
in `docs/COMPLIANCE_AUDIT.md` Part 9 and `todo.md`; not implemented as part of
this decision.

*Added 2026-08-09.*

---

## D-17 — One test per mandatory rule, named by rule ID

**Decision.** Test functions carry the rule ID, e.g.
`test_e13_rejects_diagonal_move`. [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md)
maps every rule to its test or deterministic manual procedure.

**Why.** The brief requires every mandatory behaviour to have a test or
deterministic verification procedure. Naming by rule ID makes coverage
auditable by grep, and makes the compliance argument in the README concrete
rather than assertive.

**Cost.** Some tests are trivial. Worth it — the audit trail is itself a
deliverable.
