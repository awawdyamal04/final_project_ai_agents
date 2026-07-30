# ARCHITECTURE

Minimum architecture that satisfies every mandatory requirement in
[REQUIREMENTS.md](REQUIREMENTS.md). Design goal, in the project's stated
priority order: mandatory compliance first, then an end-to-end working system,
then automated verification, then minimal complexity.

Nothing here is invented beyond the PDF. Where a component exists only because
a rule demands it, the rule ID is cited.

---

## 1. The two constraints that shape everything

**Symmetry (E-1, E-2, Ch. 2).** The cop and the thief are the *same program*
running with a different role. There is no referee, no shared game-state server,
and no shared memory. A peer only ever knows: its own position, the scent field
its opponent emitted, the hints it received, and the commitments exchanged.

**Local truth (E-8, E-9, Ch. 7).** No component that runs during a live match
may hold or display the opponent's true position. The full global state is
reconstructible **only after the match**, by the replay verifier, from the two
logs plus the final nonce reveal.

These two constraints partition the system cleanly: *everything that runs live
is blind; only the post-game verifier is omniscient.* Every module below is on
one side of that line, and the line is enforced by module boundaries, not by
convention.

---

## 2. Layer map for one peer

```
                        ┌──────────────────────────────────────┐
                        │            ORCHESTRATOR              │   E-3: single gateway.
                        │  single entry point; coordinates,    │   Holds no decision
                        │  does not decide, does not talk      │   logic and no
                        └──┬────┬────┬────┬────┬────┬──────────┘   low-level I/O.
                           │    │    │    │    │    │
       ┌───────────────────┘    │    │    │    │    └───────────────────┐
       │              ┌─────────┘    │    └────────┐                    │
       ▼              ▼              ▼             ▼                    ▼
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐    ┌──────────────┐
│   STATE    │ │  DECISION  │ │    MCP     │ │    LOG    │    │  RELIABILITY │
│  MACHINE   │ │  (strategy)│ │ CONNECTOR  │ │  MANAGER  │    │ deadline +   │
│ E-4, E-5   │ │  E-25 sep. │ │  Ch. 2     │ │ E-36      │    │ watchdog     │
└─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬─────┘    │ E-6, E-7     │
      │              │              │              │          └──────────────┘
      │              ▼              ▼              ▼
      │       ┌────────────┐ ┌────────────┐ ┌────────────┐
      │       │ LOCAL TRUTH│ │  FastMCP   │ │ JSONL      │
      │       │ + OBSERVE  │ │ server AND │ │ audit log  │
      │       │ + BELIEF   │ │ client     │ │ + 4 JSON   │
      │       └────────────┘ └─────┬──────┘ │ artefacts  │
      │                            │        └────────────┘
      │                            ▼
      │                     ┌────────────┐
      │                     │  TUNNEL    │  E-10: public URL
      │                     │ (external) │
      │                     └────────────┘
      ▼
┌────────────┐        ┌──────────────────┐        ┌──────────────────┐
│  LIVE GUI  │        │  GATEKEEPER →    │        │  REPLAY VERIFIER │
│ local truth│        │  Gmail reporting │        │  E-20  (offline) │
│ only E-8/9 │        │  E-28,29,30,32   │        │  omniscient      │
└────────────┘        └──────────────────┘        └──────────────────┘
```

---

## 3. Separation of concerns — the eight responsibilities

The project brief requires local truth, observations, strategy, communication,
audit log, GUI, replay and reporting to be clearly separated. Mapping:

### 3.1 Local truth — `domain/state.py`

The only place holding **this peer's own** ground truth: own position, the
barrier set (public, since E-15 makes every placement openly declared), step
counter, own scent emissions, and the role.

**Invariant:** this module has no field for the opponent's position. Not
`Optional`, not `None`-initialised — the attribute does not exist. That makes
E-9 a structural property rather than a discipline. A leak becomes an
`AttributeError` in a test, not a subtle bug that survives to the league.

