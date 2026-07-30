# CLAUDE.md — standing instructions

Permanent instructions for every future session on this repository. Read this
file first, then `docs/REQUIREMENTS.md` and `docs/PARAMETERS.md` before touching
code.

---

## 1. What this project is

An academic final project: **Distributed Cops-and-Robbers over a Peer-to-Peer
Network** (Orchestration of AI Agents, University of Haifa, 2026). Two
autonomous, symmetric agents — a cop and a thief — race on a discrete grid with
**no central referee**. Neither sees the other's true position. Each builds a
probabilistic belief from a decaying scent map and a verbal hint that may be a
lie. Integrity is guaranteed by commit-reveal over SHA-256, not by trust.

**The authoritative source is `police_thief_p2p.pdf`. Nothing else.** Not this
file, not the example repository, not any prior session's summary.

The PDF is in Hebrew. Raw `pypdf` extraction returns visually-reversed RTL text.
To read it, reconstruct logical order by reversing each line and un-reversing
Latin/digit runs; `PDF page = book page + 16`.

---

## 2. Source priority — apply mechanically

1. **Appendix F** parameter tables (PDF pp. 151–159) — the single source of
   truth for every quantitative value. Overrides every numerical example
   elsewhere in the book.
2. **Explicit mandatory rules** — Appendix E's 55 numbered rules
   (PDF pp. 142–150) and the rule boxes in the chapters.
3. **Recommendations** (המלצה / מומלץ).
4. **Illustrative examples**, diagrams and sample code — **never** a source of
   requirements.

The founding principle, stated at PDF p. 4: **a rule is not binding unless it is
explicitly written as a rule.** The default is *not* mandatory. Do not infer
requirements from diagrams or sample code.

When the document is ambiguous or contradictory: **document the conflict in
`docs/OPEN_QUESTIONS.md`; do not silently choose an interpretation.** PDF p. 5
grants academic freedom on contradiction *provided the choice is stated
explicitly in the report*. Every such choice must reach the final `README.md`.

**Never invent a requirement.** If the PDF does not say it, it is not required.
If a value is unresolved, leave it unresolved and escalate — do not fabricate it.

---

## 3. Non-negotiable design rules

These follow from the highest-sanction rules in Appendix E. Violating any one
disqualifies the project, not merely the match.

- **The live peer must never access or display the opponent's true position**
  (E-8, E-9). Enforced *structurally*: the live-state object has **no
  attribute** for it — not `None`, not `Optional`. A leak must surface as an
  `AttributeError` in a test, never as a subtle bug.
- **Only the replay verifier may reconstruct the full global state**, and only
  after the match, from the logs.
- **The two peers are symmetric.** No central referee, no shared game-state
  server, no shared module holding live state across roles (E-1, E-2). Cop and
  thief run in two entirely separate OS processes under separate config
  directories.
- **The LLM participates in the verbal/psychological layer only.** It must never
  validate moves, verify hashes, determine the winner, or be a source of truth.
  It sits behind one interface with two methods: produce a hint, classify a
  hint. The move is always decided in Python.
  *(The PDF does permit LLM-driven move selection — but only under explicit,
  mutual, documented agreement between both teams, and the local algorithm must
  still enforce legality. Default remains algorithmic.)*
- **All mandatory numeric parameters come from configuration.** No value from
  Appendix F may appear as a literal in game logic. The validator rejects any
  config lowering a `MINIMUM` or altering a `FIXED` value.
- **Network messages are explicit, minimal and schema-validated** on both
  ingress and egress.
- **Never commit secrets** — `credentials.json`, `token.json`, `.env`, keys
  (E-39, E-40). A secret pushed once is compromised permanently; rotate rather
  than delete.

---

## 4. How to work

- **Verified vertical slices.** Never implement the whole project in one
  uncontrolled pass. Follow the phases in `TASKS.md`; each phase must run
  end-to-end and pass its tests before the next begins.
- **Every mandatory behaviour needs a test or a deterministic verification
  procedure.** Test functions carry the rule ID
  (`test_e13_rejects_diagonal_move`) so coverage is greppable.
  `docs/ACCEPTANCE_TESTS.md` is the map.
