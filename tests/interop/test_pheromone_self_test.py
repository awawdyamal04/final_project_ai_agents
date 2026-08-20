"""Cross-team interop audit -- pheromone field (SPEC section 5).

**N/A for cross-team compatibility, not FAIL.** Per SPEC: "each peer emits
its own [scent field] and transmits it, so this is not re-derived
cross-team" -- a wrong port only breaks a peer's OWN belief map, and this
project's wire never even transmits the field at all (see
``test_wire_shape_and_locked_models.py``). It would only become a real
interop requirement if this project declared a ``scent_model`` locked
model (SPEC section 7) to match an opponent's -- which it does not.

This project's own ``domain/scent.py`` (``ScentModel``/``ScentField``) is
neither of the two registered models: it uses a **fitted Gaussian**
(``sigma=1.15``, squared-Euclidean offset, DECISIONS.md D-39) rather than
the reference's linear-Chebyshev falloff (``vectors/pheromone.json``,
tested here only to show the divergence, not to assert compatibility) or
the book's own verbatim 5x5 kernel table + upper clamp
(``multiplicative_book_v1``, SPEC section 5.1). This is a knowingly
undocumented third variant -- flagged in docs/OPEN_QUESTIONS.md rather than
silently left as a byte-identity assumption.

Deliberately not "fixed": the Gaussian choice is an already-recorded
project decision (D-39), and adding the book's missing upper clamp would
change turn-over-turn scent intensity at a repeatedly-visited cell in a way
an existing, currently-passing strategy test relies on
(``tests/strategy/test_scent_belief_strategy.py``) -- exactly the kind of
strategy-behaviour ripple this audit was told to avoid absent a real
cross-team requirement.
"""

from __future__ import annotations

from pathlib import Path

from police_thief.config.loader import load_shared_config
from police_thief.domain.board import Board
from police_thief.domain.coordinates import Coordinate
from police_thief.domain.scent import ScentField, ScentModel

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_CONFIG_PATH = REPO_ROOT / "config" / "game.json"


def _field(board_size: int = 7, grid_size: int = 5) -> ScentField:
    model = ScentModel(center_intensity=0.9, decay=0.1, window=grid_size)
    board = Board(size=board_size, origin_index=0)
    return ScentField(model=model, board=board)


def test_this_project_s_emission_is_not_the_reference_model():
    """Reference vector: centre 0.9, orthogonal-Chebyshev neighbour 0.6.
    This project's fitted-Gaussian model produces a visibly different
    orthogonal value at the same offset -- a real, known divergence, not a
    bug in either model considered alone (SPEC: 'two teams that each use a
    Gaussian in good faith can produce different fields, silently')."""
    field = _field()
    field.emit(Coordinate(3, 3))
    reference_orthogonal = 0.6
    ours_orthogonal = round(field.intensity_at(Coordinate(2, 3)), 3)
    assert ours_orthogonal != reference_orthogonal


def test_shared_config_still_drives_the_three_fixed_parameters():
    """App. F fixes centre intensity, decay and grid size regardless of
    model form -- only the model's curve shape is a project decision."""
    cfg = load_shared_config(SHARED_CONFIG_PATH)
    model = ScentModel.from_config(cfg)
    assert model.center_intensity == 0.9
    assert model.decay == 0.1
    assert model.window == 5