Barriers are shared knowledge legitimately: E-15/E-16 require the cop to declare
every placement truthfully and openly, so both peers converge on an identical
barrier set.

### 3.1.1 The state model: why `LocalState` cannot represent global truth

*Implemented in Phase 1.*

E-8 and E-9 carry the heaviest sanctions in the specification — disqualification
of the project — and they are the two rules a working implementation is most
likely to break by accident, because the opponent's position is exactly what
every part of the program would find convenient to know.

The guarantee is therefore structural, not procedural. `LocalState` is a frozen,
slotted dataclass whose fields are exhaustively:

| Field | Why it is legal |
|---|---|
| `role` | Which side this peer is |
| `position` | This peer's **own** cell — its own truth |
| `board` | Dimensions and the barrier set. Barriers are public **by obligation**: the cop must declare every placement and its exact location (E-15, E-16), so both peers converge on an identical set. Shared knowledge the rules *require*, not a leak. |
| `turn` | Local turn counter |
| `barriers_placed` | This peer's own quota consumption |
| `terminal` | Whether this peer considers the sub-game over |

There is **no attribute** for the opponent's position: not `None`, not
`Optional`, not a private underscore field. `slots=True` means one cannot be
attached at runtime either. A leak surfaces as an `AttributeError` in a unit
test rather than as an advantage that survives to the league.

This follows the Dec-POMDP formalism directly (Ch. 1, PDF p. 21): each agent's
observation Ωᵢ is a strict subset of the true state S. An object able to hold S
would be modelling a game nobody is playing.

**Capture therefore lives outside the state** (D-28). All three capture
conditions bar E-47 need both positions, so they are free functions in
`domain/capture.py` taking both as explicit parameters, called by something that
legitimately holds them: the test harness in Phase 1, the capture-claim protocol
(E-21, E-22) in the delivered system, and the replay verifier afterwards. The
awkwardness of threading both positions through is the point — it makes every
omniscient call site visible and countable.

`sim/` is the one package containing an omniscient component, and its docstring
says so in the first line: **nothing in it is production authority**.

### 3.2 Observations — `domain/scent.py`, `domain/observation.py`

Implements the emission/decay physics of Chapter 4 exactly as configured:
emission window `[pheromone_grid_size]` with centre
`[pheromone_center_intensity]` and radial falloff; systemic decay
`τ(t+1) = max(0, (1−ρ)·τ(t) + Δτ)` applied **at the end of each full turn**,
i.e. after both peers have moved.

**Asymmetry to respect:** each peer reads *only the opponent's* scent field, not
its own (Ch. 4, PDF pp. 41, 45). Two separate fields are therefore maintained:
the one this peer emits (sent/derivable by the opponent) and the one it
observes.

Scent cannot lie — it is emitted by the act of moving and cannot be forged. The
**only** deception channel is the verbal hint.

### 3.3 Strategy — `strategy/` (a genuinely separate module)

Ch. 6 (PDF p. 58) requires a **separate** strategy module wired into the peer
runtime at a precise seam: **immediately after decoding the incoming hint, and
before packing the outgoing commit**. Between those two points sits all of the
agent's intelligence.

```
incoming hint + observed scent
        │
        ▼
   hint decode ──► belief update (Bayes) ──► move choice (algorithmic)
                                                    │
                                          bluff text (LLM or template)
                                                    │
                                                    ▼
                                            outgoing Commit
```

Interface: `BrainBase` with `_pick_move` (and `_decide_move` for the cop, which
also selects the barrier). Selected via `config/game.toml → [strategy]`.

**Default policy:** Bayesian belief map + Manhattan distance — the reference
implementation's default and one of the three equal-standing routes. RL is out
of scope for the MVP (explicitly optional; the course did not teach it).

**Hard boundary:** the move is always decided in Python. The LLM touches only
the verbal layer. Move legality is enforced locally regardless of what any
model proposes — this holds even under the mutual-agreement exception of
PDF p. 66.

### 3.4 Communication — `net/mcp_server.py`, `net/mcp_client.py`

