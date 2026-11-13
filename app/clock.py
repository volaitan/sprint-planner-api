"""Single source of 'today', so tests can move time forward through a sprint."""
from datetime import date


def today() -> date:
    return date.today()
