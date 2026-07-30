"""The verbal layer: composing and reading natural-language hints.

This is the *only* deception channel in the game. Scent is emitted by movement
and cannot be forged; the hint is the one place a peer may mislead. The
specification is equally clear about what this layer must never touch: it does
not choose actions, does not validate moves, does not score, and never sees the
opponent's position. It turns a direction into a sentence and a sentence back
into a guess.

Default provider is ``template``: deterministic, offline, zero tokens, no API.
A whole series can be played this way, which puts the competition on the
movement algorithm rather than on who bought more inference. The
:class:`HintProvider` protocol leaves room for a language-model provider later
without changing any caller.

Determinism matters here as much as anywhere else: two peers replaying the same
match must reproduce the same hints, so nothing draws from a random source. The
choice of phrasing and of when to lie is a pure function of
``(game_id, turn, role)``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Protocol

from police_thief.domain.enums import Direction

MAX_HINT_WORDS_FALLBACK = 15
"""Used only if a caller omits the configured limit. The real value is
``hint_max_words`` from the shared config."""


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------

_NUMERIC_POSITION = re.compile(
    r"""(
        \(\s*\d+\s*,\s*\d+\s*\)      # (3,4)
      | \[\s*\d+\s*,\s*\d+\s*\]      # [3,4]
      | \b\d+\s*,\s*\d+\b            # 3,4
      | \b(?:row|col|column|cell|x|y)\s*[:=]?\s*\d+
      | \b[A-Ha-h]\s?\d\b            # B4
    )""",
    re.VERBOSE,
)


class HintRejected(ValueError):
    """A hint violates the agreed constraints (E-26, E-27)."""


def validate_hint(text: str, max_words: int) -> str:
    """Check a hint and return it, or raise.

    Applied to hints we *send* as well as hints we receive, so a bug in our own
    composer is caught here rather than by the opponent rejecting our move.
    """
    if not isinstance(text, str):
        raise HintRejected(f"hint must be text, got {type(text).__name__}")
    stripped = text.strip()
    if not stripped:
        raise HintRejected("hint must not be empty")

    words = stripped.split()
    if len(words) > max_words:
        raise HintRejected(
            f"hint is {len(words)} words, over the agreed limit of {max_words}"
        )
    if _NUMERIC_POSITION.search(stripped):
        raise HintRejected(
            "hint encodes a numeric position; communication must be free "
            "natural language, and a coordinate protocol is forbidden"
        )
    return stripped


def truncate_to_words(text: str, max_words: int) -> str:
    """Cut a hint to the word limit rather than letting it be rejected."""
    words = text.strip().split()
    return " ".join(words[:max_words]) if len(words) > max_words else text.strip()


# ----------------------------------------------------------------------
# Requests and results
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HintRequest:
    """Everything a provider may know.

    Note the absence: no opponent position, no board, no belief. A provider
    that wanted to leak could not reach anything to leak.
    """

    game_id: str
    role: str
    turn: int
    actual_direction: Direction | None
    """What we really did. ``None`` for a barrier placement."""
    map_area: str = ""
    max_words: int = MAX_HINT_WORDS_FALLBACK


@dataclass(frozen=True, slots=True)
class HintResult:
    text: str
    intent: str
    """``"truth"`` or ``"lie"`` -- declared, sealed in the commit, and revealed.

    Committing the intent is what stops a peer claiming after the fact that it
    "meant to lie" about a hint that turned out wrong.
    """
    claimed_direction: Direction | None = None
    provider: str = "template"


@dataclass(frozen=True, slots=True)
class HintReading:
    """What we made of an incoming hint."""

    claimed_direction: Direction | None
    confidence: float
    """How clearly the text names a direction, 0..1. Not how much we believe it."""
    raw: str = ""


# ----------------------------------------------------------------------
# Provider interface
# ----------------------------------------------------------------------


class HintProvider(Protocol):
    """Composes and reads hints. Never decides a move."""

    name: str

    def compose(self, request: HintRequest) -> HintResult: ...

    def interpret(self, text: str) -> HintReading: ...


# ----------------------------------------------------------------------
# Template provider -- the offline default
# ----------------------------------------------------------------------

_DIRECTION_WORDS: dict[Direction, tuple[str, ...]] = {
    Direction.N: ("north", "northward", "uptown"),
    Direction.S: ("south", "southward", "downtown"),
    Direction.E: ("east", "eastward", "eastside"),
    Direction.W: ("west", "westward", "westside"),
    Direction.STAY: ("still", "stationary", "unmoved"),
}
"""Keywords per direction, matched on whole words only.

