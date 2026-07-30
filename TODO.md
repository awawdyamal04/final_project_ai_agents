# TODO

Mandatory repository content (Appendix E rule 50, PDF p. 149).

Live task list. The full phased breakdown with exit criteria is in
[TASKS.md](TASKS.md); this file tracks what is actually in flight.

---

## Done

- [x] Read `police_thief_p2p.pdf` end to end (160 pages, Hebrew RTL)
- [x] Extract all 55 Appendix E mandatory rules with sanctions and PDF pages
- [x] Extract all 32 Appendix F parameters with value, type, status and owner
- [x] Classify every requirement MANDATORY / RECOMMENDED / EXAMPLE
- [x] Design the minimum architecture
- [x] Design the FastMCP protocol and message schemas
- [x] Map every mandatory rule to a test or deterministic procedure
- [x] Log all contradictions and ambiguities
- [x] Record decisions with reasoning and reversal conditions
- [x] Compliance audit of the documentation against the PDF
- [x] `.gitignore` covering every secret named in the specification
- [x] Initial documentation commit
- [x] **Second-pass audit against the rendered PDF pages** (not text extraction):
      all 55 rules and all 32 parameters re-verified visually; three gaps found
      and fixed (transition-function agreement, binding field names, log record
      schema)

## Start now — external latency, runs in parallel (D-20)

- [ ] Provision Google Cloud project + OAuth consent screen (`gmail.send` scope,
      test users). Account setup only; reporting code stays in Phase 9.
- [ ] Begin opponent-team coordination — two counting matches against different
      groups are mandatory and depend on other people's schedules.

## Next — Phase 0, project skeleton

- [ ] `pyproject.toml` — Python 3.12, `fastmcp`, `pytest`, `pytest-asyncio`
- [ ] Package skeleton under `src/police_thief/`
- [ ] `config/police/` and `config/thief/` trees with `game.json` + `game.toml`
- [ ] Typed config loader
- [ ] Config validator enforcing MINIMUM / FIXED / NEGOTIABLE semantics
- [ ] Canonical JSON helper — one implementation, used everywhere
- [ ] `tests/` skeleton with rule-ID naming
- [ ] Seven PRD stubs under `docs/prd/`

## Blocked / needs an answer

- [ ] **Q-12 — step-zero signing key.** The specification says the declaration is
      signed "with a pre-supplied key" but never says who supplies it, what
      algorithm, or how it is verified. Interim: SHA-256 commitment (D-8).
      **Ask the lecturer before the first counting match.** Do not invent a key
      scheme.

## Must be negotiated with each opponent team

Before any counting match. These are properties of a judge-free protocol — both
sides must compute identically, so both sides must agree first.

- [ ] Shared config values, including `num_games` = 6 (Q-1)
- [ ] Sealed-record schema for the commit hash (Q-4)
- [ ] Turn model — simultaneous under commit-reveal (Q-2)
- [ ] Capture resolution under simultaneous movement (Q-9)
- [ ] Scent emission/decay model with its concrete numeric example (E-23)
- [ ] Response and watchdog timeouts (Q-5)

## Before submission

- [ ] Split into two repositories, cop and thief
- [ ] Academic README in both, with all six mandatory components
- [ ] Document every contradiction choice in the README
- [ ] Screenshots: live belief map; replay showing `Verified OK`
- [ ] Verify no secret anywhere in **full** git history
- [ ] Annotated tag `v1.0-submission`, pushed
- [ ] Moodle: PDF form unaltered, one submission per member, 8-character group
      code, self-grade for code quality only
