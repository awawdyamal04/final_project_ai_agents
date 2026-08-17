"""Reading and constructing configuration objects.

The loader owns three responsibilities the parsers do not handle for us:
duplicate-key detection, running the validation layers in order, and building
frozen typed objects. It never repairs input -- a malformed configuration is an
error every time.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from police_thief.config.exceptions import (
    ConfigFileNotFoundError,
    ConfigParseError,
    DuplicateConfigKeyError,
    InvalidConfigTypeError,
    InvalidConfigValueError,
    MissingConfigFieldError,
    UnknownConfigFieldError,
)
from police_thief.config.models import (
    BoardAndAgents,
    EmailSettings,
    GameIdentity,
    LlmSettings,
    MovementAndBarriers,
    NetworkAndLeague,
    NetworkSettings,
    Pheromones,
    PrivateConfig,
    RateLimiterGatekeeper,
    Scoring,
    SharedConfig,
    StrategySettings,
    VerbalSettings,
    World,
)
from police_thief.config.validation import (
    validate_cross_fields,
    validate_parameter_policies,
    validate_private_does_not_shadow_shared,
    validate_shared_schema,
)
from police_thief.domain.enums import (
    AxisOriginCorner,
    EmailMode,
    Role,
    VerbalProvider,
)

# --------------------------------------------------------------------------
# Duplicate-key detection
# --------------------------------------------------------------------------


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """``object_pairs_hook`` that rejects repeated keys.

    ``json.load`` keeps the last occurrence of a duplicated key and says
    nothing. In a document whose entire purpose is byte-identical agreement
    between two parties, that lets two peers read different values from what
    they each believe is the same file.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateConfigKeyError(
                f"duplicate key {key!r} in the same JSON object; the shared "
                f"configuration must be unambiguous"
            )
        seen[key] = value
    return seen


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigFileNotFoundError(f"no configuration file at {path}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigParseError(f"{path} is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise ConfigParseError(f"cannot read {path}: {exc}") from exc


def parse_shared_mapping(text: str, *, source: str = "<string>") -> dict[str, Any]:
    """Parse shared-configuration JSON, rejecting duplicate keys."""
    try:
        parsed = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except DuplicateConfigKeyError:
        raise
    except json.JSONDecodeError as exc:
        raise ConfigParseError(f"{source} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise InvalidConfigTypeError(
            f"{source}: shared configuration must be a JSON object, "
            f"got {type(parsed).__name__}"
        )
    return parsed


# --------------------------------------------------------------------------
# Shared configuration
# --------------------------------------------------------------------------


def build_shared_config(
    mapping: Mapping[str, Any], *, source_path: Path | None = None
) -> SharedConfig:
    """Validate a parsed mapping and build the frozen typed object."""
    validate_shared_schema(mapping)
    validate_parameter_policies(mapping)
    validate_cross_fields(mapping)

    board = mapping["board_and_agents"]
    world = mapping["world"]
    movement = mapping["movement_and_barriers"]
    scoring = mapping["scoring"]
    pheromones = mapping["pheromones"]
    league = mapping["network_and_league"]
    limiter = mapping["rate_limiter_gatekeeper"]

    return SharedConfig(
        schema_version=mapping["schema_version"],
        agreed_between=tuple(mapping["agreed_between"]),
        board_and_agents=BoardAndAgents(
            grid_size=board["grid_size"],
            num_agents=board["num_agents"],
            axis_origin_corner=AxisOriginCorner(board["axis_origin_corner"]),
            axis_start_index=board["axis_start_index"],
            thief_start=tuple(board["thief_start"]),
            cop_start=tuple(board["cop_start"]),
        ),
        world=World(
            map_area=world["map_area"],
            hint_max_words=world["hint_max_words"],
        ),
        movement_and_barriers=MovementAndBarriers(
            move_set=tuple(movement["move_set"]),
            max_barriers=movement["max_barriers"],
            max_moves=movement["max_moves"],
            survival_threshold=movement["survival_threshold"],
        ),
        scoring=Scoring(
            capture_cop=scoring["capture_cop"],
            capture_thief=scoring["capture_thief"],
            survival_cop=scoring["survival_cop"],
            survival_thief=scoring["survival_thief"],
            tie_score=scoring["tie_score"],
            technical_loss=scoring["technical_loss"],
        ),
        pheromones=Pheromones(
            pheromone_center_intensity=float(
                pheromones["pheromone_center_intensity"]
            ),
            pheromone_decay=float(pheromones["pheromone_decay"]),
            pheromone_grid_size=pheromones["pheromone_grid_size"],
        ),
        network_and_league=NetworkAndLeague(
            response_timeout_sec=league["response_timeout_sec"],
            watchdog_timeout_sec=league["watchdog_timeout_sec"],
            num_games=league["num_games"],
            diversity_reward=league["diversity_reward"],
            min_games_to_pass=league["min_games_to_pass"],
            max_games_per_team=league["max_games_per_team"],
            token_budget_per_series=league["token_budget_per_series"],
        ),
        rate_limiter_gatekeeper=RateLimiterGatekeeper(
            requests_per_minute=limiter["requests_per_minute"],
            concurrent_requests=limiter["concurrent_requests"],
            retry_backoff_sec=limiter["retry_backoff_sec"],
            max_retries=limiter["max_retries"],
            queue_depth=limiter["queue_depth"],
        ),
        raw=mapping,
        source_path=source_path,
    )


def load_shared_config(path: str | Path) -> SharedConfig:
    """Load, validate and freeze ``config/game.json``."""
    path = Path(path)
    mapping = parse_shared_mapping(_read_text(path), source=str(path))
    return build_shared_config(mapping, source_path=path)


# --------------------------------------------------------------------------
# Private configuration
# --------------------------------------------------------------------------

_PRIVATE_SECTIONS: tuple[str, ...] = (
    "game",
    "network",
    "strategy",
    "trash_talk",
    "llm",
    "email",
)
_REQUIRED_PRIVATE_SECTIONS: tuple[str, ...] = ("game", "network")

_GROUP_ID_LENGTH = 8
"""E-45: a unique 8-character group identification code, without spaces."""


def parse_private_mapping(text: str, *, source: str = "<string>") -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigParseError(f"{source} is not valid TOML: {exc}") from exc


def build_private_config(
    mapping: Mapping[str, Any], *, source_path: Path | None = None
) -> PrivateConfig:
    validate_private_does_not_shadow_shared(mapping)

    allowed = set(_PRIVATE_SECTIONS) | {"version"}
    for unknown in sorted(set(mapping) - allowed):
        raise UnknownConfigFieldError(
            f"unknown private section {unknown!r}; allowed: {sorted(allowed)}"
        )
    for missing in _REQUIRED_PRIVATE_SECTIONS:
        if missing not in mapping:
            raise MissingConfigFieldError(
                f"private configuration is missing the [{missing}] section"
            )

    game = mapping["game"]
    network = mapping["network"]
    strategy = mapping.get("strategy", {})
    trash_talk = mapping.get("trash_talk", {})
    llm = mapping.get("llm", {})
    email = mapping.get("email", {})

    for key in ("group_name", "group_id", "members"):
        if key not in game:
            raise MissingConfigFieldError(f"private [game] is missing {key!r}")

    group_id = game["group_id"]
    if not isinstance(group_id, str):
        raise InvalidConfigTypeError(
            f"[game] group_id must be a string, got {type(group_id).__name__}"
        )
    if len(group_id) != _GROUP_ID_LENGTH or any(c.isspace() for c in group_id):
        raise InvalidConfigValueError(
            f"[game] group_id must be exactly {_GROUP_ID_LENGTH} characters "
            f"with no spaces (E-45), got {group_id!r}"
        )

    for key in ("role", "opponent_url"):
        if key not in network:
            raise MissingConfigFieldError(f"private [network] is missing {key!r}")

    raw_role = network["role"]
    try:
        role = Role(raw_role)
    except ValueError as exc:
        raise InvalidConfigValueError(
            f"[network] role must be one of "
            f"{sorted(r.value for r in Role)}, got {raw_role!r}"
        ) from exc

    port = network.get("port", 0)
    if isinstance(port, bool) or not isinstance(port, int):
        raise InvalidConfigTypeError(
            f"[network] port must be an integer, got {type(port).__name__}"
        )
    if not 1 <= port <= 65535:
        raise InvalidConfigValueError(
            f"[network] port must lie in 1..65535, got {port}"
        )

    opponent_url = network["opponent_url"]
    if not isinstance(opponent_url, str) or not opponent_url.strip():
        raise InvalidConfigValueError(
            "[network] opponent_url must be a non-empty string"
        )
    if not opponent_url.startswith(("http://", "https://")):
        raise InvalidConfigValueError(
            f"[network] opponent_url must be an http(s) URL, got "
            f"{opponent_url!r}"
        )

    raw_provider = trash_talk.get("provider", VerbalProvider.TEMPLATE.value)
    try:
        provider = VerbalProvider(raw_provider)
    except ValueError as exc:
        raise InvalidConfigValueError(
            f"[trash_talk] provider must be one of "
            f"{sorted(p.value for p in VerbalProvider)}, got {raw_provider!r}"
        ) from exc

    raw_mode = email.get("mode", EmailMode.SEND.value)
    try:
        mode = EmailMode(raw_mode)
    except ValueError as exc:
        raise InvalidConfigValueError(
            f"[email] mode must be one of "
            f"{sorted(m.value for m in EmailMode)}, got {raw_mode!r}"
        ) from exc

    return PrivateConfig(
        version=str(mapping.get("version", "0")),
        game=GameIdentity(
            group_name=game["group_name"],
            group_id=group_id,
            members=tuple(game["members"]),
            repos=dict(game.get("repos", {})),
        ),
        network=NetworkSettings(
            role=role,
            host=network.get("host", "127.0.0.1"),
            port=port,
            opponent_url=opponent_url,
            turn_timeout_seconds=network.get("turn_timeout_seconds", 180),
        ),
        strategy=StrategySettings(
            thief_class=strategy.get("thief_class"),
            police_class=strategy.get("police_class"),
        ),
        trash_talk=VerbalSettings(
            provider=provider,
            every_n_steps=trash_talk.get("every_n_steps", 1),
        ),
        llm=LlmSettings(
            model=llm.get("model"),
            step_deadline_seconds=llm.get("step_deadline_seconds", 30),
        ),
        email=EmailSettings(
            recipient=email.get(
                "recipient", "rmisegal+uoh26finalgame@gmail.com"
            ),
            mode=mode,
            credentials_path=Path(email.get("credentials_path", "credentials.json")),
            token_path=Path(email.get("token_path", "token.json")),
        ),
        source_path=source_path,
    )


def load_private_config(path: str | Path) -> PrivateConfig:
    """Load, validate and freeze a private per-peer TOML file."""
    path = Path(path)
    mapping = parse_private_mapping(_read_text(path), source=str(path))
    return build_private_config(mapping, source_path=path)
