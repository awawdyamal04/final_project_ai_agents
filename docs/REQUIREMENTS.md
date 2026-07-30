# REQUIREMENTS — Distributed Cops-and-Robbers over P2P

Extracted from `police_thief_p2p.pdf` (book version 3.0.0, Dr. Yoram Segal,
University of Haifa, Dept. of Computer Science, 2026).

## How to read this document

**Page references.** The PDF viewer's page number and the printed book page
number differ by a constant 16 (`PDF page = book page + 16`). All references
below are given as **PDF p. N** — the number your viewer shows.

**Classification.** Every item is tagged:

| Tag | Meaning |
|---|---|
| `MANDATORY` | The PDF states it as a binding rule (חובה / איסור), or it is a threshold condition for submission. |
| `RECOMMENDED` | The PDF marks it המלצה / מומלץ / מומלץ מאוד. Not binding. |
| `EXAMPLE` | Illustration, diagram, sample code, or scenario. **Not binding.** |

**The default is NOT binding.** PDF p. 4 states this as the founding principle:
*a rule is not binding unless it is explicitly written to be a rule.* All
illustrations, examples, code excerpts and scenarios in the book are a *mode of
demonstration* and do not constitute game rules unless explicitly marked as
part of the rules. Where the book does not say a rule is binding, each side may
agree with its opponent on different behaviour.

**Source of truth for numbers.** The only source of obligation for quantitative
values is the *Mandatory Parameter Table* in **Appendix F** (PDF pp. 151–159).
See [PARAMETERS.md](PARAMETERS.md). Numeric literals appearing in the body text
are code-names in square brackets, never hard numbers.

