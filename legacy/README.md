# legacy —— 早期模块化草稿（当前未启用）

这三个文件是最初尝试「把逻辑拆成模块」时写的版本，**当前 `main.py` 完全没有引用它们**，
功能已在 `main.py` 内部以自包含方式重新实现（为了 `pyinstaller -F` 单文件分发方便）。

保留原因：其中的函数划分（哈希计算 / 类型判断 / 预览命名 / 冲突处理）比 `main.py` 里更清晰，
后续如果要把 `main.py` 拆成 `core/` 包，可以直接以它们为基础改写。

## 注意：字段命名不一致，不能直接 import

| 含义 | legacy 中的键名 | `main.py` 中的键名 |
| --- | --- | --- |
| SHA256 指纹 | `sha256` | `sha` |
| UUID 名称 | `uuid_name` | `uuid` |
| 自定义名称 | `custom_name` | `custom` |
| 重命名结果 | `new_name` | `newname` |

另外 `renamer.update_selected_preview()` 内部用的是 `from utils import ...` 这种绝对导入，
在 `legacy/` 目录下运行时需要把该目录加入 `sys.path`，否则会 `ModuleNotFoundError`。

## 文件用途（供参考）

- `utils.py`：`get_file_sha256` / `get_file_type` / `format_file_size` / `format_modified_time` /
  `build_preview_name` / `format_duplicate_suffix`
- `renamer.py`：`detect_duplicates` / `update_selected_preview` / `apply_custom_to_selected` / `execute_rename`
- `config.py`：`APP_NAME` / `APP_VERSION` / `APP_AUTHOR`

## 若决定启用

1. 统一键名（推荐改成 `main.py` 现有的一套，避免改动主程序）；
2. 把 `from utils import ...` 改成相对导入或包内导入；
3. 逐段替换 `main.py` 中对应方法，每替换一处跑一次界面自测；
4. 在 `main.py` 顶部改为 `from config import APP_NAME, APP_VERSION, APP_AUTHOR`，
   并确认 PyInstaller 能自动收集 `config` 模块（同目录模块默认会被收集）。
