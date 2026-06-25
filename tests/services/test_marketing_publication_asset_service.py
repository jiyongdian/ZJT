import json
from pathlib import Path
from types import SimpleNamespace


def _seed_config_cache(monkeypatch):
    monkeypatch.setenv("comfyui_env", "unit")
    import config.config_util as config_util

    config_util._config_cache["config_unit.yml"] = {
        "database": {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "unit",
            "password": "unit",
            "database": "unit",
        }
    }


def test_promote_assets_copies_cache_files_and_rewrites_snapshot(tmp_path, monkeypatch):
    _seed_config_cache(monkeypatch)
    from services.marketing_publication_asset_service import MarketingPublicationAssetService

    root = tmp_path
    cache_file = root / "upload" / "cache" / "2026-06-24" / "result.png"
    ref_file = root / "upload" / "temp" / "20260624" / "ref.png"
    cache_file.parent.mkdir(parents=True)
    ref_file.parent.mkdir(parents=True)
    cache_file.write_bytes(b"result-bytes")
    ref_file.write_bytes(b"ref-bytes")

    created_mappings = []

    def fake_create(**kwargs):
        created_mappings.append(kwargs)
        return len(created_mappings)

    monkeypatch.setattr(
        "services.marketing_publication_asset_service.MediaFileMappingModel.create",
        fake_create,
    )

    ai_tool = SimpleNamespace(
        id=91,
        user_id=7,
        prompt="make a bright poster",
        result_url="/upload/cache/2026-06-24/result.png",
        image_path="/upload/temp/20260624/ref.png",
        reference_images=json.dumps(["/upload/temp/20260624/ref.png"]),
        audio_path=None,
        video_path=None,
        type=12,
        ratio="9:16",
        duration=None,
        image_size="2K",
        extra_config=json.dumps({"image_mode": "first_last_frame", "model_key": "seedream_5"}),
        implementation=3,
    )

    promoted = MarketingPublicationAssetService.promote_assets(ai_tool, 123, root_dir=root)

    result_path = root / promoted["result_url"].lstrip("/")
    ref_path = root / "upload" / "marketing_publications" / "123" / "reference_1.png"

    assert promoted["result_url"] == "/upload/marketing_publications/123/result.png"
    assert promoted["cover_url"] == "/upload/marketing_publications/123/result.png"
    assert promoted["reference_images"] == ["/upload/marketing_publications/123/reference_1.png"]
    assert result_path.read_bytes() == b"result-bytes"
    assert ref_path.read_bytes() == b"ref-bytes"
    assert promoted["params_snapshot"]["prompt"] == "make a bright poster"
    assert promoted["params_snapshot"]["media"][0]["serverUrl"] == promoted["reference_images"][0]
    assert promoted["params_snapshot"]["reference_images"] == promoted["reference_images"]
    assert {m["policy_code"] for m in created_mappings} == {"never_expire"}


def test_text_to_image_snapshot_does_not_use_result_as_remix_media(tmp_path, monkeypatch):
    _seed_config_cache(monkeypatch)
    from services.marketing_publication_asset_service import MarketingPublicationAssetService

    root = tmp_path
    cache_file = root / "upload" / "cache" / "2026-06-25" / "text2image.png"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_bytes(b"result-bytes")

    monkeypatch.setattr(
        "services.marketing_publication_asset_service.MediaFileMappingModel.create",
        lambda **kwargs: 1,
    )
    monkeypatch.setattr(
        "services.marketing_publication_asset_service.MarketingPublicationAssetService._get_task_config",
        lambda task_id: SimpleNamespace(category="text_to_image", key="seedream_5", name="Seedream 5.0"),
    )

    ai_tool = SimpleNamespace(
        id=93,
        user_id=7,
        prompt="make a puppy portrait",
        result_url="/upload/cache/2026-06-25/text2image.png",
        image_path=None,
        reference_images=None,
        audio_path=None,
        video_path=None,
        type=16,
        ratio="9:16",
        duration=None,
        image_size="2K",
        extra_config=None,
        implementation=3,
    )

    promoted = MarketingPublicationAssetService.promote_assets(ai_tool, 125, root_dir=root)

    assert promoted["params_snapshot"]["prompt"] == "make a puppy portrait"
    assert promoted["params_snapshot"]["result_url"] == promoted["result_url"]
    assert "media" not in promoted["params_snapshot"]
    assert "reference_images" not in promoted["params_snapshot"]


def test_promote_assets_copies_absolute_local_upload_url_without_http_download(tmp_path, monkeypatch):
    _seed_config_cache(monkeypatch)
    from services.marketing_publication_asset_service import MarketingPublicationAssetService

    root = tmp_path
    upload_file = root / "upload" / "temp" / "20260625" / "upload_20260625_104009_160fa219.png"
    upload_file.parent.mkdir(parents=True)
    upload_file.write_bytes(b"uploaded-reference")
    result_file = root / "upload" / "cache" / "2026-06-25" / "result.png"
    result_file.parent.mkdir(parents=True)
    result_file.write_bytes(b"result-bytes")

    monkeypatch.setattr(
        "services.marketing_publication_asset_service.MediaFileMappingModel.create",
        lambda **kwargs: 1,
    )
    monkeypatch.setattr(
        "services.marketing_publication_asset_service.urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not download local upload URL")),
    )

    ai_tool = SimpleNamespace(
        id=94,
        user_id=7,
        prompt="edit with uploaded reference",
        result_url="/upload/cache/2026-06-25/result.png",
        image_path="http://localhost:11000/upload/temp/20260625/upload_20260625_104009_160fa219.png",
        reference_images=None,
        audio_path=None,
        video_path=None,
        type=12,
        ratio="1:1",
        duration=None,
        image_size=None,
        extra_config=None,
        implementation=3,
    )

    promoted = MarketingPublicationAssetService.promote_assets(ai_tool, 126, root_dir=root)

    ref_path = root / "upload" / "marketing_publications" / "126" / "reference_1.png"
    assert ref_path.read_bytes() == b"uploaded-reference"
    assert promoted["reference_images"] == ["/upload/marketing_publications/126/reference_1.png"]


