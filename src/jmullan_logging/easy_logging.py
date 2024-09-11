import logging
import os
import sys
from typing import TextIO

from jmullan_logging import formatters


def easy_initialize_logging(
    log_level: str | None = None,
    stream: TextIO | None = None,
    formatter: logging.Formatter | None = None,
):
    """A very simple way to configure logging, suitable for toy applications.

    :param log_level: The string log level. Falls back to LOGLEVEL in the env variables or INFO
    :param stream: Write to this stream, or stdout if omitted
    :param formatter: Supply a formatter, or jmullan_logging.formatters.ConsoleFormatter if omitted
    :return:
    """
    if log_level is None:
        log_level = os.environ.get("LOGLEVEL", "INFO").upper() or "INFO"

    logging.captureWarnings(True)

    if stream is None:
        stream = sys.stdout

    if formatter is None:
        if stream.isatty():
            formatter = formatters.ConsoleFormatter()
        else:
            formatter = formatters.ECSJsonFormatter()

    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    root_logger.setLevel(log_level)
