"""Small helpers for Server-Sent Events."""

import json
from typing import Any, Dict, Optional


def parse_last_event_id(value: Optional[str]) -> int:
    """Parse a SSE Last-Event-ID value into a positive database id."""
    try:
        event_id = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return event_id if event_id > 0 else 0


def format_sse_event(payload: Dict[str, Any], event_id: Optional[int] = None) -> str:
    """Format payload as a SSE event, optionally including an event id."""
    data = json.dumps(payload, ensure_ascii=False)
    if event_id is None:
        return f"data: {data}\n\n"
    return f"id: {event_id}\ndata: {data}\n\n"