Each peer runs **both**: a FastMCP server exposing tools the opponent calls, and
a client calling the opponent's tools. Fully symmetric; no strong/weak side.

Schemas are explicit and validated on both ingress and egress. The message set
is deliberately small — see [PROTOCOL.md](PROTOCOL.md).

The tunnel (ngrok/Localtonet) is **external tooling**, not code we write: the
server binds to a host/port and the tunnel publishes it. `localhost` is
permitted only in early development stages (Ch. 2, PDF p. 29).

### 3.5 Audit log — `audit/log.py`

Append-only **JSON Lines** during the match: one record per protocol event,
written before the corresponding network call returns. JSONL because a crashed
peer must leave a readable partial log for the watchdog's controlled extraction
(E-7).

At end of match the JSONL is sealed into the canonical `[log_file]`
(`log_<game_id>_g<NN>.json`) for the replay verifier.

Mutual audit (E-36) runs at the end of **every** match, before agreeing the
result: each side re-hashes the opponent's revealed steps and compares to the
commitments. Any mismatch → technical loss (E-19), score 0 for the forger.

### 3.6 Live GUI — `gui/live.py`

Minimal-setup toolkit: **Tkinter** (stdlib, no install, cross-platform). The PDF
names Tkinter/PyQt only as examples.

Two display mechanisms, both mandated in substance by Ch. 7:

- **Belief heatmap** — the peer's probabilistic belief about the *hidden*
  opponent, deeper colour = higher probability. Never the opponent's true cell.
- **Turn banner** — green `YOUR TURN` when the turn has been received and action
  is enabled; grey `LOCKED` once the commit has been transmitted, with input
  ignored. The banner is the visual representation of the state machine and
  prevents a race condition where both sides act on the same step.

**The GUI reads from the local-truth and belief modules only.** It is given no
handle to the network layer's raw opponent data. This is what makes E-8/E-9
verifiable by test rather than by inspection.

Screenshots of the belief map are a submission requirement.

### 3.7 Replay and verification — `replay/verifier.py`, `replay/viewer.py`

**The only omniscient component, and it runs only after the match.**

- `verifier.py` — pure function over a log: for each entry, recompute
  SHA-256 over the canonical sealed record and compare to the stored
  commitment. Returns `Verified OK` or `TAMPERED`; a single failure voids the
  whole match.
- `viewer.py` — Tkinter window loading `[log_file]`, stepping forward/backward,
  displaying the reconstructed global state, with a green `Verified OK` stamp
  or a glaring red `TAMPERED` banner.

Separating the pure verifier from the viewer is what makes E-19/E-20 testable in
pytest without a display. Screenshot of `Verified OK` is a submission
requirement.

### 3.8 Reporting — `report/gatekeeper.py`, `report/gmail.py`, `report/build.py`

- `build.py` — assembles the four JSON artefacts (`declaration`, `config`,
  `log`, `result`) with the mandatory fields: both teams' GitHub links, per
  sub-game commit hash, total tokens consumed, hardware declarations, agreement
  confirmations.
- `gatekeeper.py` — three cumulative gates in order: Quota Manager → Token
  Bucket → DOS Detector. Fail fast; on DOS detection the whole pipe locks.
  Sacrifices one report to save the account.
- `gmail.py` — send-only scope `gmail.send`, JSON as an **attachment**, never
  free text. Honours 429 by backing off.

**Not built until the core system works** (Stage 7 of the recommended order).

---

### 3.4.1 The transport as implemented (Phase 2)

```
 PROCESS A (cop)                              PROCESS B (thief)
┌──────────────────────────┐   HTTP/MCP   ┌──────────────────────────┐
│ FastMCP server :8801     │◄─────────────│ PeerClient               │
│  health_check            │              │  gatekeeper → deadline → │
│  receive_protocol_message│              │  bounded retry           │
│        │ validated       │              └──────────────────────────┘
│        ▼ Envelope        │   HTTP/MCP   ┌──────────────────────────┐
│ PeerOrchestrator ────────┼─────────────►│ FastMCP server :8802     │
│  identity → registry →   │  PeerClient  │  (same surface)          │
│  state machine → act     │              │        │                 │
│  LocalState (own only)   │              │        ▼                 │
│  watchdog, events JSONL  │              │ PeerOrchestrator (same)  │
└──────────────────────────┘              └──────────────────────────┘
        no third process · no shared file · no shared memory
```

