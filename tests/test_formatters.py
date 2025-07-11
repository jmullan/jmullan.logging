import pytest

from jmullan.logging import formatters


def test_flatten_dict():
    assert formatters.flatten_dict({"a": "b", "c": {"d": "e"}}) == {"a": "b", "c.d": "e"}
    assert formatters.flatten_dict({"a.b": "c", "a.b.d": "e"}) == {"a.b": "c", "a.b.d": "e"}
    assert formatters.flatten_dict({"a": {"b": 1}, "a.b": 2}) == {"a.b": 2}


def test_union_keys():
    assert formatters.union_keys({"a": "b", "c": "d"}, {}) == ["a", "c"]
    assert formatters.union_keys({"a": "b", "c": "d"}, {"e": "f"}) == ["a", "c", "e"]
    assert formatters.union_keys({}, {"e": "f"}) == ["e"]
    assert formatters.union_keys({"a": "b", "c": {}}, {"e": "f"}) == ["a", "e"]
    assert formatters.union_keys({"a": "b", "c": "d"}, {"e": "f", "g": None}) == [
        "a",
        "c",
        "e",
        "g",
    ]


@pytest.mark.parametrize(
    ("from_", "into", "expected"),
    [
        ({}, {}, {}),
        ({"a": "b"}, {"a": "d"}, {"a": "b"}),
        ({"a": "b"}, {"c": "d"}, {"c": "d", "a": "b"}),
        ({"a": "b"}, {"a": {}}, {}),
        ({"a": "b"}, {"a": {"c": "d"}}, {"a": {"c": "d"}}),
    ],
)
def test_merge_values(from_, into, expected):
    assert expected == formatters.merge_values(from_, into)


@pytest.mark.parametrize(
    ("dot_string", "value", "expected"),
    [("a.b.c", "e", ("a", {"b": {"c": "e"}})), ("a.b", 2, ("a", {"b": 2})), ("a", "b", ("a", "b"))],
)
def test_de_dot(dot_string, value, expected):
    assert expected == formatters.de_dot(dot_string, value)
    assert formatters.de_dot("a.b.c", "e") == ("a", {"b": {"c": "e"}})
    assert formatters.de_dot("a.b", 2) == ("a", {"b": 2})
    assert formatters.de_dot("a", "b") == ("a", "b")


def test_normalize_dict():
    assert formatters.normalize_dict({"a.b": "c"}) == {"a": {"b": "c"}}
    assert formatters.normalize_dict({"a.b": "c", "a.d": "e"}) == {"a": {"b": "c", "d": "e"}}
    assert formatters.normalize_dict({"a.b": "c", "a.b.d": "e"}) == {"a": {"b": {"d": "e"}}}
    assert formatters.normalize_dict({"a.b": [1, 2, 3]}) == {"a": {"b": [1, 2, 3]}}
    assert formatters.normalize_dict({"a.b": [1, 2, {"c.d": "e"}]}) == {"a": {"b": [1, 2, {"c": {"d": "e"}}]}}


def test_format_json():
    jf = formatters.ECSJsonFormatter()
    assert jf.format_json({}) == "{}"
    assert jf.format_json({"a.b": "c"}) == '{"a":{"b":"c"}}'
    assert jf.format_json({"d.e": "f", "a.b": "c"}) == '{"a":{"b":"c"},"d":{"e":"f"}}'
    assert jf.format_json({"d.e": "f", "d.a": "c"}) == '{"d":{"a":"c","e":"f"}}'

    event = {
        "d.e": "f",
        "d.a": "c",
        "@timestamp": "anything",
        "log.level": "INFO",
        "message": "something",
    }
    expected = '{"@timestamp":"anything","log.level":"INFO","message":"something","d":{"a":"c","e":"f"}}'
    assert jf.format_json(event) == expected
