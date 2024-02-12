import inspect
import logging
import threading
from collections import ChainMap
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)


_THREAD_DATA = threading.local()
if not hasattr(_THREAD_DATA, "stack"):
    _THREAD_DATA.stack = ChainMap()


class LoggingContext(dict):
    """A logging context stack."""


def current_logging_context() -> dict:
    return dict(_THREAD_DATA.stack.copy())


@contextmanager
def logging_context(**kwargs):
    """Add fields to logging

    For single logging lines use logging.level(message, extra={'x': 1})
    """
    parent = _THREAD_DATA.stack
    try:
        child = _THREAD_DATA.stack.new_child(kwargs)
        _THREAD_DATA.stack = child
        yield child
    finally:
        _THREAD_DATA.stack = parent


def logging_context_from_args(*intercept_args) -> Callable:
    """Decorate a method with this in order to add specific arguments to the logging context.


    For instance, this would add the value to the context when the function is called:
    ```
    @logging_context_from_args("foo")
    def thing(foo, bar):
        pass
    ```
    """

    def decorator(function: Callable) -> Callable:
        """Given a function, tries to match valid parameters to the function's signature"""
        signature = inspect.signature(function)
        valid_parameters = {x for x in intercept_args if x in signature.parameters}
        if not valid_parameters:
            logger.error(
                "None of the parameters %s you are trying to attach to the logging context"
                " are in the given function's signature %s(%s)",
                intercept_args,
                function.__name__,
                ", ".join(signature.parameters.keys()),
            )
            return function

        @wraps(function)
        def wrapper(*args, **kwargs):

            try:
                bound_arguments = signature.bind(*args, **kwargs)
                bound_arguments.apply_defaults()
                context = {
                    x: y for x, y in bound_arguments.arguments.items() if x in valid_parameters
                }
            except Exception:
                context = {}
            with logging_context(**context):
                function(*args, **kwargs)

        return wrapper

    return decorator
