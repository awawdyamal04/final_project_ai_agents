# Q-20 — two-process HTTP transport stall: proof of resolution

Observed evidence only. Nothing here is estimated or reconstructed; every figure
below came from a command that was run or from a log file that run produced.
Raw logs are **not** reproduced here — `logs/` is gitignored, and the audit
chains contain nonces disclosed at the final reveal.

Related records: [docs/OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md) Q-20 ·
[docs/DECISIONS.md](../docs/DECISIONS.md) D-42 ·
[docs/ACCEPTANCE_TESTS.md](../docs/ACCEPTANCE_TESTS.md) §13.

---

## 1. Root cause

**Stdout PIPE backpressure blocking the asyncio event loop.** Not a FastMCP
defect, and not the session accumulation previously suspected.

The peer runtime built its operational event sink as `JsonEventSink(echo=True)`,
so every event was also written to stdout by a synchronous
`print(..., flush=True)` — called from inside the turn coroutines, on the same
event loop that runs the FastMCP server. Uvicorn added one INFO line per HTTP
request to the same stream. Both subprocess launchers captured that stdout with
`stdout=subprocess.PIPE` and did not drain it while the game ran.

An OS pipe buffer is finite. Once full, the next `print` blocks, and blocking
there parks the whole loop. The process therefore stayed alive and never
crashed, while its server could neither accept nor answer connections. The
opposite peer saw `RuntimeError: Client failed to connect: All connection
attempts failed` and reported the turn failed on a deadline. The diagnostic
measured roughly 40 seconds of event-loop lag at the freeze.

This accounts for every recorded symptom at once: independence from client
design (five topologies were tried, all failed), the repeatable landing near
turn 6 (the same volume of output fills the same buffer), and the fact that the
identical turn sequence ran to 35 turns in-process, where no pipe exists.

---

## 2. Production changes

| File | Change |
|---|---|
| `src/police_thief/peer/run.py` | Event sink constructed with `echo=args.verbose` instead of `echo=True` — quiet by default. |
| `src/police_thief/peer/run.py` | New `--verbose` CLI flag (`store_true`) to opt back into live stdout echo. |
| `src/police_thief/peer/server.py` | `PeerServer.log_level` field defaulting to `"warning"`, passed to uvicorn — removes the per-request INFO flood, keeps warnings and errors. |
| `src/police_thief/peer/server.py` | `stateless_http=True` and `json_response=True` passed to the FastMCP HTTP app. |

Two things deliberately **unchanged**:

- **JSONL operational logging and the hash-chained audit log are untouched.**
  Nothing was removed from either; only the stdout copy was turned off. The
  files remain the authoritative record.
- `stateless_http` / `json_response` are kept as transport simplifications. They
  were introduced while the session-accumulation hypothesis was still live, and
  they are safe, but the stall survived them — they are not the fix.

Rejected alternatives and why, in full: [docs/DECISIONS.md](../docs/DECISIONS.md)
D-42 (a dedicated server thread; raising retries and timeouts).

---

## 3. Focused regression results

```
python -m pytest tests/peer/test_http_stress.py tests/peer/test_stdout_backpressure.py -q
2 passed in 49.43s
```

Both speak real HTTP over a real localhost socket, unlike the rest of the peer
suite.

**`tests/peer/test_http_stress.py`** —
`test_stateless_server_survives_repeated_real_http_reconnects`. A live
`PeerServer` on an ephemeral port takes 45 real HTTP sessions: 8 reopen cycles
of 5 sequential calls, a 4-way concurrent burst, then one final fresh
connection that must still be accepted.

**`tests/peer/test_stdout_backpressure.py`** —
`test_q20_undrained_stdout_pipe_does_not_freeze_two_peers`. Two real peer
subprocesses play 12 turns with `stdout=subprocess.PIPE` **never drained during
the run**, which is exactly the condition that froze the loop. Asserted: both
exit 0; each undrained pipe holds under 16 KiB for the whole game; the
operational JSONL still records `ready`, `opponent_commit` and `opponent_reveal`
in both directions; both audit JSONL files are non-empty; play reaches turn ≥ 10
with no `send_unacknowledged`.

Neither test tries to make the *old* server fail — that failure was
timing-dependent and a test built on it would be flaky. Both are
one-directional: the fixed runtime must survive the churn.

---

## 4. Full suite

```
python -m pytest -q
1467 passed, 3 skipped in 74.88s
```

