# PROTOCOL

The minimum FastMCP tool interface and wire contract between two peers.

> **Implementation status (Phases 2–3).** Handshake *and* the cryptographic
> turn are implemented and running between two real processes: envelope schema,
> codec, config-hash exchange, commit → acknowledge → reveal → final-reveal
> audit, hash-chained audit logging, duplicate handling, retry/timeout, and the
> full state machine. §0 documents the implemented wire format and supersedes
> the sketches in §§2–6 for the messages it covers. Still design-only: the
> capture claim, and the two-log game replay. Built against **fastmcp 3.4.5**.

---

## 0. Phase 2 wire format (implemented)

### 0.1 Envelope

Every message is one JSON object with exactly these ten keys — a closed schema;
unknown or missing keys are rejected (`ProtocolValidationError`):

```jsonc
{
  "schema_version":   "1.0",       // must match exactly
  "protocol_version": "1.0",       // compatible iff major versions match
  "message_id":       "<uuid4>",   // preserved across retries (idempotency key)
  "game_id":          "…",         // both peers launched with the same value
  "sender_role":      "police",    // "police" | "thief"
  "receiver_role":    "thief",
  "message_type":     "hello",     // closed set, §0.2
  "turn_number":      null,        // int ≥ 0 or null; null throughout Phase 2
  "timestamp":        "2026-07-28T12:00:00.000+00:00",  // informational ONLY
  "payload":          { … }        // closed schema per message type
}
```

Encoding is canonical JSON (the single project implementation), UTF-8, bounded
at **64 KiB** — an unbounded decoder is a DoS surface (E-29). The timestamp is
never hashed and never orders anything: two machines have two clocks, and the
PDF names clock drift among the real-world failures to survive (p. 109).
Ordering comes from `turn_number` and the state machine.

### 0.2 Message types and payloads (closed set)

| Type | Payload keys | Purpose |
|---|---|---|
| `health_check` | — | Liveness probe; carries no game information |
| `hello` | `peer_name`, `software_version`, `capabilities` | Introduce; verify mandatory capabilities |
| `config_hash` | `config_sha256`, `config_schema_version` | E-11 exchange |
| `config_accepted` | `config_sha256` | Hashes match |
| `config_rejected` | `reason`, `our_config_sha256`, `their_config_sha256` | Refuse to play |
| `ready` | — | Handshake complete on the sender's side |
| `ack` | `acknowledged_message_id` | Generic acknowledgement |
| `error` | `code`, `detail` | Structured failure report |
| `game_finished` | `reason` | Sub-game/match conclusion signal |
| `shutdown` | `reason` | Clean wind-down notice |

No payload has a field for a position, a board, or a cell — asserted by test.
Turn-bearing messages (`commit`/`ack`/`reveal`…) are deliberately absent until
Phase 5; see D-29.

### 0.3 FastMCP tool surface

Two tools per peer, symmetric on both sides:

- `health_check()` → `{ok, peer}`
- `receive_protocol_message(envelope)` → `{ok, error, detail?, retryable?, envelope?}`

Validation failures return `ok:false` **as a structured reply**, never as a
transport exception, so both peers log the same thing and the sender can
distinguish "rejected" (do not retry) from "lost" (retry within bounds).

### 0.4 Handshake sequence (implemented)

```
A: hello ────────────────► B      capabilities checked both ways
A ◄──────────────── hello :B      (as the reply payload)
A: config_hash ──────────► B      B compares against its own hash
A ◄─ config_accepted/rejected :B  rejected ⇒ ERROR state, no turns, exit 1
A: ready ────────────────► B
A ◄─────────────────── ack :B     READY when both sent and received ready
```

Both peers run this concurrently in both directions — each is client and server
at once. On `config_rejected` **both** sides refuse to play (verified in a real
two-process run: both exit 1, state `error`, no turn is ever attempted).

### 0.5 Retries, deadlines, duplicates (implemented)

- Every call: admitted by the Gatekeeper (queue → rate → concurrency, from
  Appendix F values), deadlined at `response_timeout_sec`, retried at most
  `max_retries` times with `retry_backoff_sec` spacing. Validation failures are
  never retried.
- The **message id is preserved across retries**; the receiver's bounded
  registry (capacity `queue_depth`) returns the cached reply for an exact
  repeat and raises `ConflictingDuplicateError` for the same id with a
  different payload (D-31).
