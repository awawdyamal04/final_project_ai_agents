# Distributed Cops-and-Robbers over a Peer-to-Peer Network

Academic final project — *Orchestration of AI Agents*, Department of Computer
Science, University of Haifa, 2026.

Two autonomous, **symmetric** agents — a cop and a thief — race on a discrete
grid with **no central referee and no shared game-state server**. Neither agent
can see the other's true position. Each builds a probabilistic belief about its
opponent from two sources: a decaying scent trail that cannot be forged, and a
verbal hint that may well be a lie. Integrity between two mutually distrustful
peers is guaranteed not by trust but by mathematics — commit-reveal over
SHA-256, audited after the fact.

> **Status — implemented and tested:** configuration, game domain, FastMCP
> transport, cryptography (commit-reveal + hash-chained audit), strategy
> (Bayesian belief + heuristics), scent/belief maps, the Live GUI, and the
> offline replay verifier. The full suite is **1467 passed, 3 skipped,
> 0 failed**. Two independent peer processes handshake over FastMCP, verify
> identical configuration hashes, and play **cryptographically committed
> turns**: neither sees the other's action before committing, neither can change
> it afterwards, and every event is written to a hash-chained tamper-evident log
> that an independent verifier checks. A **complete 35-turn match between two
> real processes over real HTTP** is now demonstrated end to end —
> **Q-20 is resolved** (see below).
>
> **Not yet proven / not done:** **Q-19** (long `--gui` runs destabilise the
> server) remains an open known limitation, untested against the Q-20 fix.
> Public-internet tunnelling, Gmail reporting, league matches against other
> groups, and the submission split are **future phases, not started**. **Q-12**
> (the step-zero signing key) still needs the lecturer, and **Q-18** still needs
> negotiation. See [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) and
> [TASKS.md](TASKS.md).

---

## Authoritative source

`police_thief_p2p.pdf` (book version 3.0.0, Dr. Yoram Segal) is the sole
specification. Everything in `docs/` is an extraction from it, with page
references throughout.

Two conventions worth knowing before reading the PDF yourself:

- **`PDF page = book page + 16`.** The printed page numbers in the footer and
  your PDF viewer's page counter differ by a constant 16. All references in this
  repository use the **viewer's** number.
- **The default is not binding.** PDF p. 4 states the founding principle: a rule
  is not binding unless it is explicitly written as a rule. Every illustration,
  diagram, code excerpt and scenario in the book is a mode of demonstration, not
  a requirement.

The single source of truth for every quantitative value is the **Mandatory
Parameter Table in Appendix F** (PDF pp. 151–159). Numeric values never appear
as hard numbers in the book's body text — only as code-names in square brackets
such as `[grid_size]`.

---

## Documentation

Read in this order.

| Document | What it holds |
|---|---|
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | All 55 Appendix E rules plus chapter obligations, organised by subsystem, classified MANDATORY / RECOMMENDED / EXAMPLE, with PDF pages and the stated sanction for each |
| [docs/PARAMETERS.md](docs/PARAMETERS.md) | Every Appendix F parameter — name, value, type, meaning, status, and which config file owns it |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Minimum architecture, layer separation, process model for one peer, how two identical peers take different roles |
| [docs/PROTOCOL.md](docs/PROTOCOL.md) | The eight-tool FastMCP interface, message schemas, config-hash exchange, turn ordering, commit-reveal sequencing, timeout/duplicate/invalid-sequence behaviour, completion signalling |
| [docs/ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) | Every mandatory rule mapped to an executable test or a deterministic manual procedure |
| [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) | Contradictions and ambiguities found in the PDF, with status and resolution |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decisions taken, with reasoning, cost and reversal conditions |
| [docs/COMPLIANCE_AUDIT.md](docs/COMPLIANCE_AUDIT.md) | Per-requirement COVERED / MISSING / AMBIGUOUS / NOT APPLICABLE status |
| [prd.md](prd.md) | Product requirements — **what** the system must do: goal, problem, Dec-POMDP, scent/belief/commit-reveal methods, constraints, success criteria, deliverables, open questions |
| [plan.md](plan.md) | Work plan — **how** it is built, in verified vertical slices |
| [todo.md](todo.md) | Live task checklist |
| [TASKS.md](TASKS.md) | Dependency-ordered phases; mandatory work separated from optional enhancements |
| [results/README.md](results/README.md) | Observed artefacts: screenshots, replay reports, benchmarks, plots |
| [CLAUDE.md](CLAUDE.md) | Standing instructions for future development sessions |