Layering, enforced by import-graph tests: `protocol/` (schemas + codec) knows
no transport and no game; `peer/server.py`/`client.py` know FastMCP but import
no rules, scoring, capture or strategy; `peer/orchestrator.py` coordinates but
decides nothing (E-3). The server's single generic validated receiver replaces
the eight-tool sketch in [PROTOCOL.md](PROTOCOL.md) §1 (decision D-29) — the
handshake tools collapsed into one message channel; the Phase 5 turn tools will
be added to the same surface.

Pinned dependency: **fastmcp 3.4.5** (API verified before implementation:
`FastMCP(name=)`, `@mcp.tool`, `run_async(transport="http", …)`,
`Client(url | FastMCP)`, `call_tool → CallToolResult.data`, `ToolError`).

## 4. Process model for one peer

One peer = **one OS process**, containing:

| Thread / task | Responsibility | Why separate |
|---|---|---|
| **asyncio event loop (main)** | FastMCP server + client, orchestrator, state machine, strategy, logging | The protocol is request/response over the network; asyncio keeps deadline tracking natural via `asyncio.wait_for` |
| **Tkinter main thread** | Live GUI render + turn banner | Tk is not thread-safe and insists on owning its own loop |
| **Watchdog task** | Heartbeat monitor; controlled shutdown + state persistence on freeze | E-7 requires it to survive a frozen main loop |

Practical arrangement: Tk owns the process main thread and the asyncio loop runs
in a worker thread, communicating with the GUI through a thread-safe queue
drained by `root.after()`. This is the smallest arrangement that keeps both
loops alive without a framework.

The watchdog is a task on the asyncio loop for the MVP; if the loop itself can
wedge, it is promoted to a separate thread. Deciding this needs measurement, not
speculation — recorded as an implementation note in [TASKS.md](../TASKS.md).

**Deadline tracker vs watchdog.** The deadline tracker guards *one request*
(`response_timeout_sec`); the watchdog guards *the whole process*
(`watchdog_timeout_sec`). A request whose deadline passed **is a failure**, not
an invitation to wait longer.

---

## 5. Two identical peers, different roles

The same package runs both sides. Nothing about the code is role-specific except
what the role legitimately changes.

```bash
python -m police_thief peer --role police
python -m police_thief peer --role thief
```

**What the role changes:**

| Aspect | Cop | Thief |
|---|---|---|
| Start cell | `cop_start` | `thief_start` |
| Barrier placement | Permitted, on a turn where movement is forgone, within one step; capped at `max_barriers` | Not permitted |
| Capture claim | Issues it | Must answer truthfully (E-21) |
| Belief target | Believes about the thief | Believes about the cop |
| Objective | Minimise Manhattan distance to belief peak | Maximise it / survive `survival_threshold` steps |
| Scoring | `capture_cop` / `survival_cop` | `capture_thief` / `survival_thief` |
| Brain class key | `[strategy] police_class` | `[strategy] thief_class` |

**What the role does NOT change:** the protocol, the state machine, the
commit-reveal sequence, the scent physics, the log format, the GUI structure,
the replay verifier, the reporting pipeline. All symmetric.

**Process and config isolation (E-1, E-2).** The two peers run as two entirely
separate OS processes under separate configuration directories
(`config/police/` vs `config/thief/`). Enforced structurally: no module holds
mutable cross-role state, no singleton is shared, and the role is passed
explicitly as a constructor argument rather than read from a global. The two
submitted repositories (E-49) reinforce this — each repo ships one role's config
tree.

---

## 6. Data flow for a single step

