import contextvars
import inspect
import logging
from collections import ChainMap
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)

_stack = contextvars.ContextVar("LoggingContext.stack", default=ChainMap())  # type: contextvars.ContextVar[ChainMap]


def current_logging_context() -> dict:
    return dict(_stack.get().copy())


@contextmanager
def logging_context(**kwargs) -> Iterator[ChainMap]:
    """Add fields to logging

    For single logging lines use logging.level(message, extra={'x': 1})
    """
    token = None
    try:
        child = _stack.get().new_child(kwargs)
        token = _stack.set(child)
        yield child
    finally:
        try:
            if token is not None:
                _stack.reset(token)
        except Exception:
            logger.error("Could not reset logging context")


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
        if not intercept_args:
            logger.error(
                "No parameters were specified to attach to the logging context of the given function %s",
                set(intercept_args),
                function.__name__,
            )
            return function

        signature = inspect.signature(function)
        valid_parameters = {x for x in intercept_args if x in signature.parameters}
        invalid_parameters = {x for x in intercept_args if x not in signature.parameters}
        if invalid_parameters:
            logger.error(
                "Invalid parameters %s were attempted to be attached to the logging context"
                " that are not in the given function's signature %s(%s)",
                invalid_parameters,
                function.__name__,
                ", ".join(signature.parameters.keys()),
            )
        if not valid_parameters:
            logger.error(
                "None of the parameters %s you are trying to attach to the logging context"
                " are in the given function's signature %s(%s)",
                set(intercept_args),
                function.__name__,
                ", ".join(signature.parameters.keys()),
            )
            return function

        @wraps(function)
        def wrapper(*args, **kwargs):
            try:
                bound_arguments = signature.bind(*args, **kwargs)
                bound_arguments.apply_defaults()
                context = {x: y for x, y in bound_arguments.arguments.items() if x in valid_parameters}
            except Exception:
                context = {}
            with logging_context(**context):
                function(*args, **kwargs)

        return wrapper

    return decorator
