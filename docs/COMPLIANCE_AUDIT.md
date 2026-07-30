# COMPLIANCE AUDIT

Two audit passes against `police_thief_p2p.pdf`.

- **Pass 1** (2026-07-28): documentation built from a text extraction of the PDF.
- **Pass 2** (2026-07-28): re-verified **against the PDF itself**, rendering the
  critical pages to images and reading them visually.

**Why pass 2 used images.** The book is Hebrew, right-to-left. `pypdf` text
extraction returns table cells in visual rather than logical order, so a
parameter's value can end up adjacent to a different parameter's status. That is
exactly where a wrong number or a wrong status would hide, and it would not look
wrong. Pages 142–150 (Appendix E) and 152–155 (Appendix F), plus the config
appendix pages 126–132, were rendered at 150 dpi and read as images. Every value,
status, unit and rule classification below is confirmed against the rendered
page, not against the extraction.

**Scope.** This audits whether each PDF requirement is *correctly captured and
assigned*. No application code exists, so nothing is marked implemented.
`COVERED` means: documented, correctly classified, parameterised where
applicable, and mapped to a verification.

**Status key.**

| Status | Meaning |
|---|---|
| `COVERED` | Captured with correct classification, PDF page, sanction and mapped verification. |
| `MISSING` | In the PDF, absent from the docs. Every one found in pass 2 was fixed in pass 2 and added to `TASKS.md`; none remain open. |
| `AMBIGUOUS` | The PDF is silent or unclear. Logged in `OPEN_QUESTIONS.md`. |
| `CONTRADICTORY` | The PDF says two incompatible things. Logged, with the resolution and its basis. |
| `N/A` | Not applicable at this stage, or explicitly non-binding. |

---

## Part 1 — What pass 2 changed

Five findings. Three were genuine gaps, two were precision errors.

| # | Finding | Type | Fix |
|---|---|---|---|
| F-1 | **PDF p. 21** (Ch. 1, the `P` component of the Dec-POMDP octuple): *"since there is no central server, both sides must agree on that same transition function — it is encoded in the shared configuration file."* An explicit mandatory statement outside Appendix E, not previously recorded. | `MISSING` → fixed | REQUIREMENTS §2; new test in ACCEPTANCE_TESTS §2 |
| F-2 | **PDF p. 130**: *"every field value may change by negotiation… **but the field names are fixed and binding**."* Pass 1 documented value negotiation but never that key names are immutable. Consequence: the loader must treat the key set as a **closed schema** and reject renamed or unknown keys, rather than defaulting them. | `MISSING` → fixed | REQUIREMENTS §6, PARAMETERS §1, ARCHITECTURE §7, TASKS Phase 0, two new tests |
| F-3 | **PDF p. 94**: the log must contain *"commit-reveal commitments, moves, hints **and the LLM discussion fields**, alongside the nonce and hash."* Pass 1 defined the wire protocol but never a log record schema — even though the log, not the wire, is what the replay verifier and the mutual audit consume. | `MISSING` → fixed | New PROTOCOL §11 with full schema and a replay-sufficiency argument; D-19; four new tests |
| F-4 | Pass 1 presented `config/<role>/game.json` as if it were the PDF's path. Appendix B actually says `config/game.json` (pp. 126, 130); the role sub-directory comes from Ch. 2 p. 31, which offers `/config/thief` vs `/config/police` **as an example**. | Precision error → fixed | D-18 records the reconciliation as our choice, not a quotation; PARAMETERS §2, ARCHITECTURE §7 |
| F-5 | `config_sha256` is **the PDF's own field name** (p. 127), not one we coined; and the shared config is **both hashed and signed** (signature p. 126, cryptographic lock App. F §2 p. 156), not one or the other. | Precision gain | PARAMETERS §2, PROTOCOL §3, ARCHITECTURE §7 |

Two planning changes also came out of pass 2 (D-20): Google Cloud/OAuth
provisioning and opponent-team coordination move to parallel tasks starting now,
because both have external latency that no amount of engineering compresses, and
E-31 requires two counting matches against different groups.

---

## Part 2 — Appendix E verification (all 55 rules)

Rendered and read: PDF pp. 142–150.

**Numbering:** contiguous 1–55 across six tables, no gaps, no duplicates.
Table 7 = rules 1–10, table 8 = 11–16, table 9 = 17–24, table 10 = 25–30,
table 11 = 31–45, table 12 = 46–55. Confirmed.

