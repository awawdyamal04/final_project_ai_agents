"""Typed configuration objects.

Two of them, deliberately never merged:

``SharedConfig``
    The signed constitution. Everything both peers must agree on. Hashed into
    ``config_sha256`` and exchanged before play.

``PrivateConfig``
    Per-peer local settings. Never on the wire, never signed, never an input to
    ``config_sha256``.

The PDF's own test for which is which (PDF p. 128): *"must the opponent agree to
this value, or rely on it?"* -- yes gives the shared JSON, no gives the private
TOML.

Both are frozen. A configuration that can be mutated after validation is a
configuration whose hash no longer describes it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from police_thief.domain.enums import (
    AxisOriginCorner,
    EmailMode,
    Role,
    VerbalProvider,
)

Coord = tuple[int, int]


# --------------------------------------------------------------------------
# Shared -- config/game.json
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BoardAndAgents:
    grid_size: int
    num_agents: int
    axis_origin_corner: AxisOriginCorner
    axis_start_index: int
    thief_start: Coord
    cop_start: Coord


@dataclass(frozen=True, slots=True)
class World:
    map_area: str
    hint_max_words: int


@dataclass(frozen=True, slots=True)
class MovementAndBarriers:
    move_set: tuple[str, ...]
    max_barriers: int
    max_moves: int
    survival_threshold: int


@dataclass(frozen=True, slots=True)
class Scoring:
    capture_cop: int
    capture_thief: int
    survival_cop: int
    survival_thief: int
    tie_score: int
    technical_loss: int
    """Not an Appendix F parameter -- see policy.TECHNICAL_LOSS_DEFAULT."""


@dataclass(frozen=True, slots=True)
class Pheromones:
    pheromone_center_intensity: float
    pheromone_decay: float
    pheromone_grid_size: int


@dataclass(frozen=True, slots=True)
class NetworkAndLeague:
    response_timeout_sec: int
    watchdog_timeout_sec: int
    num_games: int
    diversity_reward: int
    min_games_to_pass: int
    max_games_per_team: int
    token_budget_per_series: int


@dataclass(frozen=True, slots=True)
class RateLimiterGatekeeper:
    requests_per_minute: int
    concurrent_requests: int
    retry_backoff_sec: int
    max_retries: int
    queue_depth: int


@dataclass(frozen=True, slots=True)
class SharedConfig:
    """The signed constitution loaded from ``config/game.json``.

    ``raw`` keeps the exact parsed mapping. The hash is computed from that, not
    from the typed fields, so the digest describes the document as agreed --
    including any structural field this class does not model. Reconstructing the
    mapping from the dataclass would risk a digest that differs from the
    opponent's for a purely representational reason.
    """

    schema_version: str
    agreed_between: tuple[str, ...]
    board_and_agents: BoardAndAgents
    world: World
    movement_and_barriers: MovementAndBarriers
    scoring: Scoring
    pheromones: Pheromones
    network_and_league: NetworkAndLeague
    rate_limiter_gatekeeper: RateLimiterGatekeeper
    raw: Mapping[str, Any] = field(repr=False)
    source_path: Path | None = field(default=None, repr=False)

    @property
    def grid_size(self) -> int:
        return self.board_and_agents.grid_size

    def cells(self) -> int:
        return self.grid_size * self.grid_size

    def in_bounds(self, cell: Coord) -> bool:
        """True when ``cell`` lies on the board under the agreed axis system."""
        low = self.board_and_agents.axis_start_index
        high = low + self.grid_size
        return low <= cell[0] < high and low <= cell[1] < high


# --------------------------------------------------------------------------
# Private -- config/<role>/game.toml
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GameIdentity:
    group_name: str
    group_id: str
    """Exactly 8 characters, no spaces (E-45)."""
    members: tuple[str, ...]
    repos: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class NetworkSettings:
    role: Role
    host: str
    port: int
    opponent_url: str
    turn_timeout_seconds: int


@dataclass(frozen=True, slots=True)
class StrategySettings:
    """Which brain class runs. Empty means the shipped heuristic."""

    thief_class: str | None = None
    police_class: str | None = None


@dataclass(frozen=True, slots=True)
class VerbalSettings:
    """How deception text is produced. The move is always pure Python."""

    provider: VerbalProvider = VerbalProvider.TEMPLATE
    every_n_steps: int = 1


@dataclass(frozen=True, slots=True)
class LlmSettings:
    model: str | None = None
    step_deadline_seconds: int = 30


@dataclass(frozen=True, slots=True)
class EmailSettings:
    recipient: str = "rmisegal+uoh26finalgame@gmail.com"
    mode: EmailMode = EmailMode.SEND
    credentials_path: Path = Path("credentials.json")
    token_path: Path = Path("token.json")
    """Paths only. The files themselves are gitignored secrets (E-39, E-40) and
    their contents never enter configuration."""


@dataclass(frozen=True, slots=True)
class PrivateConfig:
    """Per-peer settings from ``config/<role>/game.toml``.

    Never crosses the network, never signed, and **not** an input to
    ``config_sha256``.
    """

    version: str
    game: GameIdentity
    network: NetworkSettings
    strategy: StrategySettings
    trash_talk: VerbalSettings
    llm: LlmSettings
    email: EmailSettings
    source_path: Path | None = field(default=None, repr=False)

    @property
    def role(self) -> Role:
        return self.network.role