**Academic freedom on contradiction (PDF p. 5).** Where the book contradicts
itself, the student may choose one of the readings and proceed, **provided the
choice is stated explicitly in the report**: where the contradiction was
identified, what was chosen, and why. A reasoned, documented choice is not held
against the team. This does not extend to Appendix F, which remains the single
binding source for numeric values. Our exercised choices are recorded in
[DECISIONS.md](DECISIONS.md) and [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

---

## 0. Rule index (Appendix E)

Appendix E (PDF pp. 142–150) consolidates the binding rules into one categorical
checklist of **55 numbered rules**, in six tables, each with an explicit
sanction. Rule numbers below (`E-1` … `E-55`) are the PDF's own numbering and
are used throughout this repository as the canonical requirement IDs.

Appendix E's own framing (PDF p. 142): non-compliance carries clear systemic
meaning — *from disqualification, through technical loss, to loss of points*.

Note that **exactly one** of the 55 entries is classified by the PDF itself as a
recommendation rather than an obligation: **E-25** (do not let the LLM decide
the move). Every other entry is חובה (obligation) or איסור (prohibition).

---

## 1. Network architecture, decentralisation and local epistemology

*Appendix E table 7 (PDF pp. 142–144); Chapter 2 (PDF pp. 24–32); Chapter 7
(PDF p. 70); Chapter 8 (PDF pp. 77–84).*

| ID | Requirement | Class | Sanction (as stated) | Source |
|---|---|---|---|---|
| E-1 | Run the thief code and the cop code in **two entirely separate processes**. | MANDATORY | Total failure; breaks the Zero-Trust model. | PDF p. 142 |
| E-2 | **Never** share memory or variables between the two sides. | MANDATORY (prohibition) | Immediate disqualification of the solution for information leakage. | PDF p. 143 |
| E-3 | Define the **orchestrator component as the single entry point** to all sub-systems. | MANDATORY | Technical instability and loss. | PDF p. 143 |
| E-4 | Manage game states with a **proper state machine**. | MANDATORY | Technical loss resulting from a deadlock in the system. | PDF p. 143 |
| E-5 | **Reject every attempt at an illegal state transition** in the state machine. | MANDATORY | Logic error leading to a loss. | PDF p. 143 |
| E-6 | Implement a **deadline-tracking mechanism** to prevent freezing while waiting for the opponent. | MANDATORY | System paralysis and loss on time (timeout). | PDF p. 143 |
| E-7 | Operate a **watchdog** to monitor process crashes and extract data in a controlled way. | MANDATORY | Game crash and loss of official documentation. | PDF p. 143 |
| E-8 | Display **local truth only** in the live user interface. | MANDATORY | Disqualification of the system's legality due to an information breach. | PDF p. 143 |
| E-9 | **Never** display the full objective board state in the live interface. | MANDATORY (prohibition) | Disqualification of the project for an illegal advantage. | PDF p. 143 |
| E-10 | Use a **tunnelling tool** to expose the local server to the public internet. | MANDATORY | Inability to compete in the league against opponents. | PDF p. 144 |

**Supporting detail (Chapter 2).**

- Each agent is **simultaneously a FastMCP server and a client**. There is no
  "strong" side and "weak" side; the two peers are completely equivalent in
  their network role. `MANDATORY` (architecture), PDF pp. 25–26.
- Separate configuration directories per side, e.g. `/config/thief` vs
  `/config/police`. The specific paths are `EXAMPLE`; the *separation* is
  `MANDATORY`. PDF p. 31.
- Prohibited in the strongest terms: sharing memory, importing a shared module
  that holds live state, or reading shared variables between the two sides.
  Such sharing grants one side access to the other's "local truth", breaks the
  Zero-Trust model, and disqualifies the solution — *even if the game "works"
  technically*. `MANDATORY`, PDF p. 31.
- Running the servers on `localhost` is permitted **only** in early coding
  stages. In the live league every team **must** expose its FastMCP server to
  the public internet via a tunnelling tool. `ngrok` / `Localtonet` are named as
  `EXAMPLE` tools. PDF p. 29.
- Tunnel resilience is part of game resilience: if one tunnel drops, the
  counterpart loses the ability to verify moves and reaches a deadlock in turn
  scheduling. `RECOMMENDED` framing, PDF p. 30.

**Local truth (Chapter 7, PDF p. 70).** A design principle: each agent's
interface shows only the information accessible *to it* — its own position, the
scent map it senses, and the hints it received — and **never** the full
objective board state. There is no bird's-eye view showing both sides'
positions simultaneously. This follows directly from the Dec-POMDP formalism:
observation Ωᵢ is a partial subset of the true state S, so an interface exposing
the full S would violate the rules of the game. `MANDATORY`.

**Orchestrator and state machine (Chapter 8, PDF pp. 78–80).** The orchestrator
is a central software component acting as a single gateway to all of the agent's
sub-systems. It initialises connections, invokes the decision module,
coordinates between components and communicates with the log managers — but
contains **no decision logic or low-level communication of its own**. Its job is
to coordinate, not to execute. The five sub-systems it fronts are: MCP
Connector, Decision Module, Log Manager, Deadline Tracker, Watchdog.

The legal state machine for a single game turn (PDF p. 79, figure 11) is given
as: `WAITING_FOR_OPPONENT` → `COMPUTING_MOVE` → `COMMITTING` →
`AWAITING_REVEAL` → `VERIFYING` → back to `WAITING_FOR_OPPONENT`, with
`TECHNICAL_LOSS` as a terminal error state reachable from the communication
phases. The specific state *names* and the transition table are `EXAMPLE`
(sample code, PDF p. 80); having *a* proper state machine that rejects illegal
transitions is `MANDATORY` (E-4, E-5).

**Deadline tracker vs watchdog (PDF p. 81).** Distinct responsibilities:
the deadline tracker guards a *single request* (every request over the FastMCP
server carries a timestamp and an expiry deadline; on expiry the system retries
or declares technical loss); the watchdog guards *the whole system* (an
independent background process monitoring the main game loop for a heartbeat,
performing a controlled shutdown and state persistence if the system freezes).
A missed deadline **must** be treated as a failure, not as an invitation to wait
longer. `MANDATORY` (E-6, E-7).

---

## 2. Spatial mechanics, physics and board constraints

*Appendix E table 8 (PDF pp. 144); Chapter 3 (PDF pp. 33–39); Appendix E table
12 rules 46–48 (PDF p. 149).*

| ID | Requirement | Class | Sanction (as stated) | Source |
|---|---|---|---|---|
| E-11 | Verify the configuration file is **completely identical, byte-for-byte**, on both sides. | MANDATORY | Disqualification of the match for breaking symmetry. | PDF p. 144 |
| E-12 | Raise minimum values in the parameter table **by agreement only**; **never** lower them. | MANDATORY | Breach of the threshold conditions, leading to disqualification of the score. | PDF p. 144 |
| E-13 | Move **only** in orthogonal directions. | MANDATORY | Illegal move and technical loss. | PDF p. 144 |
| E-14 | **No** diagonal moves. | MANDATORY (prohibition) | Rejection of the move by the opponent and a loss. | PDF p. 144 |
| E-15 | **Declare openly** every barrier placement. | MANDATORY | Board forgery and automatic loss at audit. | PDF p. 144 |
| E-16 | **Never** lie about the barrier placement location. | MANDATORY (prohibition) | Severe grounds for disqualification. | PDF p. 144 |
| E-46 | A barrier placed on the cell where the thief stands at that moment **counts as a capture** (the cop wins). | MANDATORY | — (source: Chapter 3) | PDF p. 149 |
| E-47 | A thief trapped with **no legal move whatsoever** is likewise considered captured. | MANDATORY | — (source: Chapter 3) | PDF p. 149 |
| E-48 | Score **every** end scenario according to the scoring table and the parameter table. | MANDATORY | — (source: Chapter 3) | PDF p. 149 |

**Supporting detail (Chapter 3).**

- The arena is a **discrete** finite grid. Physics is enforced by the agents
  themselves, each in its turn, according to a pre-agreed configuration file
  (`config/game.json`) shared byte-identically. There is **no external judge**.
  `MANDATORY`, PDF p. 34.
- **Both sides must agree on the same transition function.** Chapter 1
  (PDF p. 21), describing the `P` component of the Dec-POMDP octuple, states:
  *"since there is no central server, both sides must agree on that same
  transition function — it is encoded in the shared configuration file."*
  `MANDATORY`. This is the formal statement of what E-11 enforces
  mechanically, and it is why the config hash is a precondition for play rather
  than a nicety: an identical config **is** an identical physics engine.
  *(Added in the second-pass audit — previously implied by E-11 but not stated.)*
- The contract is set by **negotiation** between each pair of teams and may
  therefore differ from pair to pair. It **must** be mutually agreed. It **must
  not weaken or dilute** the instructions defined in the book: *the agreed
  contract is a floor, not a ceiling*. Teams **may** (and are encouraged to)
  upgrade the rules and legally exploit any gap not defined in the book, for
  mutual benefit or competitive advantage — as long as everything is legal and
  agreed between the sides. `MANDATORY` (floor) + `RECOMMENDED` (upgrading),
  PDF p. 34.
- Each cell is represented as a `(row, col)` pair. Two negotiated parameters fix
  how the pair is read: `[axis_origin_corner]` (the corner holding cell (0,0);
  default top-left, with the vertical axis growing downward) and
  `[axis_start_index]` (the number each axis starts counting from; default 0).
  Both are negotiable **but must be identical** between the sides, otherwise
  one side's `[3,3]` is not the other's `[3,3]` and the race falls apart.
  `MANDATORY` (identity), PDF p. 34.
- Start positions are **not random and not fixed in advance**: they are
  determined in the negotiation stage, and any legal agreed layout is permitted.
  The thief-in-centre / cop-in-corner layout is explicitly labelled an example
  only. `MANDATORY` (negotiated) / `EXAMPLE` (the specific layout), PDF p. 35.
- Legal move set: one cell in one of the four orthogonal directions (up, down,
  left, right), **or** staying in place. Diagonal movement is forbidden.
  `MANDATORY`, PDF p. 37.

**The barrier rule (PDF p. 37), stated as a rule box:**

> On a turn where the cop **forgoes movement**, it may place a barrier on any
> cell within one step of it — the cell it stands on itself, or one of the four
> orthogonally adjacent cells — and that cell becomes **impassable to both
> players until the end of the game**. A barrier is irreversible: a blocked cell
> stays blocked. **Trapping placement:** if the cop places a barrier on the cell
> where the thief stands, the thief is captured at that moment. Likewise, a
> thief imprisoned with no legal move (all adjacent cells blocked by barriers
> and/or board edges) is also considered captured. **Declaration duty:** the cop
> must truthfully declare every barrier placement and its exact location; it may
> not place a barrier covertly, and may not lie about its location.

The cop's maximum barrier quota is `[max_barriers]`; every placement is
therefore a resource-management decision. `MANDATORY`.

**Iron rules — movement and truthful declaration (PDF p. 38).** A diagonal move
is illegal; an attempt to perform one is rejected by the opposing agent, which
enforces the physics. When the cop declares a Capture Claim, a **cryptographic
obligation** falls on the thief to answer truthfully; an attempt to lie at this
stage will necessarily be exposed at the audit-log stage and will entail
absolute systemic disqualification. `MANDATORY`.

**Scoring table (Chapter 3, table 2, PDF p. 38).** `MANDATORY` (E-48):

| End event | Win condition | Cop score | Thief score |
|---|---|---|---|
| Successful capture | The cop lands on the thief's cell and declares a Capture Claim | `[capture_cop]` | `[capture_thief]` |
| Prolonged survival | The thief survives `[survival_threshold]` valid steps without capture | `[survival_cop]` | `[survival_thief]` |
| Technical loss | A side crashes, exceeds time, or performs a cryptographic forgery | 0 | 0 |

The broken symmetry is deliberate: capture gives the cop its highest reward;
prolonged survival gives the thief *its* highest reward. Technical loss zeroes
**both** sides, incentivising both to preserve protocol correctness rather than
win "on a timeout". PDF pp. 38–39.

---

## 3. Cryptography, log integrity and zero-knowledge

*Appendix E table 9 (PDF p. 145); Chapter 5 (PDF pp. 48–56); Chapter 4 (PDF
p. 47); Chapter 7 (PDF pp. 72–75).*

| ID | Requirement | Class | Sanction (as stated) | Source |
|---|---|---|---|---|
| E-17 | Use a **commit-reveal protocol based on SHA-256**. | MANDATORY | Absence of the mechanism renders the solution illegal. | PDF p. 145 |
| E-18 | Keep the **nonce absolutely secret until the end of the game**. | MANDATORY | Disqualification of the defence due to the risk of a dictionary attack. | PDF p. 145 |
| E-19 | **Technically disqualify** the match on any hash mismatch at the audit stage. | MANDATORY | Iron rule dictating a score of **0** for the forging team. | PDF p. 145 |
| E-20 | Build a **viewer application to replay and verify the game log**. | MANDATORY | Threshold condition for approving audits and for submitting the project. | PDF p. 145 |
| E-21 | Declare **truth only** when a thief is caught. | MANDATORY | Immediate disqualification for denial of reality. | PDF p. 145 |
| E-22 | **Never** falsely declare a capture; a false declaration entails immediate disqualification. | MANDATORY (prohibition) | Score zero and technical loss with no right of appeal. | PDF p. 145 |
| E-23 | **Cryptographically lock the scent emission model before the game starts.** | MANDATORY | A deviation in the decay formula voids the match. | PDF p. 145 |
| E-24 | Perform a **cryptographic hardware declaration before the game starts**. | MANDATORY | Forfeiture of eligibility for the computational-fairness bonus. | PDF p. 145 |
| E-53 | Record in the **step-zero declaration the commit hash** that was played. Code may be changed between matches, but every match **must** update the commit identifier. | MANDATORY | — (source: Chapter 5) | PDF p. 150 |

**The commit-reveal mechanism (Chapter 5, PDF pp. 50–52).** Four mandatory
cryptographic phases per game step, **in order**:

1. **Commit.** The agent picks its physical move and the hint it will send
   (including an `Intent` flag stating whether the hint is truthful or
   deceptive), draws a unique `Nonce`, and transmits **only** the signature
   `H_commit`, not its content.
2. **Acknowledge.** The opponent confirms receipt and that it is *locked* on it.
   This prevents the sender retreating from its commitment and ensures the
   reveal happens only once both sides have fixed their moves.
3. **Reveal.** The agent sends the `Move` and the natural-language hint. **The
   nonce stays hidden at this stage**, to prevent premature reverse-engineering
   of the signatures.
4. **Final Reveal / Audit.** Only at the end of the whole game are all `Nonce`
   values revealed, for full mutual audit.

The commitment signature (PDF p. 50):

```
H_commit = SHA256( State ‖ Move ‖ Intent ‖ Nonce )
```

where `‖` is byte concatenation, not numeric addition.

**Canonical serialisation is mandatory in substance (PDF pp. 50–51).** The
concatenation is performed via canonical JSON serialisation — *sorted keys and
fixed separators* — so that both peers hash **byte-identical** input. The PDF
states explicitly that the record actually sealed is **richer than the four
fields shown** and also includes the verbal hint, the intent classification, the
step number and the role. The exact four-field formula as printed is therefore
`EXAMPLE`-grade detail; the requirement to have a single agreed, canonical,
byte-identical sealed record is `MANDATORY`. See [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) Q-4
and [PROTOCOL.md](PROTOCOL.md) for the schema we lock.

**Nonce generation.** The PDF's sample code uses `secrets.token_hex(16)` and
notes the use of the `secrets` module for a cryptographic nonce rather than the
too-predictable `random`. Sample code is `EXAMPLE`; using a cryptographically
secure nonce is the substance of E-18. PDF pp. 52–53.

**Mutual audit (PDF p. 55).** At the end of the match each agent submits its
full log including the nonce reveals for all of its steps. Each side
**reconstructs** the opponent's data through SHA-256: it takes the revealed
`State`, `Move`, `Intent` and `Nonce`, re-hashes them, and compares the result
to the signature declared at the commit stage. Any mismatch unambiguously proves
tampering — there is no room for interpretation or statistical doubt, since
SHA-256 is sensitive to every single bit. The cheating team absorbs a heavy
technical loss — total loss of the match, independent of the result on the
board. `MANDATORY`.

**Zero-knowledge framing (PDF p. 54).** At the commit stage the opponent
receives absolute certainty that a locked decision exists — but zero knowledge
of its content. Commitment is separated from disclosure. `MANDATORY` in
substance (this *is* commit-reveal), explanatory in form.

**Step-0 and computational fairness (Chapter 5, PDF pp. 55–56).** Before the
first move, a "step zero" is performed. Each agent collects its machine
specification: operating system, number and frequency of CPU cores, RAM size,
presence of a GPU accelerator and VRAM, and the name of the language model
running. Alongside the hardware spec, the step-zero declaration also documents
the **code version**, the **team name**, the **sub-game number**, and (E-53) the
**GitHub commit hash** the code ran at for that match. The whole specification
is packed into a JSON string and cryptographically signed with a pre-supplied
key so it cannot be forged after the fact. In parallel, all LLM token
consumption is monitored and likewise cryptographically locked, to prevent
denial of the computational resources actually consumed. `MANDATORY`.

The lecturer applies a **normalisation formula** when computing league scores,
granting bonuses to algorithmically efficient solutions — those achieving good
results with minimal resource consumption. The incentive is inverted: raw
hardware power is not rewarded; algorithmic sophistication is. `MANDATORY`
(as league scoring policy), PDF p. 56.

**Locking the scent model before a series (Chapter 4, PDF p. 47).** Before the
series opens, the two teams **must** exchange the full emission and decay model
**including a concrete numerical example** (e.g. a centre cell receives τ = 0.9,
and after one turn of decay at rate ρ it becomes 0.9·(1−ρ)). The sides must
verify they interpret the same formula in exactly the same way, and **only then
cryptographically lock** the agreement — for instance via a SHA-256 hash of the
agreed formula together with the numeric example, so that any future deviation
in the mechanism's behaviour is immediately detected. It is **permitted and even
recommended** that one team supply the other with the shared scent-mechanism
code itself, so both sides run exactly the same behaviour with no room for
interpretation that would harm the fairness of the series. `MANDATORY` (the
lock, E-23) + `RECOMMENDED` (sharing code).

**The replay viewer (Chapter 7, PDF pp. 72–75).** A **mandatory submission
requirement**, not an optional component. The player loads the final log file
and the viewer's user can step forward and backward in time using controls. Its
distinctive feature is not the graphical display but the cryptographic
verification: at each step the engine runs a live verification function taking
the `Nonce` and the move appearing in the visible log, re-encodes them via
SHA-256, and compares against the original commitment value.

- If the values match, a **green `Verified OK` stamp** is displayed.
- If **any** change is found in past data — an attempt to forge the log — the
  viewer prints a **glaring red `TAMPERED` banner and the match is immediately
  disqualified.** There is no appeal and no retroactive correction.

`MANDATORY`. Screenshots of the viewer showing `Verified OK`, alongside a
screenshot of the belief map in the Live GUI, are part of the submission
requirements (Appendix C).

The `verify_step` code sketch on PDF p. 74 hashes only `nonce|move`; the PDF
annotates this itself: *"the sketch simplifies the input for illustration; in
practice the signature covers the full step components — Move, State, Intent and
Nonce — as detailed in the protocol in Chapter 5."* The sketch is therefore
`EXAMPLE`.

---

## 4. Scent traces / pheromones (physics of observation)

*Chapter 4 (PDF pp. 40–47).*

This chapter carries no Appendix E rule numbers of its own except E-23 (locking
the model). The mechanics below are the agreed physics encoded in the shared
config; the parameters are `MANDATORY` via Appendix F.

- Whenever an agent moves or stays in place, a **scent field** of side
  `[pheromone_grid_size]` is created around its position. Intensity at the
  emission centre — the cell the agent occupies — is set to
  `[pheromone_center_intensity]`; moving away from the centre, intensity falls
  by a **radial distribution**. `MANDATORY` (as agreed physics), PDF p. 43.
- At the end of **each full turn** — that is, after **both** the cop **and** the
  thief have completed their move — all existing scent traces on the board
  undergo systemic decay at rate `[pheromone_decay]`. PDF p. 43.
- The update rule for the scent intensity in cell (i,j):

  ```
  τij(t+1) = max( 0, (1 − ρ)·τij(t) + Δτij )
  ```

  where ρ is the decay rate, `Δτij` is the new emission determined by the
  radial proximity of the cell to the agent's emission centre (at the centre
  itself `Δτ = 0.9`; if the agent is far, `Δτij = 0`), and the clamp at zero
  guarantees intensity is never negative. `MANDATORY` (as agreed physics),
  PDF p. 43.
