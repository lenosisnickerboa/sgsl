from pathlib import Path
from typing import Type, Union

from app.resources import resource_path
from game.cs2.game import CS2Game
from game.csgo.game import CSGOGame
from game.game import Game
from game.null_game.game import NullGame
from game.vu.game import VUGame

# Bundled by build-for-release.bat only (via a PyInstaller --add-data
# entry), so a plain from-source run and a build-for-test.bat build
# both keep the Null Game -- it's just excluded from the release exe,
# whose real users shouldn't see a fake game in the list.
_ExcludeNullGameMarker = "app/assets/exclude_null_game.marker"


class GameFactory:
    """Creates Game instances by name, without callers needing to know
    the concrete class."""

    _registry: dict[str, Type[Game]] = {}

    @classmethod
    def register(cls, name: str, game_cls: Type[Game]) -> None:
        cls._registry[name] = game_cls

    @classmethod
    def create(cls, directory: Union[str, Path], terminal) -> Game:
        if "Null Game" in cls._registry:
            game = NullGame(directory, terminal)
            if game.detect():
                return game
        game = CS2Game(directory, terminal)
        if game.detect():
            return game
        game = CSGOGame(directory, terminal)
        if game.detect():
            return game
        game = VUGame(directory, terminal)
        if game.detect():
            return game
        return None

    @classmethod
    def create_from_name(cls, name: str, directory: Union[str, Path], terminal) -> Game:
        try:
            game_cls = cls._registry[name]
        except KeyError:
            raise ValueError(
                f"Unknown game: {name!r}. Available: {sorted(cls._registry.keys())}"
            )
        return game_cls(directory, terminal)

    @classmethod
    def games(cls) -> list[str]:
        return list(cls._registry.keys())


# Register games
if not resource_path(_ExcludeNullGameMarker).exists():
    GameFactory.register("Null Game", NullGame)
GameFactory.register("Counter-Strike 2", CS2Game)
GameFactory.register("Counter-Strike: Global Offensive", CSGOGame)
GameFactory.register("Venice Unleashed", VUGame)