- Watchdog: `watchdog_timeout_sec` of silence → structured `watchdog_stall`,
  `DISCONNECTED`, controlled wind-down. Connection loss is an operational
  failure, not a self-declared game outcome (D-32).

### 0.7 The cryptographic turn (implemented, Phase 3)

**Sealed record** — closed schema, versioned, agreed with the opponent (D-34):

```jsonc
{
  "v": "1.0",
  "game_id": "…", "sub_game": 1, "turn": 7, "role": "police",
  "state":  "<sha256 of the committer's OWN pre-move local state>",
  "action": {"v":1, "kind":"move", "direction":"N"},
  "hint":   "…", "intent": "truth",          // "truth" | "lie"
  "nonce":  "<32 lowercase hex, secrets.token_hex(16)>"
}
```

No timestamp (two clocks would break byte-identity), no private config, no
opponent position, no board state. `state` is a *hash*, so it binds the
commitment to a position without disclosing one.

**Commitment formula:**

```
commitment = SHA256( canonical_json_bytes(sealed_record) )   // 64 lowercase hex
```

Same canonical helper as the config hash and every other digest in the project.

**Message sequence** — the PDF's four phases (Ch. 5, pp. 50–51):

```
A                                                    B
│── COMMIT {commitment}          ─────────────────► │   digest only
│ ◄───────────────── COMMIT_ACK {locked:true} ──────│   "prevents retreating"
│                    …both must have committed…      │
│── REVEAL {sealed WITHOUT nonce} ────────────────► │   action + hint only
│ ◄───────────────── REVEAL_ACK  ───────────────────│
│                    …repeat per turn…               │
│── FINAL_REVEAL {records with nonces} ───────────► │   end of match ONLY
│ ◄──── FINAL_REVEAL_ACK {audit:"OK", turns:N} ─────│   SHA-256 recomputed here
```

**The nonce is not in the per-turn reveal** (E-18, D-36). Consequently an
in-turn reveal is verified for *binding* — schema, game, sub-game, turn, role,
prior commitment, structural validity — while the *commitment* is verified at
the final reveal. See OPEN_QUESTIONS.md Q-16.

**Duplicate and replay handling:** exact duplicate commit/reveal is idempotent;
a *different* commitment or reveal for the same role and turn fails the turn
(a decision cannot be changed once made); a reveal with no prior commitment, or
for a stale or future turn, or claiming the wrong game/sub-game/role, is
rejected. `COMMIT`/`REVEAL` must carry a `turn_number` or the envelope is
rejected — a commitment unbound to a turn could be replayed into another.

**Timeouts:** each wait is bounded by `response_timeout_sec`; sends are bounded
by `max_retries` with `retry_backoff_sec`; failure enters `TURN_FAILED` and the
pending nonce is discarded, never logged and never reused.

### 0.8 Audit log (implemented, Phase 3)

Append-only JSONL, one record per line, hash-chained. **Distinct from the
operational log** of §0.5 — that is telemetry; this is evidence.

```jsonc
{
  "schema_version": "1.0", "event_id": "<uuid>",
  "game_id": "…", "role": "police", "sub_game": 1, "turn_number": 7,
  "event_type": "local_commit",          // closed set
  "timestamp": "…",
  "previous_event_hash": "<64 hex, genesis = 0*64>",
  "current_event_hash":  "<64 hex>",
  "payload": { … }
}
```

```
current_event_hash = SHA256( canonical_json_bytes(record WITHOUT current_event_hash) )
```

`previous_event_hash` is inside that input — that inclusion *is* the chain.
The verifier recomputes from genesis and detects modification, deletion,
insertion, reordering, duplicate event ids and malformed lines, reporting the
first failure. Demonstrated against real logs.

**Privacy schedule.** Before a reveal the log holds commitments, message ids and
protocol state — never the action, its target, or any nonce. Nonces appear in
**exactly one** record type, `final_reveal`. The writer raises rather than
filters, so a mistake surfaces where it was made.

### 0.6 Peer lifecycle states (implemented)

```
CREATED → STARTING → SERVER_READY → CONNECTING → HELLO_EXCHANGE
        → CONFIG_EXCHANGE → CONFIG_VERIFIED → READY_WAIT → READY
        → FINISHING → FINISHED
```

Phase 3 adds the turn cycle, reachable from `READY` and repeatable:

