# Q-19 — `--gui` GUI lifecycle: root causes, fixes, and Windows proof

Full record of Q-19's investigation and resolution. Companion to
[q20_transport_proof.md](q20_transport_proof.md), which resolves the separate
transport stall Q-19 was originally assumed to share a cause with. Everything
below is observed evidence — real Windows runs, real code, real log files —
not a projection.

**Status: Q-19 RESOLVED.** See [../docs/OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md)
Q-19 and [../docs/DECISIONS.md](../docs/DECISIONS.md) D-44.

---

## 1. Original Q-19 symptom

Recorded in `docs/OPEN_QUESTIONS.md` (Phase 6): under `--gui`, Tk must own the
main thread, so the peer's asyncio loop runs in a worker thread. Past roughly
six commit-reveal turns, the FastMCP HTTP server stopped answering and a turn
failed on "opponent commitment never arrived." Headless runs were unaffected —
a 35-turn two-process game completed and audited cleanly without `--gui`.

## 2. Relationship to Q-20, and why that relationship was initially unproven

Q-19 was first recorded as sharing Q-20's cause. Q-20's proven root cause
(D-42) was stdout PIPE backpressure: a synchronous `print(..., flush=True)`
from inside the asyncio loop, undrained by the process launchers, filled the
OS pipe buffer and blocked the loop. That fix (event-sink echo off by default,
uvicorn `log_level="warning"`) is transport-generic — it says nothing about Tk
or the GUI thread specifically. `docs/OPEN_QUESTIONS.md`'s own Q-20 entry
records this precisely: *"the mechanism identified here is not GUI-specific,
so whether it also explains the `--gui` instability has not been
demonstrated. Q-19 remains open and untested against this fix."* Retesting
`--gui` against the Q-20 fix, rather than assuming it, was therefore the
starting point of this work — and it surfaced three further, GUI-specific
defects (§6, §8–10, §11–12 below) that Q-20's fix does not touch and could not
have fixed.

## 3. Windows Tcl/Tk environment issue and resolution

Tk is not thread-safe and must own the process's main thread. Two other
arrangements were tried and rejected, per `gui/live.py`'s module docstring and
`peer/run.py::_main_with_gui`'s docstring: driving Tk from a worker thread
**crashes the interpreter on Windows**, and pumping Tk's event loop from
inside the asyncio loop (`root.update()` called periodically from async code)
stalls a commit exchange long enough to miss its deadline and fail the turn.

**Resolution:** Tk owns the main thread; the peer's entire asyncio runtime
(`run_peer`) runs on a background `threading.Thread` (`_main_with_gui`'s
`worker()`). The two threads exchange only frozen, immutable `LiveView`
snapshots through `ViewSlot`, which is lock-free by construction because
`LiveView` is a frozen dataclass — publishing is a single reference swap, so
there is no shared mutable state to tear.

## 4. `--gui-delay` feature

`peer/run.py` adds `--gui-delay SECONDS` (`gui_delay_seconds()`, parsed and
range-checked at `argparse` time, before any peer, orchestrator or network
connection exists). Range: `[0, GUI_DELAY_MAX_SEC]` where
`GUI_DELAY_MAX_SEC = 10.0`; default `0` (no pause); ignored entirely without
`--gui`. Purpose: let a person watching the live window actually see each
turn resolve, rather than the board flickering through 35 turns in well under
a second.

## 5. Why the delay is outside protocol deadlines

`_maybe_gui_pause()` (`peer/run.py`) runs only under `--gui` with a positive
`--gui-delay`, and only strictly *between* turns — never after the last one.
By the time it runs, `orchestrator.play_turn(turn)` has already returned:
every commit, reveal, acknowledgement and deadline for that turn is settled.
The next turn's deadlines are relative (`asyncio.wait_for` started fresh
inside the next `play_turn` call), not anchored to match start, so idle time
here is invisible to the protocol. A watchdog heartbeat is called on both
sides of the sleep defensively, in case the watchdog loop is ever started in
the normal run path (it currently is not — see `Watchdog.start`).

## 6. Stale `YOUR TURN` / `GAME COMPLETE` root cause

