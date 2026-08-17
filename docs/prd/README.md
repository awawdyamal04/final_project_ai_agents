# Stage PRDs

Seven short PRDs, one per development stage from the PDF's own recommended
build order (Ch. 10, PDF pp. 101–103; table reproduced in
[../REQUIREMENTS.md](../REQUIREMENTS.md) §9). Their *existence* here is
mandatory (E-50, PDF p. 149); the seven-stage decomposition itself is a
**recommendation**, not a rule, and the PDF says so explicitly at the head of
the chapter.

**Relationship to the root [prd.md](../../prd.md).** The root PRD is the
authoritative, complete WHAT document — every mandatory requirement, traced to
the PDF. These stage files are narrower: what a *reader of this one increment*
needs, and nothing more. They exist to satisfy E-50's requirement for
stage-scoped PRDs and to make each increment's exit criterion checkable in
isolation. Where the two disagree, the root `prd.md` and
`docs/REQUIREMENTS.md` win — that is the actual source of truth.

**Relationship to [TASKS.md](../../TASKS.md).** `TASKS.md` is the live,
dependency-ordered execution tracker and is what actually governs build order
— it deliberately deviates from the PDF's stage order in two places (crypto
before cloud exposure; template-only verbal layer before any LLM), each
reasoned in `TASKS.md` itself. The mapping below is stage-to-phase, not
stage-to-stage-number, because the two orderings diverge.

| PDF stage | This file | TASKS.md phase | Status (2026-08-08) |
|---|---|---|---|
| 1. Base Logic | [stage-1-base-logic.md](stage-1-base-logic.md) | Phase 1 | ✅ Complete |
| 2. Basic MCP Infrastructure | [stage-2-basic-mcp-infrastructure.md](stage-2-basic-mcp-infrastructure.md) | Phase 2 | ✅ Complete |
| 3. Blind Strategy | [stage-3-blind-strategy.md](stage-3-blind-strategy.md) | Phase 3 | ✅ Complete |
| 4. Language and Scent | [stage-4-language-and-scent.md](stage-4-language-and-scent.md) | Phase 4 | ✅ Complete (template provider; LLM providers optional, not started) |
| 5. Cloud Exposure and Tunnelling | [stage-5-cloud-exposure-and-tunnelling.md](stage-5-cloud-exposure-and-tunnelling.md) | Phase 8 | Not started |
| 6. Security and Cryptography | [stage-6-security-and-cryptography.md](stage-6-security-and-cryptography.md) | Phase 5 (built ahead of stage 5, see TASKS.md) | ✅ Complete |
| 7. Reporting and Visualisation Shell | [stage-7-reporting-and-visualisation.md](stage-7-reporting-and-visualisation.md) | Phase 9 (GUI itself shipped in Phase 7) | Reporting/Gmail not started; GUI ✅ complete (Q-19 open) |