def test_text_to_video_snapshot_does_not_use_result_as_remix_media(tmp_path, monkeypatch):
    _seed_config_cache(monkeypatch)
    from services.marketing_publication_asset_service import MarketingPublicationAssetService

    root = tmp_path
    result_file = root / "upload" / "cache" / "2026-06-25" / "text2video.mp4"
    result_file.parent.mkdir(parents=True)
    result_file.write_bytes(b"video-result")

    monkeypatch.setattr(
        "services.marketing_publication_asset_service.MediaFileMappingModel.create",
        lambda **kwargs: 1,
    )
    monkeypatch.setattr(
        "services.marketing_publication_asset_service.MarketingPublicationAssetService._get_task_config",
        lambda task_id: SimpleNamespace(category="text_to_video", key="seedance_1", name="Seedance 1.0"),
    )

    ai_tool = SimpleNamespace(
        id=95,
        user_id=7,
        prompt="make a product video",
        result_url="/upload/cache/2026-06-25/text2video.mp4",
        image_path=None,
        reference_images=None,
        audio_path=None,
        video_path=None,
        type=22,
        ratio="16:9",
        duration=5,
        image_size=None,
        extra_config=None,
        implementation=3,
    )

    promoted = MarketingPublicationAssetService.promote_assets(ai_tool, 127, root_dir=root)

    assert promoted["params_snapshot"]["mode"] == "video"
    assert promoted["params_snapshot"]["media_type"] == "video"
    assert promoted["params_snapshot"]["result_url"] == promoted["result_url"]
    assert "media" not in promoted["params_snapshot"]
    assert "video_urls" not in promoted["params_snapshot"]
    assert "reference_images" not in promoted["params_snapshot"]


def test_image_and_video_references_are_included_for_video_remix(tmp_path, monkeypatch):
    _seed_config_cache(monkeypatch)
    from services.marketing_publication_asset_service import MarketingPublicationAssetService

    root = tmp_path
    result_file = root / "upload" / "cache" / "2026-06-25" / "result.mp4"
    image_ref = root / "upload" / "temp" / "20260625" / "first.png"
    video_ref = root / "upload" / "temp" / "20260625" / "ref.mp4"
    for path, payload in [(result_file, b"video-result"), (image_ref, b"image-ref"), (video_ref, b"video-ref")]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    monkeypatch.setattr(
        "services.marketing_publication_asset_service.MediaFileMappingModel.create",
        lambda **kwargs: 1,
    )
    monkeypatch.setattr(
        "services.marketing_publication_asset_service.MarketingPublicationAssetService._get_task_config",
        lambda task_id: SimpleNamespace(category="image_to_video", key="seedance_1", name="Seedance 1.0"),
    )

    ai_tool = SimpleNamespace(
        id=96,
        user_id=7,
        prompt="animate the product",
        result_url="/upload/cache/2026-06-25/result.mp4",
        image_path="/upload/temp/20260625/first.png",
        reference_images=None,
        audio_path=None,
        video_path="/upload/temp/20260625/ref.mp4",
        type=23,
        ratio="16:9",
        duration=5,
        image_size=None,
        extra_config=None,
        implementation=3,
    )

    promoted = MarketingPublicationAssetService.promote_assets(ai_tool, 128, root_dir=root)

    assert promoted["reference_images"] == ["/upload/marketing_publications/128/reference_1.png"]
    assert promoted["video_urls"] == ["/upload/marketing_publications/128/video_1.mp4"]
    assert promoted["params_snapshot"]["media"] == [
        {
            "type": "image",
            "serverUrl": "/upload/marketing_publications/128/reference_1.png",
            "thumbnailUrl": "/upload/marketing_publications/128/reference_1.png",
        },
        {
            "type": "video",
            "serverUrl": "/upload/marketing_publications/128/video_1.mp4",
            "thumbnailUrl": "/upload/marketing_publications/128/video_1.mp4",
        },
    ]


def test_promote_assets_fails_when_source_file_is_missing(tmp_path, monkeypatch):
    _seed_config_cache(monkeypatch)
    from services.marketing_publication_asset_service import PublicationAssetError
    from services.marketing_publication_asset_service import MarketingPublicationAssetService

    ai_tool = SimpleNamespace(
        id=92,
        user_id=7,
        prompt="expired file",
        result_url="/upload/cache/2026-06-24/missing.png",
        image_path=None,
        reference_images=None,
        audio_path=None,
        video_path=None,
        type=12,
        ratio="1:1",
        duration=None,
        image_size=None,
        extra_config=None,
        implementation=3,
    )

    try:
        MarketingPublicationAssetService.promote_assets(ai_tool, 124, root_dir=tmp_path)
    except PublicationAssetError as exc:
        assert "missing" in str(exc).lower() or "not found" in str(exc).lower()
    else:
        raise AssertionError("Expected PublicationAssetError for missing source file")