`banner_for()` (`gui/live.py`) already checked `view.final_status` first and
correctly rendered `GAME COMPLETE` once it was set — the rendering logic was
never the bug. The bug was **when** `final_status` got set. It was previously
assigned only inside `run_peer`'s `finally` block, which does not execute
until the whole function is exiting — i.e., after Ctrl+C ends an `--hold`
wait, not when the protocol work that `--hold` is waiting after has actually
finished. A peer sitting in `--hold` kept publishing fresh `turn_complete`
snapshots every 0.2s (the background `run_gui` loop polls unconditionally)
whose `final_status` was still `None`. `banner_for` treats that phase as
"acting," so the window showed `YOUR TURN` for the entire time a person was
looking at a match that had already ended.

## 7. Final-status publication fix

`_mark_gui_finished()` (`peer/run.py`) sets `orchestrator.final_status` and
publishes exactly one fresh snapshot. It is called twice, both times
idempotently and safely: immediately after `_play_turns` returns
`EXIT_OK` — before `--hold`'s indefinite wait begins — and again in the
`finally` block, which covers the handshake/turn-failure paths (where the
first call site never runs) and the no-`--hold` path. The published view is
exactly `snapshot(orchestrator)`, the same function and the same information
boundary as every other frame; nothing about this call adds a new field or a
new source of truth.

## 8. Automatic PNG screenshot lifecycle

`gui/capture.py::should_capture(view, already_captured)` is a pure, Tk-free
trigger: `True` exactly once per match, the first time a *rendered* view
carries `final_status`. `drive_on_main_thread`'s `tick()` (`gui/live.py`)
calls it on every 120ms Tk poll, after `window.render(view)` has actually
drawn the frame — not merely after a snapshot was published to the
cross-thread slot, and not after `mainloop()` returns, by which point the
window may already be closed or destroyed. `capture_window()` then grabs the
window on that same thread.

## 9. Pillow dependency

`pyproject.toml`'s `[project.dependencies]` gained `"Pillow>=10.0"`,
floor-pinned (unlike `fastmcp`'s exact pin). `capture_window()` uses
`PIL.ImageGrab.grab()` over the window's actual screen rectangle (forcing a
`root.update()` repaint first, since a configured widget does not guarantee
its pixels have reached the screen). If Pillow is unavailable or the grab
fails for any reason, `_eps_fallback()` writes a PostScript dump of the
canvas alone — missing the status panel, not the requested format — and this
is always reported through `ScreenshotOutcome.degraded = True`, never
silently presented as equivalent to the PNG.

## 10. Ctrl+C / X-close lifecycle

Before this fix, neither trigger reached the worker thread's own shutdown
event at all: Ctrl+C raised an uncaught `KeyboardInterrupt` on the Tk thread,
and closing the window (`WM_DELETE_WINDOW` → `PeerWindow._on_close`) just
quit the Tk loop and left the asyncio worker sitting in `--hold` until
`_main_with_gui`'s 60-second `thread.join(timeout=60)` abandoned it.

**Fix:** `ViewSlot.bind_stop(loop, stop_event)` lets the worker register its
own event loop and `stop` event once, at startup. `ViewSlot.request_stop()`
is then callable safely from the Tk thread (window close, or a
`KeyboardInterrupt` caught around `mainloop()`) and asks the worker's loop to
set its `stop` event via `loop.call_soon_threadsafe(stop_event.set)` —
`asyncio.Event` is not itself thread-safe, so a direct cross-thread `.set()`
would race the loop's own waiter scheduling. A request arriving before
`bind_stop` has run is remembered (`_stop_pending`) and replayed once binding
catches up, so nothing is silently dropped during startup.

## 11. Benign Uvicorn lifespan `CancelledError` investigation

`PeerServer.stop()` must cancel the `asyncio.Task` wrapping
`mcp.run_async(...)`, because that call builds its own internal
`uvicorn.Server` and never exposes it — there is no reference to uvicorn's own
graceful `should_exit` flag. Cancelling mid-`main_loop()` skips uvicorn's own
`Server.shutdown()`, so uvicorn's internal lifespan task (spawned by its own,
likewise unexposed `LifespanOn.startup()`) is orphaned, parked waiting for a
"lifespan.shutdown" ASGI message that will now never arrive. It sits pending —
not yet an error — until `asyncio.run()`'s own end-of-program task sweep
cancels it, which happens *after* `run_peer` has already returned and printed
"shutdown finished."

Two hypotheses were tested for what logs the resulting traceback:

- **Shape A (first, disproven hypothesis).** `uvicorn.lifespan.on.LifespanOn.main()`'s
  own `except BaseException as exc: self.logger.error(msg, exc_info=exc)`, a
  fixed message prefix with the exception passed via `exc_info`. A filter
  built against this shape was shipped, then **proven wrong on a real Windows
  run** (`game_id` `q19-shutdown-proof-10-02`): the traceback still appeared.
