# League match runbook

Practical commands only. See `CLAUDE.md`/`docs/PROTOCOL.md` for the design.

## 1. Expose our peers publicly (ngrok)

Our server already binds to `127.0.0.1` by default (`config/*.toml.example`
`[network] host/port`) and ngrok connects to that same machine's loopback --
**no code or config change is needed** for ngrok specifically. One tunnel per
peer process, in two separate terminals, alongside the two peer processes
themselves (four terminals total):

```
# Terminal 1 -- our cop process
python -m police_thief.peer.run --shared config/game.json ^
    --private config/police/game.toml --game-id <agreed-id> --hold

# Terminal 2 -- tunnel the cop's port (default 8801)
ngrok http 8801

# Terminal 3 -- our thief process
python -m police_thief.peer.run --shared config/game.json ^
    --private config/thief/game.toml --game-id <agreed-id> --hold

# Terminal 4 -- tunnel the thief's port (default 8802)
ngrok http 8802
```

Each `ngrok http` prints a `Forwarding` line, e.g.
`https://ab12-1-2-3-4.ngrok-free.app -> http://localhost:8801`. Our public
URL to send the opponent is that HTTPS URL **plus the `/mcp` path**:
`https://ab12-1-2-3-4.ngrok-free.app/mcp`.

If ngrok is unavailable, Localtonet works the same way (`localtonet http 8801`);
give its printed public URL + `/mcp` instead.

No auth token exists in the protocol today (config_sha256 + commit-reveal are
the integrity mechanism, not a connection-level secret). If a tunnel needs to
be private, use the tunnel tool's own auth (e.g. `ngrok http 8801 --basic-auth
"user:pass"`), not something invented here.

## 2. Point at the opponent

Copy the example TOML once (gitignored from then on -- see `.gitignore`):

```
cp config/cop.toml.example config/police/game.toml     # if we are cop
cp config/thief.toml.example config/thief/game.toml    # if we are thief
```

Edit `[network] opponent_url` in that file to the URL the other team sends
you, **or** override it per-run without editing the file:

```
python -m police_thief.peer.run --shared config/game.json ^
    --private config/police/game.toml --game-id <agreed-id> ^
    --opponent-url https://theirs.ngrok-free.app/mcp --hold
```

## 3. Preflight before the counting match

```
python scripts/league_preflight.py --shared config/game.json ^
    --private config/police/game.toml ^
    --opponent-url https://theirs.ngrok-free.app/mcp
```

Exit 0 + `PASS` means reachable, HELLO/capabilities accepted, config hash
matches, READY accepted -- safe to start counting turns. Any `FAIL` line
names the exact stage and reason.

## 4. Run the counting match

```
python -m police_thief.peer.run --shared config/game.json ^
    --private config/police/game.toml --game-id <agreed-id> ^
    --opponent-url https://theirs.ngrok-free.app/mcp --turns 35
```

At the end it prints `MATCH COMPLETE`/`TECHNICAL LOSS` plus game id,
opponent, role, turns, audit status, replay status (always "pending offline
replay" -- a live peer cannot know its own winner, D-41), and the Gmail
status. It always writes `results/league/<game_id>_<role>_<ts>.json` and
appends a row to `results/league/index.csv`, whether or not email sends.

## 5. Gmail reporting -- one-time setup

1. Google Cloud Console -> new/existing project -> **Enable the Gmail API**.
2. **OAuth consent screen** -> External -> add yourself as a test user.
3. **Credentials -> Create Credentials -> OAuth client ID -> Desktop app** ->
   download the JSON -> save as `credentials.json` in the repo root (already
   gitignored).
4. `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`
5. First real match run: a browser window opens once for consent; after
   that, `token.json` (also gitignored) is reused silently.

Without `credentials.json` present, the match runner still saves the JSON
report and prints `EMAIL NOT SENT -- OAUTH SETUP REQUIRED: ...` -- the result
is never lost.
