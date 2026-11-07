# -*- coding: utf-8 -*-
"""v2.0.0 端到端自测：导入 → 查重 → 预览 → 重命名 → 撤销 → 异常分支

用法（必须在带 tkinter 的 Python 下运行，会短暂创建窗口）：
    python tests/test_e2e.py
全部通过时退出码为 0。
"""
import os
import sys
import time
import shutil
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fvr_appdata_")

import tkinter as tk
import main

calls = {"info": [], "warn": [], "error": []}
main.messagebox.showinfo = lambda t, m, **k: calls["info"].append((t, m))
main.messagebox.showwarning = lambda t, m, **k: calls["warn"].append((t, m))
main.messagebox.showerror = lambda t, m, **k: calls["error"].append((t, m))
main.messagebox.askyesno = lambda t, m, **k: True

ok_count = 0
fail_count = 0


def check(name, cond, extra=""):
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  [PASS] {name}")
    else:
        fail_count += 1
        print(f"  [FAIL] {name} {extra}")


def pump(seconds=0.6):
    """模拟 mainloop：驱动 after 回调，让 UI 队列排空。"""
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


root = tk.Tk()
app = main.App(root)
pump(0.3)
print("1. 界面构建")
check("8 列表格", len(app.tree["columns"]) == 8, app.tree["columns"])
check("版本号 v2.0.0", main.APP_VERSION == "Version 2.0.0", main.APP_VERSION)
check("标题含版本", "Version 2.0.0" in root.title(), root.title())

work = tempfile.mkdtemp(prefix="fvr_files_")
p1 = os.path.join(work, "a.txt"); open(p1, "w").write("same")
p2 = os.path.join(work, "b.txt"); open(p2, "w").write("same")
p3 = os.path.join(work, "c.txt"); open(p3, "w").write("diff")

print("2. 导入与查重（含一个不存在的路径，测异常分支）")
app._add([p1, p2, p3, os.path.join(work, "not_exist.txt")])
pump(1.0)
check("scanning 已复位", app.scanning is False)
check("加载 3 个有效文件", len(app.files) == 3, len(app.files))
dups = [f for f in app.files if f["status"] == "重复"]
check("识别出 2 个重复", len(dups) == 2, [f["name"] for f in dups])
check("坏路径计为失败", "读取失败" in app.status_var.get(), app.status_var.get())
check("表格已刷新", len(app.tree.get_children()) == 3, len(app.tree.get_children()))

print("3. 重复导入去重")
app._add([p1])
pump(0.6)
check("同一路径不重复加入", len(app.files) == 3, len(app.files))

print("4. 命名预览（SHA256 完整 64 位）")
app.set_all_checked(True)
app.run_update()
check("预览已生成", all(f["newname"] for f in app.files))
check("哈希为 64 位", len(app.files[0]["sha"]) == 64)
check("预览名 = 哈希 + 扩展名", app.files[0]["newname"] == app.files[0]["sha"] + ".txt")

print("5. 非法文件名拦截（只勾选 1 个文件）")
app.set_all_checked(False)
victim = app.files[0]
victim["checked"] = True
good_name = victim["newname"]
victim["newname"] = "非法:名字.txt"
app.run_rename()
last = calls["info"][-1][1]
check("非法字符被拦截", "失败：1" in last, last)
check("原文件未被改名", os.path.exists(p1))
victim["newname"] = good_name

print("6. 执行重命名（3 个文件，含同哈希冲突追号）")
app.set_all_checked(True)
app.run_update()
app.run_rename()
pump(0.3)
names = sorted(os.listdir(work))
check("磁盘上仍是 3 个文件", len(names) == 3, names)
check("都已改成哈希名", all(len(n) > 60 for n in names), names)
check("同哈希冲突自动追号", any("（01）" in n for n in names), names)
check("撤销栈记录 3 条", len(app._last_rename) == 3, len(app._last_rename))
msg6 = calls["info"][-1][1]
check("提示含日志路径", "操作日志" in msg6)
log_line = [ln for ln in msg6.splitlines() if ln.startswith("操作日志：")]
check("日志文件已生成",
      bool(log_line) and os.path.exists(log_line[0].split("：", 1)[1].strip()),
      log_line)

print("7. 撤销")
app.undo_last_rename()
pump(0.3)
check("文件名已还原", sorted(os.listdir(work)) == ["a.txt", "b.txt", "c.txt"],
      sorted(os.listdir(work)))
check("撤销栈已清空", app._last_rename == [])

print("8. 增量刷新与排序")
app.set_all_checked(False)
app.files[0]["checked"] = True
app._refresh_rows([0])
check("单行刷新生效", app.tree.item("0", "values")[0] == main.CHECKED)
app.sort_by("size")
check("排序后仍可用", len(app.tree.get_children()) == 3)

print("9. 清空")
app.clear_list()
check("列表已清空", app.files == [] and app._paths == set())

print("10. 名称校验函数")
check("正常名通过", main.name_problem("abc.txt") is None)
check("冒号拦截", main.name_problem("a:b.txt") is not None)
check("保留名拦截", main.name_problem("CON.txt") is not None)
check("末尾点拦截", main.name_problem("abc.") is not None)
check("超长拦截", main.name_problem("a" * 260 + ".txt") is not None)

root.destroy()
shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(os.environ["LOCALAPPDATA"], ignore_errors=True)

print(f"\n结果：通过 {ok_count} 项，失败 {fail_count} 项")
sys.exit(1 if fail_count else 0)
