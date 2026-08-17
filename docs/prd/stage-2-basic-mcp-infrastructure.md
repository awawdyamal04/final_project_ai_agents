# Stage 2 — Basic MCP Infrastructure

*PDF Ch. 2; stage table PDF pp. 101–103. Corresponds to [TASKS.md](../../TASKS.md) Phase 2.*

## What

Split the single process into two real OS processes, each running its own
FastMCP server, exchanging **pure geometric** information over localhost —
numeric coordinates only, no natural language and no cryptography yet.
Handshake, identity checks, a state machine, and admission control (gatekeeper,
rate limiting, deadlines, watchdog) all belong here, because they are transport
concerns, not game-rule concerns.

## Why

This is where "no central referee" stops being a design intent and becomes an
enforced fact: `PeerOrchestrator` is the single gateway per process (E-3), and
there is no shared module holding state for both roles (E-1, E-2). Proving the
transport here, over localhost, before Stage 5 moves it to the public internet
and before Stage 6 wraps it in cryptography, isolates transport bugs from
crypto bugs and network-latency bugs — exactly the ordering rationale
`TASKS.md` cites for keeping Phase 2 ahead of both.

## Scope boundary

No strategy, no scent, no belief, no commit-reveal. The turn payload itself is
defined here (`protocol/action_codec.py`) but not transmitted with a
commitment until Stage 6.

## Milestone (PDF p. 105, observed not just written)

A geometric message leaving agent A over localhost is received and correctly
decoded at agent B.

## Status: ✅ Complete

`peer/server.py`, `peer/client.py`, `peer/orchestrator.py`, `peer/states.py`,
`peer/gatekeeper.py`, `peer/deadline.py`, `peer/registry.py`, `peer/run.py`,
demonstrated with `scripts/run_two_peers.py` launching two real processes:
symmetric READY, config-mismatch mutual refusal, peer-unavailable handling,
clean shutdown. See TASKS.md Phase 2 and
[../REQUIREMENTS.md](../REQUIREMENTS.md) §1 (E-1 through E-10) and §2 (E-11).

Stage 7b (`TASKS.md`, unplanned) later hardened this transport further: the
Q-20 stdout-pipe-backpressure stall was root-caused and fixed here, proven
over a real 35-turn two-process match.