---

## The shape of the system

```
        PEER A (cop)                                  PEER B (thief)
   ┌───────────────────┐                        ┌───────────────────┐
   │   Orchestrator    │                        │   Orchestrator    │
   │  (single gateway) │                        │  (single gateway) │
   ├───────────────────┤                        ├───────────────────┤
   │ state machine     │                        │ state machine     │
   │ strategy (Python) │                        │ strategy (Python) │
   │ local truth only  │                        │ local truth only  │
   │ belief map        │                        │ belief map        │
   │ JSONL audit log   │                        │ JSONL audit log   │
   ├───────────────────┤                        ├───────────────────┤
   │ FastMCP  server   │◄──── public internet ─►│ FastMCP  server   │
   │          client   │      (NAT traversal    │          client   │
   └─────────┬─────────┘       via tunnel)      └─────────┬─────────┘
             │                                            │
        Live GUI                                     Live GUI
     (belief heatmap,                             (belief heatmap,
      turn banner —                                turn banner —
      never the truth)                             never the truth)

                    ── after the match only ──
                     ┌────────────────────┐
                     │  Replay verifier   │   the only omniscient
                     │  Verified OK /     │   component; runs offline
                     │  TAMPERED          │   over the sealed logs
                     └────────────────────┘
```

Every peer is **simultaneously a server and a client**. There is no strong side
and no weak side. The same program runs both roles; the role changes only the
start cell, whether barrier placement is permitted, which side of the belief the
agent models, and how it scores.

---

## Design commitments

Five properties the implementation is built to guarantee structurally rather
than by convention:

**The live agent is blind.** The live-state object has no attribute for the
opponent's position — not `None`, not `Optional`. A leak surfaces as an
`AttributeError` in a unit test rather than as a subtle bug that survives to the
league. Only the replay verifier, running after the match over the sealed logs,
ever reconstructs the full global state.

**Moves are decided in Python, always.** The language model touches only the
verbal layer: composing a hint, and classifying an opponent's hint as truthful
or deceptive. It never validates a move, verifies a hash, or determines a
winner. The default verbal provider is a zero-token template, so the entire
series can be played with no model at all and the competition rests on the
movement algorithm.

**Numbers live in configuration.** No value from Appendix F appears as a literal
in game logic. A validator rejects any configuration that lowers a `MINIMUM`
value or alters a `FIXED` one, and both peers exchange a canonical hash of the
shared config before play — a mismatch means refusing to play, not playing
badly.

**Commitments bind.** Each step is sealed as a canonical JSON record hashed with
SHA-256 before anything is revealed; the nonce stays secret until the end of the
match. A single altered character anywhere in a log is caught at audit, and the
match is void.

**Everything mandatory is verifiable.** Each of the 55 rules maps to a pytest
test or a deterministic manual procedure, named by rule ID so coverage can be
checked by grep.

---

## Technology

Python 3.12 · FastMCP · asyncio · pytest · SHA-256 · JSON Lines audit logs ·
JSON (shared signed config) + TOML (private per-peer config) · Tkinter for the
live GUI and replay viewer · Gmail API with `gmail.send` scope only, added last.

Deliberately absent: Docker, databases, cloud infrastructure, web frameworks,
paid LLM APIs, and reinforcement learning. The specification is explicit that
the course did not teach RL and that a fully strong agent can be built from
heuristics alone; it is one optional tool among three equal-standing routes, and
out of scope until every mandatory requirement is complete and verified.

---

## Installation

Python 3.12. The one runtime dependency is `fastmcp` (pinned `3.4.5`); dev
extras are `pytest` and `pytest-asyncio`. Versions are declared once in
`pyproject.toml`; `requirements.txt` installs the same set via an editable
install.

```bash
python -m pip install -e ".[dev]"      # or: python -m pip install -r requirements.txt
```

## Verifying a configuration

The shared constitution and a private per-peer file are validated by a single
command. It prints the configuration hash both peers must agree on, and exits
non-zero if anything is wrong.

