import abc
import datetime
import io
import json
import logging
import traceback
from collections.abc import Mapping
from typing import Any

import colorist

from jmullan_logging.helpers import current_logging_context

_EMPTY = object()


def flatten_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    """Adds dots to all nested fields in dictionaries.

    Entries with different forms of nesting update.
    {"a": {"b": {"c": 4}} -> {"a.b.c": 4}
    {"a": {"b": 1}, "a.b": 2} -> {"a.b": 2}
    """
    top_level = {}
    for key, val in value.items():
        if not isinstance(val, Mapping):
            top_level[key] = val
        else:
            val = flatten_dict(val)
            for sub_key, sub_value in val.items():
                sub_key = f"{key}.{sub_key}"
                top_level[sub_key] = sub_value
    return top_level


def key_to_dict(key: str, value: Any) -> dict[str, Any]:
    if "." not in key:
        return {key: value}
    parts = key.split(".", 1)
    return {key: key_to_dict(parts[1], value)}


def merge_dicts(into_dict: dict[str, Any], from_dict: dict[str, Any]) -> dict[str, Any]:
    new_dict = {}
    if into_dict is not None:
        new_dict.update(into_dict)

    for key, value in from_dict.items():
        into_value = new_dict.get(key)
        if into_value is None:
            new_dict[key] = value
        elif isinstance(dict, value) and isinstance(dict, into_value):
            new_dict[key] = merge_dicts(into_value, value)
        else:
            new_dict[key] = value
    return new_dict


def union_keys(dx: dict[str, Any], dy: dict[str, Any]) -> list[str]:
    """Take the keys from the first dictionary and then the second dictionary, preserving order.

    Keys matched to a value of an empty dictionary are ignored!
    """
    keyholder = {x: None for x, y in dx.items() if y != {}}
    # update maintains order
    keyholder.update({x: None for x, y in dy.items() if y != {}})
    return list(keyholder.keys())


def unflatten_dict(value: dict[str, Any]) -> dict[str, Any]:
    """Changes dictionary of dotted items into a nested dictionary

    Entries with different forms of nesting update.
    {"a.b.c": 4} -> {"a": {"b": {"c": 4}}
    {"a.b": 2} -> {"a": {"b": 2}
    """
    top_level: dict[str, Any] = {}
    for key, val in value.items():
        subdict = key_to_dict(key, val)
        top_level = merge_dicts(top_level, subdict)
    return top_level


def merge_values(from_: dict[Any, Any], into: dict[Any, Any]) -> Any:
    """Merge deeply nested dictionary structures.

    In case of collisions between a dictionary and non-dictionary, the dictionary wins.

    If two dictionaries are merged, and a key / value pair has an empty dictionary as
    the value, it will be pruned.
    """
    if isinstance(from_, dict) and isinstance(into, dict):
        output = {}
        for key in union_keys(into, from_):
            value = merge_values(from_.get(key, _EMPTY), into.get(key, _EMPTY))
            if value != {}:
                output[key] = value
        return output
    elif isinstance(from_, dict):
        return from_.copy()
    elif isinstance(into, dict):
        return into.copy()
    elif from_ == _EMPTY and into == _EMPTY:
        # this should never happen
        return None
    elif from_ == _EMPTY:
        return into
    else:
        return from_


def de_dot(dot_string: str, value: Any) -> tuple[str, Any]:
    """Turn value and dotted string key into a nested dictionary."""
    arr = dot_string.split(".")
    while len(arr) > 1:
        value = {arr.pop(): value}
    return arr.pop(), value


def normalize_dict(value: dict[str, Any]) -> dict[str, Any]:
    """Expands all dotted names to nested dictionaries."""
    if not isinstance(value, dict):
        return value

    output: dict[str, Any] = {}
    for key, val in value.items():
        if isinstance(val, dict):
            # dig into the dictionary to process all sub-nodes
            val = normalize_dict(val)
        elif isinstance(val, list):
            # process all items in the list
            val = [normalize_dict(x) for x in val]

        # now see if the key needs to get turned into levels of nesting
        key, val = de_dot(key, val)

        output[key] = merge_values(val, output.get(key, _EMPTY))
    return output


def iso_date(record: logging.LogRecord) -> str:
    iso_minus_timezone = datetime.datetime.utcfromtimestamp(record.created).isoformat()
    return "%sZ" % iso_minus_timezone


def render_traceback(exception_info) -> str:
    """Format and return the specified exception information as a string.

    This default implementation just uses
    traceback.print_exception()
    """
    if exception_info is None:
        return ""
    sio = io.StringIO()
    tb = exception_info[2]
    traceback.print_tb(tb, file=sio)
    # traceback.print_exception(ei[0], ei[1], tb, None, sio)
    s = sio.getvalue()
    sio.close()
    s = s.lstrip("\n")
    return s


# inspired by https://github.com/madzak/python-json-logger/blob/master/src/pythonjsonlogger/jsonlogger.py
#
# base list from https://docs.python.org/3/library/logging.html#logrecord-attributes
RECORD_MAPPINGS = {
    "args": "",
    "asctime": "",
    "created": "",
    "exc_info": "",
    "exc_text": "",
    "filename": "log.origin.file.name",
    "funcName": "log.origin.function",
    "levelname": "log.level",
    "levelno": "",
    "lineno": "log.origin.file.line",
    "module": "",
    "msecs": "",
    "message": "",
    "msg": "",
    "name": "log.logger",
    "pathname": "log.file.path",
    "process": "process.pid",
    "processName": "process.name",
    "relativeCreated": "",
    "taskName": "",
    "stack_info": "",
    "thread": "process.thread.id",
    "threadName": "process.thread.name",
}