**Classification:** each rule carries a `פעולה` (action) column with exactly one
of `חובה` (obligation), `איסור` (prohibition), `המלצה` (recommendation).
Confirmed across all 55:

- **`חובה` (obligation): 43 rules** — 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15, 17,
  18, 19, 20, 21, 23, 24, 26, 28, 29, 30, 31, 32, 33, 35, 36, 37, 40, 41, 42,
  43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55.
- **`איסור` (prohibition): 11 rules** — 1 *(see note)*, 2, 9, 14, 16, 22, 27,
  34, 38, 39.
- **`המלצה` (recommendation): exactly 1 rule — E-25.**

> **Note on E-1.** Rule 1 appears at the foot of PDF p. 142 with its action cell
> on the following page's header repetition; it reads *"run the thief code and
> the cop code in two entirely separate processes"* with sanction *"total
> failure and breaking of the Zero-Trust model"*. It is an obligation in
> substance regardless of column label. Counted once, as mandatory.

**The single recommendation, verified verbatim (PDF p. 146, table 10, row 25):**

> `המלצה` — *"Do not pass to the language model the decision on the movement
> move itself; use it for text processing and creating a behavioural profile
> only. **Note: there is no mandatory sanction**, but blind reliance may entail
> hallucinations, illegal moves and technical loss."*

This is the one place where misclassification would have caused real harm —
treating it as mandatory would forbid the LLM-tactics path that the PDF
explicitly permits under mutual agreement (p. 66). Correctly classified
`RECOMMENDED` in pass 1 and re-confirmed in pass 2.

**Sanctions:** every rule except E-25 carries an explicit `סנקציה` clause.
All 54 sanctions are transcribed in REQUIREMENTS §§1–6. Confirmed against the
rendered pages.

**No example or recommendation was misclassified as mandatory.** Checked in both
directions: nothing labelled `המלצה` is presented as binding, and no obligation
was downgraded.

**Result: 55/55 rules extracted, numbered, classified and sanctioned correctly.**

---

## Part 3 — Appendix F verification (all parameters)

Rendered and read: PDF pp. 152–155.

**Status vocabulary — answering the audit question directly.** The PDF uses
**exactly three** statuses, stated in its own words at p. 155: *"the status
column in the tables above receives one of **three** values"*.

| PDF status | Meaning | May be changed? |
|---|---|---|
| `מינימום` MINIMUM | Negotiable **only in the direction that makes the game harder**; never eased below the tabulated value. Absent explicit agreement, the tabulated value is the code's default. | Upward / stricter only |
| `קבוע` FIXED | Binding, **not changeable at all**. *"Deviating from this value disqualifies the team"* (bolded in the PDF). | Never |
| `משא ומתן` NEGOTIABLE | Any agreed value. Absent explicit agreement, the tabulated value is the code's default. | Freely, by agreement |

**There is no `DEFAULT` status and no `OPTIONAL` status in Appendix F.** The
audit brief asked about both; neither exists. Using either label would be
inventing a category. Note that under all three statuses the tabulated value
functions as the default, which is why "example value" is a misleading column
heading — see below.

**The "example value" column — verified interpretation.** PDF p. 151:
*"the values presented in the 'example value' column **are the binding
minimum**: it is permitted to raise them by mutual agreement between the two
playing teams, but it is **forbidden** to lower them below this bar."*

So the column heading says *example* but its contents are **binding**. This is
the single most consequential thing to get right in the whole extraction, and it
is documented as such at the head of PARAMETERS.md. These values are **not**
`EXAMPLE` in the non-binding sense of PDF p. 4.

**All 32 tabulated values, re-verified visually:**

