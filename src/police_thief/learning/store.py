"""Atomic, fail-safe persistence for learning profiles.

Persists under ``results/learning/`` (default): ``global_profile.json`` and
``opponents/<key>.json``. Every write is atomic (temp file + ``os.replace``,
same directory so the replace is same-filesystem) -- an interrupted match
can leave a stray ``.tmp`` file, never a half-written profile. Every read is
wrapped so a missing, corrupt, or schema-incompatible file degrades to a
fresh default profile rather than raising: learning failure must never make
the actual peer fail.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from pathlib import Path

from police_thief.learning.profile import LearningProfile

DEFAULT_LEARNING_DIR = Path("results/learning")
GLOBAL_PROFILE_NAME = "global_profile.json"
OPPONENTS_SUBDIR = "opponents"

_SAFE_KEY = re.compile(r"[^A-Za-z0-9_-]+")


def opponent_key(declared_group_name: str | None) -> str:
    """A filesystem-safe, stable key from the opponent's *declared*
    ``group_name`` (the only opponent identity the protocol actually
    exchanges over HELLO -- there is no wire field for the private
    ``group_id``). ``None``/empty collapses to a fixed "unknown" key so an
    unidentified opponent still degrades to the global profile rather than
    crashing the lookup.
    """
    name = (declared_group_name or "").strip()
    if not name:
        return "unknown"
    return _SAFE_KEY.sub("-", name).strip("-").lower() or "unknown"


def _global_path(learning_dir: Path) -> Path:
    return Path(learning_dir) / GLOBAL_PROFILE_NAME


def _opponent_path(learning_dir: Path, key: str) -> Path:
    return Path(learning_dir) / OPPONENTS_SUBDIR / f"{key}.json"


def _load(path: Path) -> LearningProfile:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("profile file did not contain a JSON object")
        return LearningProfile.from_dict(raw)
    except FileNotFoundError:
        return LearningProfile()
    except Exception:
        # Corrupt, truncated, or schema-incompatible: fail safe, never crash
        # the peer over a damaged learning file.
        return LearningProfile()


def _save(path: Path, profile: LearningProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(profile.to_dict(), indent=2)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.remove(tmp_name)
        raise


def load_global_profile(learning_dir: Path = DEFAULT_LEARNING_DIR) -> LearningProfile:
    return _load(_global_path(learning_dir))


def load_opponent_profile(
    key: str, learning_dir: Path = DEFAULT_LEARNING_DIR
) -> LearningProfile:
    return _load(_opponent_path(learning_dir, key))


def save_global_profile(
    profile: LearningProfile, learning_dir: Path = DEFAULT_LEARNING_DIR
) -> None:
    _save(_global_path(learning_dir), profile)


def save_opponent_profile(
    key: str, profile: LearningProfile, learning_dir: Path = DEFAULT_LEARNING_DIR
) -> None:
    _save(_opponent_path(learning_dir, key), profile)