**1467 passed, 3 skipped, 0 failed.**

---

## 5. The real match

### Configuration

| | |
|---|---|
| `game_id` | `real-game-001` |
| Sub-game | 1 |
| Transport | real loopback FastMCP HTTP — cop `http://127.0.0.1:8801/mcp`, thief `http://127.0.0.1:8802/mcp` |
| Processes | two independent OS processes, one per role |
| Shared config | `config/game.json`, `config_sha256` `410066bfe426b268092f69b07e95e2bab4fa8826dd5b1b8643cbbf6befd0a24d` (agreed by both peers at handshake) |
| Grid | 7×7 |
| Start cells | cop `[0, 0]`, thief `[3, 3]` |
| Simultaneity policy | capture `post_move_positions_only`; blocked move `blocked_move_becomes_stay` |
| Turn limit requested | 35 |
| Run timestamps (from the audit chains) | 2026-07-30T20:46:49Z → 2026-07-30T20:48:22Z UTC |

The blocked-move policy is the unresolved Q-18 reading applied so a
demonstration terminates; it is not a ruling.

### Play

- **35 turns completed.** Both peers logged 35 `turn_applied` records and a
  `sub_game_end` carrying `turns_played: 35`.
- **Both processes exited 0.**
- **No `PeerTimeoutError`** and **no `send_unacknowledged`** in either
  operational log.
- **No in-play connection-refused channel restart.** Closing
  `transport_diagnostics`, cop side: primary channel 71 calls / 0 failures /
  0 restarts; control channel 4 calls / 0 failures / 0 restarts.
- 18 `retry` events on the cop side, all `RateLimitExceededError` from the
  peer's own token-bucket gatekeeper (E-28) and all resolved on the retry.
  These are the local rate limiter doing its job, not transport failures.

### Final reveal, mutual audit, chains

- **Final reveal verified all 35 turns** — each peer's `audit_result` record
  reads `{"result": "verified", "turns": 35}`.
- **Mutual audit verified both directions.**
- **Both audit chains verify independently**, recomputed after the run:

```
python -c "from police_thief.audit.verifier import verify_chain_file; \
  print(verify_chain_file('logs/audit_police_real-game-001.jsonl').describe())"
```

| Log | Result |
|---|---|
| `audit_police_real-game-001.jsonl` | `Verified OK (179 records)` |
| `audit_thief_real-game-001.jsonl` | `Verified OK (179 records)` |

179 records each = 1 `sub_game_start` + 35 × (`local_commit`,
`opponent_commit`, `local_reveal`, `opponent_reveal`, `turn_applied`) +
`final_reveal` + `audit_result` + `sub_game_end`.

### Independent offline replay

```
python -m police_thief.replay.viewer \
  --cop logs/audit_police_real-game-001.jsonl \
  --thief logs/audit_thief_real-game-001.jsonl
```

```
  result        survival on turn 35
  winner        thief
  score         cop 5, thief 10
  verification  VERIFIED OK
```

The replay trusts neither peer: it re-verifies both chains, re-hashes every
commitment against the revealed nonces in both directions, re-applies the
physics and recomputes the outcome (D-41). Both peers claimed nothing, and the
replay's independently derived result is the one recorded above.

### Result

**Survival on turn 35. Winner: thief. Score: cop 5, thief 10.**

---

## 6. Remaining open work — all unrelated to Q-20

This proves the transport and one complete local match. It proves nothing about
the following, none of which has been done:

- **Q-19 — long `--gui` runs destabilise the FastMCP server.** Still open. It
  was previously assumed to share a cause with Q-20; that link is now
  **unproven**, and Q-19 has not been retested against this fix.
- **Q-12 — the step-zero signing key.** Still ESCALATE; must be asked of the
  lecturer before the first counting match. No key scheme has been invented.
- **Q-18 — a barrier landing on the cell the opponent already chose.** Still
  NEGOTIATE. The policy used in this run is a harness choice, not a ruling.
- **Phase 8 — public exposure.** No tunnel, no off-host match. This match ran
  entirely on loopback.
- **Phase 9 — reporting.** No Gmail integration, no match artefacts under
  `matches/`, no report sent.
- **Phase 10 — league play.** No counting matches against any other group.
- **Phase 11 — submission.** No repository split, no `v1.0-submission` tag.
- The natural-language hint layer's LLM modes remain deferred; the default
  zero-token template provider is what played this match.
