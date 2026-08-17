# PARAMETERS — Appendix F, the Mandatory Parameter Table

Source: `police_thief_p2p.pdf`, **Appendix F** (PDF pp. 151–159 = book
pp. 135–143). `PDF page = book page + 16`.

> **Verification.** Every table below was re-verified in a second pass by
> rendering PDF pages 152–155 to images and reading them visually, rather than
> by text extraction. This matters: the PDF is right-to-left, and text
> extraction returns table cells out of order, which is exactly where a wrong
> value or a wrong status would hide. All 32 values, all statuses, all units and
> all parameter names below are confirmed against the rendered pages.

> Appendix F is **the single source of truth for every quantitative value in the
> project.** Throughout the book, numeric values do not appear as "hard" numbers
> in the body text but as an intuitive Hebrew **code-name enclosed in square
> brackets** — for example `[grid_size]`. The actual value is determined **only
> here**. (PDF p. 151)

---

## 1. How to read the "example value" column — this is critical

PDF p. 151 defines the reading rule, and PDF p. 155 defines the status column.
Getting this wrong is the single most likely way to build the wrong system.

> The values presented in the "example value" column **are the binding
> minimum**: it is **permitted** to raise them by mutual agreement between the
> two playing teams, but it is **forbidden** to lower them below this bar. A
> parameter marked *fixed* cannot be changed at all; a parameter marked
> *negotiable* is determined entirely in the negotiation stage between the
> sides, and the value shown is an example only.

So the column heading says "example value" but its contents are **not** in the
`EXAMPLE` (non-binding) class used in [REQUIREMENTS.md](REQUIREMENTS.md). They
are binding defaults. Precisely:

| Status | Hebrew | Binding meaning (PDF p. 155) |
|---|---|---|
| **MINIMUM** | מינימום | The sides may negotiate the value, **but only in the direction that makes the game harder** (usually increasing it) — never an easement below the tabulated value. **In the absence of an explicit agreed definition between the sides, the code must ensure the tabulated value is the default the team uses.** |
| **FIXED** | קבוע | A binding value that **cannot be changed at all**. Deviating from this value **disqualifies the team**. (The PDF bolds this sanction.) |
| **NEGOTIABLE** | משא ומתן | The sides may agree on **any** value. **In the absence of an explicit agreed definition between the sides, the code must ensure the tabulated value is the default the team uses.** |

**These are the only three statuses in the document.** Verified page by page
against the rendered tables in the second-pass audit. The PDF's own wording is
*"the status column in the tables above receives one of **three** values"*
(PDF p. 155). There is **no** `DEFAULT` status and **no** `OPTIONAL` status
anywhere in Appendix F; any such label appearing in project documentation would
be invented. `NEGOTIABLE` is the closest thing to "default" — and note that under
all three statuses the tabulated value functions as the code's default.

**Field names are fixed and binding (PDF p. 130).** Distinct from the value
statuses, and easy to miss: *"every field value may change by negotiation (in
the stricter direction only, for a parameter of type 'minimum'), **but the field
names are fixed and binding**."* Negotiation may change what a value is; it may
never rename a key or restructure the object. The config loader must therefore
treat the key set as a closed schema and reject unknown or renamed keys.

**Consequence for implementation.** For all three statuses the tabulated value is
the code's default. Therefore:

- Every one of these values **must be read from configuration**, never
  hard-coded in game logic. (Project rule; also implied by E-11/E-12.)
- The shipped default configuration **must** carry exactly these values.
- Validation code **must** reject a loaded config that lowers a `MINIMUM` value
  or alters a `FIXED` value.

---

## 2. Configuration file ownership

Appendix B (PDF pp. 126–132) defines which file owns which parameter. The
decision test the PDF gives (PDF p. 128) is:

> Ask: *"must the opponent agree to this value, or rely on it?"* — if yes, its
> place is in the shared JSON; if not, it stays in the private TOML.

| File | Format | Scope | Signed? | Crosses the network? |
|---|---|---|---|---|
| `config/game.json` | **JSON** | The **shared constitution**: agreed match conditions, identical byte-for-byte on both sides | **Yes**, cryptographically locked | Yes — exchanged and hashed |
| `config/game.toml` | **TOML** | **Private, local** per-peer settings only | No | **No** |

