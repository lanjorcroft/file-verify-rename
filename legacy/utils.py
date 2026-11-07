"""工具函数：计算 SHA256、获取文件信息、生成序号等

【legacy / 未启用】当前 main.py 未引用本文件，同等功能内联在 main.py 中。
键名与 main.py 不一致（sha256 / new_name vs sha / newname），详见同目录 README.md。
"""

import hashlib
import os
import uuid
from datetime import datetime


def get_file_sha256(file_path: str, chunk_size: int = 64 * 1024) -> str:
    """计算文件 SHA256 指纹"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def get_file_extension(file_path: str) -> str:
    """获取文件扩展名"""
    _, ext = os.path.splitext(file_path)
    return ext.lower()


def get_file_type(file_path: str) -> str:
    """根据扩展名判断文件类型"""
    ext = get_file_extension(file_path)

    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico", ".tif", ".tiff"}
    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}
    audio_exts = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"}
    document_exts = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv"}
    archive_exts = {".zip", ".rar", ".7z", ".tar", ".gz"}
    code_exts = {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".cs", ".go", ".json", ".xml"}

    if ext in image_exts:
        return "图片"
    if ext in video_exts:
        return "视频"
    if ext in audio_exts:
        return "音频"
    if ext in document_exts:
        return "文档"
    if ext in archive_exts:
        return "压缩包"
    if ext in code_exts:
        return "代码"

    return ext[1:].upper() if ext else "未知"


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.2f} MB"
    return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"


def format_modified_time(file_path: str) -> str:
    """获取文件修改日期"""
    try:
        timestamp = os.path.getmtime(file_path)
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def generate_uuid_name() -> str:
    """生成 UUID 名称"""
    return uuid.uuid4().hex


def build_preview_name(rule: str, fingerprint: str,
                       uuid_name: str, custom_name: str,
                       prefix: str, suffix: str) -> str:
    """
    生成预览文件名（不含扩展名）。
    方案 B：预览时不根据列表重名追加序号，只按规则生成基础名。
    """

    if rule == "UUID命名":
        base = uuid_name
    elif rule == "自定义命名":
        base = custom_name if custom_name else "未命名"
    else:
        base = fingerprint

    return f"{prefix}{base}{suffix}"


def format_duplicate_suffix(template: str, index: int) -> str:
    """
    根据模板生成重复追加部分。
    例如 template="（{n:02d}）"，index=1 → "（01）"
    """
    return template.format(n=index)