- **Shape B (confirmed, by instrumenting a real `PeerServer.start()` →
  `stop()` cycle against the exact installed `fastmcp`/`uvicorn`/`starlette`
  versions).** Starlette's own `Router.lifespan()` catches the cancellation
  itself — one level inside uvicorn's `LifespanOn.main()`, not at it — formats
  it with `traceback.format_exc()`, and reports it through the ASGI protocol
  as `{"type": "lifespan.shutdown.failed", "message": <formatted text>}`.
  `LifespanOn.send()` handles that message type with
  `self.logger.error(message["message"])` — a bare string, with `exc_info`
  left `None`. The record's message is the full rendered traceback text, and
  the exception is not attached structurally at all.

## 12. Exact final logging fix

`peer/server.py`'s `_QuietExpectedLifespanCancellation` (a `logging.Filter`)
is installed once per process on the `"uvicorn.error"` logger
(`_install_lifespan_cancellation_filter()`, called from
`PeerServer.__post_init__`, idempotent — checked against `logger.filters`
before adding). It matches **both** shapes:

- Shape A: message starts with `"Exception in 'lifespan' protocol"` **and**
  `record.exc_info`'s exception is exactly `asyncio.CancelledError`.
- Shape B: the message's own **last line** starts with one of
  `"asyncio.exceptions.CancelledError"`, `"asyncio.CancelledError"`, or
  `"concurrent.futures.CancelledError"`, **and** the message text contains
  both of the frame-name substrings `"in lifespan"` and `"in receive"` —
  which identify this exact call chain, unlike `File "..."` path components,
  which are not stable across installs.

A genuine bug during shutdown (a `TypeError`, a broken ASGI lifespan hook, an
unrelated `CancelledError` from somewhere else entirely) matches neither
shape and passes through unfiltered, on this logger or any other. Installing
the filter before or after uvicorn's own `Config.configure_logging()` makes
no difference — confirmed empirically: that call rebuilds *handlers* via
`logging.config.dictConfig` for loggers whose dict entry names new ones, and
never touches a logger's `.filters` list.

## 13. 10-turn Windows verification

`game_id` `q19-shutdown-proof-10-02` is the run that **disproved** the first
(Shape-A-only) filter: the traceback still appeared on a real Windows 10-turn
run, which is exactly what drove the Shape-B investigation in §11–12. No
separate 10-turn re-run of the corrected filter was requested or performed —
the subsequent 35-turn run (§14) supersedes it as the verification of the
corrected fix, since it exercises the identical shutdown path at greater
length.

## 14. 35-turn Windows verification

`game_id` `q19-final-proof-35-01`, real Windows run, reported observed
results:

- Two real Tk peer processes.
- `--gui-delay 1` visibly showed turn-by-turn movement.
- `GAME COMPLETE` displayed correctly (§6–7 fix).
- Automatic full-window PNG screenshots succeeded:
  `results/screenshots/q19_cop_final_35.png`,
  `results/screenshots/q19_thief_final_35.png` (§8–9 fix).
- Both peers completed their configured protocol run (35 turns).
- Clean GUI shutdown (§10 fix): no uncaught `KeyboardInterrupt`, no abandoned
  worker thread.
- **No Uvicorn/Starlette `CancelledError` traceback** (§11–12 fix).
- Windows full suite: **1563 passed, 1 skipped, 0 failed.**

## 15. Final Reveal evidence

Reported from the same run: Final Reveal verified all 35 turns on both sides.

## 16. Mutual audit evidence

Reported from the same run: mutual audit verified both directions (E-36).

## 17. Audit-chain evidence

Reported from the same run: both local audit chains report `Verified OK
(179 records)` — the same hash-chained, tamper-evident mechanism documented
in D-37, independently reproducible with `verify_chain_file`.

## 18. Replay result

Independently re-run in this investigation, directly against the actual
`replay_files()` function and the real
`logs/audit_police_q19-final-proof-35-01.jsonl` /
`logs/audit_thief_q19-final-proof-35-01.jsonl`:

```
VERDICT: VERIFIED OK
DESCRIBE: VERIFIED OK — capture (thief_has_no_legal_move) on turn 30; winner police; cop 20, thief 5
turns_verified: 30
```