**On the exact paths.** Appendix B names the files `config/game.json` and
`config/game.toml` (PDF pp. 126, 130) — with no role sub-directory. Separately,
Chapter 2 (PDF p. 31) requires the two roles to run *"under separate
configuration directories — **for example** `/config/thief` versus
`/config/police`"*. The word is "for example"; the *separation* is mandatory,
the specific paths are not. This repository reconciles the two as
`config/police/game.json` and `config/thief/game.json`, preserving both the
Appendix B filenames and the Chapter 2 separation. That reconciliation is our
choice, not the PDF's wording — recorded as [DECISIONS.md](DECISIONS.md) D-18.

**Signed, hashed, or both? Both.** Appendix B is explicit on each:
*"loaded byte-identically at both ends and **locked with a cryptographic
signature**"* (PDF p. 126), and JSON was chosen because it is
*"canonically serialisable (sorted keys) and therefore suited to byte-for-byte
identity, to a consistent hash (**`config_sha256`**), to cryptographic signature,
and to exchange between machines and between teams"* (PDF p. 127). Appendix F §2
adds *"verify these values are identical between the two teams, and **lock them
cryptographically**"* (PDF p. 156). `config_sha256` is therefore **the PDF's own
field name**, not one we coined.

Why JSON for the shared file (PDF p. 127): it is an unambiguous, cross-language
standard, **canonically serialisable** (sorted keys), and therefore suited to
byte-for-byte identity, to a consistent `config_sha256` hash, to cryptographic
signature, and to exchange between machines and between teams who may have
written their code in different languages. **Anything the opponent sees, verifies
or relies on must be here.**

Why TOML for the private file (PDF p. 127): it is **hand-edited** by each team,
especially readable, and **supports comments** — a decisive advantage, since the
`[strategy]` and `[trash_talk]` sections carry explanatory notes guiding the
student. This file **does not cross the network** and is not signed, so it needs
no canonical or hashable form. **No value relevant to the opponent is found in
it**; if a value becomes shared, it moves to the JSON.

**Override direction (PDF pp. 126, 132).** Where `config/game.json` exists, its
values **override** (overlay) the values of the same keys in the private TOML,
**so the private file can never "weaken" a signed condition.**

---

## 3. Table 13 — Board, axis system and start positions

*PDF p. 152.* Owner: `config/game.json` → `board_and_agents` (and `world` for
table 14).

| # | Code-name | JSON key | Meaning | Value | Type | Status |
|---|---|---|---|---|---|---|
| 1 | `[grid_size]` | `board_and_agents.grid_size` | Side of the square game grid | `7` (i.e. 7×7) | int | **MINIMUM** |
| 2 | `[num_agents]` | `board_and_agents.num_agents` | Number of players in the race | `2` | int | **FIXED** |
| 3 | `[axis_origin_corner]` | `board_and_agents.axis_origin_corner` | The corner in which cell (0,0) sits | `"top-left"` | string | **NEGOTIABLE** |
| 4 | `[axis_start_index]` | `board_and_agents.axis_start_index` | The number at which each axis starts counting | `0` | int | **NEGOTIABLE** |
| 5 | `[thief_start]` | `board_and_agents.thief_start` | The thief's start cell (centre) | `[3, 3]` | [int, int] | **NEGOTIABLE** |
| 6 | `[cop_start]` | `board_and_agents.cop_start` | The cop's start cell (corner) | `[0, 0]` | [int, int] | **NEGOTIABLE** |

Notes.

- `grid_size` is a **MINIMUM**: 7×7 is the floor, larger is permitted by mutual
  agreement. Any 10×10 grid appearing in the book's abstract, in the belief-map
  figure (PDF p. 64) or in Chapter 6's text is illustrative, not a requirement.
- Although `axis_origin_corner` and `axis_start_index` are NEGOTIABLE, Chapter 3
  (PDF p. 34) makes it **mandatory** that both sides hold **identical** values,
  otherwise one side's `[3,3]` is not the other's and the race falls apart.
- `thief_start` / `cop_start` are NEGOTIABLE and are determined in the
  negotiation stage; any legal agreed layout is permitted (PDF p. 35).