```
READY → SELECTING_ACTION → LOCAL_ACTION_SEALED → WAITING_FOR_OPPONENT_COMMIT
      → BOTH_COMMITS_RECEIVED → REVEAL_ALLOWED → LOCAL_REVEAL_SENT
      → WAITING_FOR_OPPONENT_REVEAL → VERIFYING_REVEAL → BOTH_REVEALS_VERIFIED
      → APPLYING_TURN → TURN_COMPLETE ─┬─► SELECTING_ACTION  (next turn)
                                       └─► FINISHING
```

The ordering is the safety property, not documentation of one: **the only edge
into `REVEAL_ALLOWED` comes from `BOTH_COMMITS_RECEIVED`**, and the only edge
into `APPLYING_TURN` comes from `BOTH_REVEALS_VERIFIED`. "No reveal before both
commitments" and "nothing applied before verification" are therefore
unreachable-by-construction rather than checks someone could forget.
`TURN_FAILED` is the controlled failure path from every turn state.

`ERROR` (terminal) is reachable from every non-terminal state; `DISCONNECTED`
is **not** terminal — it allows the controlled wind-down `→ FINISHING →
FINISHED`. Illegal transitions raise and leave the state unchanged.

Design constraints from [REQUIREMENTS.md](REQUIREMENTS.md): symmetric peers, no
central referee, commit-reveal over SHA-256 with the nonce hidden until end of
match, natural-language hints only (**never numeric position protocols**, E-27),
explicit and schema-validated messages.

**Status of this document.** The PDF does not specify a wire protocol. It
specifies the *obligations* the protocol must satisfy (E-17, E-18, E-26, E-27,
E-11, E-6, E-4/E-5) and shows a minimal FastMCP server as an example (PDF p. 28,
`receive_move`). Everything below is our design meeting those obligations. It is
negotiable with the opponent, and **must** be agreed with them before a match,
because both sides must speak it. Where the PDF fixes something, it is cited.

---

## 1. Symmetry

Both peers expose **the same** tool set and call **the same** tools on each
other. There is no client-only or server-only side (Ch. 2, PDF pp. 25–26).

```python
mcp = FastMCP("police_thief_peer")

@mcp.tool
def hello(...) -> dict: ...
@mcp.tool
def declare(...) -> dict: ...
@mcp.tool
def commit(...) -> dict: ...
@mcp.tool
def acknowledge(...) -> dict: ...
@mcp.tool
def reveal(...) -> dict: ...
@mcp.tool
def capture_claim(...) -> dict: ...
@mcp.tool
def final_reveal(...) -> dict: ...
@mcp.tool
def result_agreement(...) -> dict: ...
```

Eight tools. That is the whole surface.

---

## 2. Common envelope

Every request and every response carries the same envelope fields. Anything
outside the schema is rejected.

```jsonc
{
  "protocol_version": "1.0",     // string, must match exactly on both sides
  "game_id":   "…",              // string, identifies the match (all sub-games)
  "sub_game":  1,                // int, 1..num_games
  "step":      7,                // int, 0-based; 0 reserved for step-zero
  "role":      "police",         // "police" | "thief" — the SENDER's role
  "group_id":  "abcd1234",       // 8 chars, no spaces (E-45)
  "ts":        "2026-07-28T09:14:22Z"  // RFC 3339 UTC, sender's clock
}
```

Standard response envelope:

```jsonc
{
  "ok":     true,
  "error":  null,        // when ok=false: one of the error codes in §9
  "detail": null         // human-readable; never load-bearing
}
```

**Validation is mandatory on ingress.** Unknown fields, wrong types, or a
`protocol_version` mismatch are rejected with `ERR_SCHEMA`. A peer never acts on
an unvalidated message.

---

## 3. Config-hash exchange (E-11)

Before any play, both peers must prove they loaded a byte-identical shared
config. This is the mechanism that replaces the referee's authority over the
rules.

**Canonical hash definition.** The hash is taken over the shared config file's
canonical JSON serialisation — `sort_keys=True`, `separators=(",", ":")`,
UTF-8 — so that formatting differences between the two teams' files cannot
produce a false mismatch, and no semantic difference can produce a false match.

```
config_sha256 = SHA256( canonical_json_bytes( parsed(config/game.json) ) )
```

