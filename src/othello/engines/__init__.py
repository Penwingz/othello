"""Engine plugin loading."""

from othello.engines.plugins import (
    PLUGINS_DIR,
    EngineCatalog,
    EngineError,
    LoadError,
    PluginEngine,
    PluginLoadError,
    load_Engine,
)

HUMAN = "human"

__all__ = [
    "HUMAN",
    "PLUGINS_DIR",
    "EngineCatalog",
    "EngineError",
    "LoadError",
    "PluginEngine",
    "PluginLoadError",
    "load_Engine",
]
