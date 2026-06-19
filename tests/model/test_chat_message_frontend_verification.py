from datetime import datetime

from model.chat_messages import ChatMessageEntity


def test_verification_request_frontend_dict_includes_status():
    msg = ChatMessageEntity(
        role="verification",
        message_type="verification_request",
        content={
            "title": "请选择",
            "description": "请选择下一步",
            "options": ["继续", "停止"],
            "status": "cancelled",
        },
        verification_id="verification-1",
        create_at=datetime(2026, 6, 19, 10, 0, 0),
    )

    frontend = msg.to_frontend_dict()

    assert frontend["role"] == "verification"
    assert frontend["verification_status"] == "cancelled"
    assert frontend["content"]["status"] == "cancelled"
