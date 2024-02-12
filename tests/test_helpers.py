from jmullan_logging import helpers


def test_log_stack():
    log_state = helpers.LogState()
    assert log_state.top() == {}

    log_state.push(foo="bar")
    assert log_state.top() == {"foo": "bar"}

    log_state.push(foo="baz")
    assert log_state.top() == {"foo": "baz"}

    log_state.pop()
    assert log_state.top() == {"foo": "bar"}

    log_state.pop()
    assert log_state.top() == {}

    # extra pops shouldn't raise
    log_state.pop()
    assert log_state.top() == {}

    # users should not inspect the stack, but this is a test
    log_state.stack = []
    assert log_state.top() == {}
    assert log_state.pop() == {}
