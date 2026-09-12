# AI Town architecture

## Runtime shape

```text
Browser / Phaser 3
       |
       | JSON fetch + polling
       v
FastAPI server.py
       |
       +-- game_engine.py
       +-- agents.py --> Lambda SGLang or Respan gateway --> Gemma
       +-- nango_output.py --> Nango proxy --> Slack / image provider
```

The browser owns presentation and movement. The Python server owns game state, secrets, model calls, and third-party credentials. The server handles one demo session at a time.

## Frontend

- `frontend/index.html` loads Phaser from a pinned CDN version and provides the store dialogue overlay.
- `frontend/src/main.js` registers `TownScene` and `ArcadeScene`.
- `frontend/src/scenes/TownScene.js` loads the original pixel-art town background, player sprite, collisions, door triggers, and store forms.
- `frontend/src/scenes/ArcadeScene.js` renders five seats, polls game state, shows speech bubbles, and sends NPC votes.
- `frontend/src/api.js` is the only browser-to-backend transport layer.

The map is intentionally generated with Phaser primitives for the first demo; it avoids an unverified third-party tileset license and keeps the build dependency-free.

## Backend

`server.py` wraps the pre-existing engine rather than duplicating game rules. `/api/game/start` creates one human and four AI players. AI turns run in daemon threads so the browser can poll progress while Lambda responds. `/api/game/state` hides the private mafia transcript until the game is over.

The game endpoint uses the same personas as the Discord build. After a human vote, AI votes are generated, the day is resolved, mafia messages are generated privately, a target is selected, and the night is resolved.

## Store integrations

Each store has its own endpoint and a small function in `nango_output.py`:

- Photography Studio → image generation through Nango.
- Post Office → Slack message through Nango.
- Bank → live Bitcoin and Ethereum price lookup, through a CoinGecko Nango connection when configured or CoinGecko's public endpoint for local rehearsal.
- Library → stateful multi-turn librarian chat through the configured model gateway.

Errors become HTTP 503 responses and are shown in the in-world dialogue panel. The UI never displays a fake success.

## Security and demo constraints

- Keep `.env` out of version control.
- Restrict the Lambda firewall to the demo network and use an API key when the endpoint is not temporary.
- Do not send hidden roles or the mafia transcript to the browser before reveal.
- The app is intentionally single-session and single-process for the hackathon.
- The live demo should have a recorded fallback.
