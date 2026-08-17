# Stage 5 — Cloud Exposure and Tunnelling

*PDF Ch. 2; stage table PDF pp. 101–103. Corresponds to [TASKS.md](../../TASKS.md) Phase 8.*

## What

Move the transport from localhost to a public address via a tunnel (ngrok or
Localtonet), and play a full round against a peer on a genuinely different
machine.

## Why

Everything through Stage 4 (and the crypto of Stage 6, built ahead of this one
— see "Scope boundary") has been proven over localhost, where latency, packet
loss and NAT do not exist. This stage is the first point at which the system
is a real distributed system rather than two processes on one machine
pretending to be one. It is also the stage the PDF's own rationale (Ch. 10)
places *before* cryptography — "don't debug crypto through an unproven
transport" — a rationale this project's `TASKS.md` explicitly honours even
while inverting the build order (crypto was built and proven over localhost
first, in Phase 5, precisely because localhost already proved the transport in
Phase 2).

## Scope boundary

Tunnelling itself is external tooling (ngrok/Localtonet), not code this
project owns. What belongs here is: binding the server to a host/port suitable
for tunnelling, reading `opponent_url` from private config for a non-localhost
peer, and validating timeout/retry behaviour against real network latency
rather than a fake clock.

## Milestone (PDF p. 105, observed not just written)

An agent on a remote machine connects via the tunnel and plays a full round
against the local agent.

## Status: Not started

No code changes required to reach this milestone are known to be blocking —
`config/*.toml.example [network] opponent_url` already exists as a field — but
binding, tunnel documentation, and a real cross-machine match have not been
attempted. This also depends on opponent-team coordination (`todo.md`,
"Start now — external latency"), which had not begun as of 2026-08-08. See
TASKS.md Phase 8.
