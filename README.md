# AI Town

A walkable Phaser town where every store is a real AI/API interaction. The Arcade contains a visual Werewolf game: one human sits with four AI townsfolk, while the mafia secretly coordinate through the backend.

## What is implemented

- `frontend/` — Phaser 3 pixel-art town map, keyboard movement, building triggers, store panels, and Arcade scene.
- `server.py` — FastAPI HTTP layer over the existing game engine and store integrations.
- `game_engine.py` — deterministic Werewolf rules and state machine.
- `agents.py` — villager/mafia/detective personas, Lambda Gemma support, Respan support, and Library answers.
- `nango_output.py` — Nango-backed Photography Studio, Post Office, live crypto Bank, and Slack recap helpers.
- `bot.py` — the original Discord prototype, still available as a fallback/demo backup.
- `ARCHITECTURE.md` — implementation map and request flows.
- `PRD.md` — checked-in product requirements and demo scope.

## Run AI Town locally

From this folder:

```bash
python3 -m pip install -r requirements.txt
python3 server.py
```

Open <http://127.0.0.1:8000> in a browser. Use **WASD** or arrow keys, then press **E** at a doorway.

The API also exposes interactive documentation at <http://127.0.0.1:8000/docs> and a health check at <http://127.0.0.1:8000/api/health>.

## Environment

Copy `env.example` to `.env` and fill in only the integrations you are using.

### Lambda Gemma

The current demo uses an OpenAI-compatible SGLang endpoint:

```env
LAMBDA_BASE_URL=http://YOUR_LAMBDA_IP:30000/v1
LAMBDA_API_KEY=EMPTY
MODEL_A=google/gemma-2-9b-it
MODEL_B=google/gemma-2-9b-it
```

The API layer prefers Lambda when `LAMBDA_BASE_URL` is present. Never commit `.env` or expose a Lambda endpoint without a firewall/API key outside a controlled demo.

### Respan

For the scored sponsor version, configure Respan's model/provider routing, then set:

```env
USE_RESPAN=true
RESPAN_BASE_URL=https://api.respan.ai/api
RESPAN_API_KEY=your_key
MODEL_A=your_respan_model_slug_a
MODEL_B=your_respan_model_slug_b
```

With `USE_RESPAN=true`, every NPC call uses Respan's OpenAI-compatible chat-completions endpoint. For a fast Lambda-only rehearsal, leave `USE_RESPAN=false`; calls go directly to the SGLang endpoint in `LAMBDA_BASE_URL`.

Test with:

```bash
python3 agents.py
```

### Nango

Nango-backed store calls require the relevant secret, connection, and provider configuration values. The Post Office currently posts through the configured Slack connection. Photography expects an OpenAI-compatible image-generation connection; set `NANGO_IMAGE_CONNECTION_ID` if it differs from the Slack connection.

Without Nango credentials, store endpoints return a clear `503` rather than pretending an API call succeeded. Library and Arcade dialogue can still run through Lambda.

## API

- `POST /api/game/start` — starts one five-player round.
- `GET /api/game/state` — returns phase, players, chat, votes, and progress state.
- `POST /api/game/vote` — body `{ "voter": "You", "target": "Maya" }`.
- `POST /api/store/photography` — body `{ "prompt": "..." }`.
- `POST /api/store/postoffice` — body `{ "message": "..." }`.
- `POST /api/store/bank` — returns live Bitcoin and Ethereum USD prices plus 24-hour changes.
- `POST /api/store/library` — body `{ "question": "..." }`; preserves the Library conversation.

The browser polls game state instead of using websockets, keeping the demo reliable and easy to rehearse.

## Demo path

1. Start the server and open the town.
2. Walk into Photography Studio or Post Office and trigger one visible store call.
3. Walk into Arcade. The human player is seated with Maya, Chris, Priya, and Owen.
4. Watch AI dialogue appear in speech bubbles; click one NPC to vote.
5. Show the reveal and Respan traces, then explain Lambda and Nango.
6. Keep a screen recording of a successful round as the backup.

## Original Discord fallback

The Discord version remains available:

```bash
python3 bot.py
```

It uses `!join`, `!startgame`, `!vote <name>`, and human-mafia `!kill <name>`.
