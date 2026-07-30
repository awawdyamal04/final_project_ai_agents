# PLAN

Work plan. Mandatory repository content (Appendix E rule 50, PDF p. 149).

The detailed, dependency-ordered breakdown lives in [TASKS.md](TASKS.md); this
file states the strategy those phases serve.

---

## Objective

Build the **smallest reliable implementation** that satisfies every mandatory
requirement in `police_thief_p2p.pdf`. Not the most capable agent — the most
compliant, verifiable and complete system.

## Approach

**Build in verified vertical slices.** Each phase produces a system that runs
end-to-end at its own scope and passes its own tests before the next phase
begins. At any moment, the space of possible faults is confined to the layer
just added. This is the specification's own incremental-delivery principle
(Ch. 10), and it is the reason the plan resists the temptation to start with the
interesting parts — cryptography, tunnels, language models — before the boring
parts are proven.

**Compliance is designed in, not inspected in.** The rules with the heaviest
sanctions (never show the opponent's true position; never share state between
roles; never lower a mandatory parameter) are enforced by structure — an absent
attribute, an import-graph constraint, a config validator — so that a violation
surfaces as a failing test rather than as a disqualification discovered at
submission.

**Every mandatory behaviour has a named verification.** Test functions carry
their rule ID, so the compliance argument is greppable rather than assertive.
[docs/ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) is the map from the 55 rules
to the tests and procedures that discharge them.

## Sequence

1. **Foundation** — config model, validator, canonical serialisation, test
   skeleton.
2. **Base logic** — grid, movement, barriers, capture, scoring, single process.
3. **Transport** — FastMCP server and client, state machine, orchestrator, two
   processes.
4. **Intelligence** — strategy module, scent physics, belief map, verbal layer.
5. **Integrity** — commit-reveal, mutual audit, step-zero, deadlines, watchdog.
6. **Evidence** — replay verifier and viewer; live GUI.
7. **Reach** — public exposure via tunnel; a real remote match.
8. **Reporting** — the four JSON artefacts, Gatekeeper, Gmail.
9. **League** — negotiation, warm-ups, counting matches.
10. **Submission** — two repositories, academic README, screenshots, tag.

Cryptography deliberately precedes cloud exposure, inverting the specification's
recommended order. The rationale — crypto is offline-testable and carries the
heaviest sanctions, while the transport was already proven over localhost — is
recorded in [TASKS.md](TASKS.md) Phase 5. The specification's own reason for its
ordering is honoured; only the sequence differs.

## Risks and how the plan absorbs them

**Two peers must compute identically.** In a judge-free protocol, any divergence
in serialisation, physics or schema makes every audit fail. Mitigated by a single
canonical-JSON helper used everywhere, by exchanging config and scent-model
hashes before play, and by negotiating the sealed-record schema with each
opponent rather than assuming it.

**The specification contradicts itself in six places.** Mitigated by mechanical
source priority, by logging every contradiction in
[docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) rather than resolving it
silently, and by routing every choice into the final academic report — which the
specification explicitly permits, provided the choice is stated.

**One requirement cannot be resolved from the document.** The step-zero signing
key (Q-12) has no stated source. An interim SHA-256 commitment stands in; the
question is escalated to the lecturer before the first counting match rather
than closed by invention.

**Reporting is a live account with a hard quota.** Mitigated by building the
reporting shell last, behind three cumulative gates, with send-only scope.

## Out of scope

Reinforcement learning, paid LLM APIs, Docker, databases, cloud infrastructure,
web frameworks, and any abstraction without a second concrete use. Strategy
quality ranks sixth of seven in the project's priority ordering, below
compliance, working system, verification, simplicity and reliability; visual
polish ranks last.