- The mechanism is **completely symmetric**: both cop and thief emit scent, and
  **each side reads only the opponent's scent field**, not its own. PDF pp. 41,
  45.
- Scent is **natural and uncontrollable, and cannot lie**. It is emitted by the
  very act of movement and cannot be forged. An agent cannot plant a misleading
  scent trail in a place it does not occupy; all it can do is strengthen the
  scent in the cell it itself occupies (by staying there or returning to it),
  and that is a cost, not an advantage, since it helps the opponent locate it.
  **The only deception channel is the verbal hint.** PDF pp. 22, 41, 46.

The concrete numeric figures in the worked "lie detection" example (PDF p. 46 —
τ = 0.81 south-east, τ = 0.00 north) and the 5×5 emission matrix figure (PDF
p. 44) are `EXAMPLE`.

---

## 5. Strategy, language and the public network

*Appendix E table 10 (PDF p. 146); Chapter 6 (PDF pp. 57–68); Chapter 9 (PDF
pp. 88–93).*

| ID | Requirement | Class | Sanction (as stated) | Source |
|---|---|---|---|---|
| E-25 | Do **not** hand the language model the decision on the movement move itself; use it for text processing and building a behavioural profile only. | **RECOMMENDED** | The PDF states explicitly: *"there is no mandatory sanction, but blind reliance may entail hallucinations, illegal moves and technical loss."* | PDF p. 146 |
| E-26 | Conduct communication in **free natural language only**. | MANDATORY | Preservation of the psychological character of the challenge. | PDF p. 146 |
| E-27 | **Never** use direct numeric position protocols. | MANDATORY (prohibition) | Disqualification of the game's character as defined in the rule book. | PDF p. 146 |
| E-28 | Implement a **token-bucket rate limiter** for sending the reports to Gmail. | MANDATORY | Prevention of a 429 block that would paralyse the team's reporting. | PDF p. 146 |
| E-29 | Define **denial-of-service detectors** for hard protection of network resources. | MANDATORY | Interface lock, to prevent the reporting account being blocked. | PDF p. 146 |
| E-30 | Use **send-only permission** for the Gmail interface. | MANDATORY | A security breach that would entail disqualification in the code. | PDF p. 146 |

