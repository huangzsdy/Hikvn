# Strategy Factory
# Register new strategies here

STRATEGY_REGISTRY = {}


def register_strategy(name: str, strategy_class):
    """Register a strategy class."""
    STRATEGY_REGISTRY[name] = strategy_class


def get_strategy(name: str):
    """Get a strategy class by name."""
    return STRATEGY_REGISTRY.get(name)
