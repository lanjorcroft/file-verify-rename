# -*- coding: utf-8 -*-
"""
文件校验重命名工具
作者：Lanjor Croft, Independent Creator & Maker
版本：Version 2.0.0

v2.0.0 主要变化（详见 CHANGELOG.md）：
  1. 修复扫描线程异常后界面卡死（scanning 标志不复位）的问题
  2. 重命名增加「撤销上次重命名」+ 本地日志，误操作可回退
  3. 重命名前校验文件名非法字符 / Windows 保留名 / 路径超长
  4. 单行勾选改为增量刷新，大列表不再整表重建
  5. 文件夹导入容错（无权限目录跳过并计数）、去重改用集合
  6. 全局异常兜底，弹窗提示而不是静默失败
"""
import os
import sys
import csv
import queue
import uuid
import hashlib
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

APP_NAME = "文件校验重命名工具"
APP_VERSION = "Version 2.0.0"
APP_AUTHOR = "Lanjor Croft, Independent Creator & Maker"

# ===== 勾选框样式（想换成别的符号，直接改这两个字符） =====
# 可选样式举例：
#   方案1:  "☑" / "☐"   （默认，实心/空心方框）
#   方案2:  "✓" / "✗"   （对勾/叉）
#   方案3:  "■" / "□"   （实心/空心方块）
#   方案4:  "●" / "○"   （实心/空心圆）
#   方案5:  "[X]" / "[ ]"（纯文本，最稳）
CHECKED = "☑"
UNCHECKED = "☐"

