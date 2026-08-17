# Stage 3 — Blind Strategy

*PDF Ch. 6; stage table PDF pp. 101–103. Corresponds to [TASKS.md](../../TASKS.md) Phase 3.*

## What

A first decision-making module, wired at the seam between "what do I know"
and "what do I do" — but with full, accurate information about the target, no
scent, no natural language, and no deception. "Blind" describes the absence of
the perception layers that arrive in Stage 4, not the absence of intelligence:
the strategy here already has to compute a real path, not guess randomly.

## Why

Separating the strategy module from the orchestrator and giving it a narrow,
audited information boundary (`LocalView` — no opponent position, no harness,
no global state reachable from it) has to happen before Stage 4 adds belief
and deception on top of it. If the seam is wrong here, every later stage
inherits the mistake, and the mistake becomes much harder to isolate once
scent and lying are also in the picture.

## Scope boundary

No scent, no belief map, no natural-language hints. The target is known
exactly, not inferred.

## Milestone (PDF p. 105, observed not just written)

Given a known target location, the agent computes and executes the shortest
path with no manual intervention.

## Status: ✅ Complete

`strategy/base.py` (`BaseStrategy` protocol, `LocalView`),
`strategy/heuristics.py` (`CopStrategy`, `ThiefStrategy`, deterministic
Manhattan-distance scoring over `legal_actions`/`legal_moves` so an illegal
move is never even scored). The config-driven `[strategy] police_class` /
`thief_class` override (swap the brain without touching the orchestrator) is
wired via `load_strategy()` (D-43, added 2026-08-08 during a compliance
cleanup pass — the override key had existed in config since Phase 0 but
nothing read it until then). See TASKS.md Phase 3 and
[../REQUIREMENTS.md](../REQUIREMENTS.md) §2.