## 4. Table 14 — Game arena and verbal hints

*PDF p. 152.* Owner: `config/game.json` → `world`.

| # | Code-name | JSON key | Meaning | Value | Type | Status |
|---|---|---|---|---|---|---|
| 1 | `[map_area]` | `world.map_area` | The real-world region in which the game takes place — feeds real landmarks into the verbal hints. Empty (`""`) = generic landmarks | `"New York"` | string | **NEGOTIABLE** |
| 2 | `[hint_max_words]` | `world.hint_max_words` | Maximum number of words in each verbal hint sent over the network — applies to the **template mode and to the language model alike** (told to it in its system prompt) | `15` | int | **NEGOTIABLE** |

## 5. Table 15 — Movement and barriers

*PDF p. 153.* Owner: `config/game.json` → `movement_and_barriers`.

| # | Code-name | JSON key | Meaning | Value | Type | Status |
|---|---|---|---|---|---|---|
| 1 | `[move_set]` | `movement_and_barriers.move_set` | A single orthogonal move or standing still; **no diagonals** | `4 + STAY` → `["N","S","E","W","STAY"]` | list[string] | **FIXED** |
| 2 | `[max_barriers]` | `movement_and_barriers.max_barriers` | The maximum number of barriers the cop is entitled to place | `14` | int | **MINIMUM** |
| 3 | `[max_moves]` | `movement_and_barriers.max_moves` | The maximum number of moves in a sub-game | `35` | int | **MINIMUM** |
| 4 | `[survival_threshold]` | `movement_and_barriers.survival_threshold` | Steps the thief must survive to win | `35` | int | **MINIMUM** |

Note: Appendix F table 15 row 1 expresses the value as "4 + standing"; the shared
config in Appendix B (PDF p. 129) spells it as
`["N", "S", "E", "W", "STAY"]`. Status **FIXED** — the move set cannot be
changed at all.

## 6. Table 16 — Dynamic pheromones

*PDF p. 153.* Owner: `config/game.json` → `pheromones`.

| # | Code-name | JSON key | Meaning | Value | Type | Status |
|---|---|---|---|---|---|---|
| 1 | `[pheromone_center_intensity]` | `pheromones.pheromone_center_intensity` | Pheromone intensity in the emitting cell | `0.9` | float | **FIXED** |
| 2 | `[pheromone_decay]` | `pheromones.pheromone_decay` | Decay rate per turn (ρ) | `0.10` | float | **FIXED** |
| 3 | `[pheromone_grid_size]` | `pheromones.pheromone_grid_size` | Side of the emission window around the agent | `5` (i.e. 5×5) | int | **FIXED** |

All three are **FIXED** — deviation disqualifies. These are also the values that
E-23 requires to be cryptographically locked, together with the decay formula
and a concrete numeric example, before the series opens (PDF p. 47).

## 7. Table 17 — Scoring (win, survival, tie)

*PDF p. 154.* Owner: `config/game.json` → `scoring`.

| # | Code-name | JSON key | Meaning | Value | Type | Status |
|---|---|---|---|---|---|---|
| 1 | `[capture_cop]` | `scoring.capture_cop` | Score to the cop on a successful capture | `20` | int | **FIXED** |
| 2 | `[capture_thief]` | `scoring.capture_thief` | Score to the thief on a capture | `5` | int | **FIXED** |
| 3 | `[survival_cop]` | `scoring.survival_cop` | Score to the cop when the thief survives | `5` | int | **FIXED** |
| 4 | `[survival_thief]` | `scoring.survival_thief` | Score to the thief on successful survival | `10` | int | **FIXED** |
| 5 | `[tie_score]` | `scoring.tie_score` | Score to **each** side when the accumulated score of **all sub-games** against an opponent ends in a tie | `2` | int | **FIXED** |

