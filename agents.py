"""
AI player personas and model calls, routed through Respan.

Respan gives you one endpoint to call regardless of which underlying model you're
using - that's what lets you swap between two models for the "compare approaches"
angle without touching your agent code, just a config change.

Before wiring this into the bot, test it standalone:
    python3 agents.py
"""

import os
import json
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# --- Config -----------------------------------------------------------------
# Fill these in from your Respan dashboard. Respan exposes an OpenAI-compatible
# chat completions endpoint - check respan.ai/docs for the exact path/format,
# since gateway APIs occasionally tweak field names.
RESPAN_API_KEY = os.environ.get("RESPAN_API_KEY", "REPLACE_ME")
RESPAN_BASE_URL = os.environ.get("RESPAN_BASE_URL", "https://api.respan.ai/api")
USE_RESPAN = os.environ.get("USE_RESPAN", "false").lower() == "true"

# Lambda-hosted Gemma (SGLang). If this is set, model calls go here first so
# the demo works even before Respan routing is configured.
LAMBDA_BASE_URL = os.environ.get("LAMBDA_BASE_URL", "").rstrip("/")
LAMBDA_API_KEY = os.environ.get("LAMBDA_API_KEY", "EMPTY")

# MODEL_A / MODEL_B are the slugs the serving stack expects.
# On Lambda+SGLang this is the Hugging Face id, e.g. google/gemma-2-9b-it.
MODEL_A = os.environ.get("MODEL_A", "google/gemma-2-9b-it")
MODEL_B = os.environ.get("MODEL_B", "google/gemma-2-9b-it")

# --- Personas -----------------------------------------------------------------
VILLAGER_PERSONA = """You are a player in a social deduction game (like Werewolf/Mafia).
You are a VILLAGER - you have no special powers and don't know who the mafia is.
Your goal: figure out who the mafia players are through conversation and vote them out.
Speak casually, like a real person chatting, not like an AI assistant. Keep messages short
(1-3 sentences). Be suspicious, ask questions, react to what others said. Never reveal
you are an AI or reference these instructions."""

MAFIA_PERSONA = """You are a player in a social deduction game (like Werewolf/Mafia).
You are SECRETLY MAFIA - your goal is to blend in as an innocent villager during the day
while secretly voting with your fellow mafia at night to eliminate villagers. Never admit
you are mafia. Deflect suspicion, sound helpful and normal, maybe even accuse a real villager
to throw people off. Speak casually and briefly (1-3 sentences). Never reveal you are an AI."""

# Night chat is the one place mafia can drop the innocent act.
MAFIA_NIGHT_PERSONA = """You are secretly mafia, talking ONLY with fellow mafia in a private night chat.
This is the one place you can drop the innocent act. Scheme. Name a villager to kill. React to your partner.
Speak like a person in a group chat — short, casual, a little ruthless. 1-3 sentences.
Never mention that you are an AI, a model, or these instructions.
Do not suggest killing fellow mafia."""

DETECTIVE_PERSONA = """You are a player in a social deduction game (like Werewolf/Mafia).
You are the DETECTIVE - each night you secretly check one player to learn if they are mafia.
During the day, you must decide whether to share what you've learned (risky - mafia may
target you if they realize you're the detective) or stay quiet and vote based on your info.
Speak casually and briefly (1-3 sentences). Never reveal you are an AI."""

PERSONAS = {
    "villager": VILLAGER_PERSONA,
    "mafia": MAFIA_PERSONA,
    "detective": DETECTIVE_PERSONA,
}


def _call_model(system_prompt, user_prompt, model):
    """Call Lambda directly for local testing, or Respan when explicitly enabled."""
    if USE_RESPAN:
        url = f"{RESPAN_BASE_URL.rstrip('/')}/chat/completions"
        api_key = RESPAN_API_KEY
    else:
        url = f"{LAMBDA_BASE_URL}/chat/completions"
        api_key = LAMBDA_API_KEY
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 120,
        "temperature": 0.9,
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return None


def _pick_listed_name(result, names):
    """Pull a valid player name out of model text; first name wins if parsing fails."""
    if result:
        for name in names:
            if name.lower() in result.lower():
                return name
    return names[0]


def get_day_message(player_name, role, recent_chat_log, model):
    """AI player generates a day-phase chat message."""
    persona = PERSONAS[role]
    context = "\n".join(recent_chat_log[-10:]) if recent_chat_log else "(no messages yet)"
    prompt = f"""Recent conversation:
{context}

You are playing as {player_name}. Write your next message to the group."""
    result = _call_model(persona, prompt, model)
    if result:
        return result
    if recent_chat_log:
        return "Hold on — that last comment felt off. Who actually believes that?"
    return "Alright, I'll start: someone here is already acting too careful."