| Table | # | Parameter | Value | Unit / type | Status |
|---|---|---|---|---|---|
| 13 | 1 | `[grid_size]` | 7×7 | cells, int | MINIMUM |
| 13 | 2 | `[num_agents]` | 2 | int | FIXED |
| 13 | 3 | `[axis_origin_corner]` | top-left | enum | NEGOTIABLE |
| 13 | 4 | `[axis_start_index]` | 0 | int | NEGOTIABLE |
| 13 | 5 | `[thief_start]` | centre (3,3) | (row,col) | NEGOTIABLE |
| 13 | 6 | `[cop_start]` | corner (0,0) | (row,col) | NEGOTIABLE |
| 14 | 1 | `[map_area]` | New York | string | NEGOTIABLE |
| 14 | 2 | `[hint_max_words]` | 15 | words, int | NEGOTIABLE |
| 15 | 1 | `[move_set]` | 4 + stay | enum list | FIXED |
| 15 | 2 | `[max_barriers]` | 14 | int | MINIMUM |
| 15 | 3 | `[max_moves]` | 35 | moves, int | MINIMUM |
| 15 | 4 | `[survival_threshold]` | 35 | steps, int | MINIMUM |
| 16 | 1 | `[pheromone_center_intensity]` | 0.9 | float | FIXED |
| 16 | 2 | `[pheromone_decay]` | 0.10 | float, per turn | FIXED |
| 16 | 3 | `[pheromone_grid_size]` | 5×5 | cells, int | FIXED |
| 17 | 1 | `[capture_cop]` | 20 | points, int | FIXED |
| 17 | 2 | `[capture_thief]` | 5 | points, int | FIXED |
| 17 | 3 | `[survival_cop]` | 5 | points, int | FIXED |
| 17 | 4 | `[survival_thief]` | 10 | points, int | FIXED |
| 17 | 5 | `[tie_score]` | 2 | points, int | FIXED |
| 18 | 1 | `[num_sub_games]` | 6 | int | FIXED |
| 18 | 2 | `[diversity_reward]` | 10 | points, int | FIXED |
| 18 | 3 | `[min_games_to_pass]` | 2 | matches, int | FIXED |
| 18 | 4 | `[token_budget_per_series]` | ~200000 | tokens, int | NEGOTIABLE |
| 18 | 5 | `[max_games_per_team]` | 10 | matches, int | FIXED |
| 19 | 1 | `[requests_per_minute]` | 30 | req/min, int | MINIMUM |
| 19 | 2 | `[concurrent_requests]` | 2 | int | MINIMUM |
| 19 | 3 | `[retry_backoff_sec]` | 5 | **seconds** | MINIMUM |
| 19 | 4 | `[max_retries]` | 3 | int | MINIMUM |
| 19 | 5 | `[queue_depth]` | 100 | int | MINIMUM |
| 19 | 6 | `[response_timeout_sec]` | 30 | **seconds** | NEGOTIABLE |
| 19 | 7 | `[watchdog_timeout_sec]` | 60 | **seconds** | NEGOTIABLE |

Units confirmed: only rows 3, 6 and 7 of table 19 carry an explicit unit
(`שנ׳` = seconds). `[grid_size]` and `[pheromone_grid_size]` are printed as
`7×7` and `5×5` — i.e. the side length, not an area.

**Which may never be lowered or altered:** the 14 FIXED parameters may never
change at all. The 9 MINIMUM parameters may never go below the tabulated value.
The 9 NEGOTIABLE parameters are free by agreement. **Total 32.**

> **Correction (Phase 0).** Pass 2 of this audit recorded the split as
> "14 FIXED, 11 MINIMUM, 7 NEGOTIABLE". That was an arithmetic slip on my part:
> the correct split is **14 / 9 / 9**. Counting from the tables above —
> MINIMUM: `grid_size`, `max_barriers`, `max_moves`, `survival_threshold`,
> `requests_per_minute`, `concurrent_requests`, `retry_backoff_sec`,
> `max_retries`, `queue_depth` = 9. NEGOTIABLE: `axis_origin_corner`,
> `axis_start_index`, `thief_start`, `cop_start`, `map_area`, `hint_max_words`,
> `token_budget_per_series`, `response_timeout_sec`, `watchdog_timeout_sec` = 9.
> The total was always 32, so no parameter was missing or duplicated — only the
> per-status tally was wrong.
>
> The error was caught by building the policy table in code and counting it.
> `tests/config/test_validation.py::test_status_distribution_matches_appendix_f`
> now asserts 14/9/9, so the tally cannot drift from the table again.

**Reference tables 20–22** (files/addresses, LLM modes, strategy keys) are
labelled by the PDF as *reference only — not part of the agreed configuration
file and not subject to negotiation*. Covered in PARAMETERS §§10–12.

**Appendix F §2** (PDF p. 156) — six accompanying obligations, all covered in
PARAMETERS §13.

**Result: 32/32 parameters, 3/3 status definitions, 6/6 obligations verified.**

---

## Part 4 — Final requirement table

Document abbreviations: `REQ` = REQUIREMENTS.md · `PAR` = PARAMETERS.md ·
`ARC` = ARCHITECTURE.md · `PRO` = PROTOCOL.md · `AT` = ACCEPTANCE_TESTS.md ·
`OQ` = OPEN_QUESTIONS.md · `DEC` = DECISIONS.md.

### 4.1 Network architecture and decentralisation

