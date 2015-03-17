"""Common functions for the library."""

# Imports
from time import sleep
from functools import wraps
from collections import Mapping
from timeit import default_timer as time


# Decorator to support the anbled channel dictionary
def support_channel_dict(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            channels = args[0]
        except IndexError:
            channels = kwargs.pop("channels", None)
        if isinstance(channels, Mapping):
            channels = sorted(key for key, value in channels.items()
                              if value)
            args = (channels,) + args[1:]
        return func(self, *args, **kwargs)
    return wrapper


# Tick control decorator
def tick_control(tick):
    """Return a decorator that controls the duration of its execution."""
    def decorator(func):
        """Return a decorator that controls the duration of its execution."""
        def wrapper(*args, **kwargs):
            """Wrapper for time control."""
            start = time()
            value = func(*args, **kwargs)
            if not value:
                sleep_time = start + tick - time()
                if sleep_time > 0:
                    sleep(sleep_time)
            return value
        return wrapper
    return decorator
