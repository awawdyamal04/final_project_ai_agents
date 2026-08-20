# Competitive strategy sprint -- results note

Benchmark evidence: `results/strategy/benchmark_2026-08-18T14-27-50.627505+00-00.json`
(500 games/matchup, seeds 1-5, code-default weights). Sweep artefact:
`results/strategy/selected_weights.json` (not used for the numbers above --
see below).

## Thief: proven, material improvement

`RiskThiefStrategy` vs the baseline cop: **0% -> 94.4% survival** (500
games). Large, robust, holds across seeds. Meets the sprint's acceptance bar
outright.

## Cop: honest result -- parity, not proven improvement

`BeliefCopStrategy` vs the baseline thief: **100% vs 100%**, identical
avg_terminal_turn (30.0 both). Against the deterministic baseline thief,
belief-map tracking is already near-exact (see `strategy/tracker.py`'s own
docstring and OPEN_QUESTIONS.md Q-17: revealed actions let a peer pin the
opponent almost exactly), and the baseline cop already wins every game in
the minimum turns the board allows -- there is no headroom left to show a
"material" win-rate improvement there; it is a hard ceiling, not a weak
baseline.

`BeliefCopStrategy` vs `RiskThiefStrategy` (the harder, tuned opponent):
**5.4% vs baseline cop's 5.6%** over 500 games -- statistically
indistinguishable, confirmed at N=350 in a separate run (8.3% vs 8.0%).

**This does not clear the sprint's "materially improve" bar for the cop.**
Per the sprint's own instruction ("if a new strategy is NOT better, continue
tuning rather than declaring success"), this is reported as-is rather than
rounded up. Two real fixes were found and shipped along the way (both
verified by direct A/B measurement, not intuition):

* `opponent_bias` defaults to `0.0` -- at `0.2` it regressed the cop from
  100% to 55% against the baseline thief (chasing a noisy habitual-direction
  proxy when belief already knows the answer). Kept as a working, tested
  capability for if reveal semantics ever become less exact, off by default.
* `near_tie_epsilon` defaults to `0.1`, not the thief's `0.75` -- a wide
  tie window cost the cop real win rate (100% -> ~75-78%) by randomising
  between pursuit directions that were not actually equivalent.

Both were caught *because* of the benchmark harness, which is the point of
building it before trusting either strategy against a real opponent.

`scripts/strategy_sweep.py --trials 30 --games-per-seed 10` found a cop
configuration that scored equally against the tuned thief (10%) but
regressed to 48% against the baseline thief -- an overfit the sweep's
current single-opponent objective does not catch. `selected_weights.json` is
kept as evidence the search ran and as a documented limitation, not adopted:
the shipped defaults are the safer, dual-opponent-validated choice. A future
iteration should score every cop candidate against *both* opponents (or add
real multi-ply minimax rather than one-ply lookahead) before it can be
expected to beat the ceiling.