**`technical_loss` is NOT in Appendix F table 17.** The key
`scoring.technical_loss: 0` appears in the Appendix B shared-config example
(PDF p. 129), and the value `0/0` appears in Chapter 3's scoring table
(PDF p. 38) and in rule E-48 (PDF p. 149). Since Appendix F does not tabulate it,
it carries no Appendix F status. See [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-3.

## 8. Table 18 — Network and league

*PDF p. 154.* Owner: `config/game.json` → `network_and_league`.

| # | Code-name | JSON key | Meaning | Value | Type | Status |
|---|---|---|---|---|---|---|
| 1 | `[num_sub_games]` | `network_and_league.num_games` | Sub-games in a series against **one** opponent | `6` | int | **FIXED** |
| 2 | `[diversity_reward]` | `network_and_league.diversity_reward` | Score for a victory against a **new** opponent | `10` | int | **FIXED** |
| 3 | `[min_games_to_pass]` | `network_and_league.min_games_to_pass` | The minimum number of matches per team required to obtain a passing grade in the project | `2` | int | **FIXED** |
| 4 | `[token_budget_per_series]` | `network_and_league.token_budget_per_series` | Total LLM tokens each team is entitled to consume; **actual consumption is reported by email** | `~200000` | int | **NEGOTIABLE** |
| 5 | `[max_games_per_team]` | `network_and_league.max_games_per_team` | The maximum number of matches each team is entitled to play | `10` | int | **FIXED** |

**Terminology, and a genuine conflict.** The PDF distinguishes משחק (*match*, a
whole encounter against one opponent) from משחקון (*sub-game*, one race within
that encounter). Row 1 counts **sub-games**; rows 3 and 5 count **matches**. So:
a match against one opponent consists of `num_games = 6` sub-games; you must play
at least `2` matches against different groups and at most `10` matches.

Appendix F says `num_games` is `6` and **FIXED**. The Appendix B example config
(PDF p. 129) ships `"num_games": 1`, and its accompanying text (PDF p. 130) —
verified verbatim against the rendered page in the second-pass audit — says:
*"the `num_games` field is sent by default with the value 1 (a single example
sub-game); the full league series requires `[num_sub_games]` sub-games."*

**The PDF resolves the usage question itself.** That sentence states directly
that 1 is a single demonstration sub-game and that a full league series requires
`[num_sub_games]` = 6. So there is no ambiguity about what to run in a league
match. What remains inconsistent is only the *status label*: a value cannot
literally be FIXED at 6 while the shipped example carries 1. Since Appendix F is
the binding source and its narrative agrees, **6 is used for every counting
match**; 1 is a demo convenience with no league standing. See
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-1 and
[DECISIONS.md](DECISIONS.md) D-2.

Note also that `token_budget_per_series` is tabulated with a tilde (`~200000`),
signalling an estimate; its status is NEGOTIABLE.

## 9. Table 19 — Network, rate limiter and protection (the Gatekeeper pattern)

*PDF p. 155.* Owner: rows 1–5 → `config/game.json` → `rate_limiter_gatekeeper`;
rows 6–7 → `config/game.json` → `network_and_league`.

| # | Code-name | JSON key | Meaning | Value | Type | Status |
|---|---|---|---|---|---|---|
| 1 | `[requests_per_minute]` | `rate_limiter_gatekeeper.requests_per_minute` | Maximum rate of outgoing API requests | `30` | int | **MINIMUM** |
| 2 | `[concurrent_requests]` | `rate_limiter_gatekeeper.concurrent_requests` | Maximum number of concurrent requests | `2` | int | **MINIMUM** |
| 3 | `[retry_backoff_sec]` | `rate_limiter_gatekeeper.retry_backoff_sec` | Wait before a retry | `5` sec | int | **MINIMUM** |
| 4 | `[max_retries]` | `rate_limiter_gatekeeper.max_retries` | Number of attempts before failure | `3` | int | **MINIMUM** |
| 5 | `[queue_depth]` | `rate_limiter_gatekeeper.queue_depth` | Request-queue size under load | `100` | int | **MINIMUM** |
| 6 | `[response_timeout_sec]` | `network_and_league.response_timeout_sec` | Timeout for each network request | `30` sec | int | **NEGOTIABLE** |
| 7 | `[watchdog_timeout_sec]` | `network_and_league.watchdog_timeout_sec` | Freeze time until Watchdog intervention | `60` sec | int | **NEGOTIABLE** |

