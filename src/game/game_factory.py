from pathlib import Path
from typing import Type, Union

from game.cs2.game import CS2Game
from game.game import Game
from game.null_game.game import NullGame


class GameFactory:
    """Creates Game instances by name, without callers needing to know
    the concrete class."""

    _registry: dict[str, Type[Game]] = {}

    @classmethod
    def register(cls, name: str, game_cls: Type[Game]) -> None:
        cls._registry[name.lower()] = game_cls

    @classmethod
    def create(cls, directory: Union[str, Path], terminal) -> Game:
        game = NullGame(directory, terminal)
        if game.detect():
            return game
        game = CS2Game(directory, terminal)
        if game .detect():
            return game
        return None
    
    @classmethod
    def games(cls) -> list[str]:
        return list(cls._registry.keys())

# Register games
GameFactory.register("Null Game", NullGame)
GameFactory.register("Counter-Strike 2", CS2Game)
