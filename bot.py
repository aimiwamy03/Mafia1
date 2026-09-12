"""
Discord bot for AI Werewolf/Mafia.

Setup before running:
1. pip install discord.py requests python-dotenv
2. Create a Discord application + bot at discord.com/developers/applications,
   enable "Message Content Intent" under Bot settings, invite it to your server.
3. Create two text channels: #day-chat (public) and #mafia-secret
   (set permissions so only the bot can post/see it - or just don't
   invite regular members to it for the hackathon).
4. Copy .env.example to .env and fill in DISCORD_TOKEN, DAY_CHANNEL_ID,
   MAFIA_CHANNEL_ID, plus the Respan keys used by agents.py.
5. Run: python3 bot.py

Commands (typed as normal messages, simplest to build under time pressure -
slash commands are nicer but take longer to register/debug):
  !startgame          - starts a new game with the players who have !joined
  !join               - join the lobby as a human player
  !vote <name>         - cast your vote during the day phase
  !kill <name>         - human mafia: lock the night target in #mafia-secret
"""

import os
import asyncio
import random
from pathlib import Path
import discord
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from game_engine import GameEngine, Role, Phase
import agents

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DAY_CHANNEL_ID = int(os.environ["DAY_CHANNEL_ID"])
MAFIA_CHANNEL_ID = int(os.environ["MAFIA_CHANNEL_ID"])

# Ordinary first names — if judges can tell from the nametag, the hook dies.
AI_PLAYER_NAMES = ["Maya", "Chris", "Priya", "Owen"]

# Day chat should feel like people typing, not a bot dump. Seconds.
HUMAN_HEAD_START_SECONDS = 8
AI_MESSAGE_GAP_MIN = 3.5
AI_MESSAGE_GAP_MAX = 6.5
MAFIA_CHAT_GAP_MIN = 2.5
MAFIA_CHAT_GAP_MAX = 4.5
MAFIA_DISCUSSION_ROUNDS = 2

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

engine = None  # created fresh each time !startgame runs
human_join_queue = []
human_user_ids = {}  # display name -> discord user id, for secret role DMs
chat_log = []  # simple rolling list of "Name: message" strings, shared context for agents
secret_log = []  # night-only mafia channel transcript
pending_mafia_kill = None  # human !kill override during night


def is_ai_turn_model(player):
    """Alternate models across AI players so you have a real comparison to show."""
    index = AI_PLAYER_NAMES.index(player.name) if player.name in AI_PLAYER_NAMES else 0
    return agents.MODEL_A if index % 2 == 0 else agents.MODEL_B


@client.event
async def on_ready():
    print(f"Logged in as {client.user}", flush=True)
    day_channel = client.get_channel(DAY_CHANNEL_ID)
    if day_channel is None:
        try:
            day_channel = await client.fetch_channel(DAY_CHANNEL_ID)
        except discord.HTTPException as e:
            print(f"Cannot find #day-chat ({DAY_CHANNEL_ID}): {e}", flush=True)
            return
    try:
        await day_channel.send(
            "Werewolf bot online. Type `!join` to enter the lobby, then `!startgame` once everyone's in."
        )
        print("Posted online message to day-chat", flush=True)
    except discord.HTTPException as e:
        print(f"Cannot post in #day-chat: {e}", flush=True)


@client.event
async def on_message(message):
    global engine

    if message.author == client.user:
        return

    content = message.content.strip()

    if content == "!join":
        if message.author.name not in human_join_queue:
            human_join_queue.append(message.author.name)
        human_user_ids[message.author.name] = message.author.id
        await message.channel.send(f"{message.author.name} joined the lobby.")
        return

    if content == "!startgame":
        await start_game(message.channel)
        return

    if content.startswith("!vote "):
        target = content[len("!vote "):].strip()
        await handle_human_vote(message.channel, message.author.name, target)
        return

    if content.startswith("!kill "):
        target = content[len("!kill "):].strip()
        await handle_human_mafia_kill(message.channel, message.author.name, target)
        return

    # Humans talking during day — AIs read this after their head-start pause.
    if engine and engine.state.phase == Phase.DAY_DISCUSSION and message.channel.id == DAY_CHANNEL_ID:
        chat_log.append(f"{message.author.name}: {content}")
        return

    # Human mafia can actually join the secret exchange, not just watch AIs vote.
    if engine and engine.state.phase == Phase.NIGHT and message.channel.id == MAFIA_CHANNEL_ID:
        secret_log.append(f"{message.author.name}: {content}")