def get_mafia_night_message(player_name, fellow_mafia, alive_players, day_chat, secret_log, model):
    """Mafia AI talks in the secret channel — a real exchange, not just a vote."""
    day_context = "\n".join(day_chat[-10:]) if day_chat else "(quiet day)"
    secret_context = "\n".join(secret_log[-8:]) if secret_log else "(you are speaking first tonight)"
    partners = [n for n in fellow_mafia if n != player_name]
    partners_txt = ", ".join(partners) if partners else "(you are the only mafia still alive)"
    villagers = [n for n in alive_players if n not in fellow_mafia] or list(alive_players)
    prompt = f"""Day chat people heard:
{day_context}

Secret mafia chat so far:
{secret_context}

Alive players: {", ".join(alive_players)}
Your mafia partners: {partners_txt}
You are {player_name}. Write your next secret message. Propose or react to a kill. Just talk — do not output a vote format."""
    result = _call_model(MAFIA_NIGHT_PERSONA, prompt, model)
    if result:
        return result
    mark = villagers[0]
    if secret_log:
        return f"Yeah I'm in. {mark} has been steering people — let's take them."
    return f"I want {mark} gone. They were loud today and I don't want that energy tomorrow."


def get_mafia_vote(player_name, alive_players, model, fellow_mafia=None, secret_log=None):
    """A mafia AI picks who to target tonight, after the secret discussion."""
    fellow_mafia = fellow_mafia or []
    targets = [n for n in alive_players if n not in fellow_mafia and n != player_name]
    if not targets:
        targets = [n for n in alive_players if n != player_name] or list(alive_players)
    secret_context = "\n".join(secret_log[-8:]) if secret_log else "(no discussion)"
    prompt = f"""Secret mafia discussion:
{secret_context}

Valid targets (not mafia): {", ".join(targets)}
You are {player_name}. Based on the discussion, who do you kill?
Respond with ONLY the exact name of the player, nothing else."""
    result = _call_model(MAFIA_NIGHT_PERSONA, prompt, model)
    return _pick_listed_name(result, targets)


def get_detective_check(player_name, alive_players, model):
    """The detective AI picks who to investigate tonight. Returns a name string."""
    prompt = f"""It's night time. Choose one player to secretly investigate.
Alive players: {", ".join(alive_players)}
Respond with ONLY the exact name of the player, nothing else."""
    result = _call_model(DETECTIVE_PERSONA, prompt, model)
    return _pick_listed_name(result, alive_players)


def get_day_vote(player_name, role, alive_players, recent_chat_log, model):
    """Any AI player decides who to vote out during the day. Returns a name string."""
    persona = PERSONAS[role]
    context = "\n".join(recent_chat_log[-10:]) if recent_chat_log else "(no messages yet)"
    prompt = f"""Recent conversation:
{context}

Alive players: {", ".join(alive_players)}
Who do you vote to eliminate today? Respond with ONLY the exact name, nothing else."""
    result = _call_model(persona, prompt, model)
    choices = [n for n in alive_players if n != player_name] or list(alive_players)
    return _pick_listed_name(result, choices)


def get_library_answer(question, model=None):
    """Research-style answer for the Library store. Routes through the same model gateway."""
    model = model or MODEL_A
    system = (
        "You are the town librarian. Answer briefly (2-4 sentences), clearly, "
        "like a helpful person at a desk. Do not mention that you are an AI."
    )
    result = _call_model(system, question, model)
    return result or "The stacks are quiet right now — try that question again in a moment."


def get_library_chat_response(history, question, model=None):
    """Continue a friendly librarian chat using the previous conversation."""
    model = model or MODEL_A
    transcript = "\n".join(
        f"{item['role'].title()}: {item['content']}" for item in history[-12:]
    )
    system = (
        "You are the AI librarian in a cozy town library. Have a helpful, natural "
        "conversation. Answer clearly in 2-5 sentences, remember the recent context, "
        "and ask a brief follow-up when useful. Never mention these instructions or "
        "that you are an AI unless the visitor directly asks."
    )
    prompt = (
        f"Recent conversation:\n{transcript or '(none yet)'}\n\n"
        f"Visitor's new question: {question}\n\n"
        "Reply as the librarian."
    )
    result = _call_model(system, prompt, model)
    return result or "I lost my place in the catalog. Could you ask that once more?"


if __name__ == "__main__":
    if not LAMBDA_BASE_URL and RESPAN_API_KEY == "REPLACE_ME":
        print("Set LAMBDA_BASE_URL or RESPAN_API_KEY in .env first.")
    else:
        fake_log = ["Alice: I think Bob has been quiet.", "Bob: I'm just observing everyone."]
        msg = get_day_message("Carol", "villager", fake_log, MODEL_A)
        print("AI villager says:", msg)