```
1. WAITING_FOR_OPPONENT   receive opponent's Commit (hash only)  ──► log
2. COMPUTING_MOVE         decode prior hint → belief update → choose legal move
                          → compose bluff text (template by default)
3. COMMITTING             draw nonce → canonical-serialise sealed record
                          → SHA-256 → send Commit                ──► log
                          GUI banner → LOCKED
4. AWAITING_REVEAL        exchange Acknowledge; then exchange Reveal
                          (move + hint; nonce STILL HIDDEN)      ──► log
5. VERIFYING              apply both moves under agreed physics; check capture;
                          emit scent for both; decay whole field once
                          (end of full turn)                     ──► log
                          GUI banner → YOUR TURN
   → back to 1, or terminal state
```

At end of match: Final Reveal of all nonces → mutual audit (E-36) → agree result
→ each side independently emails its own `[result_file]` (E-35).

**What the log must carry.** PDF p. 94 enumerates the log's mandatory contents:
commit-reveal commitments, moves, hints, **the LLM discussion fields**, the nonce
and the hash. The full record schema, and the argument that it is sufficient for
an independent third party to replay and verify the match from the file alone,
is in [PROTOCOL.md](PROTOCOL.md) §11.

Note one deliberate omission from that schema: **the scent field is never
stored**, only recomputed from the move sequence plus the config. Storing a
rendered global scent field in a file the live peer writes would put global
truth inside the live path, which is precisely what E-9 forbids. Recomputation
costs nothing and keeps the boundary intact.

---

## 7. Configuration and its hash

Two files per peer, per [PARAMETERS.md](PARAMETERS.md):

- `config/<role>/game.json` — the **shared signed constitution**. Loaded
  byte-identically on both sides. Its SHA-256 (`config_sha256`, the PDF's own
  field name) is exchanged before the match; **any mismatch means refusing to
  play** (E-11). It is **both hashed and cryptographically signed** — Appendix B
  requires the signature, Appendix F §2 requires the cryptographic lock.
- `config/<role>/game.toml` — **private, local, never on the wire, never
  signed**. Network port, opponent URL, strategy class, LLM mode, email target,
  group identity.

**On the paths.** Appendix B names these `config/game.json` and
`config/game.toml` with no role sub-directory (PDF pp. 126, 130); Chapter 2
(PDF p. 31) mandates separate config *directories* per role and offers
`/config/thief` vs `/config/police` as an example. The `config/<role>/` layout
above reconciles both and is our choice, not the PDF's wording — see
[DECISIONS.md](DECISIONS.md) D-18.

JSON values **override** TOML values for the same key, so the private file can
never weaken a signed condition. This is stated directly at PDF p. 132:
*"when `config/game.json` exists, the match-condition values in it override
every parallel key in the TOML — so the private file can never 'weaken' a signed
condition."*

**Field names are a closed schema.** Values may move by negotiation; **key names
are fixed and binding** (PDF p. 130). The loader rejects unknown or renamed
keys rather than ignoring them, since a silently-ignored key is how two peers
end up computing different physics while both believing they agreed.

### 7.1 The configuration boundary as implemented (Phase 0)

```
config/game.json  ──►  parse (duplicate-key hook)  ──►  validate  ──►  SharedConfig
      │                                                    │              (frozen)
      │                                                    ├─ 1 closed schema
      │                                                    ├─ 2 Appendix F policy
      └──►  canonical_json_bytes ──► SHA-256 ──►           └─ 3 cross-field
                                config_sha256

config/<role>/game.toml ──► parse ──► validate ──► PrivateConfig  (frozen)
                                          │
                                          └─ rejects any shared key (D-21)
                                    NOT an input to config_sha256
```

