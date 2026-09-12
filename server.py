"""
Thin HTTP API over the existing Werewolf brain + Nango store visits.
Serve the Phaser frontend from / and JSON under /api.
"""

import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from game_engine import GameEngine, Role, Phase
import agents
import nango_output

AI_PLAYER_NAMES = ["Maya", "Chris", "Priya", "Owen"]
HUMAN_NAME = "You"

app = FastAPI(title="AI Town")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = None
chat_log = []
secret_log = []
library_history = []
busy = False
busy_note = ""
lock = threading.Lock()


class VoteBody(BaseModel):
    voter: str = HUMAN_NAME
    target: str


class PromptBody(BaseModel):
    prompt: str


class MessageBody(BaseModel):
    message: str


class QuestionBody(BaseModel):
    question: str
    session_id: str = "town"


def _model_for(name):
    index = AI_PLAYER_NAMES.index(name) if name in AI_PLAYER_NAMES else 0
    return agents.MODEL_A if index % 2 == 0 else agents.MODEL_B


def _serialize():
    reveal = engine is not None and engine.state.phase == Phase.GAME_OVER
    players = []
    if engine:
        for p in engine.state.players:
            item = {"name": p.name, "is_ai": p.is_ai, "alive": p.alive}
            if reveal:
                item["role"] = p.role.value if p.role else None
            players.append(item)
    return {
        "phase": engine.state.phase.value if engine else "lobby",
        "day_number": engine.state.day_number if engine else 0,
        "winner": engine.state.winner if engine else None,
        "players": players,
        "log": list(engine.state.log) if engine else [],
        "chat": list(chat_log),
        "secret": list(secret_log) if reveal else [],
        "votes": dict(engine.state.votes) if engine else {},
        "busy": busy,
        "busy_note": busy_note,
    }


def _run_ai_day_messages():
    global busy, busy_note
    if not engine:
        return
    busy = True
    busy_note = "Townsfolk are talking..."
    try:
        for player in list(engine.state.alive_players()):
            if not player.is_ai:
                continue
            model = _model_for(player.name)
            msg = agents.get_day_message(player.name, player.role.value, chat_log, model)
            with lock:
                chat_log.append(f"{player.name}: {msg}")
    finally:
        busy = False
        busy_note = ""


def _resolve_after_human_vote():
    global busy, busy_note, secret_log
    if not engine:
        return
    busy = True
    busy_note = "The table is voting..."
    try:
        alive_names = [p.name for p in engine.state.alive_players()]
        for player in list(engine.state.alive_players()):
            if not player.is_ai:
                continue
            model = _model_for(player.name)
            target = agents.get_day_vote(
                player.name, player.role.value, alive_names, chat_log, model
            )
            with lock:
                engine.cast_vote(player.name, target)

        engine.resolve_day_vote()
        if engine.state.phase == Phase.GAME_OVER:
            return

        busy_note = "Night falls. The mafia confer..."
        secret_log = []
        alive_names = [p.name for p in engine.state.alive_players()]
        mafia_players = [p for p in engine.state.alive_players() if p.role == Role.MAFIA]
        mafia_names = [p.name for p in mafia_players]
        villagers = [n for n in alive_names if n not in mafia_names] or list(alive_names)
        target = villagers[0]
        for player in mafia_players:
            if not player.is_ai:
                continue
            model = _model_for(player.name)
            msg = agents.get_mafia_night_message(
                player.name, mafia_names, alive_names, chat_log, secret_log, model
            )
            secret_log.append(f"{player.name}: {msg}")
            target = agents.get_mafia_vote(
                player.name, alive_names, model, mafia_names, secret_log
            )
        if mafia_players:
            engine.set_mafia_target(mafia_players[0].name, target)
        engine.resolve_night()
        if engine.state.phase != Phase.GAME_OVER:
            busy_note = "A new day begins..."
            _run_ai_day_messages()
    finally:
        busy = False
        busy_note = ""


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/game/state")
def game_state():
    return _serialize()


@app.post("/api/game/start")
def game_start():
    global engine, chat_log, secret_log, library_history, busy
    if busy:
        raise HTTPException(status_code=409, detail="A game action is already in progress")
    engine = GameEngine(mafia_count=2, detective_count=1)
    chat_log = []
    secret_log = []
    library_history = []
    engine.add_player(HUMAN_NAME, is_ai=False)
    for name in AI_PLAYER_NAMES:
        engine.add_player(name, is_ai=True, model_name=_model_for(name))
    try:
        engine.start_game()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    threading.Thread(target=_run_ai_day_messages, daemon=True).start()
    return _serialize()


@app.post("/api/game/vote")
def game_vote(body: VoteBody):
    if not engine:
        raise HTTPException(status_code=400, detail="No game in progress. Start one first.")
    if busy:
        raise HTTPException(status_code=409, detail="Wait — the table is still talking.")
    if engine.state.phase != Phase.DAY_DISCUSSION:
        raise HTTPException(status_code=400, detail=f"Cannot vote during {engine.state.phase.value}")
    try:
        engine.cast_vote(body.voter, body.target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    chat_log.append(f"{body.voter}: I vote for {body.target}.")
    threading.Thread(target=_resolve_after_human_vote, daemon=True).start()
    return _serialize()


@app.post("/api/store/photography")
def store_photography(body: PromptBody):
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Tell the photographer what to shoot.")
    try:
        image_url = nango_output.generate_photo(body.prompt.strip())
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"image_url": image_url, "prompt": body.prompt.strip()}


@app.post("/api/store/postoffice")
def store_postoffice(body: MessageBody):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Write a message to send.")
    try:
        result = nango_output.send_message(body.message.strip())
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"ok": True, "result": result}


@app.post("/api/store/bank")
def store_bank():
    try:
        return nango_output.get_crypto_prices()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/api/store/library")
def store_library(body: QuestionBody):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Ask the librarian a question.")
    global library_history
    library_history.append({"role": "user", "content": body.question.strip()})
    answer = agents.get_library_chat_response(library_history[:-1], body.question.strip())
    library_history.append({"role": "assistant", "content": answer})
    return {"answer": answer, "messages": list(library_history)}


frontend_dir = Path(__file__).resolve().parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