def get_event(record: logging.LogRecord) -> dict[str, Any]:
    """Prepares a flattened dictionary from a LogRecord that includes the basic ECS fields.

    Users of this library are expected to be hygienic about their use of field names.
    """
    event = {"@timestamp": iso_date(record), "message": record.getMessage()}

    for from_key, value in record.__dict__.items():
        if value is None:
            continue
        if from_key in RECORD_MAPPINGS:
            to_key = RECORD_MAPPINGS[from_key]
            if to_key:
                event[to_key] = value
        else:
            event[from_key] = value

    context = current_logging_context().copy()
    event.update(context)

    extra: dict = {}
    if hasattr(record, "extra"):
        extra = record.extra or {}  # type: ignore
    event.update(extra)

    if record.exc_info:
        exception = record.exc_info[1]
        event["error.type"] = type(exception).__name__
        event["error.message"] = str(exception)
        event["error.stack_trace"] = render_traceback(record.exc_info)
    return flatten_dict(event)


class EasyLoggingFormatter(abc.ABC, logging.Formatter):
    @abc.abstractmethod
    def formatMessage(self, record):
        pass


class ConsoleFormatter(EasyLoggingFormatter):
    """Logging colored formatter, adapted from https://stackoverflow.com/a/56944256/3638629."""

    reset = "\x1b[0m"

    COLORS = {
        logging.DEBUG: colorist.Color.WHITE,
        logging.INFO: colorist.BrightColor.WHITE,
        logging.WARNING: colorist.Color.YELLOW,
        logging.ERROR: colorist.Color.RED,
        logging.FATAL: colorist.Color.RED,
        logging.CRITICAL: colorist.Color.RED,
    }

    def format_extra(self, value: Any, color: str | None = None) -> str:
        if not isinstance(value, str):
            try:
                value = json.dumps(value)
            except Exception:
                value = str(value)
        return self.colorize(value, color)

    def colorize(self, value: Any, color: colorist.Color | None = None) -> str:
        if color is None:
            return f"{value}"
        return f"{color}{value}{colorist.Color.OFF}"

    def format_field(self, key: str, value: Any) -> str:
        k = self.format_extra(key, colorist.Color.GREEN)
        v = self.format_extra(value)
        return f"{k}={v}"

    def formatMessage(self, record: logging.LogRecord) -> str:
        event = get_event(record)
        color = self.COLORS.get(record.levelno)

        event = flatten_dict(event)

        timestamp = event.pop("@timestamp")
        message = event.pop("message")

        level = self.colorize(event.pop("log.level"), color)
        message = self.colorize(message, color)

        # this method is just formatting the "message". LogFormatter will supply the
        # error message and traceback
        suppress_fields = {
            "error.type",
            "error.message",
            "error.stack_trace",
            "log.file.path",
            "log.origin.file.name",
            "log.origin.file.line",
            "process.thread.id",
            "process.thread.name",
            "process.name",
            "process.pid",
            "log.origin.function"
        }
        for field in suppress_fields:
            event.pop(field, None)

        extra_pairs = [self.format_field(k, v) for k, v in event.items()]
        if extra_pairs:
            pairs_string = " ".join(extra_pairs)
            message = f"{message} | {pairs_string}"
        line = f"[{timestamp}] [{level}] {message}{self.reset}"

        return line


class PlainTextFormatter(EasyLoggingFormatter):
    """Use when you don't want any colors in your life."""

    def format_extra(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        else:
            try:
                return json.dumps(value)
            except Exception:
                return str(value)

    def format_field(self, key: str, value: Any) -> str:
        k = self.format_extra(key)
        v = self.format_extra(value)
        return f"{k}={v}"

    def formatMessage(self, record: logging.LogRecord) -> str:
        event = get_event(record)

        event = flatten_dict(event)

        timestamp = event.pop("@timestamp")
        message = event.pop("message")

        level = event.pop("log.level")

        # this method is just formatting the "message". LogFormatter will supply the
        # error message and traceback
        suppress_fields = {"error.type", "error.message", "error.stack_trace"}
        for field in suppress_fields:
            event.pop(field, None)

        extra_pairs = [self.format_field(k, v) for k, v in event.items()]
        if extra_pairs:
            pairs_string = " ".join(extra_pairs)
            message = f"{message} | {pairs_string}"
        line = f"[{timestamp}] [{level}] {message}"

        return line


def _json_dumps_fallback(value: Any) -> str:
    """Fallback handler for `json.dumps` to handle objects json doesn't know how to
    serialize.
    """
    try:
        # This is what structlog's json fallback does
        return value.__structlog__()
    except AttributeError:
        pass
    return repr(value)


class ECSJsonFormatter(EasyLoggingFormatter):
    """Logs a record as ECS-ish JSON using the event prepared by PandoraLoggingFormatter."""

    def formatMessage(self, record):
        """Format the specified record as text."""
        event = get_event(record)
        return self.format_json(event)

    def format_json(self, event: dict) -> str:
        """Turns a flattened event dictionary into a nice ECS-fields compatible json string."""
        first_keys = ["@timestamp", "log.level", "message"]

        # extract just the keys we want to be first
        ordered_event = {x: event.pop(x) for x in first_keys if event.get(x, _EMPTY) != _EMPTY}

        # sort all the keys that are not the ordered first ones and normalize it
        normalized_event = normalize_dict({x: event[x] for x in sorted(event.keys())})

        # add the sorted tree to the ordered fields
        ordered_event.update(normalized_event)

        return json.dumps(
            ordered_event, sort_keys=False, separators=(",", ":"), default=_json_dumps_fallback
        )