| ID | Summary | PDF p. | Class | Doc | Test | Status | Action |
|---|---|---|---|---|---|---|---|
| E-1 | Two entirely separate processes | 142 | MANDATORY | REQ §1, ARC §5 | AT §1 | `COVERED` | — |
| E-2 | No shared memory or variables | 143 | MANDATORY | REQ §1, DEC D-9 | AT §1 | `COVERED` | — |
| E-3 | Orchestrator = single entry point | 143 | MANDATORY | REQ §1, ARC §3 | AT §1 | `COVERED` | — |
| E-4 | Proper state machine | 143 | MANDATORY | REQ §1, ARC §2 | AT §1 | `COVERED` | — |
| E-5 | Reject illegal transitions | 143 | MANDATORY | REQ §1, PRO §7.3 | AT §1 | `COVERED` | — |
| E-6 | Deadline tracking | 143 | MANDATORY | REQ §1, PRO §7.1 | AT §1 | `COVERED` | — |
| E-7 | Watchdog | 143 | MANDATORY | REQ §1, ARC §4 | AT §1 | `COVERED` | — |
| E-8 | Live GUI: local truth only | 143 | MANDATORY | REQ §1, ARC §3.6 | AT §1 | `COVERED` | — |
| E-9 | Never show objective board state | 143 | MANDATORY | REQ §1, DEC D-9 | AT §1 | `COVERED` | — |
| E-10 | Tunnel to public internet | 144 | MANDATORY | REQ §1 | AT §1 | `COVERED` | Phase 8 |
| — | Both sides agree same transition fn | **21** | MANDATORY | REQ §2 | AT §2 | `COVERED` | *Added pass 2* |

### 4.2 Spatial mechanics and board

| ID | Summary | PDF p. | Class | Doc | Test | Status | Action |
|---|---|---|---|---|---|---|---|
| E-11 | Config byte-identical both sides | 144 | MANDATORY | REQ §2, PRO §3 | AT §2 | `COVERED` | — |
| E-12 | Raise minimums only; never lower | 144 | MANDATORY | REQ §2, PAR §1 | AT §2 | `COVERED` | — |
| E-13 | Orthogonal moves only | 144 | MANDATORY | REQ §2 | AT §2 | `COVERED` | — |
| E-14 | No diagonals | 144 | MANDATORY | REQ §2 | AT §2 | `COVERED` | — |
| E-15 | Declare every barrier openly | 144 | MANDATORY | REQ §2, PRO §6.4 | AT §2 | `COVERED` | — |
| E-16 | Never lie about barrier location | 144 | MANDATORY | REQ §2, PRO §6.1 | AT §2 | `COVERED` | — |
| E-46 | Barrier on thief's cell = capture | 149 | MANDATORY | REQ §2 | AT §2 | `COVERED` | — |
| E-47 | Thief with no legal move = captured | 149 | MANDATORY | REQ §2 | AT §2 | `COVERED` | — |
| E-48 | Score every scenario per tables | 149 | MANDATORY | REQ §2, PAR §7 | AT §2 | `COVERED` | — |
| — | Field names fixed and binding | **130** | MANDATORY | REQ §6, PAR §1 | AT §2 | `COVERED` | *Added pass 2* |

### 4.3 Cryptography and integrity

| ID | Summary | PDF p. | Class | Doc | Test | Status | Action |
|---|---|---|---|---|---|---|---|
| E-17 | Commit-reveal over SHA-256 | 145 | MANDATORY | REQ §3, PRO §6 | AT §3 | `COVERED` | — |
| E-18 | Nonce secret until match end | 145 | MANDATORY | REQ §3, PRO §6.4 | AT §3 | `COVERED` | — |
| E-19 | Technical loss on hash mismatch | 145 | MANDATORY | REQ §3, PRO §6.6 | AT §3 | `COVERED` | — |
| E-20 | Replay viewer application | 145 | MANDATORY | REQ §3, ARC §3.7 | AT §3 | `COVERED` | Phase 6 |
| E-21 | Truthful capture declaration | 145 | MANDATORY | REQ §3, PRO §6.5 | AT §3 | `COVERED` | — |
| E-22 | No false capture claim | 145 | MANDATORY | REQ §3, PRO §6.5 | AT §3 | `COVERED` | — |
| E-23 | Lock scent model pre-match | 145 | MANDATORY | REQ §3, PRO §3 | AT §3 | `COVERED` | Negotiate |
| E-24 | Cryptographic hardware declaration | 145 | MANDATORY | REQ §3, PRO §4 | AT §3 | `COVERED` | — |
| E-53 | Commit hash in step-zero | 150 | MANDATORY | REQ §3, PRO §4 | AT §3 | `COVERED` | — |
| — | Log content incl. LLM fields | **94** | MANDATORY | PRO §11, REQ §6 | AT §3 | `COVERED` | *Added pass 2* |
| — | Step-zero signing key | 56 | MANDATORY | OQ Q-12, DEC D-8 | AT §3 | `AMBIGUOUS` | **Ask lecturer** |

