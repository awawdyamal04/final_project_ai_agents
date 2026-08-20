"""Shared test helpers for the reporting suite -- not itself a test module."""

from __future__ import annotations

import sys
import types

from police_thief.reporting.match_report import MatchReport


def make_report(**overrides) -> MatchReport:
    fields = {
        "game_id": "g1",
        "role": "police",
        "opponent_url": "http://127.0.0.1:8802/mcp",
        "opponent_team": "Team B",
        "turns_played": 12,
        "exit_status": "MATCH COMPLETE",
        "audit_status": "Verified OK",
    }
    fields.update(overrides)
    return MatchReport(**fields)


def install_fake_google(monkeypatch, *, raise_on_send: Exception | None, captured: dict):
    """Stub just enough of the google API surface for one send attempt.

    The real ``google-api-python-client``/``google-auth-oauthlib`` packages
    are optional (see ``gmail_report.py``'s guarded import) and not
    installed here. A pre-valid fake credential skips the refresh/
    interactive-consent branch entirely, so only
    ``googleapiclient.discovery.build`` needs to behave -- which is where
    the real network call would happen.
    """

    class _FakeCreds:
        valid = True

        @classmethod
        def from_authorized_user_file(cls, path, scopes):
            return cls()

    class _Executor:
        def execute(self):
            if raise_on_send is not None:
                raise raise_on_send
            return {"id": "fake-message-id"}

    class _FakeMessages:
        def send(self, userId, body):
            captured["body"] = body
            return _Executor()

    class _FakeService:
        def users(self):
            return types.SimpleNamespace(messages=lambda: _FakeMessages())

    for name in (
        "google", "google.auth", "google.auth.transport",
        "google.oauth2", "google_auth_oauthlib", "googleapiclient",
    ):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))

    requests_mod = types.ModuleType("google.auth.transport.requests")
    requests_mod.Request = object
    monkeypatch.setitem(sys.modules, "google.auth.transport.requests", requests_mod)

    creds_mod = types.ModuleType("google.oauth2.credentials")
    creds_mod.Credentials = _FakeCreds
    monkeypatch.setitem(sys.modules, "google.oauth2.credentials", creds_mod)

    flow_mod = types.ModuleType("google_auth_oauthlib.flow")
    flow_mod.InstalledAppFlow = object
    monkeypatch.setitem(sys.modules, "google_auth_oauthlib.flow", flow_mod)

    discovery_mod = types.ModuleType("googleapiclient.discovery")
    discovery_mod.build = lambda name, version, credentials=None: _FakeService()
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", discovery_mod)
