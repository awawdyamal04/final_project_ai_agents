"""Private per-peer configuration, and its separation from the shared one."""

from __future__ import annotations

import pytest

from police_thief.config.exceptions import (
    InvalidConfigTypeError,
    InvalidConfigValueError,
    InvalidCrossFieldConfigError,
    MissingConfigFieldError,
    PrivateConfigShadowsSharedError,
    UnknownConfigFieldError,
)
from police_thief.config.loader import build_private_config, load_private_config
from police_thief.config.validation import validate_role_matches
from police_thief.domain.enums import EmailMode, Role, VerbalProvider

MINIMAL = {
    "version": "1.10",
    "game": {
        "group_name": "Test-Team",
        "group_id": "abcd1234",
        "members": ["id-1", "id-2"],
    },
    "network": {
        "role": "police",
        "host": "127.0.0.1",
        "port": 8801,
        "opponent_url": "http://127.0.0.1:8802/mcp",
    },
}


def _private(**overrides):
    import copy

    mapping = copy.deepcopy(MINIMAL)
    for section, values in overrides.items():
        mapping.setdefault(section, {}).update(values)
    return mapping


# --------------------------------------------------------------------------
# The shipped examples
# --------------------------------------------------------------------------


def test_valid_cop_example_loads(cop_example_path):
    private = load_private_config(cop_example_path)
    assert private.role is Role.POLICE
    assert private.network.port == 8801
    assert private.trash_talk.provider is VerbalProvider.TEMPLATE
    assert private.email.mode is EmailMode.SEND


def test_valid_thief_example_loads(thief_example_path):
    private = load_private_config(thief_example_path)
    assert private.role is Role.THIEF
    assert private.network.port == 8802


def test_examples_point_at_each_other(cop_example_path, thief_example_path):
    cop = load_private_config(cop_example_path)
    thief = load_private_config(thief_example_path)
    assert str(cop.network.port) in thief.network.opponent_url
    assert str(thief.network.port) in cop.network.opponent_url


def test_examples_default_to_send_not_draft(cop_example_path, thief_example_path):
    """E-32/E-51: a draft never reaches the lecturer. See DECISIONS.md D-5."""
    for path in (cop_example_path, thief_example_path):
        assert load_private_config(path).email.mode is EmailMode.SEND


def test_examples_contain_no_secret_values(cop_example_path, thief_example_path):
    """Committed examples carry placeholders and paths, never credentials."""
    for path in (cop_example_path, thief_example_path):
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for marker in (
            "-----begin",
            "client_secret",
            "refresh_token",
            "access_token",
            "api_key",
            "sk-ant-",
            "ya29.",
        ):
            assert marker not in lowered, f"{path} appears to contain {marker}"
        private = load_private_config(path)
        # Credentials are referenced only as paths, and never read.
        assert private.email.credentials_path.name == "credentials.json"
        assert private.email.token_path.name == "token.json"


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def test_invalid_role_is_rejected():
    with pytest.raises(InvalidConfigValueError, match="role must be one of"):
        build_private_config(_private(network={"role": "referee"}))


def test_role_is_case_sensitive():
    with pytest.raises(InvalidConfigValueError):
        build_private_config(_private(network={"role": "POLICE"}))


@pytest.mark.parametrize("port", [0, -1, 65536, 99999])
def test_invalid_port_is_rejected(port):
    with pytest.raises(InvalidConfigValueError, match="port must lie"):
        build_private_config(_private(network={"port": port}))


def test_non_integer_port_is_rejected():
    with pytest.raises(InvalidConfigTypeError, match="port must be an integer"):
        build_private_config(_private(network={"port": "8801"}))


def test_boolean_port_is_rejected():
    with pytest.raises(InvalidConfigTypeError):
        build_private_config(_private(network={"port": True}))


def test_missing_opponent_url_is_rejected():
    mapping = _private()
    del mapping["network"]["opponent_url"]
    with pytest.raises(MissingConfigFieldError, match="opponent_url"):
        build_private_config(mapping)


@pytest.mark.parametrize("url", ["", "   ", "127.0.0.1:8802", "ftp://host/mcp"])
def test_invalid_opponent_url_is_rejected(url):
    with pytest.raises(InvalidConfigValueError, match="opponent_url"):
        build_private_config(_private(network={"opponent_url": url}))


@pytest.mark.parametrize("group_id", ["short", "waytoolongvalue", "ab cd123", ""])
def test_invalid_group_id_is_rejected(group_id):
    """E-45: exactly 8 characters, no spaces."""
    with pytest.raises(InvalidConfigValueError, match="8 characters"):
        build_private_config(_private(game={"group_id": group_id}))


def test_valid_group_id_is_accepted():
    private = build_private_config(_private(game={"group_id": "a1b2c3d4"}))
    assert private.game.group_id == "a1b2c3d4"


def test_missing_required_section_is_rejected():
    mapping = _private()
    del mapping["network"]
    with pytest.raises(MissingConfigFieldError, match=r"\[network\]"):
        build_private_config(mapping)


def test_unknown_private_section_is_rejected():
    with pytest.raises(UnknownConfigFieldError, match="mystery"):
        build_private_config(_private(mystery={"a": 1}))


def test_invalid_provider_is_rejected():
    with pytest.raises(InvalidConfigValueError, match="provider must be one of"):
        build_private_config(_private(trash_talk={"provider": "gpt5"}))


def test_invalid_email_mode_is_rejected():
    with pytest.raises(InvalidConfigValueError, match="mode must be one of"):
        build_private_config(_private(email={"mode": "outbox"}))


def test_optional_sections_default_sensibly():
    private = build_private_config(_private())
    assert private.trash_talk.provider is VerbalProvider.TEMPLATE
    assert private.email.mode is EmailMode.SEND
    assert private.strategy.thief_class is None
    assert private.llm.step_deadline_seconds == 30


# --------------------------------------------------------------------------
# Separation from the shared constitution
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("network", "num_games", 1),
        ("game", "grid_size", 5),
        ("network", "max_moves", 10),
        ("llm", "survival_threshold", 3),
        ("email", "tie_score", 99),
    ],
)
def test_private_config_may_not_shadow_a_shared_parameter(section, key, value):
    """PDF p. 132: the private file may never weaken a signed condition.

    Rejecting the shadowing is stronger than overriding it -- a key that is
    never accepted can never win.
    """
    with pytest.raises(PrivateConfigShadowsSharedError, match=key):
        build_private_config(_private(**{section: {key: value}}))


def test_private_config_carries_no_shared_parameters(
    cop_example_path, thief_example_path
):
    from police_thief.config.policy import PARAMETER_POLICIES

    shared_keys = {p.key for p in PARAMETER_POLICIES}
    for path in (cop_example_path, thief_example_path):
        private = load_private_config(path)
        assert not hasattr(private, "grid_size")
        for field_name in ("network", "game", "llm", "email"):
            section = getattr(private, field_name)
            assert not (set(vars(section) if hasattr(section, "__dict__") else {})
                        & shared_keys)


def test_role_must_match_the_entry_point():
    private = build_private_config(_private(network={"role": "thief"}))
    validate_role_matches(private.role, Role.THIEF)
    with pytest.raises(InvalidCrossFieldConfigError, match="separate processes"):
        validate_role_matches(private.role, Role.POLICE)


def test_role_opponent_is_the_other_side():
    assert Role.POLICE.opponent is Role.THIEF
    assert Role.THIEF.opponent is Role.POLICE
