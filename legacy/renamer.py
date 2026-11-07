"""重命名核心逻辑

【legacy / 未启用】当前 main.py 未引用本文件，同等逻辑内联在 App._mark_duplicates /
run_update / run_rename 中。启用前需先统一键名，详见同目录 README.md。
"""

import os
from typing import List, Dict


def detect_duplicates(files: List[Dict]) -> List[Dict]:
    """根据 SHA256 指纹标记重复文件，但不再强制影响预览命名。"""
    fingerprint_map: Dict[str, List[Dict]] = {}

    for item in files:
        fp = item["sha256"]
        fingerprint_map.setdefault(fp, []).append(item)

    for group in fingerprint_map.values():
        if len(group) > 1:
            for item in group:
                item["status"] = "重复"
        else:
            group[0]["status"] = "唯一"

    return files


def update_selected_preview(files: List[Dict], rule: str,
                            prefix: str, suffix: str) -> List[Dict]:
    """
    只对勾选文件更新预览名。
    未勾选文件保持原有 new_name 不变。
    方案 B：预览不自动追加序号。
    """
    from utils import build_preview_name

    for item in files:
        if item["checked"]:
            item["new_name"] = build_preview_name(
                rule=rule,
                fingerprint=item["sha256"],
                uuid_name=item["uuid_name"],
                custom_name=item["custom_name"],
                prefix=prefix,
                suffix=suffix,
            ) + item["ext"]

    return files


def apply_custom_to_selected(files: List[Dict], custom_name: str) -> List[Dict]:
    """将自定义名称批量应用到所有勾选行，扩展名保持不变。"""
    for item in files:
        if item["checked"]:
            item["custom_name"] = custom_name
            item["new_name"] = f"{custom_name}{item['ext']}"

    return files


def execute_rename(selected_files: List[Dict],
                   duplicate_template: str) -> Dict:
    """
    真正执行批量重命名。
    方案 B：只有目标文件夹中实际出现同名冲突时，才追加序号。
    """
    from utils import format_duplicate_suffix

    success = 0
    failed = 0
    skipped = 0
    errors = []

    # 收集目标文件夹中的现有文件名，用于冲突检测
    folder_files: Dict[str, set] = {}
    for item in selected_files:
        folder = os.path.dirname(item["path"])
        if folder not in folder_files:
            try:
                folder_files[folder] = set(os.listdir(folder))
            except Exception:
                folder_files[folder] = set()

    for item in selected_files:
        old_path = item["path"]
        new_name = item["new_name"]
        folder = os.path.dirname(old_path)
        new_path = os.path.join(folder, new_name)

        try:
            if old_path == new_path:
                skipped += 1
                continue

            # 目标已存在，按冲突追加序号
            if os.path.exists(new_path) or new_name in folder_files.get(folder, set()):
                base, ext = os.path.splitext(new_name)
                counter = 1
                while True:
                    suffix = format_duplicate_suffix(duplicate_template, counter)
                    new_name_try = f"{base}{suffix}{ext}"
                    new_path_try = os.path.join(folder, new_name_try)

                    if not os.path.exists(new_path_try) and \
                       new_name_try not in folder_files.get(folder, set()):
                        new_path = new_path_try
                        new_name = new_name_try
                        break

                    counter += 1

            os.rename(old_path, new_path)
            item["path"] = new_path
            item["name"] = new_name
            success += 1

            # 加入已占用文件名集合，避免同批文件之间冲突
            folder_files.setdefault(folder, set()).add(new_name)

        except Exception as e:
            failed += 1
            errors.append(f"{item['name']}: {str(e)}")

    return {
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
    }