| Module | Responsibility |
|---|---|
| `config/policy.py` | The 32 Appendix F parameters as data. **The only module permitted to contain an Appendix F literal.** Self-checks at import. |
| `config/canonical.py` | The single canonical-JSON implementation. Every hash in the project — config, commit-reveal, log, artefacts — goes through it. |
| `config/hashing.py` | `config_sha256`. Hash only; signing waits on Q-12. |
| `config/loader.py` | Reading, duplicate-key detection, building frozen objects. |
| `config/validation.py` | The three validation layers. Derived rules marked `DERIVED` (D-22). |
| `config/models.py` | `SharedConfig` and `PrivateConfig` — separate, frozen, never merged. |
| `config/exceptions.py` | One distinct type per failure mode. |
| `config/verify.py` | CLI. Prints paths, never credential contents. |

Three properties this boundary is built to guarantee:

**Appendix F values exist in exactly one place.** Game logic reads a typed
object. `test_shipped_config_carries_every_binding_value` asserts the shipped
config matches the table; `test_exactly_32_binding_parameters` asserts the table
is complete. Neither can drift without failing.

**The two configurations never merge.** `SharedConfig` and `PrivateConfig` are
separate frozen dataclasses with no conversion between them, and a private file
naming a shared key is rejected outright rather than overridden (D-21).

**Frozen after validation.** A config that can be mutated after validation is a
config whose hash no longer describes it.

**Config loading is the one place numeric constants enter the system.** Game
logic reads from a typed config object; no numeric literal from the PDF appears
in game code. A validator rejects any config that lowers a `MINIMUM` or alters a
`FIXED` value.

---

## 8. Where the LLM may and may not appear

Permitted: composing the verbal hint; classifying the opponent's hint as
truthful or deceptive; behavioural profiling.

Forbidden by construction: validating moves, verifying hashes, determining the
winner, computing the belief update, choosing the move (default), or acting as
any source of truth.

Structurally, the LLM sits behind one interface (`strategy/verbal.py`) with two
methods — produce a hint, classify a hint — and is called by the strategy module
only. It receives no handle to the state machine, the crypto module, the log or
the scoring module. Default provider is `template`: **zero tokens**, no network,
deterministic. The whole series can be played at zero tokens.

---

## 9. Directory layout

```
police-thief-p2p/
├── README.md                  academic report (E-42, E-50; contents per Ch. 9)
├── PLAN.md                    work plan (E-50)
├── TODO.md                    task list (E-50)
├── TASKS.md                   phased breakdown
├── CLAUDE.md                  standing instructions for future sessions
├── .gitignore                 E-39, E-40
├── pyproject.toml
├── docs/
│   ├── REQUIREMENTS.md  PARAMETERS.md  ARCHITECTURE.md  PROTOCOL.md
│   ├── ACCEPTANCE_TESTS.md  OPEN_QUESTIONS.md  DECISIONS.md
│   ├── COMPLIANCE_AUDIT.md
│   └── prd/                   seven PRD files, one per stage (E-50)
├── config/
│   ├── police/game.json  police/game.toml
│   └── thief/game.json   thief/game.toml
├── matches/                   committed per-match artefacts (App. F §2)
│   └── <game_id>/             declaration / config / log / result JSON
├── src/police_thief/
│   ├── __main__.py            peer | replay entry points
│   ├── orchestrator.py        E-3 single gateway
│   ├── phases.py              E-4, E-5 state machine
│   ├── config/                loader + validator (MINIMUM/FIXED enforcement)
│   ├── domain/                state, scent, belief, rules, scoring
│   ├── crypto/                commit-reveal, canonical serialisation, step-0
│   ├── strategy/              BrainBase, heuristic brain, verbal layer
│   ├── net/                   FastMCP server + client, schemas
│   ├── audit/                 JSONL logger, mutual audit
│   ├── replay/                verifier (pure) + viewer (Tk)
│   ├── report/                artefact builder, gatekeeper, gmail
│   └── gui/                   live window
└── tests/                     pytest; one test per mandatory rule
```

---

## 10. Deliberate non-goals

Recorded so later sessions do not drift into them:

- No Docker, no database, no cloud infrastructure, no web frontend framework.
- No reinforcement learning until every mandatory requirement is complete and
  verified — and even then it is optional.
- No central referee, no shared game-state server, no shared module holding live
  state across roles.
- No abstraction introduced before a second concrete use for it exists.