**Careful with the MINIMUM semantics on rows 1–5.** "Minimum" here means the
*tabulated number is the floor of the parameter value*, and negotiation may only
move it in the direction that makes the game harder. For a rate limit, a *higher*
`requests_per_minute` is a *looser* limit — so the direction of "harder" is
worth confirming with the opponent rather than assumed. See
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-8.

---

## 10. Table 20 — Attached files, repository and addresses

*PDF p. 157.* **Reference table only** — the PDF states explicitly it is *not*
part of the agreed configuration file and is *not* subject to negotiation.

File names derive from the match identifier (`game_id`) and the sub-game number
(`<NN>`), so files from different matches never get mixed up.

| Variable | Role and content | Value |
|---|---|---|
| `[declaration_file]` | Pre-match declaration: all constant data of the match — teams, members, repositories, hardware, model, tokens and times | `declaration_<game_id>.json` |
| `[config_file]` | The agreed configuration: cryptographically locked sub-game parameters | `config_<game_id>_g<NN>.json` |
| `[log_file]` | The sub-game log, for cryptographic verification in the replay simulator | `log_<game_id>_g<NN>.json` |
| `[result_file]` | The final results report, for the lecturer to weight the league score | `result_<game_id>.json` |
| `[example_repo]` | The reference implementation of the game on GitHub | `https://github.com/rmisegal/Game-P2P-Cop-Chase` |
| `[lecturer_address]` | General mail and GitHub repository sharing | `rmisegal@gmail.com` |
| `[agent_reporting_address]` | Destination for the JSON reports the agent sends automatically | `rmisegal+uoh26finalgame@gmail.com` |

## 11. Table 21 — LLM modes for the verbal game

*PDF p. 158.* **Reference table only** — a **private choice per peer**, not part
of the agreed configuration file and not subject to negotiation. Owner:
`config/game.toml` → `[trash_talk] provider`.

All four modes concern **only the deception text**; *the move decision is always
algorithmic and in Python code*.

| Mode | Where it runs / token cost | Rate limit | Account and installation |
|---|---|---|---|
| `template` | In-process; sentences prepared in advance in code — **zero tokens**. **The default.** | None | None; offline and free |
| `ollama` | Local model at `localhost:11434` — **zero API tokens** | None | Ollama installation and model pull |
| `claude_api` | Small cloud model (e.g. Haiku) via the API — real consumption counted against `[token_budget_per_series]` | Per the account | Anthropic API key (paid account) |
| `claude_cli` | `claude -p` via the Claude Code CLI — the highest cost | Per the subscription | Login to Claude CLI (subscription) |

The `every_n_steps` parameter invokes the model only once every few turns,
reducing consumption further. **In `template` and `ollama` modes the entire
`[num_sub_games]`-sub-game series can be played at zero tokens**, and the whole
competition moves to the quality of the movement algorithm.

## 12. Table 22 — Strategy module selection

*PDF p. 159.* **Reference table only** — a **private choice per peer**, not
subject to negotiation. Owner: `config/game.toml` → `[strategy]`.

Movement policy is described by the PDF as **the core of the grade**.

| Key (`[strategy]`) | Role | How to override |
|---|---|---|
| `thief_class` | Your thief brain, written `package.module:Class` | Implement `police_thief.strategy.base.BaseStrategy`: a `name` attribute and `choose(view: LocalView) -> Action` |
| `police_class` | Your cop brain, likewise | `choose` returns either a `Move` or a `PlaceBarrier` — the cop's barrier is chosen the same way a move is |

Leaving the section empty runs the heuristic brain built into the reference
implementation. The class named must be constructible with no arguments;
`strategy/heuristics.py::load_strategy()` imports it, instantiates it, and
checks it has a callable `choose` and a `name` before accepting it —
otherwise it raises `StrategyLoadError` at startup rather than silently
falling back to the shipped heuristic (D-43). Earlier drafts of this table
described a `BrainBase` class with `_pick_move`/`_decide_move` methods; that
was the original plan and was never built. What ships is the `BaseStrategy`
protocol above — one method, `choose`, deciding both movement and (for the
cop) barrier placement.

---

## 13. Appendix F §2 — mandatory instructions accompanying the table

