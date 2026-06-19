import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from task.visual_drivers.digital_human_runninghub_v1_driver import DigitalHumanRunninghubV1Driver
from utils.file_storage.base import UploadResult


class FakeRunningHubStorage:
    def __init__(self):
        self.calls = []

    async def upload_file(self, key, file_path, content_type=None):
        self.calls.append((key, file_path, content_type))
        if "audio1.mp3" in file_path:
            return UploadResult(success=True, key="openapi/audio1.wav", url="https://rh.example/audio1.wav")
        return UploadResult(success=True, key=file_path, url=file_path)


def make_driver():
    driver = DigitalHumanRunninghubV1Driver.__new__(DigitalHumanRunninghubV1Driver)
    driver._storage = FakeRunningHubStorage()
    driver._is_local = False
    driver._host = "https://www.runninghub.cn"
    driver._webapp_id = "2017494689997398017"
    driver._api_key = "test-key"
    driver.logger = MagicMock()
    return driver


def make_ai_tool(audio_url):
    return SimpleNamespace(
        message=audio_url,
        image_path="https://example.com/person.png",
        ratio="9:16",
        prompt="hello",
    )


def get_audio_field_value(request):
    node = next(n for n in request["json"]["nodeInfoList"] if n["fieldName"] == "audio")
    return node["fieldValue"]


def test_build_create_request_uploads_localhost_audio_to_runninghub_key():
    driver = make_driver()

    request = asyncio.run(driver.build_create_request(
        make_ai_tool("http://localhost:9003/upload/marketing/pic/session/audio1.mp3")
    ))

    assert get_audio_field_value(request) == "openapi/audio1.wav"
    assert driver._storage.calls[0][1] == "http://localhost:9003/upload/marketing/pic/session/audio1.mp3"


def test_build_create_request_keeps_existing_runninghub_audio_key():
    driver = make_driver()
    key = "openapi/e2244df7cd2d647601351be00e4275fc284fc150489ca17437b0a71accc1fb9c.wav"

    request = asyncio.run(driver.build_create_request(make_ai_tool(key)))

    assert get_audio_field_value(request) == key
    assert all(call[1] != key for call in driver._storage.calls)
