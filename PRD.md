# AI Town product requirements

## Goal

Deliver a three-minute walkable AI town demo in which a human visits real API-powered stores and then plays a social-deduction round against AI townsfolk.

## P0 — implemented

- Single controllable player with WASD/arrow movement.
- Collision against building blocks.
- Five building triggers: Photography Studio, Post Office, Arcade, Bank, Library.
- Original pixel-art town presentation with buildings, paths, trees, and player sprite.
- FastAPI endpoints for game state and store actions.
- Arcade Werewolf round reusing `game_engine.py` and `agents.py`.
- Four AI NPCs with distinct seats and speech bubbles.
- AI mafia discussion is private server state until reveal.
- Lambda/SGLang-compatible model endpoint configuration.
- Nango integration helpers that fail honestly when credentials are missing.
- Bank displays live Bitcoin and Ethereum prices with 24-hour changes.
- Library supports multi-turn AI chat with conversation history.

## P1 — supported hooks

- Respan gateway can be selected through environment configuration.
- Bank and Library store endpoints are available.
- A future trace panel can consume model metadata without changing the game API.
- The state polling interface can later be replaced by websockets.

## Deliberately out of scope

- Accounts, persistence, matchmaking, mobile layout, and real networked multiplayer.
- Commercial or unclear-license art assets.
- Multiple concurrent game rooms.

## Acceptance checks

1. `python3 game_engine.py` completes without error.
2. `python3 server.py` serves the Phaser town at `/` and API docs at `/docs`.
3. `/api/health` returns `{ "ok": true }`.
4. `/api/game/start` returns five players and a day phase.
5. The browser can enter Arcade, poll speech, and vote.
6. Store failures identify the missing integration instead of claiming success.
7. A successful run is recorded before presenting live.
