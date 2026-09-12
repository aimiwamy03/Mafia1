"""
Core game logic for AI Werewolf/Mafia.
No Discord code here on purpose - test this file by itself first (see bottom),
so if the Discord bot breaks later you know the actual game rules are solid.
"""

import random
from dataclasses import dataclass, field
from enum import Enum


class Role(Enum):
    VILLAGER = "villager"
    MAFIA = "mafia"
    DETECTIVE = "detective"


class Phase(Enum):
    LOBBY = "lobby"
    DAY_DISCUSSION = "day_discussion"
    DAY_VOTE = "day_vote"
    NIGHT = "night"
    GAME_OVER = "game_over"


@dataclass
class Player:
    name: str
    is_ai: bool
    role: Role = None
    alive: bool = True
    model_name: str = None  # which model powers this AI player, for the "compare approaches" angle


@dataclass
class GameState:
    players: list = field(default_factory=list)
    phase: Phase = Phase.LOBBY
    day_number: int = 0
    votes: dict = field(default_factory=dict)  # voter_name -> target_name
    mafia_target: str = None
    detective_check_result: tuple = None  # (target_name, is_mafia)
    winner: str = None
    log: list = field(default_factory=list)

    def alive_players(self):
        return [p for p in self.players if p.alive]

    def get_player(self, name):
        for p in self.players:
            if p.name == name:
                return p
        return None


class GameEngine:
    """
    Usage:
        engine = GameEngine()
        engine.add_player("Alice", is_ai=False)
        engine.add_player("Bot1", is_ai=True, model_name="gemma-4-lambda")
        ...
        engine.start_game()
        engine.cast_vote("Alice", "Bot1")
        result = engine.resolve_day_vote()
        engine.set_mafia_target("Bot2", "Alice")
        result = engine.resolve_night()
    """

    def __init__(self, mafia_count=2, detective_count=1):
        self.state = GameState()
        self.mafia_count = mafia_count
        self.detective_count = detective_count

    def add_player(self, name, is_ai, model_name=None):
        if self.state.phase != Phase.LOBBY:
            raise ValueError("Cannot add players after the game has started")
        self.state.players.append(Player(name=name, is_ai=is_ai, model_name=model_name))

    def start_game(self):
        players = self.state.players
        if len(players) < 5:
            raise ValueError("Need at least 5 players (suggest 6-8)")

        roles = (
            [Role.MAFIA] * self.mafia_count
            + [Role.DETECTIVE] * self.detective_count
            + [Role.VILLAGER] * (len(players) - self.mafia_count - self.detective_count)
        )
        random.shuffle(roles)
        for player, role in zip(players, roles):
            player.role = role

        self.state.phase = Phase.DAY_DISCUSSION
        self.state.day_number = 1
        self._log(f"Game started with {len(players)} players. Day 1 begins.")

    def cast_vote(self, voter_name, target_name):
        voter = self.state.get_player(voter_name)
        target = self.state.get_player(target_name)
        if not voter or not voter.alive:
            raise ValueError(f"{voter_name} cannot vote (not found or dead)")
        if not target or not target.alive:
            raise ValueError(f"{target_name} is not a valid target")
        self.state.votes[voter_name] = target_name
        self._log(f"{voter_name} voted for {target_name}")

    def resolve_day_vote(self):
        """Tally votes, eliminate the top vote-getter, check win condition, move to night."""
        if not self.state.votes:
            self._log("No votes cast, no one is eliminated today.")
        else:
            tally = {}
            for target in self.state.votes.values():
                tally[target] = tally.get(target, 0) + 1
            eliminated_name = max(tally, key=tally.get)
            eliminated = self.state.get_player(eliminated_name)
            eliminated.alive = False
            self._log(f"{eliminated_name} was voted out. They were a {eliminated.role.value}.")

        self.state.votes = {}
        winner = self._check_win_condition()
        if winner:
            self.state.phase = Phase.GAME_OVER
            self.state.winner = winner
            self._log(f"Game over. {winner} wins.")
        else:
            self.state.phase = Phase.NIGHT
        return self.state

    def set_mafia_target(self, mafia_name, target_name):
        mafia = self.state.get_player(mafia_name)
        if not mafia or mafia.role != Role.MAFIA or not mafia.alive:
            raise ValueError(f"{mafia_name} is not a living mafia player")
        self.state.mafia_target = target_name
        self._log(f"(secret) {mafia_name} suggested targeting {target_name}")

    def run_detective_check(self, detective_name, target_name):
        detective = self.state.get_player(detective_name)
        if not detective or detective.role != Role.DETECTIVE or not detective.alive:
            raise ValueError(f"{detective_name} is not a living detective")
        target = self.state.get_player(target_name)
        is_mafia = target.role == Role.MAFIA
        self.state.detective_check_result = (target_name, is_mafia)
        self._log(f"(secret) Detective checked {target_name}: {'MAFIA' if is_mafia else 'not mafia'}")
        return is_mafia

    def resolve_night(self):
        """Apply the mafia's chosen target, check win condition, move to next day."""
        if self.state.mafia_target:
            victim = self.state.get_player(self.state.mafia_target)
            victim.alive = False
            self._log(f"{victim.name} was eliminated overnight. They were a {victim.role.value}.")
        self.state.mafia_target = None

        winner = self._check_win_condition()
        if winner:
            self.state.phase = Phase.GAME_OVER
            self.state.winner = winner
            self._log(f"Game over. {winner} wins.")
        else:
            self.state.day_number += 1
            self.state.phase = Phase.DAY_DISCUSSION
            self._log(f"Day {self.state.day_number} begins.")
        return self.state

    def _check_win_condition(self):
        alive = self.state.alive_players()
        mafia_alive = sum(1 for p in alive if p.role == Role.MAFIA)
        villagers_alive = sum(1 for p in alive if p.role != Role.MAFIA)
        if mafia_alive == 0:
            return "villagers"
        if mafia_alive >= villagers_alive:
            return "mafia"
        return None

    def _log(self, message):
        self.state.log.append(message)
        print(message)  # so it's visible in the console during testing/demo


if __name__ == "__main__":
    # Quick manual test - simulate one full round with fake players before touching Discord.
    engine = GameEngine(mafia_count=2, detective_count=1)
    for name in ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank"]:
        engine.add_player(name, is_ai=(name != "Alice"), model_name="gemma-4-lambda" if name != "Alice" else None)

    engine.start_game()
    print("\nRoles (for testing only, agents/players should never see this):")
    for p in engine.state.players:
        print(f"  {p.name}: {p.role.value}")

    # Simulate a day vote
    alive_names = [p.name for p in engine.state.alive_players()]
    engine.cast_vote(alive_names[0], alive_names[1])
    engine.cast_vote(alive_names[2], alive_names[1])
    engine.resolve_day_vote()

    print("\nGame log so far:")
    for line in engine.state.log:
        print(" -", line)
