import scripts.prepare_mock_assets as prepare_mock_assets


def test_mock_asset_sources_live_under_auto_test_samples():
    assert prepare_mock_assets.SAMPLES_DIR.endswith("auto_test/samples")
    assert all(
        src.startswith("auto_test/samples/")
        for src, _ in prepare_mock_assets.ASSETS
    )
