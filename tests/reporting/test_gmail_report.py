"""Regression tests for the gmail_status reporting-consistency bug (send
side). See ``test_match_report.py`` for the payload/local-file half.

Uses ``tests/reporting/_helpers.py::install_fake_google`` so
``send_report_email``'s send path can be exercised deterministically, with
no real network call and no real OAuth flow.
"""

from __future__ import annotations

import base64
import json

from police_thief.reporting.gmail_report import NOT_CONFIGURED, send_report_email
from police_thief.reporting.match_report import write_report
from tests.reporting._helpers import install_fake_google, make_report


def test_credentials_missing_returns_clear_status(tmp_path):
    report = make_report()
    report_path = write_report(report)
    sent, status = send_report_email(
        report, report_path,
        recipient="team@example.com",
        credentials_path=tmp_path / "missing-credentials.json",
        token_path=tmp_path / "token.json",
    )
    assert sent is False
    assert status.startswith(NOT_CONFIGURED)


def test_successful_send_status(tmp_path, monkeypatch):
    install_fake_google(monkeypatch, raise_on_send=None, captured={})
    (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")
    (tmp_path / "token.json").write_text("{}", encoding="utf-8")

    report = make_report(gmail_status="not attempted")
    report_path = write_report(report)
    sent, status = send_report_email(
        report, report_path,
        recipient="team@example.com",
        credentials_path=tmp_path / "credentials.json",
        token_path=tmp_path / "token.json",
    )
    assert sent is True
    assert status == "sent"

    report.gmail_status = status
    write_report(report)
    on_disk = json.loads(report_path.read_text(encoding="utf-8"))
    assert on_disk["gmail_status"] == "sent"


def test_failed_send_status(tmp_path, monkeypatch):
    install_fake_google(
        monkeypatch, raise_on_send=RuntimeError("connection reset"), captured={}
    )
    (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")
    (tmp_path / "token.json").write_text("{}", encoding="utf-8")

    report = make_report()
    report_path = write_report(report)
    sent, status = send_report_email(
        report, report_path,
        recipient="team@example.com",
        credentials_path=tmp_path / "credentials.json",
        token_path=tmp_path / "token.json",
    )
    assert sent is False
    assert "connection reset" in status

    report.gmail_status = status
    write_report(report)
    on_disk = json.loads(report_path.read_text(encoding="utf-8"))
    assert on_disk["gmail_status"] == status
    assert "not attempted" not in on_disk["gmail_status"]


def test_email_payload_never_says_not_attempted_during_real_send(tmp_path, monkeypatch):
    """The exact regression: build the body during a real (faked) send
    attempt and confirm it never carries the pre-send placeholder."""
    captured: dict = {}
    install_fake_google(monkeypatch, raise_on_send=None, captured=captured)
    (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")
    (tmp_path / "token.json").write_text("{}", encoding="utf-8")

    report = make_report(gmail_status="not attempted")
    report_path = write_report(report)
    send_report_email(
        report, report_path,
        recipient="team@example.com",
        credentials_path=tmp_path / "credentials.json",
        token_path=tmp_path / "token.json",
    )

    raw = base64.urlsafe_b64decode(captured["body"]["raw"].encode("ascii"))
    text = raw.decode("utf-8", errors="ignore")
    assert "not attempted" not in text
    assert "gmail_status" not in text