`config_sha256` is **the PDF's own field name** (Appendix B, PDF p. 127), not a
name we coined. Appendix B also requires the shared file to be *locked with a
cryptographic signature* (PDF p. 126) and Appendix F §2 to be *locked
cryptographically* (PDF p. 156) — so the shared config is **both hashed and
signed**, not one or the other. **Phase 0 implements the hash only**; the
signature waits on the step-zero signing key, which the PDF never defines
([OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-12).

**Exact calculation** — implemented in `police_thief.config.hashing`:

1. Read the file as **UTF-8**. A decoding failure is `ConfigParseError`.
2. Parse as JSON with an `object_pairs_hook` that **rejects duplicate keys**
   within any one object (`DuplicateConfigKeyError`). The standard parser keeps
   the last occurrence silently, which would let two peers read different values
   from what each believes is the same document.
3. Serialise the **entire parsed mapping** with
   `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False,
   allow_nan=False)`.
4. Encode that text as **UTF-8** to bytes.
5. `hashlib.sha256(bytes).hexdigest()` — 64 lowercase hex characters.

The whole document is hashed, including `schema_version` and `agreed_between`:
both peers load the same file, so the whole file is what must agree.

Consequences, each covered by a test:

- Source **key order** and **whitespace** do not affect the digest, so the two
  teams may format their copies differently and still match.
- Any change to a binding value **does** change the digest.
- The **private TOML is not an input** and cannot affect it. The cop and thief
  run different private files against one constitution and must produce the
  same digest.
- The digest is stable across processes and runs.

The shipped `config/game.json` hashes to:

```
410066bfe426b268092f69b07e95e2bab4fa8826dd5b1b8643cbbf6befd0a24d
```

pinned in `tests/config/test_hashing.py::test_shipped_config_matches_the_pinned_digest`
so that an unintended change to a binding value fails the suite rather than a
match.

### `hello` — handshake and config agreement

Request:

```jsonc
{
  "…envelope…",
  "peer_name":      "My-Team-cop",
  "config_sha256":  "3f9a…",       // 64 lowercase hex
  "schema_version": "1.2",
  "scent_model_sha256": "b71c…",   // E-23: hash of the agreed emission/decay
                                   // formula TOGETHER WITH its numeric example
  "games_played_counted": 3        // E-37: counted matches played so far
}
```

Response:

```jsonc
{
  "…response envelope…",
  "peer_name":      "Their-Team-thief",
  "config_sha256":  "3f9a…",
  "scent_model_sha256": "b71c…",
  "games_played_counted": 1,
  "agreed": true
}
```

**Rules.**

- If `config_sha256` differs → **refuse to play**. Return `ERR_CONFIG_MISMATCH`
  and terminate. Not a technical loss; the match simply never starts (E-11:
  "refuse to play on any mismatch").
- If `scent_model_sha256` differs → refuse to play (E-23; a deviation in the
  decay formula voids the match).
- `games_played_counted` is the E-37 declaration. It is recorded in the log and
  in `[declaration_file]`. A false declaration disqualifies (E-38); it is
  cross-checked by the lecturer against the reports both teams send.
- `hello` is idempotent and may be retried safely.

**What is hashed for the scent model.** E-23 requires exchanging the *full*
emission and decay model **including a concrete numeric example**. We hash the
canonical JSON of:

```jsonc
{
  "formula": "tau_next = max(0, (1 - rho) * tau + delta_tau)",
  "rho": 0.10,
  "center_intensity": 0.9,
  "window": 5,
  "falloff": "radial",
  "example": { "tau": 0.9, "after_one_decay_turn": 0.81 }
}
```

---

## 4. Step zero — `declare` (E-24, E-53)

Sent once per sub-game, before step 1, by both peers.

```jsonc
{
  "…envelope…",              // step = 0
  "code_version":   "1.0.0",
  "github_commit":  "a1b2c3d…",     // E-53: the commit actually played
  "github_repos":   { "cop": "https://…", "thief": "https://…" },
  "group_name":     "My-Team",
  "members":        ["id-1001", "id-1002"],
  "hardware": {
    "os":        "Windows 11 Pro 10.0.22621",
    "cpu_cores": 8,
    "cpu_ghz":   2.4,
    "ram_gb":    16,
    "gpu":       null,
    "vram_gb":   0
  },
  "llm": { "provider": "template", "model": null },
  "token_budget": 200000,
  "signature": "…"                  // signed per Ch. 5, PDF p. 56
}
```

Response echoes the peer's own declaration with the same shape.

Both declarations are written to `[declaration_file]`
(`declaration_<game_id>.json`) and are immutable for the match. Code **may**
change between matches, but every match must carry the commit hash actually
played (E-53), and an email with that commit number goes to the lecturer
(Appendix F §2).

---

## 5. Turn ordering

**Unspecified by the PDF.** The book never states whether the cop or the thief
moves first. What it *does* fix (Ch. 4, PDF p. 43) is that scent decay happens
**at the end of each full turn — after both the cop and the thief have completed
their move**. Turns are therefore *paired*, not interleaved. See
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-2.

Our design, to be confirmed in negotiation:

- A **full turn** = one step by each peer, executed **simultaneously** under
  commit-reveal. Both peers commit before either reveals, so neither can react
  to the other's move within the same turn. This is exactly what commit-reveal
  is for, and it removes the first-mover question entirely rather than resolving
  it by fiat.
- `step` counts full turns and increments only after both reveals are verified.
- Scent emission for both peers, then a single global decay pass, are applied at
  the end of the full turn — once, not twice.
- Terminal conditions are evaluated after both moves are applied.

**Simultaneity and capture.** If both peers' moves would resolve to a capture
condition in the same turn, capture is evaluated after both moves land. The
resolution rule (does the cop moving onto the thief's vacated cell count?) is a
physics question the two teams must agree in negotiation. Recorded as
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-9.

---

## 6. Commit-reveal ordering (E-17, E-18)

The four phases are mandatory **and ordered** (Ch. 5, PDF pp. 50–51).

```
        COP                                    THIEF
         │                                       │
  1      ├──────────  commit(H_commit)  ────────►│
         │◄─────────  commit(H_commit)  ─────────┤
         │                                       │
  2      ├──────────  acknowledge()    ─────────►│
         │◄─────────  acknowledge()    ──────────┤
         │                                       │
  3      ├──────────  reveal(move,hint) ────────►│      nonce STILL HIDDEN
         │◄─────────  reveal(move,hint) ─────────┤
         │                                       │
         │           …repeat for all steps…      │
         │                                       │
  4      ├────────  final_reveal(nonces) ───────►│      end of match only
         │◄───────  final_reveal(nonces) ────────┤
```

### 6.1 The sealed record

The PDF's formula is `H = SHA256(State ‖ Move ‖ Intent ‖ Nonce)` (PDF p. 50) but
states in the same breath that the record actually sealed is **richer** and also
includes the hint, the intent classification, the step number and the role, and
that concatenation is done by **canonical JSON serialisation with sorted keys
and fixed separators** so both peers hash byte-identical input.

We therefore lock this schema and hash its canonical serialisation:

```jsonc
{
  "game_id":  "…",
  "sub_game": 1,
  "step":     7,
  "role":     "police",
  "state":    "…",        // SHA-256 of the canonical pre-move local state
  "move":     "N",        // one of move_set, or a barrier action (§6.4)
  "hint":     "…",        // the exact verbal hint text that will be revealed
  "intent":   "truth",    // "truth" | "lie"
  "nonce":    "…"         // 32 hex chars, secrets.token_hex(16)
}
```

```
H_commit = SHA256( json.dumps(record, sort_keys=True,
                              separators=(",", ":")).encode("utf-8") ).hexdigest()
```

**This schema must be agreed with the opponent before the match** and its hash
included in the config-hash exchange, since both sides must recompute it
identically at audit. See [DECISIONS.md](DECISIONS.md) D-4.

`state` is a hash rather than the raw state so the commitment binds the move to a
specific game position (preventing replay of an old commitment in a new context,
per PDF p. 51) without leaking the position itself.

### 6.2 `commit`

```jsonc
// request
{ "…envelope…", "h_commit": "9c1f…" }        // 64 lowercase hex, nothing else
// response
{ "…response envelope…" }
```

Sends **only** the signature — never its content (PDF p. 50).

### 6.3 `acknowledge`

```jsonc
// request
{ "…envelope…", "acking_h_commit": "9c1f…" }
// response
{ "…response envelope…", "locked": true }
```

Confirms receipt and that the peer is *locked* on the commitment. Prevents the
sender retreating, and ensures reveal happens only once **both** sides have
fixed their moves (PDF p. 51).

### 6.4 `reveal`

```jsonc
// request
{
  "…envelope…",
  "move":   "N",                  // or {"action":"barrier","cell":[r,c]}
  "hint":   "Slipping past the bright lights near the square",
  "intent": "truth"               // "truth" | "lie"
}
// response
{ "…response envelope…", "accepted": true }
```

**The nonce is NOT sent here** (E-18, PDF p. 51). Revealing it early enables
premature reverse-engineering of signatures and exposes the commitment to a
dictionary attack over the small move space.

**Receiver obligations on `reveal`:**

1. Validate the move against the agreed physics: orthogonal or STAY only
   (E-13/E-14), within bounds, not into a barrier. An illegal move is rejected
   with `ERR_ILLEGAL_MOVE` — *the opposing agent enforces the physics*
   (PDF p. 38).
2. Validate the hint is natural language within `hint_max_words`, and contains
   no numeric position protocol (E-26, E-27). See §8.
3. If the move is a barrier placement, it must be openly declared here with its
   exact cell (E-15, E-16), and must be within one step of the cop's cell on a
   turn where the cop forgoes movement, with the quota `max_barriers` not
   exceeded.
4. Log the revealed values. They cannot be verified against `h_commit` yet — the
   nonce is still hidden — so verification is deferred to the final audit. This
   is inherent to the scheme, not a gap.

### 6.5 `capture_claim` (E-21, E-22)

Issued by the cop when it believes it has captured; the thief is under a
**cryptographic obligation to answer truthfully** (PDF p. 38).

```jsonc
// request  (cop → thief)
{ "…envelope…", "claimed_cell": [3, 4], "reason": "landed" }
   // reason: "landed" | "barrier_on_thief" | "no_legal_move"
// response (thief)
{ "…response envelope…", "confirmed": true, "thief_cell": [3, 4] }
```

Three capture conditions, all mandatory: the cop lands on the thief's cell
(Ch. 3 scoring table); the cop places a barrier on the cell where the thief
stands (E-46); the thief has no legal move at all (E-47).

A false claim by the cop, or a false denial by the thief, is exposed at audit and
carries immediate disqualification with no right of appeal (E-22).

### 6.6 `final_reveal` (end of match)

```jsonc
// request
{
  "…envelope…",
  "records": [
    { "sub_game":1, "step":1, "nonce":"…", "move":"N",
      "hint":"…", "intent":"truth", "state":"…", "h_commit":"…" },
    …
  ]
}
// response
{ "…response envelope…", "audit": "OK" }   // "OK" | "MISMATCH"
```

Only now are all nonces disclosed (E-18). Each side then performs the **mutual
audit** (E-36): for every record, recompute the canonical hash and compare
against the `h_commit` received live. Any mismatch → `MISMATCH` → technical loss
for the forging side, score 0 (E-19).

### 6.7 `result_agreement` (E-35)

```jsonc
// request
{
  "…envelope…",
  "audit_result": "OK",
  "per_sub_game": [ { "sub_game":1, "cop":20, "thief":5, "outcome":"capture" }, … ],
  "totals":       { "cop": 45, "thief": 30 },
  "tokens_used":  0,                 // E-54
  "result_sha256": "…"               // hash of the canonical result payload
}
// response
{ "…response envelope…", "agreed": true, "result_sha256": "…" }
```

Both sides must agree on the result **before** each independently emails its own
`[result_file]`. If one side fails to report, or the two reports contradict, the
match is disqualified and **both** teams score 0 (E-35).

---

## 7. Timeouts, duplicates and invalid sequences

### 7.1 Timeouts (E-6)

Every outgoing request carries a timestamp and an expiry deadline of
`response_timeout_sec` (Appendix F table 19 row 6). A request whose deadline
passed **is a failure, not an invitation to wait longer** (PDF p. 81).

| Situation | Behaviour |
|---|---|
| No response within `response_timeout_sec` | Retry up to `max_retries`, waiting `retry_backoff_sec` between attempts |
| Retries exhausted | Transition to `TECHNICAL_LOSS`, log it, close the turn cleanly, notify |
| Main loop emits no heartbeat for `watchdog_timeout_sec` | Watchdog performs controlled shutdown with state persistence (E-7) |

Technical loss zeroes **both** sides (Ch. 3 scoring table) — which is precisely
why neither side benefits from stalling.

### 7.2 Duplicates

The network may deliver a message twice, and a retry after a lost response is
indistinguishable from a duplicate. Every tool is therefore **idempotent**,
keyed on `(game_id, sub_game, step, role, tool)`:

| Case | Behaviour |
|---|---|
| Duplicate with **identical** payload | Return the previously computed response. Do not re-apply. Do not re-log as a new event; log a `duplicate_suppressed` note. |
| Duplicate with **different** payload for the same key | **Reject** with `ERR_DUPLICATE_CONFLICT`. This is an attempt to change a committed decision — exactly what commit-reveal exists to prevent. Log it as evidence for the audit. |

### 7.3 Invalid sequence (E-5)

The state machine rejects every transition not in its table, immediately, rather
than leaving the system in an undefined state (PDF p. 80).

| Case | Behaviour |
|---|---|
| Tool arrives in a phase where it is not legal (e.g. `reveal` before `acknowledge`) | Reject with `ERR_ILLEGAL_SEQUENCE`; state unchanged; logged |
| `step` skips ahead or goes backwards | Reject with `ERR_STEP_ORDER`; logged |
| `sub_game` inconsistent with local counter | Reject with `ERR_SUBGAME_ORDER` |
| `protocol_version` mismatch | Reject with `ERR_SCHEMA` at handshake; refuse to play |
| Repeated illegal-sequence attempts beyond a small threshold | Treat as a faulty or hostile peer; transition to `TECHNICAL_LOSS` |

A rejected transition never mutates state. That is what makes E-4/E-5 testable:
a test asserts that after a rejected message the phase is byte-identical to
before.

---

## 8. Natural-language constraint (E-26, E-27)

Hints must be **free natural language**. Direct numeric position protocols are
forbidden — the prohibition exists to preserve the psychological character of
the game, and violating it disqualifies the game's character as defined in the
rule book.

Ingress validation on every `reveal`:

- Word count ≤ `hint_max_words`.
- Rejected if the text encodes a coordinate: bare digit pairs, `(r,c)` / `[r,c]`
  forms, `row=`/`col=` style key-value pairs, or grid references like `B4`.
- The `intent` flag is metadata, not part of the hint text; it is committed
  (so a peer cannot retroactively claim it "meant to lie") and revealed
  alongside the hint.

Note the flag is *self-declared truthfulness*, and a peer is free to declare
`lie` and send a false hint — deception through the verbal channel is the
intended game. What is forbidden is committing `truth` and then revealing a hint
the log shows to be false, or encoding positions numerically to bypass the
psychological layer.

Scent, by contrast, cannot lie: it is emitted by movement itself and cannot be
forged (Ch. 4).

---

## 9. Error codes

```
ERR_SCHEMA               malformed message or protocol_version mismatch
ERR_CONFIG_MISMATCH      config_sha256 or scent_model_sha256 differs → refuse to play
ERR_ILLEGAL_SEQUENCE     tool called in a phase where it is not legal
ERR_STEP_ORDER           step number out of order
ERR_SUBGAME_ORDER        sub_game number out of order
ERR_DUPLICATE_CONFLICT   same key, different payload
ERR_ILLEGAL_MOVE         diagonal, out of bounds, into a barrier, or quota exceeded
ERR_ILLEGAL_HINT         exceeds hint_max_words or encodes numeric positions
ERR_COMMIT_MISMATCH      audit: recomputed hash ≠ declared commitment
ERR_TIMEOUT              deadline expired
ERR_INTERNAL             local failure; caller should retry then declare technical loss
```

Errors are returned in the response envelope (`ok:false`), never raised across
the wire as transport faults, so both sides log the same thing.

---

## 10. Game-completion signalling

A sub-game ends when exactly one of these is true. All are evaluated locally by
both peers from the shared physics, and must agree — divergence is itself a
protocol failure.

| Outcome | Trigger | Cop | Thief |
|---|---|---|---|
| Capture | Cop lands on thief's cell, or barrier placed on thief's cell (E-46), or thief has no legal move (E-47) — confirmed via `capture_claim` | `capture_cop` | `capture_thief` |
| Survival | Thief survives `survival_threshold` valid steps without capture | `survival_cop` | `survival_thief` |
| Technical loss | Crash, deadline exhaustion, or cryptographic forgery | 0 | 0 |

Sequence at completion of a **sub-game**: both peers reach the same terminal
state → log sealed → `sub_game` increments → next sub-game begins, up to
`num_games`.

Sequence at completion of a **match** (all `num_games` sub-games):

1. `final_reveal` — all nonces disclosed by both sides (E-18).
2. Mutual audit (E-36) — each side re-hashes and compares. Mismatch → technical
   loss for the forger, score 0 (E-19).
3. Tie check: if the accumulated score across **all** sub-games is equal, each
   side receives `tie_score` (Ch. 9, PDF p. 87).
4. `result_agreement` — both sides agree on the result (E-35).
5. **Each side independently** emails its own `[result_file]` as a JSON
   **attachment** to `[agent_reporting_address]` through the Gatekeeper
   (E-32, E-33, E-34, E-51). Failure by one side to report costs *that side* its
   points even if it won on the board; contradictory reports disqualify the
   match for **both**.
6. The encounter against that opponent is **sealed** — no further counting match
   against them (E-52).

---

## 11. Log record schema

*Added in the second-pass audit. Previously this document defined the wire
protocol but never the log format, even though the log — not the wire — is what
the replay verifier and the mutual audit actually consume.*

PDF p. 94 enumerates what `[log_file]` must contain: **commit-reveal
commitments, moves, hints, the LLM discussion fields, the nonce and the hash**,
with the stated purpose *"to enable full cryptographic verification in the
replay simulator"*. The LLM discussion fields are an explicit requirement and
the item most likely to be forgotten — the log is not merely a move list.

**Live format:** append-only JSON Lines, one object per protocol event, written
before the corresponding network call returns.
**Sealed format:** at end of sub-game, converted to the canonical
`log_<game_id>_g<NN>.json` — an object carrying the match metadata and an
ordered array of step records.

```jsonc
{
  "game_id": "…", "sub_game": 1, "game_uid": "…",
  "config_sha256": "…", "scent_model_sha256": "…",
  "declarations": { "police": { … }, "thief": { … } },   // step-zero, both sides
  "steps": [
    {
      "step": 7,
      "role": "police",
      "phase_trace": ["COMMITTING", "AWAITING_REVEAL", "VERIFYING"],
      "h_commit": "9c1f…",          // the commitment as sent live
      "state":    "…",              // hash of pre-move local state
      "move":     "N",              // or {"action":"barrier","cell":[r,c]}
      "hint":     "…",              // exact revealed hint text
      "intent":   "truth",          // "truth" | "lie"
      "nonce":    "…",              // populated at final reveal ONLY
      "llm": {                      // PDF p. 94: "the LLM discussion fields"
        "provider":        "template",
        "invoked":         false,
        "prompt":          null,
        "response":        null,
        "tokens_in":       0,
        "tokens_out":      0,
        "classification":  "lie"    // our read of the OPPONENT's last hint
      },
      "belief_top":  [[3,4], 0.06], // argmax cell and its probability
      "ts_sent":     "…", "ts_recv": "…"
    }
  ],
  "outcome": { "type": "capture", "police": 20, "thief": 5 },
  "tokens_total": 0
}
```

**Independent-replay sufficiency.** A third party holding only this file must be
able to re-derive everything and check it. The schema satisfies that:

| Needed to replay | Supplied by |
|---|---|
| The physics | `config_sha256` + the committed `config_<game_id>_g<NN>.json` |
| The scent model | `scent_model_sha256` + the same config |
| Start positions | config (`thief_start`, `cop_start`) |
| Every move, in order | `steps[].move`, `steps[].step`, `steps[].role` |
| Barrier placements | `steps[].move` when it is a barrier action |
| Hash verification | `h_commit` + `state` + `move` + `hint` + `intent` + `nonce` — the full sealed record of §6.1 |
| Scent field at any turn | Recomputed from moves + config; not stored, and must not be, since storing it would embed global truth in a live-written file |
| Outcome and scoring | `outcome` + config scoring block |
| Token accounting (E-54) | `steps[].llm.tokens_*` + `tokens_total` |

Two constraints on this schema follow from the local-truth rules:

- **`nonce` is null in the live log** and populated only at final reveal
  (E-18). A live log containing nonces would break the commitment scheme.
- **No opponent position is ever written by the live peer.** The verifier
  *derives* both trajectories from the two logs' moves plus the config; it does
  not read them from a field, because no such field exists. This is what keeps
  the log honest with E-9 while still being sufficient for replay.