```bash
python -m police_thief.config.verify --shared config/game.json --private config/cop.toml.example
```

```
VALID    shared configuration
  file                 config/game.json
  schema_version       1.2
  agreed_between       group-a, group-b
  board                7x7
  sub-games per match  6
  binding parameters   32 validated (14 fixed, 9 minimum, 9 negotiable)
  config_sha256        410066bfe426b268092f69b07e95e2bab4fa8826dd5b1b8643cbbf6befd0a24d
VALID    private configuration
  file                 config/cop.toml.example
  role                 police
  ...
  private config does not affect config_sha256
```

Before a match, compare digests with the opponent. A mismatch means refusing to
play — not playing badly:

```bash
python -m police_thief.config.verify --shared config/game.json --expect-hash <their-digest>
```

To set up a peer, copy the template for its role and edit it:

```bash
mkdir -p config/police && cp config/cop.toml.example config/police/game.toml
```

The private file never crosses the network, is never signed, and is **not** an
input to `config_sha256`. It may not define any key owned by the shared
constitution — the loader rejects that outright rather than silently overriding
it.

## Tests

```bash
python -m pytest
```

## Running a headless sub-game

Phase 1 implements the game domain: board, movement, barriers, capture, terminal
conditions and scoring. It runs in one process with trivial deterministic
policies — test infrastructure, not the distributed game.

```bash
python -m police_thief.sim.headless --shared config/game.json --show-turns 5
```

```
headless sub-game (single process, test harness)
  board                7x7
  cop start            [0, 0]
  thief start          [3, 3]
  survival threshold   35
  move ceiling         35
  barrier quota        14
  simultaneity policy  post_move_positions_only (not PDF-resolved)
  result               survival on turn 35; winner thief; cop 5, thief 10
  turns played         35
  (no opponent position in either peer's state)
```