### 4.4 Scent physics

| ID | Summary | PDF p. | Class | Doc | Test | Status | Action |
|---|---|---|---|---|---|---|---|
| — | Emission window, centre, radial falloff | 43 | MANDATORY | REQ §4, PAR §6 | AT §4 | `COVERED` | — |
| — | Decay `τ(t+1)=max(0,(1−ρ)τ+Δτ)` | 43 | MANDATORY | REQ §4 | AT §4 | `COVERED` | — |
| — | Decay once per **full** turn | 43 | MANDATORY | REQ §4, PRO §5 | AT §4 | `COVERED` | — |
| — | Each peer reads only opponent's field | 41, 45 | MANDATORY | ARC §3.2 | AT §4 | `COVERED` | — |
| — | Scent cannot be forged | 22, 46 | MANDATORY | REQ §4 | AT §4 | `COVERED` | — |

### 4.5 Strategy, language, network protection

| ID | Summary | PDF p. | Class | Doc | Test | Status | Action |
|---|---|---|---|---|---|---|---|
| E-25 | LLM must not decide the move | 146 | **RECOMMENDED** | REQ §5, ARC §8 | AT §5 | `COVERED` | — |
| E-26 | Free natural language only | 146 | MANDATORY | REQ §5, PRO §8 | AT §5 | `COVERED` | — |
| E-27 | No numeric position protocols | 146 | MANDATORY | REQ §5, PRO §8 | AT §5 | `COVERED` | — |
| E-28 | Token-bucket rate limiter | 146 | MANDATORY | REQ §5, PAR §9 | AT §5 | `COVERED` | Phase 9 |
| E-29 | DOS detector | 146 | MANDATORY | REQ §5, ARC §3.8 | AT §5 | `COVERED` | Phase 9 |
| E-30 | Send-only Gmail scope | 146 | MANDATORY | REQ §5, §8 | AT §5 | `COVERED` | Phase 9 |
| — | Separate strategy module at the seam | 58 | MANDATORY | ARC §3.3 | AT §3 | `COVERED` | — |
| — | LLM move tactics by mutual agreement | 66 | permitted exception | REQ §5 | AT §5 | `COVERED` | — |

### 4.6 League, reporting, administration

