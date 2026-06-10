from typing import Any, Dict, List


def _normalize_content(content: Any) -> str:
    return str(content or "").replace("\r\n", "\n").strip()


def append_message_if_not_duplicate(
    history: List[Dict[str, Any]],
    new_message: Dict[str, Any],
) -> bool:
    """Append a message unless it is identical to the latest history item."""
    if history:
        last_message = history[-1]
        same_role = last_message.get("role") == new_message.get("role")
        same_content = _normalize_content(last_message.get("content")) == _normalize_content(new_message.get("content"))
        if same_role and same_content:
            return False

    history.append(new_message)
    return True
