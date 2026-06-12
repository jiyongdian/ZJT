from utils.conversation_history import append_message_if_not_duplicate


def test_append_message_if_not_duplicate_skips_same_last_message():
    history = [
        {"role": "assistant", "content": "好的，图片分析任务已完成。"},
    ]
    new_message = {"role": "assistant", "content": "好的，图片分析任务已完成。"}

    appended = append_message_if_not_duplicate(history, new_message)

    assert appended is False
    assert len(history) == 1


def test_append_message_if_not_duplicate_appends_different_content():
    history = [
        {"role": "assistant", "content": "旧消息"},
    ]
    new_message = {"role": "assistant", "content": "新消息"}

    appended = append_message_if_not_duplicate(history, new_message)

    assert appended is True
    assert history[-1] == new_message


def test_append_message_if_not_duplicate_appends_different_role():
    history = [
        {"role": "assistant", "content": "继续"},
    ]
    new_message = {"role": "user", "content": "继续"}

    appended = append_message_if_not_duplicate(history, new_message)

    assert appended is True
    assert history[-1] == new_message