The harness holds both positions in order to adjudicate captures. That is a
property of the *test driver*, not of the game: in the delivered system the same
job is split between the capture-claim protocol and the post-match replay
verifier, and no live component ever sees both sides. Neither peer's
`LocalState` has a field for the opponent's position — see
[the state model](docs/ARCHITECTURE.md#311-the-state-model-why-localstate-cannot-represent-global-truth).

## Running two peers

Phase 2 implements the transport: each peer is an independent process running
its own FastMCP server *and* client, and the two talk directly to each other —
no central referee, no shared state. Terminal 1:

```bash
python -m police_thief.peer.run --shared config/game.json --private config/cop.toml.example --game-id local-dev
```

Terminal 2:

```bash
python -m police_thief.peer.run --shared config/game.json --private config/thief.toml.example --game-id local-dev
```

Either may start first; each polls for the other. They exchange hello and
capabilities, compare `config_sha256`, and both reach `READY`:

```
peer police
  config_sha256  410066bf…fd0a24d
  handshake      OK
  state          ready
```

If the hashes differ, **both sides refuse to play** and exit non-zero — a
mismatched constitution means the two peers would be running different physics
(E-11). Turn play arrives with commit-reveal in Phase 5.

## Playing cryptographic turns

Add `--turns N` to play N commit-reveal turns after the handshake, then
exchange final reveals and audit each other:

```bash
python -m police_thief.peer.run --shared config/game.json --private config/cop.toml.example --game-id demo --turns 2
```

```
  turn 1         commit 37c836fcbb4033a6… | opponent revealed MOVE:STAY
  turn 2         commit 81d9a3dfeb3db685… | opponent revealed MOVE:STAY
  final reveal   opponent verified 2 turn(s)
  mutual audit   both directions verified
  audit chain    Verified OK (12 records)
```

The commit carries **only** a SHA-256 digest — no action, no target, no nonce.
The reveal carries the action and hint but still **not** the nonce, which stays
secret until the end of the match, exactly as the specification requires. That
is why tampering is caught at the final audit rather than mid-turn.

To see the detection work, corrupt your own record after committing:

```bash
python -m police_thief.peer.run --shared config/game.json --private config/cop.toml.example --game-id t --turns 1 --tamper action
```

The opponent rejects the final reveal with `CommitmentMismatchError` and both
peers exit non-zero.

Audit logs are written to `logs/audit_<role>_<game-id>.jsonl` and can be
verified independently at any time:

```bash
python -c "from police_thief.audit.verifier import verify_chain_file; print(verify_chain_file('logs/audit_police_demo.jsonl').describe())"
```

One-command handshake demonstration (launches both processes, then gets out of
the way):

```bash
python scripts/run_two_peers.py
```

```bash
python scripts/run_two_peers.py --stagger 5   # thief starts 5s late
```

Operational events go to `logs/peer_<role>_<game-id>.jsonl` — telemetry only,
not the cryptographic match log, and it structurally refuses to record secrets
or any opponent position.

**The runtime is quiet on stdout by default.** Add `--verbose` to echo every
operational event live:

```bash
python -m police_thief.peer.run --shared config/game.json --private config/cop.toml.example --game-id demo --turns 5 --verbose
```

The JSONL logs are written either way and are the authoritative record —
`--verbose` adds a console copy, it does not enable logging. The default is off
because echoing every event with a synchronous `print` from inside the asyncio
loop is what caused Q-20: a launcher that captures stdout without draining it
fills the pipe buffer, the next `print` blocks the loop, and the peer's server
stops answering while the process stays alive. Use `--verbose` when you are
watching a terminal, not when a script is capturing the output (D-42).

## Verified Q-20 result

Q-20 — the two-process transport stall that repeatably froze the game around
turn 6 — is **resolved**. The cause was ours, not FastMCP's: stdout PIPE
backpressure blocking the event loop, as described above. Observed evidence from
the proving run (`game_id` `real-game-001`, two OS processes over real loopback
FastMCP HTTP, `127.0.0.1:8801` ↔ `127.0.0.1:8802`):

| | |
|---|---|
| Match length | **35 turns completed** |
| Process exit codes | **0 and 0** |
| Transport health | no `PeerTimeoutError`, no `send_unacknowledged`, no connection-refused channel restart |
| Final reveal | all 35 turns verified |
| Mutual audit | both directions verified |
| Audit chains | `Verified OK` — 179 records each |
| Independent offline replay | **`VERIFIED OK`** |
| Result | survival on turn 35; winner **thief**; cop 5, thief 10 |

Two regression tests guard it, both over real sockets:
`tests/peer/test_http_stress.py` (repeated real HTTP session reopens) and
`tests/peer/test_stdout_backpressure.py` (two real peer subprocesses played
through deliberately **undrained** stdout pipes). Full record in
[results/q20_transport_proof.md](results/q20_transport_proof.md); the decision
and the rejected alternatives are in [docs/DECISIONS.md](docs/DECISIONS.md)
D-42.

This proves the transport and a complete local match. It does **not** touch
Q-19, public-internet tunnelling, Gmail reporting or league play, all of which
remain outstanding.

## Replay verification

Reconstruct a finished sub-game from **both** peers' audit logs and decide it
independently — trusting neither peer's claimed result:

```bash
python -m police_thief.replay.viewer --cop logs/audit_police_full.jsonl --thief logs/audit_thief_full.jsonl
```

```
  turn 30
    0 1 2 3 4 5 6
  5 . . . . . C #
  6 . . . . . # T
  result        capture (thief_has_no_legal_move) on turn 30
  winner        police
  score         cop 20, thief 5
  verification  VERIFIED OK
```

Verdicts are `VERIFIED OK`, `TAMPERED`, `INCOMPLETE` or `POLICY MISMATCH`. The
viewer may show both positions because it runs offline, after the final reveal,
once the nonces are public; no live component imports it.

The two peers **must** run as two entirely separate processes under separate
configuration directories. Sharing memory or variables between them breaks the
zero-trust model and disqualifies the solution even if the game works
technically.

---

## Note on this README

At submission time this file becomes the **academic report** and must carry six
mandatory components: the chosen Dec-POMDP model, the FastMCP orchestration
dilemmas, the strategies implemented, learning curves (only if RL was used),
screenshots of the live belief map and of the replay viewer showing
`Verified OK`, and a link to the companion repository. It must also document
every contradiction identified in the specification along with the reading
chosen and the reason — the specification grants that freedom explicitly,
provided the choice is stated.

The checklist lives in [docs/ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) §7;
the contradictions are already catalogued in
[docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md).