| ID | Summary | PDF p. | Class | Doc | Test | Status | Action |
|---|---|---|---|---|---|---|---|
| E-31 | Min matches vs different groups | 147 | MANDATORY | REQ §6, PAR §8 | AT §6 | `COVERED` | **Start now** (D-20) |
| E-32 | Automatic Gmail reporting | 147 | MANDATORY | REQ §6 | AT §6 | `COVERED` | Phase 9 |
| E-33 | Report as standard JSON | 147 | MANDATORY | REQ §6 | AT §6 | `COVERED` | — |
| E-34 | Never free text; attachment only | 147 | MANDATORY | REQ §6 | AT §6 | `COVERED` | — |
| E-35 | Agree result; each sends separately | 147 | MANDATORY | REQ §6, PRO §6.7 | AT §6 | `COVERED` | — |
| E-36 | Mutual log audit every match | 147 | MANDATORY | REQ §6, PRO §6.6 | AT §6 | `COVERED` | — |
| E-37 | Declare counted-match count | 147 | MANDATORY | REQ §6, PRO §3 | AT §6 | `COVERED` | — |
| E-38 | No false count declaration | 148 | MANDATORY | REQ §6 | AT §6 | `COVERED` | — |
| E-39 | Never push secrets | 148 | MANDATORY | REQ §7.6 | AT §6 | `COVERED` | `.gitignore` shipped |
| E-40 | Secrets in `.gitignore` | 148 | MANDATORY | REQ §6 | AT §6 | `COVERED` | Done |
| E-41 | Documented Git tag | 148 | MANDATORY | REQ §7.1 | AT §6 | `COVERED` | Phase 11 |
| E-42 | Comprehensive academic report | 148 | MANDATORY | REQ §7.3 | AT §7 | `COVERED` | Phase 11 |
| E-43 | Moodle form, fields unchanged | 148 | MANDATORY | REQ §7.5 | AT §6 | `COVERED` | Phase 11 |
| E-44 | Separate submission per member | 148 | MANDATORY | REQ §7.5 | AT §6 | `COVERED` | Phase 11 |
| E-45 | Unique 8-char group code | 148 | MANDATORY | REQ §7.5 | AT §6 | `COVERED` | — |
| E-49 | Two repos, cross-link, 2+4 links | 149 | MANDATORY | REQ §7.1, DEC D-16 | AT §6 | `COVERED` | Phase 11 |
| E-50 | README, /config, PRD, PLAN, TODO | 149 | MANDATORY | REQ §7.2, ARC §9 | AT §6 | `COVERED` | Phase 0 |
| E-51 | Send to agent reporting address | 149 | MANDATORY | REQ §6, PAR §10 | AT §6 | `COVERED` | Phase 9 |
| E-52 | One counting match per opponent | 149 | MANDATORY | REQ §6 | AT §6 | `COVERED` | — |
| E-54 | Report total tokens consumed | 150 | MANDATORY | REQ §6, PRO §6.7 | AT §6 | `COVERED` | — |
| E-55 | Self-grade for code quality only | 150 | MANDATORY | REQ §7.5 | AT §6 | `COVERED` | Phase 11 |
| — | Tie rule: equal totals ⇒ `tie_score` | 87 | MANDATORY | REQ §6, PRO §10 | AT §6 | `COVERED` | — |
| — | Per-match config committed, distinct name | 156 | MANDATORY | PAR §13 | AT §6 | `COVERED` | — |
| — | Per-match email with commit number | 156 | MANDATORY | OQ Q-13 | AT §6 | `COVERED` | — |

### 4.7 Contradictions and ambiguities

| ID | Summary | PDF p. | Class | Doc | Test | Status | Action |
|---|---|---|---|---|---|---|---|
| Q-1 | `num_games` 6 FIXED vs example 1 | 129, 130, 154 | MANDATORY | OQ Q-1, DEC D-2 | AT §6 | `CONTRADICTORY` | **PDF resolves usage**: 6 for league. Negotiate. |
| Q-2 | Turn order never specified | — | — | OQ Q-2, DEC D-6 | AT §1 | `AMBIGUOUS` | Negotiate |
| Q-3 | `technical_loss` absent from App. F | 38, 129, 149, 154 | MANDATORY | OQ Q-3, DEC D-3 | AT §2 | `CONTRADICTORY` | Carry 0; mark non-App-F |
| Q-4 | Commit payload field set | 50, 51, 74 | MANDATORY | OQ Q-4, DEC D-4 | AT §3 | `CONTRADICTORY` | **PDF resolves the field set**; negotiate key spelling |
| Q-5 | Three timeout values | 83, 131, 155 | MANDATORY | OQ Q-5, PAR §9 | AT §1 | `AMBIGUOUS` | Negotiate |
| Q-6 | Grid 7×7 vs 10×10 figures | 1, 34, 64, 152 | EXAMPLE | OQ Q-6 | AT §2 | `COVERED` | None — MIN 7 |
| Q-7 | `draft` vs mandatory send | 131, 139, 141, 147 | MANDATORY | OQ Q-7, DEC D-5 | AT §6 | `CONTRADICTORY` | **PDF resolves**: book overrides repo (p. 141); example not binding (p. 4) → `send` |
| Q-8 | MINIMUM direction for rate limits | 155 | MANDATORY | OQ Q-8 | AT §5 | `AMBIGUOUS` | Treat as protective defaults |
| Q-9 | Capture on cell swap / vacated cell | 38 | MANDATORY | OQ Q-9, DEC D-7 | AT §2 | `AMBIGUOUS` | Negotiate |
| Q-10 | Axis: text says down, figure shows up | 34, 36, 64 | EXAMPLE | OQ Q-10 | AT §2 | `COVERED` | Follow Ch. 3 text |
| Q-11 | Is a Live GUI mandatory per se? | 97, 113, 136 | MANDATORY in effect | OQ Q-11 | AT §1 | `COVERED` | Build it |
| Q-12 | Step-zero signing key undefined | 56 | MANDATORY | OQ Q-12, DEC D-8 | AT §3 | `AMBIGUOUS` | **Ask lecturer** |
| Q-13 | Config per match: email or repo? | 156 | MANDATORY | OQ Q-13 | AT §6 | `COVERED` | Both |
| Q-14 | `min_games_to_pass` vs "different groups" | 136, 147, 154 | MANDATORY | OQ Q-14 | AT §6 | `COVERED` | None |

