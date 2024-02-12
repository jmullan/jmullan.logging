import argparse
import logging

from jmullan_logging.easy_logging import easy_initialize_logging
from jmullan_logging.helpers import logging_context, logging_context_from_args


class FooException(Exception):
    pass


_LEVELS = {"CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "NOTSET"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-format",
        dest="log_format",
        required=False,
        choices=[None, "json", "text"],
        help="Choose a log format",
    )
    parser.add_argument(
        "--log-level", dest="log_level", required=False, help="Choose a log level", choices=_LEVELS
    )
    args = parser.parse_args()

    easy_initialize_logging(args.log_format, args.log_level)

    logger = logging.getLogger(__name__)

    logger.info("The app is live and on air!!!")

    log = logging.getLogger("jmullan.foo")

    log.info("a" * 20, extra={"foo": "bar", "a.b": "c"})
    logger.info("b" * 20, extra={"baz": "pirate", "d.e": "f"})

    with logging_context(z="zzz"):
        log.info("d" * 20)
        with logging_context(y="yyy"):
            logger.info("e" * 20)
        log.info("f" * 20)

    @logging_context_from_args("foo")
    def error(argument_does_not_match):
        pass

    @logging_context_from_args("foo")
    def thing(foo: str, bar: str | None = None):
        logger.info("%s: %s", foo[::-1], bar)

    thing("This is testing a decorator")
    thing("This is another test", "including a positional keyword arg")
    thing("Another test", bar="with a keyword arg")
    thing(foo="Last test", bar="with a keyword arg")

    @logging_context_from_args("foo", "bar")
    def widget(foo: str, bar: str | None = None):
        logger.info("%s: %s", foo[::-1], bar)

    widget("This is testing a decorator")
    widget("This is another test", "including a positional keyword arg")
    widget("Another test", bar="with a keyword arg")
    widget(foo="Last test", bar="with a keyword arg")

    try:
        raise Exception("oh no")
    except Exception:
        logger.exception("got an exception")
    try:
        raise FooException("oh yes")
    except Exception:
        logger.exception("got another exception")

    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.warn("warn")
    logger.error("error")
    logger.fatal("fatal")
    logger.critical("critical")
