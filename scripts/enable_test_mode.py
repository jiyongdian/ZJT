#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键开启 E2E 测试挡板 + 写入 mock URL + 重置测试账户算力。

用法：
    # 直接在应用进程外/测试环境执行（不经 HTTP，无需 admin 权限）
    python scripts/enable_test_mode.py
    # 指定测试账户（运行 E2E 前重置其算力到高值，保证不被扣穿）
    E2E_TEST_USER_ID=12345 python scripts/enable_test_mode.py

注意：
- bool 值必须传 Python True/False，不能传 "false" 字符串——
  config_util.py:365 为 `'true' if value else 'false'`，非空字符串 "false" 会被当真值写成 'true'。
- 算力/CDN/token 均【不绕过】，靠独立隔离环境 + 此处重置账户算力保证可控（见方案 §6）。
- 跨进程（SyncTaskExecutor 子进程）缓存传播见方案 §7，本脚本仅清当前进程缓存。
"""
import os
import sys

# 允许从仓库根目录直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_util import set_dynamic_config_value, invalidate_dynamic_cache

# (keys_tuple, (value, value_type))
KV = {
    ("test_mode", "enabled"): (True, "bool"),
    ("test_mode", "mock_images", "text_to_image"): ("/upload/mock/e2e_text_to_image.png", "string"),
    ("test_mode", "mock_images", "image_edit"): ("/upload/mock/e2e_image_edit.png", "string"),
    ("test_mode", "mock_images", "comfyui_text_to_image"): ("/upload/mock/e2e_comfyui_tti.png", "string"),
    ("test_mode", "mock_images", "comfyui_image_edit"): ("/upload/mock/e2e_comfyui_ie.png", "string"),
    ("test_mode", "mock_images", "grid_image"): ("/upload/mock/e2e_grid_2x2.png", "string"),
    ("test_mode", "mock_images", "multi_angle_front"): ("/upload/mock/e2e_ma_front.png", "string"),
    ("test_mode", "mock_images", "multi_angle_side"): ("/upload/mock/e2e_ma_side.png", "string"),
    ("test_mode", "mock_images", "multi_angle_back"): ("/upload/mock/e2e_ma_back.png", "string"),
    ("test_mode", "mock_videos", "image_to_video"): ("/upload/mock/e2e_i2v.mp4", "string"),
    ("test_mode", "mock_videos", "text_to_video"): ("/upload/mock/e2e_t2v.mp4", "string"),
    ("test_mode", "mock_videos", "digital_human"): ("/upload/mock/e2e_dh.mp4", "string"),
    ("test_mode", "mock_videos", "face_mask"): ("/upload/mock/e2e_face_mask.mp4", "string"),
    ("test_mode", "mock_audio", "tts"): ("/upload/mock/e2e_tts.mp3", "string"),
    ("test_mode", "mock_audio", "character_audio"): ("/upload/mock/e2e_char.mp3", "string"),
}


def write_configs():
    for keys, (val, vtype) in KV.items():
        set_dynamic_config_value(*keys, value=val, value_type=vtype)
    invalidate_dynamic_cache()  # 清当前进程缓存；跨进程见方案 §7
    print(f"[enable_test_mode] 已写入 {len(KV)} 条 test_mode 配置（含 enabled=True）")


def reset_test_balance(user_id: int, amount: int = 1_000_000):
    """测试前重置测试账户算力到固定高值（方案 §6.1）。"""
    from model.computing_power import ComputingPowerModel
    cp = ComputingPowerModel.get_by_user_id(user_id)
    if cp:
        ComputingPowerModel.update(user_id, amount)  # 与 token_task.py 同款签名 (user_id, new_power)
    else:
        ComputingPowerModel.create(user_id=user_id, computing_power=amount)
    print(f"[enable_test_mode] 测试账户 {user_id} 算力已重置为 {amount}")


def main():
    write_configs()
    uid = int(os.environ.get("E2E_TEST_USER_ID", "0") or 0)
    if uid:
        try:
            reset_test_balance(uid)
        except Exception as e:
            print(f"[enable_test_mode] 重置算力失败（非致命，可手动处理）: {e}", file=sys.stderr)
    else:
        print("[enable_test_mode] 未设置 E2E_TEST_USER_ID，跳过算力重置")
    print("[enable_test_mode] done.")


if __name__ == "__main__":
    main()