- **Prefer deterministic algorithms and templates** over optional AI complexity.
- **Do not over-engineer.** No abstraction until a second concrete use exists.
- Make **small local commits after verified milestones**, not before.

**Priority order when trading off** (from the project brief):

1. Mandatory compliance
2. End-to-end working system
3. Automated verification
4. Minimal implementation complexity
5. Reliability
6. Strategy quality
7. Visual polish

---

## 5. Technology

**Use:** Python 3.12 · FastMCP · asyncio where useful · pytest · SHA-256 ·
JSON Lines audit logs · JSON for the shared signed config and TOML for the
private per-peer config (per Appendix B) · Tkinter for GUI and replay viewer ·
Gmail API **only once the core system already works**.

**Do not introduce:** Docker · databases · cloud infrastructure ·
reinforcement learning · paid LLM APIs · complex frontend frameworks ·
unnecessary abstractions.

Reinforcement learning is **out of scope** unless all mandatory requirements are
complete and verified — and even then it is one optional tool among three
equal-standing routes. The course did not teach it.

---

## 6. Configuration model

| File | Format | Scope | Signed | On the wire |
|---|---|---|---|---|
| `config/<role>/game.json` | JSON | Shared constitution; byte-identical on both sides | Yes | Hash exchanged |
| `config/<role>/game.toml` | TOML | Private, local, per-peer | No | Never |

JSON **overrides** TOML for the same key, so a private file can never weaken a
signed condition. The decision test for where a value belongs: *"must the
opponent agree to this value, or rely on it?"* — yes ⇒ JSON, no ⇒ TOML.

`docs/PARAMETERS.md` holds every parameter with its status. The three statuses
mean:

- **MINIMUM** — negotiable only in the direction that makes the game harder;
  never below the tabulated value.
- **FIXED** — cannot be changed at all; deviation disqualifies.
- **NEGOTIABLE** — any agreed value.

For all three, **the tabulated value is the code's default.**

---

## 7. Git

- Local git only. **Do not create or connect a GitHub repository** unless the
  user explicitly asks.
- Small commits after verified milestones.
- Never commit secrets, credentials, OAuth tokens, `.env` files or private keys.
- The final submission requires **two** repositories (cop, thief) with
  cross-linked READMEs and an annotated tag `v1.0-submission`. That split
  happens at submission time (see `docs/DECISIONS.md` D-16) — not before.

---

## 8. Repository map

| Path | Purpose |
|---|---|
| `docs/REQUIREMENTS.md` | All mandatory requirements by subsystem, with PDF pages and sanctions |
| `docs/PARAMETERS.md` | Appendix F, every parameter with value, type, status and owning file |
| `docs/ARCHITECTURE.md` | Minimum architecture, process model, role symmetry |
| `docs/PROTOCOL.md` | FastMCP tool interface, schemas, ordering, error handling |
| `docs/ACCEPTANCE_TESTS.md` | Every mandatory rule mapped to a test or procedure |
| `docs/OPEN_QUESTIONS.md` | Contradictions and ambiguities — **must reach the README** |
| `docs/DECISIONS.md` | Decisions with reasoning and reversal conditions |
| `docs/COMPLIANCE_AUDIT.md` | Per-requirement COVERED / MISSING / AMBIGUOUS / N-A status |
| `TASKS.md` | Dependency-ordered phases, mandatory vs optional (detailed tracker) |
| `prd.md`, `plan.md`, `todo.md` | Mandatory repository contents (E-50); the Vibe-Coding WHAT/HOW/checklist stages |
| `requirements.txt` | Course-convention install (`pip install -r`); versions live in `pyproject.toml` |
| `results/` | Observed submission artefacts: screenshots, replay reports, benchmarks, plots |

---

## 9. When you are unsure

Stop and ask **only** when:

- a mandatory requirement is genuinely ambiguous;
- a destructive action is required;
- credentials, private addresses or personal information are needed;
- two interpretations materially change compliance.

Otherwise proceed — routine implementation decisions clearly supported by the
PDF do not need approval.

**Do not fabricate unresolved parameters.** `docs/OPEN_QUESTIONS.md` Q-12
(the step-zero signing key) is currently unresolved and must be escalated to the
lecturer before the first counting match. Do not invent a key-distribution
scheme to close it.