**Separation of spatial and verbal reasoning (Chapter 6).**

- Students **must implement a separate strategy module**, connecting to the
  `PeerRuntime` layer at a precise point — immediately after decoding the
  incoming hint, and before packing the outgoing commit. Between these two
  points sits all of the agent's intelligence: belief update, legal move
  selection, and composition of the deception text. The PDF states this
  separation "is not an architectural caprice; it is the boundary separating a
  generic communication component from a thinking agent." `MANDATORY`,
  PDF p. 58.
- The LLM is **not** the decider of legal moves — it produces the rhetorical and
  deceptive layer. Legal adjudication remains the responsibility of the client
  engine and the cryptographic verification. `MANDATORY` in substance (E-26/27
  + the separate module), PDF p. 27.
- Do not trust the LLM for spatial reasoning: language models tend to
  hallucinate when computing coordinates, directions and distances in Cartesian
  space, and may confidently return an illegal move, a move colliding with a
  barrier, or a move away from the target. `RECOMMENDED` (E-25), PDF p. 65.

**The single documented exception (PDF p. 66).** The default and the
recommendation remain unambiguous: the move decision is algorithmic and the LLM
is verbal only. However, as part of the negotiable rule set, **the two sides may
agree in advance — during the pre-match negotiation — to permit LLM-based
tactics for the move decision too**, instead of exclusive reliance on the
algorithm. This permission is valid **only** by explicit, mutual, documented
agreement between the teams; one side may **not** adopt such tactics
unilaterally. Even under such agreement, the local algorithm **must still
enforce move legality** (and reject any illegal move the model proposes), and
the risk of spatial hallucination remains the responsibility of the team that
chose it. The reference implementation and the book's default remain
algorithmic. `MANDATORY` (the conditions), `RECOMMENDED` (staying algorithmic).

**Movement policy options — three equal-standing routes (PDF pp. 59–61, 67).**
The course **did not teach reinforcement learning**, and a fully strong agent
can be built with heuristics alone, with no RL at all. The three routes are
explicitly presented as equal citizens:

1. Pure heuristics — Bayesian belief map + Manhattan distance. This is the
   **default policy in the reference implementation**.
2. Your own heuristic algorithm (may incorporate belief map, scent maps,
   barrier exploitation, look-ahead such as minimax or expectimax).
3. Reinforcement learning (Q-Learning / Bellman) — **one optional tool only**.

