"""Configuration errors.

Every failure mode is a distinct type, so tests can assert *which* rule was
broken rather than merely that something was rejected. Nothing here is a
warning: a malformed or non-compliant configuration is always an error, never
something silently repaired or ignored. A silently-ignored key is how two peers
end up computing different physics while both believe they agreed.
"""

from __future__ import annotations


class ConfigError(Exception):
    """Base class for every configuration failure."""


# --------------------------------------------------------------------------
# Reading and parsing
# --------------------------------------------------------------------------


class ConfigFileNotFoundError(ConfigError):
    """The configuration file does not exist at the given path."""


class ConfigParseError(ConfigError):
    """The file is not well-formed JSON/TOML, or is not decodable as UTF-8."""


class DuplicateConfigKeyError(ConfigError):
    """The same key appears twice in one JSON object.

    ``json.load`` accepts duplicates silently, keeping the last occurrence. In a
    file whose whole purpose is byte-identical agreement between two parties,
    that is a way for two peers to read different values from what they believe
    is the same document.
    """


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------


class SchemaError(ConfigError):
    """Base class for closed-schema violations."""


class UnknownConfigFieldError(SchemaError):
    """A key not in the binding schema.

    Field names are fixed and binding (PDF p. 130): negotiation may change what
    a value *is*, never what a key is *called*.
    """


class MissingConfigFieldError(SchemaError):
    """A mandatory key is absent.

    Appendix F section 2 (PDF p. 156): every team must define *all* of the
    Appendix F values in the configuration file.
    """


class InvalidConfigTypeError(SchemaError):
    """A value has the wrong type or shape."""


class InvalidConfigValueError(SchemaError):
    """A value is well-typed but outside its permitted domain."""


# --------------------------------------------------------------------------
# Appendix F parameter policy
# --------------------------------------------------------------------------


class ParameterPolicyError(ConfigError):
    """Base class for Appendix F policy violations."""


class FixedParameterViolationError(ParameterPolicyError):
    """A FIXED parameter does not equal its binding value.

    Appendix F p. 155: "a binding value that cannot be changed at all.
    Deviating from this value disqualifies the team."
    """


class MinimumParameterViolationError(ParameterPolicyError):
    """A MINIMUM parameter is below its binding floor (E-12)."""


# --------------------------------------------------------------------------
# Cross-field and cross-file
# --------------------------------------------------------------------------


class InvalidCrossFieldConfigError(ConfigError):
    """Individually valid values that contradict one another."""


class PrivateConfigShadowsSharedError(ConfigError):
    """The private TOML defines a key owned by the shared constitution.

    PDF p. 132 requires that the shared JSON override any parallel key in the
    private TOML, "so the private file can never 'weaken' a signed condition".
    Rejecting the shadowing outright is a strictly stronger guarantee than
    overriding it, and it keeps the two configurations as separate objects.
    """


class ConfigHashMismatchError(ConfigError):
    """A computed ``config_sha256`` does not match the expected one.

    Raised at the pre-match handshake (E-11). The correct response is to refuse
    to play -- not a technical loss, the match simply never starts.
    """


# --------------------------------------------------------------------------
# Canonical serialisation
# --------------------------------------------------------------------------


class CanonicalSerialisationError(ConfigError):
    """A value cannot be canonically serialised deterministically."""
