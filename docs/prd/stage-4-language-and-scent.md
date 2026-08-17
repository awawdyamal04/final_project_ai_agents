# Stage 4 — Language and Scent

*PDF Ch. 4, Ch. 6; stage table PDF pp. 101–103. Corresponds to [TASKS.md](../../TASKS.md) Phase 4. The PDF calls this the most sensitive stage.*

## What

Replace exact target knowledge with two genuinely uncertain information
sources: a decaying pheromone/scent field the opponent cannot fake (it is
emitted by movement itself), and a free-language hint that can be true or
false. Both feed a Bayesian belief map; the strategy from Stage 3 switches
from "go to the known target" to "go to the believed target."

## Why

The PDF is explicit that this stage should only be attempted once
infrastructure and logic are already proven (Stages 1–3) — belief and
deception are the hardest layer to debug, and debugging them through an
unproven transport or an unproven strategy seam would confound the causes.
This is also the one place in the whole system where an LLM is permitted to
participate (composing and reading hints) — and the hard boundary the project
never crosses: the model produces text, never a move. `strategy/verbal.py`'s
`HintProvider` protocol enforces that structurally, not just by convention.

## Scope boundary

**Deviation from the PDF's own stage description, deliberately narrowed, not
reordered:** the PDF folds LLM integration into this stage. This project ships
the **template** hint provider only (D-13) — deterministic, offline, zero
tokens — which is itself the PDF's documented default. Real LLM-backed
providers (`ollama`, `claude_api`, `claude_cli`) are optional enhancements
(see `TASKS.md`'s "Optional enhancements"), not required for this stage's exit
criterion, and not built.

## Milestone (PDF p. 105, observed not just written)

Free-language reporting is translated into inference; the scent map updates
and decays every step; the hint layer produces a hint, true or false.

## Status: ✅ Complete (template provider; LLM providers optional, not started)

`domain/scent.py` (Gaussian radial falloff fitted to the PDF's tabulated
emission field, decay `τ(t+1) = max(0, (1−ρ)·τ(t) + Δτ)` once per full turn,
D-39), `domain/belief.py` (Bayesian belief map with impossible-cell exclusion,
D-40), `strategy/verbal.py` (`TemplateHintProvider`, hint validation against
`hint_max_words` and numeric-position leaks — E-26, E-27 — wrapped in
`SafeHintProvider` so a future network-backed provider can never break a
turn), `intent` (`truth`/`lie`) carried on every hint and sealed into the
commit-reveal record. See TASKS.md Phase 4 and
[../REQUIREMENTS.md](../REQUIREMENTS.md) §4.