async def start_game(day_channel):
    global engine, chat_log
    chat_log = []

    engine = GameEngine(mafia_count=2, detective_count=1)
    for name in human_join_queue:
        engine.add_player(name, is_ai=False)
    for name in AI_PLAYER_NAMES:
        engine.add_player(name, is_ai=True, model_name=None)  # model assigned per-turn below

    try:
        engine.start_game()
    except ValueError as e:
        await day_channel.send(f"Can't start yet: {e}")
        return

    await whisper_human_roles()

    await day_channel.send(
        f"Game started with {len(engine.state.players)} players: "
        f"{', '.join(p.name for p in engine.state.players)}.\n"
        f"Day {engine.state.day_number} discussion is open. Talk it out, then `!vote <name>` when ready."
    )

    await run_ai_day_messages(day_channel)


async def whisper_human_roles():
    """Tell humans their role in DM so mafia know to use the secret channel."""
    for player in engine.state.players:
        if player.is_ai:
            continue
        user_id = human_user_ids.get(player.name)
        if not user_id:
            continue
        user = client.get_user(user_id)
        if user is None:
            try:
                user = await client.fetch_user(user_id)
            except discord.HTTPException:
                continue
        if player.role == Role.MAFIA:
            partners = [
                p.name for p in engine.state.players
                if p.role == Role.MAFIA and p.name != player.name
            ]
            crew = ", ".join(partners) if partners else "you're solo tonight"
            text = (
                f"You are **mafia**. Partners: {crew}. "
                "Play innocent in the town channel. At night, confer in the secret mafia channel."
            )
        elif player.role == Role.DETECTIVE:
            text = "You are the **detective**. Blend in by day. Watch who deflects."
        else:
            text = "You are a **villager**. Find the mafia before they thin the town out."
        try:
            await user.send(text)
        except discord.HTTPException:
            pass


async def run_ai_day_messages(day_channel):
    """Living AIs chime in one at a time, after humans have had a chance to talk."""
    await asyncio.sleep(HUMAN_HEAD_START_SECONDS)

    speakers = [p for p in engine.state.alive_players() if p.is_ai]
    random.shuffle(speakers)
    for player in speakers:
        model = is_ai_turn_model(player)
        msg = await asyncio.to_thread(
            agents.get_day_message, player.name, player.role.value, chat_log, model
        )
        chat_log.append(f"{player.name}: {msg}")
        await day_channel.send(f"**{player.name}:** {msg}")
        await asyncio.sleep(random.uniform(AI_MESSAGE_GAP_MIN, AI_MESSAGE_GAP_MAX))


async def handle_human_vote(day_channel, voter_name, target_name):
    try:
        engine.cast_vote(voter_name, target_name)
    except ValueError as e:
        await day_channel.send(str(e))
        return
    await day_channel.send(f"{voter_name} voted for {target_name}.")

    alive_ai = [p for p in engine.state.alive_players() if p.is_ai]
    if len(engine.state.votes) >= len(engine.state.alive_players()) - len(alive_ai):
        await run_ai_day_votes(day_channel)
        await resolve_day(day_channel)


async def run_ai_day_votes(day_channel):
    alive_names = [p.name for p in engine.state.alive_players()]
    for player in engine.state.alive_players():
        if not player.is_ai:
            continue
        model = is_ai_turn_model(player)
        target = await asyncio.to_thread(
            agents.get_day_vote, player.name, player.role.value, alive_names, chat_log, model
        )
        engine.cast_vote(player.name, target)


async def resolve_day(day_channel):
    engine.resolve_day_vote()
    await day_channel.send(engine.state.log[-1])

    if engine.state.phase == Phase.GAME_OVER:
        await day_channel.send(f"**Game over - {engine.state.winner} win!**")
        await reveal_roles(day_channel)
        return

    await run_mafia_night(day_channel)


