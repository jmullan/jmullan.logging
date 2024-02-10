import inspect
import logging
import re
import threading
from collections.abc import Collection
from contextlib import contextmanager
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)

_THREAD_DATA = threading.local()


def split_request(request: str):
    """Try to find a method and path in a given string.

    The request line is expected to be formatted as "GET /example.php"
    """
    if not request:
        return {}
    matches = re.match(r"^([A-Z]+) +(/.*)", request)
    if matches:
        return {
            "http.request.method": matches.group(1),
            "http_request_path": matches.group(2),
        }
    else:
        return {"http_request_original": request}


@contextmanager
def logging_context(**kwargs):
    """Add fields to logging that will be searchable in kibana.

    For single logging lines use logging.level(message, extra={'x': 1})
    """
    log_state = get_log_state()
    log_state.push(**kwargs)
    try:
        yield
    finally:
        log_state.pop()


def logging_context_from_args(*arg_names: str):
    """Add the named arguments to the logging context whenever the decorated function is called.

    >>> @logging_context_from_args('bar', 'baz', 'qux', 'boop')
    ... def foo(bar, baz=None, *args, qux=None, **kwargs):
    ...     logger.debug("foo!")
    ...
    >>> foo(42, qux="-QUX-", boop="-BOOP-")
    foo! |bar=42 qux='-QUX-' boop='-BOOP-'
    >>> foo._logging_context_from_args
    ['bar', 'baz', 'qux', 'boop']

    For developers unfamiliar with decorators, here is the full execution order of the above code:
     1. Python defines the foo() function normally.
     2. logging_context_from_args() is called immediately and returns the internal decorator, named
        _decorate().
     3. As a result of the @ decoration syntax, Python applies the decorator: It calls _decorate()
        on foo().
     4. _decorate() collects the signature of foo()--the parameters named in foo()'s function
        definition.
     5. _decorate() defines an internal function called _wrapper(). _wrapper() does not execute yet.
     6. The @wraps() syntax means that the _wrapper() definition inherits the __name__,
        __docstring__, and type signature of the foo() definition.
     7. _decorate() attaches the ._logging_context_from_args property to _wrapper(). We don't need
        it here; it's for convenience in case someone else wants to inspect it later.
     8. When _decorate() returns, the Python @ syntax means that Python sets the name foo to the
        decorator result, the _wrapper() function definition.
     9. When the example code calls foo, Python gives it _wrapper. Python calls _wrapper() with the
        requested args.
     10. _wrapper() binds the requested args to the signature and constructs a dictionary of the
          requested ones.
     11. _wrapper enters the logging_context() and calls the original foo() inside it, with the args
         that it got from its caller.
     12. The example code demonstrates inspecting ._logging_context_from_args, which _decorate() put
         there up above.
    """

    def _decorate(f):
        """Decorate the function.

        Python runs this part once when the function is defined/decorated."""
        signature = inspect.signature(f)
        with logging_context(function=f.__module__ + "." + f.__qualname__):
            _check_signature_has_args(signature, arg_names)

        @wraps(f)
        def _wrapper(*args, **kwargs):
            """Wrap around f, collecting the requested bound arguments and adding them to the
            logging context.
            """
            try:
                bound = signature.bind(*args, **kwargs)
                context = _log_values_from_bound_arguments(arg_names, bound)
            except TypeError:
                # Raised by .bind(): Actual call arguments don't match formal parameters in the
                # function definition. f() will fail below, so let the failure happen there instead
                # of here, since the traceback there is a bit clearer.
                context = {}

            with logging_context(**context):
                # This return is from _wrapper(), which wraps around f.
                return f(*args, **kwargs)

        # Attach the arg names to the decorated function for convenience in case we want it later.
        _wrapper._logging_context_from_args = arg_names

        # Return the wrapper function. This happens at function definition/decoration time.
        return _wrapper

    # Return the decorator itself. This is the result of the logging_context_from_args('foo') call,
    # which Python applies to the decorated function as a result of the @ decorator syntax.
    return _decorate


def _check_signature_has_args(signature: inspect.Signature, arg_names: Collection[str]) -> None:
    """If any of arg_names couldn't reasonably be passed to the function, warn about them.

    The function that logging_context_from_args() decorates should only ever be called with the
    formal parameters in its definition unless the decorated function's definition uses the **kwargs
    syntax. If the function uses the **kwargs syntax then we'll check there for the argument and add
    it to the logging context if present. But if the function was defined without **kwargs syntax
    then it's nonsensical for the function to ask us to log an arg that isn't defined. If that
    happens then it's probably a typo or similar coding error in the decorator call. It's not fatal,
    but issue a warning.
    """
    has_kwargs = any(
        parameter.kind == parameter.VAR_KEYWORD for parameter in signature.parameters.values()
    )
    if has_kwargs:
        # Any arg could be present in kwargs, so no warnings needed.
        return

    for arg_name in arg_names:
        if arg_name not in signature.parameters:
            message = (
                "logging_context_from_args() got an argument name that's not in the "
                "function definition. It will never be set."
            )
            extra = {"argument_name": arg_name}
            logger.warning(message, extra=extra)


def _log_values_from_bound_arguments(
    arg_names: Collection[str], bound: inspect.BoundArguments
) -> dict[str, Any]:
    """Get a dictionary of just the named bound arguments."""
    context = {}
    for arg_name in arg_names:
        if arg_name in bound.arguments:
            context[arg_name] = bound.arguments[arg_name]
        elif arg_name in bound.kwargs:
            context[arg_name] = bound.kwargs[arg_name]
    return context


class LogState:
    """A logging context stack."""

    stack: list[dict[str, Any]]

    def __init__(self):
        self.stack = [{}]

    def push(self, **kwargs) -> None:
        new_state = self.top().copy()
        new_state.update(**kwargs)
        self.stack.append(new_state)

    def pop(self) -> dict[str, Any]:
        """If there is anything on the stack, remove the top item."""
        if self.stack:
            return self.stack.pop()
        return {}

    def top(self) -> dict[str, Any]:
        """Return the top level of the stack."""
        if not self.stack:
            self.stack.append({})
        return self.stack[-1]


def current_logging_context() -> dict:
    return get_log_state().top()


def get_log_state() -> LogState:
    if not hasattr(_THREAD_DATA, "log_state"):
        _THREAD_DATA.log_state = LogState()
    return _THREAD_DATA.log_state
