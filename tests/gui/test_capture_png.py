"""``capture_window``: the actual grab, against a fake window (no real Tk, no
real desktop capture -- ``PIL.ImageGrab`` is stubbed via ``sys.modules``).
Split out of ``test_capture.py`` (150-line compliance pass, D-44); see
``test_should_capture.py`` for the pure trigger-logic half."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from police_thief.gui.capture import capture_window


class _FakeRoot:
    def __init__(self, *, width: int = 300, height: int = 200) -> None:
        self.updated = 0
        self._width = width
        self._height = height

    def update(self) -> None:
        self.updated += 1

    def winfo_rootx(self) -> int:
        return 10

    def winfo_rooty(self) -> int:
        return 20

    def winfo_width(self) -> int:
        return self._width

    def winfo_height(self) -> int:
        return self._height


class _BrokenRoot(_FakeRoot):
    def update(self) -> None:
        raise RuntimeError("window already destroyed")


class _FakeCanvas:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.postscript_calls: list[str] = []

    def postscript(self, *, file: str, colormode: str) -> None:
        if self.fail:
            raise RuntimeError("no postscript converter available")
        self.postscript_calls.append(file)
        Path(file).write_text("%!PS-Adobe fake\n")


class _FakeWindow:
    def __init__(self, *, root: _FakeRoot | None = None, canvas: _FakeCanvas | None = None) -> None:
        self.root = root or _FakeRoot()
        self.canvas = canvas or _FakeCanvas()


class _FakeImage:
    def save(self, path) -> None:
        Path(path).write_bytes(b"fake-png-bytes")


def _stub_pil(monkeypatch, *, grab):
    """Install a fake ``PIL.ImageGrab`` in sys.modules for the duration of a
    test, so ``from PIL import ImageGrab`` inside capture_window resolves to
    it regardless of whether real Pillow happens to be installed here."""
    fake_image_grab = types.SimpleNamespace(grab=grab)
    fake_pil = types.ModuleType("PIL")
    fake_pil.ImageGrab = fake_image_grab
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.ImageGrab", fake_image_grab)


def test_capture_window_writes_a_real_png_via_imagegrab(tmp_path, monkeypatch):
    grabbed = {}

    def fake_grab(bbox):
        grabbed["bbox"] = bbox
        return _FakeImage()

    _stub_pil(monkeypatch, grab=fake_grab)

    window = _FakeWindow()
    target = tmp_path / "evidence" / "cop.png"

    outcome = capture_window(window, target)

    assert outcome.ok
    assert outcome.path == str(target)
    assert not outcome.degraded
    assert target.exists()
    assert window.root.updated == 1
    assert grabbed["bbox"] == (10, 20, 10 + 300, 20 + 200)


def test_capture_window_falls_back_to_degraded_eps_when_imagegrab_fails(tmp_path, monkeypatch):
    def fake_grab(bbox):
        raise OSError("screen grab not available in this session")

    _stub_pil(monkeypatch, grab=fake_grab)

    window = _FakeWindow()
    target = tmp_path / "cop.png"

    outcome = capture_window(window, target)

    assert outcome.path == str(target.with_suffix(".eps"))
    assert outcome.degraded is True
    assert not outcome.ok, "a degraded fallback must never report as equivalent evidence"
    assert "ImageGrab failed" in outcome.detail
    assert "OSError" in outcome.detail
    assert Path(outcome.path).exists()


def test_capture_window_reports_missing_pillow_clearly_and_falls_back(tmp_path, monkeypatch):
    # sys.modules[name] = None is the documented way to force ImportError
    # for `name`, regardless of whether it is actually installed.
    monkeypatch.setitem(sys.modules, "PIL", None)

    window = _FakeWindow()
    outcome = capture_window(window, tmp_path / "cop.png")

    assert outcome.degraded is True
    assert "Pillow not installed" in outcome.detail


def test_capture_window_reports_total_failure_clearly_when_both_paths_fail(tmp_path, monkeypatch):
    def fake_grab(bbox):
        raise OSError("no grab")

    _stub_pil(monkeypatch, grab=fake_grab)

    window = _FakeWindow(canvas=_FakeCanvas(fail=True))
    outcome = capture_window(window, tmp_path / "cop.png")

    assert outcome.path is None
    assert outcome.degraded is False
    assert not outcome.ok
    assert "EPS fallback also failed" in outcome.detail


def test_capture_window_reports_clearly_when_the_window_is_already_gone(tmp_path):
    window = _FakeWindow(root=_BrokenRoot())
    outcome = capture_window(window, tmp_path / "cop.png")

    assert outcome.path is None
    assert "window unavailable" in outcome.detail