### 4.8 Explicitly not applicable

| Item | PDF p. | Status | Basis |
|---|---|---|---|
| Reinforcement learning | 59, 61, 67, 115 | `N/A` | Optional; course did not teach it |
| All of Chapter 10 | 99 | `N/A` | Chapter states it is entirely a recommendation |
| A2A / ACP protocols | 26 | `N/A` | Recommended awareness; MCP must not be replaced |
| Research/performance report | 141 | `N/A` | "Highly recommended" |
| Tkinter/PyQt specifically | 70 | `N/A` | Example |
| ngrok/Localtonet specifically | 29 | `N/A` | Example tools |
| State-machine state names | 79, 80 | `N/A` | Sample code |
| Example repo as a base | 138 | `N/A` | **Explicitly forbidden** as a starting point |
| Docker, DBs, cloud infra | — | `N/A` | Never mentioned as requirements |
| Implementation status | — | `N/A` | No code exists yet |

---

## Part 5 — Architecture review for accidental non-compliance

Each item is a claim the architecture must survive, with the mechanism that
makes it true and the test that would catch a regression.

| Claim | Mechanism | Verdict |
|---|---|---|
| Live peer cannot access opponent's true position | `LocalState` has **no attribute** for it (D-9). Not `None`, not `Optional` — absent. A leak is an `AttributeError`. | ✅ |
| GUI cannot display global truth | GUI is constructed with handles to local-truth and belief modules only; no path to the network layer's decoded opponent data. Snapshot test on the render model. | ✅ |
| Replay is the only omniscient component | `replay/` imports nothing from the live path; reads sealed logs from disk after the match; derives trajectories rather than reading them. | ✅ |
| No hidden central game state | No module-level mutable state; role passed explicitly as a constructor argument, never read from a global; import-graph test asserts no cross-role import. | ✅ |
| Both peers symmetric | One program, one tool set, one state machine. ARC §5 tabulates exactly what the role changes (start cell, barrier permission, belief target, scoring) and what it does not (everything else). | ✅ |
| Logs sufficient for independent replay | **Was a gap.** PRO §11 now defines the schema and argues sufficiency line by line; new test hands the verifier only log + config. | ✅ *(fixed pass 2)* |
| Logs do not smuggle in global truth | Scent field and positions are **recomputed**, never stored (D-19). Nonce null until final reveal. | ✅ |
| No mandatory feature postponed too late | All mandatory features have a phase before submission. **Two adjustments made:** OAuth provisioning and opponent coordination moved to parallel start (D-20), since both have external latency. | ✅ *(adjusted pass 2)* |

One residual risk worth stating plainly: the architecture's compliance rests on
the strategy module never receiving opponent ground truth. That is currently
guaranteed by construction, but it is also the single seam where a future
optimisation ("just pass the state object through") would silently break E-9.
The structural test in AT §1 exists specifically to fail loudly if that happens.

---

## Part 6 — First coding task review

The audit brief asked six specific questions about Phase 0. Answers, all
verified against the PDF in pass 2:

**Exact paths.** Appendix B says `config/game.json` and `config/game.toml`
(PDF pp. 126, 130). Chapter 2 (p. 31) mandates separate config directories per
role, giving `/config/thief` vs `/config/police` **as an example**. We use
`config/police/…` and `config/thief/…`, which satisfies both. Recorded as our
reconciliation (D-18), not as the PDF's wording.

**Does JSON really override TOML?** Yes, stated directly at PDF p. 132: *"when
`config/game.json` exists, the match-condition values in it override every
parallel key in the TOML — so the private file can never 'weaken' a signed
condition."* Confirmed against the rendered page.

**Signed, hashed, or both?** **Both.** Appendix B: *"locked with a cryptographic
signature"* (p. 126) and canonically serialisable *"for a consistent hash
(`config_sha256`), for cryptographic signature, and for exchange between
machines"* (p. 127). Appendix F §2: *"lock them cryptographically"* (p. 156).
`config_sha256` is the PDF's own field name.

**What must be validated before the game starts.**

1. Schema: closed key set — reject unknown or renamed keys (p. 130, field names
   are binding).
2. All 32 Appendix F parameters present and typed.
3. Every FIXED parameter equals its tabulated value; every MINIMUM parameter is
   at or above it (E-12).