async def handle_human_mafia_kill(channel, voter_name, target_name):
    """Living human mafia can lock the night target from the secret channel."""
    global pending_mafia_kill
    if not engine or engine.state.phase != Phase.NIGHT:
        await channel.send("You can only `!kill` during the night.")
        return
    voter = engine.state.get_player(voter_name)
    if not voter or not voter.alive or voter.role != Role.MAFIA:
        await channel.send("Only living mafia can `!kill`.")
        return
    target = engine.state.get_player(target_name)
    if not target or not target.alive:
        await channel.send(f"{target_name} is not a valid target.")
        return
    if target.role == Role.MAFIA:
        await channel.send("Don't hit your own crew.")
        return
    pending_mafia_kill = target.name
    secret_log.append(f"{voter_name}: !kill {target.name}")
    await channel.send(f"**{voter_name}** wants **{target.name}** gone tonight.")


async def run_mafia_night(day_channel):
    global secret_log, pending_mafia_kill
    secret_log = []
    pending_mafia_kill = None

    mafia_channel = client.get_channel(MAFIA_CHANNEL_ID)
    alive_names = [p.name for p in engine.state.alive_players()]
    mafia_players = [p for p in engine.state.alive_players() if p.role == Role.MAFIA]
    mafia_names = [p.name for p in mafia_players]
    villagers = [n for n in alive_names if n not in mafia_names] or list(alive_names)
    ai_mafia = [p for p in mafia_players if p.is_ai]

    await day_channel.send("Night falls. The town sleeps...")

    target = villagers[0]
    if mafia_channel is not None:
        await mafia_channel.send(
            f"**Night {engine.state.day_number} — mafia only.** "
            f"Still alive: {', '.join(alive_names)}. "
            f"Your crew: {', '.join(mafia_names)}. Talk it out — then we make the hit."
        )

        for _ in range(MAFIA_DISCUSSION_ROUNDS):
            random.shuffle(ai_mafia)
            for player in ai_mafia:
                model = is_ai_turn_model(player)
                msg = await asyncio.to_thread(
                    agents.get_mafia_night_message,
                    player.name,
                    mafia_names,
                    alive_names,
                    chat_log,
                    secret_log,
                    model,
                )
                secret_log.append(f"{player.name}: {msg}")
                await mafia_channel.send(f"**{player.name}:** {msg}")
                await asyncio.sleep(random.uniform(MAFIA_CHAT_GAP_MIN, MAFIA_CHAT_GAP_MAX))

        for player in ai_mafia:
            model = is_ai_turn_model(player)
            target = await asyncio.to_thread(
                agents.get_mafia_vote,
                player.name,
                alive_names,
                model,
                mafia_names,
                secret_log,
            )
            await mafia_channel.send(f"**{player.name}** locks in **{target}**.")

        human_mafia = [p for p in mafia_players if not p.is_ai]
        if human_mafia:
            await mafia_channel.send(
                "Last call — talk it out, or `!kill <name>` to lock the hit. 25 seconds."
            )
            await asyncio.sleep(25)
        if pending_mafia_kill:
            target = pending_mafia_kill

    caller = mafia_players[0].name if mafia_players else "unknown"
    engine.set_mafia_target(caller, target)
    engine.resolve_night()

    await day_channel.send(engine.state.log[-1])

    if engine.state.phase == Phase.GAME_OVER:
        await day_channel.send(f"**Game over - {engine.state.winner} win!**")
        await reveal_roles(day_channel)
        return

    await day_channel.send(f"Day {engine.state.day_number} discussion is now open.")
    await run_ai_day_messages(day_channel)


async def reveal_roles(day_channel):
    lines = [f"{p.name}: {p.role.value}" + (" (AI)" if p.is_ai else " (human)") for p in engine.state.players]
    await day_channel.send("**Roles revealed:**\n" + "\n".join(lines))
    # This is also the moment to pull up the Respan dashboard live and push
    # the recap out through Nango - see nango_output.py.


client.run(DISCORD_TOKEN)
