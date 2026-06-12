import json

from utils.sse import format_sse_event, parse_last_event_id


def test_parse_last_event_id_uses_positive_integer():
    assert parse_last_event_id("42") == 42


def test_parse_last_event_id_falls_back_for_invalid_values():
    assert parse_last_event_id(None) == 0
    assert parse_last_event_id("") == 0
    assert parse_last_event_id("abc") == 0
    assert parse_last_event_id("-1") == 0


def test_format_sse_event_includes_event_id_and_json_data():
    payload = {"type": "message", "content": "hello"}

    event = format_sse_event(payload, event_id=123)

    assert event.startswith("id: 123\n")
    assert event.endswith("\n\n")
    data_line = next(line for line in event.splitlines() if line.startswith("data: "))
    assert json.loads(data_line.removeprefix("data: ")) == payload