Substring matching was tried first and is wrong: "nowhere" contains "here", so a
hint reading *"gone south, nowhere near Central Park"* matched both south and
stay, and the reader threw both away as contradictory. Words like "put" and
"here" are gone for the same reason -- they turn up inside ordinary prose.
"""

_LANDMARKS: dict[str, tuple[str, ...]] = {
    "new york": ("Times Square", "Central Park", "Brooklyn Bridge", "Harlem"),
    "london": ("the Thames", "Camden", "Soho", "Greenwich"),
    "paris": ("the Seine", "Montmartre", "the Marais", "Bastille"),
}
_GENERIC_LANDMARKS = ("the old market", "the river", "the high street", "the yard")

_TRUTH_TEMPLATES = (
    "heading {dir} past {place}",
    "moving {dir}, {place} behind me",
    "cutting {dir} near {place}",
    "slipping {dir} by {place}",
)
_LIE_TEMPLATES = (
    "doubling back {dir} toward {place}",
    "gone {dir}, nowhere near {place}",
    "breaking {dir} past {place}",
    "circling {dir} around {place}",
)
_STAY_TEMPLATES = (
    "holding still by {place}",
    "waiting it out near {place}",
)
_BARRIER_TEMPLATES = (
    "sealing the way by {place}",
    "closing a gap near {place}",
)

_OPPOSITE: dict[Direction, Direction] = {
    Direction.N: Direction.S,
    Direction.S: Direction.N,
    Direction.E: Direction.W,
    Direction.W: Direction.E,
}


def _seed(request: HintRequest) -> int:
    """A stable integer from the turn's identity.

    Hashed rather than using the raw turn so consecutive turns do not march
    through the template list in order, which would make the phrasing itself a
    tell. Deterministic: a replay reproduces every hint exactly.
    """
    material = f"{request.game_id}|{request.role}|{request.turn}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big")


def _landmarks(map_area: str) -> tuple[str, ...]:
    """Real landmarks for the agreed arena, or generic ones when unset."""
    return _LANDMARKS.get(map_area.strip().lower(), _GENERIC_LANDMARKS)


@dataclass
class TemplateHintProvider:
    """Deterministic, offline, zero-token hint composer and reader.

    ``lie_every`` controls how often a hint is deliberately misleading. It is a
    fixed cadence rather than a random draw so the behaviour is reproducible;
    an opponent who works the cadence out has learned something real about us,
    which is a fair part of the game.
    """

    name: str = "template"
    lie_every: int = 3

    def compose(self, request: HintRequest) -> HintResult:
        seed = _seed(request)
        places = _landmarks(request.map_area)
        place = places[seed % len(places)]
        max_words = request.max_words or MAX_HINT_WORDS_FALLBACK

        # Barrier placement: nothing to lie about directionally, so these are
        # always truthful. The placement itself is publicly declared anyway
        # (E-15), which makes a lie here pointless as well as detectable.
        if request.actual_direction is None:
            template = _BARRIER_TEMPLATES[seed % len(_BARRIER_TEMPLATES)]
            text = truncate_to_words(template.format(place=place), max_words)
            return HintResult(text, "truth", None, self.name)

        if request.actual_direction is Direction.STAY:
            template = _STAY_TEMPLATES[seed % len(_STAY_TEMPLATES)]
            text = truncate_to_words(template.format(place=place), max_words)
            return HintResult(text, "truth", Direction.STAY, self.name)

        lying = self.lie_every > 0 and (seed % self.lie_every == 0)
        claimed = (
            _OPPOSITE[request.actual_direction]
            if lying
            else request.actual_direction
        )
        pool = _LIE_TEMPLATES if lying else _TRUTH_TEMPLATES
        word = _DIRECTION_WORDS[claimed][seed % len(_DIRECTION_WORDS[claimed])]
        text = pool[seed % len(pool)].format(dir=word, place=place)

        return HintResult(
            text=truncate_to_words(text, max_words),
            intent="lie" if lying else "truth",
            claimed_direction=claimed,
            provider=self.name,
        )

    def interpret(self, text: str) -> HintReading:
        """Read a direction out of an incoming hint.

        Deterministic keyword matching. Reports only what the text *claims* --
        judging whether to believe it is the tracker's job, weighing the claim
        against the scent, which cannot lie.
        """
        if not isinstance(text, str) or not text.strip():
            return HintReading(None, 0.0, "")

        lowered = text.lower()
        tokens = set(re.findall(r"[a-z]+", lowered))
        matched: list[Direction] = []
        for direction, words in _DIRECTION_WORDS.items():
            if tokens & set(words):
                matched.append(direction)

        if not matched:
            return HintReading(None, 0.0, text)
        if len(matched) > 1:
            # Contradictory or hedged: it named more than one way to go.
            return HintReading(None, 0.2, text)
        return HintReading(matched[0], 0.9, text)


# ----------------------------------------------------------------------
# Safety wrapper
# ----------------------------------------------------------------------


@dataclass
class SafeHintProvider:
    """Wraps a provider so it can never break a turn.

    A hint is decoration on a move that is already decided. If a provider is
    slow, throws, or returns something invalid -- all of which a future
    network-backed provider will eventually do -- the turn must still go out.
    So every failure collapses to a fixed, valid fallback rather than
    propagating.
    """

    inner: HintProvider
    fallback: str = "moving on"
    failures: int = field(default=0, init=False)

    @property
    def name(self) -> str:
        return getattr(self.inner, "name", "unknown")

    def compose(self, request: HintRequest) -> HintResult:
        max_words = request.max_words or MAX_HINT_WORDS_FALLBACK
        try:
            result = self.inner.compose(request)
            validate_hint(result.text, max_words)
            if result.intent not in ("truth", "lie"):
                raise HintRejected(f"invalid intent {result.intent!r}")
            return result
        except Exception:
            self.failures += 1
            return HintResult(
                text=truncate_to_words(self.fallback, max_words),
                intent="truth",
                claimed_direction=None,
                provider=f"{self.name}-fallback",
            )

    def interpret(self, text: str) -> HintReading:
        try:
            return self.inner.interpret(text)
        except Exception:
            self.failures += 1
            return HintReading(None, 0.0, text if isinstance(text, str) else "")


def default_provider() -> SafeHintProvider:
    """The shipped default: deterministic templates, wrapped for safety."""
    return SafeHintProvider(TemplateHintProvider())
