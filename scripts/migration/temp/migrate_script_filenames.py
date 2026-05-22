"""
[一次性迁移] 将剧本文件名从 script_{title}.json 重命名为 {episode_number}.json

⚠️ 此脚本只需运行一次，迁移完成后可删除。

运行方式：
    cd /path/to/project
    python scripts/migration/temp/migrate_script_filenames.py

前置条件：先部署新代码，再运行此脚本（新代码兼容新旧文件名格式）。

功能：
    遍历 script_writer 数据目录下所有用户/世界的 scripts 目录，
    将 script_*.json 格式的文件重命名为 {episode_number}.json 格式。
    - 没有 episode_number 的文件保持不变
    - 集数冲突的文件会报错但不删除
    - 输出详细的迁移报告
"""

import os
import json
import sys
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录"""
    # 从当前文件位置向上查找
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / 'config').is_dir() and (parent / 'script_writer_core').is_dir():
            return parent
    # 回退到项目根目录推断
    return current.parent.parent


def migrate():
    project_root = get_project_root()
    sw_dir = project_root / "files" / "script_writer"

    if not sw_dir.exists():
        print(f"❌ 数据目录不存在: {sw_dir}")
        print("   没有需要迁移的文件。")
        return

    migrated = 0
    errors = []
    skipped = []

    print(f"📂 扫描目录: {sw_dir}")
    print("-" * 60)

    # 遍历所有 user/world/scripts 目录
    user_count = 0
    for user_dir in sw_dir.iterdir():
        if not user_dir.is_dir():
            continue
        for world_dir in user_dir.iterdir():
            if not world_dir.is_dir():
                continue
            scripts_dir = world_dir / "scripts"
            if not scripts_dir.exists():
                continue

            user_count += 1

            # 收集所有 script_*.json 文件
            old_files = list(scripts_dir.glob("script_*.json"))
            if not old_files:
                continue

            for old_file in old_files:
                try:
                    data = json.loads(old_file.read_text(encoding='utf-8'))
                    ep = data.get('episode_number')
                    title = data.get('title', '未知')

                    if ep is None:
                        skipped.append((str(old_file), "无 episode_number"))
                        print(f"  ⏭ 跳过（无集数）: {old_file.name} (title={title})")
                        continue

                    new_file = scripts_dir / f"{ep}.json"

                    if new_file.exists() and new_file != old_file:
                        # 检查是否是同一个文件（某些情况下文件名可能已经是数字格式）
                        errors.append((str(old_file), f"冲突: {new_file.name} 已存在"))
                        print(f"  ❌ 冲突: {old_file.name} -> {new_file.name} (目标已存在)")
                        continue

                    old_file.rename(new_file)
                    migrated += 1
                    print(f"  ✅ {old_file.name} -> {new_file.name} (第{ep}集: {title})")

                except json.JSONDecodeError as e:
                    errors.append((str(old_file), f"JSON解析失败: {e}"))
                    print(f"  ❌ JSON解析失败: {old_file.name}")
                except Exception as e:
                    errors.append((str(old_file), str(e)))
                    print(f"  ❌ 错误: {old_file.name} - {e}")

    # 输出报告
    print("-" * 60)
    print(f"\n📊 迁移报告:")
    print(f"   扫描目录数: {user_count}")
    print(f"   成功迁移: {migrated} 个文件")
    print(f"   跳过: {len(skipped)} 个文件")

    if skipped:
        print(f"\n   ⏭ 跳过的文件:")
        for path, reason in skipped:
            print(f"      {path}: {reason}")

    if errors:
        print(f"\n   ❌ 错误 ({len(errors)}):")
        for path, reason in errors:
            print(f"      {path}: {reason}")

    if migrated > 0:
        print(f"\n✅ 迁移完成！共重命名 {migrated} 个剧本文件。")
    elif not skipped and not errors:
        print(f"\n✅ 没有需要迁移的文件（可能已经迁移过了）。")
    else:
        print(f"\n⚠️ 迁移完成，但存在问题，请检查上方报告。")


if __name__ == "__main__":
    migrate()