In all three, the spatial decision remains with the algorithm. `RECOMMENDED`
(the choice is the team's).

**Verbal layer / hints.**

- Hint content may lean on `[map_area]`, the real-world region where the game
  "takes place", embedding real landmarks. When undefined (default `""`),
  generic landmarks are used. PDF p. 67.
- Every hint is capped at `[hint_max_words]` words — a cut applied **both** to
  the template mode **and** to the language model, which also receives the limit
  in its system prompt. `[map_area]` and `[hint_max_words]` are agreed and
  signed match conditions like the rest. `MANDATORY`, PDF p. 67.
- Four LLM operating modes, all touching **only** the deception text:
  `template` (zero tokens, the default), `ollama` (local, zero API tokens),
  `claude_api`, `claude_cli`. An `every_n_steps` parameter invokes the model
  only once every few turns. In `template` and `ollama` modes the entire series
  can be played at **zero tokens**, moving the whole competition onto the
  quality of the movement algorithm. `RECOMMENDED` (choice is private per peer),
  PDF pp. 66–67, Appendix F table 21 (PDF p. 158).

**The Gatekeeper pattern (Chapter 9, PDF pp. 88–90).** Three cumulative
protection mechanisms in the communication module, in order:

1. **Quota Manager** — a counter tracking operations performed in a given day,
   preventing the daily safety threshold being crossed.
2. **Token Bucket rate limiter** — every report requires a valid rate token;
   absence of a token blocks the send, preventing bursts that would trigger an
   immediate provider block. Update rule (PDF p. 90):
   `tokens ← min(C, tokens + r·Δt)`, allow ⟺ `tokens ≥ 1`.
3. **DOS Detector** — identifies anomalous send patterns indicating a bug or
   infinite loop; on detection the gatekeeper **locks API access entirely**,
   sacrificing the single report to save the whole account from suspension.

`MANDATORY` (E-28, E-29). The PDF is emphatic (PDF p. 89) that three different
things are called "token" in this project and must not be confused: rate tokens
(token bucket), LLM tokens, and OAuth access/refresh tokens.

**Rate-limit discipline (PDF p. 95).** Exceeding Google's API quota returns HTTP
429 (Too Many Requests). This is **not** a transient fault — blind insistence
and immediate resending may lead the provider to suspend the account. One must
respect the 429, back off, and wait for the next time window. `MANDATORY`.

---

## 6. League fairness, administrative procedures and competition purity

*Appendix E tables 11–12 (PDF pp. 147–150); Chapter 9 (PDF pp. 85–98);
Chapter 11 (PDF pp. 112–114); Appendix C (PDF pp. 133–137).*

| ID | Requirement | Class | Sanction (as stated) | Source |
|---|---|---|---|---|
| E-31 | Play the **minimum mandatory number of matches against different groups** in the league. | MANDATORY | Failing the minimum denies a passing grade. | PDF p. 147 |
| E-32 | Report match results **automatically via the Gmail interface**. | MANDATORY | Absence of reporting disqualifies the points from this match. | PDF p. 147 |
| E-33 | Design the match report as a **standard JSON data structure**. | MANDATORY | Code cannot process free text and the report will be rejected. | PDF p. 147 |
| E-34 | **Never** send a final report as free text — only as an attached JSON file. | MANDATORY (prohibition) | A non-JSON report will be refused in processing and result in a score of zero. | PDF p. 147 |
| E-35 | **Agree with the opponent on the result**, and **each team sends its own separate final report**; failure to report by one of the teams, or contradictory reporting, causes **disqualification of the match and a score of 0 for both teams**. | MANDATORY | The principal enforcement mechanism preventing reporting fraud. | PDF p. 147 |
| E-36 | Perform a **comprehensive mutual log audit at the end of every match**. | MANDATORY | A necessary condition prior to agreement on the shared JSON result. | PDF p. 147 |
| E-37 | Declare **accurately, at the start of each match, how many matches have actually been played**. | MANDATORY | Threshold condition for computing the true competition factor. | PDF p. 147 |
| E-38 | **Never** declare falsely about the number of matches. | MANDATORY (prohibition) | Absolute disqualification for a discipline and purity offence. | PDF p. 148 |
| E-39 | **Never** push secrets and credentials to the repository — even if it is private and shared with the lecturer only. | MANDATORY (prohibition) | Severe security failure and failure of the project. | PDF p. 148 |
| E-40 | Add the credentials and secrets files to the **`.gitignore`** file. | MANDATORY | Mandatory protection against leaking Gmail API permission details. | PDF p. 148 |
| E-41 | **Tag the submission version** in the repository with a documented Git tag. | MANDATORY | Administrative condition enabling the lecturer to check the final version. | PDF p. 148 |
| E-42 | Write and attach a **comprehensive academic report** as a readable file in the repository (model description, deliberations, strategy, images and RL curves). | MANDATORY | Without the report the project is not academically complete. | PDF p. 148 |
| E-43 | Download the submission form from **Moodle**, fill it in and save as **PDF**. **Do not change and do not move fields.** | MANDATORY | Bureaucratic condition for awarding a grade. | PDF p. 148 |
| E-44 | Submit the assignment in Moodle **separately for each group member**. | MANDATORY | A project without individual submission will not earn the student a grade. | PDF p. 148 |
| E-45 | Enter a **unique 8-character group identification code with no spaces**. | MANDATORY | An organisational failure preventing automatic attribution of reports to the group. | PDF p. 148 |
| E-49 | Submit **two separate GitHub repositories** — cop and thief — with a cross-link in the READMEs, **two links** in the Moodle submission, and **four links** in the JSON of both teams. | MANDATORY | — (source: Chapter 9) | PDF p. 149 |
| E-50 | Include in **each** repository, at minimum: `README`, configuration files (`/config`), **PRD** files, a **PLAN** file and **TODO** files. | MANDATORY | — (source: Chapter 9) | PDF p. 149 |
| E-51 | Send the automatic final reports to the lecturer address `[agent_reporting_address]`. | MANDATORY | — (source: Chapter 9) | PDF p. 149 |
| E-52 | Against each opponent, **only one match counts** (no repeats to accumulate points); non-counting warm-up matches are permitted. | MANDATORY | — (source: Chapter 9) | PDF p. 149 |
| E-54 | Report in the final JSON file the **total tokens consumed** in the sub-game (and in the series). | MANDATORY | — (source: Chapters 5, 9) | PDF p. 150 |
| E-55 | Give a **self-grade for code quality only** — not for the league match result. | MANDATORY | — (source: Chapter 11) | PDF p. 150 |

**League structure (Chapter 9, PDF pp. 86–87).**

- Each team must play against **different** opponents; the league score derives
  from the collection of these matches.
- **Diversity incentive:** beating an opponent you have not played before earns
  the full `[diversity_reward]`. But you may not replay the same match against
  the same team to accumulate points: against each opponent **one match counts
  only**. `MANDATORY`.
- **Warm-up matches** that do not count are permitted and even recommended, for
  checking and calibration before the counting match. Once the counting match
  has finished and both teams have agreed on its result, they send the
  end-of-match message and the encounter against that opponent **is sealed** —
  no further match against it may be played for points. `MANDATORY`.
- **Game-count declaration:** at the opening of each match, each team declares to
  its opponent how many counting matches it has already played; the diversity
  incentive weighting is determined from the mutual declarations. The
  declaration is not a matter of trust: at the end of every legal match both
  teams send the lecturer the match summary, so at any moment the lecturer knows
  how many counting matches each team has actually played. A false declaration
  discovered at project-checking time disqualifies the declaring team.
  `MANDATORY`.
- Minimum threshold: correct operation of at least `[min_games_to_pass]`
  against different groups. Upper bound: each team may play at most
  `[max_games_per_team]` counting matches. `MANDATORY`.
- **Computational fairness:** the system reduces the score advantage of those
  relying on extreme cloud resources, and rewards algorithmically efficient
  development running on limited machines. The league rewards *development
  wisdom, not raw compute power*. `MANDATORY` (scoring policy).

**Tie rule (PDF p. 87).** If the cumulative score of **all sub-games** between a
pair of teams ends in a tie — that is, the sum of points of both teams is equal
— each team receives `[tie_score]`. `MANDATORY`.

**Mandatory reporting address (PDF p. 71).** At the end of every legal match,
both agents automatically send the final report to the lecturer's email address
`[agent_reporting_address]`. This is the **single binding address** for sending
the reports; it must be defined as the fixed destination in the mail-sending
code of each of the two agents. `MANDATORY`.

**Two separate reports (PDF p. 94), stated as a rule box:**

> At the end of the match **both teams must agree on its result**, and **each
> team must itself send** the end-of-match report to the lecturer — separately
> and in the binding format. Reporting is not the responsibility of one side
> only. If a report is not received from one of the sides, **that side will not
> be credited with points for the match — even if it won on the board**.
> Agreement on the result and the sending of the **two** separate reports are
> the condition for both teams to be credited with the points due to them.

**The four attached JSON files (PDF pp. 94–95).** Four example JSON files
accompany the book, covering the full life-cycle of the match. The variable name
of each is defined in Appendix F table 20 (PDF p. 157):

| Variable | Filename pattern | Role |
|---|---|---|
| `[declaration_file]` | `declaration_<game_id>.json` | **Pre-match declaration.** Concentrates all *constant* data of the whole match (across all sub-games): identity of both teams and their members, cop and thief repository addresses, MCP server addresses, hardware specs, language model, agreed token ceiling, and match start/end times. Role: to fix, cryptographically signed, everything that does not change during the match. |
| `[config_file]` | `config_<game_id>_g<NN>.json` | **The agreed configuration.** All quantitative parameters of the sub-game (Appendix F), cryptographically locked and identical between the sides. Role: to define the physics and scoring rules both teams agreed on. |
| `[log_file]` | `log_<game_id>_g<NN>.json` | **The sub-game log.** A step-by-step record: commit-reveal commitments, moves, hints **and the LLM discussion fields**, alongside the nonce and hash. Role: to enable full cryptographic verification in the replay simulator. |
| `[result_file]` | `result_<game_id>.json` | **The final results report.** Summary across all sub-games: each team's score in each sub-game and the cumulative result, for the lecturer to weight the league score. This is the binding report emailed to `[agent_reporting_address]`. |

All four carry a shared identifier (`game_uid`) and each filename derives from
the match identifier (`game_id`) and the sub-game number (`<NN>`), so files from
different matches never get mixed up. **Mandatory fields in the report** include
the GitHub links of **both** teams, the commit identifier of each sub-game, and
the total tokens consumed. `MANDATORY`.

**Mandatory log content (PDF p. 94).** The log file's stated purpose is *"to
enable full cryptographic verification in the replay simulator"*, and its
contents are enumerated as: commit-reveal commitments, moves, hints, **the LLM
discussion fields**, the nonce, and the hash. The LLM discussion fields are an
explicit content requirement that is easy to overlook — the log is not merely a
move list. The concrete record schema is defined in
[PROTOCOL.md](PROTOCOL.md) §11. `MANDATORY`.
*(Made explicit in the second-pass audit.)*

**Field names are fixed and binding (PDF p. 130).** Appendix B states, of the
shared config: *"the key fields correspond one-to-one to the mandatory parameter
table… **every field value** may change by negotiation (in the stricter
direction only, for a parameter of type 'minimum'), **but the field names are
fixed and binding**."* So negotiation may alter values; it may **never** rename
or restructure keys. `MANDATORY`.
*(Added in the second-pass audit.)*

**Mandatory rules from Appendix F §2 (PDF p. 156).**

- Every team **must define all** of the Appendix F values in the configuration
  file. Teams **must verify these values are identical** between the two teams,
  and **lock them cryptographically**. `MANDATORY`.
- For each new match a team may change the settings, as long as they match the
  agreement with the opposing team. `MANDATORY` (permission + condition).
- Each configuration file **must be given a different name** according to the
  match, to allow easy reconstruction of each match's configuration.
  `MANDATORY`.
- It is **mandatory to attach each match's configuration file to the GitHub
  repository**. `MANDATORY`.
- Each team may change code between matches; therefore **for each match an email
  must be sent to the lecturer containing the GitHub commit number** used in
  that match. `MANDATORY`.

---

## 7. Submission requirements

*Appendix C (PDF pp. 133–137); Chapter 9 §9.4 (PDF pp. 95–97); Chapter 11 §11.5
(PDF pp. 112–114).*

### 7.1 Repositories

- Submission is **not** a single source file attached to an email but a **whole
  development artefact** — a documented, tagged code repository accessible to
  the lecturer. The manner of submission is measured with the same rigour as the
  code itself. `MANDATORY`, PDF p. 133.
- Every repository **must be accessible to the lecturer**: either **public**, or
  **shared explicitly with the lecturer's address** `[lecturer_address]`.
  `MANDATORY`, PDF pp. 133, 95.
- Each team submits **two separate repositories**: one for the cop agent and one
  for the thief agent, and provides **two links**. `MANDATORY` (E-49).
- **Mandatory cross-link:** each repository's `README.md` must contain the link
  to that team's *other* repository — the cop's README points to the thief
  repository, and vice versa. The file submitted in Moodle must contain **both**
  links (cop and thief). In the end-of-match email — inside the attached JSON —
  **four links** appear: team A's two links and team B's two links.
  `MANDATORY`, PDF p. 96.
- Development proceeds via **branches**; each substantive capability develops in
  a dedicated branch and merges into the main branch only after stabilising.
  `RECOMMENDED` (stated as development practice), PDF p. 133.
- The final submission version is **not** marked by the vague "last state of the
  branch" but fixed with a **documented (annotated) Git tag**, which freezes a
  certain and incontestable point in the repository history and lets the
  examiner reconstruct exactly the code submitted. `MANDATORY` (E-41),
  PDF pp. 133–134.
- Tagging example given (`EXAMPLE` as to the exact string):
  `git tag -a v1.0-submission -m "Final submission: Police-Thief P2P, group N"`
  followed by `git push origin v1.0-submission`. Note the submission checklist
  (table 6) names the tag **`v1.0-submission`** and requires it **pushed**.
  PDF pp. 134, 136.

### 7.2 Mandatory repository contents

Each GitHub repository **must include, at minimum** (PDF p. 96; E-50):

- `README.md` — the academic report (see below);
- `/config` — the configuration files;
- **PRD** files (product requirement definition files) used to build the code;
- a **PLAN** file (work plan);
- **TODO** files.

These files tell the development story and let the examiner reconstruct the way
of working — not only the final result. `MANDATORY`.

Additionally (PDF p. 114): ensure a folder containing the markdown PRD files is
attached to the GitHub repository, and that the repository root has a readable
`README.md`. Ensure the code and the whole project meet all the guidelines in
the course-introduction file *"Recommendations for writing and submitting
software with the aid of AI agents"*; checking of the assignment will be
performed according to the principles in that file. `MANDATORY`.

### 7.3 Mandatory contents of the academic README

The heart of the documentary submission is an extended academic report in the
`README.md` at each repository root. It is **not** merely an installation
instruction file but a scientific document explaining the design decisions,
justifying them, and presenting the empirical evidence for their success. The
list of mandatory components — **the absence of any one of them detracts from
the submission** (PDF p. 97):

1. **The chosen Dec-POMDP model.** A scientific description of the formalism
   adopted for modelling the race — state space, observations, and uncertainty.
2. **FastMCP orchestration dilemmas.** Discussion of the development
   deliberations around orchestrating communication between the agents: turn
   management, handling network failures, and the roles of the Gatekeeper and
   the Orchestrator.
3. **The strategies implemented.** Detail of the decision-making mechanism
   chosen — heuristics (Manhattan distance, Bayesian belief map), LLM-based
   strategy, or optionally Q-Learning.
4. **Learning curves** — *if* RL was used. If you trained an agent with
   reinforcement learning, the learning curves as empirical evidence of policy
   convergence. (Conditional.)
5. **Screenshots — an absolute obligation.** From the Live GUI (the belief map)
   and from the replay application demonstrating `Verified OK`.
6. **Link to the companion repository.** The link to the team's second GitHub
   repository (cop/thief), as required above.

`MANDATORY` (items 1, 2, 3, 5, 6; item 4 conditional on RL being used).

The PDF adds (PDF p. 135) that the screenshot requirement is not merely formal:
the belief map proves the agent genuinely performs probabilistic inference under
partial observation, and the `Verified OK` indication proves the integrity of
the match was preserved.

### 7.4 Submission checklist (Appendix C table 6, PDF p. 136)

| Item | Required status |
|---|---|
| Two GitHub repositories accessible to the lecturer (cop, thief) | Public **or** private and shared with the lecturer |
| Cross-link between the repositories + two links in the submission | Present |
| Documented Git tag for the submission version `v1.0-submission` | Pushed |
| Components of the report in `README.md` (Chapter 9) | Complete in both repositories |
| Screenshots of the belief map (GUI) | Attached |
| Screenshot of Replay with `Verified OK` | Attached |
| At least two matches against different groups | 2 and above |
| End-of-match email — each group separately | Both sides sent |
| No secrets uploaded to the repository (`gitignore`) | Verified |

`MANDATORY`.

### 7.5 Moodle submission (PDF p. 114)

- Submission is performed in **Moodle** according to the fixed guidelines. The
  software code must be submitted on GitHub and shared with the lecturer.
- **Each member of the group submits the assignment separately** in Moodle
  (E-44).
- The submitting group must be given a **unique 8-character identification
  code, without spaces** (E-45).
- Moodle includes a **Word file** with a template for producing the submission
  **PDF**. **Fields must not be changed and positions must not be moved** —
  only fill in the details, save as PDF, and submit (E-43).
- A **self-grade for code quality only** must be given — not for the league
  match result. A self-grade based on the match result would distort the
  criterion for measuring code quality (E-55).

`MANDATORY`.

### 7.6 Never upload secrets (PDF p. 135)

If the repository is **public**, every file uploaded to it is exposed to the
whole world; and even if it is **private and shared with the lecturer only**,
there is still an absolute prohibition on uploading identity details and access
tokens — including `credentials.json` and `token.json` of OAuth (Appendix A) and
any configuration key or secret (Appendix B). It is **mandatory** to include a
`.gitignore` at the repository root that explicitly excludes these files, so
they are not included in a commit by mistake. **A secret leaked once is
considered exposed permanently** — even if deleted in a later commit, it remains
in the Git history. `MANDATORY` (E-39, E-40).

---

## 8. Gmail API and OAuth 2.0

*Appendix A (PDF pp. 120–125); Chapter 9 §9.3 (PDF pp. 87–95).*

Five ordered setup steps (PDF pp. 120–122). Skipping a step — especially the
consent-screen definition — will cause the authorisation flow to fail at a later
and more confusing stage:

1. **Open a project and enable the service** in Google Cloud Console; explicitly
   enable the Gmail API service.
2. **Configure the OAuth consent screen.** Choose `External` (for users outside
   the organisation) or `Internal` (inside an organisation with Google
   Workspace), and add the students' email addresses to the authorised *Test
   Users* group. While the application is in `Testing` mode only users on that
   list may complete the authorisation flow.
3. **Reduce scope to the strict minimum:**
   `https://www.googleapis.com/auth/gmail.send`. This scope permits **sending**
   mail — and nothing more. **Never grant read permission** to a project that
   does not need it. `MANDATORY` (E-30).
4. **Create credentials.** Create an OAuth Client ID of type *Desktop
   Application* and download `credentials.json` to the project's local working
   directory. It is an **absolute obligation** to add this file to `.gitignore`
   **before** pushing code to GitHub.
5. **First authorisation flow.** On first run the official Google libraries open
   a browser window and request approval. On approval, `token.json` is created
   automatically, containing a short-lived Access Token alongside a long-lived
   Refresh Token. Thanks to the refresh token the agent can send reports fully
   autonomously for many months with no further manual intervention.

**Required files (Appendix A table 5, PDF p. 125).** Only two files are needed
for the infrastructure, **both secret**, and **both must be in `.gitignore`**:

| File | Source | Content | Add to `.gitignore`? |
|---|---|---|---|
| `credentials.json` | Downloaded from the console | The application's secret identifier | **Yes — mandatory** |
| `token.json` | Created on first run | Access and refresh tokens | **Yes — mandatory** |

`MANDATORY`.

**Least privilege (PDF p. 123).** Requesting `gmail.send` only — not the broader
`gmail.modify` or `mail.google.com` — is a direct application of the
least-privilege principle. The reporting agent only needs to **send**; there is
therefore no reason for it to be able to **read** or **delete** mail. Narrowing
the scope turns a stolen token from a powerful weapon into a limited and almost
harmless tool. `MANDATORY` in substance (E-30).

**Report format (PDF pp. 94–95).** The match report is not free text. It is
packed into a uniform, binding JSON structure and sent **as a file attached to
the mail message**. It contains all the team's identity details, its GitHub
addresses, its FastMCP server addresses, cryptographically signed hardware
declarations, the match timestamp, and mutual-agreement confirmations backed by
SHA-256. Any attempt to send an open, non-machine-readable plaintext report
leads to rejection of the report — and the meaning of rejection may be the loss
of that round's league points. `MANDATORY` (E-33, E-34).

---

## 9. Development process

*Chapter 10 (PDF pp. 99–106).*

The PDF states at the head of the chapter that **this entire chapter is a
recommendation** (PDF p. 99): *"This chapter is the assembly chapter, and it is
entirely in the nature of a recommendation."*

**Seven development priorities / seven PRD files** — `RECOMMENDED`
(PDF pp. 101–103). Note however the interaction with E-50, which makes the
*existence* of PRD files in the repository mandatory even though the seven-stage
decomposition itself is a recommendation.

| Stage | What is built | Relevant chapter |
|---|---|---|
| 1. Base Logic | Grid of `[grid_size]`, movement rules, `[max_barriers]`, capture detection by coordinate overlap. Whole system runs in a single process. | Ch. 3 |
| 2. Basic MCP Infrastructure | Separate the agents into separate processes; raise the FastMCP servers; program tools for sending/receiving **pure geometric** information over localhost. Agents still speak in numeric coordinates only. | Ch. 2 |
| 3. Blind Strategy | Wire an initial strategy module — simple decision-making in a world of full and accurate information. "Blind" in the sense that there is no scent, natural language or deception yet. | Ch. 6 |
| 4. Language and Scent | Replace rigid coordinates with free-language reporting; embed the dynamic pheromone equations and their decay; embed the LLM for inference and composing lies. **The most sensitive stage** — reached only after infrastructure and logic are proven. | Ch. 4, Ch. 6 |
| 5. Cloud Exposure and Tunnelling | Move from localhost to public addresses via ngrok/Localtonet; connect agents from remote machines. From here the system is a genuine distributed system. | Ch. 2 |
| 6. Security and Cryptography | Only once remote communication works, wrap it in commit-reveal; write the nonce generator; integrate the hardware declarations (Step-0). | Ch. 5 |
| 7. Reporting and Visualisation Shell | Gmail API via OAuth 2.0, completion of the GUI, polishing the Replay application. Built last because it consumes all the layers beneath it. | Ch. 9, Ch. 7, App. A |

**Milestone checklist** (`RECOMMENDED`, PDF p. 105) — verify each item *works and
has been observed* before moving to the next stage. Observed behaviour
end-to-end, not "the code was written":

- **Stage 1:** two agents move legally on a `[grid_size]` grid; movement into a
  `[max_barriers]` barrier is rejected; coordinate overlap triggers capture.
- **Stage 2:** a geometric message leaving agent A over localhost is received and
  correctly decoded at agent B.
- **Stage 3:** given a known target location, the agent computes and executes the
  shortest path with no manual intervention.
- **Stage 4:** free-language reporting is translated into inference; the scent
  map updates and decays every step; the LLM produces a hint (true or false).
- **Stage 5:** an agent on a remote machine connects via ngrok and plays a full
  round against the local agent.
- **Stage 6:** a move is committed in Commit and then revealed in Reveal with a
  valid Nonce; Step-0 verifies hardware.
- **Stage 7:** a match summary is sent by Gmail; the GUI displays the state; the
  Replay App reconstructs a recorded round.

**Do not skip ahead** (`RECOMMENDED`, PDF p. 106): it is recommended not to
approach cryptography or the cloud before base logic and MCP infrastructure over
localhost work end-to-end. Skipping foundations may not save time but double it.

**Incremental delivery** (`RECOMMENDED`, PDF p. 100): each layer is built, tested
and stabilised **before** the layer above it is laid on it. Every stage ends in a
system that works end-to-end, even if narrow in scope. Recommended to implement
each stage as a separate PRD file.

---

## 10. Success metrics

*Chapter 11 §11.4 (PDF p. 110), table 4.*

The four metrics by which each team's success and its ability to compete in the
real world of distributed AI systems will be determined — *and not the beauty of
a single algorithm* (PDF p. 137):

| Metric | Expression in the project | Chapter |
|---|---|---|
| **Coordination** | Turn management, P2P protocol over FastMCP, and synchronisation of two agents with no central judge | Ch. 2 |
| **Adaptation** | Both agents cope symmetrically with uncertainty: each side builds a belief about its opponent's position from the opponent's decaying scent map and a verbal hint, and updates a probabilistic belief map | Ch. 4, Ch. 6 |
| **Integrity** | Cheating prevention via commit-reveal and SHA-256, and a full audit pass | Ch. 5 |
| **Architecture** | Adherence to the Gatekeeper and Orchestrator patterns and failure-resistant code | Ch. 8, Ch. 10 |
| *Submission criterion* | The whole project — code, structure and submission — is assessed against the course-introduction file *"Recommendations for writing and submitting software with the aid of AI agents"* | Course intro |

---

## 11. Example code repository (Appendix D)

*PDF pp. 138–141.*

A basic, public reference implementation accompanies the book at
`[example_repo]` = `https://github.com/rmisegal/Game-P2P-Cop-Chase`
(Appendix F table 20, PDF p. 157). Code version 3.0.0.

**Explicit constraints (PDF p. 138):**

- The repository is intended **for learning only**. It demonstrates the basic
  game flow and the simple GUI — the agents move minimally, **with no strategy
  at all** — to show how the system is assembled and runs end to end.
- **You must not start the project from this repository**, because it **does not
  fully meet the project specification**. It was written as a reduced example,
  not as a submission skeleton.
- You **may** use parts of the code or modify it, and it is **recommended** to
  use it to learn how a particular component was implemented, or to clarify a
  point not understood from the book — but **your solution must stand on its own
  and meet the full requirements**.
- Licence is an **educational-use licence**. **Wherever the repository deviates
  from the book, the book and the mandatory parameter table prevail.**
  PDF p. 141.

`MANDATORY` (the constraints), `RECOMMENDED` (using it to learn).

**Optional companion deliverable (`RECOMMENDED`, "מומלץ מאוד", PDF p. 141).** A
research and performance-analysis report template
(`RESEARCH-REPORT-Performance-Analysis.md`) is attached in the reference repo's
`/docs` folder. It analyses the agent's resource consumption: how many LLM calls
a full series requires, how they stack up against providers' rate limits, and
how the fallback mechanism guarantees every sub-game finishes even when the
provider is blocked. Recommended to use it as a template so that plan, strategy
and infrastructure decisions rest on numbers rather than guesswork.

---

## 12. Items explicitly NOT mandatory

Recording these prevents over-engineering.

| Item | Status | Source |
|---|---|---|
| Reinforcement learning / Q-Learning | **Optional, one tool among several.** The course did **not** teach RL. A fully strong agent can be built with heuristics alone. | PDF pp. 59, 61, 67, 115 |
| The specific 7-stage development order | `RECOMMENDED` (the whole of Ch. 10) | PDF p. 99 |
| A2A and ACP protocols | `RECOMMENDED` to be aware of. MCP is the project requirement and **must not** be replaced. | PDF p. 26 |
| `AgentNet` reading | `RECOMMENDED` optional reading | PDF p. 60 |
| NotebookLM study technique | Tip only | PDF p. 140 |
| Tkinter / PyQt as the GUI toolkit | `EXAMPLE` — the PDF says "e.g." | PDF p. 70 |
| ngrok / Localtonet specifically | `EXAMPLE` tools; *some* tunnel is mandatory (E-10) | PDF p. 29 |
| The specific state names in the state machine | `EXAMPLE` (sample code); having a state machine is mandatory | PDF pp. 79–80 |
| `/config/thief` vs `/config/police` exact paths | `EXAMPLE`; the *separation* is mandatory | PDF p. 31 |
| Giving the LLM the move decision | Forbidden by **recommendation** E-25, **permitted** only by explicit mutual documented agreement | PDF pp. 65–66, 146 |
| Docker, databases, cloud infrastructure | Never mentioned as requirements anywhere in the PDF | — |
