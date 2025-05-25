import logging

from jmullan.logging import helpers

logger = logging.getLogger(__name__)


@helpers.logging_context_from_args("fire", "water", "air")
def element(fire, water="wet"):
    # air should get ignored
    logger.info("element!")
    assert helpers.current_logging_context() == {"fire": fire, "water": water}


def test_log_stack():
    assert helpers.current_logging_context() == {}

    with helpers.logging_context() as foo:
        assert helpers.current_logging_context() == {}
        assert foo.copy() == {}

    assert helpers.current_logging_context() == {}

    with helpers.logging_context(foo="bar") as foo:
        assert helpers.current_logging_context() == {"foo": "bar"}
        assert foo.copy() == {"foo": "bar"}
        foo["baz"] = "widget"
        assert foo.copy() == {"foo": "bar", "baz": "widget"}
        assert helpers.current_logging_context() == {"foo": "bar", "baz": "widget"}

    assert helpers.current_logging_context() == {}

    with helpers.logging_context(foo="aaa") as foo:
        assert foo.copy() == {"foo": "aaa"}
        assert helpers.current_logging_context() == {"foo": "aaa"}
        with helpers.logging_context(foo="bbb") as bar:
            assert helpers.current_logging_context() == {"foo": "bbb"}
            assert foo.copy() == {"foo": "aaa"}
            assert bar.copy() == {"foo": "bbb"}
        assert foo.copy() == {"foo": "aaa"}
        assert helpers.current_logging_context() == {"foo": "aaa"}

    assert helpers.current_logging_context() == {}

    element(None, None)
    element("a", "b")
    element("a")
    element(fire="a")
    element(None, water="b")
