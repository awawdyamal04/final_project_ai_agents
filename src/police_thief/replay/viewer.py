"""Minimal offline replay viewer.

    python -m police_thief.replay.viewer --cop logs/audit_police_x.jsonl \\
                                        --thief logs/audit_thief_x.jsonl

Renders the reconstructed board turn by turn: both positions, the barriers, the
actions, the hints with their declared intent, the final result and the
verification stamp.

**Offline only.** This is allowed to show global truth because it runs after the
match, from sealed logs, once the nonces are public. It must never be reachable
from the live peer -- a live component that could render both positions would
break the rule that costs the project its grade. The import boundary is
asserted by ``tests/replay/test_two_log_replay.py``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from police_thief.config.loader import load_shared_config
from police_thief.domain.coordinates import Coordinate
from police_thief.replay.verifier import ReplayVerdict, TurnFrame, Verdict, replay_files

COP = "C"
THIEF = "T"
BARRIER = "#"
EMPTY = "."


def render_board(frame: TurnFrame, size: int, origin: int = 0) -> list[str]:
    """One frame as text rows. Global truth -- offline only."""
    barriers = set(frame.barriers)
    rows = []
    header = "    " + " ".join(str(c) for c in range(origin, origin + size))
    rows.append(header)
    for row in range(origin, origin + size):
        cells = []
        for col in range(origin, origin + size):
            cell = Coordinate(row, col)
            if cell == frame.cop_position and cell == frame.thief_position:
                cells.append("X")           # both -- a capture by coincidence
            elif cell == frame.cop_position:
                cells.append(COP)
            elif cell == frame.thief_position:
                cells.append(THIEF)
            elif cell in barriers:
                cells.append(BARRIER)
            else:
                cells.append(EMPTY)
        rows.append(f"  {row} " + " ".join(cells))
    return rows


def render_frame(frame: TurnFrame, size: int, origin: int = 0) -> str:
    lines = [f"  turn {frame.turn}"]
    lines += render_board(frame, size, origin)
    lines.append(
        f"    cop   {frame.cop_position}  {frame.cop_action:<18}"
        f' hint "{frame.cop_hint}" [{frame.cop_intent}]'
    )
    lines.append(
        f"    thief {frame.thief_position}  {frame.thief_action:<18}"
        f' hint "{frame.thief_hint}" [{frame.thief_intent}]'
    )
    if frame.note:
        lines.append(f"    note: {frame.note} (unresolved policy, Q-18)")
    return "\n".join(lines)


def render(verdict: ReplayVerdict, size: int, *, max_frames: int = 0) -> str:
    lines = [
        f"  legend        {COP}=cop  {THIEF}=thief  {BARRIER}=barrier  X=same cell",
        f"  turns         {verdict.turns_verified}",
    ]
    frames = verdict.frames
    if max_frames and len(frames) > max_frames:
        shown = frames[:1] + frames[-(max_frames - 1):]
        note = f"  (showing {len(shown)} of {len(frames)} turns)"
    else:
        shown, note = frames, ""
    if note:
        lines.append(note)
    for frame in shown:
        lines.append("")
        lines.append(render_frame(frame, size))

    lines.append("")
    if verdict.terminal is not None and verdict.score is not None:
        winner = (
            verdict.terminal.winner.value if verdict.terminal.winner else "nobody"
        )
        detail = (
            f" ({verdict.terminal.capture_reason.value})"
            if verdict.terminal.capture_reason
            else ""
        )
        lines.append(
            f"  result        {verdict.terminal.reason.value}{detail} "
            f"on turn {verdict.terminal.turn}"
        )
        lines.append(f"  winner        {winner}")
        lines.append(
            f"  score         cop {verdict.score.cop}, thief {verdict.score.thief}"
        )
        if verdict.claims:
            lines.append(f"  peer claims   {verdict.claims}")
    if verdict.reason:
        lines.append(f"  detail        {verdict.reason}")
    lines.append(f"  verification  {verdict.verdict.value}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m police_thief.replay.viewer",
        description=(
            "Independently reconstruct and verify a sub-game from both peers' "
            "audit logs. Offline; trusts neither peer's claimed result."
        ),
    )
    parser.add_argument("--cop", required=True)
    parser.add_argument("--thief", required=True)
    parser.add_argument("--shared", default="config/game.json")
    parser.add_argument(
        "--max-frames",
        type=int,
        default=4,
        help="limit rendered turns (0 for all)",
    )
    args = parser.parse_args(argv)

    config = load_shared_config(args.shared)
    verdict = replay_files(args.cop, args.thief, config)

    print("replay verification (offline, two-log)")
    print(f"  cop log       {Path(args.cop).name}")
    print(f"  thief log     {Path(args.thief).name}")
    print(render(verdict, config.grid_size, max_frames=args.max_frames))

    return 0 if verdict.verdict is Verdict.VERIFIED_OK else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