# Windows 文件名非法字符与保留名
ILLEGAL_CHARS = set('<>:"/\\|?*')
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# ===================== 工具函数 =====================
def sha256_of_file(path, chunk=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            c = f.read(chunk)
            if not c:
                break
            h.update(c)
    return h.hexdigest()


def file_type(ext):
    ext = ext.lower()
    table = [
        ((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico", ".tif", ".tiff"), "图片"),
        ((".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"), "视频"),
        ((".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"), "音频"),
        ((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv"), "文档"),
        ((".zip", ".rar", ".7z", ".tar", ".gz"), "压缩包"),
        ((".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".cs", ".go", ".json", ".xml"), "代码"),
    ]
    for exts, name in table:
        if ext in exts:
            return name
    return ext[1:].upper() if ext else "未知"


def fmt_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def fmt_mtime(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def name_problem(name):
    """检查文件名（含扩展名）是否合法，合法返回 None，否则返回原因。"""
    if not name or name in (".", ".."):
        return "文件名为空"
    for c in name:
        if c in ILLEGAL_CHARS or ord(c) < 32:
            return f'文件名含非法字符「{c}」'
    stem = os.path.splitext(name)[0].upper()
    if stem in RESERVED_NAMES:
        return f"「{stem}」是 Windows 保留名"
    if name != name.rstrip(" ."):
        return "文件名不能以空格或点结尾"
    if len(name) > 255:
        return "文件名超过 255 字符"
    return None


def log_dir():
    """重命名日志目录：%LOCALAPPDATA%\\FileVerifyRename\\logs"""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "FileVerifyRename", "logs")
    os.makedirs(d, exist_ok=True)
    return d


# ===================== 主程序 =====================
class App:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP_NAME}  {APP_VERSION}")
        root.geometry("1320x760")
        root.minsize(1150, 680)
        root.configure(bg="#f5f6f8")
        # 全局异常兜底：回调里抛异常时弹窗提示，不再静默吞掉
        root.report_callback_exception = self._on_callback_error
        self._set_window_icon(root)
        self.files = []
        self._paths = set()          # 已加载路径集合，导入去重 O(1)
        self.scanning = False
        self.current_select_idx = None
        self.last_checked_idx = None
        self._last_rename = []       # [(旧路径, 新路径)]，用于撤销
        self._sort_state = {}        # {列名: True/False, True=降序}
        self._ui_q = queue.Queue()   # 工作线程 → 主线程的 UI 更新队列
        self._style()
        self._ui()
        self._drain_ui()

    # ---------- 窗口图标（直接用 logo.ico，无需 Pillow） ----------
    def _set_window_icon(self, root):
        # 打包后(exe)：资源被解压到 _MEIPASS 根目录；开发时：脚本同级 assets/ 目录
        base = getattr(sys, "_MEIPASS",
                       os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(base, "logo.ico"),            # 打包后
            os.path.join(base, "assets", "logo.ico"),  # 源码运行
        ]
        for ico in candidates:
            if os.path.exists(ico):
                try:
                    # default= 让弹窗、子对话框也继承该图标
                    root.iconbitmap(default=ico)
                    return
                except Exception as e:
                    print("窗口图标设置失败：", e)
        print("窗口图标设置失败：未找到 logo.ico ->", candidates)

    # ---------- 样式 ----------
    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background="#f5f6f8", foreground="#222",
                    font=("Microsoft YaHei UI", 9))
        s.configure("TFrame", background="#f5f6f8")
        s.configure("TLabel", background="#f5f6f8", foreground="#333")
        s.configure("Title.TLabel", background="#f5f6f8",
                    font=("Microsoft YaHei UI", 15, "bold"), foreground="#1f2937")
        s.configure("Sub.TLabel", background="#f5f6f8",
                    font=("Microsoft YaHei UI", 9), foreground="#6b7280")
        s.configure("Hint.TLabel", background="#f5f6f8",
                    font=("Microsoft YaHei UI", 8), foreground="#9ca3af")
        s.configure("TButton", padding=(10, 5))
        s.configure("Accent.TButton", padding=(12, 6),
                    font=("Microsoft YaHei UI", 9, "bold"))
        s.configure("TEntry", padding=3)
        s.configure("TCombobox", padding=3)
        s.configure("TLabelframe", background="#f5f6f8", padding=(12, 8))
        s.configure("TLabelframe.Label", background="#f5f6f8",
                    foreground="#374151",
                    font=("Microsoft YaHei UI", 9, "bold"))
        s.configure("Treeview", background="#fff", fieldbackground="#fff",
                    rowheight=28, font=("Microsoft YaHei UI", 9))
        s.configure("Treeview.Heading", background="#374151", foreground="#fff",
                    font=("Microsoft YaHei UI", 9, "bold"), padding=5)
        s.map("Treeview",
              background=[("selected", "#3b82f6")],
              foreground=[("selected", "#fff")])

    # ---------- 界面 ----------
    def _ui(self):
        # 标题栏
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=18, pady=(14, 8))
        title_box = ttk.Frame(header)
        title_box.pack(side=tk.LEFT)
        ttk.Label(title_box, text=APP_NAME, style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(title_box,
                  text=f"{APP_VERSION}    |    {APP_AUTHOR}",
                  style="Sub.TLabel").pack(anchor=tk.W)
        # 工具栏
        bar = ttk.Frame(self.root)
        bar.pack(fill=tk.X, padx=18, pady=(2, 6))
        ttk.Button(bar, text="上传文件", command=self.pick_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="上传文件夹", command=self.pick_folder).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="清空列表", command=self.clear_list).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="导出列表", command=self.export_list).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Button(bar, text="全选", command=lambda: self.set_all_checked(True)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="取消全选", command=lambda: self.set_all_checked(False)).pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(bar, textvariable=self.status_var,
                                      foreground="#16a34a")
        self.status_label.pack(side=tk.RIGHT)
        # 表格
        wrap = ttk.Frame(self.root)
        wrap.pack(fill=tk.BOTH, expand=True, padx=18, pady=4)
        cols = ("chk", "type", "name", "size", "mtime", "sha", "status", "newname")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        # 表头（可排序列绑定 command）
        self.tree.heading("chk",     text="勾选")
        self.tree.heading("type",    text="文件类型", command=lambda: self.sort_by("type"))
        self.tree.heading("name",    text="文件名称", command=lambda: self.sort_by("name"))
        self.tree.heading("size",    text="大小",     command=lambda: self.sort_by("size"))
        self.tree.heading("mtime",   text="修改日期", command=lambda: self.sort_by("mtime"))
        self.tree.heading("sha",     text="SHA256指纹")
        self.tree.heading("status",  text="状态",     command=lambda: self.sort_by("status"))
        self.tree.heading("newname", text="文件重命名", command=lambda: self.sort_by("newname"))
        widths = {
            "chk": 60, "type": 80, "name": 220, "size": 90,
            "mtime": 150, "sha": 520, "status": 70, "newname": 420,
        }
        anchors = {
            "chk": tk.CENTER, "type": tk.W, "name": tk.W, "size": tk.E,
            "mtime": tk.W, "sha": tk.W, "status": tk.CENTER, "newname": tk.W,
        }
        for c in cols:
            self.tree.column(c, width=widths[c], anchor=anchors[c], stretch=False)
        self.tree.tag_configure("dup", background="#fef2f2", foreground="#dc2626")
        self.tree.tag_configure("chosen", background="#dbeafe")
        hsb = ttk.Scrollbar(wrap, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(xscrollcommand=hsb.set)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<ButtonRelease-1>", self.on_row_click)
        # 命名规则面板
        panel = ttk.LabelFrame(self.root, text=" 命名规则 ")
        panel.pack(fill=tk.X, padx=18, pady=(8, 14))
        row1 = ttk.Frame(panel)
        row1.pack(fill=tk.X, padx=6, pady=(4, 6))
        ttk.Label(row1, text="命名规则：").pack(side=tk.LEFT)
        self.rule_var = tk.StringVar(value="SHA256命名")
        self.rule_cb = ttk.Combobox(row1, textvariable=self.rule_var, width=14,
                                    state="readonly",
                                    values=("SHA256命名", "UUID命名", "自定义命名"))
        self.rule_cb.pack(side=tk.LEFT, padx=(2, 16))
        self.rule_cb.bind("<<ComboboxSelected>>", lambda e: self._sync_custom_state())
        ttk.Label(row1, text="前缀：").pack(side=tk.LEFT)
        self.prefix_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.prefix_var, width=12).pack(side=tk.LEFT, padx=(2, 12))
        ttk.Label(row1, text="后缀：").pack(side=tk.LEFT)
        self.suffix_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.suffix_var, width=12).pack(side=tk.LEFT, padx=(2, 12))
        ttk.Label(row1, text="冲突追加：").pack(side=tk.LEFT)
        self.seq_fmt_var = tk.StringVar(value="（{n:02d}）")
        ttk.Entry(row1, textvariable=self.seq_fmt_var, width=16).pack(side=tk.LEFT, padx=(2, 6))
        ttk.Label(row1, text="默认用 {n:02d} 表示序号递增格式",
                  style="Hint.TLabel").pack(side=tk.LEFT)
        row2 = ttk.Frame(panel)
        row2.pack(fill=tk.X, padx=6, pady=(0, 4))
        self.custom_label = ttk.Label(row2, text="自定义名称：")
        self.custom_label.pack(side=tk.LEFT)
        self.custom_var = tk.StringVar()
        self.custom_entry = ttk.Entry(row2, textvariable=self.custom_var, width=24)
        self.custom_entry.pack(side=tk.LEFT, padx=(2, 6))
        self.custom_apply_btn = ttk.Button(row2, text="应用到勾选行",
                                           command=self.apply_custom)
        self.custom_apply_btn.pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(row2,
                  text="（自定义命名时，输入名称点“应用到勾选行”，批量应用到所有勾选文件；扩展名自动保留）",
                  style="Hint.TLabel").pack(side=tk.LEFT)
        ttk.Button(row2, text="批量重命名", style="Accent.TButton",
                   command=self.run_rename).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(row2, text="命名更新", style="Accent.TButton",
                   command=self.run_update).pack(side=tk.RIGHT)
        ttk.Button(row2, text="撤销上次重命名",
                   command=self.undo_last_rename).pack(side=tk.RIGHT, padx=(0, 6))
        self._sync_custom_state()

    # ---------- 规则切换 ----------
    def _sync_custom_state(self):
        active = self.rule_var.get() == "自定义命名"
        state = "normal" if active else "disabled"
        for w in (self.custom_entry, self.custom_apply_btn):
            try:
                w.configure(state=state)
            except Exception:
                pass

    # ---------- 上传 ----------
    def pick_files(self):
        if self.scanning:
            self._set_status("正在读取文件，请稍候…", "#d97706")
            return
        paths = filedialog.askopenfilenames(title="选择文件")
        if paths:
            self._add(paths)

    def pick_folder(self):
        if self.scanning:
            self._set_status("正在读取文件，请稍候…", "#d97706")
            return
        folder = filedialog.askdirectory(title="选择文件夹")
        if not folder:
            return
        self._set_status("正在扫描文件夹…", "#2563eb")
        self.root.update_idletasks()
        paths = []
        skipped_dirs = []

        def walk_error(e):
            skipped_dirs.append(str(getattr(e, "filename", "") or e))

        for dp, _, fns in os.walk(folder, onerror=walk_error):
            for fn in fns:
                paths.append(os.path.join(dp, fn))
        if not paths:
            messagebox.showinfo("提示", "文件夹中没有文件。")
            self._set_status("就绪", "#16a34a")
            return
        if skipped_dirs:
            messagebox.showwarning(
                "部分目录无法访问",
                f"有 {len(skipped_dirs)} 个目录因权限不足被跳过，例如：\n"
                f"{skipped_dirs[0]}")
        self._add(paths)

    # ---------- 线程 → 主线程的 UI 通道 ----------
    def _post(self, fn):
        """工作线程把 UI 操作投递到队列，由主线程执行（避免跨线程调用 Tk）。"""
        self._ui_q.put(fn)

    def _drain_ui(self):
        try:
            while True:
                fn = self._ui_q.get_nowait()
                try:
                    fn()
                except Exception as e:
                    print("UI 更新失败", e)
        except queue.Empty:
            pass
        try:
            self.root.after(40, self._drain_ui)
        except Exception:
            pass   # 窗口已销毁

    def _add(self, paths):
        if self.scanning:
            return
        self.scanning = True
        total = len(paths)
        self._set_status(f"正在读取文件… 0/{total}", "#2563eb")

        def work():
            added = 0
            failed = 0
            try:
                for i, p in enumerate(paths, 1):
                    try:
                        ap = os.path.abspath(p)
                        if ap in self._paths:
                            continue
                        ext = os.path.splitext(ap)[1]
                        self.files.append({
                            "path": ap,
                            "name": os.path.basename(ap),
                            "type": file_type(ext),
                            "size": os.path.getsize(ap),
                            "mtime": fmt_mtime(ap),
                            "ext": ext,
                            "sha": sha256_of_file(ap),
                            "uuid": uuid.uuid4().hex,
                            "custom": "",
                            "checked": False,
                            "status": "唯一",
                            "newname": "",
                        })
                        self._paths.add(ap)
                        added += 1
                    except Exception as e:
                        failed += 1
                        print("读取失败", p, e)
                    # 每 25 个文件刷新一次进度，避免频繁跨线程调度
                    if i % 25 == 0 or i == total:
                        self._post(lambda i=i: self._set_status(
                            f"正在读取文件… {i}/{total}", "#2563eb"))
            except Exception as e:
                print("扫描线程异常", e)
            finally:
                # 关键：先复位标志，再做 UI 更新；
                # 否则中途异常会让界面永久卡在「正在读取」且无法再导入
                self.scanning = False
                try:
                    self._mark_duplicates()
                except Exception as e:
                    print("重复检测失败", e)
                msg = f"已加载 {added} 个文件"
                if failed:
                    msg += f"，{failed} 个读取失败"
                self._post(self._refresh)
                self._post(lambda: self._set_status(msg, "#16a34a"))

        threading.Thread(target=work, daemon=True).start()

    def _mark_duplicates(self):
        groups = {}
        for f in self.files:
            groups.setdefault(f["sha"], []).append(f)
        for grp in groups.values():
            for f in grp:
                f["status"] = "重复" if len(grp) > 1 else "唯一"

    # ---------- 表格 ----------
    def _row_values(self, f):
        return (
            CHECKED if f["checked"] else UNCHECKED,
            f["type"], f["name"], fmt_size(f["size"]),
            f["mtime"], f["sha"], f["status"], f["newname"],
        )

    def _row_tags(self, f):
        tags = []
        if f["status"] == "重复":
            tags.append("dup")
        if f["checked"]:
            tags.append("chosen")
        return tags

    def _refresh(self):
        """整表重建：仅在导入、排序、清空等结构变化时调用。"""
        for it in self.tree.get_children():
            self.tree.delete(it)
        for i, f in enumerate(self.files):
            self.tree.insert("", tk.END, iid=str(i),
                             values=self._row_values(f), tags=self._row_tags(f))

    def _refresh_rows(self, indices):
        """增量刷新指定行：勾选等单行变化时避免整表重建。"""
        for idx in indices:
            if 0 <= idx < len(self.files):
                iid = str(idx)
                if self.tree.exists(iid):
                    f = self.files[idx]
                    self.tree.item(iid, values=self._row_values(f),
                                   tags=self._row_tags(f))

    def on_row_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        idx = int(item)
        col = self.tree.identify_column(event.x)
        if col == "#1":
            new_state = not self.files[idx]["checked"]
            # Shift 连选
            if (event.state & 0x0001) and self.last_checked_idx is not None:
                lo = min(self.last_checked_idx, idx)
                hi = max(self.last_checked_idx, idx)
                for i in range(lo, hi + 1):
                    self.files[i]["checked"] = new_state
                self._refresh_rows(range(lo, hi + 1))
            else:
                self.files[idx]["checked"] = new_state
                self._refresh_rows([idx])
            self.last_checked_idx = idx
            return
        # 普通列 = 选中行
        self.current_select_idx = idx
        self.custom_var.set(self.files[idx]["custom"])

    def set_all_checked(self, val):
        for f in self.files:
            f["checked"] = val
        self.last_checked_idx = None
        self._refresh()

    # ---------- 列排序 ----------
    def sort_by(self, col):
        if self.scanning:
            self._set_status("正在读取文件，排序请稍候…", "#d97706")
            return
        reverse = self._sort_state.get(col, False)
        # 排序键
        key_map = {
            "type":    lambda f: f["type"],
            "name":    lambda f: f["name"].lower(),
            "size":    lambda f: f["size"],
            "mtime":   lambda f: f["mtime"],
            "status":  lambda f: f["status"],
            "newname": lambda f: (f["newname"] or "").lower(),
        }
        self.files.sort(key=key_map[col], reverse=reverse)
        self._sort_state[col] = not reverse
        self.last_checked_idx = None
        self.current_select_idx = None
        self._refresh()
        arrow = "↓" if reverse else "↑"
        self._set_status(f"按【{col}】{'降序' if reverse else '升序'} {arrow}", "#2563eb")

    # ---------- 应用自定义名（批量到勾选行） ----------
    def apply_custom(self):
        if self.rule_var.get() != "自定义命名":
            messagebox.showinfo("提示", "请先在【命名规则】中切换为“自定义命名”。")
            return
        text = self.custom_var.get().strip()
        if not text:
            messagebox.showwarning("提示", "请先输入自定义名称。")
            return
        chosen = [f for f in self.files if f["checked"]]
        if not chosen:
            messagebox.showwarning("提示", "请先勾选要应用自定义名称的文件。")
            return
        for f in chosen:
            f["custom"] = text
            f["newname"] = f"{text}{f['ext']}"
        self._refresh()
        self._set_status(f"已将“{text}”应用到 {len(chosen)} 个勾选文件", "#2563eb")

    # ---------- 命名更新（只对勾选文件，预览不加序号） ----------
    def run_update(self):
        chosen = [f for f in self.files if f["checked"]]
        if not chosen:
            messagebox.showinfo("提示", f"请先勾选要命名的文件（点第一列 {UNCHECKED}/{CHECKED}）。")
            return
        rule = self.rule_var.get()
        prefix = self.prefix_var.get()
        suffix = self.suffix_var.get()
        bad = 0
        for f in chosen:
            if rule == "UUID命名":
                base = f["uuid"]
            elif rule == "自定义命名":
                base = f["custom"] or os.path.splitext(f["name"])[0]
            else:
                base = f["sha"]   # 完整 64 位
            # 预览不自动追加序号（真冲突时才在重命名阶段追号）
            f["newname"] = f"{prefix}{base}{suffix}{f['ext']}"
            if name_problem(f["newname"]):
                bad += 1
        self._refresh()
        msg = f"已为 {len(chosen)} 个勾选文件生成预览（无序号，冲突时自动追加）"
        if bad:
            msg += f"；其中 {bad} 个名称不合法，执行时会被跳过"
        self._set_status(msg, "#2563eb")

    # ---------- 批量重命名（真冲突才追加序号） ----------
    def run_rename(self):
        chosen = [f for f in self.files if f["checked"] and f["newname"]]
        if not chosen:
            messagebox.showwarning("警告",
                "没有勾选且已生成预览的文件。\n请先勾选文件，再点【命名更新】生成预览。")
            return
        if not messagebox.askyesno("确认",
                f"将对 {len(chosen)} 个文件执行重命名，是否继续？\n"
                f"（执行后可用「撤销上次重命名」回退）"):
            return
        seq_tpl = self.seq_fmt_var.get().strip() or "（{n:02d}）"
        # 收集每个文件夹里已存在的文件名，以及本批已经用掉的名字
        folder_used = {}
        for f in chosen:
            d = os.path.dirname(f["path"])
            if d not in folder_used:
                try:
                    folder_used[d] = set(os.listdir(d))
                except Exception:
                    folder_used[d] = set()
        ok, fail, skip = 0, 0, 0
        errs = []
        applied = []
        log_rows = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for f in chosen:
            old = f["path"]
            new_dir = os.path.dirname(old)
            new_name = f["newname"]
            new_path = os.path.join(new_dir, new_name)
            try:
                # 1) 文件名合法性（v2.0.0 新增）
                problem = name_problem(new_name)
                if problem:
                    raise ValueError(problem)
                # 2) 路径长度（Windows 传统上限 260，留余量）
                if len(new_path) > 255:
                    raise ValueError(f"目标路径过长（{len(new_path)} 字符）")
                if os.path.abspath(old) == os.path.abspath(new_path):
                    skip += 1
                    log_rows.append([now, old, new_path, "跳过（名称未变）"])
                    continue
                # 3) 冲突才追加序号
                if new_name in folder_used.get(new_dir, set()):
                    base, ext = os.path.splitext(new_name)
                    n = 1
                    while True:
                        try:
                            tag = seq_tpl.format(n=n)
                        except Exception:
                            tag = f"（{n:02d}）"
                        candidate = f"{base}{tag}{ext}"
                        if candidate not in folder_used.get(new_dir, set()):
                            new_name = candidate
                            new_path = os.path.join(new_dir, candidate)
                            break
                        n += 1
                os.rename(old, new_path)
                f["path"] = new_path
                f["name"] = os.path.basename(new_path)
                f["mtime"] = fmt_mtime(new_path)
                folder_used.setdefault(new_dir, set()).add(new_name)
                applied.append((old, new_path))
                ok += 1
                log_rows.append([now, old, new_path, "成功"])
            except Exception as e:
                fail += 1
                errs.append(f"{f['name']}: {e}")
                log_rows.append([now, old, new_path, f"失败：{e}"])
        # 记录本批操作，供撤销使用
        self._last_rename = applied
        log_file = self._write_rename_log(log_rows) if log_rows else None
        self._mark_duplicates()
        self._refresh()
        msg = f"成功：{ok}\n跳过：{skip}\n失败：{fail}"
        if errs:
            msg += "\n\n" + "\n".join(errs[:5])
        if log_file:
            msg += f"\n\n操作日志：{log_file}"
        if applied:
            msg += "\n\n如需回退，点【撤销上次重命名】。"
        messagebox.showinfo("完成", msg)
        self._set_status(f"重命名完成：成功 {ok}，跳过 {skip}，失败 {fail}", "#16a34a")

    def _write_rename_log(self, rows):
        """把本批重命名明细写成 CSV，返回文件路径（失败返回 None）。"""
        try:
            path = os.path.join(log_dir(), f"rename_{datetime.now():%Y%m%d_%H%M%S}.csv")
            with open(path, "w", encoding="utf-8-sig", newline="") as fp:
                w = csv.writer(fp)
                w.writerow(["时间", "原路径", "新路径", "结果"])
                w.writerows(rows)
            return path
        except Exception as e:
            print("写重命名日志失败", e)
            return None

    # ---------- 撤销上次重命名 ----------
    def undo_last_rename(self):
        if not self._last_rename:
            messagebox.showinfo("提示", "没有可撤销的重命名记录（仅支持撤销本程序最近一次操作）。")
            return
        if not messagebox.askyesno("确认",
                f"将把上次重命名的 {len(self._last_rename)} 个文件改回原名，是否继续？"):
            return
        index = {f["path"]: f for f in self.files}
        ok, fail = 0, 0
        errs = []
        for old, new in reversed(self._last_rename):
            try:
                if not os.path.exists(new):
                    raise FileNotFoundError("新文件不存在")
                if os.path.exists(old):
                    raise FileExistsError("原名已被占用")
                os.rename(new, old)
                item = index.get(new)
                if item:
                    item["path"] = old
                    item["name"] = os.path.basename(old)
                    item["mtime"] = fmt_mtime(old)
                ok += 1
            except Exception as e:
                fail += 1
                errs.append(f"{os.path.basename(new)}: {e}")
        self._last_rename = []
        self._mark_duplicates()
        self._refresh()
        msg = f"已还原：{ok}"
        if fail:
            msg += f"\n失败：{fail}\n" + "\n".join(errs[:5])
        messagebox.showinfo("撤销完成", msg)
        self._set_status(f"撤销完成：还原 {ok} 个，失败 {fail} 个",
                         "#16a34a" if not fail else "#dc2626")

    # ---------- 导出 ----------
    def export_list(self):
        if not self.files:
            messagebox.showinfo("提示", "列表为空。")
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            title="导出列表")
        if not p:
            return
        try:
            with open(p, "w", encoding="utf-8-sig", newline="") as fp:
                w = csv.writer(fp)
                w.writerow(["勾选", "文件类型", "文件名称", "大小",
                            "修改日期", "SHA256指纹", "状态", "文件重命名"])
                for f in self.files:
                    w.writerow([
                        "是" if f["checked"] else "否",
                        f["type"], f["name"], fmt_size(f["size"]),
                        f["mtime"], f["sha"], f["status"], f["newname"],
                    ])
            messagebox.showinfo("成功", f"已导出：\n{p}")
        except Exception as e:
            messagebox.showerror("失败", str(e))

    # ---------- 清空 / 状态 ----------
    def clear_list(self):
        if not self.files:
            return
        if messagebox.askyesno("确认", "清空列表？"):
            self.files.clear()
            self._paths.clear()
            self.current_select_idx = None
            self.last_checked_idx = None
            self._refresh()
            self._set_status("已清空", "#2563eb")

    def _set_status(self, text, color):
        self.status_var.set(text)
        try:
            self.status_label.configure(foreground=color)
        except Exception:
            pass

    # ---------- 全局异常兜底 ----------
    def _on_callback_error(self, exc, val, tb):
        import traceback
        traceback.print_exception(exc, val, tb)
        try:
            messagebox.showerror("程序异常",
                                 f"{exc.__name__}: {val}\n\n程序未崩溃，可继续操作；"
                                 f"详细堆栈已输出到控制台。")
            self._set_status(f"操作出错：{val}", "#dc2626")
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