Turn 30 detail: cop `(5,5)`, thief `(6,6)`, barriers `{(5,6), (6,5)}`, cop
action `BARRIER:6,5`, thief action `MOVE:N`, note `blocked_move_becomes_stay`.
The thief's cell `(6,6)` is a board corner with exactly two in-bounds
neighbours, `(5,6)` and `(6,5)`; both are barriers as of turn 30, so
`legal_relocations` is empty and E-47 (`thief_has_no_legal_move`) fires. Full
turn-by-turn trace, including the separate Q-18 `blocked_move_becomes_stay`
resolution on turns 29 and 30, is preserved in this session's investigation
record.

## 19. Why live 35 turns vs. replay terminal turn 30 is expected under D-41

This is **not** a new Q-19 defect. It is `docs/DECISIONS.md` D-41's
architecture working exactly as designed, now demonstrated end to end on a
real two-process Windows run:

> "A live peer cannot adjudicate — it never sees its opponent's position — so
> it plays to the turn limit and the replay decides where the game actually
> ended. Confirmed in a real run: both peers played 35 turns; the replay
> found the capture at turn 30."

That sentence already describes this exact scenario, and it was written
before this run occurred. `TASKS.md`'s own Phase 6 completion note
independently records the identical pattern from an earlier demonstration:
*"Real 35-turn two-process game replays VERIFIED OK, reconstructing a capture
at turn 30 (cop 20, thief 5)."* The README's own worked example of the replay
viewer (`## Replay verification`) shows this same turn-30 capture as its
illustration.

**Mechanism, confirmed by direct code inspection.** `peer/run.py::_play_turns`
(line 408: `for turn in range(1, args.turns + 1): opponent_action = await
orchestrator.play_turn(turn)`) contains no domain capture/terminal check, and
structurally cannot: E-46 (barrier-on-thief) and E-47 (thief has no legal
move) both require knowledge a live peer does not have or should not compute
alone under E-8/E-9 — E-46 needs the *opponent's* cell, which `LocalState` has
no attribute for by design (D-9); E-47 needs the thief's own state and is, per
`domain/capture.py`'s own docstring, *"the one capture condition a live peer
could in principle evaluate for itself"* — but nothing in the current
implementation actually wires that self-check into a live stop (see the
capture-claim gap, §20 below). `replay/verifier.py::_reconstruct`, by
contrast, runs offline after the match with both sealed logs available,
evaluates `evaluate_full_turn_capture` after every turn, and `break`s the
instant a verdict is returned — which is why it stops examining the log at
turn 30 while the live processes correctly ran to their configured
`--turns 35`.

## 20. Final Windows pytest result

**1563 passed, 1 skipped, 0 failed** (`game_id` `q19-final-proof-35-01` run).

## 21. Screenshot paths

- `results/screenshots/q19_cop_final_35.png`
- `results/screenshots/q19_thief_final_35.png`

## 22. Information-boundary statement

The live GUI never receives, holds, or can display the opponent's true
position. `gui/view_model.py`'s `LiveView` has no field for it (D-9); the
window is constructed with handles to the local-truth and belief modules
only. The legend drawn in every live window states this in the interface
itself: *"The opponent's true position is not shown, and is not available to
show."* None of the Q-19 fixes in this document touched `LocalState`,
`LiveView`'s field set, or what data crosses the `ViewSlot` boundary — the
structural guarantee (E-8, E-9) is untouched and unaffected by this work.

---

## Separately confirmed: `capture_claim` (E-21/E-22) is unimplemented

Not a Q-19 finding, and not fixed here. Investigating §19 surfaced a genuine,
pre-existing compliance gap: `docs/PROTOCOL.md` §6.5 documents a
`capture_claim` protocol message (E-21/E-22, PDF p. 149-ish) — the cop
declares a suspected capture, the thief is cryptographically obligated to
answer truthfully — as the PDF's own designed mechanism for a live mid-match
stop. A full grep of `src/` found **zero** occurrences of `capture_claim` or
`CAPTURE_CLAIM`: no `MessageType.CAPTURE_CLAIM`, no handler, nothing wired
into `_play_turns`. `docs/COMPLIANCE_AUDIT.md` nonetheless marks E-21 and E-22
`COVERED`. See `docs/COMPLIANCE_AUDIT.md` Part 9 and
`docs/OPEN_QUESTIONS.md`/`todo.md` for the tracked follow-up. **Not
implemented in this phase**, per explicit instruction.
