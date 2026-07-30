"""Configuration subsystem.

This package is the *only* place where the binding numeric values of Appendix F
enter the system. Game logic reads a typed config object; no module outside
``policy.py`` may carry an Appendix F literal.

Two configurations, deliberately kept as separate typed objects:

``SharedConfig``
    The signed constitution (``config/game.json``). Everything both peers must
    agree on. Hashed with :func:`~police_thief.config.hashing.config_sha256`
    and exchanged before play; a mismatch means refusing to play (E-11).

``PrivateConfig``
    Per-peer local settings (``config/<role>/game.toml``). Never crosses the
    network, never signed, never hashed into ``config_sha256``.
"""

from police_thief.config.canonical import canonical_json_bytes, canonical_json_text
from police_thief.config.hashing import config_sha256, sha256_hex
from police_thief.config.loader import (
    load_private_config,
    load_shared_config,
    parse_shared_mapping,
)
from police_thief.config.models import PrivateConfig, SharedConfig
from police_thief.config.policy import PARAMETER_POLICIES, ParameterPolicy

__all__ = [
    "PARAMETER_POLICIES",
    "ParameterPolicy",
    "PrivateConfig",
    "SharedConfig",
    "canonical_json_bytes",
    "canonical_json_text",
    "config_sha256",
    "load_private_config",
    "load_shared_config",
    "parse_shared_mapping",
    "sha256_hex",
]
