#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
准备 E2E mock 预设资源到 upload/mock/。

需人工提供真实样本文件（视频/音频/2x2图/多角度图）放于 auto_test/samples/，
脚本仅做拷贝与缺失校验。
所有 mock 文件统一放 upload/mock/（server.py 已挂为 StaticFiles，/upload/mock/x 可直接 HTTP 访问）。

用法：
    python scripts/prepare_mock_assets.py
"""
import os
import sys
import stat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "upload", "mock")
SAMPLES_DIR = "auto_test/samples"

# (auto_test/samples 下源文件, upload/mock 目标文件名)
ASSETS = [
    (f"{SAMPLES_DIR}/e2e_text_to_image.png", "e2e_text_to_image.png"),
    (f"{SAMPLES_DIR}/e2e_image_edit.png", "e2e_image_edit.png"),
    (f"{SAMPLES_DIR}/e2e_comfyui_tti.png", "e2e_comfyui_tti.png"),
    (f"{SAMPLES_DIR}/e2e_comfyui_ie.png", "e2e_comfyui_ie.png"),
    (f"{SAMPLES_DIR}/e2e_grid_2x2.png", "e2e_grid_2x2.png"),   # 必须是真实 2x2 拼图
    (f"{SAMPLES_DIR}/e2e_ma_front.png", "e2e_ma_front.png"),
    (f"{SAMPLES_DIR}/e2e_ma_side.png", "e2e_ma_side.png"),
    (f"{SAMPLES_DIR}/e2e_ma_back.png", "e2e_ma_back.png"),
    (f"{SAMPLES_DIR}/e2e_i2v.mp4", "e2e_i2v.mp4"),            # 真实可播 mp4
    (f"{SAMPLES_DIR}/e2e_t2v.mp4", "e2e_t2v.mp4"),
    (f"{SAMPLES_DIR}/e2e_dh.mp4", "e2e_dh.mp4"),
    (f"{SAMPLES_DIR}/e2e_face_mask.mp4", "e2e_face_mask.mp4"),  # 下游 os.path.exists 校验，必须真实
    (f"{SAMPLES_DIR}/e2e_tts.mp3", "e2e_tts.mp3"),
    (f"{SAMPLES_DIR}/e2e_char.mp3", "e2e_char.mp3"),
    # 世界导入测试资产（由方案 §5.10 方式1：播种世界后真实导出固化，再放 auto_test/samples/）
    (f"{SAMPLES_DIR}/world_export_sample.zip", "world_export_sample.zip"),
]


def main():
    os.makedirs(DST, exist_ok=True)
    import shutil
    missing = []
    ok = 0
    for src, name in ASSETS:
        s = os.path.join(ROOT, src)
        d = os.path.join(DST, name)
        if not os.path.exists(s):
            missing.append(src)
            continue
        # 若目标已存在且为只读，先移除只读属性再覆盖
        if os.path.exists(d):
            os.chmod(d, stat.S_IWRITE)
        shutil.copy2(s, d)
        ok += 1
        print(f"OK  {d}")
    print(f"\n完成：{ok}/{len(ASSETS)} 个资源已就位到 {DST}")
    if missing:
        print(f"\n缺失样本（请准备后重跑）:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