*PDF p. 156.* These are obligations, not parameters:

1. Every team **must define all** of the above values in the configuration file.
2. Teams **must verify these values are identical** between the two teams, and
   **lock them cryptographically**.
3. In each new match a team **may** change the settings, as long as they conform
   to the agreement with the opposing team.
4. Each configuration file **must be given a different name** according to the
   match, to permit easy reconstruction of each match's configuration.
5. It is **mandatory to attach each match's configuration file to the GitHub
   repository**.
6. Each team may change code between matches; therefore **for each match an
   email must be sent to the lecturer containing the GitHub commit number** used
   in that match.

---

## 14. Consolidated shared config skeleton

Reproduced from Appendix B (PDF pp. 129–130) with the Appendix F values applied.
`schema_version` and `agreed_between` are structural fields from Appendix B, not
Appendix F parameters. **`num_games` is set to the Appendix F value of 6, not
the example file's 1** — see §8 above.

```json
{
  "schema_version": "1.2",
  "agreed_between": ["group-a", "group-b"],
  "board_and_agents": {
    "grid_size": 7,
    "num_agents": 2,
    "thief_start": [3, 3],
    "cop_start": [0, 0],
    "axis_origin_corner": "top-left",
    "axis_start_index": 0
  },
  "world": {
    "map_area": "New York",
    "hint_max_words": 15
  },
  "movement_and_barriers": {
    "move_set": ["N", "S", "E", "W", "STAY"],
    "max_barriers": 14,
    "max_moves": 35,
    "survival_threshold": 35
  },
  "scoring": {
    "capture_cop": 20, "capture_thief": 5,
    "survival_cop": 5, "survival_thief": 10,
    "tie_score": 2, "technical_loss": 0
  },
  "pheromones": {
    "pheromone_center_intensity": 0.9,
    "pheromone_decay": 0.10,
    "pheromone_grid_size": 5
  },
  "network_and_league": {
    "response_timeout_sec": 30, "watchdog_timeout_sec": 60,
    "num_games": 6, "diversity_reward": 10,
    "min_games_to_pass": 2, "max_games_per_team": 10,
    "token_budget_per_series": 200000
  },
  "rate_limiter_gatekeeper": {
    "requests_per_minute": 30, "concurrent_requests": 2,
    "retry_backoff_sec": 5, "max_retries": 3, "queue_depth": 100
  }
}
```

## 15. Private per-peer TOML skeleton

Reproduced from Appendix B (PDF p. 131). **None of these are Appendix F
parameters** except where they shadow a JSON key (in which case the JSON wins).
This file never crosses the network and is never signed.

```toml
version = "1.10"

[game]
group_name = "My-Team"
group_id   = "my-team"          # 8 chars, no spaces (E-45)
sub_game_number = 1
members = ["id-1001", "id-1002"]
repos = { cop = "https://github.com/you/cop-repo",
          thief = "https://github.com/you/thief-repo" }

[network]
my_port = 8802                              # MY MCP server port
opponent_url = "http://127.0.0.1:8801/mcp"  # the only thing I know about the opponent
turn_timeout_seconds = 180

# [strategy] -- optional: point at YOUR brain subclass (else the shipped heuristic runs)
# thief_class  = "my_team.strategy:MyThiefBrain"
# police_class = "my_team.strategy:MyPoliceBrain"

# [trash_talk] -- optional: HOW the banter is produced. The MOVE is always pure Python.
# provider = "template"   # template(0 tokens, default) | ollama | claude_api | claude_cli

[llm]
model = "claude-opus-4-8[1m]"   # MY choice; the opponent may differ
step_deadline_seconds = 30      # hard cap on LLM thinking per step

[email]
recipient = "rmisegal+uoh26finalgame@gmail.com"
mode = "draft"
```

Two items in this skeleton need attention before use:

- `turn_timeout_seconds = 180` sits alongside the shared
  `response_timeout_sec = 30` and `watchdog_timeout_sec = 60`, and the Chapter 8
  watchdog sample uses `timeout_sec=180`. Which governs a turn is not stated.
  See [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-5.
- `mode = "draft"` conflicts with E-32/E-51, which require the report to be
  **sent** to the lecturer. See [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-7.