4. `config_sha256` matches the opponent's; otherwise **refuse to play** (E-11).
5. `scent_model_sha256` matches, including the numeric example (E-23).
6. `num_games` = 6 for any counting match (D-2).
7. `axis_origin_corner` and `axis_start_index` identical to the opponent's —
   otherwise one side's `[3,3]` is not the other's (p. 34).
8. Step-zero declarations exchanged before step 1 (E-24, E-53).

**Shared vs private ownership.** The PDF's own decision test (p. 128): *"must
the opponent agree to this value, or rely on it?"* — yes ⇒ shared JSON, no ⇒
private TOML. All 32 Appendix F parameters are shared. Private: group identity,
network port, opponent URL, strategy class, LLM provider and model, email
target, GUI settings. Tables 20–22 are reference only, not config.

**What must be agreed with the opponent** — five items, all blocking a counting
match: shared config values including `num_games` (Q-1); the sealed-record key
spelling (Q-4); the turn model (Q-2); capture resolution under simultaneity
(Q-9); the scent model with its numeric example (E-23). Plus the timeouts (Q-5).

---

## Part 7 — Cross-document consistency

| Check | Result |
|---|---|
| All 55 Appendix E IDs in REQ **and** AT | ✅ 55/55 |
| All 32 Appendix F parameters in PAR with value, type, unit, status, owner | ✅ 32/32 |
| Parameters referenced in ARC/PRO exist in PAR | ✅ no orphans |
| No Appendix F literal hard-coded as a requirement in ARC/PRO | ✅ all by code-name or config key |
| Every ARC §9 component has a TASKS phase | ✅ |
| Every TASKS phase has exit criteria and named tests | ✅ 12 phases |
| Every PRO tool appears in TASKS | ✅ 8/8 |
| Every OQ entry resolved-with-DEC, or flagged NEGOTIATE/ESCALATE | ✅ 14 entries |
| Every DEC resolving a contradiction cites its OQ ID | ✅ D-2,3,4,5,6,7,8 |
| New pass-2 findings propagated to all affected documents | ✅ F-1→REQ,AT; F-2→REQ,PAR,ARC,TASKS,AT; F-3→PRO,ARC,AT,TASKS,DEC; F-4→PAR,ARC,DEC; F-5→PAR,PRO,ARC |
| README doc table matches files in `docs/` | ✅ 8 documents |
| CLAUDE.md priority order matches DEC D-1 | ✅ |
| CLAUDE.md repo map matches ARC §9 | ✅ |
| `.gitignore` covers every secret named in the PDF | ✅ |
| `.gitignore` does not exclude artefacts that must be committed | ✅ explicit comment |
| Mandatory vs optional marked consistently in TASKS | ✅ `[M]`/`[O]`/`[P]` |
| Deviations from PDF's recommended order documented with rationale | ✅ TASKS Phases 4, 5, 8 |
| No MISSING item left without a TASKS entry | ✅ all three pass-2 gaps have Phase 0/2 tasks |

---

## Part 8 — Result

| Metric | Count |
|---|---|
| Appendix E rules found and verified | **55** (43 obligation, 11 prohibition, **1 recommendation**) |
| Binding parameters in Appendix F | **32** (14 FIXED, 9 MINIMUM, 9 NEGOTIABLE) |
| Status vocabularies used by the PDF | **3** (no DEFAULT, no OPTIONAL) |
| `COVERED` | **93** |
| `MISSING` | **0** (3 found in pass 2, all fixed in pass 2) |
| `AMBIGUOUS` | **5** (Q-2, Q-5, Q-8, Q-9, Q-12) |
| `CONTRADICTORY` | **4** (Q-1, Q-3, Q-4, Q-7 — all four resolved; 3 by the PDF's own text) |
| `N/A` | **10** |

**Unresolved and requiring outside input: one.** Q-12, the step-zero signing
key. The PDF says the declaration is signed *"with a pre-supplied key"* and
never says who supplies it, which algorithm, or how the counterpart verifies it.
An interim SHA-256 commitment is specified (D-8); **no key-distribution scheme
has been invented**. Ask the lecturer before the first counting match.

**Requiring agreement with each opponent: six** — shared config values including
`num_games` (Q-1), sealed-record key spelling (Q-4), turn model (Q-2), capture
resolution (Q-9), scent model with numeric example (E-23), timeouts (Q-5). These
are inherent to a judge-free protocol: both sides must compute identically, so
both must agree first. None blocks Phase 1 coding.
